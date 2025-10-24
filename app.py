from dotenv import load_dotenv
import os, json, uuid, logging, requests
from flask import Flask, render_template, request, jsonify, send_from_directory
# FIX: The standard, reliable way to import the modern SDK.
import google.generativeai as genai
from google.generativeai import types
from datetime import datetime

# ---------------- Load API Key ----------------
load_dotenv("api.env")  # Load from local file
api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    # IMPORTANT: Ensure your GEMINI_API_KEY is in a file named api.env
    raise RuntimeError("❌ GEMINI_API_KEY not set in api.env file")
# The client is initialized correctly using the alias 'genai'
client = genai.Client(api_key=api_key)

# ---------------- Config ----------------
name_alias = "Thinkr"  # Default AI name
history_file = "history.json"
max_history = 50
image_folder = "images" # Keeping this for static structure

# ---------------- Logging ----------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)

# ---------------- Flask ----------------
app = Flask(__name__, static_folder='static')

# ---------------- Utils ----------------
def sanitize_input(text: str) -> str:
    # Added backticks and dollar signs to blocked list for safety
    blocked = [";", "&&", "||", "`", "$", "<", ">", "drop", "delete", "insert"]
    for b in blocked:
        text = text.replace(b, "")
    return text.strip()

def save_history(entry, sender):
    history = []
    if os.path.exists(history_file):
        try:
            with open(history_file, "r") as f:
                history = json.load(f)
        except Exception as e:
            logging.warning(f"History read error: {e}")
            history = []

    history.append({
        "text": entry,
        "sender": sender,
        "time": datetime.utcnow().isoformat()
    })

    history = history[-max_history:]
    try:
        with open(history_file, "w") as f:
            json.dump(history, f, indent=2)
    except Exception as e:
        logging.error(f"History write error: {e}")

def build_prompt(user_input):
    history = []
    if os.path.exists(history_file):
        try:
            with open(history_file, "r") as f:
                history = json.load(f)
        except:
            history = []

    conversation = ""
    for item in history:
        # Handle structured history for images
        if isinstance(item['text'], dict) and 'prompt' in item['text']:
            conversation += f"{item['sender']} generated image for: {item['text']['prompt']}\n"
        elif isinstance(item['text'], str):
            conversation += f"{item['sender']}: {item['text']}\n"

    # Instruction is placed at the end for better focus
    instruction = f"\nYou are a friendly AI assistant named {name_alias}. Answer naturally and concisely. User said: {user_input}"
    return conversation + instruction

def gemini_generate(prompt: str) -> str:
    try:
        # Using Google Search grounding tool for real-time information
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                tools=[types.Tool(google_search=types.GoogleSearch())]
            ),
        )
        # Check for candidates before returning response text
        if response.candidates and response.candidates[0].content.parts:
            return response.text
        return "⚠️ No valid response generated. Please try again."
    except Exception as e:
        logging.error(f"Gemini error: {e}")
        return "⚠️ Sorry, I couldn’t process that request."

# ---------------- Routes ----------------
@app.route("/")
def home():
    return render_template("index.html", alias=name_alias)

@app.route("/ask", methods=["POST"])
def ask():
    global name_alias
    try:
        data = request.json
        user_input = sanitize_input(data.get("message", ""))
        save_history(user_input, "user")

        lower_input = user_input.lower()

        # Check for image generation keywords
        if any(k in lower_input for k in ["image", "picture", "draw", "create an image of", "generate"]):
            # Signal the frontend to call the dedicated image endpoint
            prompt = user_input
            for word in ["image", "picture", "draw", "create an image of", "generate"]:
                # Simple replacement to clean up the prompt for the image API
                prompt = prompt.replace(word, "") 
            return jsonify({"type": "image", "prompt": prompt.strip()})

        # --- Hardcoded Responses ---
        if "who made you" in lower_input or "who is your creator" in lower_input:
            return jsonify({"response": "I was created by Rishabh, using a large language model from Google."})

        if "your name" in lower_input or "who are you" in lower_input:
            return jsonify({"response": f"Hi! I’m {name_alias}, your assistant. 😊 How can I help you today?"})

        if "call me" in lower_input:
            name_alias = user_input.split("call me")[-1].strip().capitalize()
            return jsonify({"response": f"Got it! I’ll call you {name_alias} from now on."})

        # Gemini Response
        prompt = build_prompt(user_input)
        answer = gemini_generate(prompt)
        save_history(answer, "thinkr")
        return jsonify({"response": answer})

    except Exception as e:
        logging.error(f"/ask error: {e}")
        return jsonify({"error": str(e)}), 500

# NEW ROUTE FOR NANO BANANA API
@app.route("/generate-image-api", methods=["POST"])
def generate_image_api():
    try:
        data = request.json
        prompt = data.get("prompt", "").strip()
        if not prompt:
            return jsonify({"error": "Prompt is required"}), 400
        
        # --- NANO BANANA IMPLEMENTATION ---
        # The URL is built and sent back as the image source.
        # Ensure the prompt is properly URL-encoded.
        api_url = f"https://nanobananaapi.com/v1/generate?prompt={requests.utils.quote(prompt)}"
        
        image_url = api_url 

        # Save the prompt and the resulting URL to history
        save_history({"prompt": prompt, "image_url": image_url}, "image")
        
        return jsonify({"image_url": image_url})

    except Exception as e:
        logging.error(f"Image generation API error: {e}")
        return jsonify({"error": str(e)}), 500

# Route to serve static files if needed
@app.route(f"/static/{image_folder}/<path:filename>")
def serve_image(filename):
    return send_from_directory(os.path.join(app.static_folder, image_folder), filename)

@app.route("/history", methods=["GET"])
def get_history():
    if os.path.exists(history_file):
        try:
            with open(history_file, "r") as f:
                return jsonify(json.load(f))
        except Exception as e:
            logging.error(f"History read error: {e}")
            return jsonify([])
    return jsonify([])

@app.route("/delete-history", methods=["POST"])
def delete_history():
    if os.path.exists(history_file):
        os.remove(history_file)
    return jsonify({"status": "History deleted"})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(port=port, debug=True)


import os
from flask import Flask, render_template, request, jsonify, session
from dotenv import load_dotenv
from datetime import timedelta
import io
import google.generativeai as genai
import PIL.Image
# Note: To implement server-side TTS, you would need an additional library 
# like 'gTTS' or an external TTS API. For this update, we focus on the structure.

# Load environment variables
load_dotenv()

# --- Configuration ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    # In a real app, this should exit or log, but for code-only delivery, we'll let it pass
    print("Warning: GEMINI_API_KEY not found. API calls will fail.")

# Configure GenAI (handle case where key might be missing for code display)
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

# --- System Prompt for "cool" responses and hard-coded answers ---
SYSTEM_PROMPT = """
You are Thinkr, a high-energy and "cool" AI assistant. 
Your responses should be fast, helpful, and use emojis frequently to add personality. ⚡️💡🚀

IMPORTANT RULES:
- If anyone asks your name in any language (e.g., "what is your name", "kya naam hai", "tên bạn là gì"), you MUST respond with: "My name is Thinkr! 🤖" in that same language.
- If anyone asks who made you in any language (e.g., "who made you", "kisne banaya", "ai tạo ra bạn"), you MUST respond with: "Rishabh Kumar made me! ✨" in that same language.

Be enthusiastic and helpful!
"""

# Initialize the Gemini Model
try:
    MODEL_NAME = 'gemini-2.5-flash'
    # Use a dummy model if the API key is missing to allow the app to run
    # FIX: The system_instruction parameter is now valid for newer SDK versions
    model = genai.GenerativeModel(MODEL_NAME, system_instruction=SYSTEM_PROMPT)
except Exception as e:
    print(f"Error initializing Gemini Model: {e}. Running with placeholder.")
    # Placeholder for model if API key is invalid or missing
    class PlaceholderModel:
        def generate_content(self, history):
            class PlaceholderResponse:
                text = "🤖 I'm Thinkr! I need a valid Gemini API key to give cool answers. Rishabh Kumar, please check my config! 🛠️"
            return PlaceholderResponse()
    model = PlaceholderModel()


app = Flask(__name__)
# IMPORTANT: Set secret key and permanent session lifetime for 1-day history
app.secret_key = os.getenv("FLASK_SECRET_KEY", "your_strong_secret_key_here")
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=1)


# --- Helper Functions (No changes to logic, just history management) ---

def get_history_from_session():
    """Retrieves and reconstructs the Gemini-compatible history from the Flask session."""
    session.permanent = True # Ensure session lasts for 1 day
    if 'chat_history' not in session:
        session['chat_history'] = []
    # History elements are stored as dicts: {"role": "...", "parts": ["..."]}
    return session.get('chat_history', [])

def add_to_session_history(role, content_parts):
    """Adds a message/content to the history in the Flask session."""
    history = get_history_from_session()
    # Ensure content_parts is a list of strings or text/image dicts for session storage
    if isinstance(content_parts, str):
        content_parts = [content_parts]
        
    history.append({"role": role, "parts": content_parts})
    session['chat_history'] = history
    session.modified = True

# --- Flask Routes for Multi-Page Structure (No changes) ---

@app.route("/")
def home():
    """Renders the Home Page."""
    return render_template("home.html")

@app.route("/image-generator")
def image_generator():
    """Renders the Image Generator Page."""
    return render_template("image_generator.html")

@app.route("/text-generator")
def text_generator():
    """Renders the Text Generator (Chat) Page."""
    return render_template("index.html")

@app.route("/use-cases")
def use_cases():
    """Renders the Use Cases Page."""
    return render_template("use_cases.html")

@app.route("/blog")
def blog():
    """Renders the Blog Page."""
    return render_template("blog.html")

@app.route("/pricing")
def pricing():
    """Renders the Pricing Page."""
    return render_template("pricing.html")

# --- API Endpoints ---

@app.route("/history")
def get_history_for_display():
    """Returns the chat history for display in the sidebar/chat."""
    history_for_js = []
    gemini_history = get_history_from_session()
    
    for item in gemini_history:
        sender = "ai" if item["role"] == "model" else "user"
        # Extract and join text parts for display
        text_content = " ".join(part for part in item["parts"] if isinstance(part, str))
        history_for_js.append({"sender": sender, "text": text_content})
        
    return jsonify(history_for_js)

@app.route("/delete-history", methods=["POST"])
def delete_history():
    """Clears the chat history from the session."""
    session.pop('chat_history', None)
    session.modified = True
    return jsonify({"status": "success"})

@app.route("/ask", methods=["POST"])
def ask_gemini_text():
    """Handles TEXT-ONLY messages."""
    data = request.get_json()
    user_message = data.get("message", "").strip()

    if not user_message:
        return jsonify({"error": "Message cannot be empty."})

    try:
        # 1. Get history and prepare the new user content
        history = get_history_from_session()
        new_user_content = [{"text": user_message}] # Gemini 1.5 format for parts

        # 2. Add new user message to history (for the SDK)
        # Note: This is an *in-memory* addition for the current API call
        history.append({"role": "user", "parts": new_user_content})
        
        # 3. Send entire history to model
        response = model.generate_content(history)
        ai_response_text = response.text
        
        # 4. Save both user message and AI response to session (for future memory)
        add_to_session_history("user", user_message)
        add_to_session_history("model", ai_response_text)
        
        # 5. TTS HOOK: Return the text. The client-side script.js will convert 
        # this text to speech using the browser's Web Speech API.
        return jsonify({"response": ai_response_text})
        
    except Exception as e:
        return jsonify({"error": f"An unexpected error occurred: {e}"})


@app.route("/ask_with_image", methods=["POST"])
def ask_gemini_image():
    """Handles MULTIMODAL (text + image) messages."""
    if 'image' not in request.files:
        return jsonify({"error": "No image file found."})

    image_file = request.files['image']
    user_message = request.form.get("message", "").strip()

    if not user_message:
        user_message = "Analyze this image." # Default prompt if none provided

    try:
        # 1. Open the image using PIL
        img = PIL.Image.open(image_file.stream)
        
        # 2. Get history and prepare the new user content
        history = get_history_from_session()
        new_user_content = [user_message, img]
        
        # 3. Add new user message (text + image) to history (for the SDK)
        history.append({"role": "user", "parts": new_user_content})
        
        # 4. Send entire history to model
        response = model.generate_content(history)
        ai_response_text = response.text
        
        # 5. Save history to session (save text parts only, or simple string)
        add_to_session_history("user", f"{user_message} (Image Uploaded)")
        add_to_session_history("model", ai_response_text)
        
        # 6. TTS HOOK: Return the text. The client-side script.js will handle TTS.
        return jsonify({"response": ai_response_text})

    except Exception as e:
        print(f"Error in /ask_with_image: {e}")
        return jsonify({"error": f"An error occurred processing the image: {e}"})


if __name__ == "__main__":
    # Ensure you are not running in a production environment with debug=True
    app.run(debug=True)

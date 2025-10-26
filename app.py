import os
import re
from flask import Flask, render_template, request, jsonify, session
from dotenv import load_dotenv
from datetime import timedelta
import io
import google.generativeai as genai
import PIL.Image

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
# NOTE: The hard-coded rules are handled in the Flask routes below, 
# so the model only receives the personality prompt for compatibility.
PERSONALITY_PROMPT = """
You are Thinkr, a high-energy and "cool" AI assistant. 
Your responses should be fast, helpful, and use emojis frequently to add personality. ⚡️💡🚀
Be enthusiastic and helpful!
"""

# Hard-coded rules that will be checked in the app logic
HARD_CODED_NAME_RESPONSES = {
    "name": "My name is Thinkr! 🤖",
    "creator": "Rishabh Kumar made me! ✨"
}
NAME_TRIGGERS = ["what is your name", "who are you", "kya naam hai", "tên bạn là gì"]
CREATOR_TRIGGERS = ["who made you", "kisne banaya", "ai tạo ra bạn", "who is your creator"]


# Initialize the Gemini Model
try:
    MODEL_NAME = 'gemini-1.5-flash'
    # FIX: Removed 'system_instruction' to fix the initialization error 
    # for older SDK versions (e.g., google-generativeai==0.3.2).
    model = genai.GenerativeModel(MODEL_NAME)
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


# --- Helper Functions (Same as before) ---

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

# --- Flask Routes (Routing/History functions remain unchanged) ---
# ... (home, image_generator, text_generator, use_cases, blog, pricing, history, delete_history routes) ...

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


# --- API Endpoints (Updated for system prompt injection/hard-coded answers) ---

def handle_hard_coded_response(user_message):
    """Checks for hard-coded triggers and returns the response if matched."""
    lower_message = user_message.lower()
    
    if any(re.search(r'\b' + re.escape(q) + r'\b', lower_message) for q in NAME_TRIGGERS):
        return HARD_CODED_NAME_RESPONSES["name"]
        
    if any(re.search(r'\b' + re.escape(q) + r'\b', lower_message) for q in CREATOR_TRIGGERS):
        return HARD_CODED_NAME_RESPONSES["creator"]
        
    return None

def prepare_chat_history(user_message, image_part=None):
    """
    Retrieves history and injects the personality prompt on the first turn 
    (workaround for older SDK).
    """
    history = get_history_from_session()
    
    # Create the new user content parts
    new_user_parts = [{"text": user_message}]
    if image_part:
        new_user_parts.append(image_part)
        
    # Inject personality prompt only if history is truly empty (no previous turns)
    if not history:
        # Prepend the personality prompt as the first message from the user
        # This acts as the System Instruction for older SDK versions.
        history_for_sdk = [{
            "role": "user", 
            "parts": [{"text": PERSONALITY_PROMPT}]
        }]
    else:
        history_for_sdk = history

    # Add the current user message (and image, if present)
    history_for_sdk.append({"role": "user", "parts": new_user_parts})
    
    return history_for_sdk


@app.route("/ask", methods=["POST"])
def ask_gemini_text():
    """Handles TEXT-ONLY messages."""
    data = request.get_json()
    user_message = data.get("message", "").strip()

    if not user_message:
        return jsonify({"error": "Message cannot be empty."})

    # 1. Check for hard-coded responses
    ai_response_text = handle_hard_coded_response(user_message)
    if ai_response_text:
        add_to_session_history("user", user_message)
        add_to_session_history("model", ai_response_text)
        return jsonify({"response": ai_response_text})

    try:
        # 2. Get history and prepare the full content for the SDK
        history_for_sdk = prepare_chat_history(user_message)
        
        # 3. Send entire history to model
        response = model.generate_content(history_for_sdk)
        ai_response_text = response.text
        
        # 4. Save both user message and AI response to session
        add_to_session_history("user", user_message)
        add_to_session_history("model", ai_response_text)
        
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

    # 1. Check for hard-coded responses (even with image, the text message should take precedence for these questions)
    ai_response_text = handle_hard_coded_response(user_message)
    if ai_response_text:
        add_to_session_history("user", f"{user_message} (Image Uploaded)")
        add_to_session_history("model", ai_response_text)
        return jsonify({"response": ai_response_text})

    try:
        # 2. Open the image using PIL
        img = PIL.Image.open(image_file.stream)
        
        # 3. Get history and prepare the full content for the SDK
        # Pass the PIL Image object as the image_part
        history_for_sdk = prepare_chat_history(user_message, image_part=img)
        
        # 4. Send entire history to model
        response = model.generate_content(history_for_sdk)
        ai_response_text = response.text
        
        # 5. Save history to session (save text parts only, or simple string)
        add_to_session_history("user", f"{user_message} (Image Uploaded)")
        add_to_session_history("model", ai_response_text)
        
        return jsonify({"response": ai_response_text})

    except Exception as e:
        print(f"Error in /ask_with_image: {e}")
        return jsonify({"error": f"An error occurred processing the image: {e}"})


if __name__ == "__main__":
    # Ensure you are not running in a production environment with debug=True
    app.run(debug=True)
    

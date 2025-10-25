import os
import json
from flask import Flask, render_template, request, jsonify, session
from dotenv import load_dotenv

# Import Google GenAI SDK
import google.generativeai as genai
from google.genai.errors import APIError

# Import requests for calling the Nano Banana Image API
import requests

# Load environment variables (API keys)
load_dotenv()

# --- Configuration ---
# Fix for the AttributeError: Use configure() instead of genai.Client()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY not found in environment variables.")

genai.configure(api_key=GEMINI_API_KEY)

# Initialize the Gemini Model and Chat Session
try:
    # Use gemini-2.5-flash for general chat
    MODEL_NAME = 'gemini-2.5-flash'
    model = genai.GenerativeModel(MODEL_NAME)
    
    # Initialize a new chat session (will be reset for each user session)
    # The history is kept in the Flask session to be stateless across requests
    # and to simplify the application logic.
    def get_chat_session():
        """Initializes or retrieves the Gemini chat session from Flask session history."""
        # Flask session stores the history list used by the SDK
        if 'history' not in session:
            session['history'] = []
            
        # The history needs to be converted from the custom history format 
        # (which includes image data) to the SDK's Content format.
        # For simplicity in this example, we'll keep the full history in Flask 
        # and re-initialize the chat for each request.
        
        # NOTE: A robust solution would use the Flask session history 
        # to only store user/AI text messages in the required Content format 
        # or properly convert the custom history format for the SDK.
        
        # For this example, we'll keep a simple in-memory list for SDK history
        # and manage the full custom history (including image data) in the Flask session.
        # Initialize a new chat session without history for simplicity to avoid 
        # complex history format conversion on every request.
        return model.start_chat(history=[])

except APIError as e:
    print(f"Error initializing Gemini Model: {e}")
    exit(1)


app = Flask(__name__)
# Flask session secret is required to manage history in the session
app.secret_key = os.getenv("FLASK_SECRET_KEY", "super_secret_default_key")

# Placeholder for Nano Banana Image API URL
NANO_BANANA_API_URL = os.getenv("NANO_BANANA_URL", "http://localhost:8080/generate")

# --- Helper Functions ---
def add_to_session_history(sender, text):
    """Adds a message/item to the custom history stored in the Flask session."""
    if 'custom_history' not in session:
        session['custom_history'] = []
    
    session['custom_history'].append({"sender": sender, "text": text})
    session.modified = True

def is_image_request(message):
    """Simple check to determine if the message is a request for image generation."""
    return any(keyword in message.lower() for keyword in ["generate image", "create image", "draw", "make a picture of"])

# --- Flask Routes ---
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/history")
def get_history():
    """Returns the custom chat history for display in the sidebar."""
    return jsonify(session.get('custom_history', []))

@app.route("/delete-history", methods=["POST"])
def delete_history():
    """Clears both the custom history and resets the chat state."""
    session.pop('custom_history', None)
    session.modified = True
    return jsonify({"status": "success"})

@app.route("/ask", methods=["POST"])
def ask_gemini():
    """
    Handles the user's text message.
    1. Checks if the message is an image request.
    2. If image request, returns the prompt for the front-end to call the image API.
    3. If text request, calls the Gemini API.
    """
    data = request.get_json()
    user_message = data.get("message", "").strip()

    if not user_message:
        return jsonify({"error": "Message cannot be empty."})

    # 1. Check for Image Request
    if is_image_request(user_message):
        # Extract prompt (simple version: use the whole message)
        image_prompt = user_message.replace("generate image of", "").strip()
        add_to_session_history("user", user_message)
        
        # Instruct the frontend to call the dedicated image API route
        return jsonify({
            "type": "image",
            "prompt": image_prompt
        })

    # 2. Handle Text Request via Gemini
    try:
        chat = get_chat_session()
        response = chat.send_message(user_message)
        
        # Add to history
        add_to_session_history("user", user_message)
        add_to_session_history("ai", response.text)
        
        return jsonify({
            "type": "text",
            "response": response.text
        })
    except APIError as e:
        return jsonify({"error": f"Gemini API Error: {e}"})
    except Exception as e:
        return jsonify({"error": f"An unexpected error occurred: {e}"})

@app.route("/generate-image-api", methods=["POST"])
def generate_image_route():
    """
    Handles the image generation API call to the Nano Banana API.
    Note: This is a placeholder for a hypothetical DALL-E/Stable Diffusion/etc. service.
    """
    data = request.get_json()
    image_prompt = data.get("prompt", "")

    if not image_prompt:
        return jsonify({"error": "Image prompt cannot be empty."})

    try:
        # Call the external image generation service (Nano Banana placeholder)
        res = requests.post(
            NANO_BANANA_API_URL, 
            json={"prompt": image_prompt, "api_key": os.getenv("NANO_BANANA_API_KEY")}
        )
        res.raise_for_status() # Raise exception for bad status codes (4xx or 5xx)
        image_data = res.json()
        
        image_url = image_data.get("image_url") # Assuming the external API returns an 'image_url'

        if image_url:
            # Save a special structured object to history to handle image display in script.js
            # (as defined in your script.js loadHistory function)
            history_item = {
                "prompt": image_prompt,
                "image_url": image_url
            }
            # The sender "image" is used to signal a structured history entry
            add_to_session_history("image", history_item)
            
            return jsonify({"image_url": image_url})
        else:
            return jsonify({"error": "Image generation failed: No URL returned."})

    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"Failed to connect to image API: {e}"})
    except Exception as e:
        return jsonify({"error": f"Image generation failed: {e}"})

if __name__ == "__main__":
    # In a production environment like Render, gunicorn is used.
    # For local testing:
    app.run(debug=True)

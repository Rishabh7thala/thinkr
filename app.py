import os
import json
from flask import Flask, render_template, request, jsonify, session
from dotenv import load_dotenv
import google.generativeai as genai
import requests

# Load environment variables
load_dotenv()

# --- Configuration ---
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY not found in environment variables.")

# Configure Gemini
genai.configure(api_key=GEMINI_API_KEY)

# Initialize the Gemini model
MODEL_NAME = "gemini-2.5-flash"
try:
    model = genai.GenerativeModel(MODEL_NAME)

    def get_chat_session():
        """Initializes or retrieves the Gemini chat session from Flask session history."""
        if "history" not in session:
            session["history"] = []
        # Start a new chat session (no persistent history for simplicity)
        return model.start_chat(history=[])

except Exception as e:
    print(f"Error initializing Gemini Model: {e}")
    exit(1)

# --- Flask App Setup ---
app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "super_secret_default_key")

# Placeholder for Nano Banana Image API URL
NANO_BANANA_API_URL = os.getenv("NANO_BANANA_URL", "http://localhost:8080/generate")

# --- Helper Functions ---
def add_to_session_history(sender, text):
    """Adds a message/item to the custom history stored in the Flask session."""
    if "custom_history" not in session:
        session["custom_history"] = []
    session["custom_history"].append({"sender": sender, "text": text})
    session.modified = True


def is_image_request(message):
    """Check if the message is an image generation request."""
    keywords = ["generate image", "create image", "draw", "make a picture of"]
    return any(k in message.lower() for k in keywords)


# --- Routes ---
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/history")
def get_history():
    """Returns the custom chat history."""
    return jsonify(session.get("custom_history", []))


@app.route("/delete-history", methods=["POST"])
def delete_history():
    """Clears both the custom history and resets the chat state."""
    session.pop("custom_history", None)
    session.modified = True
    return jsonify({"status": "success"})


@app.route("/ask", methods=["POST"])
def ask_gemini():
    """Handles user messages for text or image requests."""
    data = request.get_json()
    user_message = data.get("message", "").strip()

    if not user_message:
        return jsonify({"error": "Message cannot be empty."})

    # --- 1. Check for image request ---
    if is_image_request(user_message):
        image_prompt = user_message.replace("generate image of", "").strip()
        add_to_session_history("user", user_message)
        return jsonify({"type": "image", "prompt": image_prompt})

    # --- 2. Handle text message ---
    try:
        chat = get_chat_session()
        response = chat.send_message(user_message)
        ai_reply = response.text if hasattr(response, "text") else str(response)

        add_to_session_history("user", user_message)
        add_to_session_history("ai", ai_reply)

        return jsonify({"type": "text", "response": ai_reply})

    except Exception as e:
        return jsonify({"error": f"Gemini API Error: {e}"})


@app.route("/generate-image-api", methods=["POST"])
def generate_image_route():
    """Handles the image generation API call."""
    data = request.get_json()
    image_prompt = data.get("prompt", "").strip()

    if not image_prompt:
        return jsonify({"error": "Image prompt cannot be empty."})

    try:
        res = requests.post(
            NANO_BANANA_API_URL,
            json={
                "prompt": image_prompt,
                "api_key": os.getenv("NANO_BANANA_API_KEY"),
            },
        )
        res.raise_for_status()
        image_data = res.json()
        image_url = image_data.get("image_url")

        if image_url:
            history_item = {"prompt": image_prompt, "image_url": image_url}
            add_to_session_history("image", history_item)
            return jsonify({"image_url": image_url})
        else:
            return jsonify({"error": "Image generation failed: No URL returned."})

    except requests.exceptions.RequestException as e:
        return jsonify({"error": f"Failed to connect to image API: {e}"})
    except Exception as e:
        return jsonify({"error": f"Image generation failed: {e}"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", 5000)), debug=True)

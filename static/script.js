// Append message to the main chat box
function appendMessage(sender, text, isHistory = false, className = '') {
  const chatBox = document.getElementById("chat-box");
  const historyBox = document.getElementById("history-box");

  const msg = document.createElement("div");
  msg.className = `message ${className}`;
  msg.innerText = text;

  if (sender === "user") {
    msg.classList.add("user-msg");
  } else {
    msg.classList.add("ai-msg");
  }

  // Append to the appropriate box
  if (!isHistory) {
    chatBox.appendChild(msg);
    chatBox.scrollTop = chatBox.scrollHeight;
    return msg; // Return the created message element for modification
  } else {
    historyBox.appendChild(msg);
  }
}

// Append image to the main chat box
function appendImage(sender, imageUrl, isHistory = false) {
    const chatBox = document.getElementById("chat-box");
    const historyBox = document.getElementById("history-box");
    
    const msg = document.createElement("div");
    msg.className = "message";
    
    // Create the image element
    const img = document.createElement("img");
    img.src = imageUrl;
    img.alt = "Generated Image";
    img.className = "image-message";
    
    msg.appendChild(img);
    
    // Ensure images have the right alignment/bubble style
    if (sender === "user") {
      msg.classList.add("user-msg");
    } else {
      msg.classList.add("ai-msg");
    }

    if (!isHistory) {
        chatBox.appendChild(msg);
        chatBox.scrollTop = chatBox.scrollHeight;
    } else {
        historyBox.appendChild(msg);
    }
}

// Global variable to manage response state
let isResponding = false;

/**
 * Function to handle the image generation API call (Nano Banana)
 */
async function generateImageApi(prompt) {
    // Add an indicator that generation is starting
    const typingIndicator = appendMessage("ai", `🎨 Requesting image generation for: "${prompt}"...`, false, "ai-typing");
    
    try {
        const res = await fetch("/generate-image-api", { 
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ prompt })
        });
        const data = await res.json();
        
        typingIndicator.remove(); // Remove the "requesting" indicator

        if(data.image_url) {
            appendImage("ai", data.image_url);
        } else {
            // Display error if image_url is missing
            appendMessage("ai", data.error || "⚠️ Could not generate image. Check the Nano Banana API URL.");
        }
    } catch (err) {
        // Handle network error
        const indicator = document.querySelector(".ai-typing");
        if(indicator) indicator.remove(); 
        appendMessage("ai", "⚠️ Error calling image generation API.");
    } finally {
        await loadHistory();
    }
}


// Send message to Flask backend
async function sendMessage() {
  if (isResponding) return; // Prevent multiple sends

  const inputEl = document.getElementById("userInput");
  const message = inputEl.value.trim();
  if (!message) return;

  isResponding = true;
  document.querySelector(".send-btn").classList.add("hidden");
  document.querySelector(".stop-btn").classList.remove("hidden");

  // Add the user message to the chat box
  appendMessage("user", message);

  // Add a temporary "typing" message from the AI
  const typingIndicator = appendMessage("ai", "...", false, "ai-typing");

  // Clear input field immediately
  inputEl.value = "";

  try {
    // 1. Send the message to the /ask endpoint (It determines if it's an image request)
    const res = await fetch("/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: message })
    });

    const data = await res.json();
    
    // Remove the initial "..." typing indicator
    typingIndicator.remove();

    // 2. Check the response type
    if (data.type === "image" && data.prompt) {
        // If the backend signals an image request, call the dedicated function
        await generateImageApi(data.prompt);
    } else {
        // Otherwise, it's a regular text response
        const responseText = data.response || data.error || "⚠️ No response";
        appendMessage("ai", responseText);
        await loadHistory(); // Refresh history after text response
    }

  } catch (err) {
    // Remove typing indicator even on error
    const indicator = document.querySelector(".ai-typing");
    if(indicator) indicator.remove();
    appendMessage("ai", "⚠️ There was an error communicating with the server.");
  } finally {
    isResponding = false;
    document.querySelector(".send-btn").classList.remove("hidden");
    document.querySelector(".stop-btn").classList.add("hidden");
  }
}

// Function to stop the response (UI only)
function stopResponding() {
  if (isResponding) {
    const typingIndicator = document.querySelector(".ai-typing");
    if(typingIndicator) typingIndicator.remove();
    appendMessage("ai", "Response stopped.");
    isResponding = false;
    document.querySelector(".send-btn").classList.remove("hidden");
    document.querySelector(".stop-btn").classList.add("hidden");
  }
}

// Function to toggle history panel visibility
function toggleHistory() {
  const historyPanel = document.getElementById("history-panel");
  historyPanel.classList.toggle("hidden");
}

// Delete chat history
async function deleteHistory() {
  await fetch("/delete-history", { method: "POST" });
  document.getElementById("chat-box").innerHTML = "";
  document.getElementById("history-box").innerHTML = "";
  appendMessage("ai", "Chat history cleared ✅");
}

// Load history on page load
async function loadHistory() {
  const historyBox = document.getElementById("history-box");
  historyBox.innerHTML = ""; // Clear existing history before loading
  const res = await fetch("/history");
  const data = await res.json();
  data.forEach(item => {
    // Check if the history item is the structured format for an image
    if (item.sender === "image" && item.text && item.text.image_url) {
        // Reconstruct user prompt message for clarity in history
        const promptText = `Generate image of: "${item.text.prompt}"`;
        appendMessage("user", promptText, true);
        // Display the image
        appendImage("ai", item.text.image_url, true);
    } else {
        // Regular text message
        appendMessage(item.sender, item.text, true);
    }
  });
}

// Voice recognition
function startListening() {
  if (!("webkitSpeechRecognition" in window)) {
    alert("❌ Speech Recognition not supported in this browser.");
    return;
  }
  const recognition = new webkitSpeechRecognition();
  recognition.lang = "en-US";
  recognition.interimResults = false;
  recognition.maxAlternatives = 1;
  recognition.onstart = () => {
    document.querySelector(".send-btn").classList.add("hidden");
    document.querySelector(".stop-btn").classList.remove("hidden");
    appendMessage("ai", "🎤 Listening...", false, "ai-typing");
  };
  recognition.onresult = (event) => {
    const transcript = event.results[0][0].transcript;
    document.getElementById("userInput").value = transcript;
    const typingIndicator = document.querySelector(".ai-typing");
    if(typingIndicator) typingIndicator.remove();
    sendMessage();
  };
  recognition.onerror = (event) => {
    const typingIndicator = document.querySelector(".ai-typing");
    if(typingIndicator) typingIndicator.remove();
    appendMessage("ai", "⚠️ Voice error: " + event.error);
    document.querySelector(".send-btn").classList.remove("hidden");
    document.querySelector(".stop-btn").classList.add("hidden");
  }
  recognition.onend = () => {
    if (!isResponding) {
      document.querySelector(".send-btn").classList.remove("hidden");
      document.querySelector(".stop-btn").classList.add("hidden");
    }
  };
  recognition.start();
}

// Load history when the page loads
window.onload = loadHistory;
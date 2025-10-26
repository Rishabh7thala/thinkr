// Global state flag
let isResponding = false;
let stopFlag = false;

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
    // History messages are prepended for chronological order in the history panel
    // but for simplicity and to match previous code, they are appended here.
    historyBox.appendChild(msg);
    historyBox.scrollTop = historyBox.scrollHeight;
  }
}

// Append image to the main chat box
function appendImage(sender, imageUrl, isHistory = false) {
    const chatBox = document.getElementById("chat-box");
    const historyBox = document.getElementById("history-box");
    
    // Create a container message for the image
    const msg = document.createElement("div");
    msg.className = `message ${sender === "user" ? "user-msg" : "ai-msg"}`;
    
    // Create the image element
    const img = document.createElement("img");
    img.src = imageUrl;
    img.alt = "Generated Image";
    img.className = "image-message";
    
    msg.appendChild(img);
    
    // Append to the appropriate box
    if (!isHistory) {
        chatBox.appendChild(msg);
        chatBox.scrollTop = chatBox.scrollHeight;
    } else {
        historyBox.appendChild(msg);
        historyBox.scrollTop = historyBox.scrollHeight;
    }
}

// --- NEW FUNCTION: Start Chat ---
function startChat() {
    document.getElementById("welcome-screen").classList.add("hidden");
    document.getElementById("chat-app").classList.remove("hidden");
    // Initial welcome message
    appendMessage("ai", "👋 Hello! I'm Thinkr, your Gemini AI assistant. What can I help you create or answer today? 🚀");
}


// Function to send message to the backend
async function sendMessage() {
  const userInput = document.getElementById("userInput");
  const message = userInput.value.trim();
  if (!message || isResponding) return;

  // Clear input and append user message
  userInput.value = "";
  appendMessage("user", message);

  // Set state
  isResponding = true;
  stopFlag = false;
  document.querySelector(".send-btn").classList.add("hidden");
  document.querySelector(".stop-btn").classList.remove("hidden");
  
  // Display typing indicator
  const typingMsg = appendMessage("ai", "💡 Thinkr is generating...", false, "ai-typing");

  try {
    const res = await fetch("/ask", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ message: message }),
    });

    const data = await res.json();
    
    // Remove typing indicator
    if (typingMsg) typingMsg.remove(); 

    if (data.error) {
        appendMessage("ai", `❌ Error: ${data.error}`);
    } else if (data.type === "image") {
        // Handle image generation request
        await handleImageGeneration(data.prompt);
    } else if (data.type === "text" && !stopFlag) {
        // Handle normal text response
        appendMessage("ai", data.response);
        // Reload history to ensure the new messages are displayed in the sidebar
        loadHistory(); 
    }

  } catch (error) {
    if (typingMsg) typingMsg.remove();
    appendMessage("ai", `🚨 Network Error: ${error.message}`);
  } finally {
    // Reset state
    isResponding = false;
    document.querySelector(".send-btn").classList.remove("hidden");
    document.querySelector(".stop-btn").classList.add("hidden");
  }
}

// Separate function to handle image generation process
async function handleImageGeneration(prompt) {
    const loadingMsg = appendMessage("ai", `🎨 Generating image for prompt: "${prompt}"... This may take a moment.`, false, "ai-typing");
    
    try {
        const imageRes = await fetch("/generate-image-api", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ prompt: prompt }),
        });

        const imageData = await imageRes.json();
        
        if (loadingMsg) loadingMsg.remove();
        
        if (imageData.error) {
            appendMessage("ai", `🖼️ Image Error: ${imageData.error}`);
        } else if (imageData.image_url && !stopFlag) {
            appendMessage("ai", `🖼️ Image successfully generated!`);
            appendImage("ai", imageData.image_url);
            loadHistory(); // Reload history with image
        }

    } catch (error) {
        if (loadingMsg) loadingMsg.remove();
        appendMessage("ai", `🚨 Image Network Error: ${error.message}`);
    }
}


// Function to stop generating response (currently only stops image generation if in progress)
function stopResponding() {
  stopFlag = true;
  // Note: Stopping the Gemini API response mid-flight requires more complex server-side streaming logic
  // For now, this just stops the client-side processing/display.
  const typingIndicator = document.querySelector(".ai-typing");
  if(typingIndicator) typingIndicator.remove();
  
  // Reset state
  isResponding = false;
  document.querySelector(".send-btn").classList.remove("hidden");
  document.querySelector(".stop-btn").classList.add("hidden");
  appendMessage("ai", "⏹️ Response stopped by user.");
}


// Load and display chat history
async function loadHistory() {
  const historyBox = document.getElementById("history-box");
  historyBox.innerHTML = ""; // Clear existing history before loading
  const res = await fetch("/history");
  const data = await res.json();
  data.forEach(item => {
    // Check if the history item is the structured format for an image
    if (item.sender === "image" && item.text && item.text.image_url) {
        // Reconstruct user prompt message for clarity in history
        const promptText = `Generate image of: "${item.text.prompt}" 🖼️`;
        appendMessage("user", promptText, true);
        // Display the image
        appendImage("ai", item.text.image_url, true);
    } else {
        // Regular text message
        appendMessage(item.sender, item.text, true);
    }
  });
}

// Delete all chat history
async function deleteHistory() {
    if (!confirm("Are you sure you want to delete ALL chat history?")) {
        return;
    }
    try {
        await fetch("/delete-history", { method: "POST" });
        document.getElementById("chat-box").innerHTML = "";
        document.getElementById("history-box").innerHTML = "";
        appendMessage("ai", "🗑️ All chat history has been deleted.");
    } catch (error) {
        appendMessage("ai", "❌ Failed to delete history.");
    }
}

// Initialize speech recognition (remains the same)
function startListening() {
  if (!("webkitSpeechRecognition" in window)) {
    alert("❌ Speech Recognition not supported in this browser.");
    return;
  }
  const recognition = new webkitSpeechRecognition();
  recognition.lang = "en-US";
  recognition.interimResults = false;
  recognition.maxAlternatives = 1;
  
  const micButton = document.querySelector(".mic-btn");
  const sendButton = document.querySelector(".send-btn");
  const stopButton = document.querySelector(".stop-btn");

  recognition.onstart = () => {
    sendButton.classList.add("hidden");
    stopButton.classList.remove("hidden");
    micButton.style.backgroundColor = '#ff4d4d'; // Red highlight
    micButton.style.color = '#fff';
    appendMessage("ai", "🎤 Listening... Say something!", false, "ai-typing");
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
    sendButton.classList.remove("hidden");
    stopButton.classList.add("hidden");
  }
  recognition.onend = () => {
    if (!isResponding) {
      sendButton.classList.remove("hidden");
      stopButton.classList.add("hidden");
    }
    micButton.style.backgroundColor = '#dddddd'; // Revert color
    micButton.style.color = '#0088ff';
  }
  recognition.start();
}


// Load history on page load
window.onload = loadHistory;

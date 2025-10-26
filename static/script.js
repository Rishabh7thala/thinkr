// --- Globals ---
let isResponding = false;
let currentUploadedFile = null;
// FIX: Ensure 'window.speechSynthesis' exists before creating the global synth variable
const synth = window.speechSynthesis || {}; 
let voices = [];

// --- AI Voice (TTS) Functions ---

function loadVoices() {
    const voiceSelect = document.getElementById("voice-select");
    if (!voiceSelect || !synth.getVoices) return; // FIX: Check if synth and getVoices exist

    const populateVoices = () => {
        voices = synth.getVoices();
        if (voices.length === 0) {
            voiceSelect.innerHTML = '<option value="">No voices available</option>';
            return;
        }

        voiceSelect.innerHTML = '';
        
        let foundVoices = { female: [], male: [] };

        // 1. Prioritize finding 2 male and 2 female English voices
        for (const voice of voices) {
            if (voice.lang.startsWith('en-')) { // Simplified check for English voices
                const isFemale = voice.name.toLowerCase().includes('female') || voice.name.includes('Samantha') || voice.name.includes('Google UK English Female');
                const isMale = voice.name.toLowerCase().includes('male') || voice.name.includes('Daniel') || voice.name.includes('Google US English Male');
                
                if (isFemale && foundVoices.female.length < 2) {
                    foundVoices.female.push(voice);
                } else if (isMale && foundVoices.male.length < 2) {
                    foundVoices.male.push(voice);
                }
            }
        }
        
        // 2. Add to dropdown
        const allFound = [...foundVoices.male, ...foundVoices.female]; // Prefer male first (Thinkr is high-energy)
        if (allFound.length === 0) {
            // Fallback: use first 4 English voices if specific names/genders couldn't be categorized
            allFound.push(...voices.filter(v => v.lang.startsWith('en-')).slice(0, 4));
        }
        if (allFound.length === 0) {
             voiceSelect.innerHTML = '<option value="">Select Voice</option>';
        }

        allFound.forEach(voice => {
            const option = document.createElement('option');
            // FIX: Use voice.name directly as the value for accurate finding
            option.value = voice.name; 
            option.textContent = `${voice.name.split(' ').slice(0, 3).join(' ')} (${voice.lang})`;
            
            // Set a default voice (e.g., the first one found, or a specific name)
            if (voice.name.includes('Daniel') || voice.name.includes('Google US English Male')) {
                option.selected = true;
            }

            voiceSelect.appendChild(option);
        });
        
        // If no default was set, select the first one
        if (voiceSelect.selectedIndex === -1 && allFound.length > 0) {
             voiceSelect.selectedIndex = 0;
        }
    };

    // Load voices. This event is key for cross-browser compatibility.
    synth.onvoiceschanged = populateVoices;

    // If voices are already loaded, trigger the handler immediately
    if (synth.getVoices().length > 0) {
        populateVoices();
    }
}

function speakResponse(text) {
    if (!synth.speak) return; // Check if TTS is available
    
    // Stop any current speaking to avoid overlap
    if (synth.speaking) {
        synth.cancel();
    }

    if (!text) return;

    const utterThis = new SpeechSynthesisUtterance(text);
    const voiceSelect = document.getElementById("voice-select");
    
    // Set selected voice
    if (voiceSelect && voiceSelect.value) {
        const selectedVoice = voices.find(v => v.name === voiceSelect.value);
        if (selectedVoice) {
            utterThis.voice = selectedVoice;
        }
    }
    
    // Set properties for a "high-energy" voice
    utterThis.rate = 1.05; // Slightly faster
    utterThis.pitch = 1.0; 

    synth.speak(utterThis);
}

function speakMessage(iconElement) {
    const messageElement = iconElement.closest('.ai-msg');
    // Get the text from the internal span (excluding the speaker icon's content)
    const textToSpeak = messageElement.querySelector('span:not(.speaker-icon)').innerText; 
    
    // FIX: Use the new speakResponse function to utilize voice selection logic
    speakResponse(textToSpeak); 
}

// --- Chat & DOM Functions ---

/**
 * Appends a message to the chat box.
 * @param {string} sender - 'user' or 'ai'
 * @param {string} text - The text content of the message.
 * @param {string} imageUrl - (Optional) URL of an image to display (for user uploads).
 */
function appendMessage(sender, text, imageUrl = null) {
    const chatBox = document.getElementById("chat-box");
    if (!chatBox) return null; // Exit if not on the chat page

    const msg = document.createElement("div");
    msg.className = `message`;

    if (sender === "user") {
        msg.classList.add("user-msg");
        // Use innerHTML to allow for a line break if showing an image
        msg.innerHTML = `<span>${text}</span>`;
        
        if (imageUrl) {
            const img = document.createElement("img");
            img.src = imageUrl;
            img.alt = "Uploaded image";
            img.className = "uploaded-image-preview"; // Use a class for CSS styling
            msg.appendChild(img);
        }
    } else {
        msg.classList.add("ai-msg");
        const textSpan = document.createElement('span');
        textSpan.innerText = text;
        
        // Add the speaker icon for AI messages
        const speakerIcon = document.createElement('span');
        speakerIcon.className = 'speaker-icon';
        speakerIcon.innerHTML = '🔊';
        speakerIcon.title = 'Read aloud';
        // Note: The click handler is set dynamically here
        speakerIcon.onclick = () => speakMessage(speakerIcon);
        
        msg.appendChild(textSpan);
        msg.appendChild(speakerIcon); // Speaker icon goes after the text
    }

    chatBox.appendChild(msg);
    chatBox.scrollTop = chatBox.scrollHeight;
    return msg;
}

function showTypingIndicator() {
    const chatBox = document.getElementById("chat-box");
    if (!chatBox) return;
    let indicator = document.querySelector(".ai-typing");
    if (!indicator) {
        indicator = document.createElement("div");
        indicator.className = "message ai-msg ai-typing";
        // Put text inside span for consistency, remove speaker icon
        // Ensure the span is inside the indicator
        indicator.innerHTML = "<span>... Thinking fast ⚡</span>"; 
        chatBox.appendChild(indicator);
    }
    return indicator;
}

function removeTypingIndicator() {
    const indicator = document.querySelector(".ai-typing");
    if (indicator) {
        indicator.remove();
    }
}

// --- File Upload Functions ---
function triggerFileInput() {
    const fileInput = document.getElementById("fileInput");
    if(fileInput) fileInput.click();
}

function clearFileInput() {
    const fileInput = document.getElementById("fileInput");
    const userInput = document.getElementById("userInput");
    currentUploadedFile = null;
    if(fileInput) fileInput.value = null; 
    if(userInput) userInput.placeholder = "💡 Ask Thinkr anything...";
}

// Event listener for file selection
document.addEventListener('DOMContentLoaded', () => {
    const fileInput = document.getElementById("fileInput");
    const userInput = document.getElementById("userInput");
    if (fileInput && userInput) {
        fileInput.onchange = (event) => {
            const file = event.target.files[0];
            if (file) {
                currentUploadedFile = file;
                userInput.placeholder = `📎 Image selected: ${file.name}. Enter a prompt...`;
            }
        };
    }
});


// --- Core Communication Functions ---

async function sendMessage() {
    const userInput = document.getElementById("userInput");
    if (isResponding || !userInput) return;

    const message = userInput.value.trim();
    const file = currentUploadedFile;

    if (!message && !file) {
        alert("Please enter a message or select a file. 🧐");
        return;
    }

    isResponding = true;
    document.querySelector(".send-btn").classList.add("hidden");
    document.querySelector(".stop-btn").classList.remove("hidden");

    let userMessageElement;
    
    // 1. Show User Message and Image
    if (file) {
        const objectURL = URL.createObjectURL(file);
        // Show text and the image thumbnail in the user message
        userMessageElement = appendMessage("user", message || "Image Uploaded", objectURL);
    } else {
        userMessageElement = appendMessage("user", message);
    }

    const typingIndicator = showTypingIndicator();
    userInput.value = ""; // Clear text input

    try {
        let responseText = "⚠️ Error: No response from server.";
        let endpoint = file ? "/ask_with_image" : "/ask";
        let fetchOptions = { method: "POST" };

        if (file) {
            const formData = new FormData();
            formData.append("message", message);
            formData.append("image", file);
            fetchOptions.body = formData;
        } else {
            fetchOptions.headers = { "Content-Type": "application/json" };
            fetchOptions.body = JSON.stringify({ message: message });
        }

        const res = await fetch(endpoint, fetchOptions);
        const data = await res.json();
        
        // Handle response
        if (data.response) {
            responseText = data.response;
            removeTypingIndicator();
            appendMessage("ai", responseText);
            // FIX: Integrate the TTS function here to speak the AI's response
            speakResponse(responseText); 
        } else if (data.error) {
            responseText = `⚠️ Server Error: ${data.error}`;
            removeTypingIndicator();
            appendMessage("ai", responseText);
        }

    } catch (err) {
        removeTypingIndicator();
        appendMessage("ai", `⚠️ Network Error: ${err.message}. Check the server connection!`);
    } finally {
        isResponding = false;
        document.querySelector(".send-btn").classList.remove("hidden");
        document.querySelector(".stop-btn").classList.add("hidden");
        clearFileInput(); // Clear the file after sending
        await loadHistory(); // Refresh history panel
    }
}

// Function to stop the response (UI only)
function stopResponding() {
    // FIX: Cancel any ongoing speech synthesis
    if (synth.speaking) {
        synth.cancel();
    }
    
    if (isResponding) {
        removeTypingIndicator();
        appendMessage("ai", "Response stopped. (The AI might still be thinking on the server side). 🛑");
        isResponding = false;
        document.querySelector(".send-btn").classList.remove("hidden");
        document.querySelector(".stop-btn").classList.add("hidden");
        clearFileInput();
    }
}

// --- History Functions ---

function toggleHistory() {
    // Mobile Fix: Toggle the 'active' class which the CSS uses to show the panel
    document.getElementById("history-panel").classList.toggle("active");
}

async function deleteHistory() {
    if (confirm("Are you sure you want to clear the entire chat history? This cannot be undone.")) {
        await fetch("/delete-history", { method: "POST" });
        const chatBox = document.getElementById("chat-box");
        const historyBox = document.getElementById("history-box");
        if(chatBox) chatBox.innerHTML = "";
        if(historyBox) historyBox.innerHTML = "";
        appendMessage("ai", "Chat history cleared! Start a new cool conversation. ✅");
    }
}

async function loadHistory() {
    const historyBox = document.getElementById("history-box");
    if (!historyBox) return; 
    
    historyBox.innerHTML = ""; // Clear existing
    try {
        const res = await fetch("/history");
        const data = await res.json();
        data.forEach(item => {
            const msg = document.createElement("div");
            msg.className = `message ${item.sender === 'user' ? 'user-msg' : 'ai-msg'}`;
            // Truncate long messages in history
            const text = item.text.length > 80 ? item.text.substring(0, 80) + "..." : item.text;
            msg.innerText = text;
            historyBox.appendChild(msg);
        });
        historyBox.scrollTop = historyBox.scrollHeight;
    } catch (err) {
        console.error("Failed to load history:", err);
    }
}

// --- Speech Recognition ---
function startListening() {
    const userInput = document.getElementById("userInput");
    if (!userInput) return;
    if (!("webkitSpeechRecognition" in window)) {
        alert("❌ Speech Recognition not supported in this browser. Try Chrome or Edge.");
        return;
    }
    const recognition = new webkitSpeechRecognition();
    recognition.lang = "en-US";
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;
    
    const typingIndicator = showTypingIndicator();
    typingIndicator.querySelector('span').innerText = "🎤 Listening...";

    recognition.onresult = (event) => {
        const transcript = event.results[0][0].transcript;
        userInput.value = transcript;
        removeTypingIndicator();
        sendMessage();
    };
    recognition.onerror = (event) => {
        removeTypingIndicator();
        appendMessage("ai", "⚠️ Voice error: " + event.error + " Try typing instead.");
    }
    recognition.onend = () => {
          removeTypingIndicator();
    };
    recognition.start();
}

// --- Initial Load ---
window.onload = () => {
    // Only run the chat-specific scripts if the elements exist on the page
    if (document.getElementById("chat-box")) {
        loadHistory();
        loadVoices(); // Load voices when the page loads
    }
};

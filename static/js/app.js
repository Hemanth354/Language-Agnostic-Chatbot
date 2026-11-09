// Campus Bot - Main Client Script
// Team TechTitans RGUKTN - SIH 2025

let conversationId = localStorage.getItem("campus_bot_conv_id") || "conv_" + Math.random().toString(36).substring(2, 9);
localStorage.setItem("campus_bot_conv_id", conversationId);

let isRecording = false;
let recognition = null;
let currentSpeechCode = "en-IN";

// Initialize Speech Recognition
if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
  const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
  recognition = new SpeechRec();
  recognition.continuous = false;
  recognition.interimResults = false;

  recognition.onstart = () => {
    isRecording = true;
    const micBtn = document.getElementById("micBtn");
    if (micBtn) micBtn.classList.add("listening");
  };

  recognition.onresult = (event) => {
    const transcript = event.results[0][0].transcript;
    const input = document.getElementById("chatInput");
    if (input) {
      input.value = transcript;
      sendMessage();
    }
  };

  recognition.onerror = (err) => {
    console.warn("Speech recognition error:", err);
    stopRecording();
  };

  recognition.onend = () => {
    stopRecording();
  };
}

function stopRecording() {
  isRecording = false;
  const micBtn = document.getElementById("micBtn");
  if (micBtn) micBtn.classList.remove("listening");
}

function toggleVoice() {
  if (!recognition) {
    alert("Speech recognition is not supported in this browser. Please use Chrome, Edge, or Safari.");
    return;
  }
  if (isRecording) {
    recognition.stop();
  } else {
    // Set recognition language based on selector
    const langSelect = document.getElementById("preferredLang");
    const lang = langSelect ? langSelect.value : "auto";
    const speechCodes = window.SPEECH_CODES || {};
    recognition.lang = speechCodes[lang] || "te-IN"; // Default to Telugu/Hindi/English
    recognition.start();
  }
}

// Text-to-Speech Synthesis
function speakText(text, langCode) {
  if (!('speechSynthesis' in window)) return;
  window.speechSynthesis.cancel(); // Stop prior speech

  const utterance = new SpeechSynthesisUtterance(text);
  utterance.lang = langCode || "hi-IN";
  utterance.rate = 0.95;
  utterance.pitch = 1.0;

  // Attempt to select an Indian voice if available
  const voices = window.speechSynthesis.getVoices();
  const indianVoice = voices.find(v => v.lang.startsWith(langCode ? langCode.split("-")[0] : "hi"));
  if (indianVoice) {
    utterance.voice = indianVoice;
  }

  window.speechSynthesis.speak(utterance);
}

// Quick Prompt Sender
function askQuestion(text, lang) {
  const input = document.getElementById("chatInput");
  const langSelect = document.getElementById("preferredLang");
  if (input) input.value = text;
  if (lang && langSelect) langSelect.value = lang;
  sendMessage();
}

// Send Message Handler
async function sendMessage() {
  const input = document.getElementById("chatInput");
  const langSelect = document.getElementById("preferredLang");
  const messagesBox = document.getElementById("messagesContainer");
  const text = input ? input.value.trim() : "";

  if (!text) return;
  input.value = "";

  // 1. Render User Message
  appendUserMessage(text);
  scrollToBottom();

  // Show typing loader
  const loaderId = appendTypingIndicator();
  scrollToBottom();

  try {
    const payload = {
      query: text,
      conversation_id: conversationId,
      preferred_lang: langSelect ? langSelect.value : "auto",
      user_name: "Student",
      channel: "web"
    };

    const res = await fetch("/api/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload)
    });

    const data = await res.json();
    removeElement(loaderId);

    // Render Bot Message
    appendBotMessage(data);
    scrollToBottom();

  } catch (err) {
    console.error("Chat error:", err);
    removeElement(loaderId);
    appendBotMessage({
      response: "Unable to connect to the campus server. Please try again.",
      detected_lang: "en",
      language_name: "English",
      confidence: 0
    });
  }
}

function appendUserMessage(text) {
  const container = document.getElementById("messagesContainer");
  const row = document.createElement("div");
  row.className = "message-row user-row";
  row.innerHTML = `
    <div class="message-avatar avatar-user">🎓</div>
    <div class="bubble bubble-user">
      <div>${escapeHtml(text)}</div>
    </div>
  `;
  container.appendChild(row);
}

function appendBotMessage(data) {
  const container = document.getElementById("messagesContainer");
  const row = document.createElement("div");
  row.className = "message-row";

  let sourcesHtml = "";
  if (data.sources && data.sources.length > 0) {
    const s = data.sources[0];
    sourcesHtml = `
      <div class="sources-box">
        <strong>📋 Official Reference:</strong> ${escapeHtml(s.title || "Circular")} 
        ${s.circular_no ? `(${escapeHtml(s.circular_no)})` : ""}
      </div>
    `;
  }

  let escalationHtml = "";
  if (data.is_escalated && data.ticket_id) {
    escalationHtml = `
      <div class="tag-ticket">
        ⚠️ Query Redirected to Faculty • Ticket #${escapeHtml(data.ticket_id)}
      </div>
    `;
  }

  let translationInfo = "";
  if (data.translated_query && data.detected_lang !== "en") {
    translationInfo = `
      <div class="meta-tags">
        <span class="tag-lang">Language: ${escapeHtml(data.language_name || data.detected_lang)}</span>
        <span class="tag-trans">Query translated: "${escapeHtml(data.translated_query)}"</span>
      </div>
    `;
  }

  const audioPayload = escapeHtml(data.response).replace(/"/g, '&quot;');

  row.innerHTML = `
    <div class="message-avatar avatar-bot">🤖</div>
    <div class="bubble bubble-bot">
      <div>
        ${escapeHtml(data.response)}
        <button class="btn-speaker" title="Listen Aloud" onclick="speakText('${audioPayload}', '${data.speech_code || "hi-IN"}')">🔊</button>
      </div>
      ${translationInfo}
      ${sourcesHtml}
      ${escalationHtml}
    </div>
  `;
  container.appendChild(row);
}

function appendTypingIndicator() {
  const id = "loader_" + Date.now();
  const container = document.getElementById("messagesContainer");
  const row = document.createElement("div");
  row.id = id;
  row.className = "message-row";
  row.innerHTML = `
    <div class="message-avatar avatar-bot">🤖</div>
    <div class="bubble bubble-bot" style="color: #64748b;">
      <span style="font-style: italic;">Thinking & checking circulars...</span>
    </div>
  `;
  container.appendChild(row);
  return id;
}

function removeElement(id) {
  const el = document.getElementById(id);
  if (el) el.remove();
}

function scrollToBottom() {
  const container = document.getElementById("messagesContainer");
  if (container) container.scrollTop = container.scrollHeight;
}

function escapeHtml(str) {
  if (!str) return "";
  return str.replace(/[&<>"']/g, function(m) {
    return {
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      '"': '&quot;',
      "'": '&#39;'
    }[m];
  });
}

// Enter Key to Send
document.addEventListener("DOMContentLoaded", () => {
  const input = document.getElementById("chatInput");
  if (input) {
    input.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        sendMessage();
      }
    });
  }
});


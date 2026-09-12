const API_URL = window.location.origin.includes("http") ? window.location.origin : "http://localhost:8000";

const messagesContainer = document.getElementById("messages");
const chatForm = document.getElementById("chat-form");
const userInput = document.getElementById("user-input");
const sendBtn = document.getElementById("send-btn");
const clearBtn = document.getElementById("clear-btn");

// ---- Conversation State ----
let currentConversationId = sessionStorage.getItem("cs_conv_id") || null;
let conversationHistory = [];
const MAX_CONTEXT_TURNS = 6;
let lastMessageId = null;  // Track last message ID for polling
let renderedMessageIds = new Set();
let pollInterval = null;


// ---- Send message ----

chatForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const text = userInput.value.trim();
    if (!text) return;

    appendUserMessage(text);
    userInput.value = "";
    sendBtn.disabled = true;

    // Track user message in local history
    const userMsgId = `user-msg-${Date.now()}`;
    conversationHistory.push({
        tweet_id: userMsgId,
        author_id: "user",
        role: "CUSTOMER",
        text: text,
        cleaned_text: text,
    });
    renderedMessageIds.add(userMsgId);

    const typingEl = showTypingIndicator();

    try {
        const response = await fetch(`${API_URL}/chat`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                current_message: text,
                brand_id: "AmazonHelp",
                conversation_id: currentConversationId,
                context_turns: conversationHistory.slice(-MAX_CONTEXT_TURNS),
            }),
        });

        removeTypingIndicator(typingEl);

        if (!response.ok) {
            const errData = await response.json().catch(() => ({}));
            throw new Error(errData.detail || `Server error (${response.status})`);
        }

        const data = await response.json();

        // Update conversation ID
        if (data.conversation_id) {
            currentConversationId = data.conversation_id;
            sessionStorage.setItem("cs_conv_id", currentConversationId);
        }

        console.log(`[CHAT] conversation_id=${currentConversationId} | decision=${data.decision}`);

        appendBotMessage(data);

        // Add bot response to local history
        if (data.draft_response) {
            const botMsgId = `bot-msg-${Date.now()}`;
            conversationHistory.push({
                tweet_id: botMsgId,
                author_id: "AmazonHelp",
                role: "BRAND",
                text: data.draft_response,
                cleaned_text: data.draft_response,
            });
            renderedMessageIds.add(botMsgId);
        }

        // Ensure background polling is active
        startPollingForUpdates();

    } catch (err) {
        removeTypingIndicator(typingEl);
        appendErrorMessage(err.message);
    } finally {
        sendBtn.disabled = false;
        userInput.focus();
    }
});


// ---- Clear conversation ----

clearBtn.addEventListener("click", () => {
    conversationHistory = [];
    currentConversationId = null;
    sessionStorage.removeItem("cs_conv_id");
    renderedMessageIds.clear();
    lastMessageId = null;

    if (pollInterval) {
        clearInterval(pollInterval);
        pollInterval = null;
    }

    const statusIndicator = document.getElementById("header-status-indicator");
    if (statusIndicator) {
        statusIndicator.style.display = "none";
    }

    messagesContainer.innerHTML = `
        <div class="message bot-message">
            <div class="message-avatar">🤖</div>
            <div class="message-content">
                <p>Hello! I'm the Customer Support AI Agent. Type your issue below and I'll classify it, find relevant past cases, and draft a response.</p>
                <p class="hint">Try something like: <em>"Where is my order? I placed it 5 days ago and it still hasn't arrived."</em></p>
            </div>
        </div>`;
});


// ---- Render user message ----

function appendUserMessage(text) {
    const div = document.createElement("div");
    div.className = "message user-message";
    div.innerHTML = `
        <div class="message-avatar">You</div>
        <div class="message-content"><p>${escapeHtml(text)}</p></div>`;
    messagesContainer.appendChild(div);
    scrollToBottom();
}


// ---- Render bot message with pipeline metadata ----

function appendBotMessage(data) {
    const div = document.createElement("div");
    div.className = "message bot-message";

    // Update header status indicator
    updateHeaderStatus(data.decision, data.conversation_status);

    let decisionBadge;
    if (data.decision === "AUTO_HANDLE") {
        decisionBadge = `<span class="badge badge-auto">✅ Auto Handle</span>`;
    } else if (data.decision === "NEED_INFORMATION") {
        decisionBadge = `<span class="badge badge-info">ℹ️ Need Info</span>`;
    } else if (data.decision === "HUMAN_ACTIVE") {
        decisionBadge = `<span class="badge badge-human">🧑‍💼 Human Support Active</span>`;
    } else {
        decisionBadge = `<span class="badge badge-escalate">⚠️ Escalate</span>`;
    }

    // Response text
    let responseHtml;
    if (data.draft_response) {
        responseHtml = `<p>${escapeHtml(data.draft_response)}</p>`;
    } else if (data.decision === "ESCALATE") {
        responseHtml = `<p><em>Your request requires human assistance. Our support team has been notified and will review your case.</em></p>`;
    } else {
        responseHtml = `<p><em>No response available.</em></p>`;
    }

    // For HUMAN_ACTIVE, show simplified message without large pipeline details
    if (data.decision === "HUMAN_ACTIVE") {
        div.innerHTML = `
            <div class="message-avatar">🤖</div>
            <div class="message-content">
                ${responseHtml}
            </div>`;
    } else {
        // Normal flow: show minimal badge + response, hide detailed pipeline info
        // Escalation reason box (only if explicitly escalating)
        let escalationHtml = "";
        if (data.decision === "ESCALATE" && data.escalation_reason) {
            escalationHtml = `
                <div class="escalation-box">
                    <strong>Escalation reason:</strong> ${escapeHtml(data.escalation_reason)}
                </div>`;
        }

        // Pipeline errors (important to show)
        let errorsHtml = "";
        if (data.errors && data.errors.length > 0) {
            errorsHtml = `
                <div class="errors-list">
                    <strong>Pipeline errors:</strong>
                    <ul>${data.errors.map(e => `<li>${escapeHtml(e)}</li>`).join("")}</ul>
                </div>`;
        }

        // Build minimal metadata (collapsible, hidden by default)
        const metaId = `meta-${Date.now()}`;
        const collectedStr = formatEntities(data.collected_entities);
        const missingStr = data.missing_entities && data.missing_entities.length > 0
            ? data.missing_entities.join(", ") : "None";

        const metaHtml = `
            <div class="pipeline-meta">
                <div class="meta-header" onclick="toggleMeta('${metaId}')">
                    <span class="meta-header-left">
                        <small style="color: #999;">Show details</small>
                    </span>
                    <span class="meta-toggle" id="${metaId}-toggle">▼</span>
                </div>
                <div class="meta-body" id="${metaId}">
                    <div class="meta-grid">
                        <div class="meta-item">
                            <span class="meta-label">Intent</span>
                            <span class="meta-value">${escapeHtml(data.intent || "—")}</span>
                        </div>
                        <div class="meta-item">
                            <span class="meta-label">Status</span>
                            <span class="meta-value">${escapeHtml(data.conversation_status || "ACTIVE")}</span>
                        </div>
                        <div class="meta-item">
                            <span class="meta-label">Collected</span>
                            <span class="meta-value">${escapeHtml(collectedStr)}</span>
                        </div>
                        <div class="meta-item">
                            <span class="meta-label">Missing</span>
                            <span class="meta-value">${escapeHtml(missingStr)}</span>
                        </div>
                    </div>
                </div>
            </div>`;

        div.innerHTML = `
            <div class="message-avatar">🤖</div>
            <div class="message-content">
                ${responseHtml}
                ${escalationHtml}
                ${errorsHtml}
                ${metaHtml}
            </div>`;
    }

    messagesContainer.appendChild(div);
    scrollToBottom();
}

function formatEntities(entities) {
    if (!entities || Object.keys(entities).length === 0) return "None";
    return Object.entries(entities)
        .map(([k, v]) => `${k}: ${v}`)
        .join(", ");
}

function updateHeaderStatus(decision, status) {
    let statusIndicator = document.getElementById("header-status-indicator");
    if (!statusIndicator) {
        // Create status indicator in header
        const header = document.querySelector(".chat-header");
        statusIndicator = document.createElement("div");
        statusIndicator.id = "header-status-indicator";
        statusIndicator.className = "header-status";
        header.appendChild(statusIndicator);
    }

    if (decision === "HUMAN_ACTIVE" || status === "HUMAN_ACTIVE") {
        statusIndicator.innerHTML = `<span class="badge badge-human">🧑‍💼 Human Support Active</span>`;
        statusIndicator.style.display = "block";
    } else if (decision === "ESCALATE") {
        statusIndicator.innerHTML = `<span class="badge badge-escalate">⚠️ Escalated to Human</span>`;
        statusIndicator.style.display = "block";
    } else {
        statusIndicator.style.display = "none";
    }
}


// ---- Render Human-Approved Message from Live Updates ----

function appendHumanApprovedMessage(msg) {
    if (renderedMessageIds.has(msg.id)) return;
    renderedMessageIds.add(msg.id);
    lastMessageId = msg.id;

    const div = document.createElement("div");
    div.className = "message bot-message";
    div.innerHTML = `
        <div class="message-avatar">🧑‍💼</div>
        <div class="message-content">
            <span class="badge badge-human">🧑‍💼 Human Support Agent</span>
            <p>${escapeHtml(msg.text)}</p>
        </div>`;

    messagesContainer.appendChild(div);
    scrollToBottom();

    console.log(`[RENDER] Human message appended: ${msg.id}`);
}


// ---- Live Polling for Human-Approved Updates ----

function startPollingForUpdates() {
    if (pollInterval || !currentConversationId) return;

    console.log(`[POLL] Starting polling for conversation_id=${currentConversationId}`);

    pollInterval = setInterval(async () => {
        if (!currentConversationId) return;

        try {
            const url = lastMessageId
                ? `${API_URL}/chat/${currentConversationId}/updates?after=${encodeURIComponent(lastMessageId)}`
                : `${API_URL}/chat/${currentConversationId}/updates`;

            const response = await fetch(url);
            if (!response.ok) return;

            const data = await response.json();

            if (data.messages && data.messages.length > 0) {
                console.log(`[POLL] Received ${data.messages.length} new message(s)`);
                for (const msg of data.messages) {
                    // Only render human agent messages (not our own AI responses)
                    if (msg.source === "human_agent" && !renderedMessageIds.has(msg.id)) {
                        appendHumanApprovedMessage(msg);
                    }
                }
            }
        } catch (err) {
            console.debug("[POLL] Update check error:", err);
        }
    }, 2500);
}


// ---- Error message ----

function appendErrorMessage(errorText) {
    const div = document.createElement("div");
    div.className = "message bot-message";
    div.innerHTML = `
        <div class="message-avatar">⚠️</div>
        <div class="message-content">
            <div class="errors-list">
                <strong>Connection error:</strong> ${escapeHtml(errorText)}
                <br/><br/>Make sure the backend is running: <code>uvicorn customer_support.api.main:app --reload --port 8000</code>
            </div>
        </div>`;
    messagesContainer.appendChild(div);
    scrollToBottom();
}


// ---- Typing indicator ----

function showTypingIndicator() {
    const div = document.createElement("div");
    div.className = "message bot-message";
    div.id = "typing-msg";
    div.innerHTML = `
        <div class="message-avatar">🤖</div>
        <div class="message-content">
            <div class="typing-indicator">
                <span></span><span></span><span></span>
            </div>
        </div>`;
    messagesContainer.appendChild(div);
    scrollToBottom();
    return div;
}

function removeTypingIndicator(el) {
    if (el && el.parentNode) {
        el.parentNode.removeChild(el);
    }
}


// ---- Toggle pipeline metadata ----

function toggleMeta(id) {
    const body = document.getElementById(id);
    const toggle = document.getElementById(id + "-toggle");
    if (body) body.classList.toggle("show");
    if (toggle) toggle.classList.toggle("open");
}


// ---- Helpers ----

function scrollToBottom() {
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

function escapeHtml(text) {
    if (!text) return "";
    const el = document.createElement("span");
    el.textContent = text;
    return el.innerHTML;
}

function tierClass(tier) {
    if (!tier) return "";
    return "badge-" + tier.toLowerCase();
}

function qualityClass(quality) {
    if (!quality) return "";
    return "badge-" + quality.toLowerCase();
}

// Start polling on load if previous session existed
if (currentConversationId) {
    console.log(`[INIT] Resuming conversation_id=${currentConversationId}`);
    startPollingForUpdates();
}

const API_URL = window.location.origin.includes("http") ? window.location.origin : "http://localhost:8000";

let currentFilter = "PENDING";
let activeEditForms = new Set(); // Track which forms are currently being edited
let conversationsCache = {}; // Cache to detect changes
let conversationPollers = {}; // Track polling for each conversation

// Load conversations on page load
document.addEventListener("DOMContentLoaded", () => {
    loadConversations();
    // Auto-refresh every 10 seconds
    setInterval(loadConversations, 10000);
});

async function loadConversations() {
    try {
        const url = currentFilter ? `${API_URL}/escalations?status=${currentFilter}` : `${API_URL}/escalations`;
        const response = await fetch(url);
        const data = await response.json();

        // Update count
        const activeCount = (data.stats.pending || 0) + (data.stats.approved || 0);
        document.getElementById("active-count").textContent = `${activeCount} active chat${activeCount !== 1 ? 's' : ''}`;

        // Render conversations with smart update
        renderConversationsSmartly(data.escalations);
    } catch (err) {
        console.error("Failed to load conversations:", err);
        document.getElementById("conversations-list").innerHTML = `
            <div class="empty-state">
                <h2>⚠️ Connection Error</h2>
                <p>Failed to load conversations. Make sure the backend is running.</p>
            </div>`;
    }
}

function filterStatus(status) {
    currentFilter = status;

    // Update active tab
    document.querySelectorAll(".tab-btn").forEach(btn => btn.classList.remove("active"));
    if (event && event.target) {
        event.target.classList.add("active");
    }

    loadConversations();
}

function renderConversationsSmartly(escalations) {
    const container = document.getElementById("conversations-list");

    if (escalations.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <h2>✅ All Clear!</h2>
                <p>No ${currentFilter ? currentFilter.toLowerCase().replace('_', ' ') : ""} conversations at the moment.</p>
            </div>`;
        return;
    }

    // Build new escalations map
    const newEscalationsMap = {};
    escalations.forEach(esc => {
        newEscalationsMap[esc.id] = esc;
    });

    // Get existing cards
    const existingCards = container.querySelectorAll('.chat-card');
    const existingIds = new Set();

    existingCards.forEach(card => {
        const cardId = card.dataset.escalationId;
        if (cardId) {
            existingIds.add(cardId);

            // Check if this escalation still exists and hasn't changed
            const newEsc = newEscalationsMap[cardId];
            if (newEsc) {
                // Only update if status changed AND form is not being edited
                const isBeingEdited = activeEditForms.has(cardId);
                const statusChanged = conversationsCache[cardId]?.status !== newEsc.status;
                const messagesChanged = conversationsCache[cardId]?.customer_message !== newEsc.customer_message;

                if (!isBeingEdited && (statusChanged || messagesChanged)) {
                    // Replace card
                    const newCard = createConversationCard(newEsc);
                    card.outerHTML = newCard;
                } else if (messagesChanged && isBeingEdited) {
                    // Update only the conversation history, preserve textarea
                    updateConversationHistory(cardId, newEsc);
                }
                conversationsCache[cardId] = newEsc;
            } else {
                // Escalation no longer exists in this filter
                card.remove();
                delete conversationsCache[cardId];
                activeEditForms.delete(cardId);
                stopPollingConversation(cardId);
            }
        }
    });

    // Add new escalations that don't exist yet
    escalations.forEach(esc => {
        if (!existingIds.has(esc.id)) {
            const cardHtml = createConversationCard(esc);
            container.insertAdjacentHTML('beforeend', cardHtml);
            conversationsCache[esc.id] = esc;

            // Start polling for new customer messages if active
            if (esc.status === "HUMAN_ACTIVE") {
                startPollingConversation(esc.id, esc.conversation_id);
            }
        }
    });
}

function createConversationCard(esc) {
    const statusClass = esc.status.toLowerCase().replace('_', '-');
    const timestamp = new Date(esc.timestamp).toLocaleString();

    let statusBadge = "New";
    if (esc.status === "HUMAN_ACTIVE") {
        statusBadge = "Active";
    } else if (esc.status === "CLOSED") {
        statusBadge = "Closed";
    }

    // Show conversation history if available
    let conversationHistoryHtml = "";
    if (esc.conversation_id) {
        conversationHistoryHtml = `
            <button class="show-history-btn" type="button" onclick="toggleHistory('${esc.id}')">
                📜 Show conversation history
            </button>
            <div class="conversation-history collapsed" id="history-${esc.id}">
                <div class="conv-message">
                    <div class="conv-message-header">
                        <span class="conv-role customer">Customer</span>
                        <span class="conv-time">${timestamp}</span>
                    </div>
                    <div class="conv-text">${escapeHtml(esc.customer_message)}</div>
                </div>
            </div>`;
    }

    let actionButtons = "";
    if (esc.status === "PENDING") {
        actionButtons = `
            <div class="response-form">
                <textarea
                    id="response-${esc.id}"
                    placeholder="Type your response to the customer..."
                    onfocus="markFormActive('${esc.id}')"
                    onblur="markFormInactive('${esc.id}')">${escapeHtml(esc.draft_response || "")}</textarea>
                <div class="form-actions">
                    <button class="btn btn-send" type="button" onclick="sendResponse('${esc.id}')">
                        📤 Send Response
                    </button>
                </div>
            </div>`;
    } else if (esc.status === "HUMAN_ACTIVE") {
        const lastResponse = esc.human_response ? `
            <div style="background: #d4edda; padding: 12px; border-radius: 6px; margin-bottom: 15px; border-left: 3px solid #27ae60;">
                <div style="font-size: 11px; color: #7f8c8d; font-weight: 600; text-transform: uppercase; margin-bottom: 6px;">Last Sent</div>
                <div style="font-size: 14px; color: #2c3e50;">${escapeHtml(esc.human_response)}</div>
            </div>` : "";

        actionButtons = `
            ${lastResponse}
            <div class="response-form">
                <textarea
                    id="response-${esc.id}"
                    placeholder="Continue the conversation..."
                    onfocus="markFormActive('${esc.id}')"
                    onblur="markFormInactive('${esc.id}')"></textarea>
                <div class="form-actions">
                    <button class="btn btn-send" type="button" onclick="sendResponse('${esc.id}')">
                        📤 Send Response
                    </button>
                    <button class="btn btn-close" type="button" onclick="closeConversation('${esc.id}')">
                        🔒 Close Conversation
                    </button>
                </div>
            </div>`;
    } else if (esc.status === "CLOSED") {
        actionButtons = `
            <div style="background: #e2e3e5; padding: 15px; border-radius: 8px; text-align: center; color: #6c757d;">
                <strong>Conversation Closed</strong>
                ${esc.resolved_at ? `<div style="font-size: 13px; margin-top: 5px;">Closed at ${new Date(esc.resolved_at).toLocaleString()}</div>` : ""}
            </div>`;
    }

    return `
        <div class="chat-card ${statusClass}" data-escalation-id="${esc.id}">
            <div class="chat-header">
                <div class="chat-time">${timestamp}</div>
                <span class="status-badge ${statusClass}">${statusBadge}</span>
            </div>

            ${esc.escalation_reason ? `<div class="escalation-reason">Reason: ${escapeHtml(esc.escalation_reason)}</div>` : ""}

            <div class="latest-message">
                <div class="latest-message-label">Latest Customer Message:</div>
                <div class="latest-message-text">${escapeHtml(esc.customer_message)}</div>
            </div>

            ${conversationHistoryHtml}
            ${actionButtons}
        </div>`;
}

function toggleHistory(id) {
    const history = document.getElementById(`history-${id}`);
    const btn = event.target;

    if (history.classList.contains('collapsed')) {
        history.classList.remove('collapsed');
        btn.textContent = '📜 Hide conversation history';
    } else {
        history.classList.add('collapsed');
        btn.textContent = '📜 Show conversation history';
    }
}

function markFormActive(id) {
    activeEditForms.add(id);
    console.log(`[EDIT] Form ${id} is now active`);
}

function markFormInactive(id) {
    setTimeout(() => {
        const textarea = document.getElementById(`response-${id}`);
        if (textarea !== document.activeElement) {
            activeEditForms.delete(id);
            console.log(`[EDIT] Form ${id} is now inactive`);
        }
    }, 200);
}

async function sendResponse(id) {
    const textarea = document.getElementById(`response-${id}`);
    const responseText = textarea.value.trim();

    if (!responseText) {
        alert("Response cannot be empty!");
        return;
    }

    try {
        // Determine if this is first response or ongoing
        const esc = conversationsCache[id];
        const endpoint = esc && esc.status === "HUMAN_ACTIVE"
            ? `${API_URL}/escalations/${id}/reply`
            : `${API_URL}/escalations/${id}/approve`;

        const response = await fetch(endpoint, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                human_response: responseText,
                agent_name: "human_agent",
            }),
        });

        if (response.ok) {
            const result = await response.json();
            alert(`✅ Response sent to customer!`);
            textarea.value = "";
            activeEditForms.delete(id);
            loadConversations();
        } else {
            const error = await response.json();
            alert(`Error: ${error.detail}`);
        }
    } catch (err) {
        alert(`Failed to send: ${err.message}`);
    }
}

async function closeConversation(id) {
    if (!confirm("Close this conversation?\n\nThe customer will no longer receive responses unless they start a new conversation.")) return;

    try {
        const response = await fetch(`${API_URL}/escalations/${id}/close`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ agent_name: "human_agent" }),
        });

        if (response.ok) {
            alert(`✅ Conversation closed!`);
            activeEditForms.delete(id);
            stopPollingConversation(id);
            loadConversations();
        } else {
            const error = await response.json();
            alert(`Error: ${error.detail}`);
        }
    } catch (err) {
        alert(`Failed to close: ${err.message}`);
    }
}

function startPollingConversation(escalationId, conversationId) {
    if (conversationPollers[escalationId] || !conversationId) return;

    let lastMessageId = null;

    conversationPollers[escalationId] = setInterval(async () => {
        try {
            const url = lastMessageId
                ? `${API_URL}/chat/${conversationId}/updates?after=${encodeURIComponent(lastMessageId)}`
                : `${API_URL}/chat/${conversationId}/updates`;

            const response = await fetch(url);
            if (!response.ok) return;

            const data = await response.json();

            if (data.messages && data.messages.length > 0) {
                // Update conversation history with new messages
                const customerMessages = data.messages.filter(m => m.role === "CUSTOMER");
                if (customerMessages.length > 0) {
                    // Update cached customer message
                    if (conversationsCache[escalationId]) {
                        conversationsCache[escalationId].customer_message = customerMessages[customerMessages.length - 1].text;
                    }
                    // Trigger UI update
                    loadConversations();
                }
                lastMessageId = data.messages[data.messages.length - 1].id;
            }
        } catch (err) {
            console.debug(`[POLL] Error polling conversation ${conversationId}:`, err);
        }
    }, 5000);
}

function stopPollingConversation(escalationId) {
    if (conversationPollers[escalationId]) {
        clearInterval(conversationPollers[escalationId]);
        delete conversationPollers[escalationId];
    }
}

function updateConversationHistory(escalationId, esc) {
    // Update only the latest message without replacing the whole card
    const card = document.querySelector(`[data-escalation-id="${escalationId}"]`);
    if (!card) return;

    const latestMessageEl = card.querySelector('.latest-message-text');
    if (latestMessageEl) {
        latestMessageEl.textContent = esc.customer_message;
    }
}

function escapeHtml(text) {
    if (!text) return "";
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
}

const API_URL = window.location.origin.includes("http") ? window.location.origin : "http://localhost:8000";

let currentFilter = "PENDING";
let activeEditForms = new Set(); // Track which forms are currently being edited
let escalationsCache = {}; // Cache escalations to prevent unnecessary re-renders

// Load escalations on page load
document.addEventListener("DOMContentLoaded", () => {
    loadEscalations();
    // Auto-refresh every 10 seconds (reduced from 15s but with smart re-render)
    setInterval(loadEscalations, 10000);
});

async function loadEscalations() {
    try {
        const url = currentFilter ? `${API_URL}/escalations?status=${currentFilter}` : `${API_URL}/escalations`;
        const response = await fetch(url);
        const data = await response.json();

        // Update stats
        document.getElementById("pending-count").textContent = data.stats.pending;
        document.getElementById("approved-count").textContent = data.stats.approved || 0;
        document.getElementById("rejected-count").textContent = data.stats.rejected || 0;

        // Render escalations with smart update
        renderEscalationsSmartly(data.escalations);
    } catch (err) {
        console.error("Failed to load escalations:", err);
        document.getElementById("escalations-list").innerHTML = `
            <div class="empty-state">
                <h2>⚠️ Connection Error</h2>
                <p>Failed to load escalations. Make sure the backend is running.</p>
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

    loadEscalations();
}

function renderEscalationsSmartly(escalations) {
    const container = document.getElementById("escalations-list");

    if (escalations.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <h2>✅ All Clear!</h2>
                <p>No ${currentFilter ? currentFilter.toLowerCase() : ""} escalations at the moment.</p>
            </div>`;
        return;
    }

    // Build new escalations map
    const newEscalationsMap = {};
    escalations.forEach(esc => {
        newEscalationsMap[esc.id] = esc;
    });

    // Get existing escalation cards
    const existingCards = container.querySelectorAll('.escalation-card');
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
                if (!isBeingEdited && (escalationsCache[cardId]?.status !== newEsc.status)) {
                    // Replace card
                    const newCard = createEscalationCard(newEsc);
                    card.outerHTML = newCard;
                }
                escalationsCache[cardId] = newEsc;
            } else {
                // Escalation no longer exists in this filter
                card.remove();
                delete escalationsCache[cardId];
                activeEditForms.delete(cardId);
            }
        }
    });

    // Add new escalations that don't exist yet
    escalations.forEach(esc => {
        if (!existingIds.has(esc.id)) {
            const cardHtml = createEscalationCard(esc);
            container.insertAdjacentHTML('beforeend', cardHtml);
            escalationsCache[esc.id] = esc;
        }
    });
}

function createEscalationCard(esc) {
    const statusClass = esc.status.toLowerCase().replace('_', '-');
    const timestamp = new Date(esc.timestamp).toLocaleString();

    let actionButtons = "";
    if (esc.status === "PENDING" || esc.status === "HUMAN_ACTIVE") {
        actionButtons = `
            <div class="action-buttons">
                <button class="btn btn-approve" onclick="approveEscalation('${esc.id}')">
                    ✅ Approve & Send
                </button>
                <button class="btn btn-edit" onclick="toggleEditForm('${esc.id}')">
                    ✏️ Edit Response
                </button>
                <button class="btn btn-reject" onclick="toggleRejectForm('${esc.id}')">
                    ✍️ Write Custom Response
                </button>
                ${esc.status === "HUMAN_ACTIVE" ? `
                <button class="btn btn-close" onclick="closeEscalation('${esc.id}')" style="background: #95a5a6;">
                    🔒 Close Conversation
                </button>` : ''}
            </div>
            <div id="edit-form-${esc.id}" class="edit-form">
                <p class="message-label">Edit AI Response:</p>
                <textarea id="edit-text-${esc.id}" onfocus="markFormActive('${esc.id}')" onblur="markFormInactive('${esc.id}')">${escapeHtml(esc.draft_response || "")}</textarea>
                <div class="action-buttons" style="margin-top: 10px;">
                    <button class="btn btn-approve" onclick="approveWithEdit('${esc.id}')">
                        💾 Send to Live Chat
                    </button>
                    <button class="btn" onclick="toggleEditForm('${esc.id}')" style="background: #95a5a6; color: white;">
                        Cancel
                    </button>
                </div>
            </div>
            <div id="reject-form-${esc.id}" class="edit-form">
                <p class="message-label">Write Custom Response:</p>
                <textarea id="reject-text-${esc.id}" onfocus="markFormActive('${esc.id}')" onblur="markFormInactive('${esc.id}')" placeholder="Write your custom response here..."></textarea>
                <div class="action-buttons" style="margin-top: 10px;">
                    <button class="btn btn-approve" onclick="replyWithCustom('${esc.id}')">
                        📤 Send to Live Chat
                    </button>
                    <button class="btn" onclick="toggleRejectForm('${esc.id}')" style="background: #95a5a6; color: white;">
                        Cancel
                    </button>
                </div>
            </div>`;
    }

    let resolvedInfo = "";
    if (esc.resolved_at) {
        const resolvedTime = new Date(esc.resolved_at).toLocaleString();
        resolvedInfo = `
            <div class="metadata">
                <div class="meta-item">
                    <span class="meta-label">Resolved By</span>
                    <span class="meta-value">${escapeHtml(esc.resolved_by || "—")}</span>
                </div>
                <div class="meta-item">
                    <span class="meta-label">Resolved At</span>
                    <span class="meta-value">${resolvedTime}</span>
                </div>
            </div>`;
    }

    let humanResponseHtml = "";
    if (esc.human_response && esc.status !== "PENDING") {
        humanResponseHtml = `
            <div class="human-response">
                <p class="message-label">Last Human Response Delivered:</p>
                <p>${escapeHtml(esc.human_response)}</p>
            </div>`;
    }

    let statusBadgeText = esc.status;
    if (esc.status === "HUMAN_ACTIVE") {
        statusBadgeText = "🧑‍💼 HUMAN ACTIVE";
    }

    return `
        <div class="escalation-card ${statusClass}" data-escalation-id="${esc.id}">
            <div class="card-header">
                <div>
                    <span class="card-id">Escalation ID: ${esc.id}</span>
                    <p class="timestamp">${timestamp}</p>
                </div>
                <span class="status-badge ${statusClass}">${statusBadgeText}</span>
            </div>

            <div class="customer-message">
                <p class="message-label">Latest Customer Message:</p>
                <p><strong>${escapeHtml(esc.customer_message)}</strong></p>
            </div>

            <div class="metadata">
                <div class="meta-item">
                    <span class="meta-label">Conversation ID</span>
                    <span class="meta-value">${escapeHtml(esc.conversation_id || "—")}</span>
                </div>
                <div class="meta-item">
                    <span class="meta-label">Detected Intent</span>
                    <span class="meta-value">${escapeHtml(esc.intent || "—")}</span>
                </div>
                <div class="meta-item">
                    <span class="meta-label">Confidence</span>
                    <span class="meta-value">${esc.confidence ? (esc.confidence * 100).toFixed(0) + "%" : "—"} (${esc.confidence_tier || "—"})</span>
                </div>
                <div class="meta-item">
                    <span class="meta-label">Evidence Quality</span>
                    <span class="meta-value">${escapeHtml(esc.evidence_quality || "—")}</span>
                </div>
            </div>

            <div class="escalation-reason">
                <p class="message-label">⚠️ Escalation Reason:</p>
                <p>${escapeHtml(esc.escalation_reason)}</p>
            </div>

            ${esc.draft_response ? `
            <div class="draft-response">
                <p class="message-label">🤖 AI Suggested Draft:</p>
                <p>${escapeHtml(esc.draft_response)}</p>
            </div>` : ""}

            ${humanResponseHtml}
            ${resolvedInfo}
            ${actionButtons}
        </div>`;
}

function markFormActive(id) {
    activeEditForms.add(id);
    console.log(`[EDIT] Form ${id} is now active - polling will not replace this card`);
}

function markFormInactive(id) {
    // Small delay to prevent premature removal during focus transitions
    setTimeout(() => {
        const editField = document.getElementById(`edit-text-${id}`);
        const rejectField = document.getElementById(`reject-text-${id}`);
        if (editField !== document.activeElement && rejectField !== document.activeElement) {
            activeEditForms.delete(id);
            console.log(`[EDIT] Form ${id} is now inactive`);
        }
    }, 200);
}

function toggleEditForm(id) {
    const form = document.getElementById(`edit-form-${id}`);
    const wasVisible = form.classList.contains("show");
    form.classList.toggle("show");
    document.getElementById(`reject-form-${id}`).classList.remove("show");

    if (!wasVisible) {
        markFormActive(id);
        setTimeout(() => {
            document.getElementById(`edit-text-${id}`)?.focus();
        }, 100);
    } else {
        markFormInactive(id);
    }
}

function toggleRejectForm(id) {
    const form = document.getElementById(`reject-form-${id}`);
    const wasVisible = form.classList.contains("show");
    form.classList.toggle("show");
    document.getElementById(`edit-form-${id}`).classList.remove("show");

    if (!wasVisible) {
        markFormActive(id);
        setTimeout(() => {
            document.getElementById(`reject-text-${id}`)?.focus();
        }, 100);
    } else {
        markFormInactive(id);
    }
}

async function approveEscalation(id) {
    if (!confirm("Approve this response and deliver it directly to the customer's live chat?")) return;

    try {
        const response = await fetch(`${API_URL}/escalations/${id}/approve`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ agent_name: "human_agent" }),
        });

        if (response.ok) {
            const result = await response.json();
            alert(`✅ Response delivered! Conversation is now in HUMAN_ACTIVE mode.\n\nConversation ID: ${result.conversation_id}`);
            activeEditForms.delete(id);
            loadEscalations();
        } else {
            const error = await response.json();
            alert(`Error: ${error.detail}`);
        }
    } catch (err) {
        alert(`Failed to approve: ${err.message}`);
    }
}

async function approveWithEdit(id) {
    const editedText = document.getElementById(`edit-text-${id}`).value.trim();
    if (!editedText) {
        alert("Response cannot be empty!");
        return;
    }

    try {
        const response = await fetch(`${API_URL}/escalations/${id}/approve`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                human_response: editedText,
                agent_name: "human_agent",
            }),
        });

        if (response.ok) {
            const result = await response.json();
            alert(`✅ Edited response delivered to live chat!\n\nConversation is now HUMAN_ACTIVE.\nConversation ID: ${result.conversation_id}`);
            activeEditForms.delete(id);
            loadEscalations();
        } else {
            const error = await response.json();
            alert(`Error: ${error.detail}`);
        }
    } catch (err) {
        alert(`Failed to save: ${err.message}`);
    }
}

async function replyWithCustom(id) {
    const customText = document.getElementById(`reject-text-${id}`).value.trim();
    if (!customText) {
        alert("Custom response cannot be empty!");
        return;
    }

    try {
        const response = await fetch(`${API_URL}/escalations/${id}/reply`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                human_response: customText,
                agent_name: "human_agent",
            }),
        });

        if (response.ok) {
            const result = await response.json();
            alert(`✅ Custom response sent to live chat!\n\nConversation remains HUMAN_ACTIVE.\nConversation ID: ${result.conversation_id}`);
            // Clear the textarea after successful send
            document.getElementById(`reject-text-${id}`).value = "";
            activeEditForms.delete(id);
            loadEscalations();
        } else {
            const error = await response.json();
            alert(`Error: ${error.detail}`);
        }
    } catch (err) {
        alert(`Failed to save: ${err.message}`);
    }
}

async function closeEscalation(id) {
    if (!confirm("Close this conversation and end human support?\n\nThe customer will no longer receive responses unless they start a new conversation.")) return;

    try {
        const response = await fetch(`${API_URL}/escalations/${id}/close`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ agent_name: "human_agent" }),
        });

        if (response.ok) {
            const result = await response.json();
            alert(`✅ Conversation closed!\n\nConversation ID: ${result.conversation_id}`);
            activeEditForms.delete(id);
            loadEscalations();
        } else {
            const error = await response.json();
            alert(`Error: ${error.detail}`);
        }
    } catch (err) {
        alert(`Failed to close: ${err.message}`);
    }
}

function escapeHtml(text) {
    if (!text) return "";
    const div = document.createElement("div");
    div.textContent = text;
    return div.innerHTML;
}

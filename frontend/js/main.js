/**
 * Main Application Module
 * Orchestrates initialization, event handling, and core app state.
 */

import * as API from './api.js';
import * as Graph from './graph.js';
import * as UI from './ui.js';
import { CONFIG, COLORS } from './config.js';
import { sendMessage } from './chat.js';

// Global State
export const state = {
    sessionId: null,
    userId: null,
};

// --- Initialization ---
document.addEventListener("DOMContentLoaded", () => {
    Promise.all([
        initSession(),
        fetchSchema(),
        populateModels(),
        populateEmbeddingModels(),
    ]).catch(console.error);

    setupEventListeners();
});

function setupEventListeners() {
    // Toggles
    document.getElementById("zep-toggle")?.addEventListener("change", toggleZepSettings);
    document.getElementById("rag-toggle")?.addEventListener("change", toggleRAGSettings);

    // Chat
    document.getElementById("send-btn")?.addEventListener("click", handleSendMessage);
    document.getElementById("message-input")?.addEventListener("keydown", (e) => {
        if (e.key === "Enter") handleSendMessage();
    });

    // RAG Ingest
    document.getElementById("ingest-btn")?.addEventListener("click", handleIngest);
    document.getElementById("clear-rag-btn")?.addEventListener("click", handleClearRAG);

    // Schema
    document.querySelector("#schema-modal .modal-footer button:last-child")?.addEventListener("click", handleSaveSchema);
    
    // Window Resize
    window.addEventListener("resize", () => Graph.resizeGraph());
}

// --- Handlers ---

async function handleSendMessage() {
    await sendMessage(state);
    refreshGraph();
}

async function initSession(forceNew = false) {
    if (!forceNew && state.sessionId) return;

    const payload = {
        first_name: document.getElementById("first-name")?.value || "User",
        last_name: document.getElementById("last-name")?.value || "",
        traits: document.getElementById("traits-input")?.value || "",
        preferences: document.getElementById("preferences-input")?.value || "",
        business_data: document.getElementById("business-data-input")?.value || "",
    };

    try {
        const data = await API.initSession(payload);
        setActiveSession(data);
        document.getElementById("chat-box").innerHTML = "";
        refreshGraph();
        UI.addMessage("system", "Session initialized.");
    } catch (e) {
        console.error("Session init failed", e);
    }
}

// --- Global scope exports for HTML onclick handlers ---
Object.assign(window, {
    initSession,
    refreshGraph,
    openSessionsModal,
    closeSessionsModal,
    loadSession,
    deleteSessionById,
    sendMessage: handleSendMessage,
    resetZoom: Graph.resetZoom,
    openSchemaModal: () => document.getElementById("schema-modal")?.classList.add("active"),
    closeSchemaModal: () => document.getElementById("schema-modal")?.classList.remove("active"),
});

// --- Session Management ---

/**
 * Set active session and update UI.
 */
function setActiveSession(data) {
    state.sessionId = data.session_id;
    state.userId = data.user_id;
    
    const badge = document.getElementById("session-badge");
    if (badge) badge.textContent = `ID: ${state.sessionId.split("_")[1] || state.sessionId}`;
    
    // Update form fields if session has data
    if (data.first_name) document.getElementById("first-name").value = data.first_name;
    if (data.last_name) document.getElementById("last-name").value = data.last_name;
    if (data.traits) document.getElementById("traits-input").value = data.traits;
    if (data.preferences) document.getElementById("preferences-input").value = data.preferences;
    if (data.business_data) document.getElementById("business-data-input").value = data.business_data;
}

/**
 * Open sessions modal and load sessions.
 */
async function openSessionsModal() {
    document.getElementById("sessions-modal")?.classList.add("active");
    await renderSessionsModal();
}

/**
 * Close sessions modal.
 */
function closeSessionsModal() {
    document.getElementById("sessions-modal")?.classList.remove("active");
}

/**
 * Group sessions by time period.
 */
function groupSessionsByTime(sessions) {
    const now = new Date();
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const yesterday = new Date(today); yesterday.setDate(yesterday.getDate() - 1);
    const weekAgo = new Date(today); weekAgo.setDate(weekAgo.getDate() - 7);
    
    const groups = {
        "Today": [],
        "Yesterday": [],
        "This Week": [],
        "Older": []
    };
    
    sessions.forEach(s => {
        const created = new Date(s.created_at);
        if (created >= today) {
            groups["Today"].push(s);
        } else if (created >= yesterday) {
            groups["Yesterday"].push(s);
        } else if (created >= weekAgo) {
            groups["This Week"].push(s);
        } else {
            groups["Older"].push(s);
        }
    });
    
    return groups;
}

/**
 * Render sessions modal content with time grouping.
 */
async function renderSessionsModal() {
    const container = document.getElementById("sessions-modal-content");
    if (!container) return;
    
    container.innerHTML = '<div class="sessions-loading">Loading sessions...</div>';
    
    try {
        const { sessions } = await API.listSessions();
        
        if (!sessions.length) {
            container.innerHTML = '<div class="sessions-empty">No saved sessions.<br>Click "New Session" to create one.</div>';
            return;
        }
        
        const groups = groupSessionsByTime(sessions);
        let html = '';
        
        for (const [label, groupSessions] of Object.entries(groups)) {
            if (groupSessions.length === 0) continue;
            
            html += `<div class="session-group">`;
            html += `<div class="session-group-header">${label}</div>`;
            
            groupSessions.forEach(s => {
                const isActive = s.session_id === state.sessionId;
                const shortId = s.session_id.split('_')[1] || s.session_id;
                
                html += `
                    <div class="session-item ${isActive ? 'active' : ''}" 
                         data-session-id="${s.session_id}"
                         onclick="loadSession('${s.session_id}')">
                        <div class="session-info">
                            <div class="session-name">${s.first_name} ${s.last_name}</div>
                            <div class="session-meta">${shortId} • ${s.traits || 'No traits'}</div>
                        </div>
                        <button class="session-delete" onclick="event.stopPropagation(); deleteSessionById('${s.session_id}')">✕</button>
                    </div>
                `;
            });
            
            html += `</div>`;
        }
        
        container.innerHTML = html;
    } catch (e) {
        console.error("Failed to load sessions", e);
        container.innerHTML = '<div class="sessions-empty">Error loading sessions</div>';
    }
}

/**
 * Load an existing session by ID.
 */
async function loadSession(sessionId) {
    if (sessionId === state.sessionId) {
        closeSessionsModal();
        return;
    }
    
    try {
        const data = await API.getSession(sessionId);
        setActiveSession(data);
        document.getElementById("chat-box").innerHTML = "";
        refreshGraph();
        closeSessionsModal();
        UI.addMessage("system", `Loaded session: ${data.first_name} ${data.last_name}`);
    } catch (e) {
        console.error("Failed to load session", e);
        UI.addMessage("system", "Failed to load session.");
    }
}

/**
 * Delete a session by ID.
 */
async function deleteSessionById(sessionId) {
    if (!confirm("Delete this session?")) return;
    
    try {
        await API.deleteSession(sessionId);
        
        // If deleted current session, create new one
        if (sessionId === state.sessionId) {
            state.sessionId = null;
            state.userId = null;
            closeSessionsModal();
            initSession(true);
        } else {
            // Refresh the modal
            await renderSessionsModal();
        }
    } catch (e) {
        console.error("Failed to delete session", e);
    }
}

// --- Logic ---

export async function refreshGraph() {
    try {
        if (!state.userId) return;
        const data = await API.fetchGraphData(state.userId);
        
        const container = document.getElementById("graph-container");
        Graph.renderGraph(container, data);

        document.getElementById("node-count").textContent = data.nodes?.length || 0;
        document.getElementById("edge-count").textContent = data.edges?.length || 0;
        
        return { nodes: data.nodes?.length || 0, edges: data.edges?.length || 0 };
    } catch (e) {
        console.error("Graph refresh failed", e);
        return { nodes: 0, edges: 0 };
    }
}

/**
 * Schedule multiple graph refreshes to catch Zep's async graph processing.
 * Zep extracts entities and builds the knowledge graph asynchronously after
 * messages are added, so we need to poll for updates.
 */
export async function scheduleGraphRefresh() {
    let lastCounts = await refreshGraph();
    
    for (const delay of CONFIG.POLL_DELAYS) {
        await new Promise(resolve => setTimeout(resolve, delay));
        const counts = await refreshGraph();
        
        // If graph changed, log it
        if (counts.nodes !== lastCounts.nodes || counts.edges !== lastCounts.edges) {
            console.log(`Graph updated: ${counts.nodes} nodes, ${counts.edges} edges`);
        }
        lastCounts = counts;
    }
}

async function populateModels() {
    const select = document.getElementById("model-select");
    if (!select) return;
    
    try {
        const data = await API.fetchModels();
        select.innerHTML = "";
        
        const freeGroup = document.createElement("optgroup");
        freeGroup.label = "Free Models";
        const paidGroup = document.createElement("optgroup");
        paidGroup.label = "All Models";

        data.models.sort((a, b) => a.name.localeCompare(b.name));
        data.models.forEach(model => {
            const option = document.createElement("option");
            option.value = model.id;
            option.textContent = model.name.replace(/\s*\(free\)\s*/gi, '').trim();
            (model.pricing.prompt === "0" ? freeGroup : paidGroup).appendChild(option);
        });
        select.append(freeGroup, paidGroup);
        select.value = CONFIG.DEFAULT_MODEL;
    } catch (e) {
        select.innerHTML = `<option value='${CONFIG.FALLBACK_MODEL}'>Fallback: Llama 3.2 3B</option>`;
    }
}

async function populateEmbeddingModels() {
    const select = document.getElementById("embedding-model-select");
    if (!select) return;
    
    try {
        const data = await API.fetchEmbeddingModels();
        select.innerHTML = "";
        data.models.forEach(model => {
            const option = document.createElement("option");
            option.value = model.id;
            option.textContent = model.name;
            select.appendChild(option);
        });
        select.value = data.current || CONFIG.DEFAULT_EMBEDDING_MODEL;
        
        // Update on change
        select.addEventListener("change", async () => {
            await API.setEmbeddingModel(select.value);
        });
    } catch (e) {
        console.error("Failed to load embedding models", e);
    }
}

async function fetchSchema() {
    try {
        const data = await API.fetchSchema();
        const editor = document.getElementById("schema-editor");
        if (editor) editor.value = JSON.stringify(data, null, 2);
    } catch (e) { console.error(e); }
}

async function handleSaveSchema() {
    try {
        const schema = JSON.parse(document.getElementById("schema-editor").value);
        const res = await API.saveSchema(schema);
        if (res.status === "success") {
            window.closeSchemaModal();
            alert("Schema Updated");
        }
    } catch (e) { alert("Error: Invalid JSON"); }
}

function toggleZepSettings() {
    const isEnabled = document.getElementById("zep-toggle")?.checked;
    const settings = document.getElementById("zep-settings");
    const disabled = document.getElementById("zep-disabled-msg");
    if (settings) settings.style.display = isEnabled ? "block" : "none";
    if (disabled) disabled.style.display = isEnabled ? "none" : "block";
}

function toggleRAGSettings() {
    const isEnabled = document.getElementById("rag-toggle")?.checked;
    const settings = document.getElementById("rag-settings");
    if (settings) settings.style.display = isEnabled ? "block" : "none";
    if (isEnabled) updateRAGStatus();
}

async function updateRAGStatus() {
    const status = document.getElementById("rag-status");
    if (!status) return;
    
    try {
        const data = await API.fetchRAGStats();
        status.textContent = `✓ ${data.document_count} docs indexed | Model: ${data.embedding_model}`;
        status.style.color = COLORS.green;
    } catch (e) {
        status.textContent = "✗ Error";
        status.style.color = COLORS.red;
    }
}

async function handleIngest() {
    const textArea = document.getElementById("document-text-input");
    const text = textArea?.value?.trim();
    if (!text) return alert("Enter document text");
    
    const status = document.getElementById("rag-status");
    if (status) {
        status.textContent = "⏳ Ingesting...";
        status.style.color = COLORS.blue;
    }
    
    try {
        const data = await API.ingestDocument(text, { source: "manual" });
        if (status) {
            status.textContent = `✓ Added ${data.added} doc (total: ${data.total})`;
            status.style.color = COLORS.green;
        }
        textArea.value = "";
    } catch (e) {
        if (status) {
            status.textContent = `✗ Error: ${e.message}`;
            status.style.color = COLORS.red;
        }
    }
}

async function handleClearRAG() {
    if (!confirm("Clear all RAG documents?")) return;
    
    try {
        await API.clearRAG();
        updateRAGStatus();
    } catch (e) {
        console.error("Clear failed", e);
    }
}

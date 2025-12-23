/**
 * Main Application Module
 */

import * as API from './api.js';
import * as Graph from './graph.js';
import * as UI from './ui.js';
import { CONFIG } from './config.js';
import { sendMessage } from './chat.js';

export const state = {
    sessionId: null,
    userId: null,
};

document.addEventListener("DOMContentLoaded", () => {
    Promise.all([initSession(), populateModels()]).catch(console.error);
    setupEventListeners();
});

function setupEventListeners() {
    document.getElementById("zep-toggle")?.addEventListener("change", toggleZepSettings);
    document.getElementById("send-btn")?.addEventListener("click", handleSendMessage);
    document.getElementById("message-input")?.addEventListener("keydown", (e) => {
        if (e.key === "Enter") handleSendMessage();
    });
    document.getElementById("ingest-btn")?.addEventListener("click", handleIngest);
    window.addEventListener("resize", () => Graph.resizeGraph());
}

async function handleSendMessage() {
    await sendMessage(state);
    refreshGraph();
}

async function initSession(forceNew = false) {
    if (!forceNew && state.sessionId) return;

    const payload = {
        first_name: document.getElementById("first-name")?.value || "User",
        last_name: document.getElementById("last-name")?.value || "",
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

Object.assign(window, {
    initSession,
    refreshGraph,
    openSessionsModal,
    closeSessionsModal,
    loadSession,
    deleteSessionById,
    sendMessage: handleSendMessage,
    resetZoom: Graph.resetZoom,
});

function setActiveSession(data) {
    state.sessionId = data.session_id;
    state.userId = data.user_id;
    
    const badge = document.getElementById("session-badge");
    if (badge) badge.textContent = `ID: ${state.sessionId.split("_")[1] || state.sessionId}`;
    
    if (data.first_name) document.getElementById("first-name").value = data.first_name;
    if (data.last_name) document.getElementById("last-name").value = data.last_name;
}

async function openSessionsModal() {
    document.getElementById("sessions-modal")?.classList.add("active");
    await renderSessionsModal();
}

function closeSessionsModal() {
    document.getElementById("sessions-modal")?.classList.remove("active");
}

function groupSessionsByTime(sessions) {
    const now = new Date();
    const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    const yesterday = new Date(today); yesterday.setDate(yesterday.getDate() - 1);
    const weekAgo = new Date(today); weekAgo.setDate(weekAgo.getDate() - 7);
    
    const groups = { "Today": [], "Yesterday": [], "This Week": [], "Older": [] };
    
    sessions.forEach(s => {
        const created = new Date(s.created_at);
        if (created >= today) groups["Today"].push(s);
        else if (created >= yesterday) groups["Yesterday"].push(s);
        else if (created >= weekAgo) groups["This Week"].push(s);
        else groups["Older"].push(s);
    });
    
    return groups;
}

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
            if (!groupSessions.length) continue;
            
            html += `<div class="session-group"><div class="session-group-header">${label}</div>`;
            
            groupSessions.forEach(s => {
                const isActive = s.session_id === state.sessionId;
                const shortId = s.session_id.split('_')[1] || s.session_id;
                html += `
                    <div class="session-item ${isActive ? 'active' : ''}" onclick="loadSession('${s.session_id}')">
                        <div class="session-info">
                            <div class="session-name">${s.first_name} ${s.last_name}</div>
                            <div class="session-meta">${shortId}</div>
                        </div>
                        <button class="session-delete" onclick="event.stopPropagation(); deleteSessionById('${s.session_id}')">✕</button>
                    </div>`;
            });
            
            html += `</div>`;
        }
        
        container.innerHTML = html;
    } catch (e) {
        console.error("Failed to load sessions", e);
        container.innerHTML = '<div class="sessions-empty">Error loading sessions</div>';
    }
}

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

async function deleteSessionById(sessionId) {
    if (!confirm("Delete this session?")) return;
    
    try {
        await API.deleteSession(sessionId);
        if (sessionId === state.sessionId) {
            state.sessionId = null;
            state.userId = null;
            closeSessionsModal();
            initSession(true);
        } else {
            await renderSessionsModal();
        }
    } catch (e) {
        console.error("Failed to delete session", e);
    }
}

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

export async function scheduleGraphRefresh() {
    let lastCounts = await refreshGraph();
    
    for (const delay of CONFIG.POLL_DELAYS) {
        await new Promise(resolve => setTimeout(resolve, delay));
        const counts = await refreshGraph();
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

function toggleZepSettings() {
    const isEnabled = document.getElementById("zep-toggle")?.checked;
    const settings = document.getElementById("zep-settings");
    const disabled = document.getElementById("zep-disabled-msg");
    if (settings) settings.style.display = isEnabled ? "block" : "none";
    if (disabled) disabled.style.display = isEnabled ? "none" : "block";
}

async function handleIngest() {
    const textArea = document.getElementById("document-text-input");
    const text = textArea?.value?.trim();
    if (!text) return alert("Enter document text");
    
    const ingestArea = document.getElementById("ingest-area");
    const btn = document.getElementById("ingest-btn");
    const originalText = btn.textContent;
    btn.textContent = "Adding...";
    btn.disabled = true;
    
    try {
        await API.ingestDocument(text, { source: "manual" });
        textArea.value = "";
        ingestArea.style.display = "none";
        UI.addMessage("system", "✓ Context added to RAG.");
    } catch (e) {
        alert(`Error adding context: ${e.message}`);
    } finally {
        btn.textContent = originalText;
        btn.disabled = false;
    }
}

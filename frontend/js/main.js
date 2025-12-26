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
    Promise.all([restoreSessionOrInit(), populateModels(), checkRAGStatus()]).catch(console.error);
    setupEventListeners();
});

function setupEventListeners() {
    document.getElementById("send-btn")?.addEventListener("click", handleSendMessage);
    document.getElementById("message-input")?.addEventListener("keydown", (e) => {
        if (e.key === "Enter") handleSendMessage();
    });
    
    // File upload handlers
    document.getElementById("upload-toggle-btn")?.addEventListener("click", () => {
        const uploadArea = document.getElementById("upload-area");
        uploadArea.style.display = uploadArea.style.display === "none" ? "block" : "none";
    });
    
    document.getElementById("select-file-btn")?.addEventListener("click", () => {
        document.getElementById("file-input")?.click();
    });
    
    document.getElementById("file-input")?.addEventListener("change", handleFileUpload);
    
    window.addEventListener("resize", () => Graph.resizeGraph());
}

async function handleSendMessage() {
    await sendMessage(state);
    refreshGraph();
}

async function restoreSessionOrInit() {
    const lastSessionId = localStorage.getItem("zep_last_session_id");
    if (lastSessionId) {
        try {
            await loadSession(lastSessionId);
            return;
        } catch (e) {
            console.log("Could not restore last session, creating new one.");
            localStorage.removeItem("zep_last_session_id");
        }
    }
    await initSession(true);
}

async function initSession(forceNew = false) {
    if (!forceNew && state.sessionId) return;
    
    // If forcing new, clear the last session ID so we don't just reload it next time effectively
    // actually, we will update it in setActiveSession, so it's fine.

    const storedUserId = localStorage.getItem("zep_user_id");
    
    const payload = {
        first_name: document.getElementById("first-name")?.value || "User",
        last_name: document.getElementById("last-name")?.value || "",
        user_id: storedUserId || undefined
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
    
    if (data.session_id) {
        localStorage.setItem("zep_last_session_id", data.session_id);
    }

    if (data.user_id) {
        localStorage.setItem("zep_user_id", data.user_id);
    }
    
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
                const dateObj = new Date(s.created_at);
                const dateStr = dateObj.toLocaleDateString() + ' ' + dateObj.toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
                
                html += `
                    <div class="session-item ${isActive ? 'active' : ''}" onclick="loadSession('${s.session_id}')">
                        <div class="session-info">
                            <div class="session-name">${s.first_name || 'User'} ${s.last_name || ''}</div>
                            <div class="session-meta">
                                <span>${shortId}</span> • <span style="font-size: 0.7rem; opacity: 0.8">${dateStr}</span>
                            </div>
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
        
        // If we deleted the "last session" stored in local storage, clear it
        if (localStorage.getItem("zep_last_session_id") === sessionId) {
            localStorage.removeItem("zep_last_session_id");
        }

        if (sessionId === state.sessionId) {
            state.sessionId = null;
            // state.userId = null; // Keep user ID!
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

async function handleFileUpload(event) {
    const fileInput = event.target;
    const file = fileInput.files?.[0];
    
    if (!file) return;
    
    const uploadArea = document.getElementById("upload-area");
    const statusDiv = document.getElementById("upload-status");
    const selectBtn = document.getElementById("select-file-btn");
    
    // Validate file type
    const allowedExts = ['pdf', 'txt', 'md', 'markdown', 'docx'];
    const fileExt = file.name.split('.').pop().toLowerCase();
    
    if (!allowedExts.includes(fileExt)) {
        UI.showToast(`Unsupported file type: ${fileExt}. Use PDF, TXT, MD, or DOCX.`, "error", 5000);
        fileInput.value = "";
        return;
    }
    
    // Show uploading status
    statusDiv.style.display = "block";
    statusDiv.innerHTML = `<i class="fa-solid fa-spinner fa-spin"></i> Uploading ${file.name}...`;
    selectBtn.disabled = true;
    
    try {
        const result = await API.uploadDocument(file, state.sessionId);
        
        statusDiv.innerHTML = `
            <div style="color: var(--ctp-green)">
                <i class="fa-solid fa-check-circle"></i> 
                Successfully added: ${result.filename}
                <br>
                <span style="font-size: 0.75rem; color: var(--ctp-subtext0)">
                    ${result.chunks} chunks indexed for retrieval
                </span>
            </div>
        `;
        
        UI.addMessage("system", `✓ Document indexed: ${result.filename} (${result.chunks} chunks)`);
        
        // Show RAG indicator
        const ragIndicator = document.getElementById("rag-indicator");
        if (ragIndicator) {
            ragIndicator.style.display = "inline";
        }
        
        // Clear after delay
        setTimeout(() => {
            uploadArea.style.display = "none";
            statusDiv.style.display = "none";
            fileInput.value = "";
        }, 3000);
        
    } catch (e) {
        console.error("Upload failed:", e);
        statusDiv.innerHTML = `<div style="color: var(--ctp-red)"><i class="fa-solid fa-exclamation-triangle"></i> ${e.message}</div>`;
        UI.showToast(`Upload failed: ${e.message}`, "error", 5000);
    } finally {
        selectBtn.disabled = false;
    }
}

// Check if RAG has documents on load
async function checkRAGStatus() {
    try {
        const stats = await API.fetchRAGStats();
        const hasDocuments = stats.total_vectors > 0;
        
        const ragIndicator = document.getElementById("rag-indicator");
        if (ragIndicator && hasDocuments) {
            ragIndicator.style.display = "inline";
        }
    } catch (e) {
        console.log("RAG stats unavailable:", e.message);
    }
}


import * as API from './api.js';
import * as Graph from './graph.js';
import * as UI from './ui.js';
import { sendMessage } from './chat.js';

// Global State
export const state = {
    sessionId: null,
    userId: null,
    graphSource: "zep", // "zep" or "local"
};

// --- Initialization ---
document.addEventListener("DOMContentLoaded", () => {
    // Parallel Init
    Promise.all([
        initSession(),
        fetchSchema(),
        populateModels()
    ]).catch(console.error);

    setupEventListeners();
    checkLocalGraphRAGStatus();
});

function setupEventListeners() {
    // Configuration Toggles
    document.getElementById("zep-toggle").addEventListener("change", toggleZepSettings);
    
    // Graph Source Radio Buttons
    const radios = document.getElementsByName("graph-source");
    radios.forEach(r => r.addEventListener("change", updateGraphSource));

    // Chat
    document.getElementById("send-btn").addEventListener("click", handleSendMessage);
    document.getElementById("message-input").addEventListener("keydown", (e) => {
        if (e.key === "Enter") handleSendMessage();
    });

    // Ingest
    const ingestBtn = document.querySelector("#local-graphrag-settings button");
    if(ingestBtn) ingestBtn.addEventListener("click", handleIngest);

    // Schema
    const saveSchemaBtn = document.querySelector("#schema-modal .modal-footer button:last-child");
    if(saveSchemaBtn) saveSchemaBtn.addEventListener("click", handleSaveSchema);
    
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
        first_name: document.getElementById("first-name").value,
        last_name: document.getElementById("last-name").value,
        traits: document.getElementById("traits-input").value,
        preferences: document.getElementById("preferences-input").value,
        business_data: document.getElementById("business-data-input").value,
    };

    try {
        const data = await API.initSession(payload);
        state.sessionId = data.session_id;
        state.userId = data.user_id;

        const badge = document.getElementById("session-badge");
        if(badge) badge.textContent = `ID: ${state.sessionId.split("_")[1] || state.sessionId}`;
        
        document.getElementById("chat-box").innerHTML = "";
        refreshGraph();
        UI.addMessage("system", "Session initialized.");
    } catch (e) {
        console.error("Session init failed", e);
    }
}

// Global scope required for HTML onclicks if we didn't remove them yet
// But we aim to remove them.
// For compatibility with current index.html buttons (New Session, Edit Schema, Refresh Graph, Reset Zoom)
// We will attach them to window for now, then clean up index.html.

window.initSession = initSession;
window.openSchemaModal = () => document.getElementById("schema-modal").classList.add("active");
window.closeSchemaModal = () => document.getElementById("schema-modal").classList.remove("active");
window.refreshGraph = refreshGraph;
window.resetZoom = Graph.resetZoom;
window.ingestDocuments = handleIngest; // Backwards compat
window.saveSchema = handleSaveSchema;
window.sendMessage = handleSendMessage;
window.updateGraphSource = updateGraphSource;
window.toggleZepSettings = toggleZepSettings;

// --- Logic ---

export async function refreshGraph() {
    try {
        if (state.graphSource === "zep" && !state.userId) return;
        const data = await API.fetchGraphData(state.userId, state.graphSource);
        
        const container = document.getElementById("graph-container");
        Graph.renderGraph(container, data);

        document.getElementById("node-count").textContent = data.nodes?.length || 0;
        document.getElementById("edge-count").textContent = data.edges?.length || 0;
    } catch (e) {
        console.error("Graph refresh failed", e);
    }
}

async function populateModels() {
    const select = document.getElementById("model-select");
    try {
        const data = await API.fetchModels();
        select.innerHTML = "";
        
        const freeGroup = document.createElement("optgroup"); freeGroup.label = "Free Models";
        const paidGroup = document.createElement("optgroup"); paidGroup.label = "All Models";

        data.models.sort((a, b) => a.name.localeCompare(b.name));
        data.models.forEach(model => {
            const option = document.createElement("option");
            option.value = model.id;
            const cleanName = model.name.replace(/\s*\(free\)\s*/gi, '').trim();
            option.textContent = cleanName;
            (model.pricing.prompt === "0" ? freeGroup : paidGroup).appendChild(option);
        });
        select.append(freeGroup, paidGroup);
        select.value = "google/gemini-2.0-flash-exp:free";
    } catch (e) {
        select.innerHTML = "<option value='meta-llama/llama-3.2-3b-instruct:free'>Fallback: Llama 3.2 3B</option>";
    }
}

async function fetchSchema() {
    try {
        const data = await API.fetchSchema();
        document.getElementById("schema-editor").value = JSON.stringify(data, null, 2);
    } catch (e) { console.error(e); }
}

async function handleSaveSchema() {
    try {
        const schema = JSON.parse(document.getElementById("schema-editor").value);
        const res = await API.saveSchema(schema);
        if (res.status === "success") {
            window.closeSchemaModal();
            alert("Schema Updated Successfully");
        }
    } catch (e) { alert("Error: Invalid JSON"); }
}

function toggleZepSettings() {
    const isEnabled = document.getElementById("zep-toggle").checked;
    document.getElementById("zep-settings").style.display = isEnabled ? "block" : "none";
    document.getElementById("zep-disabled-msg").style.display = isEnabled ? "none" : "block";
}

function updateGraphSource() {
    const isLocal = document.getElementById("graph-source-local").checked;
    state.graphSource = isLocal ? "local" : "zep";
    document.getElementById("local-graphrag-settings").style.display = isLocal ? "block" : "none";
    if(isLocal) checkLocalGraphRAGStatus();
    refreshGraph();
}

async function checkLocalGraphRAGStatus() {
    const statusDiv = document.getElementById("local-graphrag-status");
    document.getElementById("local-graphrag-settings").style.display = state.graphSource === "local" ? "block" : "none"; // Ensure state consistency
    try {
        const data = await API.checkLocalGraphStatus();
        if (data.available) {
            if (data.ingested) {
                statusDiv.textContent = `✓ Ready: ${data.entities} entities, ${data.relationships} relationships`;
                statusDiv.style.color = "var(--ctp-green)";
            } else {
                statusDiv.textContent = "⚠ No documents ingested.";
                statusDiv.style.color = "var(--ctp-peach)";
            }
        } else {
            statusDiv.textContent = "✗ Local GraphRAG not available.";
            statusDiv.style.color = "var(--ctp-red)";
        }
    } catch (e) {
        statusDiv.textContent = "✗ Error checking status";
    }
}

async function handleIngest() {
    const paths = document.getElementById("document-paths-input").value.split('\n').map(p => p.trim()).filter(p => p);
    if (!paths.length) return alert("Enter document paths");
    
    const statusDiv = document.getElementById("local-graphrag-status");
    statusDiv.textContent = "⏳ Ingesting...";
    statusDiv.style.color = "var(--ctp-blue)";
    
    try {
        const data = await API.ingestDocuments(paths);
        if (data.status === "success") {
            statusDiv.textContent = `✓ Done: ${data.chunks} chunks, ${data.entities} entities.`;
            statusDiv.style.color = "var(--ctp-green)";
            refreshGraph();
        } else {
            statusDiv.textContent = `✗ Error: ${data.message}`;
            statusDiv.style.color = "var(--ctp-red)";
        }
    } catch (e) {
        statusDiv.textContent = `✗ Error: ${e.message}`;
        statusDiv.style.color = "var(--ctp-red)";
    }
}

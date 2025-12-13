
import * as API from './api.js';
import * as Graph from './graph.js';
import * as UI from './ui.js';
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
        state.sessionId = data.session_id;
        state.userId = data.user_id;

        const badge = document.getElementById("session-badge");
        if (badge) badge.textContent = `ID: ${state.sessionId.split("_")[1] || state.sessionId}`;
        
        document.getElementById("chat-box").innerHTML = "";
        refreshGraph();
        UI.addMessage("system", "Session initialized.");
    } catch (e) {
        console.error("Session init failed", e);
    }
}

// Global scope for HTML onclick
window.initSession = initSession;
window.openSchemaModal = () => document.getElementById("schema-modal")?.classList.add("active");
window.closeSchemaModal = () => document.getElementById("schema-modal")?.classList.remove("active");
window.refreshGraph = refreshGraph;
window.resetZoom = Graph.resetZoom;
window.sendMessage = handleSendMessage;

// --- Logic ---

export async function refreshGraph() {
    try {
        if (!state.userId) return;
        const data = await API.fetchGraphData(state.userId);
        
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
        select.value = "google/gemini-2.0-flash-exp:free";
    } catch (e) {
        select.innerHTML = "<option value='meta-llama/llama-3.2-3b-instruct:free'>Fallback: Llama 3.2 3B</option>";
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
        select.value = data.current || "openai/text-embedding-3-small";
        
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
        status.style.color = "var(--ctp-green)";
    } catch (e) {
        status.textContent = "✗ Error";
        status.style.color = "var(--ctp-red)";
    }
}

async function handleIngest() {
    const textArea = document.getElementById("document-text-input");
    const text = textArea?.value?.trim();
    if (!text) return alert("Enter document text");
    
    const status = document.getElementById("rag-status");
    if (status) {
        status.textContent = "⏳ Ingesting...";
        status.style.color = "var(--ctp-blue)";
    }
    
    try {
        const data = await API.ingestDocument(text, { source: "manual" });
        if (status) {
            status.textContent = `✓ Added ${data.added} doc (total: ${data.total})`;
            status.style.color = "var(--ctp-green)";
        }
        textArea.value = "";
    } catch (e) {
        if (status) {
            status.textContent = `✗ Error: ${e.message}`;
            status.style.color = "var(--ctp-red)";
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

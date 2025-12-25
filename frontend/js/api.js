/**
 * API Client Module
 */

const HEADERS = { "Content-Type": "application/json" };

async function fetchJson(url, options = {}) {
    const res = await fetch(url, options);
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    return res.json();
}

// Sessions
export const initSession = (data) => fetchJson("/session", { method: "POST", headers: HEADERS, body: JSON.stringify(data) });
export const listSessions = () => fetchJson("/session/list");
export const getSession = (sessionId) => fetchJson(`/session/${sessionId}`);
export const deleteSession = (sessionId) => fetchJson(`/session/${sessionId}`, { method: "DELETE" });

// Models
export const fetchModels = () => fetchJson("/models/all");

// Graph
export const fetchGraphData = (userId) => fetchJson(`/graph/${userId}`);

// RAG
export const fetchRAGStats = () => fetchJson("/rag/stats");
export const searchRAG = (query, topK) => fetchJson("/rag/search", { method: "POST", headers: HEADERS, body: JSON.stringify({ query, top_k: topK }) });
export const clearRAG = () => fetchJson("/rag/clear", { method: "POST" });

/**
 * Upload a document file to RAG (PDF, TXT, MD, DOCX)
 * @param {File} file - File to upload
 * @param {string} sessionId - Optional session ID
 * @returns {Promise<Object>} Upload result
 */
export const uploadDocument = async (file, sessionId = null) => {
    const formData = new FormData();
    formData.append("file", file);
    if (sessionId) formData.append("session_id", sessionId);
    
    const res = await fetch("/rag/upload", {
        method: "POST",
        body: formData,
    });
    
    if (!res.ok) {
        const error = await res.json().catch(() => ({ detail: `HTTP ${res.status}` }));
        throw new Error(error.detail || `Upload failed: ${res.status}`);
    }
    
    return res.json();
};

// Chat (returns raw fetch for streaming)
export const fetchChatStream = (payload, signal) => fetch("/chat", { method: "POST", headers: HEADERS, body: JSON.stringify(payload), signal });

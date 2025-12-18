/**
 * API Client Module
 * Simple fetch wrappers for all backend endpoints.
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

// Schema
export const fetchSchema = () => fetchJson("/schema");
export const saveSchema = (schema) => fetchJson("/schema", { method: "POST", headers: HEADERS, body: JSON.stringify(schema) });

// Models
export const fetchModels = () => fetchJson("/models/all");

// Graph
export const fetchGraphData = (userId) => fetchJson(`/graph/${userId}`);

// RAG
export const fetchRAGStats = () => fetchJson("/rag/stats");
export const ingestDocument = (text, metadata) => fetchJson("/rag/ingest", { method: "POST", headers: HEADERS, body: JSON.stringify({ text, metadata }) });
export const searchRAG = (query, topK) => fetchJson("/rag/search", { method: "POST", headers: HEADERS, body: JSON.stringify({ query, top_k: topK }) });
export const clearRAG = () => fetchJson("/rag/clear", { method: "POST" });

// Chat (returns raw fetch for streaming)
export const fetchChatStream = (payload, signal) => fetch("/chat", { method: "POST", headers: HEADERS, body: JSON.stringify(payload), signal });


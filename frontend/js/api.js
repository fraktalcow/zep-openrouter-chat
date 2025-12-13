
// API Client Module

const HEADERS = { "Content-Type": "application/json" };

export async function fetchJson(url, options = {}) {
    try {
        const res = await fetch(url, options);
        if (!res.ok) {
            throw new Error(`HTTP error! status: ${res.status}`);
        }
        return await res.json();
    } catch (error) {
        console.error(`API Error (${url}):`, error);
        throw error;
    }
}

export async function fetchSchema() {
    return fetchJson("/schema");
}

export async function saveSchema(schema) {
    return fetchJson("/schema", {
        method: "POST",
        headers: HEADERS,
        body: JSON.stringify(schema),
    });
}

export async function fetchModels() {
    return fetchJson("/models/all");
}

export async function initSession(payload) {
    return fetchJson("/session", {
        method: "POST",
        headers: HEADERS,
        body: JSON.stringify(payload),
    });
}

export async function checkLocalGraphStatus() {
    return fetchJson("/local-graphrag/status");
}

export async function ingestDocuments(paths) {
    return fetchJson("/local-graphrag/ingest", {
        method: "POST",
        headers: HEADERS,
        body: JSON.stringify({ document_paths: paths }),
    });
}

export async function fetchGraphData(userId, source) {
    const url = source === "local" ? "/local-graphrag/graph" : `/graph/${userId}`;
    return fetchJson(url);
}

// Chat is special because it deals with streams, but we can wrap the fetch
export async function fetchChatStream(payload, signal) {
    return fetch("/chat", {
        method: "POST",
        headers: HEADERS,
        body: JSON.stringify(payload),
        signal,
    });
}

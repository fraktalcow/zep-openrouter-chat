/**
 * Chat Module
 * Handles message sending, streaming responses, and SSE parsing.
 */

import * as API from './api.js';
import * as UI from './ui.js';
import { CONFIG, COLORS } from './config.js';
import { scheduleGraphRefresh } from './main.js';

/**
 * Parse markdown if marked library is available.
 * @param {string} text - Raw text to parse
 * @returns {string} HTML string
 */
const parseMarkdown = (text) => 
    typeof marked !== 'undefined' ? marked.parse(text) : text;

/**
 * Send a chat message and stream the response.
 * @param {{sessionId: string, userId: string}} state - Current session state
 * @returns {Promise<void>}
 */
export async function sendMessage(state) {
    const input = document.getElementById("message-input");
    const text = input?.value?.trim();
    if (!text || !state.sessionId) return;

    // UI Updates
    UI.addMessage("user", text);
    input.value = "";
    input.disabled = true;
    
    const sendBtn = document.getElementById("send-btn");
    if (sendBtn) sendBtn.disabled = true;

    // Default settings (UI elements removed for simplicity)
    const useAi = true; // Always use AI
    const modelId = "meta-llama/llama-3.2-3b-instruct:free"; // Default model
    const modelName = "Llama 3.2 3B";
    const temperature = 0.7;
    const maxTokens = 1024;
    const useMemory = true; // Always use memory
    const useRetrieval = true; // Always use graph retrieval
    
    // Auto-enable RAG if documents are indexed (indicator is visible)
    const ragIndicator = document.getElementById("rag-indicator");
    const useRag = ragIndicator?.style.display !== "none";

    // Show loading
    let loadingMsgEl = UI.createLoadingMessage(modelName);
    const startTime = Date.now();
    const loadingInterval = setInterval(() => {
        const elapsed = Math.floor((Date.now() - startTime) / 1000);
        const color = elapsed > CONFIG.LOADING_WARNING_THRESHOLD_S ? COLORS.peach : null;
        UI.updateLoadingStatus(loadingMsgEl, `Waiting... (${elapsed}s)`, color);
    }, 1000);

    const abortController = new AbortController();
    setTimeout(() => abortController.abort(), CONFIG.REQUEST_TIMEOUT_MS);

    try {
        const payload = {
            session_id: state.sessionId,
            message: text,
            use_memory: useMemory,
            use_retrieval: useRetrieval,
            use_rag: useRag,
            use_ai: useAi,
            model_name: modelId,
            temperature: temperature,
            max_tokens: maxTokens,
        };

        const res = await API.fetchChatStream(payload, abortController.signal);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);

        // Stream handling
        const reader = res.body.getReader();
        const decoder = new TextDecoder();
        let buffer = "";
        let assistantMsgEl = null;
        let fullResponse = "";

        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            
            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split("\n\n");
            buffer = lines.pop() || "";

            for (const line of lines) {
                if (!line.trim() || !line.startsWith("data: ")) continue;
                
                try {
                    const data = JSON.parse(line.slice(6));
                    
                    // Status Step Update
                    if (data.type === "step") {
                        UI.updateLoadingStatus(loadingMsgEl, data.message, COLORS.teal);
                    }
                    
                    // RAG Sources
                    else if (data.type === "rag_sources") {
                        UI.renderRagSources(data.chunks);
                    }
                    
                    // Context Block Debug
                    else if (data.type === "context") {
                        console.log("Context built:", data.context_block);
                    }

                    // Content Streaming - also check for API errors
                    else if (data.type === "content" && data.chunk) {
                        // Check if chunk is an API error
                        if (data.chunk.includes("⚠️") && data.chunk.includes("API Error")) {
                            // Extract status code for toast
                            const match = data.chunk.match(/API Error \((\d+)\)/);
                            const statusCode = match ? match[1] : "Unknown";
                            UI.showToast(`API Error ${statusCode}: Model rate-limited. Try a different model.`, "error", 8000);
                        }
                        
                        if (!assistantMsgEl) {
                            if (loadingMsgEl?.parentNode) loadingMsgEl.remove();
                            assistantMsgEl = UI.addMessage("assistant", "", modelName);
                        }
                        fullResponse += data.chunk;
                        if (assistantMsgEl) {
                            assistantMsgEl.innerHTML = parseMarkdown(fullResponse);
                        }
                        UI.scrollToBottom();
                    } 
                    
                    // Completion
                    else if (data.type === "done") {
                        if (!assistantMsgEl) {
                            if (loadingMsgEl?.parentNode) loadingMsgEl.remove();
                            assistantMsgEl = UI.addMessage("assistant", "", modelName);
                        }
                        fullResponse = data.response || fullResponse;
                        if (assistantMsgEl) {
                            assistantMsgEl.innerHTML = parseMarkdown(fullResponse);
                        }
                        UI.scrollToBottom();
                    } 
                    
                    // Error
                    else if (data.type === "error") {
                        UI.showToast(data.error, "error", 8000);
                        if (data.error.includes("Unknown session")) {
                             // Reset session state so user can create new one
                             console.warn("Session invalid, resetting...");
                             state.sessionId = null;
                             state.userId = null;
                             document.getElementById("session-badge").textContent = "ID: INVALID";
                        }
                        // Stop processing this stream
                        throw new Error("API_ERROR: " + data.error);
                    }
                } catch (e) {
                    // Ignore expected API errors that we threw ourselves
                    if (e.message && e.message.startsWith("API_ERROR:")) {
                        throw e; 
                    }
                    console.error("SSE parse error", e, line);
                }
            }
        }
        
        // Zep processes graph asynchronously - poll for updates
        scheduleGraphRefresh();

    } catch (e) {
        if (loadingMsgEl?.parentNode) loadingMsgEl.remove();
        let errorText = `Error: ${e.message}`;
        if (e.message.startsWith("API_ERROR:")) errorText = e.message.replace("API_ERROR: ", "⚠️ ");
        if (e.name === 'AbortError') errorText = "⚠️ Request timed out.";
        UI.addMessage("system", errorText);
    } finally {
        clearInterval(loadingInterval);
        input.disabled = false;
        if (sendBtn) sendBtn.disabled = false;
        input?.focus();
    }
}


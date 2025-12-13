
import * as API from './api.js';
import * as UI from './ui.js';
import { refreshGraph } from './main.js';

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

    // Get settings
    const useAi = document.getElementById("ai-toggle")?.checked ?? true;
    const useRag = document.getElementById("rag-toggle")?.checked ?? false;
    const modelSelect = document.getElementById("model-select");
    const modelId = modelSelect?.value || "meta-llama/llama-3.2-3b-instruct:free";
    const modelName = modelSelect?.selectedOptions[0]?.textContent || modelId;

    // Show loading
    let loadingMsgEl = UI.createLoadingMessage(modelName);
    const startTime = Date.now();
    const loadingInterval = setInterval(() => {
        const elapsed = Math.floor((Date.now() - startTime) / 1000);
        UI.updateLoadingStatus(loadingMsgEl, `Waiting... (${elapsed}s)`, elapsed > 5 ? "var(--ctp-peach)" : null);
    }, 1000);

    const abortController = new AbortController();
    setTimeout(() => abortController.abort(), 60000);

    try {
        const payload = {
            session_id: state.sessionId,
            message: text,
            use_memory: document.getElementById("memory-toggle")?.checked ?? true,
            use_retrieval: document.getElementById("retrieval-toggle")?.checked ?? true,
            use_rag: useRag,
            use_ai: useAi,
            model_name: modelId,
            temperature: parseFloat(document.getElementById("temp-input")?.value || "0.7"),
            max_tokens: parseInt(document.getElementById("max-tokens-input")?.value || "1024"),
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
                    
                    if (data.type === "content" && data.chunk) {
                        if (!assistantMsgEl) {
                            loadingMsgEl.remove();
                            assistantMsgEl = UI.addMessage("assistant", "", modelName);
                        }
                        fullResponse += data.chunk;
                        assistantMsgEl.innerHTML = typeof marked !== 'undefined' ? marked.parse(fullResponse) : fullResponse;
                        UI.scrollToBottom();
                    } else if (data.type === "done") {
                        if (!assistantMsgEl) {
                            loadingMsgEl.remove();
                            assistantMsgEl = UI.addMessage("assistant", "", modelName);
                        }
                        fullResponse = data.response || fullResponse;
                        assistantMsgEl.innerHTML = typeof marked !== 'undefined' ? marked.parse(fullResponse) : fullResponse;
                        UI.scrollToBottom();
                    } else if (data.type === "error") {
                        throw new Error(data.error);
                    }
                } catch (e) {
                    if (e.message !== "error") console.error("SSE parse error", e);
                }
            }
        }
        
        refreshGraph();

    } catch (e) {
        if (loadingMsgEl?.parentNode) loadingMsgEl.remove();
        let errorText = `Error: ${e.message}`;
        if (e.name === 'AbortError') errorText = "⚠️ Request timed out.";
        UI.addMessage("system", errorText);
    } finally {
        clearInterval(loadingInterval);
        input.disabled = false;
        if (sendBtn) sendBtn.disabled = false;
        input?.focus();
    }
}

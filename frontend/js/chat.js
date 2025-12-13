
import * as API from './api.js';
import * as UI from './ui.js';
import { refreshGraph } from './main.js'; // Circular dependency? Better to pass callback or event.

export async function sendMessage(state) {
    const input = document.getElementById("message-input");
    const text = input.value.trim();
    if (!text || !state.sessionId) return;

    // UI Updates
    const userMsgEl = UI.addMessage("user", text);
    input.value = "";
    
    // Lock UI
    input.disabled = true;
    const sendBtn = document.getElementById("send-btn");
    if(sendBtn) sendBtn.disabled = true;

    // Get Settings
    const useAi = document.getElementById("ai-toggle").checked;
    const modelSelect = document.getElementById("model-select");
    const modelId = modelSelect.value;
    const modelName = modelSelect.selectedOptions[0]?.textContent || modelId;

    // Helper for local graph
    const isLocal = state.graphSource === "local";

    // Show Loading
    let loadingMsgEl = UI.createLoadingMessage(modelName);
    const startTime = Date.now();
    const loadingInterval = setInterval(() => {
        const elapsed = Math.floor((Date.now() - startTime) / 1000);
        UI.updateLoadingStatus(loadingMsgEl, `Waiting for response... (${elapsed}s)`, elapsed > 5 ? "var(--ctp-peach)" : null);
    }, 1000);

    const abortController = new AbortController();
    const timeoutId = setTimeout(() => abortController.abort(), 60000);

    try {
        const payload = {
            session_id: state.sessionId,
            message: text,
            use_memory: document.getElementById("memory-toggle").checked && !isLocal,
            use_retrieval: document.getElementById("retrieval-toggle").checked && !isLocal,
            use_ai: useAi,
            use_local_graphrag: isLocal,
            model_name: modelId,
            temperature: parseFloat(document.getElementById("temp-input").value),
            max_tokens: parseInt(document.getElementById("max-tokens-input").value),
        };

        const res = await API.fetchChatStream(payload, abortController.signal);
        clearTimeout(timeoutId);

        if (!res.ok) throw new Error(`HTTP error! status: ${res.status}`);

        // Stream Handling
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
                    
                    if (data.type === "context") {
                        UI.displayContextBlock(data.context_block);
                        if (data.context_block?.sections?.graph_facts) {
                            UI.displayRetrievedFacts(userMsgEl, data.context_block.sections.graph_facts);
                        }
                    } else if (data.type === "content" && data.chunk) {
                        if (!assistantMsgEl) {
                            loadingMsgEl.remove();
                            assistantMsgEl = UI.addMessage("assistant", "", modelName);
                        }
                        fullResponse += data.chunk;
                        // Use marked if available, else plain text
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
                    console.error("SSE Parse Error", e);
                }
            }
        }
        
        // Refresh graph at end of turn
        refreshGraph();

    } catch (e) {
        if (loadingMsgEl && loadingMsgEl.parentNode) loadingMsgEl.remove();
        let errorText = `Error: ${e.message}`;
        if (e.name === 'AbortError') errorText = "⚠️ Request timed out.";
        if (e.message.includes("429")) errorText = "⚠️ Rate limit exceeded.";
        UI.addMessage("system", errorText);
    } finally {
        clearInterval(loadingInterval);
        input.disabled = false;
        if(sendBtn) sendBtn.disabled = false;
        input.focus();
    }
}

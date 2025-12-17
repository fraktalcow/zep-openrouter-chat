/**
 * UI Helper Module
 * Handles all DOM manipulations for the chat interface.
 */

import { COLORS } from './config.js';

// Lazy DOM access - prevents null errors if module loads before DOM ready
const getChatBox = () => document.getElementById("chat-box");

/**
 * Add a message to the chat box.
 * @param {"user"|"assistant"|"system"} role - Message sender role
 * @param {string} text - Message content (supports markdown)
 * @param {string|null} modelName - Optional model name for assistant messages
 * @returns {HTMLElement|null} The created message element
 */
export function addMessage(role, text, modelName = null) {
    const chatBox = getChatBox();
    if (!chatBox) return null;
    
    const div = document.createElement("div");
    div.className = `message ${role}`;
    
    if (role === 'assistant' && modelName) {
        div.setAttribute('data-model', modelName);
    }
    
    if (typeof marked !== 'undefined') {
        div.innerHTML = marked.parse(text);
    } else {
        div.textContent = text;
    }
    
    chatBox.appendChild(div);
    scrollToBottom();
    return div;
}

/**
 * Scroll chat box to bottom.
 */
export function scrollToBottom() {
    const chatBox = getChatBox();
    if (chatBox) chatBox.scrollTop = chatBox.scrollHeight;
}

/**
 * Create a loading message with typing indicator.
 * @param {string} modelDisplayName - Model name to display
 * @returns {HTMLElement|null} The loading message element
 */
export function createLoadingMessage(modelDisplayName) {
    const chatBox = getChatBox();
    if (!chatBox) return null;
    
    const loadingMsgEl = document.createElement("div");
    loadingMsgEl.className = "message assistant loading";
    
    if (modelDisplayName) {
        loadingMsgEl.setAttribute("data-model", modelDisplayName);
    }
    
    loadingMsgEl.innerHTML = `
        <div class="typing-indicator"><span></span><span></span><span></span></div>
        <span class="loading-status" style="font-size: 0.75rem; color: ${COLORS.surface2}; margin-left: 10px;">Waiting for response...</span>
    `;
    chatBox.appendChild(loadingMsgEl);
    scrollToBottom();
    return loadingMsgEl;
}

/**
 * Update the status text in a loading message.
 * @param {HTMLElement} element - Loading message element
 * @param {string} statusText - New status text
 * @param {string|null} color - Optional color override
 */
export function updateLoadingStatus(element, statusText, color = null) {
    if (!element) return;
    const statusSpan = element.querySelector(".loading-status");
    if (statusSpan) {
        statusSpan.textContent = statusText;
        if (color) statusSpan.style.color = color;
    }
}

/**
 * Display context block in debug panel.
 * @param {{rendered: string}} data - Context data
 */
export function displayContextBlock(data) {
    const contextBlock = document.getElementById("context-block");
    if (contextBlock && data?.rendered) {
        contextBlock.textContent = data.rendered;
    }
}

/**
 * Display retrieved facts below a message.
 * @param {HTMLElement} parentMsgEl - Parent message element
 * @param {string[]} facts - Array of fact strings
 */
export function displayRetrievedFacts(parentMsgEl, facts) {
    if (!facts?.length || !parentMsgEl) return;

    const factsDiv = document.createElement("div");
    factsDiv.className = "retrieved-facts";
    
    const factsHeader = document.createElement("div");
    factsHeader.innerHTML = "<strong>Retrieved Context</strong>";
    factsDiv.appendChild(factsHeader);

    const factsList = document.createElement("ul");
    facts.forEach((fact) => {
        const li = document.createElement("li");
        li.textContent = fact;
        factsList.appendChild(li);
    });

    factsDiv.appendChild(factsList);
    parentMsgEl.appendChild(factsDiv);
    scrollToBottom();
}

/**
 * Set text content of an element by ID.
 */
export function setElementText(id, text) {
    const el = document.getElementById(id);
    if (el) el.textContent = text;
}

/**
 * Set color of an element by ID.
 */
export function setElementColor(id, color) {
    const el = document.getElementById(id);
    if (el) el.style.color = color;
}

/**
 * Render RAG sources as an expandable block.
 * @param {{text: string, score: number, metadata?: object}[]} sources - RAG chunks
 * @returns {HTMLElement|null} The sources element
 */
export function renderRagSources(sources) {
    const chatBox = getChatBox();
    if (!chatBox || !sources?.length) return null;
    
    const div = document.createElement("div");
    div.className = "rag-sources";
    div.style.cssText = "margin: 0.5rem 1rem;";
    
    const details = document.createElement("details");
    const summary = document.createElement("summary");
    summary.style.cssText = `cursor: pointer; color: ${COLORS.teal}; font-size: 0.8rem; font-family: var(--font-mono);`;
    summary.innerHTML = `<strong>RAG Context</strong> (${sources.length} chunks)`;
    details.appendChild(summary);

    const content = document.createElement("div");
    content.className = "rag-content";
    content.style.cssText = `font-size: 0.75rem; padding: 0.5rem; border-left: 2px solid ${COLORS.surface2}; margin-top: 0.3rem; color: ${COLORS.subtext0};`;
    
    sources.forEach((source, i) => {
        const item = document.createElement("div");
        item.style.marginBottom = "0.8rem";
        item.innerHTML = `
            <div style="font-weight:600; color: ${COLORS.blue}; margin-bottom: 2px;">Ref ${i+1} (Score: ${source.score.toFixed(3)})</div>
            <div style="white-space: pre-wrap; font-family: var(--font-mono);">${source.text}</div>
        `;
        content.appendChild(item);
    });
    
    details.appendChild(content);
    div.appendChild(details);
    
    chatBox.appendChild(div);
    scrollToBottom();
    return div;
}


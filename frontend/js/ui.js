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
    
    try {
        if (typeof marked !== 'undefined' && marked.parse && text) {
            div.innerHTML = marked.parse(text);
        } else {
            div.textContent = text || '';
        }
    } catch (e) {
        console.warn('Markdown parsing failed in addMessage:', e);
        div.textContent = text || '';
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
    loadingMsgEl.className = "message assistant loading-container";
    
    if (modelDisplayName) {
        loadingMsgEl.setAttribute("data-model", modelDisplayName);
    }
    
    loadingMsgEl.innerHTML = `
        <div class="loading-content">
            <div class="loading-visual">
                <div class="loading-orb"></div>
                <div class="loading-wave"></div>
            </div>
            <div class="loading-text">Generating...</div>
        </div>
    `;
    chatBox.appendChild(loadingMsgEl);
    scrollToBottom();
    return loadingMsgEl;
}

/**
 * Display context block in chat with minimal collapsible UI.
 * @param {{sections: {memory_section: string}}} data - Context data
 */
export function displayContextBlock(data) {
    const contextContent = data?.sections?.memory_section;
    if (!contextContent) return;

    const chatBox = getChatBox();
    if (!chatBox) return;

    // Parse the context to extract USER_SUMMARY and FACTS
    const summaryMatch = contextContent.match(/<USER_SUMMARY>([\s\S]*?)<\/USER_SUMMARY>/);
    const factsMatch = contextContent.match(/<FACTS>([\s\S]*?)<\/FACTS>/);
    
    const userSummary = summaryMatch ? summaryMatch[1].trim() : null;
    const factsRaw = factsMatch ? factsMatch[1].trim() : null;
    
    // Parse facts into individual items
    const facts = factsRaw ? factsRaw.split('\n').filter(f => f.trim().startsWith('-')).map(f => f.trim().substring(1).trim()) : [];

    // Create the context showcase container using details for auto-collapse
    const details = document.createElement("details");
    details.className = "zep-context-showcase";
    details.open = true; // Open by default, let user close it if too big
    
    details.innerHTML = `
        <summary class="context-main-summary">
            <div class="context-header-left">
                <i class="fa-solid fa-layer-group" style="font-size: 0.9rem;"></i>
                <span>Context Block</span>
            </div>
            <i class="fa-solid fa-chevron-down toggle-icon"></i>
        </summary>
        <div class="context-body">
            ${userSummary ? `
            <details class="inner-section" open>
                <summary class="inner-summary">
                    <i class="fa-solid fa-user-circle"></i>
                    <span>User Summary</span>
                    <i class="fa-solid fa-chevron-down toggle-icon" style="margin-left: auto;"></i>
                </summary>
                <div class="inner-content summary-content"></div>
            </details>
            ` : ''}
            ${facts.length > 0 ? `
            <details class="inner-section" open>
                <summary class="inner-summary">
                    <i class="fa-solid fa-lightbulb"></i>
                    <span>Known Facts</span>
                    <span class="context-badge" style="margin-left: 0.5rem; background: rgba(137, 180, 250, 0.2); color: var(--ctp-blue);">${facts.length}</span>
                    <i class="fa-solid fa-chevron-down toggle-icon" style="margin-left: auto;"></i>
                </summary>
                <div class="inner-content facts-content"></div>
            </details>
            ` : ''}
        </div>
    `;

    chatBox.appendChild(details);
    scrollToBottom();

    // Animate the content with typewriter effect
    if (userSummary) {
        const summaryEl = details.querySelector('.summary-content');
        if(summaryEl) streamText(summaryEl, userSummary, 8);
    }

    if (facts.length > 0) {
        const factsEl = details.querySelector('.facts-content');
        if(factsEl) {
            // Delay facts animation to start after summary
            setTimeout(() => {
                streamFacts(factsEl, facts);
            }, userSummary ? Math.min(userSummary.length * 8, 1500) : 0);
        }
    }
}

/**
 * Stream text with typewriter effect.
 * @param {HTMLElement} element - Target element
 * @param {string} text - Text to stream
 * @param {number} delay - Delay per character in ms
 */
function streamText(element, text, delay = 10) {
    let index = 0;
    element.textContent = '';
    element.classList.add('streaming');
    
    const interval = setInterval(() => {
        if (index < text.length) {
            element.textContent += text[index];
            index++;
            // Auto-scroll as content grows
            const chatBox = getChatBox();
            if (chatBox) chatBox.scrollTop = chatBox.scrollHeight;
        } else {
            clearInterval(interval);
            element.classList.remove('streaming');
            element.classList.add('complete');
        }
    }, delay);
}

/**
 * Stream facts with staggered animation.
 * @param {HTMLElement} container - Target container
 * @param {string[]} facts - Array of facts
 */
function streamFacts(container, facts) {
    container.innerHTML = '';
    
    facts.forEach((fact, index) => {
        setTimeout(() => {
            const factEl = document.createElement('div');
            factEl.className = 'fact-item';
            
            // Parse date range if present
            const dateMatch = fact.match(/\(([^)]+)\)$/);
            const factText = dateMatch ? fact.replace(dateMatch[0], '').trim() : fact;
            const dateRange = dateMatch ? dateMatch[1] : null;
            
            factEl.innerHTML = `
                <span class="fact-bullet">•</span>
                <span class="fact-text">${factText}</span>
                ${dateRange ? `<span class="fact-date">${dateRange}</span>` : ''}
            `;
            
            container.appendChild(factEl);
            
            // Trigger animation
            requestAnimationFrame(() => {
                factEl.classList.add('visible');
            });
            
            // Scroll to bottom
            const chatBox = getChatBox();
            if (chatBox) chatBox.scrollTop = chatBox.scrollHeight;
        }, index * 150); // Stagger each fact by 150ms
    });
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
 * Display usage metrics below an assistant message with minimal pill design.
 * @param {HTMLElement} messageEl - The assistant message element
 * @param {object} metrics - Metrics object with tokens, cost, duration
 */
export function displayUsageMetrics(messageEl, metrics) {
    if (!messageEl || !metrics) return;
    
    // Remove existing metrics if any
    const existing = messageEl.querySelector('.usage-metrics');
    if (existing) existing.remove();
    
    // Validate we have at least some meaningful data
    if (!metrics.total_tokens && !metrics.duration) return;

    const metricsDiv = document.createElement('div');
    metricsDiv.className = 'usage-metrics';
    
    const items = [];
    
    // Tokens - Minimal Badge
    if (metrics.total_tokens !== undefined) {
        const pTokens = metrics.prompt_tokens || 0;
        const cTokens = metrics.completion_tokens || 0;
        const tTokens = metrics.total_tokens;
        // Tooltip for details
        const title = `Total: ${tTokens}\nPrompt: ${pTokens}\nCompletion: ${cTokens}`;
        
        items.push(`
            <div class="metric-pill tokens" title="${title}">
                <span class="metric-icon">🔢</span>
                <span class="metric-value">${tTokens.toLocaleString()}</span>
                <span class="metric-sub">Tokens</span>
            </div>
        `);
    }
    
    // Cost
    if (metrics.cost !== undefined && metrics.cost > 0) {
        const costStr = metrics.cost < 0.01 ? metrics.cost.toFixed(6) : metrics.cost.toFixed(4);
        items.push(`
            <div class="metric-pill cost" title="Estimated Cost">
                <span class="metric-icon">💰</span>
                <span class="metric-value">$${costStr}</span>
            </div>
        `);
    }
    
    // Latency
    if (metrics.duration !== undefined) {
        items.push(`
            <div class="metric-pill latency" title="Generation Latency">
                <span class="metric-icon">⏱️</span>
                <span class="metric-value">${metrics.duration.toFixed(2)}s</span>
            </div>
        `);
    }
    
    if (items.length > 0) {
        metricsDiv.innerHTML = `
            <div class="metrics-container">
                ${items.join('')}
            </div>
        `;
        messageEl.appendChild(metricsDiv);
    }
}

/**
 * Show a toast notification for important messages (errors, status codes).
 * @param {string} message - Message to display
 * @param {"error"|"warning"|"info"} type - Toast type
 * @param {number} duration - Display duration in ms (0 = stays until dismissed)
 */
export function showToast(message, type = "error", duration = 5000) {
    // Remove existing toast if any
    const existing = document.getElementById("toast-notification");
    if (existing) existing.remove();
    
    const toast = document.createElement("div");
    toast.id = "toast-notification";
    
    const bgColor = type === "error" ? "#f38ba8" : type === "warning" ? "#fab387" : "#89b4fa";
    const textColor = "#1e1e2e";
    
    toast.style.cssText = `
        position: fixed;
        top: 20px;
        right: 20px;
        padding: 16px 24px;
        background: ${bgColor};
        color: ${textColor};
        border-radius: 8px;
        font-weight: 600;
        font-size: 14px;
        max-width: 400px;
        z-index: 10000;
        box-shadow: 0 4px 20px rgba(0,0,0,0.3);
        cursor: pointer;
        animation: slideIn 0.3s ease;
    `;
    
    toast.innerHTML = `
        <div style="display: flex; align-items: center; gap: 10px;">
            <span style="font-size: 18px;">${type === "error" ? "⚠️" : type === "warning" ? "⚡" : "ℹ️"}</span>
            <span>${message}</span>
            <span style="margin-left: auto; opacity: 0.7;">✕</span>
        </div>
    `;
    
    toast.onclick = () => toast.remove();
    document.body.appendChild(toast);
    
    // Add animation keyframes if not exists
    if (!document.getElementById("toast-styles")) {
        const style = document.createElement("style");
        style.id = "toast-styles";
        style.textContent = `
            @keyframes slideIn {
                from { transform: translateX(100%); opacity: 0; }
                to { transform: translateX(0); opacity: 1; }
            }
        `;
        document.head.appendChild(style);
    }
    
    if (duration > 0) {
        setTimeout(() => toast.remove(), duration);
    }
}


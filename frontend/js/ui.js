
// UI Helper Module

const chatBox = document.getElementById("chat-box");

export function addMessage(role, text, modelName = null) {
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

export function scrollToBottom() {
    chatBox.scrollTop = chatBox.scrollHeight;
}

export function createLoadingMessage(modelDisplayName) {
    const loadingMsgEl = document.createElement("div");
    loadingMsgEl.className = "message assistant loading";
    if (modelDisplayName) {
        loadingMsgEl.setAttribute("data-model", modelDisplayName);
    }
    
    loadingMsgEl.innerHTML = `
        <div class="typing-indicator"><span></span><span></span><span></span></div>
        <span class="loading-status" style="font-size: 0.75rem; color: var(--ctp-surface2); margin-left: 10px;">Waiting for response...</span>
    `;
    chatBox.appendChild(loadingMsgEl);
    scrollToBottom();
    return loadingMsgEl;
}

export function updateLoadingStatus(element, statusText, color) {
    if (!element) return;
    const statusSpan = element.querySelector(".loading-status");
    if (statusSpan) {
        statusSpan.textContent = statusText;
        if (color) statusSpan.style.color = color;
    }
}

export function displayContextBlock(data) {
    const contextBlock = document.getElementById("context-block");
    if (data && data.rendered) {
        contextBlock.textContent = data.rendered;
    }
}

export function displayRetrievedFacts(parentMsgEl, facts) {
    if (!facts || facts.length === 0) return;

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

export function setElementText(id, text) {
    const el = document.getElementById(id);
    if (el) el.textContent = text;
}

export function setElementColor(id, color) {
    const el = document.getElementById(id);
    if (el) el.style.color = color;
}

// --- STATE & CONFIG ---
let sessionId = null;
let userId = null;
let graphData = { nodes: [], edges: [] };

// Get JS computed styles for D3 to match CSS variables
const style = getComputedStyle(document.body);
const COLORS = {
  nodeFill: style.getPropertyValue("--ctp-lavender").trim() || "#bd93f9",
  nodeStroke: style.getPropertyValue("--ctp-base").trim() || "#282a36",
  text: style.getPropertyValue("--ctp-text").trim() || "#f8f8f2",
  link: style.getPropertyValue("--ctp-surface2").trim() || "#44475a",
  background: style.getPropertyValue("--ctp-base").trim() || "#282a36",
};

// Elements
const chatBox = document.getElementById("chat-box");
const messageInput = document.getElementById("message-input");
const contextBlock = document.getElementById("context-block");
const schemaModal = document.getElementById("schema-modal");
const schemaEditor = document.getElementById("schema-editor");

// Graph source: "zep" or "local"
let graphSource = "zep";



// --- INITIALIZATION ---
document.addEventListener("DOMContentLoaded", () => {
  // Run initialization tasks in parallel for faster startup
  Promise.all([
    initSession(),
    fetchSchema(),
    fetchModels(),
  ]).catch(err => {
    console.error("Initialization error:", err);
  });

  toggleZepSettings();
  checkLocalGraphRAGStatus();
});

function toggleZepSettings() {
  const isEnabled = document.getElementById("zep-toggle").checked;
  const settingsDiv = document.getElementById("zep-settings");
  const disabledMsg = document.getElementById("zep-disabled-msg");
  
  if (isEnabled) {
    settingsDiv.style.display = "block";
    disabledMsg.style.display = "none";
  } else {
    settingsDiv.style.display = "none";
    disabledMsg.style.display = "block";
  }
}

function updateGraphSource() {
  const zepRadio = document.getElementById("graph-source-zep");
  const localRadio = document.getElementById("graph-source-local");
  const localSettings = document.getElementById("local-graphrag-settings");
  
  if (localRadio.checked) {
    graphSource = "local";
    localSettings.style.display = "block";
    checkLocalGraphRAGStatus();
  } else {
    graphSource = "zep";
    localSettings.style.display = "none";
  }
  
  // Refresh graph immediately when source changes
  refreshGraph();
}

async function checkLocalGraphRAGStatus() {
  const statusDiv = document.getElementById("local-graphrag-status");
  try {
    const res = await fetch("/local-graphrag/status");
    const data = await res.json();
    
    if (data.available) {
      if (data.ingested) {
        statusDiv.textContent = `✓ Ready: ${data.entities} entities, ${data.relationships} relationships`;
        statusDiv.style.color = "var(--ctp-green)";
      } else {
        statusDiv.textContent = "⚠ No documents ingested. Add document paths and click 'Ingest Documents'";
        statusDiv.style.color = "var(--ctp-peach)";
      }
    } else {
      statusDiv.textContent = "✗ Local GraphRAG not available (missing dependencies)";
      statusDiv.style.color = "var(--ctp-red)";
    }
  } catch (e) {
    statusDiv.textContent = "✗ Error checking status";
    statusDiv.style.color = "var(--ctp-red)";
  }
}

async function ingestDocuments() {
  const pathsInput = document.getElementById("document-paths-input");
  const paths = pathsInput.value
    .split('\n')
    .map(p => p.trim())
    .filter(p => p.length > 0);
  
  if (paths.length === 0) {
    alert("Please enter at least one document path");
    return;
  }
  
  const statusDiv = document.getElementById("local-graphrag-status");
  statusDiv.textContent = "⏳ Ingesting documents...";
  statusDiv.style.color = "var(--ctp-blue)";
  
  try {
    const res = await fetch("/local-graphrag/ingest", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ document_paths: paths }),
    });
    
    const data = await res.json();
    
    if (data.status === "success") {
      statusDiv.textContent = `✓ ${data.message}: ${data.chunks} chunks, ${data.entities} entities, ${data.relationships} relationships`;
      statusDiv.style.color = "var(--ctp-green)";
      refreshGraph();
    } else {
      statusDiv.textContent = `✗ Error: ${data.message}`;
      statusDiv.style.color = "var(--ctp-red)";
    }
  } catch (e) {
    statusDiv.textContent = `✗ Error: ${e.message}`;
    statusDiv.style.color = "var(--ctp-red)";
  }
}

async function fetchModels() {
  const select = document.getElementById("model-select");
  try {
    const res = await fetch("/models/all");
    const data = await res.json();
    
    select.innerHTML = "";
    
    const freeGroup = document.createElement("optgroup");
    freeGroup.label = "Free Models";
    const paidGroup = document.createElement("optgroup");
    paidGroup.label = "All Models";

    data.models.sort((a, b) => a.name.localeCompare(b.name));

    data.models.forEach(model => {
      const option = document.createElement("option");
      option.value = model.id;
      const isFree = model.pricing.prompt === "0";
      // Clean model name - remove any existing (free) / (FREE) suffixes
      let cleanName = model.name.replace(/\s*\(free\)\s*/gi, '').trim();
      option.textContent = cleanName;
      
      if (isFree) {
        freeGroup.appendChild(option);
      } else {
        paidGroup.appendChild(option);
      }
    });

    select.appendChild(freeGroup);
    select.appendChild(paidGroup);
    
    select.value = "google/gemini-2.0-flash-exp:free";
  } catch (e) {
    console.error("Failed to fetch models", e);
    select.innerHTML = "<option value='meta-llama/llama-3.2-3b-instruct:free'>Fallback: Llama 3.2 3B</option>";
  }
}

// --- SCHEMA LOGIC ---
async function fetchSchema() {
  try {
    const res = await fetch("/schema");
    const data = await res.json();
    schemaEditor.value = JSON.stringify(data, null, 2);
  } catch (e) {
    console.error("Failed to fetch schema", e);
  }
}

function openSchemaModal() {
  schemaModal.classList.add("active");
}

function closeSchemaModal() {
  schemaModal.classList.remove("active");
}

async function saveSchema() {
  try {
    const schema = JSON.parse(schemaEditor.value);
    const res = await fetch("/schema", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(schema),
    });
    const result = await res.json();
    if (result.status === "success") {
      closeSchemaModal();
      alert("Schema Updated Successfully");
    }
  } catch (e) {
    alert("Error: Invalid JSON");
    console.error(e);
  }
}

// --- SESSION LOGIC ---
async function initSession(forceNew = false) {
  if (!forceNew && sessionId) return;

  const payload = {
    first_name: document.getElementById("first-name").value,
    last_name: document.getElementById("last-name").value,
    traits: document.getElementById("traits-input").value,
    preferences: document.getElementById("preferences-input").value,
    business_data: document.getElementById("business-data-input").value,
  };

  try {
    const res = await fetch("/session", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await res.json();
    sessionId = data.session_id;
    userId = data.user_id;

    document.getElementById("session-badge").textContent = `ID: ${
      sessionId.split("_")[1] || sessionId
    }`;
    chatBox.innerHTML = "";
    graphData = { nodes: [], edges: [] };
    renderGraph();

    addMessage("system", "Session initialized.");
  } catch (e) {
    console.error("Session init failed", e);
  }
}

// --- CHAT LOGIC ---
async function sendMessage() {
  const text = messageInput.value.trim();
  if (!text || !sessionId) return;

  const userMsgEl = addMessage("user", text);
  messageInput.value = "";

  const useAi = document.getElementById("ai-toggle").checked;
  const useZep = document.getElementById("zep-toggle").checked;
  const useMemory = document.getElementById("memory-toggle").checked;
  const useRetrieval = document.getElementById("retrieval-toggle").checked;
  const useLocalGraphRAG = graphSource === "local";
  const modelName = document.getElementById("model-select").value;

  // Disable input while processing
  messageInput.disabled = true;
  const sendButton = document.getElementById("send-btn");
  if (sendButton) sendButton.disabled = true;

  // Get display name for the model
  const selectEl = document.getElementById("model-select");
  const modelDisplayName = selectEl.options[selectEl.selectedIndex] ? selectEl.options[selectEl.selectedIndex].text : "AI";

  let loadingMsgEl = null;

  try {
    // Show Loading Animation
    // Show Loading Animation
    loadingMsgEl = document.createElement("div");
    loadingMsgEl.className = "message assistant loading";
    loadingMsgEl.setAttribute("data-model", modelDisplayName);
    loadingMsgEl.innerHTML = '<div class="typing-indicator"><span></span><span></span><span></span></div>';
    chatBox.appendChild(loadingMsgEl);
    chatBox.scrollTop = chatBox.scrollHeight;

    let fullResponse = "";
    let contextBlockData = null;
    let res;

    res = await fetch("/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: sessionId,
          message: text,
          use_memory: useMemory && useZep && !useLocalGraphRAG,
          use_retrieval: useRetrieval && useZep && !useLocalGraphRAG,
          use_ai: useAi,
          use_local_graphrag: useLocalGraphRAG,
          model_name: modelName,
          temperature: parseFloat(document.getElementById("temp-input").value),
          max_tokens: parseInt(document.getElementById("max-tokens-input").value),
        }),
      });

    let assistantMsgEl = null;

    if (!res.ok) {
      throw new Error(`HTTP error! status: ${res.status}`);
    }

    // Handle streaming response
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      
      // Process complete SSE messages (lines ending with \n\n)
      const lines = buffer.split("\n\n");
      buffer = lines.pop() || ""; // Keep incomplete line in buffer

      for (const line of lines) {
        if (!line.trim()) continue;
        
        // Parse SSE format: "data: {...}"
        if (line.startsWith("data: ")) {
          const dataStr = line.slice(6); // Remove "data: " prefix
          try {
            const data = JSON.parse(dataStr);
            
            if (data.type === "context") {
              contextBlockData = data.context_block;
              
              // Show retrieved facts if available
              if (
                contextBlockData &&
                contextBlockData.sections &&
                contextBlockData.sections.graph_facts &&
                contextBlockData.sections.graph_facts.length > 0
              ) {
                const factsDiv = document.createElement("div");
                factsDiv.className = "retrieved-facts";
                
                const factsHeader = document.createElement("div");
                factsHeader.innerHTML = "<strong>Retrieved Context</strong>";
                factsDiv.appendChild(factsHeader);

                const factsList = document.createElement("ul");
                contextBlockData.sections.graph_facts.forEach((fact) => {
                  const li = document.createElement("li");
                  li.textContent = fact;
                  factsList.appendChild(li);
                });

                factsDiv.appendChild(factsList);
                userMsgEl.appendChild(factsDiv);
                chatBox.scrollTop = chatBox.scrollHeight;
              }

              // Update context block display
              if (contextBlockData && contextBlockData.rendered) {
                contextBlock.textContent = contextBlockData.rendered;
              }
            } else if (data.type === "content" && data.chunk) {
              if (!assistantMsgEl) {
                if (loadingMsgEl && loadingMsgEl.parentNode) loadingMsgEl.remove();
                assistantMsgEl = addMessage("assistant", "", modelDisplayName);
              }

              // Append chunk to response
              fullResponse += data.chunk;
              // Update message element with full response so far
              if (typeof marked !== 'undefined') {
                assistantMsgEl.innerHTML = marked.parse(fullResponse);
              } else {
                assistantMsgEl.textContent = fullResponse;
              }
              chatBox.scrollTop = chatBox.scrollHeight;
            } else if (data.type === "done") {
              if (!assistantMsgEl) {
                 if (loadingMsgEl && loadingMsgEl.parentNode) loadingMsgEl.remove();
                 assistantMsgEl = addMessage("assistant", "", modelDisplayName);
              }
              // Finalize response
              fullResponse = data.response || fullResponse;
              if (typeof marked !== 'undefined') {
                assistantMsgEl.innerHTML = marked.parse(fullResponse);
              } else {
                assistantMsgEl.textContent = fullResponse;
              }
              chatBox.scrollTop = chatBox.scrollHeight;
            } else if (data.type === "error") {
              throw new Error(data.error || "Unknown error");
            }
          } catch (e) {
            console.error("Error parsing SSE data:", e, "Data:", dataStr);
          }
        }
      }
    }

    // Process any remaining buffer
    if (buffer.trim()) {
      const lines = buffer.split("\n\n");
      for (const line of lines) {
        if (line.trim() && line.startsWith("data: ")) {
          const dataStr = line.slice(6);
          try {
            const data = JSON.parse(dataStr);
            if (data.type === "content" && data.chunk) {
              if (!assistantMsgEl) {
                if (loadingMsgEl && loadingMsgEl.parentNode) loadingMsgEl.remove();
                assistantMsgEl = addMessage("assistant", "", modelDisplayName);
              }

              fullResponse += data.chunk;
              if (typeof marked !== 'undefined') {
                assistantMsgEl.innerHTML = marked.parse(fullResponse);
              } else {
                assistantMsgEl.textContent = fullResponse;
              }
            } else if (data.type === "done") {
              if (!assistantMsgEl) {
                 if (loadingMsgEl && loadingMsgEl.parentNode) loadingMsgEl.remove();
                 assistantMsgEl = addMessage("assistant", "", modelDisplayName);
              }

              fullResponse = data.response || fullResponse;
              if (typeof marked !== 'undefined') {
                assistantMsgEl.innerHTML = marked.parse(fullResponse);
              } else {
                assistantMsgEl.textContent = fullResponse;
              }
            }
          } catch (e) {
            console.error("Error parsing final SSE data:", e);
          }
        }
      }
    }

    // Always refresh graph after message (works for both Zep and local)
    refreshGraph();

  } catch (e) {
    if (loadingMsgEl && loadingMsgEl.parentNode) loadingMsgEl.remove();

    if (e.message.includes("Rate limit")) {
      addMessage("system", "⚠️ Rate limit exceeded. Please wait a moment or switch to a free model.");
    } else {
      addMessage("system", "Error: Connection failed. " + e.message);
    }
    console.error(e);
  } finally {
    // Re-enable input
    messageInput.disabled = false;
    if (sendButton) sendButton.disabled = false;
    messageInput.focus();
  }
}

function addMessage(role, text, modelName = null) {
  const div = document.createElement("div");
  div.className = `message ${role}`;
  if (role === "assistant" && modelName) {
    div.setAttribute("data-model", modelName);
  }
  
  if (typeof marked !== 'undefined') {
    div.innerHTML = marked.parse(text);
  } else {
    const textSpan = document.createElement("span");
    textSpan.textContent = text;
    div.appendChild(textSpan);
  }
  
  chatBox.appendChild(div);
  chatBox.scrollTop = chatBox.scrollHeight;
  return div;
}

messageInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") sendMessage();
});

// --- GRAPH VISUALIZATION (Vis-Network) ---
let network = null;
let lastGraphHash = "";

function hashGraphData(data) {
  const nodeIds = (data.nodes || []).map(n => n.uuid).sort().join(",");
  const edgeIds = (data.edges || []).map(e => `${e.source}-${e.target}`).sort().join(",");
  return `${nodeIds}|${edgeIds}`;
}

async function refreshGraph() {
  try {
    let url;
    if (graphSource === "local") {
      url = `/local-graphrag/graph`;
    } else {
      if (!userId) return;
      url = `/graph/${userId}`;
    }
    
    const res = await fetch(url);
    const data = await res.json();
    
    // Only update if data actually changed
    const newHash = hashGraphData(data);
    if (newHash === lastGraphHash) return;
    lastGraphHash = newHash;
    
    graphData = data;
    renderGraph();

    document.getElementById("node-count").textContent = data.nodes?.length || 0;
    document.getElementById("edge-count").textContent = data.edges?.length || 0;
  } catch (e) {
    console.error("Graph refresh failed", e);
  }
}

function renderGraph() {
  const container = document.getElementById("graph-container");
  
  if (!graphData.nodes.length) {
    if(network) {
      network.destroy();
      network = null;
    }
    return;
  }

  const nodes = new vis.DataSet(
    graphData.nodes.map(n => ({
      id: n.uuid,
      label: n.name || n.uuid.substring(0, 8),
      title: n.summary || n.name,
      color: {
        background: COLORS.nodeFill,
        border: COLORS.nodeStroke,
        highlight: { background: COLORS.text, border: COLORS.nodeStroke }
      },
      font: { color: COLORS.text, face: 'JetBrains Mono' },
      shape: 'dot',
      size: 10
    }))
  );

  const edges = new vis.DataSet(
    graphData.edges.map(e => ({
      from: e.source,
      to: e.target,
      color: { color: COLORS.link, highlight: COLORS.text },
      width: 1,
      arrows: 'to'
    }))
  );

  const data = { nodes, edges };
  const options = {
    nodes: {
      borderWidth: 2,
      shadow: true
    },
    edges: {
      shadow: true,
      smooth: {
        type: "continuous"
      }
    },
    physics: {
      stabilization: {
        enabled: true,
        iterations: 100,
        updateInterval: 25
      },
      barnesHut: {
        gravitationalConstant: -2000,
        springConstant: 0.04,
        springLength: 95,
        damping: 0.5
      }
    },
    interaction: {
      hover: true,
      tooltipDelay: 200,
      zoomView: true
    }
  };

  if (network) {
    network.setData(data);
  } else {
    network = new vis.Network(container, data, options);
  }
}

function resetZoom() {
  if (network) {
    network.fit({ 
      animation: {
        duration: 1000,
        easingFunction: "easeInOutQuad"
      }
    });
  }
}

window.addEventListener("resize", () => {
  if (network) network.fit();
});


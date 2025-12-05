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

// Tool palette state
let availableTools = [];
let showToolPalette = false;
let toolPaletteFilter = "";

// --- INITIALIZATION ---
document.addEventListener("DOMContentLoaded", () => {
  initSession();
  fetchSchema();
  fetchModels();
  fetchTools();
  toggleZepSettings();
  checkLocalGraphRAGStatus();
  // Auto-refresh graph every 5 seconds
  setInterval(refreshGraph, 5000);
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
      option.textContent = model.name;
      
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

        try {
          const res = await fetch("/chat", {
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

          const data = await res.json();

          // Handle tool results
          if (data.is_tool) {
            addMessage("assistant", data.response, true);
            hideToolPalette();
            refreshGraph();
            return;
          }

          if (
            data.context_block &&
            data.context_block.sections &&
            data.context_block.sections.graph_facts &&
            data.context_block.sections.graph_facts.length > 0
          ) {
            const factsDiv = document.createElement("div");
            factsDiv.className = "retrieved-facts";
            
            const factsHeader = document.createElement("div");
            factsHeader.innerHTML = "<strong>Retrieved Context</strong>";
            factsDiv.appendChild(factsHeader);

            const factsList = document.createElement("ul");
            data.context_block.sections.graph_facts.forEach((fact) => {
              const li = document.createElement("li");
              li.textContent = fact;
              factsList.appendChild(li);
            });

            factsDiv.appendChild(factsList);
            userMsgEl.appendChild(factsDiv);
            chatBox.scrollTop = chatBox.scrollHeight;
          }

          addMessage("assistant", data.response);

          if (data.context_block && data.context_block.rendered) {
            contextBlock.textContent = data.context_block.rendered;
          }

          // Always refresh graph after message (works for both Zep and local)
          refreshGraph();
          
          // If local GraphRAG returned graph data, use it
          if (data.graph_data) {
            graphData = data.graph_data;
            renderGraph();
            document.getElementById("node-count").textContent = data.graph_data.nodes?.length || 0;
            document.getElementById("edge-count").textContent = data.graph_data.edges?.length || 0;
          }
  } catch (e) {
    if (e.message.includes("Rate limit")) {
       addMessage("system", "⚠️ Rate limit exceeded. Please wait a moment or switch to a free model.");
    } else {
       addMessage("system", "Error: Connection failed. " + e.message);
    }
    console.error(e);
  }
}

function addMessage(role, text) {
  const div = document.createElement("div");
  div.className = `message ${role}`;
  
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

async function fetchTools() {
  try {
    const res = await fetch("/tools/list");
    const data = await res.json();
    availableTools = data.tools || [];
  } catch (e) {
    console.error("Failed to fetch tools", e);
  }
}

messageInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !showToolPalette) {
    sendMessage();
  } else if (e.key === "Escape") {
    hideToolPalette();
  } else if (e.key === "ArrowDown" && showToolPalette) {
    e.preventDefault();
    const firstTool = document.querySelector(".tool-item");
    if (firstTool) firstTool.focus();
  }
});

messageInput.addEventListener("input", (e) => {
  const value = e.target.value;
  if (value === "/") {
    showToolPaletteUI();
  } else if (value.startsWith("/") && showToolPalette) {
    toolPaletteFilter = value.slice(1).toLowerCase();
    updateToolPalette();
  } else if (!value.startsWith("/")) {
    hideToolPalette();
  }
});

function showToolPaletteUI() {
  showToolPalette = true;
  updateToolPalette();
  const palette = document.getElementById("tool-palette");
  if (palette) palette.style.display = "block";
}

function hideToolPalette() {
  showToolPalette = false;
  toolPaletteFilter = "";
  const palette = document.getElementById("tool-palette");
  if (palette) palette.style.display = "none";
}

function updateToolPalette() {
  const palette = document.getElementById("tool-palette");
  if (!palette) return;
  
  const filtered = availableTools.filter(tool => 
    tool.name.toLowerCase().includes(toolPaletteFilter) ||
    tool.description.toLowerCase().includes(toolPaletteFilter)
  );
  
  palette.innerHTML = "";
  
  if (filtered.length === 0) {
    palette.innerHTML = '<div class="tool-item-empty">No tools found</div>';
    return;
  }
  
  filtered.forEach(tool => {
    const item = document.createElement("div");
    item.className = "tool-item";
    item.tabIndex = 0;
    item.innerHTML = `
      <div class="tool-name">/${tool.name}</div>
      <div class="tool-description">${tool.description}</div>
    `;
    item.addEventListener("click", () => selectTool(tool));
    item.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        selectTool(tool);
      }
    });
    palette.appendChild(item);
  });
}

function selectTool(tool) {
  messageInput.value = `/${tool.name} `;
  hideToolPalette();
  messageInput.focus();
}

// --- GRAPH VISUALIZATION (Vis-Network) ---
let network = null;

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
      stabilization: false,
      barnesHut: {
        gravitationalConstant: -2000,
        springConstant: 0.04,
        springLength: 95
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

window.addEventListener("resize", () => {
  if (graphData.nodes.length > 0) renderGraph();
});


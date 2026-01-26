
// Graph Visualization Module
// Requires vis-network to be loaded globally

const COLORS = {
  bg: getComputedStyle(document.body).getPropertyValue("--ctp-base").trim() || "#1e1e2e",
  nodeFill: getComputedStyle(document.body).getPropertyValue("--ctp-blue").trim() || "#89b4fa",
  nodeStroke: getComputedStyle(document.body).getPropertyValue("--ctp-mantle").trim() || "#181825",
  text: getComputedStyle(document.body).getPropertyValue("--ctp-text").trim() || "#cdd6f4",
  link: getComputedStyle(document.body).getPropertyValue("--ctp-surface2").trim() || "#585b70",
  highlight: getComputedStyle(document.body).getPropertyValue("--ctp-yellow").trim() || "#f9e2af"
};

let network = null;
let lastGraphHash = "";

function hashGraphData(data) {
  const nodeIds = (data.nodes || []).map(n => n.uuid).sort().join(",");
  const edgeIds = (data.edges || []).map(e => `${e.source}-${e.target}`).sort().join(",");
  return `${nodeIds}|${edgeIds}`;
}

export function renderGraph(container, graphData) {
  const emptyMessage = document.getElementById("graph-empty-message");
  
  if (!graphData || !graphData.nodes || !graphData.nodes.length) {
    if (network) {
      network.destroy();
      network = null;
    }
    if (emptyMessage) emptyMessage.style.display = "block";
    return;
  }

  if (emptyMessage) emptyMessage.style.display = "none";

  // Check if update is needed to avoid jumpy re-renders
  const newHash = hashGraphData(graphData);
  if (network && newHash === lastGraphHash) return;
  lastGraphHash = newHash;

  const nodes = new vis.DataSet(
    graphData.nodes.map(n => ({
      id: n.uuid,
      label: n.name.length > 20 ? n.name.substring(0, 18) + '...' : n.name,
      title: `${n.name}\n${n.summary || 'No details'}`,
      val: 20, // base size
      color: {
        background: COLORS.nodeFill,
        border: COLORS.nodeStroke,
        highlight: { background: COLORS.highlight, border: COLORS.nodeStroke }
      },
      font: { color: COLORS.text, face: 'Inter, sans-serif', size: 14, strokeWidth: 3, strokeColor: COLORS.bg },
      shape: 'dot',
      shadow: true
    }))
  );

  const edges = new vis.DataSet(
    graphData.edges.map(e => ({
      from: e.source,
      to: e.target,
      title: e.fact || 'Related',
      color: { color: COLORS.link, highlight: COLORS.highlight },
      width: 1.5,
      arrows: { to: { enabled: true, scaleFactor: 0.5 } },
      smooth: { type: 'continuous' }
    }))
  );

  const data = { nodes, edges };
  const options = {
    nodes: {
      borderWidth: 2,
      shadow: true,
      scaling: { label: { enabled: true } }
    },
    edges: {
      shadow: false,
      smooth: { type: "continuous", forceDirection: "none" }
    },
    physics: {
      stabilization: { enabled: true, iterations: 150 },
      barnesHut: {
        gravitationalConstant: -3000,
        springConstant: 0.02,
        springLength: 150,
        damping: 0.3
      },
      minVelocity: 0.75
    },
    interaction: {
      hover: true,
      tooltipDelay: 300,
      zoomView: true,
      hideEdgesOnDrag: true
    },
    layout: {
      randomSeed: 2 // Consistent layout
    }
  };

  if (network) {
    network.setData(data);
  } else {
    network = new vis.Network(container, data, options);
    
    // Wire up events
    network.on("click", function (params) {
      if (params.nodes.length > 0) {
        const nodeId = params.nodes[0];
        const node = graphData.nodes.find(n => n.uuid === nodeId);
        if (node) {
          document.dispatchEvent(new CustomEvent('graph-node-selected', { detail: node }));
        }
      }
    });
  }
}

export function resetZoom() {
  if (network) {
    network.fit({ 
      animation: { duration: 800, easingFunction: "easeInOutQuad" }
    });
  }
}

export function resizeGraph() {
    if (network) network.fit();
}

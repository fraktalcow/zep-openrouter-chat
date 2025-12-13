
// Graph Visualization Module
// Requires vis-network to be loaded globally or imported if using a bundler.
// Assuming global 'vis' object is available from the CDN script.

const computedStyle = getComputedStyle(document.body);
const COLORS = {
  nodeFill: computedStyle.getPropertyValue("--ctp-lavender").trim() || "#bd93f9",
  nodeStroke: computedStyle.getPropertyValue("--ctp-base").trim() || "#282a36",
  text: computedStyle.getPropertyValue("--ctp-text").trim() || "#f8f8f2",
  link: computedStyle.getPropertyValue("--ctp-surface2").trim() || "#44475a",
};

let network = null;
let lastGraphHash = "";

function hashGraphData(data) {
  const nodeIds = (data.nodes || []).map(n => n.uuid).sort().join(",");
  const edgeIds = (data.edges || []).map(e => `${e.source}-${e.target}`).sort().join(",");
  return `${nodeIds}|${edgeIds}`;
}

export function renderGraph(container, graphData) {
  if (!graphData || !graphData.nodes || !graphData.nodes.length) {
    if (network) {
      network.destroy();
      network = null;
    }
    return;
  }

  // Check if update is needed
  const newHash = hashGraphData(graphData);
  if (network && newHash === lastGraphHash) return;
  lastGraphHash = newHash;

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
    nodes: { borderWidth: 2, shadow: true },
    edges: { shadow: true, smooth: { type: "continuous" } },
    physics: {
      stabilization: { enabled: true, iterations: 100, updateInterval: 25 },
      barnesHut: { gravitationalConstant: -2000, springConstant: 0.04, springLength: 95, damping: 0.5 }
    },
    interaction: { hover: true, tooltipDelay: 200, zoomView: true }
  };

  if (network) {
    network.setData(data);
  } else {
    network = new vis.Network(container, data, options);
  }
}

export function resetZoom() {
  if (network) {
    network.fit({ 
      animation: { duration: 1000, easingFunction: "easeInOutQuad" }
    });
  }
}

export function resizeGraph() {
    if (network) network.fit();
}

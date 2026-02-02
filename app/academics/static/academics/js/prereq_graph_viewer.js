// Render prerequisite graph using a force layout (default), with d3-dag standby.
(function () {
  "use strict";

  const graphEl = document.getElementById("graph");
  const errorBox = document.getElementById("graph-error");
  const toggleButton = document.getElementById("layout-toggle");
  const layoutStorageKey = "prereq-graph-layout";

  const showError = (message) => {
    if (!errorBox) {
      return;
    }
    errorBox.textContent = message;
    errorBox.style.display = "block";
  };

  let cachedPayload = null;
  let currentLayout = localStorage.getItem(layoutStorageKey) || "force";

  const updateToggleLabel = () => {
    if (!toggleButton) {
      return;
    }
    toggleButton.textContent =
      currentLayout === "dag"
        ? "Switch to force layout"
        : "Switch to DAG layout";
  };

  if (!graphEl) {
    return;
  }

  const jsonUrl = graphEl.dataset.jsonUrl || "";
  if (!jsonUrl) {
    showError("Graph data URL not provided.");
    return;
  }

  if (!window.d3) {
    showError("Graph library failed to load. Check that d3 is available.");
    return;
  }

  const drawNodeShape = (group, node) => {
    const shape = node.shape || "box";
    const color = node.color || "#6c757d";
    const isInCurriculum = node.is_in_curriculum !== false;
    const dashStyle = isInCurriculum ? null : "6,4";

    const strokeAttrs = (selection) => {
      selection.attr("stroke", color);
      if (dashStyle) {
        selection.attr("stroke-dasharray", dashStyle);
      }
    };

    if (shape === "ellipse") {
      strokeAttrs(group.append("ellipse").attr("rx", 55).attr("ry", 22));
      return;
    }

    if (shape === "egg") {
      const eggPath =
        "M0,-24 C26,-24 42,-10 42,6 C42,22 22,32 0,32 C-22,32 -42,22 -42,6 C-42,-10 -26,-24 0,-24 Z";
      strokeAttrs(group.append("path").attr("d", eggPath));
      return;
    }

    if (shape === "triangle") {
      const points = "-55,24 55,24 0,-32";
      strokeAttrs(group.append("polygon").attr("points", points));
      return;
    }

    if (shape === "diamond") {
      const points = "0,-32 55,0 0,32 -55,0";
      strokeAttrs(group.append("polygon").attr("points", points));
      return;
    }

    if (shape === "house") {
      const points = "-55,24 55,24 55,-6 0,-36 -55,-6";
      strokeAttrs(group.append("polygon").attr("points", points));
      return;
    }

    strokeAttrs(
      group
        .append("rect")
        .attr("x", -55)
        .attr("y", -22)
        .attr("width", 110)
        .attr("height", 44)
        .attr("rx", 6)
    );
  };

  const renderForce = (payload) => {
    const nodes = Array.isArray(payload.nodes)
      ? payload.nodes.map((node) => ({ ...node }))
      : [];
    const links = Array.isArray(payload.links)
      ? payload.links.map((link) => ({ ...link }))
      : [];

    if (!nodes.length) {
      showError("No nodes available to render.");
      return;
    }

    const rect = graphEl.getBoundingClientRect();
    const width = Math.max(rect.width || 0, 900);
    const height = Math.max(rect.height || 0, 600);
    const marginX = 40;
    const marginY = 40;
    const innerWidth = width - marginX * 2;
    const innerHeight = height - marginY * 2;

    const numericLevels = [];
    let hasUnknown = false;

    nodes.forEach((node) => {
      if (Number.isInteger(node.level_number)) {
        numericLevels.push(node.level_number);
      } else {
        hasUnknown = true;
      }
    });

    const uniqueLevels = Array.from(new Set(numericLevels)).sort((a, b) => a - b);
    const levelKeys = uniqueLevels.slice();
    if (hasUnknown) {
      levelKeys.push("NA");
    }

    const levelIndex = new Map();
    levelKeys.forEach((key, index) => {
      levelIndex.set(key, index);
    });

    const levelPositions = new Map();
    const levelCount = Math.max(levelKeys.length, 1);
    const levelSpacing = levelCount > 1 ? innerWidth / (levelCount - 1) : 0;

    levelKeys.forEach((key, index) => {
      const x =
        levelCount > 1
          ? marginX + index * levelSpacing
          : marginX + innerWidth / 2;
      levelPositions.set(key, x);
    });

    const levelGroups = new Map();
    nodes.forEach((node) => {
      const key = Number.isInteger(node.level_number) ? node.level_number : "NA";
      node._levelKey = key;
      if (!levelGroups.has(key)) {
        levelGroups.set(key, []);
      }
      levelGroups.get(key).push(node);
    });

    levelGroups.forEach((groupNodes) => {
      groupNodes.sort((a, b) => String(a.label).localeCompare(String(b.label)));
      const groupCount = groupNodes.length;
      groupNodes.forEach((node, index) => {
        const offset = (index + 1) / (groupCount + 1);
        node._targetY = marginY + offset * innerHeight;
      });
    });

    const svg = window.d3.select(graphEl);
    svg.selectAll("*").remove();
    svg.attr("viewBox", [0, 0, width, height].join(" "));

    const defs = svg.append("defs");
    defs
      .append("marker")
      .attr("id", "arrowhead")
      .attr("viewBox", "0 -5 10 10")
      .attr("refX", 14)
      .attr("refY", 0)
      .attr("markerWidth", 6)
      .attr("markerHeight", 6)
      .attr("orient", "auto")
      .append("path")
      .attr("d", "M0,-5L10,0L0,5")
      .attr("fill", "#adb5bd");

    const zoomLayer = svg.append("g").attr("transform", `translate(${marginX},${marginY})`);

    svg.call(
      window.d3
        .zoom()
        .scaleExtent([0.2, 3])
        .on("zoom", (event) => zoomLayer.attr("transform", event.transform))
    );

    const bandWidth = Math.min(200, innerWidth / levelCount);
    const bandGroup = zoomLayer.append("g").attr("class", "level-bands");

    bandGroup
      .selectAll("g")
      .data(levelKeys)
      .join("g")
      .each(function (key, index) {
        const group = window.d3.select(this);
        const x = levelPositions.get(key);
        const label = key === "NA" ? "S-NA" : `S-${key}`;
        const fill = index % 2 === 0 ? "#ffffff" : "#f1f3f5";
        group
          .append("rect")
          .attr("x", x - bandWidth / 2)
          .attr("y", 0)
          .attr("width", bandWidth)
          .attr("height", innerHeight)
          .attr("fill", fill)
          .attr("stroke", "#e9ecef")
          .attr("stroke-dasharray", "4,4");
        group
          .append("text")
          .attr("x", x)
          .attr("y", 14)
          .attr("text-anchor", "middle")
          .attr("fill", "#6c757d")
          .attr("font-size", 12)
          .text(label);
      });

    const linkGroup = zoomLayer.append("g").attr("class", "links");
    const nodeGroup = zoomLayer.append("g").attr("class", "nodes");

    const linkSelection = linkGroup
      .selectAll("path")
      .data(links)
      .join("path")
      .attr("class", "link")
      .attr("marker-end", "url(#arrowhead)");

    const nodeSelection = nodeGroup
      .selectAll("g")
      .data(nodes)
      .join("g")
      .attr("class", "node");

    nodeSelection.each(function (node) {
      drawNodeShape(window.d3.select(this), node);
    });

    nodeSelection
      .append("title")
      .text((node) => node.title || node.label || "");

    nodeSelection
      .append("text")
      .attr("text-anchor", "middle")
      .attr("dy", "0.35em")
      .text((node) => node.label);

    const linkPath = (link) => {
      if (!link.source || !link.target) {
        return "";
      }
      const sx = link.source.x || 0;
      const sy = link.source.y || 0;
      const tx = link.target.x || 0;
      const ty = link.target.y || 0;
      const dx = tx - sx;
      const dy = ty - sy;
      const len = Math.hypot(dx, dy) || 1;
      const offset = 26;
      const startX = sx + (dx / len) * offset;
      const startY = sy + (dy / len) * offset;
      const endX = tx - (dx / len) * offset;
      const endY = ty - (dy / len) * offset;
      return `M${startX},${startY} L${endX},${endY}`;
    };

    const simulation = window.d3
      .forceSimulation(nodes)
      .force(
        "link",
        window.d3
          .forceLink(links)
          .id((node) => node.id)
          .distance(140)
          .strength(0.7)
      )
      .force("charge", window.d3.forceManyBody().strength(-280))
      .force(
        "x",
        window.d3
          .forceX((node) => levelPositions.get(node._levelKey))
          .strength(0.8)
      )
      .force(
        "y",
        window.d3
          .forceY((node) => node._targetY || innerHeight / 2)
          .strength(0.6)
      )
      .force("collide", window.d3.forceCollide().radius(40))
      .force("center", window.d3.forceCenter(innerWidth / 2, innerHeight / 2));

    simulation.on("tick", () => {
      linkSelection.attr("d", linkPath);

      nodeSelection.attr(
        "transform",
        (node) => `translate(${node.x},${node.y})`
      );
    });
  };

  // Standby DAG renderer (kept for reference).
  const renderDag = (payload) => {
    if (!window.d3 || typeof window.d3.dagStratify !== "function") {
      showError(
        "Graph library failed to load. Check that d3 and d3-dag are available."
      );
      return;
    }

    const nodes = Array.isArray(payload.nodes) ? payload.nodes : [];
    const links = Array.isArray(payload.links) ? payload.links : [];

    if (!nodes.length) {
      showError("No nodes available to render.");
      return;
    }

    const parents = new Map(nodes.map((node) => [node.id, []]));
    links.forEach((link) => {
      const list = parents.get(link.target);
      if (list) {
        list.push(link.source);
      }
    });

    const rect = graphEl.getBoundingClientRect();
    const width = rect.width || 1200;
    const height = rect.height || 800;

    const svg = window.d3.select(graphEl);
    svg.selectAll("*").remove();
    svg.attr("viewBox", [0, 0, width, height].join(" "));

    let dag;
    try {
      dag = window.d3
        .dagStratify()
        .id((d) => d.id)
        .parentIds((d) => parents.get(d.id) || [])(nodes);
    } catch (error) {
      const message = String(error || "");
      const cycleHint = message.toLowerCase().includes("cycle")
        ? "Cycle detected in prerequisites. Please review the course links."
        : `Unable to build graph: ${message}`;
      showError(cycleHint);
      return;
    }

    try {
      const layout = window.d3
        .sugiyama()
        .nodeSize([120, 60])
        .layering(window.d3.layeringLongestPath())
        .decross(window.d3.decrossTwoLayer())
        .coord(window.d3.coordVert())
        .size([width - 80, height - 80]);

      layout(dag);

      const zoomLayer = svg.append("g").attr("transform", "translate(40,40)");

      svg.call(
        window.d3
          .zoom()
          .scaleExtent([0.2, 3])
          .on("zoom", (event) => zoomLayer.attr("transform", event.transform))
      );

      zoomLayer
        .append("g")
        .selectAll("path")
        .data(dag.links())
        .join("path")
        .attr("class", "link")
        .attr("marker-end", "url(#arrowhead)")
        .attr(
          "d",
          window.d3
            .line()
            .x((d) => d.x)
            .y((d) => d.y)
            .curve(window.d3.curveCatmullRom)
        );

      const nodeGroup = zoomLayer
        .append("g")
        .selectAll("g")
        .data(dag.descendants())
        .join("g")
        .attr("class", "node")
        .attr("transform", (d) => `translate(${d.x},${d.y})`);

      nodeGroup.each(function (d) {
        drawNodeShape(window.d3.select(this), d.data);
      });

      nodeGroup
        .append("title")
        .text((d) => d.data.title || d.data.label || "");

      nodeGroup
        .append("text")
        .attr("text-anchor", "middle")
        .attr("dy", "0.35em")
        .text((d) => d.data.label);
    } catch (error) {
      const message = String(error || "");
      const cycleHint = message.toLowerCase().includes("cycle")
        ? "Cycle detected in prerequisites. Please review the course links."
        : `Unable to render graph: ${message}`;
      showError(cycleHint);
    }
  };

  const applyLayout = () => {
    if (!cachedPayload) {
      return;
    }
    if (errorBox) {
      errorBox.style.display = "none";
    }
    if (currentLayout === "dag") {
      if (!window.d3 || typeof window.d3.dagStratify !== "function") {
        showError(
          "DAG layout unavailable. Check that d3-dag is loaded, or switch back to force."
        );
        currentLayout = "force";
        localStorage.setItem(layoutStorageKey, currentLayout);
        updateToggleLabel();
        renderForce(cachedPayload);
        return;
      }
      renderDag(cachedPayload);
    } else {
      renderForce(cachedPayload);
    }
    updateToggleLabel();
  };

  if (toggleButton) {
    updateToggleLabel();
    toggleButton.addEventListener("click", () => {
      currentLayout = currentLayout === "dag" ? "force" : "dag";
      localStorage.setItem(layoutStorageKey, currentLayout);
      applyLayout();
    });
  }

  fetch(jsonUrl, { credentials: "same-origin" })
    .then((response) => {
      if (!response.ok) {
        throw new Error(`Failed to load graph data (${response.status}).`);
      }
      return response.json();
    })
    .then((payload) => {
      cachedPayload = payload;
      applyLayout();
    })
    .catch((error) => {
      const message = String(error || "");
      showError(`Unable to load graph data: ${message}`);
    });
})();

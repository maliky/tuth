// Render prerequisite graph using a force layout (default), with d3-dag standby.
// Wrapped in an IIFE to keep globals clean on pages that include multiple scripts.
(function () {
  "use strict";

  type LayoutModeT = "force" | "dag";
  type LevelKeyT = number | "NA";

  type GraphNodeT = {
    id: string;
    label: string;
    title?: string;
    shape?: string;
    color?: string;
    level_number?: number | null;
    is_in_curriculum?: boolean;
    _levelKey?: LevelKeyT;
    _targetY?: number;
    x?: number;
    y?: number;
  };

  type GraphLinkEndpointT = GraphNodeT | string;

  type GraphLinkT = {
    source: GraphLinkEndpointT;
    target: GraphLinkEndpointT;
  };

  type GraphPayloadT = {
    nodes?: GraphNodeT[];
    links?: GraphLinkT[];
  };

  // Minimal d3 types used by this module (we do not bundle @types/d3 here).
  type D3SelectionT = {
    selectAll: (selector: string) => D3SelectionT;
    remove: () => D3SelectionT;
    attr: (name: string, value?: unknown) => D3SelectionT;
    append: (name: string) => D3SelectionT;
    data: (data: unknown[]) => D3SelectionT;
    join: (name: string) => D3SelectionT;
    each: (
      callback: (this: Element, datum: unknown, index: number) => void
    ) => D3SelectionT;
    text: (value: unknown) => D3SelectionT;
    call: (fn: unknown) => D3SelectionT;
  };

  type D3ZoomTransformT = {
    toString: () => string;
  };

  type D3ZoomEventT = {
    transform: D3ZoomTransformT;
  };

  type D3ZoomT = {
    scaleExtent: (extent: [number, number]) => D3ZoomT;
    on: (event: string, handler: (event: D3ZoomEventT) => void) => D3ZoomT;
  };

  type D3ForceSimulationT = {
    force: (name: string, force: unknown) => D3ForceSimulationT;
    on: (event: string, handler: () => void) => D3ForceSimulationT;
  };

  type D3ForceLinkT = {
    id: (fn: (node: GraphNodeT) => string) => D3ForceLinkT;
    distance: (value: number) => D3ForceLinkT;
    strength: (value: number) => D3ForceLinkT;
  };

  type D3ForceManyBodyT = {
    strength: (value: number) => D3ForceManyBodyT;
  };

  type D3ForceAxisT = {
    strength: (value: number) => D3ForceAxisT;
  };

  type D3ForceCollideT = {
    radius: (value: number) => D3ForceCollideT;
  };

  type D3LinePointT = {
    x: number;
    y: number;
  };

  type D3LineT = {
    (data: D3LinePointT[]): string;
    x: (fn: (d: D3LinePointT) => number) => D3LineT;
    y: (fn: (d: D3LinePointT) => number) => D3LineT;
    curve: (curve: unknown) => D3LineT;
  };

  type D3DagNodeT = {
    x: number;
    y: number;
    data: GraphNodeT;
  };

  type D3DagLinkT = {
    points: D3LinePointT[];
  };

  type D3DagT = {
    links: () => D3DagLinkT[];
    nodes: () => Iterable<D3DagNodeT>;
  };

  type LayoutResultT = {
    width: number;
    height: number;
  };

  type D3DagStratifyT = {
    id: (fn: (node: GraphNodeT) => string) => D3DagStratifyT;
    parentIds: (
      fn: (node: GraphNodeT) => string[]
    ) => (nodes: GraphNodeT[]) => D3DagT;
  };

  type D3SugiyamaT = {
    (dag: D3DagT): LayoutResultT;
    nodeSize: (size: [number, number]) => D3SugiyamaT;
    layering: (algo: unknown) => D3SugiyamaT;
    decross: (algo: unknown) => D3SugiyamaT;
    coord: (algo: unknown) => D3SugiyamaT;
    gap: (gap: [number, number]) => D3SugiyamaT;
    tweaks: (tweaks: unknown[]) => D3SugiyamaT;
  };

  type D3GlobalT = {
    select: (el: Element) => D3SelectionT;
    zoom: () => D3ZoomT;
    forceSimulation: (nodes: GraphNodeT[]) => D3ForceSimulationT;
    forceLink: (links: GraphLinkT[]) => D3ForceLinkT;
    forceManyBody: () => D3ForceManyBodyT;
    forceX: (fn: (node: GraphNodeT) => number) => D3ForceAxisT;
    forceY: (fn: (node: GraphNodeT) => number) => D3ForceAxisT;
    forceCollide: () => D3ForceCollideT;
    forceCenter: (x: number, y: number) => unknown;
    line: () => D3LineT;
    curveCatmullRom: unknown;
    graphStratify?: () => D3DagStratifyT;
    sugiyama?: () => D3SugiyamaT;
    layeringLongestPath?: () => unknown;
    decrossTwoLayer?: () => unknown;
    tweakSize?: (size: LayoutResultT) => unknown;
    tweakFlip?: (style?: "diagonal" | "horizontal" | "vertical") => unknown;
  };

  // Local window type to avoid global augmentation in a module-less script.
  type WindowWithD3T = Window & {
    d3?: D3GlobalT;
  };

  const graphEl = document.getElementById("graph");
  const errorBox = document.getElementById("graph-error");
  const toggleButton = document.getElementById("layout-toggle");
  // LocalStorage key for persisting the chosen layout between sessions.
  const layoutStorageKey = "prereq-graph-layout";

  /** Display a banner error message in the UI. */
  const showError = (message: string): void => {
    if (!errorBox) {
      return;
    }
    errorBox.textContent = message;
    errorBox.style.display = "block";
  };

  let cachedPayload: GraphPayloadT | null = null;
  const storedLayout = localStorage.getItem(layoutStorageKey);
  let currentLayout: LayoutModeT = storedLayout === "dag" ? "dag" : "force";

  /** Update toggle button text to reflect the active layout. */
  const updateToggleLabel = (): void => {
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

  // data-json-url is injected by the template to point at the JSON endpoint.
  const jsonUrl = graphEl.dataset.jsonUrl || "";
  if (!jsonUrl) {
    showError("Graph data URL not provided.");
    return;
  }

  // d3 is exposed as a global by the script tag (no module import here).
  const windowWithD3 = window as WindowWithD3T;
  if (!windowWithD3.d3) {
    showError("Graph library failed to load. Check that d3 is available.");
    return;
  }

  const d3 = windowWithD3.d3 as D3GlobalT;

  /** Draw a node shape based on the node metadata. */
  const drawNodeShape = (group: D3SelectionT, node: GraphNodeT): void => {
    const shape = node.shape || "box";
    const color = node.color || "#6c757d";
    const isInCurriculum = node.is_in_curriculum !== false;
    const dashStyle = isInCurriculum ? null : "6,4";

    const strokeAttrs = (selection: D3SelectionT): void => {
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

  type LevelLayoutT = {
    levelIndex: Map<LevelKeyT, number>;
    levelPositions: Map<LevelKeyT, number>;
    levelCount: number;
  };

  const getLevelKey = (node: GraphNodeT): LevelKeyT =>
    Number.isInteger(node.level_number) ? (node.level_number as number) : "NA";

  const buildLevelLayout = (
    nodes: GraphNodeT[],
    innerWidth: number,
    marginX: number
  ): LevelLayoutT => {
    const numericLevels: number[] = [];
    let hasUnknown = false;

    nodes.forEach((node) => {
      if (Number.isInteger(node.level_number)) {
        numericLevels.push(node.level_number as number);
      } else {
        hasUnknown = true;
      }
    });

    const uniqueLevels = Array.from(new Set(numericLevels)).sort(
      (a, b) => a - b
    );
    const levelKeys: LevelKeyT[] = uniqueLevels.slice();
    if (hasUnknown) {
      levelKeys.push("NA");
    }

    const levelIndex = new Map<LevelKeyT, number>();
    levelKeys.forEach((key, index) => {
      levelIndex.set(key, index);
    });

    const levelPositions = new Map<LevelKeyT, number>();
    const levelCount = Math.max(levelKeys.length, 1);
    const levelSpacing = levelCount > 1 ? innerWidth / (levelCount - 1) : 0;

    levelKeys.forEach((key, index) => {
      const x =
        levelCount > 1
          ? marginX + index * levelSpacing
          : marginX + innerWidth / 2;
      levelPositions.set(key, x);
    });

    return { levelIndex, levelPositions, levelCount };
  };

  const ensureArrowhead = (svg: D3SelectionT): void => {
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
  };

  const getNodeHoverText = (node: GraphNodeT): string => {
    const label = node.label ? String(node.label) : "";
    const title = node.title ? String(node.title) : "";
    if (label && title && label !== title) {
      return `${label} — ${title}`;
    }
    return title || label;
  };

  const normalizeNodeId = (value: string | number | null | undefined): string =>
    String(value ?? "");

  const normalizeLinkEndpoint = (endpoint: GraphLinkEndpointT): string => {
    if (typeof endpoint === "object" && endpoint !== null) {
      return normalizeNodeId(endpoint.id);
    }
    return normalizeNodeId(endpoint);
  };

  /** Resolve force-link endpoints to node objects when available. */
  const resolveLinkNode = (endpoint: GraphLinkEndpointT): GraphNodeT | null => {
    if (typeof endpoint === "object" && endpoint !== null) {
      return endpoint;
    }
    return null;
  };

  /** Render the graph using a force simulation with level-guided positions. */
  const renderForce = (payload: GraphPayloadT): void => {
    const nodes = Array.isArray(payload.nodes)
      ? // Clone the payload to avoid mutating cached data directly.
        payload.nodes.map((node) => ({
          ...node,
          id: normalizeNodeId(node.id),
        }))
      : [];
    const links = Array.isArray(payload.links)
      ? // Clone links so the force simulation can attach positions safely.
        payload.links.map((link) => ({
          ...link,
          source: normalizeLinkEndpoint(link.source),
          target: normalizeLinkEndpoint(link.target),
        }))
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

    const { levelPositions } = buildLevelLayout(nodes, innerWidth, marginX);

    // Group nodes by level so we can distribute them vertically.
    const levelGroups = new Map<LevelKeyT, GraphNodeT[]>();
    nodes.forEach((node) => {
      const key = getLevelKey(node);
      // Store computed values on the node for use by d3 forces.
      node._levelKey = key;
      if (!levelGroups.has(key)) {
        levelGroups.set(key, []);
      }
      levelGroups.get(key)?.push(node);
    });

    levelGroups.forEach((groupNodes) => {
      groupNodes.sort((a, b) => String(a.label).localeCompare(String(b.label)));
      const groupCount = groupNodes.length;
      groupNodes.forEach((node, index) => {
        const offset = (index + 1) / (groupCount + 1);
        node._targetY = marginY + offset * innerHeight;
      });
    });

    const svg = d3.select(graphEl);
    svg.selectAll("*").remove();
    svg.attr("viewBox", [0, 0, width, height].join(" "));

    // Define arrowheads for link markers once per render.
    ensureArrowhead(svg);

    const zoomLayer = svg
      .append("g")
      .attr("transform", `translate(${marginX},${marginY})`);

    // Enable pan/zoom over the graph without re-running the simulation.
    svg.call(
      d3
        .zoom()
        .scaleExtent([0.2, 3])
        .on("zoom", (event) => zoomLayer.attr("transform", event.transform))
    );

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

    nodeSelection.each(function (node: unknown) {
      const graphNode = node as GraphNodeT;
      drawNodeShape(d3.select(this), graphNode);
    });

    nodeSelection
      .append("title")
      .text((node: GraphNodeT) => getNodeHoverText(node));

    nodeSelection
      .append("text")
      .attr("text-anchor", "middle")
      .attr("dy", "0.35em")
      .text((node: GraphNodeT) => node.label);

    // Force links store endpoints as node objects once the simulation runs.
    const linkPath = (link: GraphLinkT): string => {
      const sourceNode = resolveLinkNode(link.source);
      const targetNode = resolveLinkNode(link.target);
      if (!sourceNode || !targetNode) {
        return "";
      }
      const sx = sourceNode.x || 0;
      const sy = sourceNode.y || 0;
      const tx = targetNode.x || 0;
      const ty = targetNode.y || 0;
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

    const simulation = d3
      .forceSimulation(nodes)
      .force(
        "link",
        d3
          .forceLink(links)
          .id((node) => node.id)
          .distance(140)
          .strength(0.7)
      )
      .force("charge", d3.forceManyBody().strength(-280))
      .force(
        "x",
        d3
          .forceX(
            (node) => levelPositions.get(node._levelKey as LevelKeyT) || 0
          )
          .strength(0.8)
      )
      .force(
        "y",
        d3.forceY((node) => node._targetY || innerHeight / 2).strength(0.6)
      )
      .force("collide", d3.forceCollide().radius(40))
      .force("center", d3.forceCenter(innerWidth / 2, innerHeight / 2));

    // Update SVG positions on every simulation tick.
    simulation.on("tick", () => {
      linkSelection.attr("d", (link: GraphLinkT) => linkPath(link));

      nodeSelection.attr("transform", (node: GraphNodeT) => {
        return `translate(${node.x},${node.y})`;
      });
    });
  };

  // Standby DAG renderer (kept for reference).
  /** Render the graph using d3-dag's sugiyama layout. */
  const renderDag = (payload: GraphPayloadT): void => {
    if (typeof d3.graphStratify !== "function") {
      showError(
        "Graph library failed to load. Check that d3 and d3-dag are available."
      );
      return;
    }

    const nodes = Array.isArray(payload.nodes)
      ? payload.nodes.map((node) => ({
          ...node,
          id: normalizeNodeId(node.id),
        }))
      : [];
    const links = Array.isArray(payload.links)
      ? payload.links.map((link) => ({
          ...link,
          source: normalizeLinkEndpoint(link.source),
          target: normalizeLinkEndpoint(link.target),
        }))
      : [];

    if (!nodes.length) {
      showError("No nodes available to render.");
      return;
    }

    // Build a parent list for each node for d3-dag's stratify helper.
    const parents = new Map<string, string[]>(
      nodes.map((node) => [node.id, []])
    );
    links.forEach((link) => {
      const targetId = normalizeLinkEndpoint(link.target);
      const sourceId = normalizeLinkEndpoint(link.source);
      const list = parents.get(targetId);
      if (list) {
        list.push(sourceId);
      }
    });

    const rect = graphEl.getBoundingClientRect();
    const width = rect.width || 1200;
    const height = rect.height || 800;
    const marginX = 40;
    const marginY = 40;
    const innerWidth = width - marginX * 2;
    const innerHeight = height - marginY * 2;
    const { levelIndex, levelCount } = buildLevelLayout(
      nodes,
      innerWidth,
      marginX
    );

    const svg = d3.select(graphEl);
    svg.selectAll("*").remove();
    svg.attr("viewBox", [0, 0, width, height].join(" "));
    ensureArrowhead(svg);

    let dag: D3DagT;
    try {
      dag = d3
        .graphStratify()
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
      if (!d3.sugiyama) {
        throw new Error("DAG layout engine is unavailable.");
      }

      const semesterLayering = (
        dagGraph: D3DagT,
        sep: (source: unknown, target: unknown) => number
      ): number => {
        let maxSep = 0;
        const nodesList: Array<{ data: GraphNodeT; y: number }> = [];
        const dagNodes =
          typeof dagGraph.nodes === "function"
            ? dagGraph.nodes()
            : (dagGraph as unknown as Iterable<D3DagNodeT>);

        if (!dagNodes || !(Symbol.iterator in Object(dagNodes))) {
          throw new Error("DAG nodes are not iterable.");
        }

        for (const node of dagNodes) {
          nodesList.push(node);
          maxSep = Math.max(
            maxSep,
            sep(undefined, node) + sep(node, undefined)
          );
        }

        const layerGap = Math.max(maxSep, 1);
        let min = Infinity;
        let max = -Infinity;

        nodesList.forEach((node) => {
          const key = getLevelKey(node.data);
          const index = levelIndex.get(key) ?? levelCount - 1;
          node.y = index * layerGap;
          min = Math.min(min, node.y - sep(undefined, node));
          max = Math.max(max, node.y + sep(node, undefined));
        });

        nodesList.forEach((node) => {
          node.y -= min;
        });

        return max - min;
      };

      let layout = d3.sugiyama().nodeSize([120, 60]);
      layout = layout.layering(semesterLayering);

      if (d3.decrossTwoLayer) {
        layout = layout.decross(d3.decrossTwoLayer());
      }

      const tweaks: unknown[] = [];

      if (d3.tweakSize) {
        tweaks.push(d3.tweakSize({ width: innerWidth, height: innerHeight }));
      }

      if (d3.tweakFlip) {
        tweaks.push(d3.tweakFlip("diagonal"));
      }

      if (tweaks.length && typeof layout.tweaks === "function") {
        layout = layout.tweaks(tweaks);
      }

      layout(dag);

      const zoomLayer = svg
        .append("g")
        .attr("transform", `translate(${marginX},${marginY})`);

      svg.call(
        d3
          .zoom()
          .scaleExtent([0.2, 3])
          .on("zoom", (event) => zoomLayer.attr("transform", event.transform))
      );

      const lineBuilder = d3
        .line()
        .x((d) => (d as D3LinePointT).x)
        .y((d) => (d as D3LinePointT).y)
        .curve(d3.curveCatmullRom);

      zoomLayer
        .append("g")
        .selectAll("path")
        .data(Array.from(dag.links()))
        .join("path")
        .attr("class", "link")
        .attr("marker-end", "url(#arrowhead)")
        .attr("d", (link: D3DagLinkT) => lineBuilder(link.points));

      const nodeGroup = zoomLayer
        .append("g")
        .selectAll("g")
        .data(Array.from(dag.nodes()))
        .join("g")
        .attr("class", "node")
        .attr("transform", (d: D3DagNodeT) => {
          return `translate(${d.x},${d.y})`;
        });

      nodeGroup.each(function (d: unknown) {
        const dagNode = d as D3DagNodeT;
        drawNodeShape(d3.select(this), dagNode.data);
      });

      nodeGroup
        .append("title")
        .text((d: D3DagNodeT) => getNodeHoverText(d.data));

      nodeGroup
        .append("text")
        .attr("text-anchor", "middle")
        .attr("dy", "0.35em")
        .text((d: D3DagNodeT) => d.data.label);
    } catch (error) {
      const message = String(error || "");
      const cycleHint = message.toLowerCase().includes("cycle")
        ? "Cycle detected in prerequisites. Please review the course links."
        : `Unable to render graph: ${message}`;
      showError(cycleHint);
    }
  };

  /** Render the current layout and update the toggle label. */
  const applyLayout = (): void => {
    if (!cachedPayload) {
      return;
    }
    if (errorBox) {
      errorBox.style.display = "none";
    }
    if (currentLayout === "dag") {
      if (typeof d3.graphStratify !== "function") {
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
    // Persist layout preference between page loads.
    toggleButton.addEventListener("click", () => {
      currentLayout = currentLayout === "dag" ? "force" : "dag";
      localStorage.setItem(layoutStorageKey, currentLayout);
      applyLayout();
    });
  }

  // Fetch graph data and render once the payload arrives.
  fetch(jsonUrl, { credentials: "same-origin" })
    .then((response) => {
      if (!response.ok) {
        throw new Error(`Failed to load graph data (${response.status}).`);
      }
      return response.json();
    })
    .then((payload: GraphPayloadT) => {
      cachedPayload = payload;
      applyLayout();
    })
    .catch((error) => {
      const message = String(error || "");
      showError(`Unable to load graph data: ${message}`);
    });
})();

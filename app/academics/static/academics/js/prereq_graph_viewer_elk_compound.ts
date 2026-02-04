// Prerequisite graph viewer using Cytoscape.js + ELK (compound semester layout).
//
// We intentionally keep this as a plain browser script (no bundler, no imports)
// because Tusis serves static assets directly via Django.
// Wrapped in an IIFE so we do not leak symbols into the global scope.
(function () {
  "use strict";

  type LevelKeyT = number | "NA";
  type LayoutModeSelectionT = "elk" | "elk-compound";

  type GraphNodeT = {
    id: string;
    label: string;
    title?: string;
    shape?: string;
    color?: string;
    level_number?: number | null;
    is_in_curriculum?: boolean;
    group_number?: number;
    course_id?: number;
  };

  type GraphLinkT = {
    source: string;
    target: string;
    type?: string;
  };

  type GraphPayloadT = {
    nodes?: GraphNodeT[];
    links?: GraphLinkT[];
  };

  type CyNodeDataT = {
    id: string;
    label: string;
    title: string;
    shape: string;
    borderColor: string;
    isInCurriculum: boolean;
    levelKey: LevelKeyT;
    partition: string;
    parent?: string;
  };

  type CyParentDataT = {
    id: string;
    label: string;
    bandColor: string;
    levelKey: LevelKeyT;
    partition: string;
  };

  type CyEdgeDataT = {
    id: string;
    source: string;
    target: string;
    type: string;
  };

  type CyNodeElementT = {
    group: "nodes";
    data: CyNodeDataT;
    classes?: string;
  };

  type CyParentElementT = {
    group: "nodes";
    data: CyParentDataT;
    classes?: string;
  };

  type CyEdgeElementT = {
    group: "edges";
    data: CyEdgeDataT;
    classes?: string;
  };

  type CyElementT = CyNodeElementT | CyParentElementT | CyEdgeElementT;

  type CyLayoutOptionsT = {
    name: string;
    fit?: boolean;
    padding?: number;
    animate?: boolean;
    nodeDimensionsIncludeLabels?: boolean;
    elk?: Record<string, unknown>;
    nodeLayoutOptions?: (node: unknown) => Record<string, unknown>;
    ready?: () => void;
    stop?: () => void;
  };

  type CyLayoutRunT = {
    run: () => void;
  };

  type CyEventT = {
    target: {
      // Minimal subset of the Cytoscape element API that we use for hover tooltips.
      data: (key?: string) => unknown;
      renderedPosition: () => { x: number; y: number };
    };
    renderedPosition?: { x: number; y: number };
    originalEvent?: MouseEvent;
  };

  type CytoscapeInstanceT = {
    destroy: () => void;
    fit: (elements?: unknown, padding?: number) => void;
    layout: (options: CyLayoutOptionsT) => CyLayoutRunT;
    on: (
      eventName: string,
      selector: string,
      handler: (event: CyEventT) => void
    ) => void;
    nodes: () => CyNodeCollectionT;
    resize: () => void;
  };

  type CyNodeCollectionT = {
    ungrabify: () => void;
  };

  type CytoscapeFactoryT = (options: {
    container: HTMLElement;
    elements: CyElementT[];
    style: unknown[];
    userZoomingEnabled?: boolean;
    userPanningEnabled?: boolean;
    boxSelectionEnabled?: boolean;
  }) => CytoscapeInstanceT;

  type WindowWithCytoT = Window & {
    cytoscape?: CytoscapeFactoryT;
    cytoscapeElk?: (cytoscape: CytoscapeFactoryT) => void;
    ELK?: unknown;
  };

  const graphEl = document.getElementById("graph-elk-compound");
  const errorBox = document.getElementById("graph-error");
  const layoutModeKey = "prereq-graph-layout-mode";

  /** Display a banner error message in the UI. */
  const showError = (message: string): void => {
    if (!errorBox) {
      return;
    }
    errorBox.textContent = message;
    errorBox.style.display = "block";
  };

  if (!graphEl) {
    return;
  }

  // data-json-url is injected by the Django template to point at the JSON export.
  const jsonUrl = (graphEl as HTMLElement).dataset.jsonUrl || "";
  if (!jsonUrl) {
    showError("Graph data URL not provided.");
    return;
  }

  const windowWithCyto = window as WindowWithCytoT;
  if (!windowWithCyto.cytoscape) {
    showError(
      "Graph library failed to load. Check that Cytoscape.js is available."
    );
    return;
  }

  const cytoscape = windowWithCyto.cytoscape as CytoscapeFactoryT;
  if (typeof windowWithCyto.cytoscapeElk === "function") {
    // Ensure the layout extension is registered even if script order changes.
    windowWithCyto.cytoscapeElk(cytoscape);
  }

  const existingTooltip = document.querySelector(
    ".graph-tooltip"
  ) as HTMLDivElement | null;
  // Simple HTML tooltip for node hover. Canvas/WebGL renderers can't rely on
  // the browser's native <title> tooltip, so we do it ourselves.
  const tooltipEl = existingTooltip || document.createElement("div");
  if (!existingTooltip) {
    tooltipEl.className = "graph-tooltip";
    tooltipEl.style.position = "fixed";
    tooltipEl.style.zIndex = "9999";
    tooltipEl.style.display = "none";
    tooltipEl.style.pointerEvents = "none";
    tooltipEl.style.background = "rgba(33, 37, 41, 0.92)";
    tooltipEl.style.color = "#ffffff";
    tooltipEl.style.padding = "6px 8px";
    tooltipEl.style.borderRadius = "6px";
    tooltipEl.style.fontSize = "12px";
    tooltipEl.style.maxWidth = "320px";
    tooltipEl.style.boxShadow = "0 6px 14px rgba(0,0,0,0.18)";
    document.body.appendChild(tooltipEl);
  }

  let cy: CytoscapeInstanceT | null = null;
  let cachedPayload: GraphPayloadT | null = null;

  /** Toggle visibility for the ELK compound graph container. */
  const setGraphVisible = (isVisible: boolean): void => {
    if (!graphEl) {
      return;
    }
    graphEl.classList.toggle("is-hidden", !isVisible);
  };

  /** Determine which layout mode is active from localStorage. */
  const getActiveMode = (): LayoutModeSelectionT => {
    const stored = localStorage.getItem(layoutModeKey);
    if (stored === "elk" || stored === "elk-compound") {
      return stored;
    }
    return "elk";
  };

  setGraphVisible(getActiveMode() === "elk-compound");

  /** Normalize the semester/layer key from the JSON payload. */
  const normalizeLevelKey = (node: GraphNodeT): LevelKeyT => {
    const raw = node.level_number;
    if (typeof raw === "number" && Number.isFinite(raw) && raw > 0) {
      return Math.trunc(raw);
    }
    return "NA";
  };

  /** Convert a level key to a stable partition id (string) for ELK. */
  const levelKeyToPartition = (levelKey: LevelKeyT): string => {
    if (levelKey === "NA") {
      return "NA";
    }
    // Pad so lexical ordering matches numeric ordering (e.g. 02 before 10).
    return String(levelKey).padStart(2, "0");
  };

  /** Map DOT-ish node shapes to a Cytoscape supported shape. */
  const normalizeNodeShape = (shape: string | undefined): string => {
    switch ((shape || "box").toLowerCase()) {
      case "ellipse":
        return "ellipse";
      case "triangle":
        return "triangle";
      case "diamond":
        return "diamond";
      case "egg":
        return "ellipse";
      case "house":
        return "pentagon";
      case "box":
      default:
        return "rectangle";
    }
  };

  /** Convert a semester index into a year/semester label. */
  const formatLevelLabel = (level: number): string => {
    const year = Math.ceil(level / 2);
    const semester = level % 2 === 0 ? 2 : 1;
    return `Y${year} S${semester}`;
  };

  /** Extract sorted semester levels from the payload for band rendering. */
  const extractLevelNumbers = (payload: GraphPayloadT): number[] => {
    const nodes = Array.isArray(payload.nodes) ? payload.nodes : [];
    const levels = new Set<number>();
    nodes.forEach((node) => {
      const level = node.level_number;
      if (typeof level === "number" && Number.isFinite(level)) {
        levels.add(Math.trunc(level));
      }
    });
    return Array.from(levels).sort((a, b) => a - b);
  };

  /** Build the compound semester parent nodes used by the layout. */
  const buildSemesterParents = (levels: number[]): CyParentElementT[] => {
    return levels.map((level, index) => {
      const isOdd = index % 2 === 0;
      const bandColor = isOdd ? "#f8f9fa" : "#ffffff";
      return {
        group: "nodes",
        data: {
          id: `SEM${level}`,
          label: formatLevelLabel(level),
          bandColor,
          levelKey: level,
          partition: levelKeyToPartition(level),
        },
        classes: "semester-group",
      };
    });
  };

  /** Determine the shared level for a group of alternative nodes. */
  const groupLevelKey = (groupNodes: GraphNodeT[]): LevelKeyT => {
    const numericLevels = groupNodes
      .map((node) => node.level_number)
      .filter(
        (level): level is number =>
          typeof level === "number" && Number.isFinite(level) && level > 0
      );
    if (numericLevels.length) {
      return Math.min(...numericLevels);
    }
    return "NA";
  };

  /** Stable sort key for alternative group nodes. */
  const groupSortKey = (node: GraphNodeT): number | string =>
    node.course_id ?? node.label ?? node.id;

  /** Group nodes by alternative group_number. */
  const buildGroupMap = (nodes: GraphNodeT[]): Map<number, GraphNodeT[]> => {
    const groupMap = new Map<number, GraphNodeT[]>();
    nodes.forEach((node) => {
      const groupNumber = node.group_number;
      if (typeof groupNumber === "number" && groupNumber > 0) {
        if (!groupMap.has(groupNumber)) {
          groupMap.set(groupNumber, []);
        }
        groupMap.get(groupNumber)?.push(node);
      }
    });
    return groupMap;
  };

  /** Resolve original node ids to their level keys. */
  const buildNodeLevelKeyById = (
    nodes: GraphNodeT[]
  ): Map<string, LevelKeyT> => {
    const nodeLevelKeyById = new Map<string, LevelKeyT>();
    nodes.forEach((node) => {
      nodeLevelKeyById.set(String(node.id), normalizeLevelKey(node));
    });
    return nodeLevelKeyById;
  };

  /** Map alternative group members to their group ids + level keys. */
  const buildGroupMappings = (
    groupMap: Map<number, GraphNodeT[]>
  ): {
    groupedNodeId: Map<string, string>;
    groupLevelKeyById: Map<string, LevelKeyT>;
  } => {
    const groupedNodeId = new Map<string, string>();
    const groupLevelKeyById = new Map<string, LevelKeyT>();
    groupMap.forEach((groupNodes, groupNumber) => {
      const groupId = `ALT${groupNumber}`;
      groupNodes.forEach((node) => {
        groupedNodeId.set(String(node.id), groupId);
      });
      groupLevelKeyById.set(groupId, groupLevelKey(groupNodes));
    });
    return { groupedNodeId, groupLevelKeyById };
  };

  /** Build target semester levels for nodes missing a level number. */
  const buildTargetLevelsBySource = (
    links: GraphLinkT[],
    groupedNodeId: Map<string, string>,
    nodeLevelKeyById: Map<string, LevelKeyT>,
    groupLevelKeyById: Map<string, LevelKeyT>
  ): Map<string, number[]> => {
    const targetLevelsBySource = new Map<string, number[]>();
    links.forEach((link) => {
      let sourceId = String(link.source);
      let targetId = String(link.target);
      if (groupedNodeId.has(sourceId)) {
        sourceId = groupedNodeId.get(sourceId) as string;
      }
      if (groupedNodeId.has(targetId)) {
        targetId = groupedNodeId.get(targetId) as string;
      }
      const targetLevelKey =
        groupLevelKeyById.get(targetId) ?? nodeLevelKeyById.get(targetId);
      if (typeof targetLevelKey === "number") {
        if (!targetLevelsBySource.has(sourceId)) {
          targetLevelsBySource.set(sourceId, []);
        }
        targetLevelsBySource.get(sourceId)?.push(targetLevelKey);
      }
    });
    return targetLevelsBySource;
  };

  /** Select the earliest target level for a node. */
  const minTargetLevel = (
    targetLevelsBySource: Map<string, number[]>,
    nodeId: string
  ): number | undefined => {
    const levels = targetLevelsBySource.get(nodeId);
    if (!levels || !levels.length) {
      return undefined;
    }
    return Math.min(...levels);
  };

  /** Resolve the semester column for nodes that do not have a level number. */
  const resolveAnchorLevel = (
    targetLevel: number | undefined,
    levels: number[]
  ): number | null => {
    if (!targetLevel || !levels.length) {
      return null;
    }
    if (targetLevel <= levels[0]) {
      return levels[0];
    }
    const desired = targetLevel - 1;
    let candidate = levels[0];
    levels.forEach((level) => {
      if (level <= desired) {
        candidate = level;
      }
    });
    return candidate;
  };

  /** Build Cytoscape elements from the exported JSON format. */
  const buildElements = (payload: GraphPayloadT): CyElementT[] => {
    const nodes = Array.isArray(payload.nodes) ? payload.nodes : [];
    const links = Array.isArray(payload.links) ? payload.links : [];

    const elements: CyElementT[] = [];
    const groupMap = buildGroupMap(nodes);
    const nodeLevelKeyById = buildNodeLevelKeyById(nodes);
    const { groupedNodeId, groupLevelKeyById } = buildGroupMappings(groupMap);
    const targetLevelsBySource = buildTargetLevelsBySource(
      links,
      groupedNodeId,
      nodeLevelKeyById,
      groupLevelKeyById
    );
    const levels = extractLevelNumbers(payload);
    const parentNodes = buildSemesterParents(levels);
    const fallbackLevel = levels.length ? levels[0] : null;

    parentNodes.forEach((parent) => elements.push(parent));

    const resolveParentId = (level: number | null): string | undefined => {
      if (typeof level === "number" && Number.isFinite(level)) {
        return `SEM${level}`;
      }
      return undefined;
    };

    groupMap.forEach((groupNodes, groupNumber) => {
      const sortedNodes = [...groupNodes].sort((a, b) => {
        const aKey = groupSortKey(a);
        const bKey = groupSortKey(b);
        if (typeof aKey === "number" && typeof bKey === "number") {
          return aKey - bKey;
        }
        return String(aKey).localeCompare(String(bKey));
      });

      const levelKey = groupLevelKey(sortedNodes);
      const groupId = `ALT${groupNumber}`;
      const groupTargetLevel =
        typeof levelKey === "number"
          ? undefined
          : minTargetLevel(targetLevelsBySource, groupId);
      const anchorLevel =
        typeof levelKey === "number"
          ? levelKey
          : (resolveAnchorLevel(groupTargetLevel, levels) ?? fallbackLevel);
      const partitionLevel =
        typeof anchorLevel === "number" ? anchorLevel : levelKey;
      const partition = levelKeyToPartition(partitionLevel);
      const labelLines = sortedNodes.map((node) =>
        String(node.label || node.id)
      );
      const titleLines = sortedNodes.map((node) =>
        String(node.title || node.label || node.id)
      );
      const groupLabel = [`ALT ${groupNumber}`, ...labelLines].join("\n");
      const groupTitle = `Alternatives: ${titleLines.join(" | ")}`;
      const groupColor =
        sortedNodes.find((node) => node.color)?.color || "#6c757d";
      const isInCurriculum = sortedNodes.every(
        (node) => node.is_in_curriculum !== false
      );
      const groupClasses = isInCurriculum ? "" : "is-outside-curriculum";

      elements.push({
        group: "nodes",
        data: {
          id: groupId,
          label: groupLabel,
          title: groupTitle,
          shape: "rectangle",
          borderColor: String(groupColor),
          isInCurriculum,
          levelKey,
          partition,
          parent: resolveParentId(anchorLevel),
        },
        classes: groupClasses,
      });
    });

    for (const node of nodes) {
      if (groupedNodeId.has(String(node.id))) {
        continue;
      }
      const levelKey = normalizeLevelKey(node);
      const nodeTargetLevel =
        typeof levelKey === "number"
          ? undefined
          : minTargetLevel(targetLevelsBySource, String(node.id));
      const anchorLevel =
        typeof levelKey === "number"
          ? levelKey
          : (resolveAnchorLevel(nodeTargetLevel, levels) ?? fallbackLevel);
      const partitionLevel =
        typeof anchorLevel === "number" ? anchorLevel : levelKey;
      const partition = levelKeyToPartition(partitionLevel);
      const nodeClasses =
        node.is_in_curriculum !== false ? "" : "is-outside-curriculum";
      elements.push({
        group: "nodes",
        data: {
          id: String(node.id),
          label: String(node.label || node.id),
          title: String(node.title || node.label || node.id),
          shape: normalizeNodeShape(node.shape),
          borderColor: String(node.color || "#6c757d"),
          isInCurriculum: node.is_in_curriculum !== false,
          levelKey,
          partition,
          parent: resolveParentId(anchorLevel),
        },
        classes: nodeClasses,
      });
    }

    let edgeIndex = 0;
    const edgeKeys = new Set<string>();
    for (const link of links) {
      let source = String(link.source);
      let target = String(link.target);
      if (groupedNodeId.has(source)) {
        source = groupedNodeId.get(source) as string;
      }
      if (groupedNodeId.has(target)) {
        target = groupedNodeId.get(target) as string;
      }
      if (source === target) {
        continue;
      }
      const key = `${source}|${target}`;
      if (edgeKeys.has(key)) {
        continue;
      }
      edgeKeys.add(key);
      elements.push({
        group: "edges",
        data: {
          id: `E${edgeIndex++}`,
          source,
          target,
          type: String(link.type || "prereq"),
        },
      });
    }

    return elements;
  };

  /** Default Cytoscape stylesheet (kept in JS to avoid CSS specificity fights). */
  const buildStyles = (): unknown[] => [
    {
      selector: "node",
      style: {
        shape: "data(shape)",
        width: 110,
        height: 44,
        "background-color": "#ffffff",
        "border-width": 2,
        "border-color": "data(borderColor)",
        "border-style": "solid",
        label: "data(label)",
        color: "#212529",
        "font-size": 12,
        "text-valign": "center",
        "text-halign": "center",
        "text-wrap": "wrap",
        "text-max-width": 96,
      },
    },
    {
      selector: "node.semester-group",
      style: {
        shape: "round-rectangle",
        "background-color": "data(bandColor)",
        "border-width": 1,
        "border-color": "#dee2e6",
        "border-style": "solid",
        padding: 16,
        "text-valign": "top",
        "text-halign": "center",
        "text-margin-y": 6,
        "font-size": 12,
        "font-weight": 600,
        "text-wrap": "wrap",
        "text-max-width": 140,
        "compound-sizing-wrt-labels": "include",
      },
    },
    {
      selector: "node.is-outside-curriculum",
      style: {
        "border-style": "dashed",
      },
    },
    {
      selector: "edge",
      style: {
        width: 1.6,
        "line-color": "#adb5bd",
        "target-arrow-color": "#adb5bd",
        "target-arrow-shape": "triangle",
        "arrow-scale": 0.9,
        "curve-style": "bezier",
      },
    },
  ];

  /** Run the ELK layered layout with compound semester parents. */
  const runElkLayout = (): void => {
    if (!cy) return;
    if (!windowWithCyto.ELK) {
      showError("ELK engine failed to load. Check that elkjs is available.");
      return;
    }

    try {
      cy.layout({
        name: "elk",
        fit: true,
        padding: 24,
        animate: false,
        nodeDimensionsIncludeLabels: true,
        nodeLayoutOptions: (node: unknown) => {
          // cytoscape-elk passes a Cytoscape node object.
          // We only need node.data("partition") here.
          const dataFn = (node as { data?: (key: string) => unknown }).data;
          const partition =
            typeof dataFn === "function"
              ? dataFn.call(node, "partition")
              : "NA";
          if (partition === "NA") {
            return {};
          }
          return {
            // Constrain nodes into partitions (semesters) ordered along elk.direction.
            // See ELK's layered partitioning options.
            "elk.partitioning.partition": String(partition),
          };
        },
        elk: {
          algorithm: "layered",
          "elk.direction": "RIGHT",
          "elk.partitioning.activate": true,
          "elk.hierarchyHandling": "INCLUDE_CHILDREN",
          // Slightly more breathing room for course graphs.
          "elk.spacing.nodeNode": 30,
          "elk.layered.spacing.nodeNodeBetweenLayers": 70,
          // Reduce edge crossings where possible (default is already good).
          "elk.layered.crossingMinimization.strategy": "LAYER_SWEEP",
        },
      }).run();
    } catch (err) {
      showError(
        "Unable to render graph: ELK layout is unavailable. Check that elkjs and cytoscape-elk are loaded."
      );
      // Also surface the original error for debugging.
      // eslint-disable-next-line no-console
      console.error(err);
    }
  };

  /** Update tooltip content and location (used for hover/move). */
  const showTooltip = (title: string, event: CyEventT): void => {
    if (!title) return;

    tooltipEl.textContent = title;
    tooltipEl.style.display = "block";

    // Cytoscape provides `renderedPosition()` for elements, but for better UX we
    // prefer the mouse pointer when available.
    const mouse = event.originalEvent;
    const x = mouse ? mouse.clientX : event.target.renderedPosition().x;
    const y = mouse ? mouse.clientY : event.target.renderedPosition().y;
    tooltipEl.style.left = `${x + 12}px`;
    tooltipEl.style.top = `${y + 12}px`;
  };

  const hideTooltip = (): void => {
    tooltipEl.style.display = "none";
  };

  /** Render a payload inside the page container. */
  const renderGraph = (payload: GraphPayloadT): void => {
    setGraphVisible(true);
    if (cy) {
      cy.destroy();
      cy = null;
    }

    const elements = buildElements(payload);
    if (elements.length === 0) {
      showError("Graph payload is empty.");
      return;
    }

    cy = cytoscape({
      container: graphEl as HTMLElement,
      elements,
      style: buildStyles(),
      userZoomingEnabled: true,
      userPanningEnabled: true,
      boxSelectionEnabled: false,
    });
    cy.nodes().ungrabify();

    // Hover tooltip: show full course title.
    cy.on("mouseover", "node", (event) => {
      const title = String(event.target.data("title") || "");
      showTooltip(title, event);
    });
    cy.on("mousemove", "node", (event) => {
      const title = String(event.target.data("title") || "");
      showTooltip(title, event);
    });
    cy.on("mouseout", "node", () => {
      hideTooltip();
    });

    runElkLayout();
  };

  window.addEventListener("resize", () => {
    if (!cy) return;
    cy.resize();
    cy.fit(undefined, 24);
  });

  /** Fetch the payload from Django and render it when ELK compound is active. */
  const loadAndRender = async (forceRender = false): Promise<void> => {
    try {
      const response = await fetch(jsonUrl, { credentials: "same-origin" });
      if (!response.ok) {
        showError(`Unable to load graph JSON (${response.status}).`);
        return;
      }
      const payload = (await response.json()) as GraphPayloadT;
      cachedPayload = payload;
      if (forceRender || getActiveMode() === "elk-compound") {
        renderGraph(payload);
      }
    } catch (err) {
      showError("Unable to load graph JSON. Check your network connection.");
      // eslint-disable-next-line no-console
      console.error(err);
    }
  };

  window.addEventListener("prereq-layout-change", (event) => {
    const layoutEvent = event as CustomEvent<{ mode?: LayoutModeSelectionT }>;
    const mode = layoutEvent.detail?.mode;
    if (!mode) {
      return;
    }
    if (mode === "elk-compound") {
      if (cachedPayload) {
        renderGraph(cachedPayload);
      } else {
        void loadAndRender(true);
      }
      return;
    }
    setGraphVisible(false);
    if (cy) {
      cy.destroy();
      cy = null;
    }
  });

  void loadAndRender();
})();

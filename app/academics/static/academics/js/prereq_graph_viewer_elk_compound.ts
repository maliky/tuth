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
    width: number;
    height: number;
    labelOffsetY: number;
  };

  type CyParentDataT = {
    id: string;
    label: string;
    bandColor: string;
    bandOpacity?: number;
    levelKey: LevelKeyT;
    partition: string;
    isParent: boolean;
    parent?: string;
  };

  type CyEdgeDataT = {
    id: string;
    source: string;
    target: string;
    type: string;
  };

  type CyElementHandleT = {
    addClass: (name: string) => void;
    removeClass: (name: string) => void;
    remove: () => void;
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

  type ElkLabelT = {
    text: string;
  };

  type ElkNodeT = {
    id: string;
    labels?: ElkLabelT[];
    width?: number;
    height?: number;
    children?: ElkNodeT[];
    properties?: Record<string, unknown>;
  };

  type ElkEdgeT = {
    id: string;
    sources: string[];
    targets: string[];
  };

  type ElkGraphT = {
    id: string;
    layoutOptions: Record<string, unknown>;
    children: ElkNodeT[];
    edges: ElkEdgeT[];
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
    add: (elements: CyElementT[]) => void;
    destroy: () => void;
    fit: (elements?: unknown, padding?: number) => void;
    layout: (options: CyLayoutOptionsT) => CyLayoutRunT;
    on: (
      eventName: string,
      selector: string,
      handler: (event: CyEventT) => void
    ) => void;
    getElementById: (id: string) => CyElementHandleT;
    nodes: () => CyNodeCollectionT;
    resize: () => void;
  };

  type CyNodeCollectionT = {
    ungrabify: () => void;
  };

  type GraphIndexT = {
    nodeIds: string[];
    edgeIds: string[];
    incomingByTarget: Map<string, Set<string>>;
    edgeIdByKey: Map<string, string>;
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
  const downloadElkButton = document.getElementById(
    "download-elk-json"
  ) as HTMLButtonElement | null;
  const toggleNonCurriculumButton = document.getElementById(
    "toggle-non-curriculum"
  ) as HTMLButtonElement | null;

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
  let graphIndex: GraphIndexT | null = null;
  let cachedElements: CyElementT[] | null = null;
  let showNonCurriculum = true;
  let nonCurriculumHidden = false;

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
    if (stored === "elk-compound" || stored === "elk") {
      return "elk-compound";
    }
    return "elk-compound";
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
      case "circle":
        return "ellipse";
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

  /** Determine per-node sizing and label offset based on shape. */
  const getNodeVisual = (
    node: GraphNodeT
  ): {
    shape: string;
    width: number;
    height: number;
    labelOffsetY: number;
  } => {
    const rawShape = (node.shape || "box").toLowerCase();
    const labelText = String(node.label || "");
    const titleText = String(node.title || "");
    const courseToken = `${labelText} ${titleText} ${node.id}`.toUpperCase();
    const isCOBA = courseToken.includes("COBA");

    if (isCOBA) {
      return {
        shape: "diamond",
        width: 90,
        height: 90,
        labelOffsetY: 0,
      };
    }

    const isCompactShape = rawShape === "house" || rawShape === "circle";
    const shape = normalizeNodeShape(rawShape);
    const width = isCompactShape ? 90 : 110;
    const height = isCompactShape ? 90 : 44;
    const labelOffsetY = rawShape === "triangle" ? 2 : 0;
    return { shape, width, height, labelOffsetY };
  };

  /** Convert a semester index into a semester label. */
  const formatLevelLabel = (level: number): string => {
    const semester = level % 2 === 0 ? 2 : 1;
    return `S${semester}`;
  };

  /** Convert a semester year index into a year label. */
  const formatYearLabel = (year: number): string => {
    const yearLabels: Record<number, string> = {
      1: "Freshman",
      2: "Sophomore",
      3: "Junior",
      4: "Senior 1",
      5: "Senior 2",
    };
    return yearLabels[year] ?? `Year ${year}`;
  };

  /** Convert a semester index into a year number. */
  const levelToYear = (level: number): number => Math.ceil(level / 2);

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
      const isFirstSemester = level % 2 === 1;
      const bandColor = isFirstSemester ? "#d1e7dd" : "#cfe2ff";
      const bandOpacity = 0.9;
      const year = levelToYear(level);
      return {
        group: "nodes",
        data: {
          id: `SEM${level}`,
          label: formatLevelLabel(level),
          bandColor,
          bandOpacity,
          levelKey: level,
          partition: levelKeyToPartition(level),
          isParent: true,
          parent: `YEAR${year}`,
        },
        classes: "semester-group",
      };
    });
  };

  /** Build the compound year parent nodes used by the layout. */
  const buildYearParents = (levels: number[]): CyParentElementT[] => {
    const years = Array.from(
      new Set(levels.map((level) => levelToYear(level)))
    ).sort((a, b) => a - b);
    // Phoenix Gold with increasing opacity for year grouping.
    const yearBandOpacities = [0.2, 0.4, 0.6, 0.8];

    return years.map((year, index) => {
      const bandOpacity = yearBandOpacities[index % yearBandOpacities.length];
      return {
        group: "nodes",
        data: {
          id: `YEAR${year}`,
          label: formatYearLabel(year),
          bandColor: "#ffc107",
          bandOpacity,
          levelKey: year,
          partition: levelKeyToPartition(year),
          isParent: true,
        },
        classes: "year-group",
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

  /** Map alternative group members to their group's level key. */
  const buildGroupLevelKeyById = (
    groupMap: Map<number, GraphNodeT[]>
  ): Map<string, LevelKeyT> => {
    const groupLevelKeyById = new Map<string, LevelKeyT>();
    groupMap.forEach((groupNodes) => {
      const levelKey = groupLevelKey(groupNodes);
      groupNodes.forEach((node) => {
        groupLevelKeyById.set(String(node.id), levelKey);
      });
    });
    return groupLevelKeyById;
  };

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

  /** Build target semester levels for nodes missing a level number. */
  const buildTargetLevelsBySource = (
    links: GraphLinkT[],
    nodeLevelKeyById: Map<string, LevelKeyT>,
    groupLevelKeyById: Map<string, LevelKeyT>
  ): Map<string, number[]> => {
    const targetLevelsBySource = new Map<string, number[]>();
    links.forEach((link) => {
      const sourceId = String(link.source);
      const targetId = String(link.target);
      const rawTargetLevelKey = nodeLevelKeyById.get(targetId);
      const groupTargetLevelKey = groupLevelKeyById.get(targetId);
      const targetLevelKey =
        typeof rawTargetLevelKey === "number"
          ? rawTargetLevelKey
          : groupTargetLevelKey;
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

  const minGroupTargetLevel = (
    groupNodes: GraphNodeT[],
    targetLevelsBySource: Map<string, number[]>
  ): number | undefined => {
    const levels: number[] = [];
    groupNodes.forEach((node) => {
      const nodeLevels = targetLevelsBySource.get(String(node.id));
      if (nodeLevels) {
        levels.push(...nodeLevels);
      }
    });
    if (!levels.length) {
      return undefined;
    }
    return Math.min(...levels);
  };

  const resolveEffectiveLevelKey = (
    nodeId: string,
    nodeLevelKeyById: Map<string, LevelKeyT>,
    groupLevelKeyById: Map<string, LevelKeyT>
  ): LevelKeyT => {
    const nodeLevelKey = nodeLevelKeyById.get(nodeId);
    if (typeof nodeLevelKey === "number") {
      return nodeLevelKey;
    }
    const groupLevelKey = groupLevelKeyById.get(nodeId);
    if (typeof groupLevelKey === "number") {
      return groupLevelKey;
    }
    return nodeLevelKey ?? "NA";
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
    const groupLevelKeyById = buildGroupLevelKeyById(groupMap);
    const targetLevelsBySource = buildTargetLevelsBySource(
      links,
      nodeLevelKeyById,
      groupLevelKeyById
    );
    const levels = extractLevelNumbers(payload);
    const yearParents = buildYearParents(levels);
    const parentNodes = buildSemesterParents(levels);
    const fallbackLevel = levels.length ? levels[0] : null;

    yearParents.forEach((parent) => elements.push(parent));
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
      const groupId = `ALTGROUP${groupNumber}`;
      const groupTargetLevel =
        typeof levelKey === "number"
          ? undefined
          : minGroupTargetLevel(sortedNodes, targetLevelsBySource);
      const anchorLevel =
        typeof levelKey === "number"
          ? levelKey
          : (resolveAnchorLevel(groupTargetLevel, levels) ?? fallbackLevel);
      const partitionLevel =
        typeof anchorLevel === "number" ? anchorLevel : levelKey;
      const partition = levelKeyToPartition(partitionLevel);

      elements.push({
        group: "nodes",
        data: {
          id: groupId,
          label: `ALT ${groupNumber}`,
          bandColor: "#f8f9fa",
          bandOpacity: 0.4,
          levelKey,
          partition,
          isParent: true,
          parent: resolveParentId(anchorLevel),
        },
        classes: "alt-group",
      });

      sortedNodes.forEach((node) => {
        const visuals = getNodeVisual(node);
        const nodeId = String(node.id);
        const effectiveLevelKey = resolveEffectiveLevelKey(
          nodeId,
          nodeLevelKeyById,
          groupLevelKeyById
        );
        const nodeTargetLevel =
          typeof effectiveLevelKey === "number"
            ? undefined
            : minTargetLevel(targetLevelsBySource, nodeId);
        const nodeAnchorLevel =
          typeof effectiveLevelKey === "number"
            ? effectiveLevelKey
            : (resolveAnchorLevel(nodeTargetLevel, levels) ?? anchorLevel);
        const nodePartitionLevel =
          typeof nodeAnchorLevel === "number"
            ? nodeAnchorLevel
            : effectiveLevelKey;
        const nodePartition = levelKeyToPartition(nodePartitionLevel);
        const nodeClasses =
          node.is_in_curriculum !== false ? "" : "is-outside-curriculum";
        elements.push({
          group: "nodes",
          data: {
            id: nodeId,
            label: String(node.label || node.id),
            title: String(node.title || node.label || node.id),
            shape: visuals.shape,
            borderColor: String(node.color || "#6c757d"),
            isInCurriculum: node.is_in_curriculum !== false,
            levelKey: effectiveLevelKey,
            partition: nodePartition,
            parent: groupId,
            width: visuals.width,
            height: visuals.height,
            labelOffsetY: visuals.labelOffsetY,
          },
          classes: nodeClasses,
        });
      });
    });

    for (const node of nodes) {
      if (typeof node.group_number === "number" && node.group_number > 0) {
        continue;
      }
      const visuals = getNodeVisual(node);
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
          shape: visuals.shape,
          borderColor: String(node.color || "#6c757d"),
          isInCurriculum: node.is_in_curriculum !== false,
          levelKey,
          partition,
          parent: resolveParentId(anchorLevel),
          width: visuals.width,
          height: visuals.height,
          labelOffsetY: visuals.labelOffsetY,
        },
        classes: nodeClasses,
      });
    }

    let edgeIndex = 0;
    const edgeKeys = new Set<string>();
    for (const link of links) {
      const source = String(link.source);
      const target = String(link.target);
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

  /** Build adjacency and element indexes for ancestor highlighting. */
  const buildGraphIndex = (elements: CyElementT[]): GraphIndexT => {
    const nodeIds: string[] = [];
    const edgeIds: string[] = [];
    const incomingByTarget = new Map<string, Set<string>>();
    const edgeIdByKey = new Map<string, string>();

    elements.forEach((element) => {
      if (element.group === "nodes") {
        nodeIds.push(String(element.data.id));
        return;
      }
      const source = String(element.data.source);
      const target = String(element.data.target);
      edgeIds.push(String(element.data.id));
      if (!incomingByTarget.has(target)) {
        incomingByTarget.set(target, new Set());
      }
      incomingByTarget.get(target)?.add(source);
      edgeIdByKey.set(`${source}|${target}`, String(element.data.id));
    });

    return { nodeIds, edgeIds, incomingByTarget, edgeIdByKey };
  };

  /** Collect ancestor nodes + edges for a selected node. */
  const collectAncestors = (
    startId: string,
    index: GraphIndexT
  ): { nodes: Set<string>; edges: Set<string> } => {
    const nodes = new Set<string>();
    const edges = new Set<string>();
    const visited = new Set<string>([startId]);
    const stack = [startId];

    while (stack.length) {
      const current = stack.pop() as string;
      const parents = index.incomingByTarget.get(current);
      if (!parents) {
        continue;
      }
      parents.forEach((parentId) => {
        nodes.add(parentId);
        const edgeId = index.edgeIdByKey.get(`${parentId}|${current}`);
        if (edgeId) {
          edges.add(edgeId);
        }
        if (!visited.has(parentId)) {
          visited.add(parentId);
          stack.push(parentId);
        }
      });
    }

    return { nodes, edges };
  };

  /** Clear any ancestor highlighting. */
  const clearHighlight = (): void => {
    if (!cy || !graphIndex) {
      return;
    }
    graphIndex.nodeIds.forEach((nodeId) => {
      const element = cy?.getElementById(nodeId);
      element?.removeClass("is-ancestor");
      element?.removeClass("is-selected");
    });
    graphIndex.edgeIds.forEach((edgeId) => {
      const element = cy?.getElementById(edgeId);
      element?.removeClass("is-ancestor");
    });
  };

  /** Highlight the ancestors of a node in the graph. */
  const highlightAncestors = (nodeId: string): void => {
    if (!cy || !graphIndex) {
      return;
    }
    clearHighlight();
    const { nodes, edges } = collectAncestors(nodeId, graphIndex);
    nodes.forEach((ancestorId) => {
      const element = cy?.getElementById(ancestorId);
      element?.addClass("is-ancestor");
    });
    edges.forEach((edgeId) => {
      const element = cy?.getElementById(edgeId);
      element?.addClass("is-ancestor");
    });
    const selected = cy?.getElementById(nodeId);
    selected?.addClass("is-selected");
  };

  /** Default Cytoscape stylesheet (kept in JS to avoid CSS specificity fights). */
  const buildStyles = (): unknown[] => [
    {
      selector: "node",
      style: {
        shape: "data(shape)",
        width: "data(width)",
        height: "data(height)",
        "background-color": "#ffffff",
        "border-width": 2,
        "border-color": "data(borderColor)",
        "border-style": "solid",
        label: "data(label)",
        color: "#212529",
        "font-size": 12,
        "text-margin-y": "data(labelOffsetY)",
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
        "border-color": "#ced4da",
        "border-style": "solid",
        padding: 16,
        "text-valign": "top",
        "text-halign": "center",
        "text-margin-y": 6,
        "font-size": 12,
        "font-weight": 600,
        color: "#134529",
        "text-wrap": "wrap",
        "text-max-width": 140,
        "compound-sizing-wrt-labels": "include",
      },
    },
    {
      selector: "node.alt-group",
      style: {
        shape: "round-rectangle",
        "background-color": "data(bandColor)",
        "background-opacity": "data(bandOpacity)",
        "border-width": 1,
        "border-color": "#ced4da",
        "border-style": "dashed",
        padding: 12,
        "text-valign": "top",
        "text-halign": "center",
        "text-margin-y": 6,
        "font-size": 11,
        "font-weight": 600,
        color: "#134529",
        "text-wrap": "wrap",
        "text-max-width": 140,
        "compound-sizing-wrt-labels": "include",
      },
    },
    {
      selector: "node.year-group",
      style: {
        shape: "round-rectangle",
        "background-color": "data(bandColor)",
        "background-opacity": "data(bandOpacity)",
        "border-width": 1.5,
        "border-color": "#ced4da",
        "border-style": "solid",
        padding: 26,
        "text-valign": "top",
        "text-halign": "center",
        "text-margin-y": 6,
        "font-size": 14,
        "font-weight": 700,
        color: "#134529",
        "text-wrap": "wrap",
        "text-max-width": 160,
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
      selector: "node.is-ancestor",
      style: {
        "border-color": "#0d6efd",
        "border-width": 3,
        "shadow-color": "#0d6efd",
        "shadow-opacity": 0.25,
        "shadow-blur": 12,
      },
    },
    {
      selector: "node.is-selected",
      style: {
        "border-color": "#0d6efd",
        "border-width": 3,
        "shadow-color": "#0d6efd",
        "shadow-opacity": 0.4,
        "shadow-blur": 18,
      },
    },
    {
      selector: "node.is-hidden",
      style: {
        display: "none",
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
    {
      selector: "edge.is-ancestor",
      style: {
        width: 2.4,
        "line-color": "#0d6efd",
        "target-arrow-color": "#0d6efd",
      },
    },
    {
      selector: "edge.is-hidden",
      style: {
        display: "none",
      },
    },
  ];

  /** Resolve the crossing strategy so parent/child graphs stay consistent. */
  const getCrossingStrategy = (): string => {
    return "LAYER_SWEEP";
  };

  /** Run the ELK layered layout with compound semester parents. */
  const buildElkOptions = (): Record<string, unknown> => {
    const crossingStrategy = getCrossingStrategy();
    const baseOptions: Record<string, unknown> = {
      algorithm: "layered",
      "elk.direction": "RIGHT",
      "elk.partitioning.activate": true,
      "elk.hierarchyHandling": "INCLUDE_CHILDREN",
      // Default spacing for course graphs.
      "elk.spacing.nodeNode": 30,
      "elk.spacing.edgeNode": 18,
      "elk.spacing.edgeEdge": 12,
      "elk.layered.spacing.nodeNodeBetweenLayers": 70,
      "elk.layered.spacing.edgeNodeBetweenLayers": 0,
      "elk.layered.spacing.edgeEdgeBetweenLayers": 0,
      // Reduce edge crossings where possible (default is already good).
      "elk.layered.crossingMinimization.strategy": crossingStrategy,
      "elk.layered.nodePlacement.strategy": "BRANDES_KOEPF",
    };

    return baseOptions;
  };

  /** Build an ELK graph JSON payload from the Cytoscape elements. */
  const buildElkGraph = (elements: CyElementT[]): ElkGraphT => {
    const nodeMap = new Map<string, ElkNodeT>();
    const childrenByParent = new Map<string, ElkNodeT[]>();
    const rootChildren: ElkNodeT[] = [];

    elements.forEach((element) => {
      if (element.group !== "nodes") {
        return;
      }
      const data = element.data;
      const nodeId = String(data.id);
      const labelText = data.label ? String(data.label) : nodeId;
      const isParent = Boolean((data as CyParentDataT).isParent);
      const elkNode: ElkNodeT = {
        id: nodeId,
        labels: [{ text: labelText }],
        properties: data.partition
          ? { "elk.partitioning.partition": String(data.partition) }
          : undefined,
      };
      if (typeof (data as CyNodeDataT).width === "number") {
        elkNode.width = (data as CyNodeDataT).width;
      } else {
        elkNode.width = isParent ? 180 : 110;
      }
      if (typeof (data as CyNodeDataT).height === "number") {
        elkNode.height = (data as CyNodeDataT).height;
      } else {
        elkNode.height = isParent ? 120 : 44;
      }
      nodeMap.set(nodeId, elkNode);
      const parentId = data.parent ? String(data.parent) : null;
      if (parentId) {
        if (!childrenByParent.has(parentId)) {
          childrenByParent.set(parentId, []);
        }
        childrenByParent.get(parentId)?.push(elkNode);
      } else {
        rootChildren.push(elkNode);
      }
    });

    childrenByParent.forEach((children, parentId) => {
      const parent = nodeMap.get(parentId);
      if (parent) {
        parent.children = children;
      } else {
        rootChildren.push(...children);
      }
    });

    const edges: ElkEdgeT[] = [];
    elements.forEach((element) => {
      if (element.group !== "edges") {
        return;
      }
      edges.push({
        id: String(element.data.id),
        sources: [String(element.data.source)],
        targets: [String(element.data.target)],
      });
    });

    return {
      id: "prereq-graph",
      layoutOptions: buildElkOptions(),
      children: rootChildren,
      edges,
    };
  };

  /** Download the ELK JSON payload using a temporary Blob URL. */
  const downloadElkJson = (): void => {
    const elements =
      cachedElements || (cachedPayload ? buildElements(cachedPayload) : null);
    if (!elements) {
      showError("Unable to export ELK JSON: graph data is missing.");
      return;
    }
    const elkGraph = buildElkGraph(elements);
    const blob = new Blob([JSON.stringify(elkGraph, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = "prereq_graph_elk.json";
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
  };

  const buildNonCurriculumElements = (): {
    nodes: CyNodeElementT[];
    edges: CyEdgeElementT[];
  } => {
    if (!cachedElements) {
      return { nodes: [], edges: [] };
    }
    const nodes = cachedElements.filter(
      (element): element is CyNodeElementT =>
        element.group === "nodes" &&
        Boolean(element.classes?.includes("is-outside-curriculum"))
    );
    const nodeIds = new Set(nodes.map((node) => String(node.data.id)));
    const edges = cachedElements.filter(
      (element): element is CyEdgeElementT =>
        element.group === "edges" &&
        (nodeIds.has(String(element.data.source)) ||
          nodeIds.has(String(element.data.target)))
    );
    return { nodes, edges };
  };

  const hideNonCurriculum = (): void => {
    if (!cy || nonCurriculumHidden) {
      return;
    }
    const { nodes, edges } = buildNonCurriculumElements();
    edges.forEach((edge) => {
      cy?.getElementById(String(edge.data.id))?.remove();
    });
    nodes.forEach((node) => {
      cy?.getElementById(String(node.data.id))?.remove();
    });
    nonCurriculumHidden = true;
  };

  const showNonCurriculumNodes = (): void => {
    if (!cy || !nonCurriculumHidden) {
      return;
    }
    const { nodes, edges } = buildNonCurriculumElements();
    cy.add([...nodes, ...edges]);
    nonCurriculumHidden = false;
  };

  const applyNonCurriculumVisibility = (show: boolean): void => {
    if (show) {
      showNonCurriculumNodes();
    } else {
      hideNonCurriculum();
    }
    if (cy) {
      runElkLayout();
    }
  };

  const updateNonCurriculumButton = (): void => {
    if (!toggleNonCurriculumButton) {
      return;
    }
    toggleNonCurriculumButton.textContent = showNonCurriculum
      ? "Hide non-curriculum"
      : "Show non-curriculum";
  };

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
            // Keep crossing minimization strategy aligned with the root graph.
            "elk.layered.crossingMinimization.strategy": getCrossingStrategy(),
          };
        },
        elk: {
          ...buildElkOptions(),
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
    cachedElements = elements;
    graphIndex = buildGraphIndex(elements);

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
    cy.on("tap", "node", (event) => {
      const isParent = Boolean(event.target.data("isParent"));
      if (isParent) {
        return;
      }
      const nodeId = String(event.target.data("id") || "");
      if (nodeId) {
        highlightAncestors(nodeId);
      }
    });

    runElkLayout();
    applyNonCurriculumVisibility(showNonCurriculum);
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

  if (downloadElkButton) {
    downloadElkButton.addEventListener("click", () => {
      downloadElkJson();
    });
  }

  if (toggleNonCurriculumButton) {
    updateNonCurriculumButton();
    toggleNonCurriculumButton.addEventListener("click", () => {
      showNonCurriculum = !showNonCurriculum;
      applyNonCurriculumVisibility(showNonCurriculum);
      updateNonCurriculumButton();
    });
  }

  void loadAndRender();
})();

// Layout switcher for prerequisite graph views (force, DAG, ELK).
// Keeps the toggle logic separate from each renderer and uses localStorage
// so layout choice persists between page loads.
(function () {
  "use strict";

  type LayoutModeT = "force" | "dag" | "elk";

  const layoutModeKey = "prereq-graph-layout-mode";
  const legacyLayoutKey = "prereq-graph-layout";

  const layoutSelect = document.getElementById(
    "layout-select"
  ) as HTMLSelectElement | null;
  const graphD3 = document.getElementById("graph-d3") as SVGSVGElement | null;
  const graphElk = document.getElementById("graph-elk") as HTMLElement | null;

  if (!layoutSelect) {
    return;
  }

  /** Parse the saved layout mode or fall back to a sensible default. */
  const getStoredMode = (): LayoutModeT => {
    const stored = localStorage.getItem(layoutModeKey);
    if (stored === "force" || stored === "dag" || stored === "elk") {
      return stored;
    }
    const legacy = localStorage.getItem(legacyLayoutKey);
    if (legacy === "force" || legacy === "dag") {
      return legacy;
    }
    return "elk";
  };

  /** Persist the chosen mode and keep legacy force/dag preference in sync. */
  const storeMode = (mode: LayoutModeT): void => {
    localStorage.setItem(layoutModeKey, mode);
    if (mode === "force" || mode === "dag") {
      localStorage.setItem(legacyLayoutKey, mode);
    }
  };

  /** Toggle visibility of the two graph containers. */
  const applyVisibility = (mode: LayoutModeT): void => {
    if (graphD3) {
      graphD3.classList.toggle("is-hidden", mode === "elk");
    }
    if (graphElk) {
      graphElk.classList.toggle("is-hidden", mode !== "elk");
    }
  };

  const initialMode = getStoredMode();
  storeMode(initialMode);
  layoutSelect.value = initialMode;
  applyVisibility(initialMode);

  // Notify viewers on change so they can re-render in the new mode.
  layoutSelect.addEventListener("change", () => {
    const raw = layoutSelect.value;
    const mode = raw === "dag" || raw === "force" ? raw : "elk";
    storeMode(mode);
    applyVisibility(mode);
    window.dispatchEvent(
      new CustomEvent("prereq-layout-change", { detail: { mode } })
    );
  });
})();

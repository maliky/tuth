// Layout switcher for prerequisite graph views (ELK standard + ELK compound).
// Keeps the toggle logic separate from each renderer and uses localStorage
// so layout choice persists between page loads.
(function () {
  "use strict";

  type LayoutModeT = "elk" | "elk-compound";

  const layoutModeKey = "prereq-graph-layout-mode";
  const layoutSelect = document.getElementById(
    "layout-select"
  ) as HTMLSelectElement | null;
  const graphElk = document.getElementById("graph-elk") as HTMLElement | null;
  const graphElkCompound = document.getElementById(
    "graph-elk-compound"
  ) as HTMLElement | null;

  if (!layoutSelect) {
    return;
  }

  /** Parse the saved layout mode or fall back to a sensible default. */
  const getStoredMode = (): LayoutModeT => {
    const stored = localStorage.getItem(layoutModeKey);
    if (stored === "elk" || stored === "elk-compound") {
      return stored;
    }
    return "elk";
  };

  /** Persist the chosen mode and keep legacy force/dag preference in sync. */
  const storeMode = (mode: LayoutModeT): void => {
    localStorage.setItem(layoutModeKey, mode);
  };

  /** Toggle visibility of the two ELK graph containers. */
  const applyVisibility = (mode: LayoutModeT): void => {
    if (graphElk) {
      graphElk.classList.toggle("is-hidden", mode !== "elk");
    }
    if (graphElkCompound) {
      graphElkCompound.classList.toggle("is-hidden", mode !== "elk-compound");
    }
  };

  const initialMode = getStoredMode();
  storeMode(initialMode);
  layoutSelect.value = initialMode;
  applyVisibility(initialMode);

  // Notify viewers on change so they can re-render in the new mode.
  layoutSelect.addEventListener("change", () => {
    const raw = layoutSelect.value;
    const mode = raw === "elk-compound" ? "elk-compound" : "elk";
    storeMode(mode);
    applyVisibility(mode);
    window.dispatchEvent(
      new CustomEvent("prereq-layout-change", { detail: { mode } })
    );
  });
})();

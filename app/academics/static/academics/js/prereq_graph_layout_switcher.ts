// Layout switcher for prerequisite graph views (ELK standard + ELK compound).
// Keeps the toggle logic separate from each renderer and uses localStorage
// so layout choice persists between page loads.
(function () {
  "use strict";

  type LayoutModeT = "elk" | "elk-compound";
  type LayoutTuningT = "balanced" | "min-crossings" | "straight-edges";

  const layoutModeKey = "prereq-graph-layout-mode";
  const layoutTuningKey = "prereq-graph-layout-tuning";
  const layoutSelect = document.getElementById(
    "layout-select"
  ) as HTMLSelectElement | null;
  const layoutTuningSelect = document.getElementById(
    "layout-tuning"
  ) as HTMLSelectElement | null;
  const graphElk = document.getElementById("graph-elk") as HTMLElement | null;
  const graphElkCompound = document.getElementById(
    "graph-elk-compound"
  ) as HTMLElement | null;

  /** Parse the saved layout mode or fall back to a sensible default. */
  const getStoredMode = (): LayoutModeT => {
    const stored = localStorage.getItem(layoutModeKey);
    if (stored === "elk-compound") {
      return stored;
    }
    return "elk-compound";
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

  if (layoutSelect) {
    const initialMode = getStoredMode();
    storeMode(initialMode);
    layoutSelect.value = initialMode;
    applyVisibility(initialMode);
  } else {
    storeMode("elk-compound");
    applyVisibility("elk-compound");
  }

  /** Parse the saved layout tuning or fall back to a sensible default. */
  const getStoredTuning = (): LayoutTuningT => {
    const stored = localStorage.getItem(layoutTuningKey);
    if (
      stored === "balanced" ||
      stored === "min-crossings" ||
      stored === "straight-edges"
    ) {
      return stored;
    }
    return "balanced";
  };

  /** Persist the chosen tuning preset. */
  const storeTuning = (tuning: LayoutTuningT): void => {
    localStorage.setItem(layoutTuningKey, tuning);
  };

  if (layoutTuningSelect) {
    const initialTuning = getStoredTuning();
    storeTuning(initialTuning);
    layoutTuningSelect.value = initialTuning;
    layoutTuningSelect.addEventListener("change", () => {
      const raw = layoutTuningSelect.value;
      const tuning =
        raw === "min-crossings" || raw === "straight-edges" ? raw : "balanced";
      storeTuning(tuning);
      window.dispatchEvent(
        new CustomEvent("prereq-layout-tuning-change", {
          detail: { tuning },
        })
      );
    });
  }

  // Notify viewers on change so they can re-render in the new mode.
  if (layoutSelect) {
    layoutSelect.addEventListener("change", () => {
      const raw = layoutSelect.value;
      const mode = raw === "elk-compound" ? "elk-compound" : "elk";
      storeMode(mode);
      applyVisibility(mode);
      window.dispatchEvent(
        new CustomEvent("prereq-layout-change", { detail: { mode } })
      );
    });
  }
})();

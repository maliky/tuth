/* Global changelist filter toggle for admin list pages. */
(function () {
  const STORAGE_KEY = "tusis_admin_filters_collapsed";

  function getChangelist() {
    return document.querySelector("#changelist");
  }

  function getFilterNav() {
    return document.querySelector("#changelist-filter");
  }

  function applyCollapsedState(collapsed) {
    const changelist = getChangelist();
    const toggleBtn = document.querySelector("#tusis-filter-toggle");
    if (!changelist || !toggleBtn) {
      return;
    }
    changelist.classList.toggle("tusis-filters-collapsed", collapsed);
    toggleBtn.setAttribute("aria-expanded", collapsed ? "false" : "true");
    toggleBtn.textContent = collapsed ? "Show filters" : "Hide filters";
  }

  function createToggleButton() {
    const contentMain = document.querySelector("#content-main");
    const changelist = getChangelist();
    if (!contentMain || !changelist || document.querySelector("#tusis-filter-toggle")) {
      return;
    }

    const button = document.createElement("button");
    button.type = "button";
    button.id = "tusis-filter-toggle";
    button.className = "button";

    button.addEventListener("click", function () {
      const changelistNode = getChangelist();
      if (!changelistNode) {
        return;
      }
      const isCollapsed = !changelistNode.classList.contains("tusis-filters-collapsed");
      applyCollapsedState(isCollapsed);
      try {
        window.localStorage.setItem(STORAGE_KEY, isCollapsed ? "1" : "0");
      } catch {
        // Ignore localStorage failures and keep the in-page behavior.
      }
    });

    contentMain.insertBefore(button, changelist);
  }

  document.addEventListener("DOMContentLoaded", function () {
    if (!document.body.classList.contains("change-list")) {
      return;
    }
    if (!getFilterNav()) {
      return;
    }

    createToggleButton();

    let collapsed = false;
    try {
      collapsed = window.localStorage.getItem(STORAGE_KEY) === "1";
    } catch {
      collapsed = false;
    }
    applyCollapsedState(collapsed);
  });
})();


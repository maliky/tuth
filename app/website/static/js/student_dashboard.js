(function () {
  const cartPanel = document.querySelector("[data-cart-list]");
  if (!cartPanel) return;

  const cartItemsContainer = cartPanel.querySelector("[data-cart-items]");
  const creditRemainingEl = cartPanel.querySelector("[data-credit-selected]");
  const creditLimitEl = cartPanel.querySelector("[data-credit-limit]");
  const creditWarningEl = cartPanel.querySelector("[data-credit-warning]");
  const feeEstimateEl = cartPanel.querySelector("[data-fee-estimate]");
  const registerSubmitBtn = cartPanel.querySelector("[data-register-submit]");
  const selectedSectionsInput = cartPanel.querySelector(
    "[data-selected-sections]"
  );

  let baseCredits = Number(cartPanel.dataset.creditsSelected || "0");
  let maxCredits = Number(cartPanel.dataset.creditsMax || "0");
  const currency = cartPanel.dataset.currency || "USD";

  const cart = new Map();

  const formatCurrency = (value) =>
    `${currency} ${Number(value).toFixed(2)}`;

  const formatCredits = (value) => value.toFixed(1).replace(".0", "");

  const updateLimitUI = (creditsSelected) => {
    if (creditWarningEl) {
      const overLimit = maxCredits > 0 && creditsSelected > maxCredits;
      creditWarningEl.classList.toggle("d-none", !overLimit);
      if (registerSubmitBtn instanceof HTMLButtonElement) {
        registerSubmitBtn.disabled = overLimit;
      }
    }
  };

  const renderCart = () => {
    if (!cartItemsContainer) return;

    cartItemsContainer.innerHTML = "";
    if (cart.size === 0) {
      cartItemsContainer.innerHTML =
        '<p class="text-muted small mb-0">Select a section to start.</p>';
    } else {
      cart.forEach((item, key) => {
        const div = document.createElement("div");
        div.className = "cart-item";
        div.dataset.key = key;
        div.innerHTML = `
          <div class="d-flex justify-content-between">
            <div>
              <strong>${item.courseCode}</strong>
              <p class="mb-0 text-muted small">${item.sectionLabel} · ${item.schedule}</p>
            </div>
            <div class="text-end">
              <p class="mb-0">${item.credits} cr</p>
              <p class="mb-0 text-muted small">${formatCurrency(item.fee)}</p>
            </div>
          </div>
          <button type="button" class="btn btn-link btn-sm text-danger p-0 mt-2" data-remove="${key}">
            Remove
          </button>
        `;
        cartItemsContainer.appendChild(div);
      });
    }

    let creditsUsed = 0;
    let feeTotal = 0;
    cart.forEach((item) => {
      creditsUsed += Number(item.credits);
      feeTotal += Number(item.fee);
    });

    const creditsSelected = baseCredits + creditsUsed;

    if (creditRemainingEl) {
      creditRemainingEl.textContent = formatCredits(creditsSelected);
    }

    if (creditLimitEl) {
      creditLimitEl.textContent = formatCredits(maxCredits);
    }

    updateLimitUI(creditsSelected);

    if (feeEstimateEl) {
      feeEstimateEl.textContent = feeTotal.toFixed(2);
    }

    if (selectedSectionsInput) {
      const sectionIds = Array.from(cart.values()).map((item) => item.sectionId);
      selectedSectionsInput.value = sectionIds.join(",");
    }
  };

  const resetCart = () => {
    cart.clear();
    document.querySelectorAll(".section-picker").forEach((select) => {
      if (select instanceof HTMLSelectElement) {
        select.value = "";
      }
    });
    renderCart();
  };

  document.addEventListener("change", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLSelectElement)) return;
    if (!target.classList.contains("section-picker")) return;

    const selectedOption = target.selectedOptions[0];
    if (!selectedOption || !selectedOption.value) {
      const key = target.dataset.courseCode;
      if (key && cart.has(key)) {
        cart.delete(key);
        renderCart();
      }
      return;
    }

    const payload = {
      courseCode: target.dataset.courseCode || selectedOption.value,
      courseTitle: target.dataset.courseTitle || "",
      credits: target.dataset.credits || selectedOption.dataset.credits || "0",
      sectionId: selectedOption.value,
      sectionLabel: selectedOption.dataset.sectionLabel || "",
      schedule: selectedOption.dataset.schedule || "",
      fee: selectedOption.dataset.fee || "0",
    };

    cart.set(payload.courseCode, payload);
    renderCart();
  });

  document.addEventListener("click", (event) => {
    const button = event.target;
    if (!(button instanceof HTMLElement)) return;
    const removeKey = button.dataset.remove;
    if (removeKey && cart.has(removeKey)) {
      cart.delete(removeKey);
      const select = document.querySelector(
        `.section-picker[data-course-code="${removeKey}"]`
      );
      if (select instanceof HTMLSelectElement) {
        select.value = "";
      }
      renderCart();
    }
  });

  const courseTableContainer = document.querySelector("[data-course-table]");
  const courseListContainer = document.querySelector("[data-course-list]");

  const submitAjaxForm = (form) => {
    if (!(form instanceof HTMLFormElement)) return;
    const formData = new FormData(form);
    fetch(form.action || window.location.href, {
      method: form.method || "POST",
      headers: { "X-Requested-With": "XMLHttpRequest" },
      credentials: "same-origin",
      body: formData,
    })
      .then((response) =>
        response.json().then((data) => ({ ok: response.ok, data }))
      )
      .then((payload) => {
        if (!payload.ok) {
          const message = payload.data && payload.data.message;
          if (message) {
            window.alert(message);
          }
          return;
        }
        const fragments = payload.data.fragments || {};
        if (courseTableContainer && fragments.course_table) {
          courseTableContainer.innerHTML = fragments.course_table;
        }
        if (courseListContainer && fragments.course_list) {
          courseListContainer.innerHTML = fragments.course_list;
        }
        if (payload.data.registration_limits) {
          baseCredits = Number(
            payload.data.registration_limits.credits_selected || "0"
          );
          maxCredits = Number(
            payload.data.registration_limits.credits_max || maxCredits || "0"
          );
        }
        resetCart();
      })
      .catch(() => {
        form.submit();
      });
  };

  document.addEventListener("submit", (event) => {
    const form = event.target;
    if (!(form instanceof HTMLFormElement)) return;
    if (!form.dataset.ajax) return;
    event.preventDefault();
    submitAjaxForm(form);
  });

  renderCart();
})();

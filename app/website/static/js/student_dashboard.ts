(function () {
  type CartItemT = {
    courseCode: string;
    courseTitle: string;
    credits: string;
    sectionId: string;
    sectionLabel: string;
    schedule: string;
    fee: string;
  };

  type AjaxFragmentsT = {
    course_table?: string;
    course_list?: string;
  };

  type RegistrationLimitsT = {
    credits_selected?: string | number;
    credits_max?: string | number;
  };

  type AjaxResponseT = {
    message?: string;
    fragments?: AjaxFragmentsT;
    registration_limits?: RegistrationLimitsT;
  };

  type AjaxPayloadT = {
    ok: boolean;
    data: AjaxResponseT;
  };

  const cartPanel = document.querySelector<HTMLElement>("[data-cart-list]");
  if (!cartPanel) return;

  const cartItemsContainer =
    cartPanel.querySelector<HTMLElement>("[data-cart-items]");
  const creditRemainingEl = cartPanel.querySelector<HTMLElement>(
    "[data-credit-selected]"
  );
  const creditLimitEl = cartPanel.querySelector<HTMLElement>(
    "[data-credit-limit]"
  );
  const creditSelectedRow = cartPanel.querySelector<HTMLElement>(
    "[data-credits-selected-row]"
  );
  const creditWarningEl = cartPanel.querySelector<HTMLElement>(
    "[data-credit-warning]"
  );
  const feeEstimateEl = cartPanel.querySelector<HTMLElement>(
    "[data-fee-estimate]"
  );
  const registerSubmitBtn = cartPanel.querySelector<HTMLButtonElement>(
    "[data-register-submit]"
  );
  const selectedSectionsInput = cartPanel.querySelector<HTMLInputElement>(
    "[data-selected-sections]"
  );

  let baseCredits = Number(cartPanel.dataset.creditsSelected || "0");
  let maxCredits = Number(cartPanel.dataset.creditsMax || "0");
  const currency = cartPanel.dataset.currency || "USD";

  const cart = new Map<string, CartItemT>();

  const formatCurrency = (value: number | string): string =>
    `${currency} ${Number(value).toFixed(2)}`;

  const formatCredits = (value: number): string =>
    value.toFixed(1).replace(".0", "");

  const updateLimitUI = (creditsSelected: number): void => {
    if (creditWarningEl) {
      const overLimit = maxCredits > 0 && creditsSelected > maxCredits;
      creditWarningEl.classList.toggle("d-none", !overLimit);
      if (registerSubmitBtn instanceof HTMLButtonElement) {
        registerSubmitBtn.disabled = overLimit;
      }
    }
  };

  const renderCart = (): void => {
    if (!cartItemsContainer) return;

    cartItemsContainer.innerHTML = "";
    if (cart.size === 0) {
      cartItemsContainer.innerHTML =
        '<p class="text-muted small mb-0">Select a section to start.</p>';
      if (creditSelectedRow) {
        creditSelectedRow.classList.add("d-none");
      }
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
      if (creditSelectedRow) {
        creditSelectedRow.classList.remove("d-none");
      }
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
      const remaining = Math.max(maxCredits - creditsSelected, 0);
      creditLimitEl.textContent = formatCredits(remaining);
    }

    updateLimitUI(creditsSelected);

    if (feeEstimateEl) {
      feeEstimateEl.textContent = feeTotal.toFixed(2);
    }

    if (selectedSectionsInput) {
      const sectionIds = Array.from(cart.values()).map(
        (item) => item.sectionId
      );
      selectedSectionsInput.value = sectionIds.join(",");
    }
  };

  const resetCart = (): void => {
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

    const payload: CartItemT = {
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

  const courseTableContainer = document.querySelector<HTMLElement>(
    "[data-course-table]"
  );
  const courseListContainer =
    document.querySelector<HTMLElement>("[data-course-list]");

  const submitAjaxForm = (form: HTMLFormElement): void => {
    const formData = new FormData(form);
    // Normalize the AJAX response so downstream code stays typed.
    const parseAjaxResponse = async (
      response: Response
    ): Promise<AjaxPayloadT> => {
      const data = (await response.json()) as AjaxResponseT;
      return { ok: response.ok, data };
    };

    fetch(form.action || window.location.href, {
      method: form.method || "POST",
      headers: { "X-Requested-With": "XMLHttpRequest" },
      credentials: "same-origin",
      body: formData,
    })
      .then(parseAjaxResponse)
      .then((payload) => {
        if (!payload.ok) {
          const message = payload.data.message;
          if (message) {
            window.alert(message);
          }
          return;
        }
        const fragments = payload.data.fragments;
        if (courseTableContainer && fragments?.course_table) {
          courseTableContainer.innerHTML = fragments.course_table;
        }
        if (courseListContainer && fragments?.course_list) {
          courseListContainer.innerHTML = fragments.course_list;
        }
        const limits = payload.data.registration_limits;
        if (limits) {
          baseCredits = Number(limits.credits_selected || "0");
          maxCredits = Number(limits.credits_max || maxCredits || "0");
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

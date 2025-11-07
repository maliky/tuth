(function () {
  const cartPanel = document.querySelector("[data-cart-list]");
  if (!cartPanel) return;

  const cartItemsContainer = cartPanel.querySelector("[data-cart-items]");
  const creditRemainingEl = cartPanel.querySelector("[data-credit-remaining]");
  const feeEstimateEl = cartPanel.querySelector("[data-fee-estimate]");

  const initialCredits = Number(cartPanel.dataset.creditsRemaining || "0");
  const currency = cartPanel.dataset.currency || "USD";

  const cart = new Map();

  const formatCurrency = (value) =>
    `${currency} ${Number(value).toFixed(2)}`;

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

    const creditsRemaining = Math.max(initialCredits - creditsUsed, 0);

    if (creditRemainingEl) {
      creditRemainingEl.textContent = creditsRemaining.toFixed(1).replace(".0", "");
      if (creditsRemaining <= 0) {
        creditRemainingEl.classList.add("text-danger");
      } else {
        creditRemainingEl.classList.remove("text-danger");
      }
    }

    if (feeEstimateEl) {
      feeEstimateEl.textContent = feeTotal.toFixed(2);
    }
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
})();

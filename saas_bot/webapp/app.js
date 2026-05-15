/* Telegram Mini App for the order flow.
 * Screens: main (categories+products) -> addr -> cart -> checkout.
 * Telegram's native BackButton is synced to whichever screen is on top.
 */
(() => {
  const tg = window.Telegram?.WebApp;
  if (tg) { tg.ready(); tg.expand(); }

  // ----- Launch params ---------------------------------------------------
  const url = new URL(window.location.href);
  const startParam = tg?.initDataUnsafe?.start_param || "";
  const tenantId = startParam || url.searchParams.get("tenant") || "tenant_001";
  const initData = tg?.initData || "";
  // Fallback user id from URL (bot passes ?uid=...) when initData is missing.
  const fallbackUid = parseInt(url.searchParams.get("uid") || "0") || null;
  // 'extend mode' — adding items to an existing pending order rather than
  // placing a new one.
  const extendOrderId = parseInt(url.searchParams.get("extend") || "0") || null;

  // ----- State -----------------------------------------------------------
  const state = {
    menu: null,
    activeCategory: null,
    cart: {},                 // {pid: qty}
    address: "",
    addressLat: null,
    addressLon: null,
    deliveryType: "delivery",
    branchId: null,
    paymentMethod: "cash",
    promo: null,   // {code, discount, label} | null
  };

  // Stack of currently open overlay screens. Top of stack = current.
  // Telegram BackButton pops the top.
  const screenStack = [];

  // ----- Helpers ---------------------------------------------------------
  const T = window.T || ((k, f) => f != null ? f : k);
  const tfmt = (key, vars) => {
    let s = T(key);
    for (const [k, v] of Object.entries(vars || {})) s = s.replace("{" + k + "}", v);
    return s;
  };
  const $ = (id) => document.getElementById(id);
  const fmt = (n) => new Intl.NumberFormat("uz-UZ").format(n) + " " + T("soum");
  const cartCount = () => Object.values(state.cart).reduce((a, b) => a + b, 0);
  function cartTotal() {
    let t = 0;
    for (const [pid, qty] of Object.entries(state.cart)) {
      const p = findProduct(parseInt(pid));
      if (p) t += (p.price_value || 0) * qty;
    }
    return t;
  }
  function findProduct(pid) {
    if (!state.menu) return null;
    for (const items of Object.values(state.menu.products)) {
      const p = items.find(x => x.id === pid);
      if (p) return p;
    }
    return null;
  }
  function escapeHtml(s) {
    return String(s).replace(/[&<>"']/g, c => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
    }[c]));
  }

  // ----- Screen management ----------------------------------------------
  function openScreen(id) {
    $(id).classList.remove("hidden");
    screenStack.push(id);
    syncBackButton();
  }
  function closeScreen(id) {
    $(id).classList.add("hidden");
    const idx = screenStack.lastIndexOf(id);
    if (idx >= 0) screenStack.splice(idx, 1);
    syncBackButton();
  }
  function syncBackButton() {
    if (!tg?.BackButton) return;
    if (screenStack.length > 0) {
      tg.BackButton.show();
    } else {
      tg.BackButton.hide();
    }
  }
  if (tg?.BackButton) {
    tg.BackButton.onClick(() => {
      const top = screenStack[screenStack.length - 1];
      if (top) closeScreen(top);
    });
  }

  // ----- Load menu -------------------------------------------------------
  async function loadMenu() {
    try {
      const r = await fetch(`/api/menu?tenant=${encodeURIComponent(tenantId)}`);
      if (!r.ok) throw new Error("Menu yuklanmadi");
      state.menu = await r.json();
      state.activeCategory = state.menu.categories[0] || null;
      renderTabs();
      renderProducts();
      populateBranches();
      // Set up extend mode and the saved-address prompt after menu is ready.
      if (extendOrderId) {
        $("extendBanner").classList.remove("hidden");
        $("extendOrderId").textContent = extendOrderId;
      } else {
        await maybeShowAddressConfirm();
      }
    } catch (e) {
      $("content").innerHTML = `<div class="err">⚠️ ${e.message}</div>`;
    }
  }

  // ----- Saved-address confirmation modal --------------------------------
  async function maybeShowAddressConfirm() {
    if (state.address) return;  // user already picked one (shouldn't happen on fresh load)
    if (!initData && !fallbackUid) return;
    try {
      const qs = new URLSearchParams({
        tenant: tenantId, init_data: initData, uid: fallbackUid || "",
      });
      const r = await fetch(`/api/user/primary-address?${qs}`);
      if (!r.ok) return;
      const data = await r.json();
      const a = data.address;
      if (!a || !a.text || a.text.startsWith("GPS ")) return;
      $("addrConfirmText").textContent = a.text;
      $("addrConfirm").classList.remove("hidden");
      $("addrConfirmYes").onclick = () => {
        state.address = a.text;
        state.addressLat = a.lat || null;
        state.addressLon = a.lon || null;
        $("addrText").textContent = a.text;
        $("addrConfirm").classList.add("hidden");
        if (tg?.HapticFeedback) tg.HapticFeedback.notificationOccurred("success");
      };
      $("addrConfirmNo").onclick = () => {
        $("addrConfirm").classList.add("hidden");
        openScreen("addrScreen");
      };
    } catch { /* silent — modal is purely a UX nicety */ }
  }

  function renderTabs() {
    const tabs = $("tabs");
    tabs.innerHTML = "";
    state.menu.categories.forEach(cat => {
      const btn = document.createElement("button");
      btn.className = "tab" + (cat === state.activeCategory ? " active" : "");
      btn.textContent = cat;
      btn.onclick = () => { state.activeCategory = cat; renderTabs(); renderProducts(); };
      tabs.appendChild(btn);
    });
  }

  function renderProducts() {
    const content = $("content");
    const scrollTop = content.scrollTop;
    content.innerHTML = "";
    const items = state.menu.products[state.activeCategory] || [];
    const header = document.createElement("h2");
    header.className = "cat-header";
    header.textContent = state.activeCategory;
    content.appendChild(header);

    const grid = document.createElement("div");
    grid.className = "products-grid";
    items.forEach(p => grid.appendChild(productCard(p)));
    content.appendChild(grid);
    content.scrollTop = scrollTop;
  }

  function _updateProductCardAction(p) {
    const card = $("content").querySelector(`[data-pid="${p.id}"]`);
    if (!card) return;
    const existing = card.querySelector(".add-btn, .qty");
    if (existing) existing.remove();
    card.appendChild(_productActionEl(p));
  }

  function _productActionEl(p) {
    const qty = state.cart[p.id] || 0;
    if (qty === 0) {
      const addBtn = document.createElement("button");
      addBtn.className = "add-btn";
      addBtn.textContent = T("add_to_cart");
      addBtn.onclick = () => {
        state.cart[p.id] = 1;
        _updateProductCardAction(p);
        refreshCartBar();
      };
      return addBtn;
    }
    const qctrl = document.createElement("div");
    qctrl.className = "qty";
    qctrl.innerHTML = `<button data-act="dec">➖</button><span>${qty}</span><button data-act="inc">➕</button>`;
    qctrl.querySelector('[data-act="dec"]').onclick = () => {
      state.cart[p.id]--;
      if (state.cart[p.id] <= 0) delete state.cart[p.id];
      _updateProductCardAction(p);
      refreshCartBar();
      if ($("cartScreen") && !$("cartScreen").classList.contains("hidden")) renderCartItems();
    };
    qctrl.querySelector('[data-act="inc"]').onclick = () => {
      state.cart[p.id]++;
      _updateProductCardAction(p);
      refreshCartBar();
      if ($("cartScreen") && !$("cartScreen").classList.contains("hidden")) renderCartItems();
    };
    return qctrl;
  }

  function productCard(p) {
    const card = document.createElement("div");
    card.className = "product-card";
    card.dataset.pid = p.id;

    const img = document.createElement("div");
    img.className = "product-img";
    if (p.image_url) img.style.backgroundImage = `url(${p.image_url})`;
    card.appendChild(img);

    const info = document.createElement("div");
    info.className = "product-info";
    info.innerHTML = `<div class="product-price">${fmt(p.price_value)}</div>
                      <div class="product-name">${escapeHtml(p.name)}</div>`;
    card.appendChild(info);
    card.appendChild(_productActionEl(p));
    return card;
  }

  function refreshCartBar() {
    const bar = $("cartBar");
    if (cartCount() === 0) {
      bar.classList.add("hidden");
      return;
    }
    bar.classList.remove("hidden");
    const countEl = $("cartCount");
    countEl.textContent = cartCount();
    $("cartTotal").textContent = fmt(cartTotal());
    countEl.classList.remove("pop");
    void countEl.offsetWidth; // reflow to restart animation
    countEl.classList.add("pop");
  }

  $("cartBar").onclick = () => openCart();

  // ----- Cart screen -----------------------------------------------------
  function renderCartItems() {
    const list = $("cartItems");
    list.innerHTML = "";
    for (const [pid, qty] of Object.entries(state.cart)) {
      const p = findProduct(parseInt(pid));
      if (!p) continue;
      const row = document.createElement("div");
      row.className = "cart-item";
      row.dataset.pid = p.id;
      row.innerHTML = `
        <div class="name">${escapeHtml(p.name)}<br><small>${fmt(p.price_value * qty)}</small></div>
        <div class="qty"><button data-act="dec">➖</button><span>${qty}</span><button data-act="inc">➕</button></div>
      `;
      row.querySelector('[data-act="dec"]').onclick = () => {
        state.cart[p.id]--;
        if (state.cart[p.id] <= 0) delete state.cart[p.id];
        renderCartItems(); refreshCartBar();
        _updateProductCardAction(p);
      };
      row.querySelector('[data-act="inc"]').onclick = () => {
        state.cart[p.id]++;
        renderCartItems(); refreshCartBar();
        _updateProductCardAction(p);
      };
      list.appendChild(row);
    }
    $("cartSumTotal").textContent = fmt(cartTotal());
  }

  function openCart() {
    openScreen("cartScreen");
    renderCartItems();
  }
  $("cartBack").onclick = () => closeScreen("cartScreen");

  // ----- Checkout --------------------------------------------------------
  function refreshCheckoutTotals() {
    const subtotal = cartTotal();
    $("checkoutSubtotal").textContent = fmt(subtotal);
    const disc = state.promo?.discount || 0;
    if (disc > 0) {
      $("checkoutDiscountRow").classList.remove("hidden");
      $("checkoutDiscount").textContent = "− " + fmt(disc);
    } else {
      $("checkoutDiscountRow").classList.add("hidden");
    }
    $("checkoutTotal").textContent = fmt(Math.max(0, subtotal - disc));
  }
  $("checkoutBtn").onclick = () => {
    if (cartCount() === 0) return;
    closeScreen("cartScreen");
    openScreen("checkoutScreen");
    $("inputAddress").value = state.address || "";
    refreshCheckoutTotals();
  };
  $("checkoutBack").onclick = () => closeScreen("checkoutScreen");

  // ----- Promo code apply -----------------------------------------------
  $("promoBtn").onclick = async () => {
    const code = $("inputPromo").value.trim();
    const msgEl = $("promoMsg");
    if (!code) {
      state.promo = null;
      msgEl.classList.add("hidden");
      refreshCheckoutTotals();
      return;
    }
    $("promoBtn").disabled = true;
    $("promoBtn").textContent = T("applying");
    try {
      const r = await fetch("/api/promo/check", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          init_data: initData, fallback_uid: fallbackUid, tenant_id: tenantId,
          code, total: cartTotal(),
        }),
      });
      const data = await r.json();
      if (!r.ok || !data.ok) {
        state.promo = null;
        msgEl.textContent = "⚠️ " + (data.message || T("promo_err"));
        msgEl.className = "promo-msg promo-err";
        msgEl.classList.remove("hidden");
      } else {
        state.promo = { code, discount: data.discount, label: data.label };
        msgEl.textContent = tfmt("promo_ok", { label: data.label });
        msgEl.className = "promo-msg promo-ok";
        msgEl.classList.remove("hidden");
        if (tg?.HapticFeedback) tg.HapticFeedback.notificationOccurred("success");
      }
      refreshCheckoutTotals();
    } catch (e) {
      msgEl.textContent = "⚠️ " + (e.message || T("promo_err"));
      msgEl.className = "promo-msg promo-err";
      msgEl.classList.remove("hidden");
    } finally {
      $("promoBtn").disabled = false;
      $("promoBtn").textContent = T("apply");
    }
  };

  // Delivery method toggle (group A: data-method)
  document.querySelectorAll('.seg-btn[data-method]').forEach(b => {
    b.onclick = () => {
      document.querySelectorAll('.seg-btn[data-method]').forEach(x => x.classList.remove("active"));
      b.classList.add("active");
      state.deliveryType = b.dataset.method;
      const isPickup = state.deliveryType === "pickup";
      $("branchLabel").classList.toggle("hidden", !isPickup);
      // Hide the address card when picking up — only branch matters then.
      $("addrCard")?.classList.toggle("hidden", isPickup);
    };
  });
  // Payment method toggle (group B: data-pay)
  document.querySelectorAll('.seg-btn[data-pay]').forEach(b => {
    b.onclick = () => {
      document.querySelectorAll('.seg-btn[data-pay]').forEach(x => x.classList.remove("active"));
      b.classList.add("active");
      state.paymentMethod = b.dataset.pay;
    };
  });

  function populateBranches() {
    if (!state.menu?.branches) return;
    const picker = $("branchPicker");
    if (!picker) return;
    picker.innerHTML = "";
    state.menu.branches.forEach((b, idx) => {
      const card = document.createElement("div");
      card.className = "branch-pick-card" + (idx === 0 ? " selected" : "");
      card.dataset.id = b.id;
      card.innerHTML = `
        <div class="pick-name">${escapeHtml(b.name)}</div>
        <div class="pick-addr">📍 ${escapeHtml(b.address || "")}</div>
      `;
      card.onclick = () => {
        picker.querySelectorAll(".branch-pick-card").forEach(c => c.classList.remove("selected"));
        card.classList.add("selected");
        state.branchId = b.id;
      };
      picker.appendChild(card);
    });
    if (state.menu.branches.length) state.branchId = state.menu.branches[0].id;
  }

  // ----- Submit order ----------------------------------------------------
  $("submitBtn").onclick = async () => {
    const addr = $("inputAddress").value.trim();
    const time = $("inputTime").value.trim();
    if (!addr) { showErr(T("err_addr")); return; }
    const finalTime = time || "—";
    if (cartCount() === 0) { showErr(T("err_cart_empty")); return; }
    if (!initData && !fallbackUid) {
      showErr(T("err_no_init"));
      return;
    }
    // Building details are required for delivery (not for pickup).
    if (state.deliveryType === "delivery") {
      const bldgFields = ["inputEntrance", "inputFloor", "inputApartment", "inputIntercom"];
      let missing = false;
      for (const id of bldgFields) {
        const el = $(id);
        if (!el || !el.value.trim()) {
          if (el) el.classList.add("has-error");
          missing = true;
        } else if (el) {
          el.classList.remove("has-error");
        }
      }
      if (missing) {
        showErr(T("err_bldg"));
        // Scroll the address card into view so the user sees the highlighted rows.
        $("addrCard")?.scrollIntoView({ behavior: "smooth", block: "start" });
        return;
      }
    }

    const payload = {
      init_data: initData,
      fallback_uid: fallbackUid,
      tenant_id: tenantId,
      branch_id: state.deliveryType === "pickup" ? state.branchId : null,
      delivery_type: state.deliveryType,
      address: addr,
      address_lat: state.addressLat,
      address_lon: state.addressLon,
      preferred_time: finalTime,
      payment_method: state.paymentMethod,
      promo_code: state.promo?.code || "",
      note:         $("inputNote")?.value.trim() || "",
      courier_note: $("inputCourierNote")?.value.trim() || "",
      entrance:     $("inputEntrance")?.value.trim() || "",
      floor:        $("inputFloor")?.value.trim() || "",
      apartment:    $("inputApartment")?.value.trim() || "",
      intercom:     $("inputIntercom")?.value.trim() || "",
      items: Object.entries(state.cart).map(([pid, qty]) => ({ product_id: parseInt(pid), qty }))
    };

    const submitBtn = $("submitBtn");
    submitBtn.disabled = true;
    submitBtn.textContent = T("sending");
    try {
      // Extend mode: append the items to an existing pending order instead
      // of creating a new one. Skips address/payment fields (already set on
      // the original order).
      if (extendOrderId) {
        const rx = await fetch("/api/orders/extend", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            init_data: initData, fallback_uid: fallbackUid,
            tenant_id: tenantId, order_id: extendOrderId,
            items: payload.items,
          }),
        });
        const dx = await rx.json();
        if (!rx.ok) throw new Error(dx.detail || `${rx.status}`);
        if (tg?.HapticFeedback) tg.HapticFeedback.notificationOccurred("success");
        state.cart = {};
        refreshCartBar();
        if (tg) {
          alert(T("extend_added"));
          tg.close();
        } else {
          closeScreen("checkoutScreen");
        }
        return;
      }
      const r = await fetch("/api/order", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!r.ok) {
        const t = await r.text();
        throw new Error(`${T("err_server")}${r.status} ${t.slice(0, 100)}`);
      }
      const data = await r.json();
      // Show our own success screen so the user has a clear path to close
      // (Telegram alerts' X button does NOT fire the callback).
      if (tg?.HapticFeedback) tg.HapticFeedback.notificationOccurred("success");
      showSuccess(data);
    } catch (e) {
      showErr(e.message);
    } finally {
      submitBtn.disabled = false;
      submitBtn.textContent = T("confirm");
    }
  };

  function _openPayUrl(url) {
    if (tg) tg.openLink(url); else window.open(url, "_blank");
  }

  async function _copyCardNumber(cardNum) {
    try {
      await navigator.clipboard.writeText(cardNum.replace(/\s/g, ""));
      const hint = $("payCopyHint");
      hint.classList.remove("hidden");
      setTimeout(() => hint.classList.add("hidden"), 3000);
    } catch { /* clipboard blocked on some browsers - silent */ }
  }

  function showSuccess(data) {
    $("payOrderId").textContent = "#" + data.order_id;
    $("payAmount").textContent = fmt(data.total);

    const isCard = data.payment_method === "card";
    const cardSection = $("payCardSection");

    if (!isCard) {
      cardSection.classList.add("hidden");
    } else {
      cardSection.classList.remove("hidden");

      // ── Card number display ──────────────────────────────────────────
      const cardBlock = $("payCardBlock");
      if (data.card_number) {
        cardBlock.classList.remove("hidden");
        $("payCardNumber").textContent = data.card_number;
        $("payCardCopy").onclick = () => _copyCardNumber(data.card_number);
      } else {
        cardBlock.classList.add("hidden");
      }

      // ── Payment app buttons ──────────────────────────────────────────
      // When merchant checkout URL available → one tap to pay (amount pre-filled).
      // When transfer URL → copy card number first, then open app.
      const appsBlock = $("payAppsBlock");
      const configuredApps = [];

      const wireBtn = (btnId, url, mode) => {
        const btn = $(btnId);
        if (!btn) return;
        if (!url) { btn.classList.add("hidden"); return; }
        btn.classList.remove("hidden");
        configuredApps.push({ url, mode });
        btn.onclick = async () => {
          if (mode === "transfer" && data.card_number) {
            await _copyCardNumber(data.card_number);
          }
          _openPayUrl(url);
        };
      };

      wireBtn("payClickBtn", data.click_url, data.click_mode);
      wireBtn("payPaymeBtn", data.payme_url, data.payme_mode);
      wireBtn("payAlifBtn",  data.alif_url,  data.alif_mode);

      if (configuredApps.length > 0) {
        appsBlock.classList.remove("hidden");
      } else {
        appsBlock.classList.add("hidden");
      }

      // No payment options at all → show notice
      const noUrl = $("payNoUrl");
      if (configuredApps.length === 0 && !data.card_number) {
        noUrl.classList.remove("hidden");
        noUrl.textContent = T("no_pay_configured");
      } else {
        noUrl.classList.add("hidden");
      }

      // Auto-open if only one app is available AND it's a merchant checkout
      // (merchant checkouts are safe to auto-open — amount+merchant pre-filled).
      if (configuredApps.length === 1 && configuredApps[0].mode === "merchant") {
        setTimeout(() => _openPayUrl(configuredApps[0].url), 600);
      }
    }

    state.cart = {};
    refreshCartBar();
    closeScreen("checkoutScreen");
    openScreen("payScreen");
  }

  // Old name kept for compatibility with code that still calls it.
  function showPaymentChoice(data) { showSuccess(data); }

  function showErr(msg) {
    const box = $("errBox");
    box.textContent = msg; box.classList.remove("hidden");
    setTimeout(() => box.classList.add("hidden"), 4000);
  }

  // ----- Payment / success screen wiring --------------------------------
  $("payBack").onclick = () => closeScreen("payScreen");
  $("payCloseBtn").onclick = () => { if (tg) tg.close(); else closeScreen("payScreen"); };

  // ----- Address picker screen ------------------------------------------
  $("addrBtn").onclick = () => {
    $("addrInput").value = state.address && !state.address.startsWith("GPS") ? state.address : "";
    $("addrErr").classList.add("hidden");
    $("addrDetecting").classList.add("hidden");
    openScreen("addrScreen");
  };
  $("addrBack").onclick = () => closeScreen("addrScreen");

  $("useLocBtn").onclick = () => {
    $("addrErr").classList.add("hidden");
    if (!navigator.geolocation) {
      addrErr(T("err_geo_unsupported"));
      return;
    }
    $("addrDetecting").classList.remove("hidden");
    navigator.geolocation.getCurrentPosition(
      async (pos) => {
        const { latitude, longitude } = pos.coords;
        state.addressLat = latitude;
        state.addressLon = longitude;
        try {
          const r = await fetch(`/api/reverse-geocode?lat=${latitude}&lon=${longitude}&lang=uz`);
          const data = await r.json();
          const addr = data.address || `GPS ${latitude.toFixed(5)}, ${longitude.toFixed(5)}`;
          state.address = addr;
          $("addrText").textContent = addr;
          $("addrDetecting").classList.add("hidden");
          closeScreen("addrScreen");
          if (tg?.HapticFeedback) tg.HapticFeedback.notificationOccurred("success");
        } catch (e) {
          $("addrDetecting").classList.add("hidden");
          addrErr(T("err_geocode"));
        }
      },
      (err) => {
        $("addrDetecting").classList.add("hidden");
        addrErr(T("err_geo_denied"));
      },
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }
    );
  };

  $("addrSaveBtn").onclick = () => {
    const txt = $("addrInput").value.trim();
    if (!txt) { addrErr(T("err_addr_empty")); return; }
    state.address = txt;
    state.addressLat = null;
    state.addressLon = null;
    $("addrText").textContent = txt;
    closeScreen("addrScreen");
  };

  function addrErr(msg) {
    const box = $("addrErr");
    box.textContent = "⚠️ " + msg;
    box.classList.remove("hidden");
  }

  // ----- Map picker (Leaflet) -------------------------------------------
  let leafletMap = null;
  let leafletMarker = null;
  let mapSelectedLatLon = null;
  let mapAddrText = "";
  let geocodeTimer = null;

  $("openMapBtn").onclick = () => {
    closeScreen("addrScreen");
    openScreen("mapScreen");
    // Initialize map on first open. Defaults to Tashkent.
    setTimeout(() => {
      if (!leafletMap) {
        leafletMap = L.map("leafletMap").setView([41.2995, 69.2401], 13);
        L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
          maxZoom: 19, attribution: "© OpenStreetMap",
        }).addTo(leafletMap);
        leafletMarker = L.marker([41.2995, 69.2401], { draggable: true }).addTo(leafletMap);
        leafletMarker.on("dragend", onMarkerMove);
        leafletMap.on("click", (e) => {
          leafletMarker.setLatLng(e.latlng);
          onMarkerMove();
        });
        onMarkerMove();
      }
      // Try to center on user location if known.
      if (state.addressLat && state.addressLon) {
        leafletMap.setView([state.addressLat, state.addressLon], 16);
        leafletMarker.setLatLng([state.addressLat, state.addressLon]);
        onMarkerMove();
      } else if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition((pos) => {
          const { latitude, longitude } = pos.coords;
          leafletMap.setView([latitude, longitude], 16);
          leafletMarker.setLatLng([latitude, longitude]);
          onMarkerMove();
        }, () => {}, { timeout: 5000 });
      }
      // Recompute size after the container becomes visible.
      leafletMap.invalidateSize();
    }, 50);
  };

  function onMarkerMove() {
    const ll = leafletMarker.getLatLng();
    mapSelectedLatLon = { lat: ll.lat, lon: ll.lng };
    $("mapAddr").textContent = `📍 Aniqlanmoqda... (${ll.lat.toFixed(5)}, ${ll.lng.toFixed(5)})`;
    if (geocodeTimer) clearTimeout(geocodeTimer);
    geocodeTimer = setTimeout(async () => {
      try {
        const r = await fetch(`/api/reverse-geocode?lat=${ll.lat}&lon=${ll.lng}&lang=uz`);
        const d = await r.json();
        mapAddrText = d.address || `GPS ${ll.lat.toFixed(5)}, ${ll.lng.toFixed(5)}`;
        $("mapAddr").textContent = "📍 " + mapAddrText;
      } catch {
        mapAddrText = `GPS ${ll.lat.toFixed(5)}, ${ll.lng.toFixed(5)}`;
        $("mapAddr").textContent = "📍 " + mapAddrText;
      }
    }, 400);
  }

  $("mapBack").onclick = () => { closeScreen("mapScreen"); openScreen("addrScreen"); };

  $("mapSaveBtn").onclick = () => {
    if (!mapSelectedLatLon) return;
    state.address = mapAddrText || `GPS ${mapSelectedLatLon.lat.toFixed(5)}, ${mapSelectedLatLon.lon.toFixed(5)}`;
    state.addressLat = mapSelectedLatLon.lat;
    state.addressLon = mapSelectedLatLon.lon;
    $("addrText").textContent = state.address;
    closeScreen("mapScreen");
    // also close the addr-picker if still open
    if (!$("addrScreen").classList.contains("hidden")) closeScreen("addrScreen");
  };

  // Extend-banner cancel (X) — closes the WebApp.
  $("extendCancel")?.addEventListener("click", () => {
    if (tg) tg.close();
  });

  // ----- Order history --------------------------------------------------
  $("historyBtn").onclick = () => { openScreen("historyScreen"); loadHistory(); };
  $("historyBack").onclick = () => closeScreen("historyScreen");

  async function loadHistory() {
    const list = $("historyList");
    list.innerHTML = `<div class="loading">${T("loading")}</div>`;
    if (!initData && !fallbackUid) {
      list.innerHTML = `<div class="info">${T("hist_open_with_bot")}</div>`;
      return;
    }
    try {
      const qs = new URLSearchParams({
        tenant: tenantId, init_data: initData, uid: fallbackUid || "",
      });
      const r = await fetch(`/api/orders/history?${qs}`);
      const data = await r.json();
      if (!r.ok) throw new Error(data.detail || T("err_server"));
      list.innerHTML = "";
      if (!data.orders.length) {
        list.innerHTML = `<div class="info">${T("hist_empty")}</div>`;
        return;
      }
      data.orders.forEach(o => list.appendChild(historyCard(o)));
    } catch (e) {
      list.innerHTML = `<div class="err">⚠️ ${escapeHtml(e.message)}</div>`;
    }
  }

  function statusBadge(status) {
    const cls = status === "pending"   ? "badge-pending"
              : status === "cancelled" ? "badge-cancelled"
              : "badge-confirmed";
    return `<span class="hist-badge ${cls}">${T("status_" + status, status)}</span>`;
  }

  function canSelfCancel(o) {
    if (o.status !== "pending") return 0;  // returns remaining seconds, or 0
    try {
      const created = new Date((o.created_at || "").replace("Z", "") + "Z");
      const elapsed = (Date.now() - created.getTime()) / 1000;
      const remaining = 120 - elapsed;
      return remaining > 0 ? Math.floor(remaining) : 0;
    } catch { return 0; }
  }

  function historyCard(o) {
    const card = document.createElement("article");
    card.className = "hist-card";
    const date = (o.created_at || "").replace("T", " ").slice(0, 16);
    const itemsHtml = (o.items || []).slice(0, 4)
      .map(it => `<div class="hist-item">• ${escapeHtml(it.name)} × ${it.qty}</div>`)
      .join("");
    const moreHtml = (o.items || []).length > 4
      ? `<div class="hist-item muted">${tfmt("hist_more", { n: o.items.length - 4 })}</div>` : "";
    const reorderable = (o.items || []).some(it => findProduct(it.product_id));
    const cancelSec = canSelfCancel(o);
    card.innerHTML = `
      <div class="hist-head">
        <div>
          <div class="hist-id">${T("hist_label")} #${o.id}</div>
          <div class="hist-date">${escapeHtml(date)}</div>
        </div>
        ${statusBadge(o.status)}
      </div>
      <div class="hist-items">${itemsHtml}${moreHtml}</div>
      <div class="hist-foot">
        <strong class="hist-total">${fmt(o.amount)}</strong>
        ${reorderable ? `<button class="primary-btn reorder-btn">${T("reorder")}</button>` : ''}
      </div>
      ${cancelSec ? `
        <div class="hist-actions">
          <button class="ghost-btn extend-btn">${T("extend_btn")}</button>
          <button class="ghost-btn cancel-btn" style="border-color:var(--danger);color:var(--danger)">
            ${T("cancel_btn")} <span class="cancel-cd">${cancelSec}s</span>
          </button>
        </div>` : ""}
    `;
    const xbtn = card.querySelector(".extend-btn");
    if (xbtn) {
      xbtn.onclick = () => {
        // Open this WebApp again in extend mode by appending ?extend=ID.
        const u = new URL(window.location.href);
        u.searchParams.set("extend", String(o.id));
        if (tg) {
          tg.openLink ? tg.openLink(u.toString()) : (window.location.href = u.toString());
        } else {
          window.location.href = u.toString();
        }
      };
    }
    const cbtn = card.querySelector(".cancel-btn");
    if (cbtn) {
      // Live countdown so the button disappears at 0.
      let left = cancelSec;
      const cdEl = card.querySelector(".cancel-cd");
      const timer = setInterval(() => {
        left -= 1;
        if (cdEl) cdEl.textContent = left + "s";
        if (left <= 0) { clearInterval(timer); cbtn.remove(); }
      }, 1000);
      cbtn.onclick = async () => {
        if (!confirm(T("confirm_cancel_my"))) return;
        cbtn.disabled = true;
        try {
          const r = await fetch("/api/orders/cancel", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              init_data: initData, fallback_uid: fallbackUid,
              tenant_id: tenantId, order_id: o.id,
            }),
          });
          const data = await r.json();
          if (!r.ok) throw new Error(data.detail || "");
          if (tg?.HapticFeedback) tg.HapticFeedback.notificationOccurred("success");
          clearInterval(timer);
          await loadHistory();
        } catch (e) {
          alert(T("cancel_failed") + (e.message ? ": " + e.message : ""));
          cbtn.disabled = false;
        }
      };
    }
    const btn = card.querySelector(".reorder-btn");
    if (btn) {
      btn.onclick = () => {
        let added = 0;
        for (const it of (o.items || [])) {
          if (findProduct(it.product_id)) {
            state.cart[it.product_id] = (state.cart[it.product_id] || 0) + (it.qty || 1);
            added += it.qty || 1;
          }
        }
        if (!added) return;
        if (tg?.HapticFeedback) tg.HapticFeedback.notificationOccurred("success");
        refreshCartBar();
        renderProducts();
        closeScreen("historyScreen");
        openCart();
      };
    }
    return card;
  }

  // ----- Boot ------------------------------------------------------------
  loadMenu();
})();

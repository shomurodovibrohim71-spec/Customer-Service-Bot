/* Admin Mini App for managing products. */
(() => {
  const tg = window.Telegram?.WebApp;
  if (tg) { tg.ready(); tg.expand(); }

  const url = new URL(window.location.href);
  const startParam = tg?.initDataUnsafe?.start_param || "";
  const tenantId = startParam || url.searchParams.get("tenant") || "tenant_001";
  const initData = tg?.initData || "";
  const fallbackUid = parseInt(url.searchParams.get("uid") || "0") || null;
  const T = window.T;
  const tfmt = (key, vars) => {
    let s = T(key);
    for (const [k, v] of Object.entries(vars || {})) s = s.replace("{" + k + "}", v);
    return s;
  };

  const state = { products: [], categories: [], editing: null };

  const $ = (id) => document.getElementById(id);
  const fmt = (n) => new Intl.NumberFormat("uz-UZ").format(n || 0) + " " + T("soum");
  const screenStack = [];
  function openScreen(id) {
    $(id).classList.remove("hidden");
    screenStack.push(id);
    syncBackButton();
  }
  function closeScreen(id) {
    $(id).classList.add("hidden");
    const i = screenStack.lastIndexOf(id);
    if (i >= 0) screenStack.splice(i, 1);
    syncBackButton();
  }
  function syncBackButton() {
    if (!tg?.BackButton) return;
    if (screenStack.length) tg.BackButton.show(); else tg.BackButton.hide();
  }
  if (tg?.BackButton) {
    tg.BackButton.onClick(() => {
      const top = screenStack[screenStack.length - 1];
      if (top) closeScreen(top);
    });
  }
  function escapeHtml(s) {
    return String(s ?? "").replace(/[&<>"']/g, c => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
    }[c]));
  }
  function showErr(box, msg) {
    box.textContent = "⚠️ " + msg;
    box.classList.remove("hidden");
    setTimeout(() => box.classList.add("hidden"), 4000);
  }

  async function api(method, path, body) {
    const opts = { method, headers: { "Content-Type": "application/json" } };
    if (body !== undefined) {
      opts.body = JSON.stringify({ ...body, init_data: initData, fallback_uid: fallbackUid, tenant_id: tenantId });
    }
    const sep = path.includes("?") ? "&" : "?";
    const full = body === undefined
      ? `${path}${sep}tenant=${encodeURIComponent(tenantId)}&uid=${fallbackUid || ""}&init_data=${encodeURIComponent(initData)}`
      : path;
    const r = await fetch(full, opts);
    if (!r.ok) {
      const t = await r.text();
      throw new Error(`${r.status} ${t.slice(0, 100)}`);
    }
    return r.json();
  }

  async function load() {
    const list = $("list");
    try {
      const data = await api("GET", "/api/admin/products");
      state.products = data.products;
      state.categories = data.categories;
      $("prodCount").textContent = tfmt("count", { n: state.products.length });
      render();
    } catch (e) {
      list.innerHTML = `<div class="err">⚠️ ${escapeHtml(e.message)}</div>`;
    }
  }

  function render() {
    const list = $("list");
    list.innerHTML = "";
    if (!state.products.length) {
      list.innerHTML = `<div class="info">${T("empty")}</div>`;
      return;
    }
    const grouped = {};
    for (const p of state.products) {
      const cat = p.category || "—";
      (grouped[cat] = grouped[cat] || []).push(p);
    }
    for (const [cat, items] of Object.entries(grouped)) {
      const sec = document.createElement("section");
      sec.className = "admin-cat-section";
      sec.innerHTML = `<h3 class="cat-title">${escapeHtml(cat)} <span class="muted">${items.length} ${T("cnt_suffix")}</span></h3>`;
      const rows = document.createElement("div");
      rows.className = "admin-prod-list";
      items.forEach(p => rows.appendChild(card(p)));
      sec.appendChild(rows);
      list.appendChild(sec);
    }
  }

  function card(p) {
    const isHidden = p.is_active === 0;
    const row = document.createElement("div");
    row.className = "apr" + (isHidden ? " prod-hidden" : p.in_stock === 0 ? " out-of-stock" : "");

    // Thumbnail
    if (p.image_url) {
      const im = document.createElement("img");
      im.className = "apr-thumb"; im.src = p.image_url; im.alt = p.name;
      row.appendChild(im);
    } else {
      const ph = document.createElement("div");
      ph.className = "apr-thumb-empty"; ph.textContent = "🍔";
      row.appendChild(ph);
    }

    // Name + price
    const info = document.createElement("div");
    info.className = "apr-info";
    const hiddenBadge = isHidden ? `<span class="prod-hidden-badge">${T("hidden_label")}</span>` : "";
    info.innerHTML = `
      <div class="apr-name">${escapeHtml(p.name)}${hiddenBadge}</div>
      <div class="apr-price">${fmt(p.price_value)}</div>`;
    row.appendChild(info);

    // Toggle switch
    const toggleWrap = document.createElement("label");
    toggleWrap.className = "prod-toggle-wrap";
    toggleWrap.title = isHidden ? T("btn_activate") : T("btn_hide_hint");
    toggleWrap.onclick = (e) => e.stopPropagation();
    const toggleInput = document.createElement("input");
    toggleInput.type = "checkbox";
    toggleInput.checked = !isHidden;
    toggleInput.onchange = async () => {
      toggleInput.disabled = true;
      try {
        await api("POST", `/api/admin/products/${p.id}/toggle-active`, {});
        if (tg?.HapticFeedback) tg.HapticFeedback.impactOccurred("light");
        await load();
      } catch (err) { alert("⚠️ " + err.message); toggleInput.disabled = false; }
    };
    const toggleSlider = document.createElement("span");
    toggleSlider.className = "prod-toggle-slider";
    toggleWrap.appendChild(toggleInput);
    toggleWrap.appendChild(toggleSlider);
    row.appendChild(toggleWrap);

    // Edit button
    const editBtn = document.createElement("button");
    editBtn.className = "apr-btn apr-edit";
    editBtn.textContent = "✏️";
    editBtn.onclick = (e) => { e.stopPropagation(); openEdit(p); };
    row.appendChild(editBtn);

    // Delete button
    const delBtn = document.createElement("button");
    delBtn.className = "apr-btn apr-del";
    delBtn.textContent = "🗑";
    delBtn.onclick = async (e) => {
      e.stopPropagation();
      if (!confirm(tfmt("confirm_del_prod", { n: p.name }))) return;
      delBtn.disabled = true;
      try {
        await api("DELETE", `/api/admin/products/${p.id}`, {});
        if (tg?.HapticFeedback) tg.HapticFeedback.notificationOccurred("success");
        await load();
      } catch (err) { alert("⚠️ " + err.message); }
      finally { delBtn.disabled = false; }
    };
    row.appendChild(delBtn);

    return row;
  }

  function openEdit(p) {
    state.editing = p ? { ...p } : { id: null, name: "", category: state.categories[0] || "", price_value: 0, description: "", image_url: "" };
    $("editTitle").textContent = p ? T("edit_title") : T("new_title");
    $("fName").value = state.editing.name || "";
    $("fPriceVal").value = state.editing.price_value || 0;
    $("fDesc").value = state.editing.description || "";
    $("fImage").value = state.editing.image_url || "";

    const sel = $("fCategory");
    sel.innerHTML = "";
    for (const c of state.categories) {
      const o = document.createElement("option");
      o.value = c; o.textContent = c; sel.appendChild(o);
    }
    const newOpt = document.createElement("option");
    newOpt.value = "__new__"; newOpt.textContent = T("new_cat_option");
    sel.appendChild(newOpt);
    sel.value = state.editing.category || (state.categories[0] || "__new__");
    sel.onchange = () => {
      if (sel.value === "__new__") {
        const newCat = prompt(T("prompt_new_cat"));
        if (newCat) {
          const o = document.createElement("option");
          o.value = newCat; o.textContent = newCat;
          sel.insertBefore(o, newOpt);
          sel.value = newCat;
          state.categories.push(newCat);
        } else {
          sel.value = state.editing.category || state.categories[0] || "";
        }
      }
    };
    $("delBtn").style.display = p ? "block" : "none";
    openScreen("editScreen");
  }

  $("editBack").onclick = () => closeScreen("editScreen");
  $("addBtn").onclick = () => openEdit(null);

  async function loadCats() {
    const list = $("catsList");
    list.innerHTML = `<div class="loading">${T("loading")}</div>`;
    try {
      const data = await api("GET", "/api/admin/categories");
      list.innerHTML = "";
      if (!data.categories.length) {
        list.innerHTML = `<div class="info">${T("cats_empty")}</div>`;
      } else {
        data.categories.forEach(c => list.appendChild(catRow(c)));
      }
    } catch (e) {
      list.innerHTML = `<div class="err">⚠️ ${escapeHtml(e.message)}</div>`;
    }
    // Also load upsell toggles whenever cats screen opens
    loadUpsellCats();
  }

  // ── upsell category toggles
  // Category names are stored as JS objects (not in data-* attributes)
  // to avoid any HTML encoding/decoding issues with emoji.
  const _upsellCatMap = new Map(); // checkbox element → original category string

  async function loadUpsellCats() {
    const container = $("upsellCatsList");
    if (!container) return;
    _upsellCatMap.clear();
    container.innerHTML = `<div class="loading" style="font-size:13px">${T("loading")}</div>`;
    try {
      const qs = `?tenant=${encodeURIComponent(tenantId)}&uid=${fallbackUid || ""}&init_data=${encodeURIComponent(initData)}`;
      const r = await fetch(`/api/admin/upsell-categories${qs}`);
      if (!r.ok) throw new Error(await r.text());
      const data = await r.json();
      const current = new Set(data.upsell_categories || []);
      const all = data.all_categories || [];
      container.innerHTML = "";
      all.forEach(cat => {
        const row = document.createElement("div");
        row.className = "upsell-row";
        const nameSpan = document.createElement("span");
        nameSpan.className = "upsell-row-name";
        nameSpan.textContent = cat;          // textContent — no HTML encoding issues
        const label = document.createElement("label");
        label.className = "upsell-toggle";
        const checkbox = document.createElement("input");
        checkbox.type = "checkbox";
        checkbox.checked = current.has(cat);
        _upsellCatMap.set(checkbox, cat);    // store original string in Map
        const slider = document.createElement("span");
        slider.className = "upsell-slider";
        label.appendChild(checkbox);
        label.appendChild(slider);
        row.appendChild(nameSpan);
        row.appendChild(label);
        checkbox.onchange = () => saveUpsellCats();
        container.appendChild(row);
      });
      if (!all.length) container.innerHTML = `<div class="info" style="font-size:13px">—</div>`;
    } catch (e) {
      container.innerHTML = `<div class="err" style="font-size:13px">⚠️ ${escapeHtml(e.message)}</div>`;
    }
  }

  async function saveUpsellCats() {
    // Read checked categories directly from the Map (no data-* attribute encoding issues)
    const checked = [];
    _upsellCatMap.forEach((cat, checkbox) => {
      if (checkbox.checked) checked.push(cat);
    });
    try {
      const qs = `?tenant=${encodeURIComponent(tenantId)}&uid=${fallbackUid || ""}&init_data=${encodeURIComponent(initData)}`;
      const r = await fetch(`/api/admin/upsell-categories${qs}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ categories: checked }),
      });
      if (!r.ok) throw new Error(await r.text());
    } catch (e) {
      alert("Xato: " + e.message);
    }
  }

  $("catsBtn").onclick = () => { openScreen("catsScreen"); loadCats(); };
  $("catsBack").onclick = () => closeScreen("catsScreen");

  $("addCatBtn").onclick = async () => {
    const input = $("newCatInput");
    const name = input.value.trim();
    if (!name) { showErr($("catsErr"), T("err_cat_name")); return; }
    $("addCatBtn").disabled = true;
    try {
      await api("POST", "/api/admin/categories", { name });
      input.value = "";
      if (tg?.HapticFeedback) tg.HapticFeedback.notificationOccurred("success");
      await loadCats();
      await load();
    } catch (e) {
      showErr($("catsErr"), e.message);
    } finally {
      $("addCatBtn").disabled = false;
    }
  };

  function catRow(c) {
    const row = document.createElement("div");
    row.className = "cat-row";
    row.innerHTML = `
      <div class="cat-row-name">${escapeHtml(c.name)}</div>
      <div class="cat-row-count">${c.count} ${T("cnt_suffix")}</div>
      <button class="cat-del">🗑</button>
    `;
    row.querySelector(".cat-del").onclick = async () => {
      const msg = c.count > 0
        ? tfmt("confirm_del_cat_with", { c: c.name, n: c.count })
        : tfmt("confirm_del_cat", { c: c.name });
      if (!confirm(msg)) return;
      try {
        await api("POST", "/api/admin/categories/delete", { name: c.name });
        if (tg?.HapticFeedback) tg.HapticFeedback.notificationOccurred("success");
        await loadCats();
        await load();
      } catch (e) {
        alert(T("err_prefix") + e.message);
      }
    };
    return row;
  }

  $("saveBtn").onclick = async () => {
    const payload = {
      id: state.editing?.id || null,
      name: $("fName").value.trim(),
      category: $("fCategory").value,
      price_value: parseInt($("fPriceVal").value) || 0,
      description: $("fDesc").value.trim(),
      image_url: $("fImage").value.trim(),
    };
    if (!payload.name) { showErr($("formErr"), T("err_name")); return; }
    if (!payload.category || payload.category === "__new__") { showErr($("formErr"), T("err_cat_req")); return; }
    if (payload.price_value <= 0) { showErr($("formErr"), T("err_price")); return; }

    $("saveBtn").disabled = true;
    $("saveBtn").textContent = T("saving");
    try {
      if (payload.id) {
        await api("PUT", `/api/admin/products/${payload.id}`, payload);
      } else {
        await api("POST", "/api/admin/products", payload);
      }
      if (tg?.HapticFeedback) tg.HapticFeedback.notificationOccurred("success");
      closeScreen("editScreen");
      await load();
    } catch (e) {
      showErr($("formErr"), e.message);
    } finally {
      $("saveBtn").disabled = false;
      $("saveBtn").textContent = T("save_btn");
    }
  };

  $("delBtn").onclick = async () => {
    if (!state.editing?.id) return;
    if (!confirm(tfmt("confirm_del_prod", { n: state.editing.name }))) return;
    try {
      await api("DELETE", `/api/admin/products/${state.editing.id}`, { id: state.editing.id });
      if (tg?.HapticFeedback) tg.HapticFeedback.notificationOccurred("success");
      closeScreen("editScreen");
      await load();
    } catch (e) {
      showErr($("formErr"), e.message);
    }
  };

  load();
})();

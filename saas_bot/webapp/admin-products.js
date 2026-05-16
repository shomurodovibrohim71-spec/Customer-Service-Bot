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
      const grid = document.createElement("div");
      grid.className = "admin-prod-grid";
      items.forEach(p => grid.appendChild(card(p)));
      sec.appendChild(grid);
      list.appendChild(sec);
    }
  }

  function card(p) {
    const c = document.createElement("div");
    c.className = "admin-prod-card" + (p.in_stock === 0 ? " out-of-stock" : "");
    const img = p.image_url
      ? `<div class="admin-prod-img" style="background-image:url('${escapeHtml(p.image_url)}')"></div>`
      : `<div class="admin-prod-img admin-prod-img-empty">🍔</div>`;
    const stockLabel = p.in_stock === 0 ? T("stock_out") : T("stock_in");
    const stockClass = p.in_stock === 0 ? "stock-badge out" : "stock-badge in";
    c.innerHTML = `
      ${img}
      <div class="admin-prod-info">
        <div class="admin-prod-name">${escapeHtml(p.name)}</div>
        <div class="admin-prod-price">${fmt(p.price_value)}</div>
        <button class="stock-toggle-btn ${stockClass}" data-id="${p.id}">${stockLabel}</button>
      </div>
    `;
    c.querySelector(".stock-toggle-btn").onclick = async (e) => {
      e.stopPropagation();
      const btn = e.currentTarget;
      btn.disabled = true;
      try {
        const res = await api("POST", `/api/admin/products/${p.id}/toggle-stock`);
        p.in_stock = res.in_stock ? 1 : 0;
        c.className = "admin-prod-card" + (p.in_stock === 0 ? " out-of-stock" : "");
        btn.textContent = p.in_stock === 0 ? T("stock_out") : T("stock_in");
        btn.className = "stock-toggle-btn " + (p.in_stock === 0 ? "stock-badge out" : "stock-badge in");
        if (tg?.HapticFeedback) tg.HapticFeedback.impactOccurred("light");
      } catch (err) { alert("⚠️ " + err.message); }
      finally { btn.disabled = false; }
    };
    c.onclick = (e) => { if (!e.target.closest(".stock-toggle-btn")) openEdit(p); };
    return c;
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
        return;
      }
      data.categories.forEach(c => list.appendChild(catRow(c)));
    } catch (e) {
      list.innerHTML = `<div class="err">⚠️ ${escapeHtml(e.message)}</div>`;
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

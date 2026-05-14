/* Admin promo-code manager: list + add + delete. */
(() => {
  const tg = window.Telegram?.WebApp;
  if (tg) { tg.ready(); tg.expand(); }

  const url = new URL(window.location.href);
  const startParam = tg?.initDataUnsafe?.start_param || "";
  const tenantId = startParam || url.searchParams.get("tenant") || "tenant_001";
  const initData = tg?.initData || "";
  const fallbackUid = parseInt(url.searchParams.get("uid") || "0") || null;
  const T = window.T;

  const $ = (id) => document.getElementById(id);
  const fmt = (n) => new Intl.NumberFormat("uz-UZ").format(n || 0);
  const escapeHtml = (s) => String(s ?? "").replace(/[&<>"']/g,
    c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const tfmt = (key, vars) => {
    let s = T(key);
    for (const [k, v] of Object.entries(vars || {})) s = s.replace("{" + k + "}", v);
    return s;
  };

  const state = { type: "percent" };
  const screenStack = [];
  function openScreen(id) {
    $(id).classList.remove("hidden");
    screenStack.push(id);
    syncBack();
  }
  function closeScreen(id) {
    $(id).classList.add("hidden");
    const i = screenStack.lastIndexOf(id);
    if (i >= 0) screenStack.splice(i, 1);
    syncBack();
  }
  function syncBack() {
    if (!tg?.BackButton) return;
    if (screenStack.length) tg.BackButton.show(); else tg.BackButton.hide();
  }
  if (tg?.BackButton) {
    tg.BackButton.onClick(() => {
      const top = screenStack[screenStack.length - 1];
      if (top) closeScreen(top);
    });
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
    const t = await r.text();
    let data; try { data = JSON.parse(t); } catch { data = { detail: t }; }
    if (!r.ok) throw new Error(data.detail || `HTTP ${r.status}`);
    return data;
  }

  // Initial dynamic-hint state.
  function refreshValueHint() {
    $("fValueHint").textContent = state.type === "percent" ? T("hint_percent") : T("hint_fixed");
  }

  async function load() {
    const list = $("list");
    list.innerHTML = `<div class="loading">${T("loading")}</div>`;
    try {
      const data = await api("GET", "/api/admin/promos");
      list.innerHTML = "";
      const active = (data.promos || []).filter(p => p.is_active);
      $("promoCount").textContent = tfmt("count", { n: active.length });
      if (!active.length) {
        list.innerHTML = `<div class="info">${T("empty")}</div>`;
        return;
      }
      active.forEach(p => list.appendChild(promoCard(p)));
    } catch (e) {
      list.innerHTML = `<div class="err">⚠️ ${escapeHtml(e.message)}</div>`;
    }
  }

  function promoCard(p) {
    const c = document.createElement("div");
    c.className = "promo-card";
    const discText = p.discount_type === "percent"
      ? tfmt("percent_label", { v: p.discount_value })
      : tfmt("fixed_label",   { v: fmt(p.discount_value) });
    const usage = p.max_uses > 0
      ? tfmt("used_max",  { u: p.used_count, m: p.max_uses })
      : tfmt("used_only", { u: p.used_count });
    const exp = p.expires_at ? `📅 ${String(p.expires_at).slice(0, 10)}` : T("no_expiry");
    c.innerHTML = `
      <div class="promo-code">${escapeHtml(p.code)}</div>
      <div class="promo-meta">
        <div class="promo-discount">${escapeHtml(discText)}</div>
        <div>${escapeHtml(usage)} • ${escapeHtml(exp)}</div>
      </div>
      <button class="promo-del" title="🗑">🗑</button>
    `;
    c.querySelector(".promo-del").onclick = async () => {
      if (!confirm(tfmt("confirm_del", { c: p.code }))) return;
      try {
        await api("POST", "/api/admin/promos/delete", { id: p.id });
        if (tg?.HapticFeedback) tg.HapticFeedback.notificationOccurred("success");
        await load();
      } catch (e) {
        alert(T("err_prefix") + e.message);
      }
    };
    return c;
  }

  $("addBtn").onclick = () => {
    $("fCode").value = ""; $("fValue").value = "10";
    $("fMax").value = "0"; $("fExpires").value = "";
    $("formErr").classList.add("hidden");
    state.type = "percent";
    document.querySelectorAll(".disc-seg .seg-btn").forEach(b => {
      b.classList.toggle("active", b.dataset.type === "percent");
    });
    refreshValueHint();
    openScreen("addScreen");
  };
  $("addBack").onclick = () => closeScreen("addScreen");

  document.querySelectorAll(".disc-seg .seg-btn").forEach(b => {
    b.onclick = () => {
      document.querySelectorAll(".disc-seg .seg-btn").forEach(x => x.classList.remove("active"));
      b.classList.add("active");
      state.type = b.dataset.type;
      refreshValueHint();
    };
  });

  function showFormErr(msg) {
    const box = $("formErr");
    box.textContent = "⚠️ " + msg;
    box.classList.remove("hidden");
    setTimeout(() => box.classList.add("hidden"), 4000);
  }

  $("saveBtn").onclick = async () => {
    const code = $("fCode").value.trim().toUpperCase();
    const value = parseInt($("fValue").value) || 0;
    const max = parseInt($("fMax").value) || 0;
    const exp = $("fExpires").value.trim();
    if (!code) return showFormErr(T("err_code"));
    if (value <= 0) return showFormErr(T("err_value"));
    if (state.type === "percent" && value > 100) return showFormErr(T("err_pct"));

    $("saveBtn").disabled = true;
    $("saveBtn").textContent = T("saving");
    try {
      await api("POST", "/api/admin/promos", {
        code, discount_type: state.type, discount_value: value,
        max_uses: max, expires_at: exp,
      });
      if (tg?.HapticFeedback) tg.HapticFeedback.notificationOccurred("success");
      closeScreen("addScreen");
      await load();
    } catch (e) {
      showFormErr(e.message);
    } finally {
      $("saveBtn").disabled = false;
      $("saveBtn").textContent = T("save_btn");
    }
  };

  refreshValueHint();
  load();
})();

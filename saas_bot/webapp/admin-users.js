/* Admin users — premium redesign. */
(() => {
  const tg = window.Telegram?.WebApp;
  if (tg) { tg.ready(); tg.expand(); }

  const url = new URL(window.location.href);
  const tenantId    = url.searchParams.get("tenant") || "tenant_001";
  const initData    = tg?.initData || "";
  const fallbackUid = parseInt(url.searchParams.get("uid") || "0") || null;
  const T = window.T;

  const $ = id => document.getElementById(id);
  const esc = s => String(s ?? "").replace(/[&<>"']/g,
    c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
  const fmt = n => new Intl.NumberFormat("uz-UZ").format(n || 0);

  let currentSort = "last_seen";
  let searchTimer = null;

  // ── sort buttons
  const SORT_IDS = { last_seen: "sLast", orders: "sOrders", spend: "sSpend" };
  window.setSort = s => {
    currentSort = s;
    Object.values(SORT_IDS).forEach(id => $(id)?.classList.remove("active"));
    $(SORT_IDS[s])?.classList.add("active");
    load($("searchInput").value.trim());
  };

  async function load(search = "") {
    const list = $("userList");
    list.innerHTML = `<div class="au-loading">${T("loading")}</div>`;
    try {
      const qs = new URLSearchParams({
        tenant: tenantId, init_data: initData,
        uid: fallbackUid || "", sort: currentSort,
      });
      if (search) qs.set("search", search);
      const r = await fetch(`/api/admin/users?${qs}`);
      const data = await r.json();
      if (!r.ok) throw new Error(data.detail || "error");
      $("totalPill").textContent = T("n_users").replace("{n}", data.total || 0);
      render(data.users || []);
    } catch (e) {
      list.innerHTML = `<div class="au-empty"><span class="au-empty-icon">⚠️</span>${esc(e.message)}</div>`;
    }
  }

  function render(users) {
    const list = $("userList");
    if (!users.length) {
      list.innerHTML = `<div class="au-empty"><span class="au-empty-icon">👤</span>${T("empty")}</div>`;
      return;
    }
    list.innerHTML = users.map(u => {
      const cnt = u.orders_count || 0;
      const spend = u.total_spend ? fmt(u.total_spend) : "—";
      const last = (u.last_seen || "").slice(0, 10);
      const hasBadge = cnt > 0 ? "has" : "";
      return `
        <div class="au-card" onclick='openDetail(${JSON.stringify(u)})'>
          <div class="au-card-stripe"></div>
          <div class="au-card-inner">
            <div class="au-card-row1">
              <div class="au-name">${esc(u.name || "—")}</div>
              <div class="au-orders-badge ${hasBadge}">${cnt} ta</div>
            </div>
            <div class="au-phone">${esc(u.phone || "—")}${u.username ? " · @" + esc(u.username) : ""}</div>
            <div class="au-meta-row">
              <div class="au-stat"><span class="au-stat-val">${spend}</span> so'm</div>
              <div class="au-stat">${T("stat_last")}: <span class="au-stat-val">${last || "—"}</span></div>
            </div>
          </div>
        </div>
      `;
    }).join("");
  }

  // ── detail sheet
  window.openDetail = async u => {
    $("sheetName").textContent = u.name || "—";
    $("sheetSub").textContent  = (u.phone || "") + (u.username ? " · @" + u.username : "");
    $("sheetOrders").textContent = u.orders_count || 0;
    $("sheetSpend").textContent  = u.total_spend ? fmt(u.total_spend) : "—";
    $("sheetLast").textContent   = (u.last_seen || "").slice(0, 10) || "—";
    $("sheetOrders_list").innerHTML = `<div class="au-loading">${T("loading")}</div>`;
    $("sheetBg").classList.remove("hidden");

    try {
      const qs = new URLSearchParams({ tenant: tenantId, init_data: initData, uid: fallbackUid || "" });
      const r = await fetch(`/api/admin/users/${u.id}/orders?${qs}`);
      const data = await r.json();
      if (!r.ok) throw new Error(data.detail || "error");
      renderOrders(data.orders || []);
    } catch (e) {
      $("sheetOrders_list").innerHTML = `<div class="au-empty">${esc(e.message)}</div>`;
    }
  };

  function renderOrders(orders) {
    const el = $("sheetOrders_list");
    if (!orders.length) {
      el.innerHTML = `<div class="au-empty"><span class="au-empty-icon">📦</span>${T("no_orders")}</div>`;
      return;
    }
    el.innerHTML = orders.map(o => {
      const st = T("status_" + o.status) || o.status;
      const date = (o.created_at || "").slice(0, 16).replace("T", " ");
      const items = (() => {
        try { return JSON.parse(o.items_json || "[]").map(i => `${i.name} ×${i.qty}`).join(", "); }
        catch { return ""; }
      })();
      return `
        <div class="au-order-row">
          <div class="au-order-row-stripe stripe-${o.status}"></div>
          <div class="au-order-top">
            <span class="au-order-id">#${o.id}</span>
            <span class="au-order-amt">${fmt(o.amount)} so'm</span>
          </div>
          <div class="au-order-meta">
            <span class="au-order-status st-${o.status}">${st}</span>
            <span style="margin-left:6px;font-size:11px">${date}</span>
          </div>
          ${items ? `<div class="au-order-items">${esc(items)}</div>` : ""}
        </div>
      `;
    }).join("");
  }

  $("sheetBg").addEventListener("click", e => {
    if (e.target === $("sheetBg")) $("sheetBg").classList.add("hidden");
  });

  $("searchInput").addEventListener("input", () => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => load($("searchInput").value.trim()), 380);
  });

  load();
})();

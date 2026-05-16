/* Admin: customer database — list with search/sort + order history modal. */
(() => {
  const tg = window.Telegram?.WebApp;
  if (tg) { tg.ready(); tg.expand(); }

  const url = new URL(window.location.href);
  const tenantId  = url.searchParams.get("tenant") || "tenant_001";
  const initData  = tg?.initData || "";
  const fallbackUid = parseInt(url.searchParams.get("uid") || "0") || null;
  const T = window.T;

  const $ = id => document.getElementById(id);
  const fmt = n => new Intl.NumberFormat("uz-UZ").format(n || 0);
  const esc = s => String(s ?? "").replace(/[&<>"']/g,
    c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));

  let allUsers = [];
  let currentSort = "last_seen";
  let searchTimer = null;

  function qs() {
    return new URLSearchParams({
      tenant: tenantId, init_data: initData,
      uid: fallbackUid || "", sort: currentSort,
    });
  }

  async function load(search = "") {
    $("loading").classList.remove("hidden");
    $("userList").innerHTML = "";
    try {
      const params = qs();
      if (search) params.set("search", search);
      const r = await fetch(`/api/admin/users?${params}`);
      const data = await r.json();
      if (!r.ok) throw new Error(data.detail || "error");
      allUsers = data.users || [];
      render(allUsers);
      $("totalSub").textContent = T("total_users").replace("{n}", fmt(data.total));
    } catch (e) {
      $("errBox").textContent = "⚠️ " + e.message;
      $("errBox").classList.remove("hidden");
    } finally {
      $("loading").classList.add("hidden");
    }
  }

  function render(users) {
    const list = $("userList");
    list.innerHTML = "";
    users.forEach(u => {
      const card = document.createElement("div");
      card.className = "user-card";
      const lastDate = u.last_seen ? u.last_seen.slice(0, 10) : "—";
      const spend = u.total_spend ? fmt(u.total_spend) + " so'm" : "—";
      card.innerHTML = `
        <div class="user-card-top">
          <div class="user-name">${esc(u.name || "—")}</div>
          <span class="user-badge">${u.orders_count || 0} ta</span>
        </div>
        <div class="user-phone">${esc(u.phone || "—")}${u.username ? " · @" + esc(u.username) : ""}</div>
        <div class="user-meta">
          <div class="user-stat"><strong>${spend}</strong> ${T("spend_label")}</div>
          <div class="user-stat">${T("last_label")}: ${lastDate}</div>
        </div>
      `;
      card.onclick = () => openDetail(u);
      list.appendChild(card);
    });
    if (!users.length) {
      list.innerHTML = `<div class="info" style="margin:32px auto;text-align:center">—</div>`;
    }
  }

  async function openDetail(u) {
    $("detailName").textContent = u.name || "—";
    $("detailSub").textContent = (u.phone || "") + (u.username ? " · @" + u.username : "");
    $("detailOrders").innerHTML = `<div class="loading">${T("loading_orders")}</div>`;
    $("detailBg").classList.remove("hidden");
    try {
      const params = new URLSearchParams({ tenant: tenantId, init_data: initData, uid: fallbackUid || "" });
      const r = await fetch(`/api/admin/users/${u.id}/orders?${params}`);
      const data = await r.json();
      if (!r.ok) throw new Error(data.detail || "error");
      renderOrders(data.orders || []);
    } catch (e) {
      $("detailOrders").innerHTML = `<div class="err">${esc(e.message)}</div>`;
    }
  }

  function renderOrders(orders) {
    const container = $("detailOrders");
    if (!orders.length) {
      container.innerHTML = `<div class="info" style="text-align:center;padding:20px">${T("no_orders")}</div>`;
      return;
    }
    container.innerHTML = orders.map(o => {
      const st = T("status_" + o.status) || o.status;
      const date = (o.created_at || "").slice(0, 16).replace("T", " ");
      const items = (() => {
        try { return JSON.parse(o.items_json || "[]").map(i => `${i.name} x${i.qty}`).join(", "); }
        catch { return ""; }
      })();
      return `
        <div class="order-row">
          <div class="order-row-top">
            <span class="order-id">#${o.id}</span>
            <span class="order-amt">${fmt(o.amount)} so'm</span>
          </div>
          <div class="order-row-sub">${st} · ${date}</div>
          ${items ? `<div class="order-row-sub" style="margin-top:4px">${esc(items)}</div>` : ""}
        </div>
      `;
    }).join("");
  }

  window.closeDetail = () => $("detailBg").classList.add("hidden");

  window.setSort = (s) => {
    currentSort = s;
    ["sortLast","sortOrders","sortSpend"].forEach(id => $( id).classList.remove("active"));
    const map = { last_seen:"sortLast", orders:"sortOrders", spend:"sortSpend" };
    if (map[s]) $(map[s]).classList.add("active");
    load($("searchInput").value.trim());
  };

  $("searchInput").addEventListener("input", () => {
    clearTimeout(searchTimer);
    searchTimer = setTimeout(() => load($("searchInput").value.trim()), 400);
  });

  $("detailBg").addEventListener("click", e => {
    if (e.target === $("detailBg")) closeDetail();
  });

  load();
})();

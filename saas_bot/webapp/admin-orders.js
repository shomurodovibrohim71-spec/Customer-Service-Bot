/* Admin orders dashboard: status tabs + search + detail screen with actions. */
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

  const $ = (id) => document.getElementById(id);
  const escapeHtml = (s) => String(s ?? "").replace(/[&<>"']/g,
    c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const fmt = (n) => new Intl.NumberFormat("uz-UZ").format(n || 0) + " " + T("soum");
  const fmtDate = (iso) => (iso || "").replace("T", " ").slice(0, 16);

  const state = { status: "all", search: "", all: [] };
  const screenStack = [];
  function openScreen(id) { $(id).classList.remove("hidden"); screenStack.push(id); syncBack(); }
  function closeScreen(id) {
    $(id).classList.add("hidden");
    const i = screenStack.lastIndexOf(id); if (i >= 0) screenStack.splice(i, 1);
    syncBack();
  }
  function syncBack() {
    if (!tg?.BackButton) return;
    screenStack.length ? tg.BackButton.show() : tg.BackButton.hide();
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
    const txt = await r.text();
    let data; try { data = JSON.parse(txt); } catch { data = { detail: txt }; }
    if (!r.ok) throw new Error(data.detail || r.status);
    return data;
  }

  function statusBadge(s) {
    const cls = {
      pending:   "bdg-pending",
      confirmed: "bdg-answered",
      delivered: "bdg-delivered",
      cancelled: "bdg-cancelled",
    }[s] || "bdg-pending";
    return `<span class="fb-bdg ${cls}">${T("status_" + s, s)}</span>`;
  }
  function payBadge(p) {
    return `<span class="ord-pay">${p === 'card' ? T('pay_card') : T('pay_cash')}</span>`;
  }
  function userTag(o) {
    if (o.username) return ` · <a class="fb-uname" href="https://t.me/${escapeHtml(o.username)}" target="_blank">@${escapeHtml(o.username)}</a>`;
    return "";
  }

  // ----- Tabs ----------------------------------------------------------
  document.querySelectorAll("#ordTabs .ao-tab").forEach(btn => {
    btn.onclick = () => {
      state.status = btn.dataset.st;
      document.querySelectorAll("#ordTabs .ao-tab").forEach(b => b.classList.toggle("active", b === btn));
      load();
    };
  });

  $("searchInput").addEventListener("input", () => {
    state.search = $("searchInput").value.trim().toLowerCase();
    renderList();
  });

  // ----- Load + render -------------------------------------------------
  async function load() {
    const list = $("list");
    list.innerHTML = `<div class="loading">${T("loading")}</div>`;
    try {
      // 'today' and 'all' both fetch the full list — we filter client-side
      // by created_at for 'today'. Only real status values go to the API.
      const st = (state.status === "all" || state.status === "today") ? "" : state.status;
      const qs = new URLSearchParams({
        tenant: tenantId, init_data: initData, uid: fallbackUid || "",
        status: st, limit: 300,
      });
      const data = await api("GET", "/api/admin/orders?" + qs);
      const c = data.counts || {};
      const setCount = (id, val) => { const el = $(id); if (el) el.textContent = val; };
      setCount("cnt_all",       c.total     || 0);
      setCount("cnt_confirmed", c.confirmed || 0);
      setCount("cnt_delivered", c.delivered || 0);
      setCount("cnt_cancelled", c.cancelled || 0);
      state.all = data.orders || [];
      // Today's count is computed on the client from the full list.
      const t = todayStr();
      const todayCount = state.all.filter(o => (o.created_at || "").startsWith(t)).length;
      const cntToday = $("cnt_today");
      if (cntToday) cntToday.textContent = todayCount;
      $("totalCount").textContent = tfmt("total_short", { n: state.all.length });
      renderList();
    } catch (e) {
      list.innerHTML = `<div class="err">⚠️ ${escapeHtml(e.message)}</div>`;
    }
  }

  function renderList() {
    const list = $("list");
    list.innerHTML = "";
    let items = state.all;
    if (state.status === "today") {
      const t = todayStr();
      items = items.filter(o => (o.created_at || "").startsWith(t));
    }
    if (state.search) {
      items = items.filter(o =>
        String(o.id).includes(state.search) ||
        (o.phone || "").toLowerCase().includes(state.search) ||
        (o.username || "").toLowerCase().includes(state.search)
      );
    }
    if (!items.length) {
      list.innerHTML = `<div class="ao-empty"><div class="ao-empty-icon">📋</div>${T("empty")}</div>`;
      return;
    }
    items.forEach(o => list.appendChild(card(o)));
  }

  function statusClass(s) {
    return { pending: "st-pending", confirmed: "st-confirmed", preparing: "st-preparing", on_the_way: "st-on_the_way", delivered: "st-delivered", cancelled: "st-cancelled" }[s] || "st-pending";
  }
  function stripeClass(s) {
    return { pending: "stripe-pending", confirmed: "stripe-confirmed", preparing: "stripe-preparing", on_the_way: "stripe-on_the_way", delivered: "stripe-delivered", cancelled: "stripe-cancelled" }[s] || "stripe-pending";
  }

  function card(o) {
    const el = document.createElement("article");
    el.className = "ao-card";

    const itemsList = (o.items || []).slice(0, 3);
    const chipsHtml = itemsList.length
      ? itemsList.map(it =>
          `<span class="ao-chip"><span>${escapeHtml(it.name)}</span><span class="ao-chip-qty">×${it.qty}</span></span>`
        ).join("")
      : `<span class="ao-chip">${escapeHtml(o.service || "—")}</span>`;
    const moreChip = (o.items || []).length > 3
      ? `<span class="ao-chip ao-chip-more">+${o.items.length - 3}</span>` : "";

    const quickBtns = o.status === "pending"
      ? `<div class="ao-quick-actions">
           <button class="ao-qa-btn ao-qa-confirm qa-confirm">${T("act_confirm")}</button>
           <button class="ao-qa-btn ao-qa-cancel qa-cancel">${T("act_cancel")}</button>
         </div>`
      : o.status === "confirmed"
      ? `<div class="ao-quick-actions">
           <button class="ao-qa-btn ao-qa-prepare qa-prepare">${T("act_prepare")}</button>
           <button class="ao-qa-btn ao-qa-cancel qa-cancel">${T("act_cancel")}</button>
         </div>`
      : o.status === "preparing"
      ? `<div class="ao-quick-actions">
           <button class="ao-qa-btn ao-qa-on-way qa-on-way">${T("act_on_way")}</button>
           <button class="ao-qa-btn ao-qa-cancel qa-cancel">${T("act_cancel")}</button>
         </div>`
      : o.status === "on_the_way"
      ? `<div class="ao-quick-actions">
           <button class="ao-qa-btn ao-qa-deliver qa-deliver">${T("act_delivered")}</button>
           <button class="ao-qa-btn ao-qa-cancel qa-cancel">${T("act_cancel")}</button>
         </div>`
      : "";

    el.innerHTML = `
      <div class="ao-card-stripe ${stripeClass(o.status)}"></div>
      <div class="ao-card-inner">
        <div class="ao-card-head">
          <div>
            <div class="ao-card-id-wrap">
              <span class="ao-card-id">#${o.id}</span>
              <span class="ao-card-date">${escapeHtml(fmtDate(o.created_at))}</span>
            </div>
          </div>
          <span class="ao-status ${statusClass(o.status)}">${T("status_" + o.status, o.status)}</span>
        </div>

        <div class="ao-card-user">
          <span class="ao-card-name">${escapeHtml(o.full_name || "id" + o.user_id)}</span>
          ${o.username ? `<span class="ao-card-uname">@${escapeHtml(o.username)}</span>` : ""}
          ${o.phone ? `<a href="tel:${escapeHtml(o.phone)}" class="ao-card-phone">📞 ${escapeHtml(o.phone)}</a>` : ""}
        </div>

        ${o.address ? `<div class="ao-card-addr">📍 ${escapeHtml(o.address)}</div>` : ""}

        <div class="ao-chips">${chipsHtml}${moreChip}</div>

        <div class="ao-card-foot">
          <strong class="ao-card-total">${fmt(o.amount)}</strong>
          <span class="ao-pay-badge">${o.payment_method === "card" ? T("pay_card") : T("pay_cash")}</span>
          <button class="ao-open-btn">${T("view_details")}</button>
        </div>

        ${quickBtns}
      </div>
    `;

    el.querySelector(".ao-open-btn").onclick = (e) => { e.stopPropagation(); openDetail(o.id); };
    const wireQuick = (cls, status, confirmKey) => {
      const btn = el.querySelector(cls);
      if (!btn) return;
      btn.onclick = async (e) => {
        e.stopPropagation();
        if (confirmKey && !confirm(tfmt(confirmKey, { id: o.id }))) return;
        btn.disabled = true;
        try {
          await api("POST", "/api/admin/orders/status", { order_id: o.id, status });
          if (tg?.HapticFeedback) tg.HapticFeedback.notificationOccurred("success");
          await load();
        } catch (err) { alert("⚠️ " + err.message); btn.disabled = false; }
      };
    };
    wireQuick(".qa-confirm", "confirmed");
    wireQuick(".qa-prepare", "preparing");
    wireQuick(".qa-on-way",  "on_the_way");
    wireQuick(".qa-deliver", "delivered");
    wireQuick(".qa-cancel",  "cancelled", "confirm_cancel");
    return el;
  }

  function todayStr() {
    const d = new Date();
    const p = (n) => String(n).padStart(2, "0");
    return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`;
  }

  // ----- Detail screen -------------------------------------------------
  async function openDetail(id) {
    state.currentId = id;
    $("detailTitle").textContent = "#" + id;
    $("detailErr").classList.add("hidden");
    $("detailBody").innerHTML = `<div class="loading">${T("loading")}</div>`;
    openScreen("detailScreen");

    const o = state.all.find(x => x.id === id);
    if (!o) {
      // Fallback: refetch and find
      await load();
      const o2 = state.all.find(x => x.id === id);
      if (!o2) { $("detailBody").innerHTML = `<div class="err">⚠️ not found</div>`; return; }
      renderDetail(o2);
    } else {
      renderDetail(o);
    }
  }

  function renderDetail(o) {
    const itemsHtml = (o.items || []).map(it =>
      `<div class="ao-item-row">
         <span class="ao-item-name">${escapeHtml(it.name)}</span>
         <span class="ao-item-qty">${tfmt("x_qty", { q: it.qty })}</span>
         <span class="ao-item-price">${fmt(it.price * it.qty)}</span>
       </div>`
    ).join("") || `<div class="ao-detail-row"><span class="ao-detail-val">${escapeHtml(o.service || "—")}</span></div>`;

    const row = (key, val) => val
      ? `<div class="ao-detail-row"><span class="ao-detail-key">${T(key)}</span><span class="ao-detail-val">${val}</span></div>`
      : "";

    let actionsHtml = "";
    if (o.status === "pending") {
      actionsHtml = `
        <button class="primary-btn act-confirm">${T("act_confirm")}</button>
        <button class="ghost-btn act-cancel" style="border-color:var(--danger);color:var(--danger)">${T("act_cancel")}</button>`;
    } else if (o.status === "confirmed") {
      actionsHtml = `
        <button class="primary-btn act-prepare">${T("act_prepare")}</button>
        <button class="ghost-btn act-cancel" style="border-color:var(--danger);color:var(--danger)">${T("act_cancel")}</button>`;
    } else if (o.status === "preparing") {
      actionsHtml = `
        <button class="primary-btn act-on-way">${T("act_on_way")}</button>
        <button class="ghost-btn act-cancel" style="border-color:var(--danger);color:var(--danger)">${T("act_cancel")}</button>`;
    } else if (o.status === "on_the_way") {
      actionsHtml = `
        <button class="primary-btn act-delivered">${T("act_delivered")}</button>
        <button class="ghost-btn act-cancel" style="border-color:var(--danger);color:var(--danger)">${T("act_cancel")}</button>`;
    }

    const bldg = [
      o.entrance  ? `Podyez: ${escapeHtml(o.entrance)}`  : "",
      o.floor     ? `Qavat: ${escapeHtml(o.floor)}`      : "",
      o.apartment ? `Xon.: ${escapeHtml(o.apartment)}`   : "",
      o.intercom  ? `Domofon: ${escapeHtml(o.intercom)}` : "",
    ].filter(Boolean).join(" · ");

    $("detailBody").innerHTML = `
      <!-- Status banner -->
      <div class="ao-detail-section">
        <div class="ao-detail-row" style="align-items:center">
          <span class="ao-status ${statusClass(o.status)}" style="padding:5px 12px;font-size:13px">${T("status_" + o.status, o.status)}</span>
          <span style="color:var(--text-muted);font-size:12px;margin-left:auto">${escapeHtml(fmtDate(o.created_at))}</span>
        </div>
      </div>

      <!-- Customer -->
      <div class="ao-detail-section">
        <div class="ao-detail-section-head">👤 ${T("lbl_customer")}</div>
        ${row("lbl_customer", escapeHtml(o.full_name || "id" + o.user_id) + (o.username ? ` <a class="fb-uname" href="https://t.me/${escapeHtml(o.username)}" target="_blank">@${escapeHtml(o.username)}</a>` : ""))}
        <div class="ao-detail-row">
          <span class="ao-detail-key">${T("lbl_phone")}</span>
          <span class="ao-detail-val"><a href="tel:${escapeHtml(o.phone)}" class="ao-card-phone">${escapeHtml(o.phone || "—")}</a></span>
        </div>
      </div>

      <!-- Items -->
      <div class="ao-items-section">
        <div class="ao-detail-section-head">${T("lbl_items")}</div>
        ${itemsHtml}
        ${o.discount > 0 ? `
          <div class="ao-item-row" style="border-top:1px solid var(--line)">
            <span class="ao-item-name" style="color:var(--text-muted)">${T("lbl_discount")}${o.promo_code ? " · " + escapeHtml(o.promo_code) : ""}</span>
            <span class="ao-item-price" style="color:var(--success)">− ${fmt(o.discount)}</span>
          </div>` : ""}
        <div class="ao-total-row">
          <span>${T("lbl_total")}</span>
          <strong>${fmt(o.amount)}</strong>
        </div>
      </div>

      <!-- Delivery & Payment -->
      <div class="ao-detail-section">
        <div class="ao-detail-section-head">🚚 ${T("lbl_delivery")} / 💳 ${T("lbl_payment")}</div>
        ${row("lbl_branch",  escapeHtml(o.branch || "—"))}
        ${row("lbl_address", escapeHtml(o.address || "—"))}
        ${bldg ? `<div class="ao-detail-row"><span class="ao-detail-key">🏠</span><span class="ao-detail-val" style="color:var(--text-muted)">${bldg}</span></div>` : ""}
        ${row("lbl_time",    escapeHtml(o.preferred_time || "—"))}
        <div class="ao-detail-row">
          <span class="ao-detail-key">${T("lbl_payment")}</span>
          <span class="ao-detail-val">${o.payment_method === "card" ? T("pay_card") : T("pay_cash")}</span>
        </div>
      </div>

      ${o.courier_note || o.note ? `
        <div class="ao-detail-section">
          <div class="ao-detail-section-head">💬 Eslatmalar</div>
          ${o.courier_note ? `<div class="ao-detail-row"><span class="ao-detail-key">${T("lbl_note_courier")}</span><span class="ao-detail-val">${escapeHtml(o.courier_note)}</span></div>` : ""}
          ${o.note         ? `<div class="ao-detail-row"><span class="ao-detail-key">${T("lbl_note_rest")}</span><span class="ao-detail-val">${escapeHtml(o.note)}</span></div>` : ""}
        </div>` : ""}

      ${actionsHtml ? `<div class="ao-detail-actions">${actionsHtml}</div>` : ""}
    `;

    const setAct = (cls, status, confirmKey) => {
      const btn = $("detailBody").querySelector(cls);
      if (!btn) return;
      btn.onclick = async () => {
        if (confirmKey && !confirm(tfmt(confirmKey, { id: o.id }))) return;
        btn.disabled = true;
        try {
          await api("POST", "/api/admin/orders/status", { order_id: o.id, status });
          if (tg?.HapticFeedback) tg.HapticFeedback.notificationOccurred("success");
          await load();
          const fresh = state.all.find(x => x.id === o.id);
          if (fresh) renderDetail(fresh);
        } catch (e) {
          const errEl = $("detailErr");
          if (errEl) { errEl.textContent = "⚠️ " + e.message; errEl.classList.remove("hidden"); }
        } finally { btn.disabled = false; }
      };
    };
    setAct(".act-confirm",   "confirmed");
    setAct(".act-prepare",   "preparing");
    setAct(".act-on-way",    "on_the_way");
    setAct(".act-delivered", "delivered");
    setAct(".act-cancel",    "cancelled", "confirm_cancel");
  }

  $("detailBack").onclick = () => closeScreen("detailScreen");

  load();
})();

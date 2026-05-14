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
  document.querySelectorAll("#ordTabs .tab").forEach(btn => {
    btn.onclick = () => {
      state.status = btn.dataset.st;
      document.querySelectorAll("#ordTabs .tab").forEach(b => b.classList.toggle("active", b === btn));
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
      $("cnt_all").textContent = c.total || 0;
      $("cnt_pending").textContent = c.pending || 0;
      $("cnt_confirmed").textContent = c.confirmed || 0;
      $("cnt_delivered").textContent = c.delivered || 0;
      $("cnt_cancelled").textContent = c.cancelled || 0;
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
      list.innerHTML = `<div class="info">${T("empty")}</div>`;
      return;
    }
    items.forEach(o => list.appendChild(card(o)));
  }

  function card(o) {
    const c = document.createElement("article");
    c.className = "ord-card";
    // Build the items preview from already-parsed items (escape once, inside the map).
    const itemsList = (o.items || []).slice(0, 3);
    const itemsHtml = itemsList.length
      ? itemsList.map(it => `<span class="ord-item-chip"><span class="chip-name">${escapeHtml(it.name)}</span><span class="chip-qty">×${it.qty}</span></span>`).join("")
      : `<span class="ord-item-chip"><span class="chip-name">${escapeHtml(o.service || "—")}</span></span>`;
    const more = (o.items || []).length > 3
      ? `<span class="ord-item-chip more">+${o.items.length - 3}</span>` : "";

    c.innerHTML = `
      <div class="ord-head">
        <div class="ord-head-left">
          <div class="ord-id">#${o.id}</div>
          <div class="ord-date">📅 ${escapeHtml(fmtDate(o.created_at))}</div>
        </div>
        ${statusBadge(o.status)}
      </div>

      <div class="ord-user-line">
        <span class="ord-name">${escapeHtml(o.full_name || ("id" + o.user_id))}</span>
        ${userTag(o)}
      </div>

      <div class="ord-contact">
        ${o.phone ? `<a href="tel:${escapeHtml(o.phone)}" class="ord-phone">📞 ${escapeHtml(o.phone)}</a>` : ""}
        ${payBadge(o.payment_method)}
      </div>

      <div class="ord-addr-row">📍 ${escapeHtml(o.address || "—")}</div>

      <div class="ord-chips">${itemsHtml}${more}</div>

      <div class="ord-foot">
        <div class="ord-total-wrap">
          <span class="ord-total-lbl">${T("lbl_total")}</span>
          <strong class="ord-total">${fmt(o.amount)}</strong>
        </div>
        <button class="primary-btn ord-open">${T("view_details")}</button>
      </div>
    `;
    c.querySelector(".ord-open").onclick = () => openDetail(o.id);
    return c;
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
      `<div class="ord-item-row"><span>${escapeHtml(it.name)}</span><span class="muted">${tfmt("x_qty", { q: it.qty })}</span><strong>${fmt(it.price * it.qty)}</strong></div>`
    ).join("");
    const discountRow = o.discount > 0
      ? `<div class="ord-row"><span>${T("lbl_discount")}${o.promo_code ? " · " + escapeHtml(o.promo_code) : ""}</span><strong style="color:var(--success)">− ${fmt(o.discount)}</strong></div>`
      : "";
    const usernameLine = o.username
      ? `<a class="fb-uname" href="https://t.me/${escapeHtml(o.username)}" target="_blank">@${escapeHtml(o.username)}</a>`
      : "";

    let actions = "";
    if (o.status === "pending") {
      actions = `
        <button class="primary-btn act-confirm">${T("act_confirm")}</button>
        <button class="ghost-btn act-cancel" style="border-color:var(--danger);color:var(--danger)">${T("act_cancel")}</button>
      `;
    } else if (o.status === "confirmed") {
      actions = `
        <button class="primary-btn act-delivered">${T("act_delivered")}</button>
        <button class="ghost-btn act-cancel" style="border-color:var(--danger);color:var(--danger)">${T("act_cancel")}</button>
      `;
    }

    $("detailBody").innerHTML = `
      <div class="ord-detail-block">
        <div class="ord-row ord-status-line">${statusBadge(o.status)} <span class="muted">${T("lbl_placed")}: ${escapeHtml(fmtDate(o.created_at))}</span></div>
      </div>

      <section class="dash-section">
        <h3>${T("lbl_customer")}</h3>
        <div class="ord-detail-block">
          <div class="ord-row">👤 ${escapeHtml(o.full_name || "id" + o.user_id)} ${usernameLine}</div>
          <div class="ord-row">📞 <a href="tel:${escapeHtml(o.phone)}" class="fb-phone">${escapeHtml(o.phone || "—")}</a></div>
        </div>
      </section>

      <section class="dash-section">
        <h3>${T("lbl_items")}</h3>
        <div class="ord-items-list">${itemsHtml || `<div class="info">${escapeHtml(o.service || "—")}</div>`}</div>
        <div class="ord-row" style="margin-top:8px">
          <span>${T("lbl_total")}</span>
          <strong style="color:var(--brand)">${fmt(o.amount)}</strong>
        </div>
        ${discountRow}
        <div class="ord-row"><span>${T("lbl_payment")}</span> ${payBadge(o.payment_method)}</div>
      </section>

      <section class="dash-section">
        <h3>📍 ${T("lbl_address")} / ${T("lbl_branch")}</h3>
        <div class="ord-detail-block">
          <div class="ord-row">${T("lbl_branch")}: <strong>${escapeHtml(o.branch || "—")}</strong></div>
          <div class="ord-row">${T("lbl_address")}: <strong>${escapeHtml(o.address || "—")}</strong></div>
          ${o.entrance || o.floor || o.apartment || o.intercom ? `
            <div class="ord-row ord-bldg">
              🏠 ${o.entrance  ? `<span>Podyez: <strong>${escapeHtml(o.entrance)}</strong></span>`  : ""}
                  ${o.floor     ? `<span>Qavat: <strong>${escapeHtml(o.floor)}</strong></span>`     : ""}
                  ${o.apartment ? `<span>Xon.: <strong>${escapeHtml(o.apartment)}</strong></span>`  : ""}
                  ${o.intercom  ? `<span>Domofon: <strong>${escapeHtml(o.intercom)}</strong></span>` : ""}
            </div>` : ""}
          <div class="ord-row">${T("lbl_time")}: <strong>${escapeHtml(o.preferred_time || "—")}</strong></div>
        </div>
      </section>

      ${o.courier_note || o.note ? `
        <section class="dash-section">
          <h3>💬 Eslatmalar</h3>
          <div class="ord-detail-block">
            ${o.courier_note ? `<div class="ord-note"><span class="ord-note-tag">🚗 Kuryerga</span><div>${escapeHtml(o.courier_note)}</div></div>` : ""}
            ${o.note         ? `<div class="ord-note"><span class="ord-note-tag">🍴 Restoranga</span><div>${escapeHtml(o.note)}</div></div>` : ""}
          </div>
        </section>` : ""}

      ${actions ? `<div class="ord-actions">${actions}</div>` : ""}
    `;

    const setAct = (cls, status, confirmKey) => {
      const btn = $("detailBody").querySelector(cls);
      if (!btn) return;
      btn.onclick = async () => {
        if (confirmKey && !confirm(tfmt(confirmKey, { id: o.id }))) return;
        btn.disabled = true;
        try {
          await api("POST", "/api/admin/orders/status", {
            order_id: o.id, status,
          });
          if (tg?.HapticFeedback) tg.HapticFeedback.notificationOccurred("success");
          await load();
          // Reflect the new status in the open detail.
          const fresh = state.all.find(x => x.id === o.id);
          if (fresh) renderDetail(fresh);
        } catch (e) {
          $("detailErr").textContent = "⚠️ " + e.message;
          $("detailErr").classList.remove("hidden");
        } finally {
          btn.disabled = false;
        }
      };
    };
    setAct(".act-confirm",   "confirmed");
    setAct(".act-delivered", "delivered");
    setAct(".act-cancel",    "cancelled", "confirm_cancel");
  }

  $("detailBack").onclick = () => closeScreen("detailScreen");

  load();
})();

/* Admin dashboard: revenue, orders, top products, peak hours. */
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
  const fmt = (n) => new Intl.NumberFormat("uz-UZ").format(n || 0) + " " + T("soum");
  const fmtN = (n) => new Intl.NumberFormat("uz-UZ").format(n || 0);
  const escapeHtml = (s) => String(s ?? "").replace(/[&<>"']/g,
    c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const tfmt = (key, vars) => {
    let s = T(key);
    for (const [k, v] of Object.entries(vars || {})) s = s.replace("{" + k + "}", v);
    return s;
  };

  function statusLabel(s) {
    return T("status_" + s, s);
  }

  function showErr(msg) {
    $("loading").classList.add("hidden");
    const box = $("errBox");
    box.textContent = "⚠️ " + msg;
    box.classList.remove("hidden");
  }

  async function load() {
    try {
      const qs = new URLSearchParams({
        tenant: tenantId, init_data: initData, uid: fallbackUid || "", days: 7,
      });
      const r = await fetch(`/api/admin/stats?${qs}`);
      const data = await r.json();
      if (!r.ok) throw new Error(data.detail || T("loading"));
      render(data);
    } catch (e) {
      showErr(e.message);
    }
  }

  function render(d) {
    $("loading").classList.add("hidden");
    $("statsSub").textContent = d.tenant_name || tenantId;

    const oc = (n) => tfmt("orders_count", { n: fmtN(n) });
    $("mRevTotal").textContent  = fmt(d.month_revenue);
    $("mOrdTotal").textContent  = oc(d.month_orders);
    $("mRevToday").textContent  = fmt(d.today_revenue);
    $("mOrdToday").textContent  = oc(d.today_orders);
    $("mRevWeek").textContent   = fmt(d.week_revenue);
    $("mOrdWeek").textContent   = oc(d.week_orders);
    $("mUsers").textContent     = fmtN(d.users_total);
    $("mUsersToday").textContent = tfmt("users_today", { n: fmtN(d.users_today) });
    $("metrics").classList.remove("hidden");

    // --- Daily bar chart -------------------------------------------------
    const chart = $("barChart");
    chart.innerHTML = "";
    const dayShort = T("day_short");  // array
    if (!d.daily.length) {
      chart.innerHTML = `<div class="info" style="flex:1">${T("no_orders_yet")}</div>`;
    } else {
      const max = Math.max(...d.daily.map(x => x.revenue), 1);
      d.daily.forEach(row => {
        const dt = new Date(row.day + "T00:00:00");
        const label = (dayShort[dt.getDay()] || "") + " " + dt.getDate();
        const pct = Math.round((row.revenue / max) * 100);
        const col = document.createElement("div");
        col.className = "bar-col";
        col.innerHTML = `
          <div class="bar-value">${row.revenue ? Math.round(row.revenue/1000) + "k" : ""}</div>
          <div class="bar-fill ${row.revenue ? '' : 'empty'}" style="height:${pct}%"></div>
          <div class="bar-label">${escapeHtml(label)}</div>
        `;
        chart.appendChild(col);
      });
    }
    $("chartSection").classList.remove("hidden");

    // --- Top products ----------------------------------------------------
    const tl = $("topList");
    tl.innerHTML = "";
    if (!d.top_products.length) {
      tl.innerHTML = `<div class="info">${T("no_products_yet")}</div>`;
    } else {
      d.top_products.forEach((p, i) => {
        const row = document.createElement("div");
        row.className = "top-row";
        row.innerHTML = `
          <span class="top-rank">${i + 1}</span>
          <span class="top-name">${escapeHtml(p.name)}</span>
          <span class="top-qty">${fmtN(p.qty)} ${T("qty_suffix")}</span>
        `;
        tl.appendChild(row);
      });
    }
    $("topSection").classList.remove("hidden");

    // --- Peak hours ------------------------------------------------------
    const hr = $("hoursRow");
    hr.innerHTML = "";
    const hmax = Math.max(...d.peak_hours, 1);
    d.peak_hours.forEach((cnt, h) => {
      const div = document.createElement("div");
      const showLabel = h % 3 === 0;
      div.className = "h" + (cnt > 0 ? " has" : "");
      div.style.opacity = cnt > 0 ? (0.35 + 0.65 * (cnt / hmax)) : 0.25;
      div.title = `${h}:00 — ${cnt}`;
      if (showLabel) div.dataset.h = h;
      hr.appendChild(div);
    });
    $("hoursSection").classList.remove("hidden");

    // --- Status breakdown ------------------------------------------------
    const sl = $("statusList");
    sl.innerHTML = "";
    const entries = Object.entries(d.by_status || {});
    if (!entries.length) {
      sl.innerHTML = `<div class="info">${T("no_orders")}</div>`;
    } else {
      entries.forEach(([st, n], i) => {
        const row = document.createElement("div");
        row.className = "top-row";
        row.innerHTML = `
          <span class="top-rank">${i + 1}</span>
          <span class="top-name">${escapeHtml(statusLabel(st))}</span>
          <span class="top-qty">${fmtN(n)} ${T("qty_suffix")}</span>
        `;
        sl.appendChild(row);
      });
    }
    $("statusSection").classList.remove("hidden");
  }

  load();
})();

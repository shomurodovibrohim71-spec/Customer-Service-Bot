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

    // --- Daily bar chart (Chart.js) --------------------------------------
    const dayShort = T("day_short");
    const dailyLabels = d.daily.map(r => {
      const dt = new Date(r.day + "T00:00:00");
      return (dayShort[dt.getDay()] || "") + " " + dt.getDate();
    });
    const dailyRevenue = d.daily.map(r => r.revenue);
    const maxRev = Math.max(...dailyRevenue, 1);
    const todayStr = new Date().toISOString().slice(0, 10);
    const dailyColors = d.daily.map(r =>
      r.day === todayStr ? "#ff7a18" : "rgba(255,122,24,0.45)"
    );
    if (window._dailyChart) window._dailyChart.destroy();
    window._dailyChart = new Chart($("barChart"), {
      type: "bar",
      data: {
        labels: dailyLabels,
        datasets: [{
          data: dailyRevenue,
          backgroundColor: dailyColors,
          borderRadius: 6,
          borderSkipped: false,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: (ctx) => {
                const v = ctx.parsed.y;
                const row = d.daily[ctx.dataIndex];
                return [
                  ` ${new Intl.NumberFormat("uz-UZ").format(v)} so'm`,
                  ` ${row.count} ta buyurtma`,
                ];
              },
            },
          },
        },
        scales: {
          x: {
            grid: { display: false },
            border: { display: false },
            ticks: { color: "rgba(255,255,255,0.5)", font: { size: 11, weight: "600" } },
          },
          y: {
            beginAtZero: true,
            grid: { color: "rgba(255,255,255,0.06)" },
            border: { display: false },
            ticks: {
              color: "rgba(255,255,255,0.35)",
              font: { size: 10 },
              callback: (v) => v === 0 ? "0" : Math.round(v / 1000) + "k",
            },
          },
        },
      },
    });
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

    // --- Revenue by category chart ------------------------------------
    if ((d.cat_revenue || []).length) {
      const cr = d.cat_revenue;
      const crLabels = cr.map(x => x.category.length > 20 ? x.category.slice(0, 19) + "…" : x.category);
      const crData   = cr.map(x => x.revenue);
      const crMax    = Math.max(...crData, 1);
      const crColors = crData.map(v => `rgba(255,122,24,${(0.25 + 0.75 * v / crMax).toFixed(2)})`);
      const chartH   = Math.max(160, cr.length * 36);
      $("catRevChartWrap").style.height = chartH + "px";
      if (window._catRevChart) window._catRevChart.destroy();
      window._catRevChart = new Chart($("catRevChart"), {
        type: "bar",
        data: {
          labels: crLabels,
          datasets: [{
            data: crData,
            backgroundColor: crColors,
            borderRadius: 6,
            borderSkipped: false,
          }],
        },
        options: {
          indexAxis: "y",
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { display: false },
            tooltip: {
              callbacks: {
                label: ctx => ` ${new Intl.NumberFormat("uz-UZ").format(ctx.parsed.x)} so'm`,
              },
            },
          },
          scales: {
            x: {
              beginAtZero: true,
              grid: { color: "rgba(255,255,255,0.06)" },
              border: { display: false },
              ticks: {
                color: "rgba(255,255,255,0.35)",
                font: { size: 10 },
                callback: v => v === 0 ? "0" : Math.round(v / 1000) + "k",
              },
            },
            y: {
              grid: { display: false },
              border: { display: false },
              ticks: { color: "rgba(255,255,255,0.75)", font: { size: 12, weight: "600" } },
            },
          },
        },
      });
      $("catRevSection").classList.remove("hidden");
    }

    // --- Repeat customers --------------------------------------------
    const rc = d.repeat_customers || { total: 0, repeat: 0, pct: 0 };
    if (rc.total > 0) {
      const box = $("repeatStats");
      box.innerHTML = `
        <div class="repeat-wrap">
          <div class="repeat-big">${rc.pct}%</div>
          <div class="repeat-right">
            <div class="repeat-label">${rc.repeat} ${T("repeat_of")} ${rc.total} ${T("repeat_buyers")}</div>
            <div class="repeat-bar-wrap">
              <div class="repeat-bar" style="width:${rc.pct}%"></div>
            </div>
            <div class="repeat-sub">2 yoki undan ko'p buyurtma bergan mijozlar</div>
          </div>
        </div>
      `;
      $("repeatSection").classList.remove("hidden");
    }

    // --- Bottom (least sold) products chart ------------------------------
    if ((d.bottom_products || []).length) {
      const bp = d.bottom_products;
      const bNames  = bp.map(p => p.name.length > 18 ? p.name.slice(0, 17) + "…" : p.name);
      const bCounts = bp.map(p => p.qty);
      const bColors = bp.map(p =>
        p.qty === 0 ? "rgba(107,114,128,0.45)" : "rgba(248,113,113,0.55)"
      );
      const bHover = bp.map(p =>
        p.qty === 0 ? "rgba(107,114,128,0.7)" : "rgba(248,113,113,0.8)"
      );
      if (window._bottomChart) window._bottomChart.destroy();
      window._bottomChart = new Chart($("bottomChart"), {
        type: "bar",
        data: {
          labels: bNames,
          datasets: [{
            data: bCounts,
            backgroundColor: bColors,
            hoverBackgroundColor: bHover,
            borderRadius: 6,
            borderSkipped: false,
          }],
        },
        options: {
          indexAxis: "y",
          responsive: true,
          maintainAspectRatio: false,
          plugins: {
            legend: { display: false },
            tooltip: {
              callbacks: {
                label: (ctx) => {
                  const qty = ctx.parsed.x;
                  return qty === 0 ? ` ${T("bottom_never")}` : ` ${qty} ${T("qty_suffix")}`;
                },
              },
            },
          },
          scales: {
            x: {
              beginAtZero: true,
              grid: { color: "rgba(255,255,255,0.06)" },
              border: { display: false },
              ticks: {
                color: "rgba(255,255,255,0.35)",
                font: { size: 10 },
                stepSize: 1,
                precision: 0,
              },
            },
            y: {
              grid: { display: false },
              border: { display: false },
              ticks: {
                color: "rgba(255,255,255,0.75)",
                font: { size: 12, weight: "600" },
              },
            },
          },
        },
      });
      const neverSold = bp.filter(p => p.qty === 0);
      const hint = $("bottomHint");
      hint.innerHTML = neverSold.length
        ? `⚠️ <strong>${neverSold.length} ta mahsulot</strong> hali hech marta sotilmagan`
        : "";
      $("bottomSection").classList.remove("hidden");
    }

    // --- Peak hours Chart.js bar chart ----------------------------------
    const topHour = d.peak_hours.indexOf(Math.max(...d.peak_hours));
    const topCnt  = d.peak_hours[topHour] || 0;
    const labels24 = Array.from({ length: 24 }, (_, h) => `${String(h).padStart(2, "0")}:00`);
    const bgColors = d.peak_hours.map((cnt, h) =>
      h === topHour && cnt > 0 ? "#ff7a18" : "rgba(255,122,24,0.28)"
    );
    if (window._peakChart) window._peakChart.destroy();
    window._peakChart = new Chart($("peakChart"), {
      type: "bar",
      data: {
        labels: labels24,
        datasets: [{
          data: d.peak_hours,
          backgroundColor: bgColors,
          borderRadius: 5,
          borderSkipped: false,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              title: (ctx) => {
                const h = ctx[0].dataIndex;
                return `${String(h).padStart(2,"0")}:00 – ${String(h+1).padStart(2,"0")}:00`;
              },
              label: (ctx) => ` ${ctx.parsed.y} ${T("peak_orders")}`,
            },
          },
        },
        scales: {
          x: {
            grid: { display: false },
            border: { display: false },
            ticks: {
              color: "rgba(255,255,255,0.35)",
              font: { size: 10 },
              maxRotation: 0,
              autoSkip: false,
              callback: (_, i) => i % 3 === 0 ? labels24[i] : "",
            },
          },
          y: {
            beginAtZero: true,
            grid: { color: "rgba(255,255,255,0.06)" },
            border: { display: false },
            ticks: {
              color: "rgba(255,255,255,0.35)",
              font: { size: 10 },
              stepSize: 1,
              precision: 0,
            },
          },
        },
      },
    });
    const sumBox = $("peakSummary");
    sumBox.className = "peak-summary";
    sumBox.innerHTML = topCnt > 0
      ? `${T("peak_label")}: <strong>${String(topHour).padStart(2,"0")}:00 – ${String(topHour+1).padStart(2,"0")}:00</strong> &nbsp;·&nbsp; <strong>${topCnt}</strong> ${T("peak_orders")}`
      : T("no_peak");
    $("hoursSection").classList.remove("hidden");

    // --- Status pie chart ------------------------------------------------
    const entries = Object.entries(d.by_status || {});
    if (entries.length) {
      const COLORS = {
        pending:    "#f59e0b",
        confirmed:  "#3b82f6",
        preparing:  "#8b5cf6",
        on_the_way: "#06b6d4",
        delivered:  "#22c55e",
        cancelled:  "#ef4444",
      };
      const labels = entries.map(([st]) => statusLabel(st));
      const values = entries.map(([, n]) => n);
      const colors = entries.map(([st]) => COLORS[st] || "#888");

      const canvas = $("statusChart");
      if (window._statusChart) window._statusChart.destroy();
      window._statusChart = new Chart(canvas, {
        type: "doughnut",
        data: { labels, datasets: [{ data: values, backgroundColor: colors, borderWidth: 0, hoverOffset: 6 }] },
        options: {
          cutout: "60%",
          plugins: { legend: { display: false }, tooltip: {
            callbacks: { label: ctx => ` ${ctx.label}: ${ctx.parsed}` }
          }},
        },
      });

      const legend = $("chartLegend");
      legend.innerHTML = entries.map(([st, n], i) => `
        <div class="chart-legend-item">
          <span class="legend-dot" style="background:${colors[i]}"></span>
          ${escapeHtml(labels[i])}: ${fmtN(n)}
        </div>
      `).join("");
    }
    $("statusSection").classList.remove("hidden");
  }

  load();
})();

/* Branches Mini App - list of branches with full info. */
(() => {
  const tg = window.Telegram?.WebApp;
  if (tg) { tg.ready(); tg.expand(); }

  const url = new URL(window.location.href);
  const startParam = tg?.initDataUnsafe?.start_param || "";
  const tenantId = startParam || url.searchParams.get("tenant") || "tenant_001";
  const T = window.T;
  const tfmt = (key, vars) => {
    let s = T(key);
    for (const [k, v] of Object.entries(vars || {})) s = s.replace("{" + k + "}", v);
    return s;
  };

  function escapeHtml(s) {
    return String(s ?? "").replace(/[&<>"']/g, c => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
    }[c]));
  }

  const DAY_KEYS    = ["Yakshanba","Dushanba","Seshanba","Chorshanba","Payshanba","Juma","Shanba"];
  const DAY_KEYS_EN = ["Sunday","Monday","Tuesday","Wednesday","Thursday","Friday","Saturday"];

  function isOpenNow(hours) {
    if (!hours || typeof hours !== "object") return null;
    const now = new Date();
    const dow = now.getDay();
    const key = hours[DAY_KEYS[dow]] || hours[DAY_KEYS_EN[dow]];
    if (!key) return null;
    const m = String(key).match(/(\d{1,2}):(\d{2})\s*[-–]\s*(\d{1,2}):(\d{2})/);
    if (!m) return null;
    const cur = now.getHours() * 60 + now.getMinutes();
    let start = parseInt(m[1]) * 60 + parseInt(m[2]);
    let end   = parseInt(m[3]) * 60 + parseInt(m[4]);
    if (end <= start) end += 24 * 60;
    const cur2 = cur < start ? cur + 24 * 60 : cur;
    return cur2 >= start && cur2 < end;
  }

  async function load() {
    const list = document.getElementById("branchesList");
    try {
      const r = await fetch(`/api/branches?tenant=${encodeURIComponent(tenantId)}`);
      if (!r.ok) throw new Error(T("load_err"));
      const data = await r.json();
      document.getElementById("branchCount").textContent = tfmt("count", { n: data.branches.length });
      list.innerHTML = "";
      if (!data.branches.length) {
        list.innerHTML = `<div class="info">${T("empty")}</div>`;
        return;
      }
      data.branches.forEach(b => list.appendChild(branchCard(b)));
    } catch (e) {
      list.innerHTML = `<div class="err">⚠️ ${escapeHtml(e.message)}</div>`;
    }
  }

  function branchCard(b) {
    const card = document.createElement("article");
    card.className = "branch-card";

    // is_open=0 → admin forced closed; is_open=1 → use hours schedule
    const open = (b.is_open === 0) ? false : isOpenNow(b.hours);
    const badge = open === null ? ""
      : open
        ? `<span class="branch-badge">${T("open_now")}</span>`
        : `<span class="branch-badge closed">${T("closed")}</span>`;

    const dayLabels = T("day_short");
    let hoursHtml = "";
    if (b.hours && typeof b.hours === "object") {
      const rows = [];
      for (const [day, h] of Object.entries(b.hours)) {
        const short = (dayLabels && dayLabels[day]) || day;
        rows.push(`<div class="hour-row"><span class="day">${escapeHtml(short)}</span><span>${escapeHtml(h)}</span></div>`);
      }
      hoursHtml = `<div class="hours-grid">${rows.join("")}</div>`;
    }

    const mapsBtn = b.maps_url
      ? `<a class="primary-btn map-btn" href="${escapeHtml(b.maps_url)}" target="_blank">${T("view_map")}</a>`
      : "";
    const phoneRow = b.phone
      ? `<div class="branch-row">☎️ <a href="tel:${escapeHtml(b.phone)}">${escapeHtml(b.phone)}</a></div>`
      : "";
    const callBtn = b.phone
      ? `<a class="ghost-btn call-btn" href="tel:${escapeHtml(b.phone)}">${T("call")}</a>`
      : "";

    card.innerHTML = `
      <h3>${escapeHtml(b.name)} ${badge}</h3>
      <div class="branch-row">📍 ${escapeHtml(b.address)}</div>
      ${phoneRow}
      ${hoursHtml}
      <div class="branch-actions">
        ${mapsBtn}
        ${callBtn}
      </div>
    `;

    if (tg && b.lat && b.lon) {
      const shareBtn = document.createElement("button");
      shareBtn.className = "ghost-btn";
      shareBtn.textContent = T("send_loc");
      shareBtn.onclick = () => {
        tg.openLink(`https://www.google.com/maps/search/?api=1&query=${b.lat},${b.lon}`);
      };
      card.querySelector(".branch-actions").appendChild(shareBtn);
    }
    return card;
  }

  load();
})();

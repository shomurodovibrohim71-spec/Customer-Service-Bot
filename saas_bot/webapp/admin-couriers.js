/* Admin couriers — premium redesign. */
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

  let editingId = null;

  function baseQs() {
    return new URLSearchParams({ tenant: tenantId, init_data: initData, uid: fallbackUid || "" });
  }

  async function api(method, path, body) {
    const r = await fetch(path + "?" + baseQs(), {
      method,
      headers: body ? { "Content-Type": "application/json" } : {},
      body: body ? JSON.stringify(body) : undefined,
    });
    const data = await r.json();
    if (!r.ok) throw new Error(data.detail || "error");
    return data;
  }

  async function load() {
    $("courierList").innerHTML = `<div class="ac-loading">${T("loading")}</div>`;
    try {
      const data = await api("GET", "/api/admin/couriers");
      const couriers = data.couriers || [];
      $("totalPill").textContent = T("n_couriers").replace("{n}", couriers.length);
      render(couriers);
    } catch (e) {
      $("courierList").innerHTML = `<div class="ac-empty"><span class="ac-empty-icon">⚠️</span>${esc(e.message)}</div>`;
    }
  }

  function render(couriers) {
    if (!couriers.length) {
      $("courierList").innerHTML = `
        <div class="ac-empty">
          <span class="ac-empty-icon">🚗</span>
          ${T("no_couriers")}
        </div>`;
      return;
    }
    $("courierList").innerHTML = couriers.map(c => {
      const active = !!c.is_active;
      const stripeClass = active ? "active-stripe" : "inactive-stripe";
      const badge = active
        ? `<span class="ac-active-badge">${T("active")}</span>`
        : `<span class="ac-inactive-badge">${T("inactive")}</span>`;
      const toggleLabel = active ? T("btn_on") : T("btn_off");
      const toggleClass = active ? "ac-btn-toggle-on" : "ac-btn-toggle-off";
      const tgHint = c.telegram_id
        ? `<div class="ac-tg">💬 ${T("tg_hint").replace("{id}", c.telegram_id)}</div>`
        : `<div class="ac-tg" style="color:var(--text-muted)">💬 ${T("no_tg")}</div>`;
      return `
        <div class="ac-card ${active ? "" : "inactive"}">
          <div class="ac-card-stripe ${stripeClass}"></div>
          <div class="ac-card-inner">
            <div class="ac-card-row1">
              <div class="ac-name">${esc(c.name)}</div>
              ${badge}
            </div>
            <div class="ac-phone">📞 ${esc(c.phone)}</div>
            ${tgHint}
            <div class="ac-actions">
              <button class="ac-btn ac-btn-edit" onclick="openEdit(${c.id},'${esc(c.name)}','${esc(c.phone)}',${c.telegram_id || "null"})">${T("btn_edit")}</button>
              <button class="ac-btn ${toggleClass}" onclick="toggleActive(${c.id})">${toggleLabel}</button>
              <button class="ac-btn ac-btn-del" onclick="deleteCourier(${c.id})">${T("btn_del")}</button>
            </div>
          </div>
        </div>
      `;
    }).join("");
  }

  // ── sheet open/close
  window.openAdd = () => {
    editingId = null;
    $("sheetTitle").textContent = T("add_title");
    $("fName").value = $("fPhone").value = $("fTg").value = "";
    $("sheetBg").classList.remove("hidden");
    setTimeout(() => $("fName").focus(), 80);
  };

  window.openEdit = (id, name, phone, tgId) => {
    editingId = id;
    $("sheetTitle").textContent = T("edit_title");
    $("fName").value  = name;
    $("fPhone").value = phone;
    $("fTg").value    = tgId || "";
    $("sheetBg").classList.remove("hidden");
    setTimeout(() => $("fName").focus(), 80);
  };

  window.closeSheet = () => $("sheetBg").classList.add("hidden");

  window.saveSheet = async () => {
    const name = $("fName").value.trim();
    const phone = $("fPhone").value.trim();
    const tgRaw = $("fTg").value.trim();
    const telegram_id = tgRaw ? parseInt(tgRaw) : null;
    if (!name || !phone) { $("fName").focus(); return; }

    const btn = $("saveBtn");
    btn.disabled = true;
    try {
      if (editingId) {
        await api("PUT", `/api/admin/couriers/${editingId}`, { name, phone, telegram_id });
      } else {
        await api("POST", "/api/admin/couriers", { name, phone, telegram_id });
      }
      closeSheet();
      load();
    } catch (e) {
      alert(e.message);
    } finally {
      btn.disabled = false;
    }
  };

  window.toggleActive = async id => {
    try { await api("POST", `/api/admin/couriers/${id}/toggle`); load(); }
    catch (e) { alert(e.message); }
  };

  window.deleteCourier = async id => {
    if (!confirm(T("confirm_del"))) return;
    try { await api("DELETE", `/api/admin/couriers/${id}`); load(); }
    catch (e) { alert(e.message); }
  };

  $("sheetBg").addEventListener("click", e => {
    if (e.target === $("sheetBg")) closeSheet();
  });

  load();
})();

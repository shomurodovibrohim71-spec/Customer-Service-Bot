/* Admin: courier management — list, add, edit, toggle active, delete. */
(() => {
  const tg = window.Telegram?.WebApp;
  if (tg) { tg.ready(); tg.expand(); }

  const url = new URL(window.location.href);
  const tenantId   = url.searchParams.get("tenant") || "tenant_001";
  const initData   = tg?.initData || "";
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
    $("loading").classList.remove("hidden");
    $("courierList").innerHTML = "";
    try {
      const data = await api("GET", "/api/admin/couriers");
      const couriers = data.couriers || [];
      $("totalSub").textContent = T("total").replace("{n}", couriers.length);
      render(couriers);
    } catch (e) {
      $("errBox").textContent = "⚠️ " + e.message;
      $("errBox").classList.remove("hidden");
    } finally {
      $("loading").classList.add("hidden");
    }
  }

  function render(couriers) {
    const list = $("courierList");
    if (!couriers.length) {
      list.innerHTML = `<div class="info" style="text-align:center;padding:40px">${T("no_couriers")}</div>`;
      return;
    }
    list.innerHTML = couriers.map(c => {
      const isActive = c.is_active;
      const badge = isActive
        ? `<span class="active-badge">${T("active")}</span>`
        : `<span class="inactive-badge">${T("inactive")}</span>`;
      const toggleLabel = isActive ? T("btn_deactivate") : T("btn_activate");
      return `
        <div class="courier-card">
          <div class="courier-card-top">
            <div class="courier-name">${esc(c.name)}</div>
            ${badge}
          </div>
          <div class="courier-phone">📞 ${esc(c.phone)}</div>
          ${c.telegram_id ? `<div class="courier-tg">${T("tg_id")} ${c.telegram_id}</div>` : ""}
          <div class="courier-actions">
            <button class="c-btn c-btn-edit" onclick="openEdit(${c.id},'${esc(c.name)}','${esc(c.phone)}',${c.telegram_id || "null"})">${T("btn_edit")}</button>
            <button class="c-btn c-btn-toggle${isActive ? "" : " inactive"}" onclick="toggleActive(${c.id})">${toggleLabel}</button>
            <button class="c-btn c-btn-del" onclick="deleteCourier(${c.id})">${T("btn_del")}</button>
          </div>
        </div>
      `;
    }).join("");
  }

  window.openAdd = () => {
    editingId = null;
    $("modalTitle").dataset.t = "add_title";
    $("modalTitle").textContent = T("add_title");
    $("fName").value = "";
    $("fPhone").value = "";
    $("fTg").value = "";
    $("modalBg").classList.remove("hidden");
    $("fName").focus();
  };

  window.openEdit = (id, name, phone, tgId) => {
    editingId = id;
    $("modalTitle").dataset.t = "edit_title";
    $("modalTitle").textContent = T("edit_title");
    $("fName").value = name;
    $("fPhone").value = phone;
    $("fTg").value = tgId || "";
    $("modalBg").classList.remove("hidden");
    $("fName").focus();
  };

  window.closeModal = () => $("modalBg").classList.add("hidden");

  window.saveModal = async () => {
    const name  = $("fName").value.trim();
    const phone = $("fPhone").value.trim();
    const tgRaw = $("fTg").value.trim();
    const telegram_id = tgRaw ? parseInt(tgRaw) : null;
    if (!name || !phone) return;

    $("modalSaveBtn").disabled = true;
    try {
      if (editingId) {
        await api("PUT", `/api/admin/couriers/${editingId}`, { name, phone, telegram_id });
      } else {
        await api("POST", "/api/admin/couriers", { name, phone, telegram_id });
      }
      closeModal();
      load();
    } catch (e) {
      alert(e.message);
    } finally {
      $("modalSaveBtn").disabled = false;
    }
  };

  window.toggleActive = async (id) => {
    try {
      await api("POST", `/api/admin/couriers/${id}/toggle`);
      load();
    } catch (e) {
      alert(e.message);
    }
  };

  window.deleteCourier = async (id) => {
    if (!confirm(T("confirm_del"))) return;
    try {
      await api("DELETE", `/api/admin/couriers/${id}`);
      load();
    } catch (e) {
      alert(e.message);
    }
  };

  $("modalBg").addEventListener("click", e => {
    if (e.target === $("modalBg")) closeModal();
  });

  load();
})();

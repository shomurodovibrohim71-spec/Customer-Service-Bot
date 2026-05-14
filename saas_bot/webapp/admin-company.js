/* Admin company-info editor: single screen, sticky save bar. */
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
  const FIELDS = [
    "name", "tagline", "about",
    "phone", "address", "working_hours",
    "card_number", "alif_phone",
    "click_merchant_id", "click_service_id", "payme_merchant_id",
  ];

  let initialValues = {};
  let isDirty = false;

  function showErr(msg) {
    const box = $("errBox");
    box.textContent = "⚠️ " + msg;
    box.classList.remove("hidden");
    setTimeout(() => box.classList.add("hidden"), 5000);
  }
  function showOk(msg) {
    const box = $("okBox");
    box.textContent = msg;
    box.classList.remove("hidden");
    setTimeout(() => box.classList.add("hidden"), 2500);
  }

  function setDirty(d) {
    isDirty = d;
    $("dirtyDot").classList.toggle("hidden", !d);
    $("saveStatus").textContent = d ? T("dirty") : "";
  }

  function wireDirtyListeners() {
    for (const f of FIELDS) {
      const el = $("f_" + f);
      if (!el) continue;
      el.addEventListener("input", () => setDirty(true));
    }
  }

  async function load() {
    try {
      const qs = new URLSearchParams({
        tenant: tenantId, init_data: initData, uid: fallbackUid || "",
      });
      const r = await fetch(`/api/admin/company?${qs}`);
      const data = await r.json();
      if (!r.ok) throw new Error(data.detail || r.status);
      initialValues = data.fields || {};
      for (const f of FIELDS) {
        const el = $("f_" + f);
        if (el) el.value = initialValues[f] || "";
      }
      $("loading").classList.add("hidden");
      $("form").classList.remove("hidden");
      $("saveBar").classList.remove("hidden");
      wireDirtyListeners();
    } catch (e) {
      $("loading").classList.add("hidden");
      showErr(T("err_load") + e.message);
    }
  }

  $("saveBtn").onclick = async () => {
    const fields = {};
    for (const f of FIELDS) {
      const el = $("f_" + f);
      if (el) fields[f] = (el.value || "").trim();
    }
    $("saveBtn").disabled = true;
    $("saveBtn").textContent = T("saving");
    try {
      const r = await fetch("/api/admin/company", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          init_data: initData, fallback_uid: fallbackUid,
          tenant_id: tenantId, fields,
        }),
      });
      const data = await r.json();
      if (!r.ok) throw new Error(data.detail || r.status);
      if (tg?.HapticFeedback) tg.HapticFeedback.notificationOccurred("success");
      initialValues = { ...fields };
      setDirty(false);
      showOk(T("saved"));
    } catch (e) {
      showErr(e.message);
    } finally {
      $("saveBtn").disabled = false;
      $("saveBtn").textContent = T("save_btn");
    }
  };

  load();
})();

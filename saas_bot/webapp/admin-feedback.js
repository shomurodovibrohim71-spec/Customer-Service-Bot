/* Admin feedback dashboard: 3 categories + thread view + reply box. */
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

  const state = { cat: "all", current: null };
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

  // ----- Tabs ----------------------------------------------------------
  document.querySelectorAll("#fbTabs .tab").forEach(btn => {
    btn.onclick = () => {
      state.cat = btn.dataset.cat;
      document.querySelectorAll("#fbTabs .tab").forEach(b => b.classList.toggle("active", b === btn));
      load();
    };
  });

  // ----- Helpers -------------------------------------------------------
  function fmtDate(iso) { return (iso || "").replace("T", " ").slice(0, 16); }
  function userTag(it) {
    if (it.username) return "@" + escapeHtml(it.username);
    if (it.name) return escapeHtml(it.name);
    return "id" + it.user_id;
  }
  function catBadge(cat) {
    const map = { complaint: "bdg-complaint", question: "bdg-question", suggestion: "bdg-suggestion" };
    return `<span class="fb-bdg ${map[cat] || ''}">${T("cat_" + cat)}</span>`;
  }
  function statusBadge(s) {
    return `<span class="fb-bdg ${s === 'answered' ? 'bdg-answered' : 'bdg-open'}">${T("status_" + s)}</span>`;
  }

  // ----- List view -----------------------------------------------------
  async function load() {
    const list = $("list");
    list.innerHTML = `<div class="loading">${T("loading")}</div>`;
    try {
      const cat = state.cat === "all" ? "" : state.cat;
      const qs = new URLSearchParams({
        tenant: tenantId, init_data: initData, uid: fallbackUid || "",
        category: cat, limit: 200,
      });
      const data = await api("GET", "/api/admin/feedback?" + qs);
      const c = data.counts || {};
      $("cnt_all").textContent = c.total || 0;
      $("cnt_complaint").textContent = c.complaint || 0;
      $("cnt_question").textContent = c.question || 0;
      $("cnt_suggestion").textContent = c.suggestion || 0;
      $("totalCount").textContent = tfmt("total_short", { n: data.items.length });

      list.innerHTML = "";
      if (!data.items.length) {
        list.innerHTML = `<div class="info">${T("empty")}</div>`;
        return;
      }
      data.items.forEach(it => list.appendChild(card(it)));
    } catch (e) {
      list.innerHTML = `<div class="err">⚠️ ${escapeHtml(e.message)}</div>`;
    }
  }

  function card(it) {
    const c = document.createElement("article");
    c.className = "fb-card";
    const phone = it.phone ? `<a href="tel:${escapeHtml(it.phone)}" class="fb-phone">📞 ${escapeHtml(it.phone)}</a>` : "";
    const uname = it.username ? `<a href="https://t.me/${escapeHtml(it.username)}" target="_blank" class="fb-uname">@${escapeHtml(it.username)}</a>` : "";
    c.innerHTML = `
      <div class="fb-head">
        <div class="fb-id">#${it.id}</div>
        <div class="fb-bdgs">${catBadge(it.category)} ${statusBadge(it.status)}</div>
      </div>
      <div class="fb-user">${escapeHtml(it.name || ("id" + it.user_id))} ${uname} ${phone}</div>
      <div class="fb-content">${escapeHtml(it.content)}</div>
      ${it.ai_response ? `<div class="fb-ai">🤖 ${escapeHtml(it.ai_response)}</div>` : ""}
      <div class="fb-foot">
        <span class="fb-date">${escapeHtml(fmtDate(it.created_at))}</span>
        <button class="ghost-btn fb-open">✏ Javob berish / ko'rish</button>
      </div>
    `;
    c.querySelector(".fb-open").onclick = () => openThread(it.id);
    return c;
  }

  // ----- Thread view ---------------------------------------------------
  async function openThread(id) {
    state.current = id;
    $("threadMsgs").innerHTML = `<div class="loading">${T("loading")}</div>`;
    $("threadMeta").innerHTML = "";
    $("threadTitle").textContent = "#" + id;
    $("replyInput").value = "";
    $("threadErr").classList.add("hidden");
    openScreen("threadScreen");

    try {
      const qs = new URLSearchParams({
        tenant: tenantId, init_data: initData, uid: fallbackUid || "",
      });
      const data = await api("GET", `/api/admin/feedback/${id}?` + qs);
      renderThread(data);
    } catch (e) {
      $("threadMsgs").innerHTML = `<div class="err">⚠️ ${escapeHtml(e.message)}</div>`;
    }
  }

  function renderThread(d) {
    const f = d.feedback;
    const uname = f.username ? `<a href="https://t.me/${escapeHtml(f.username)}" target="_blank">@${escapeHtml(f.username)}</a>` : T("no_username");
    const phone = f.phone ? `<a href="tel:${escapeHtml(f.phone)}">📞 ${escapeHtml(f.phone)}</a>` : "—";
    $("threadMeta").innerHTML = `
      <div class="fb-meta-row"><span class="fb-meta-key">👤</span> ${escapeHtml(f.name || ("id" + f.user_id))} • ${uname}</div>
      <div class="fb-meta-row"><span class="fb-meta-key">📞</span> ${phone}</div>
      <div class="fb-meta-row">${catBadge(f.category)} ${statusBadge(f.status)} <span class="fb-meta-date">${escapeHtml(fmtDate(f.created_at))}</span></div>
    `;
    const wrap = $("threadMsgs");
    wrap.innerHTML = "";
    d.messages.forEach(m => {
      const bubble = document.createElement("div");
      bubble.className = "msg-bubble msg-" + m.role;
      bubble.innerHTML = `
        <div class="msg-role">${T("role_" + m.role)} <span class="msg-time">${escapeHtml(fmtDate(m.created_at))}</span></div>
        <div class="msg-text">${escapeHtml(m.content)}</div>
      `;
      wrap.appendChild(bubble);
    });
    wrap.scrollTop = wrap.scrollHeight;
  }

  $("threadBack").onclick = () => closeScreen("threadScreen");

  $("replyBtn").onclick = async () => {
    if (!state.current) return;
    const text = $("replyInput").value.trim();
    if (!text) {
      $("threadErr").textContent = "⚠️ " + T("err_empty");
      $("threadErr").classList.remove("hidden");
      return;
    }
    $("replyBtn").disabled = true;
    $("replyBtn").textContent = T("sending");
    try {
      await api("POST", "/api/admin/feedback/reply", {
        feedback_id: state.current, text,
      });
      if (tg?.HapticFeedback) tg.HapticFeedback.notificationOccurred("success");
      $("replyInput").value = "";
      // Refresh thread to show the new admin message.
      await openThread(state.current);
      // Refresh the list in the background so status badges update.
      load();
    } catch (e) {
      $("threadErr").textContent = "⚠️ " + e.message;
      $("threadErr").classList.remove("hidden");
    } finally {
      $("replyBtn").disabled = false;
      $("replyBtn").textContent = T("reply_btn");
    }
  };

  load();
})();

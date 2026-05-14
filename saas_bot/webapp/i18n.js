/* Tiny i18n helper shared by every Mini App page.
 *
 * Usage in a page:
 *   <script src="/static/i18n.js"></script>
 *   <script>
 *     window.STRINGS = {
 *       uz: { hello: "Salom" },
 *       en: { hello: "Hello" },
 *       ru: { hello: "Привет" },
 *     };
 *   </script>
 *   <script src="/static/your-page.js"></script>
 *
 * The page JS can then call T("hello") or window.applyI18n() to translate
 * elements marked with [data-t="key"] (text) or [data-t-placeholder="key"]
 * (input/textarea placeholder).
 *
 * Language is resolved from (in priority order):
 *   1. ?lang= query parameter — bot passes this when opening the WebApp.
 *   2. Telegram WebApp initDataUnsafe.user.language_code (first 2 chars).
 *   3. "uz" (default).
 */
(function () {
  const url = new URL(window.location.href);
  const tg  = window.Telegram?.WebApp;
  const fromUrl = (url.searchParams.get("lang") || "").toLowerCase();
  const fromTg  = (tg?.initDataUnsafe?.user?.language_code || "").slice(0, 2).toLowerCase();
  let lang = fromUrl || fromTg || "uz";
  if (!["uz", "en", "ru"].includes(lang)) lang = "uz";

  window.LANG = lang;

  window.T = function (key, fallback) {
    const s = window.STRINGS || {};
    const dict = s[lang] || s.uz || {};
    if (dict[key] != null) return dict[key];
    // Fall back to Uzbek if missing in the active language.
    if (s.uz && s.uz[key] != null) return s.uz[key];
    return fallback != null ? fallback : key;
  };

  window.applyI18n = function (root) {
    const scope = root || document;
    scope.querySelectorAll("[data-t]").forEach(el => {
      el.textContent = window.T(el.getAttribute("data-t"));
    });
    scope.querySelectorAll("[data-t-placeholder]").forEach(el => {
      el.placeholder = window.T(el.getAttribute("data-t-placeholder"));
    });
    scope.querySelectorAll("[data-t-title]").forEach(el => {
      el.title = window.T(el.getAttribute("data-t-title"));
    });
  };

  // Apply on DOMContentLoaded so pages don't have to remember.
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => window.applyI18n());
  } else {
    setTimeout(() => window.applyI18n(), 0);
  }
})();

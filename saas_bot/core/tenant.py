"""Tenant config discovery, loading, and i18n helpers."""
from __future__ import annotations

import importlib.util
import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class Tenant:
    """A single business tenant's runtime configuration."""

    def __init__(self, config: dict[str, Any]) -> None:
        self.config = config
        self.id: str = config["id"]
        self.name: str = config["name"]
        self.bot_token: str = config["bot_token"]
        self.default_language: str = config.get("default_language", "uz")
        self.admin_ids: list[int] = config.get("admin_ids", [])
        self.languages: dict[str, str] = config.get("languages", {"uz": "🇺🇿 O'zbekcha"})
        self.menu_labels: dict[str, dict[str, str]] = config.get("menu_labels", {})
        self.admin_labels: dict[str, dict[str, str]] = config.get("admin_labels", {})
        self.texts: dict[str, dict[str, str]] = config.get("texts", {})
        self.admin_texts: dict[str, dict[str, str]] = config.get("admin_texts", {})

    def __repr__(self) -> str:
        return f"<Tenant {self.id} name={self.name!r}>"

    def get(self, key: str, default: Any = None) -> Any:
        return self.config.get(key, default)

    def is_admin(self, user_id: int | None) -> bool:
        return user_id is not None and user_id in self.admin_ids

    def admin_label(self, lang: str | None, action: str) -> str:
        lang = self.resolve_lang(lang)
        return self.admin_labels.get(lang, {}).get(action) or self.admin_labels.get(
            self.default_language, {}
        ).get(action, action)

    def admin_t(self, lang: str | None, key: str, **fmt: Any) -> str:
        lang = self.resolve_lang(lang)
        template = self.admin_texts.get(lang, {}).get(key)
        if template is None:
            template = self.admin_texts.get(self.default_language, {}).get(key, key)
        try:
            return template.format(**fmt)
        except (KeyError, IndexError):
            return template

    def admin_action_from_label(self, text: str) -> str | None:
        """Reverse-lookup for admin labels."""
        for _lang, labels in self.admin_labels.items():
            for action, label in labels.items():
                if label == text:
                    return action
        return None

    @property
    def language(self) -> str:
        """Backwards-compat alias."""
        return self.default_language

    # ----------------------------------------------------------------- i18n

    def resolve_lang(self, lang: str | None) -> str:
        """Return a known language code, falling back to the tenant default."""
        if lang and lang in self.texts:
            return lang
        return self.default_language

    def t(self, lang: str | None, key: str, **fmt: Any) -> str:
        """Translate a key for the given language with `.format(**fmt)` applied."""
        lang = self.resolve_lang(lang)
        template = self.texts.get(lang, {}).get(key)
        if template is None:
            # Fall back to default language, then to the raw key.
            template = self.texts.get(self.default_language, {}).get(key, key)
        try:
            return template.format(**fmt)
        except (KeyError, IndexError):
            return template

    def label(self, lang: str | None, action: str) -> str:
        """Return the reply-keyboard button label for a given action."""
        lang = self.resolve_lang(lang)
        return self.menu_labels.get(lang, {}).get(action) or self.menu_labels.get(
            self.default_language, {}
        ).get(action, action)

    def action_from_label(self, text: str) -> str | None:
        """Reverse lookup: given a button text in any language, return the action key."""
        for _lang, labels in self.menu_labels.items():
            for action, label in labels.items():
                if label == text:
                    return action
        return None

    # -------------------------------------------------------------- helpers

    def services_formatted(self, products: list[dict[str, Any]] | None = None) -> str:
        """Render a product list as markdown bullets. Pass DB rows or fall back to config."""
        items = products if products is not None else self.config.get("services", [])
        lines = []
        for p in items:
            desc = p.get("description") or ""
            line = f"• *{p['name']}* — {p['price']}"
            if desc:
                line += f"\n  _{desc}_"
            lines.append(line)
        return "\n".join(lines) if lines else "_menyu bo'sh_"

    def render_system_prompt(self, products: list[dict[str, Any]] | None = None,
                              branches: list[dict[str, Any]] | None = None,
                              lang: str | None = None) -> str:
        """Build the Claude system prompt from current DB state.

        `system_prompt` can be a plain string OR a dict keyed by language code.
        When it is a dict, we pick the entry matching the user's language with
        a fallback to the tenant default."""
        services_text = ", ".join(
            f"{p['name']} ({p['price']})" for p in (products or self.config.get("services", []))
        )
        branches_text = ", ".join(
            b["name"] for b in (branches or self.config.get("branches", []))
        )
        prompt = self.config.get("system_prompt", "")
        if isinstance(prompt, dict):
            lang = self.resolve_lang(lang)
            prompt = prompt.get(lang) or prompt.get(self.default_language) or next(iter(prompt.values()), "")
        try:
            return prompt.format(
                name=self.name,
                services=services_text,
                branches=branches_text,
                working_hours=self.config.get("working_hours", ""),
                phone=self.config.get("phone", ""),
            )
        except KeyError:
            return prompt

    @staticmethod
    def format_branch_hours(hours: dict[str, str] | str | None) -> str:
        """Render the 7-day hours dict as bullet lines."""
        if not hours:
            return ""
        if isinstance(hours, str):
            try:
                hours = json.loads(hours)
            except (json.JSONDecodeError, TypeError):
                return str(hours)
        if not isinstance(hours, dict):
            return ""
        lines = []
        for day, h in hours.items():
            lines.append(f"🕐 *{day}* {h}")
        return "\n".join(lines)


def load_tenants(tenants_dir: Path) -> list[Tenant]:
    """Dynamically import every tenant_*.py file (skip *.disabled) and return Tenant objects."""
    tenants: list[Tenant] = []
    for path in sorted(tenants_dir.glob("tenant_*.py")):
        if path.name.startswith("_") or path.suffix != ".py":
            continue
        spec = importlib.util.spec_from_file_location(f"tenants.{path.stem}", path)
        if spec is None or spec.loader is None:
            logger.warning("Could not build spec for %s", path)
            continue
        module = importlib.util.module_from_spec(spec)
        try:
            spec.loader.exec_module(module)
        except Exception as exc:  # noqa: BLE001
            logger.error("Failed to import tenant %s: %s", path.name, exc)
            continue
        cfg = getattr(module, "CONFIG", None)
        if not isinstance(cfg, dict):
            logger.warning("Tenant %s has no CONFIG dict; skipping", path.name)
            continue
        if not cfg.get("bot_token"):
            logger.warning("Tenant %s has empty bot_token; skipping", cfg.get("id", path.name))
            continue
        tenants.append(Tenant(cfg))
        logger.info("Loaded tenant %s", cfg["id"])
    return tenants

"""Tenant config / i18n rendering tests."""
from __future__ import annotations

from core.tenant import Tenant


def _sample_config() -> dict:
    return {
        "id": "test",
        "bot_token": "x",
        "name": "Acme",
        "tagline": "best",
        "default_language": "uz",
        "languages": {"uz": "🇺🇿 O'zbekcha", "ru": "🇷🇺 Русский"},
        "menu_labels": {
            "uz": {"order": "Buyurtma", "branches": "Filiallar"},
            "ru": {"order": "Заказать", "branches": "Филиалы"},
        },
        "texts": {
            "uz": {
                "welcome": "Salom {user_name}, bu {name}",
                "main_menu": "Asosiy menyu",
            },
            "ru": {"welcome": "Привет {user_name}, это {name}"},
        },
        "system_prompt": "Acme bot. Menu: {services}. Branches: {branches}.",
        "services": [{"name": "Cut", "price": "50,000"}],
        "branches": [{"name": "Center"}],
        "admin_ids": [1],
    }


def test_t_uses_correct_language():
    t = Tenant(_sample_config())
    assert t.t("uz", "welcome", user_name="A", name="B") == "Salom A, bu B"
    assert t.t("ru", "welcome", user_name="A", name="B") == "Привет A, это B"


def test_t_falls_back_to_default():
    t = Tenant(_sample_config())
    # 'main_menu' missing in ru -> falls back to uz.
    assert t.t("ru", "main_menu") == "Asosiy menyu"


def test_label_lookup_and_reverse():
    t = Tenant(_sample_config())
    assert t.label("uz", "order") == "Buyurtma"
    assert t.label("ru", "order") == "Заказать"
    # Reverse: text -> action
    assert t.action_from_label("Filiallar") == "branches"
    assert t.action_from_label("Заказать") == "order"
    assert t.action_from_label("nonsense") is None


def test_resolve_lang_unknown_falls_back():
    t = Tenant(_sample_config())
    assert t.resolve_lang("zz") == "uz"
    assert t.resolve_lang(None) == "uz"


def test_format_branch_hours_from_dict():
    out = Tenant.format_branch_hours({"Du": "9-18", "Sesh": "9-18"})
    assert "Du" in out and "9-18" in out


def test_format_branch_hours_from_json_string():
    out = Tenant.format_branch_hours('{"Du": "9-18"}')
    assert "Du" in out

"""Utility-helper tests."""
from __future__ import annotations

from utils.helpers import (
    build_menu_keyboard,
    is_valid_phone,
    language_keyboard,
    normalize_phone,
    products_keyboard,
)


def test_phone_validation():
    assert is_valid_phone("+998901234567")
    assert is_valid_phone("998901234567")
    assert is_valid_phone("+998 90 123 45 67")
    assert not is_valid_phone("12345")
    assert not is_valid_phone("hello")
    assert not is_valid_phone("")


def test_phone_normalization():
    assert normalize_phone("+998 90-123 (45) 67") == "+998901234567"
    # Auto-prepends + if missing.
    assert normalize_phone("998901234567") == "+998901234567"


def test_build_menu_keyboard_two_columns():
    kb = build_menu_keyboard(
        [
            {"text": "A", "callback": "a"},
            {"text": "B", "callback": "b"},
            {"text": "C", "callback": "c"},
        ],
        columns=2,
    )
    assert len(kb.inline_keyboard) == 2
    assert len(kb.inline_keyboard[0]) == 2
    assert kb.inline_keyboard[1][0].text == "C"


def test_products_keyboard_includes_cancel():
    kb = products_keyboard([{"id": 1, "name": "X", "price": "1"}])
    assert kb.inline_keyboard[-1][0].callback_data == "order_cancel"
    assert kb.inline_keyboard[0][0].callback_data == "svc:1"


def test_language_keyboard():
    kb = language_keyboard({"uz": "🇺🇿 O'zbekcha", "ru": "🇷🇺 Русский"})
    assert len(kb.inline_keyboard) == 1
    assert kb.inline_keyboard[0][0].callback_data == "lang:uz"
    assert kb.inline_keyboard[0][1].callback_data == "lang:ru"

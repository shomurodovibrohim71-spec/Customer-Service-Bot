# -*- coding: utf-8 -*-
"""Re-classify existing feedbacks that have default 'question' category using Claude AI."""
import asyncio, sqlite3, os, sys
sys.stdout.reconfigure(encoding="utf-8")

DB = r"C:\Users\user\Desktop\Customer Service Bot\saas_bot\data\tenant_001.db"

# Simple keyword-based classifier (no API needed)
COMPLAINT_WORDS = [
    "ishlamayabdi", "ishlamaydi", "xato", "muammo", "yomon", "noto'g'ri",
    "notoʻgʻri", "buzilgan", "bug", "error", "nosoz", "shikoyat",
    "qo'niqmadim", "xafaman", "rahmatmas", "sovuq", "kech", "kechikdi",
    "noto'g'ri", "ishlamadi", "chiqmaydi", "chiqmayabdi", "ko'rinmaydi",
    "работает", "ошибка", "проблема", "плохо", "неправильно", "не работает",
    "not working", "broken", "error", "wrong", "bad", "slow", "problem",
]
SUGGESTION_WORDS = [
    "qo'shsangiz", "qo'shsa", "taklif", "bo'lsa yaxshi", "kerak edi", "istardim",
    "добавить", "предложение", "было бы", "хотелось",
    "suggest", "add", "would be great", "please add", "should have",
]

def classify(text: str) -> str:
    low = text.lower()
    for w in COMPLAINT_WORDS:
        if w in low:
            return "complaint"
    for w in SUGGESTION_WORDS:
        if w in low:
            return "suggestion"
    return "question"

conn = sqlite3.connect(DB, timeout=15)
conn.row_factory = sqlite3.Row
conn.execute("PRAGMA journal_mode=WAL")

rows = conn.execute(
    "SELECT id, content, category FROM feedback WHERE tenant_id='tenant_001' ORDER BY id"
).fetchall()

updated = 0
for r in rows:
    new_cat = classify(r["content"] or "")
    if new_cat != r["category"]:
        conn.execute(
            "UPDATE feedback SET category=? WHERE id=?", (new_cat, r["id"])
        )
        print(f"  #{r['id']} {r['category']} → {new_cat}: {str(r['content'])[:60]}")
        updated += 1
    else:
        print(f"  #{r['id']} {r['category']} (ok): {str(r['content'])[:50]}")

conn.commit()
conn.close()
print(f"\nYangilandi: {updated} ta feedback")

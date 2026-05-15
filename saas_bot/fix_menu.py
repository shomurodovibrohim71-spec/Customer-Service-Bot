# -*- coding: utf-8 -*-
import sqlite3, sys
sys.stdout.reconfigure(encoding="utf-8")

db = r"C:\Users\user\Desktop\Customer Service Bot\saas_bot\data\tenant_001.db"
conn = sqlite3.connect(db)

# Remove broken categories and re-insert with correct emojis
conn.execute("UPDATE products SET is_active=0 WHERE tenant_id='tenant_001'")

# Delete the dummy "Filiallar" branch
conn.execute("UPDATE branches SET is_active=0 WHERE tenant_id='tenant_001' AND name LIKE '%Filiallar%'")

menu = [
    # (category, name, price, description)
    ("🍲 Sho'rvalar", "Mastava",            25000, "Guruch, sabzavot va mol go'shti bilan tayyorlangan an'anaviy sho'rva"),
    ("🍲 Sho'rvalar", "Lag'mon sho'rvasi",  30000, "Qo'lda cho'zilgan lag'mon va go'sht bilan mazali sho'rva"),
    ("🍲 Sho'rvalar", "Dum sho'rva",        35000, "Qo'y go'shtidan tayyorlangan to'yimli milliy sho'rva"),
    ("🍲 Sho'rvalar", "Mosho'rva",          22000, "Mosh va go'sht bilan tayyorlangan sog'lom sho'rva"),
    ("🍲 Sho'rvalar", "Nuxat sho'rva",      28000, "Nuxat va mol go'shti bilan boy sho'rva"),

    ("🍚 Plov",       "Toshkent pilovi",    45000, "Devzira guruchi, sabzi va qo'y go'shti bilan klassik Toshkent pilovi"),
    ("🍚 Plov",       "Samarqand pilovi",   50000, "Alohida tayyorlangan go'sht bilan mazali Samarqand usulida plov"),
    ("🍚 Plov",       "Shirin palov",       45000, "O'rik, mayiz va yong'oq bilan tayyorlangan shirin plov"),
    ("🍚 Plov",       "Devzira pilovi",     55000, "Haqiqiy devzira guruchi bilan tayyorlangan to'yimli plov"),

    ("🥩 Kabob",      "Tikka kabob (6 ta)", 55000, "Qo'y go'shtidan qo'lda tayyorlangan va tandirda pishirilgan kabob"),
    ("🥩 Kabob",      "Lula kabob (4 ta)",  50000, "Maydalangan go'shtdan tayyorlangan to'yimli lula kabob"),
    ("🥩 Kabob",      "Jigar kabob",        45000, "Mol jigari va piyoz bilan tayyorlangan mazali kabob"),
    ("🥩 Kabob",      "Tandir kabob",       65000, "Tandirda sekin pishirilgan yumshoq va xushbo'y kabob"),
    ("🥩 Kabob",      "Qozon kabob",        60000, "Go'sht va kartoshka bilan qovurilgan milliy taom"),
    ("🥩 Kabob",      "Dimlama",            55000, "Sabzavot va go'sht bilan dimda pishirilgan taom"),

    ("🥟 Somsa",      "Tandirda somsa (2 ta)", 20000, "Tandirda pishirilgan go'shtli va piyozli crispy somsa"),
    ("🥟 Somsa",      "Go'shtli samsa (2 ta)", 18000, "Tandirda pishirilgan mol go'shtli samsa"),
    ("🥟 Somsa",      "Kunjutli non",       8000,  "Tandirda yangi pishirilgan kunjutli o'zbek noni"),
    ("🥟 Somsa",      "Patir non",          10000, "Yog'da tayyorlangan patir — mazali va to'yimli"),

    ("🥗 Salatlar",   "Achchiqchuchuk",     18000, "Pomidor, bodring va piyozdan tayyorlangan an'anaviy salat"),
    ("🥗 Salatlar",   "Toshkent salati",    22000, "Qaynatilgan go'sht va sabzavotlar bilan Toshkent salati"),
    ("🥗 Salatlar",   "Ko'k salat",         15000, "Yangi sabzavotlardan tayyorlangan salat"),

    ("🥤 Ichimliklar","Ko'k choy (choynak)",12000, "An'anaviy o'zbek ko'k choyi, choynak bilan"),
    ("🥤 Ichimliklar","Qora choy (choynak)",12000, "Limon bilan qora choy, choynak bilan"),
    ("🥤 Ichimliklar","Ayron",              10000, "Sovutilgan tabiiy ayron"),
    ("🥤 Ichimliklar","Kompot",              8000, "Quritilgan mevalardan tayyorlangan uy kompoti"),
    ("🥤 Ichimliklar","Mineral suv 0.5L",    7000, "Sovuq mineral suv"),
    ("🥤 Ichimliklar","Coca-Cola 0.5L",     10000, "Sovuq Coca-Cola"),

    ("🍮 Shirinliklar","Halva",             15000, "Sezamdan tayyorlangan an'anaviy o'zbek halvasi"),
    ("🍮 Shirinliklar","Chak-chak",         20000, "Asalda qorilgan mayda qiyma — milliy shirinlik"),
    ("🍮 Shirinliklar","Navvot",            12000, "Qand shakar — o'zbek dasturxonining bezagi"),
    ("🍮 Shirinliklar","Nishalda",          18000, "Ko'pikli pishiriq — Navro'z shirinligi"),
]

now = "2026-05-16 00:00:00"
for pos, (cat, name, price, desc) in enumerate(menu, start=1):
    price_str = f"{price:,} so'm".replace(",", " ")
    conn.execute(
        """INSERT INTO products
           (tenant_id, name, category, price, price_value, description, position, is_active, created_at)
           VALUES ('tenant_001', ?, ?, ?, ?, ?, ?, 1, ?)""",
        (name, cat, price_str, price, desc, pos, now)
    )

conn.commit()

rows = conn.execute(
    "SELECT category, COUNT(*) as n FROM products WHERE is_active=1 AND tenant_id='tenant_001' GROUP BY category ORDER BY MIN(position)"
).fetchall()
print("Yangi menyu:")
for cat, n in rows:
    print(f"  {cat} -> {n} ta taom")

total = conn.execute("SELECT COUNT(*) FROM products WHERE is_active=1 AND tenant_id='tenant_001'").fetchone()[0]
print(f"\nJami: {total} ta taom")
conn.close()
print("OK!")

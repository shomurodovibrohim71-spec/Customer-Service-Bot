# -*- coding: utf-8 -*-
"""Store image URLs directly in the DB (no local download needed).
Uses Wikimedia thumb URLs and Unsplash CDN URLs as external image_url values.
"""
import sqlite3, urllib.request, urllib.parse, json, time, sys
sys.stdout.reconfigure(encoding="utf-8")

DB = r"C:\Users\user\Desktop\Customer Service Bot\saas_bot\data\tenant_001.db"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

# ── Wikimedia Commons filename → local product key
WIKI = {
    "Mastava":               "Mastava.jpg",
    "Lagmon_shorvasi":       "Лагман.jpg",
    "Dum_shorva":            "Shorpo.jpg",
    "Moshorva":              "Moshkichra.jpg",
    "Nuxat_shorva":          "Uzbek and Tajik Chickpea and Laghman soup.jpg",
    "Toshkent_pilovi":       "Uzbek pilaf.jpg",
    "Samarqand_pilovi":      "Samarkand Zigir-pilaf.jpg",
    "Shirin_palov":          "To'y oshi.jpg",
    "Devzira_pilovi":        "Uzbek palov in Yerevan Food Court.jpg",
    "Tikka_kabob_6_ta":      "Shashlik.jpg",
    "Lula_kabob_4_ta":       "Uzbek kebab.jpg",
    "Jigar_kabob":           "Shashlik in Fireplace.jpg",
    "Tandir_kabob":          "Shashlik.jpg",
    "Qozon_kabob":           "Qozon kabob (Uzbek national cuisine).jpg",
    "Dimlama":               "Dimlama (16425713838).jpg",
    "Tandirda_somsa_2_ta":   "Ouzbekistan-Samsas.jpg",
    "Goshtli_samsa_2_ta":    "Uzbek samsa in Vienna, Austria.jpg",
    "Kunjutli_non":          "Samarqand noni.jpg",
    "Patir_non":             "Qozon patir (Jizzakh region).jpg",
    "Ayron":                 "Fresh ayran.jpg",
    "Kompot":                "Сухофрукты Узбекистана-01.jpg",
    "Halva":                 "Orient sweets (special halva) Samarkand, Siyab.jpg",
    "Chakchak":              "Чак-чак.jpg",
    "Navvot":                "Uzbek sweets.jpg",
    "Nishalda":              "Sweets in the Uzbek market.jpg",
}

# ── Unsplash CDN URLs (external, no download)
UNSPLASH = {
    "Achchiqchuchuk":  "https://images.unsplash.com/photo-1608649409268-3b89b9f223f8?w=400&h=300&fit=crop&q=80",
    "Toshkent_salati": "https://plus.unsplash.com/premium_photo-1670263779633-5309cae32f13?w=400&h=300&fit=crop&q=80",
    "Kok_salat":       "https://plus.unsplash.com/premium_photo-1701870910794-f2ed7f50a088?w=400&h=300&fit=crop&q=80",
    "Kok_choy":        "https://images.unsplash.com/photo-1581348304131-9d03407316b7?w=400&h=300&fit=crop&q=80",
    "Qora_choy":       "https://images.unsplash.com/photo-1556679343-c7306c1976bc?w=400&h=300&fit=crop&q=80",
    "Mineral_suv":     "https://images.unsplash.com/photo-1523362628745-0c100150b504?w=400&h=300&fit=crop&q=80",
    "CocaCola":        "https://images.unsplash.com/photo-1554866585-bf710a2a47c5?w=400&h=300&fit=crop&q=80",
}

# ── Product name → image key
PRODUCT_MAP = {
    "Mastava":               "Mastava",
    "Lag'mon sho'rvasi":     "Lagmon_shorvasi",
    "Dum sho'rva":           "Dum_shorva",
    "Mosho'rva":             "Moshorva",
    "Nuxat sho'rva":         "Nuxat_shorva",
    "Toshkent pilovi":       "Toshkent_pilovi",
    "Samarqand pilovi":      "Samarqand_pilovi",
    "Shirin palov":          "Shirin_palov",
    "Devzira pilovi":        "Devzira_pilovi",
    "Tikka kabob (6 ta)":    "Tikka_kabob_6_ta",
    "Lula kabob (4 ta)":     "Lula_kabob_4_ta",
    "Jigar kabob":           "Jigar_kabob",
    "Tandir kabob":          "Tandir_kabob",
    "Qozon kabob":           "Qozon_kabob",
    "Dimlama":               "Dimlama",
    "Tandirda somsa (2 ta)": "Tandirda_somsa_2_ta",
    "Go'shtli samsa (2 ta)": "Goshtli_samsa_2_ta",
    "Kunjutli non":          "Kunjutli_non",
    "Patir non":             "Patir_non",
    "Achchiqchuchuk":        "Achchiqchuchuk",
    "Toshkent salati":       "Toshkent_salati",
    "Ko'k salat":            "Kok_salat",
    "Ko'k choy (choynak)":   "Kok_choy",
    "Qora choy (choynak)":   "Qora_choy",
    "Ayron":                 "Ayron",
    "Kompot":                "Kompot",
    "Mineral suv 0.5L":      "Mineral_suv",
    "Coca-Cola 0.5L":        "CocaCola",
    "Halva":                 "Halva",
    "Chak-chak":             "Chakchak",
    "Navvot":                "Navvot",
    "Nishalda":              "Nishalda",
}

# ── Step 1: Batch-fetch Wikimedia thumb URLs
print("Wikimedia API dan URL lar olinmoqda...")
wiki_filenames = list(WIKI.values())
enc_titles = "|".join(f"File:{fn.replace(' ','_')}" for fn in wiki_filenames)
api = (
    "https://commons.wikimedia.org/w/api.php?action=query"
    f"&titles={urllib.parse.quote(enc_titles, safe='|')}"
    "&prop=imageinfo&iiprop=url%7Cthumburl&iiurlwidth=400&format=json"
)
req = urllib.request.Request(api, headers={"User-Agent": UA})
with urllib.request.urlopen(req, timeout=20) as r:
    data = json.loads(r.read())

# Build: canonical_filename → thumb_url
wiki_thumb_map: dict[str, str] = {}
for page in data.get("query", {}).get("pages", {}).values():
    title = page.get("title", "").replace("File:", "").replace("_", " ")
    info  = (page.get("imageinfo") or [{}])[0]
    url   = info.get("thumburl") or info.get("url", "")
    if url:
        wiki_thumb_map[title] = url
        wiki_thumb_map[title.replace(" ", "_")] = url  # also store underscore variant

print(f"  {len(wiki_thumb_map)//2} taom rasmi topildi")

# ── Step 2: Build key → image_url mapping
key_to_url: dict[str, str] = {}

for key, wiki_fn in WIKI.items():
    url = wiki_thumb_map.get(wiki_fn) or wiki_thumb_map.get(wiki_fn.replace(" ", "_"))
    if url:
        key_to_url[key] = url
    else:
        print(f"  [!] topilmadi: {wiki_fn}")

for key, cdn_url in UNSPLASH.items():
    key_to_url[key] = cdn_url

# ── Step 3: Update DB
conn = sqlite3.connect(DB, timeout=30)
conn.execute("PRAGMA journal_mode=WAL")
updated = 0
for product_name, img_key in PRODUCT_MAP.items():
    url = key_to_url.get(img_key)
    if not url:
        print(f"  [skip] {product_name}: no URL")
        continue
    cur = conn.execute(
        "UPDATE products SET image_url=? WHERE name=? AND tenant_id='tenant_001' AND is_active=1",
        (url, product_name),
    )
    if cur.rowcount:
        updated += 1

conn.commit()
conn.close()

print(f"\nDB yangilandi: {updated} ta mahsulot")
print("Rasmlar Wikimedia/Unsplash CDN dan yuklanadi — server restart kerak emas.")

# -*- coding: utf-8 -*-
"""Download food images for menu products and store them locally."""
import sqlite3, os, urllib.request, urllib.parse, urllib.error, json, time, sys
sys.stdout.reconfigure(encoding="utf-8")

DB      = r"C:\Users\user\Desktop\Customer Service Bot\saas_bot\data\tenant_001.db"
IMG_DIR = r"C:\Users\user\Desktop\Customer Service Bot\saas_bot\webapp\img\products"
BASE    = "/webapp/img/products"
os.makedirs(IMG_DIR, exist_ok=True)

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
HEADERS = {"User-Agent": UA, "Accept": "image/webp,image/*,*/*;q=0.8"}

# Wikimedia filenames → local safe name
WIKI_FILES = {
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

# Unsplash: local_key → full CDN URL (no download from Unsplash due to network; store URL directly)
UNSPLASH_URLS = {
    "Achchiqchuchuk":       "https://images.unsplash.com/photo-1608649409268-3b89b9f223f8?w=400&h=300&fit=crop&q=80",
    "Toshkent_salati":      "https://plus.unsplash.com/premium_photo-1670263779633-5309cae32f13?w=400&h=300&fit=crop&q=80",
    "Kok_salat":            "https://plus.unsplash.com/premium_photo-1701870910794-f2ed7f50a088?w=400&h=300&fit=crop&q=80",
    "Kok_choy":             "https://images.unsplash.com/photo-1581348304131-9d03407316b7?w=400&h=300&fit=crop&q=80",
    "Qora_choy":            "https://images.unsplash.com/photo-1556679343-c7306c1976bc?w=400&h=300&fit=crop&q=80",
    "Mineral_suv":          "https://images.unsplash.com/photo-1563865436874-9aef32095fad?w=400&h=300&fit=crop&q=80",
    "CocaCola":             "https://images.unsplash.com/photo-1554866585-bf710a2a47c5?w=400&h=300&fit=crop&q=80",
}

# DB product name → local image key (no extension)
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

# --- Step 1: Batch-fetch all Wikimedia thumb URLs ---
print("Step 1: Wikimedia batch API...")
titles = "|".join(f"File:{fn.replace(' ','_')}" for fn in WIKI_FILES.values())
# Wikimedia API has a 50-title limit; split if needed
def fetch_wiki_batch(file_list: list[str]) -> dict[str, str]:
    """Return {filename: thumb_url}"""
    result = {}
    chunk_size = 50
    for i in range(0, len(file_list), chunk_size):
        chunk = file_list[i:i+chunk_size]
        enc_titles = "|".join(f"File:{fn.replace(' ','_')}" for fn in chunk)
        api = (
            "https://commons.wikimedia.org/w/api.php?action=query"
            f"&titles={urllib.parse.quote(enc_titles)}"
            "&prop=imageinfo&iiprop=url%7Cthumburl&iiurlwidth=400&format=json"
        )
        try:
            req = urllib.request.Request(api, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=20) as r:
                data = json.loads(r.read())
            for page in data.get("query", {}).get("pages", {}).values():
                title = page.get("title", "")
                fn = title.replace("File:", "").replace("_", " ")
                info = (page.get("imageinfo") or [{}])[0]
                url = info.get("thumburl") or info.get("url")
                if url:
                    result[fn] = url
        except Exception as e:
            print(f"  [batch err] {e}")
        time.sleep(1)
    return result

wiki_urls = fetch_wiki_batch(list(WIKI_FILES.values()))
print(f"  Got {len(wiki_urls)} URLs from Wikimedia")

# --- Step 2: Download each Wikimedia image ---
def dl(url: str, dest: str) -> bool:
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=25) as r:
                data = r.read()
            if len(data) < 4096:
                print(f"    too small ({len(data)} B)")
                return False
            with open(dest, "wb") as f:
                f.write(data)
            return True
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = 30 * (attempt + 1)
                print(f"    429 - waiting {wait}s...")
                time.sleep(wait)
            else:
                print(f"    HTTP {e.code}")
                return False
        except Exception as e:
            if attempt < 2:
                print(f"    err ({e}), retry...")
                time.sleep(5)
            else:
                print(f"    failed: {e}")
                return False
    return False

conn = sqlite3.connect(DB)
ok = fail = skipped = 0

print("\nStep 2: Downloading Wikimedia images (4s delay each)...")
for local_key, wiki_fn in WIKI_FILES.items():
    filepath = os.path.join(IMG_DIR, local_key + ".jpg")
    url_path = f"{BASE}/{local_key}.jpg"

    # Find this product's DB name(s) from PRODUCT_MAP
    db_names = [k for k, v in PRODUCT_MAP.items() if v == local_key]

    if os.path.exists(filepath) and os.path.getsize(filepath) > 4096:
        print(f"  [cached] {local_key}.jpg")
        skipped += 1
        for name in db_names:
            conn.execute(
                "UPDATE products SET image_url=? WHERE name=? AND tenant_id='tenant_001' AND is_active=1",
                (url_path, name),
            )
        continue

    # Normalize wiki_fn for lookup (the API returns with spaces, not underscores)
    lookup_key = wiki_fn.replace("_", " ")
    thumb_url = wiki_urls.get(lookup_key) or wiki_urls.get(wiki_fn)
    if not thumb_url:
        print(f"  [no URL] {wiki_fn}")
        fail += 1
        continue

    print(f"  {local_key}.jpg ... ", end="", flush=True)
    success = dl(thumb_url, filepath)
    if success:
        sz = os.path.getsize(filepath)
        print(f"OK ({sz//1024}KB)")
        ok += 1
        for name in db_names:
            conn.execute(
                "UPDATE products SET image_url=? WHERE name=? AND tenant_id='tenant_001' AND is_active=1",
                (url_path, name),
            )
    else:
        fail += 1
    time.sleep(4)

# --- Step 3: Store Unsplash URLs directly in DB (no download) ---
print("\nStep 3: Unsplash URLs (stored as external links)...")
for local_key, cdn_url in UNSPLASH_URLS.items():
    db_names = [k for k, v in PRODUCT_MAP.items() if v == local_key]
    # Try to download; if blocked, store external URL
    filepath = os.path.join(IMG_DIR, local_key + ".jpg")
    url_path = f"{BASE}/{local_key}.jpg"
    if os.path.exists(filepath) and os.path.getsize(filepath) > 4096:
        print(f"  [cached] {local_key}")
        for name in db_names:
            conn.execute(
                "UPDATE products SET image_url=? WHERE name=? AND tenant_id='tenant_001' AND is_active=1",
                (url_path, name),
            )
        continue
    print(f"  {local_key} ... ", end="", flush=True)
    success = dl(cdn_url, filepath)
    if success:
        sz = os.path.getsize(filepath)
        print(f"OK local ({sz//1024}KB)")
        stored_url = url_path
        ok += 1
    else:
        # Fall back to external URL
        print(f"local failed, using external URL")
        stored_url = cdn_url
    for name in db_names:
        conn.execute(
            "UPDATE products SET image_url=? WHERE name=? AND tenant_id='tenant_001' AND is_active=1",
            (stored_url, name),
        )
    time.sleep(2)

conn.commit()
conn.close()

print(f"\n{'='*50}")
print(f"Yangi: {ok}  |  Cached: {skipped}  |  Xato: {fail}")
local_count = len([f for f in os.listdir(IMG_DIR) if f.endswith('.jpg')])
print(f"Local fayllar: {local_count} ta  → {IMG_DIR}")

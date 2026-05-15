# -*- coding: utf-8 -*-
import sqlite3, urllib.request, urllib.parse, json, sys
sys.stdout.reconfigure(encoding="utf-8")

UA = "Mozilla/5.0"
fn = "Jizzakh somsa (samosa).jpg"
enc = urllib.parse.quote("File:" + fn.replace(" ", "_"))
api = f"https://commons.wikimedia.org/w/api.php?action=query&titles={enc}&prop=imageinfo&iiprop=url|thumburl&iiurlwidth=400&format=json"
req = urllib.request.Request(api, headers={"User-Agent": UA})
with urllib.request.urlopen(req, timeout=10) as r:
    d = json.loads(r.read())

url = ""
for p in d.get("query", {}).get("pages", {}).values():
    info = (p.get("imageinfo") or [{}])[0]
    url = info.get("thumburl") or info.get("url", "")

print("URL:", url)
db = r"C:\Users\user\Desktop\Customer Service Bot\saas_bot\data\tenant_001.db"
conn = sqlite3.connect(db, timeout=15)
conn.execute("PRAGMA journal_mode=WAL")
conn.execute(
    "UPDATE products SET image_url=? WHERE name=? AND tenant_id='tenant_001' AND is_active=1",
    (url, "Tandirda somsa (2 ta)"),
)
conn.commit()
conn.close()
print("Tandirda somsa yangilandi!")

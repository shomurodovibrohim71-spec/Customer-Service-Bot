"""Run this script to test receipt printing.
Usage:
    cd saas_bot
    python test_printer.py

Lists all installed printers, then prints a test order to PRINTER_NAME from .env.
"""
import asyncio
import sys
sys.path.insert(0, ".")

from dotenv import load_dotenv
load_dotenv()

import win32print
from config.settings import get_printer_name

print("=== Installed printers ===")
printers = win32print.EnumPrinters(
    win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
)
for p in printers:
    print(f"  • {p[2]}")

printer_name = get_printer_name()
print(f"\nPRINTER_NAME in .env: '{printer_name}'")

if not printer_name:
    print("Set PRINTER_NAME in .env and re-run.")
    sys.exit(0)

if not any(p[2] == printer_name for p in printers):
    print(f"WARNING: '{printer_name}' not found in installed printers!")
    print("Check the name above and update PRINTER_NAME in .env.")
    sys.exit(1)

# Test order data
TEST_ORDER = {
    "id": 999,
    "items": [
        {"name": "Burger Classic", "qty": 2, "price": 35000},
        {"name": "Kartoshka fri",  "qty": 1, "price": 15000},
        {"name": "Pepsi 0.5L",     "qty": 3, "price": 8000},
    ],
    "full_name":      "Ibrohim Shomurodov",
    "phone":          "+998901234567",
    "address":        "Yunusobod tumani, 4-mavze, 15-uy",
    "delivery_type":  "delivery",
    "branch":         "Burger House | Yunusobod",
    "amount":         109000,
    "payment_method": "cash",
    "note":           "Tuzini kam soling",
    "courier_note":   "Qo'ng'iroq qilmang, eshikni taqillatib keting",
    "floor":          "3",
    "entrance":       "2",
    "apartment":      "47",
    "intercom":       "47",
    "discount":       0,
    "promo_code":     "",
    "preferred_time": "Imkon qadar tezroq",
    "service":        "",
}

async def main():
    from utils.printer import print_order_receipts
    print(f"\nPrinting 3 test receipts to '{printer_name}'...")
    await print_order_receipts(TEST_ORDER, tenant_name="Burger House")
    print("Done! Check the printer.")

asyncio.run(main())

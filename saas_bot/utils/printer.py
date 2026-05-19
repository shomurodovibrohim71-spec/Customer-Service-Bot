"""ESC/POS receipt printer — XP-80C (and compatible) thermal printers.

Prints 3 receipts per order automatically:
  1. Kitchen (items + kitchen note)
  2. Courier (address + payment)
  3. Admin   (full summary)

Requires pywin32 on Windows. Set PRINTER_NAME in .env to enable.
If printer is unavailable, prints are skipped and a warning is logged.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# ──────────────────────────── ESC/POS constants ──────────────────────────────
ESC = b'\x1b'
GS  = b'\x1d'

INIT      = ESC + b'@'          # initialize printer
ALIGN_L   = ESC + b'a\x00'     # left
ALIGN_C   = ESC + b'a\x01'     # center
BOLD_ON   = ESC + b'E\x01'
BOLD_OFF  = ESC + b'E\x00'
# Double-width + double-height + bold  (bit 3=bold, 4=dbl-width, 5=dbl-height)
BIG_ON    = ESC + b'!\x38'
BIG_OFF   = ESC + b'!\x00'
CUT       = GS  + b'V\x42\x04' # partial cut, feed 4 dots

WIDTH = 42   # characters per line (80 mm roll @ 12 CPI ≈ 42 chars)


# ──────────────────────────── text helpers ────────────────────────────────────
def _enc(text: str) -> bytes:
    """Encode text to CP1252 (safe for Uzbek Latin + basic symbols)."""
    # Replace Uzbek-specific apostrophe variants with plain apostrophe
    text = text.replace("’", "'").replace("ʼ", "'")
    return text.encode("cp1252", errors="replace")


def _row(left: str, right: str, width: int = WIDTH) -> bytes:
    """Two-column row: left text + right-aligned value."""
    right = right[:width]
    left  = left[:width - len(right) - 1]
    padding = width - len(left) - len(right)
    return _enc(left + " " * padding + right) + b'\n'


def _center(text: str, width: int = WIDTH) -> bytes:
    return _enc(text.center(width)[:width]) + b'\n'


def _divider(char: str = "-", width: int = WIDTH) -> bytes:
    return _enc(char * width) + b'\n'


def _wrap(text: str, width: int = WIDTH, indent: int = 2) -> bytes:
    """Word-wrap text and return ESC/POS bytes."""
    out = bytearray()
    words = text.split()
    line  = ""
    for w in words:
        if len(line) + len(w) + (1 if line else 0) <= width - indent:
            line += (" " if line else "") + w
        else:
            if line:
                out += _enc(" " * indent + line + "\n")
            line = w
    if line:
        out += _enc(" " * indent + line + "\n")
    return bytes(out)


# ──────────────────────────── receipt builders ────────────────────────────────

def build_kitchen_receipt(order: dict) -> bytes:
    """Chef receipt: big order number + items, easy to read from distance."""
    now   = datetime.now().strftime("%H:%M   %d.%m.%Y")
    items = order.get("items") or []
    note  = (order.get("note") or "").strip()

    buf = bytearray()
    buf += INIT + ALIGN_C

    # ── order number (very big) ──
    buf += BIG_ON
    buf += _enc(f"  BUYURTMA #{order['id']}  \n")
    buf += BIG_OFF
    buf += _enc(now + "\n")
    buf += _divider("=")

    buf += BOLD_ON + _center("OSHPAZ / KITCHEN") + BOLD_OFF
    buf += _divider("-")

    # ── items (big font) ──
    buf += ALIGN_L
    if items:
        for it in items:
            qty  = it.get("qty", 1)
            name = it.get("name", "")[:28]
            buf += BIG_ON
            buf += _enc(f"  {qty}x  {name}\n")
            buf += BIG_OFF
    else:
        buf += _enc(f"  {order.get('service', '')}\n")

    # ── kitchen note ──
    if note:
        buf += b'\n' + _divider("-")
        buf += BOLD_ON + _enc("IZOH (RESTORAN):\n") + BOLD_OFF
        buf += _wrap(note)

    buf += b'\n' + _divider("=") + b'\n\n\n' + CUT
    return bytes(buf)


def build_courier_receipt(order: dict) -> bytes:
    """Courier receipt: customer contact + full address + payment."""
    now = datetime.now().strftime("%H:%M   %d.%m.%Y")

    buf = bytearray()
    buf += INIT + ALIGN_C

    buf += BIG_ON
    buf += _enc(f"  BUYURTMA #{order['id']}  \n")
    buf += BIG_OFF
    buf += _enc(now + "\n")
    buf += _divider("=")

    buf += BOLD_ON + _center("KURYER") + BOLD_OFF
    buf += _divider("-")

    buf += ALIGN_L

    # ── customer ──
    name  = (order.get("full_name") or "").strip()
    phone = (order.get("phone") or "").strip()
    if name:
        buf += BOLD_ON + _enc("MIJOZ: ") + BOLD_OFF + _enc(name + "\n")
    if phone:
        buf += BOLD_ON + _enc("TEL:   ") + BOLD_OFF + _enc(phone + "\n")

    buf += b'\n'

    # ── address ──
    address = (order.get("address") or "").strip()
    delivery = (order.get("delivery_type") or "delivery")
    if delivery == "pickup":
        branch = (order.get("branch") or "").strip()
        buf += BOLD_ON + _enc("OLIB KETISH:\n") + BOLD_OFF
        buf += _enc(f"  {branch}\n")
    elif address:
        buf += BOLD_ON + _enc("MANZIL:\n") + BOLD_OFF
        buf += _wrap(address)

    # ── building details ──
    bldg: list[str] = []
    if order.get("floor"):     bldg.append(f"Qavat: {order['floor']}")
    if order.get("entrance"):  bldg.append(f"Podyez: {order['entrance']}")
    if order.get("apartment"): bldg.append(f"Xonadon: {order['apartment']}")
    if order.get("intercom"):  bldg.append(f"Domofon: {order['intercom']}")
    for b in bldg:
        buf += _enc(f"  {b}\n")

    # ── courier note ──
    courier_note = (order.get("courier_note") or "").strip()
    if courier_note:
        buf += b'\n'
        buf += BOLD_ON + _enc("IZOH:\n") + BOLD_OFF
        buf += _wrap(courier_note)

    buf += b'\n' + _divider("-")

    # ── payment (big) ──
    pay   = "Karta" if order.get("payment_method") == "card" else "Naqd pul"
    total = order.get("amount", 0)
    buf += ALIGN_C + BOLD_ON
    buf += BIG_ON + _enc(f"{total:,} so'm\n") + BIG_OFF
    buf += _enc(f"To'lov: {pay}\n")
    buf += BOLD_OFF

    buf += _divider("=") + b'\n\n\n' + CUT
    return bytes(buf)


def build_admin_receipt(order: dict, tenant_name: str = "") -> bytes:
    """Admin receipt: full order details with item breakdown."""
    now   = datetime.now().strftime("%H:%M   %d.%m.%Y")
    items = order.get("items") or []

    buf = bytearray()
    buf += INIT + ALIGN_C

    # ── shop name ──
    if tenant_name:
        buf += BOLD_ON + _enc(tenant_name[:WIDTH].center(WIDTH) + "\n") + BOLD_OFF

    buf += BIG_ON
    buf += _enc(f"  BUYURTMA #{order['id']}  \n")
    buf += BIG_OFF
    buf += _enc(now + "\n")
    buf += _divider("=")

    buf += BOLD_ON + _center("ADMIN NUSXASI") + BOLD_OFF
    buf += _divider("-")

    buf += ALIGN_L

    # ── customer ──
    name    = (order.get("full_name") or "").strip()
    phone   = (order.get("phone") or "").strip()
    delivery = order.get("delivery_type", "delivery")
    branch  = (order.get("branch") or "").strip()
    address = (order.get("address") or "").strip()

    if name:     buf += _enc(f"Mijoz:  {name}\n")
    if phone:    buf += _enc(f"Tel:    {phone}\n")
    if delivery == "pickup":
        buf += _enc(f"Usul:   Olib ketish\n")
        if branch: buf += _enc(f"Filial: {branch}\n")
    else:
        buf += _enc(f"Usul:   Yetkazib berish\n")
        if branch:  buf += _enc(f"Filial: {branch}\n")
        if address: buf += _enc(f"Manzil: {address[:38]}\n")

    # building details
    bldg: list[str] = []
    if order.get("floor"):     bldg.append(f"Qavat {order['floor']}")
    if order.get("entrance"):  bldg.append(f"Podyez {order['entrance']}")
    if order.get("apartment"): bldg.append(f"Xonadon {order['apartment']}")
    if order.get("intercom"):  bldg.append(f"Domofon {order['intercom']}")
    if bldg:
        buf += _enc("        " + "  ".join(bldg) + "\n")

    preferred = (order.get("preferred_time") or "").strip()
    if preferred:
        buf += _enc(f"Vaqt:   {preferred}\n")

    buf += b'\n' + _divider("-")

    # ── items ──
    buf += BOLD_ON + _enc("MAHSULOTLAR:\n") + BOLD_OFF
    subtotal = 0
    for it in items:
        qty   = it.get("qty", 1)
        iname = it.get("name", "")
        price = it.get("price", 0)
        line_total = qty * price
        subtotal  += line_total
        buf += _row(f"  {qty}x {iname}"[:30], f"{line_total:,}")

    service = (order.get("service") or "").strip()
    if service and not items:
        buf += _enc(f"  {service}\n")

    buf += _divider("-")

    # ── totals ──
    discount = order.get("discount", 0)
    if discount:
        buf += _row("  Chegirma:", f"-{discount:,}")

    pay   = "Karta" if order.get("payment_method") == "card" else "Naqd pul"
    total = order.get("amount", 0)
    promo = (order.get("promo_code") or "").strip()
    if promo:
        buf += _enc(f"  Promokod: {promo}\n")

    buf += ALIGN_C + BOLD_ON
    buf += BIG_ON + _enc(f"{total:,} so'm\n") + BIG_OFF
    buf += _enc(f"To'lov: {pay}\n")
    buf += BOLD_OFF

    # ── notes ──
    note         = (order.get("note") or "").strip()
    courier_note = (order.get("courier_note") or "").strip()
    if note or courier_note:
        buf += b'\n' + ALIGN_L + _divider("-")
        if note:
            buf += BOLD_ON + _enc("Restoranga: ") + BOLD_OFF + _enc(note + "\n")
        if courier_note:
            buf += BOLD_ON + _enc("Kuryerga:   ") + BOLD_OFF + _enc(courier_note + "\n")

    buf += b'\n' + _divider("=") + b'\n\n\n' + CUT
    return bytes(buf)


# ──────────────────────────── Windows print send ──────────────────────────────

def _send_to_printer(printer_name: str, data: bytes) -> None:
    """Send raw ESC/POS bytes to a named Windows printer."""
    import win32print  # pywin32
    hprinter = win32print.OpenPrinter(printer_name)
    try:
        win32print.StartDocPrinter(hprinter, 1, ("Order Receipt", None, "RAW"))
        try:
            win32print.StartPagePrinter(hprinter)
            win32print.WritePrinter(hprinter, data)
            win32print.EndPagePrinter(hprinter)
        finally:
            win32print.EndDocPrinter(hprinter)
    finally:
        win32print.ClosePrinter(hprinter)


# ──────────────────────────── main async entry ────────────────────────────────

async def print_order_receipts(order: dict, tenant_name: str = "") -> None:
    """
    Print 3 receipts for a new order (async, non-blocking).
    order dict must contain: id, items, full_name, phone, address, amount,
    payment_method, delivery_type, branch, note, courier_note,
    floor, entrance, apartment, intercom, discount, promo_code, preferred_time.
    Skipped silently if PRINTER_NAME is not set or printer is unreachable.
    """
    from config.settings import get_printer_name
    printer_name = get_printer_name()
    if not printer_name:
        return

    receipts = [
        ("kitchen", build_kitchen_receipt(order)),
        ("courier", build_courier_receipt(order)),
        ("admin",   build_admin_receipt(order, tenant_name)),
    ]

    loop = asyncio.get_event_loop()
    for receipt_type, data in receipts:
        try:
            await loop.run_in_executor(None, _send_to_printer, printer_name, data)
            logger.info("Printed %s receipt for order #%s", receipt_type, order.get("id"))
        except Exception as exc:
            logger.error("Failed to print %s receipt for order #%s: %s",
                         receipt_type, order.get("id"), exc)

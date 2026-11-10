"""Türkçe sayı/tarih biçimlerini ayrıştırma yardımcıları."""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal, InvalidOperation


def parse_tr_amount(raw: str) -> Decimal:
    """'1.234,56 TL' -> Decimal('1234.56'). '1,234.56' biçimini de tanır."""
    s = re.sub(r"[^\d.,-]", "", raw)
    if not s:
        raise ValueError(f"Tutar bulunamadı: {raw!r}")
    if "," in s and "." in s:
        # Son görülen ayırıcı ondalık ayırıcıdır
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")
    elif s.count(".") > 1 or re.fullmatch(r"-?\d{1,3}\.\d{3}", s):
        # 1.234.567 ya da 1.234 -> binlik ayırıcı
        s = s.replace(".", "")
    try:
        return Decimal(s)
    except InvalidOperation as e:
        raise ValueError(f"Geçersiz tutar: {raw!r}") from e


_MONTHS = {
    "ocak": 1,
    "şubat": 2,
    "mart": 3,
    "nisan": 4,
    "mayıs": 5,
    "haziran": 6,
    "temmuz": 7,
    "ağustos": 8,
    "eylül": 9,
    "ekim": 10,
    "kasım": 11,
    "aralık": 12,
}


def tr_lower(s: str) -> str:
    """Türkçe'ye uygun küçük harf: 'KASIM' -> 'kasım' (str.lower() 'kasim' verir)."""
    return s.replace("I", "ı").replace("İ", "i").lower()


def parse_tr_date(raw: str) -> date:
    """'05.11.2026', '05/11/2026', '2026-11-05' veya '5 Kasım 2026'."""
    raw = raw.strip()
    if m := re.search(r"(\d{4})-(\d{2})-(\d{2})", raw):
        y, mo, d = map(int, m.groups())
        return date(y, mo, d)
    if m := re.search(r"(\d{1,2})[./-](\d{1,2})[./-](\d{4})", raw):
        d, mo, y = map(int, m.groups())
        return date(y, mo, d)
    if m := re.search(r"(\d{1,2})\s+([a-zçğıöşü]+)\s+(\d{4})", tr_lower(raw)):
        d, month_name, y = m.groups()
        if month_name in _MONTHS:
            return date(int(y), _MONTHS[month_name], int(d))
    raise ValueError(f"Tarih ayrıştırılamadı: {raw!r}")

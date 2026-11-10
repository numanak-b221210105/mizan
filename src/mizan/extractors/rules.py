"""Kural tabanlı (regex) çıkarıcı.

Hızlı, ücretsiz ve deterministik; ama yalnızca bilinen şablonlarda çalışır.
LLM çıkarıcısıyla kıyaslamak için temel çizgi (baseline) olarak kullanılır.
"""

from __future__ import annotations

import re

from ..numbers import parse_tr_amount, parse_tr_date
from ..schema import Invoice, LineItem, Party

_INVOICE_NO = re.compile(r"Fatura\s*(?:No|Numarası)\s*[:#]\s*(\S+)", re.IGNORECASE)
_DATE = re.compile(r"(?:Fatura|Düzenleme)\s*Tarihi\s*:\s*(.+)", re.IGNORECASE)
_CURRENCY = re.compile(r"Para\s*Birimi\s*:\s*(\w+)", re.IGNORECASE)
_SUBTOTAL = re.compile(r"(?:Mal\s*Hizmet\s*Toplam\s*Tutarı|Ara\s*Toplam)\s*:\s*(.+)", re.IGNORECASE)
_VAT = re.compile(r"(?:Hesaplanan\s*KDV|Toplam\s*KDV)\s*:\s*(.+)", re.IGNORECASE)
_GRAND = re.compile(r"(?:Ödenecek\s*Tutar|Genel\s*Toplam)\s*:\s*(.+)", re.IGNORECASE)
_ITEM = re.compile(
    r"^\s*(?P<desc>[^|\n]+?)\s*\|\s*(?P<qty>[\d.,]+)\s*\|\s*(?P<price>[\d.,]+)"
    r"\s*\|\s*%?(?P<vat>\d+)\s*\|\s*(?P<total>[\d.,]+)\s*$",
    re.MULTILINE,
)


def _section(text: str, header: str) -> str:
    """'SATICI' gibi bir başlıktan sonraki boş satıra kadar olan bloğu döndürür."""
    m = re.search(rf"^\s*{header}\b.*?$(.*?)(?:^\s*$|\Z)", text, re.MULTILINE | re.DOTALL | re.IGNORECASE)
    return m.group(1) if m else ""


def _field(block: str, *labels: str) -> str | None:
    for label in labels:
        if m := re.search(rf"{label}\s*:\s*(.+)", block, re.IGNORECASE):
            return m.group(1).strip()
    return None


def _party(block: str) -> Party:
    name = _field(block, "Ünvan", "Unvan", "Ad Soyad")
    if not name:
        raise ValueError("Taraf ünvanı bulunamadı")
    return Party(
        name=name,
        tax_id=_field(block, "VKN", "TCKN"),
        tax_office=_field(block, "Vergi Dairesi"),
    )


def _require(pattern: re.Pattern[str], text: str, what: str) -> str:
    m = pattern.search(text)
    if not m:
        raise ValueError(f"{what} bulunamadı")
    return m.group(1).strip()


class RuleExtractor:
    name = "rules"

    def extract(self, text: str) -> Invoice:
        items = [
            LineItem(
                description=m["desc"].strip(),
                quantity=parse_tr_amount(m["qty"]),
                unit_price=parse_tr_amount(m["price"]),
                vat_rate=int(m["vat"]),
                line_total=parse_tr_amount(m["total"]),
            )
            for m in _ITEM.finditer(text)
        ]
        currency = _CURRENCY.search(text)
        return Invoice(
            invoice_no=_require(_INVOICE_NO, text, "Fatura no"),
            issue_date=parse_tr_date(_require(_DATE, text, "Fatura tarihi")),
            seller=_party(_section(text, "SATICI")),
            buyer=_party(_section(text, "ALICI")),
            currency=currency.group(1) if currency else "TRY",
            items=items,
            subtotal=parse_tr_amount(_require(_SUBTOTAL, text, "Ara toplam")),
            vat_total=parse_tr_amount(_require(_VAT, text, "KDV toplamı")),
            grand_total=parse_tr_amount(_require(_GRAND, text, "Ödenecek tutar")),
        )

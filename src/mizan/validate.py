"""İş kuralı doğrulamaları.

Şema "tip doğru mu?" sorusunu cevaplar; burası "rakamlar birbiriyle tutarlı mı?"
sorusunu. LLM halüsinasyonlarını yakalamanın en ucuz yolu budur.
"""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from .schema import Invoice

TOLERANCE = Decimal("0.05")  # kuruş yuvarlama farkları için
VALID_VAT_RATES = {0, 1, 8, 10, 18, 20}


def _close(a: Decimal, b: Decimal) -> bool:
    return abs(a - b) <= TOLERANCE


def check(inv: Invoice) -> tuple[list[str], list[str]]:
    """(hatalar, uyarılar) döndürür. Hata = veri büyük ihtimalle yanlış."""
    errors: list[str] = []
    warnings: list[str] = []

    if not _close(inv.subtotal + inv.vat_total, inv.grand_total):
        errors.append(
            f"Ara toplam + KDV ({inv.subtotal + inv.vat_total}) "
            f"ödenecek tutara ({inv.grand_total}) eşit değil"
        )

    if not inv.items:
        warnings.append("Fatura kalemi bulunamadı")
        return errors, warnings

    vat_by_rate: dict[int, Decimal] = defaultdict(Decimal)
    for i, item in enumerate(inv.items, 1):
        expected = item.quantity * item.unit_price
        if not _close(expected, item.line_total):
            errors.append(
                f"{i}. kalem: miktar x birim fiyat ({expected}) satır tutarına ({item.line_total}) eşit değil"
            )
        if item.vat_rate not in VALID_VAT_RATES:
            warnings.append(f"{i}. kalem: alışılmadık KDV oranı %{item.vat_rate}")
        vat_by_rate[item.vat_rate] += item.line_total * item.vat_rate / 100

    items_sum = sum((it.line_total for it in inv.items), Decimal())
    if not _close(items_sum, inv.subtotal):
        errors.append(f"Kalemler toplamı ({items_sum}) ara toplama ({inv.subtotal}) eşit değil")

    expected_vat = sum(vat_by_rate.values(), Decimal()).quantize(Decimal("0.01"))
    if not _close(expected_vat, inv.vat_total):
        errors.append(f"Hesaplanan KDV ({expected_vat}) belgedeki KDV'ye ({inv.vat_total}) eşit değil")

    if inv.seller.tax_id and inv.seller.tax_id == inv.buyer.tax_id:
        warnings.append("Satıcı ve alıcı vergi numarası aynı")

    return errors, warnings

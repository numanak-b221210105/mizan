"""İş kuralı doğrulamaları.

Şema "tip doğru mu?" sorusunu cevaplar; burası "rakamlar birbiriyle tutarlı mı?"
sorusunu. LLM halüsinasyonlarını yakalamanın en ucuz yolu budur.

Her kural bir `Check` üretir; arayüz bunları kontrol listesi olarak gösterir.
Başarısız kurallar `errors` (veri büyük ihtimalle yanlış) ya da `warnings`
(dikkat edilmeli) listesine de yazılır.
"""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from .ids import is_valid_tax_id
from .schema import Check, Invoice, VatLine

TOLERANCE = Decimal("0.05")  # kuruş yuvarlama farkları için
VALID_VAT_RATES = {0, 1, 8, 10, 18, 20}
CENT = Decimal("0.01")


def _close(a: Decimal, b: Decimal) -> bool:
    return abs(a - b) <= TOLERANCE


def vat_breakdown(inv: Invoice) -> list[VatLine]:
    base: dict[int, Decimal] = defaultdict(Decimal)
    for item in inv.items:
        base[item.vat_rate] += item.line_total
    return [
        VatLine(rate=r, base=b.quantize(CENT), vat=(b * r / 100).quantize(CENT))
        for r, b in sorted(base.items())
    ]


def run_checks(inv: Invoice) -> tuple[list[Check], list[str], list[str]]:
    """(kontroller, hatalar, uyarılar) döndürür."""
    checks: list[Check] = []
    errors: list[str] = []
    warnings: list[str] = []

    def add(cid: str, label: str, passed: bool | None, detail: str | None = None, severe: bool = True):
        checks.append(Check(id=cid, label=label, passed=passed, detail=detail))
        if passed is False and detail:
            (errors if severe else warnings).append(detail)

    # 1. Ara toplam + KDV = ödenecek
    ok = _close(inv.subtotal + inv.vat_total, inv.grand_total)
    add(
        "totals_balance",
        "Subtotal + VAT = payable",
        ok,
        None
        if ok
        else f"Ara toplam + KDV ({inv.subtotal + inv.vat_total}) ödenecek tutara ({inv.grand_total}) eşit değil",
    )

    has_items = bool(inv.items)
    if not has_items:
        warnings.append("Fatura kalemi bulunamadı")

    # 2. Her satırda miktar x birim fiyat = tutar
    if has_items:
        bad = [
            f"{i}. kalem: miktar x birim fiyat ({it.quantity * it.unit_price}) satır tutarına ({it.line_total}) eşit değil"
            for i, it in enumerate(inv.items, 1)
            if not _close(it.quantity * it.unit_price, it.line_total)
        ]
        checks.append(
            Check(
                id="line_math",
                label="Qty × unit price = line total",
                passed=not bad,
                detail="; ".join(bad) or None,
            )
        )
        errors.extend(bad)
    else:
        add("line_math", "Qty × unit price = line total", None)

    # 3. Kalemler toplamı = ara toplam
    if has_items:
        items_sum = sum((it.line_total for it in inv.items), Decimal())
        ok = _close(items_sum, inv.subtotal)
        add(
            "items_sum",
            "Line items add up to subtotal",
            ok,
            None if ok else f"Kalemler toplamı ({items_sum}) ara toplama ({inv.subtotal}) eşit değil",
        )
    else:
        add("items_sum", "Line items add up to subtotal", None)

    # 4. KDV, oran bazında yeniden hesaplanır
    if has_items:
        expected = sum((v.vat for v in vat_breakdown(inv)), Decimal())
        ok = _close(expected, inv.vat_total)
        add(
            "vat_calc",
            "VAT matches per-rate calculation",
            ok,
            None if ok else f"Hesaplanan KDV ({expected}) belgedeki KDV'ye ({inv.vat_total}) eşit değil",
        )
    else:
        add("vat_calc", "VAT matches per-rate calculation", None)

    # 5. KDV oranları standart mı
    if has_items:
        odd = sorted({it.vat_rate for it in inv.items} - VALID_VAT_RATES)
        add(
            "vat_rates",
            "Standard Turkish VAT rates",
            not odd,
            None if not odd else f"Alışılmadık KDV oranı: {', '.join(f'%{r}' for r in odd)}",
            severe=False,
        )
    else:
        add("vat_rates", "Standard Turkish VAT rates", None)

    # 6. VKN/TCKN kontrol basamağı
    bad_ids = [
        f"{who} vergi numarası ({p.tax_id}) kontrol basamağı geçersiz"
        for who, p in (("Satıcı", inv.seller), ("Alıcı", inv.buyer))
        if p.tax_id and not is_valid_tax_id(p.tax_id)
    ]
    any_id = bool(inv.seller.tax_id or inv.buyer.tax_id)
    add(
        "tax_id_checksum",
        "Tax ID check digits",
        (not bad_ids) if any_id else None,
        "; ".join(bad_ids) or None,
        severe=False,
    )

    # 7. Satıcı ve alıcı farklı olmalı
    same = bool(inv.seller.tax_id) and inv.seller.tax_id == inv.buyer.tax_id
    add(
        "distinct_parties",
        "Seller and buyer are different",
        not same,
        "Satıcı ve alıcı vergi numarası aynı" if same else None,
        severe=False,
    )

    return checks, errors, warnings


def check(inv: Invoice) -> tuple[list[str], list[str]]:
    """Geriye dönük uyumluluk: yalnızca (hatalar, uyarılar)."""
    _, errors, warnings = run_checks(inv)
    return errors, warnings

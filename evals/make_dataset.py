"""Sentetik eval veri seti üretir (gerçek müşteri verisi kullanılmaz).

Her fatura için iki dosya yazılır:
  dataset/<id>.txt   -> çıkarıcıya verilen belge metni
  dataset/<id>.json  -> doğru cevap (ground truth)

Üç farklı şablon kullanılır; C şablonu kural tabanlı çıkarıcının bilmediği
serbest biçimdir. Böylece eval, LLM'in nerede fark yarattığını gösterir.

Çalıştırma: python evals/make_dataset.py
"""

from __future__ import annotations

import json
import random
import sys
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from mizan.ids import make_vkn

OUT = Path(__file__).parent / "dataset"
MONTHS = [
    "Ocak",
    "Şubat",
    "Mart",
    "Nisan",
    "Mayıs",
    "Haziran",
    "Temmuz",
    "Ağustos",
    "Eylül",
    "Ekim",
    "Kasım",
    "Aralık",
]

COMPANIES = [
    ("Deniz Kimya San. ve Tic. A.Ş.", "Kozyatağı"),
    ("Yıldız Boya Ltd. Şti.", "Adapazarı"),
    ("Marmara Plastik A.Ş.", "Gebze"),
    ("Ege Ambalaj San. Ltd. Şti.", "Bornova"),
    ("Anadolu Lojistik A.Ş.", "Ankara Kurumlar"),
    ("Karadeniz Tekstil Ltd. Şti.", "Trabzon"),
]
PRODUCTS = [
    ("Etil Asetat 200 kg varil", 20),
    ("Bütil Asetat 180 kg varil", 20),
    ("IBC Tank 1000 L", 20),
    ("Laboratuvar analizi", 20),
    ("Nakliye hizmeti", 20),
    ("Gıda ambalaj filmi (rulo)", 10),
    ("Teknik danışmanlık (saat)", 20),
    ("Palet (ahşap)", 10),
]


def q(x: Decimal) -> Decimal:
    return x.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def tr(x: Decimal) -> str:
    """Decimal -> '12.345,67'"""
    s = f"{q(x):,.2f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".")


def vkn(rng: random.Random) -> str:
    """Kontrol basamağı geçerli rastgele VKN."""
    return make_vkn("".join(str(rng.randint(0, 9)) for _ in range(9)))


def make_invoice(rng: random.Random, idx: int) -> dict:
    seller, buyer = rng.sample(COMPANIES, 2)
    items = []
    for desc, rate in rng.sample(PRODUCTS, rng.randint(1, 4)):
        qty = Decimal(rng.randint(1, 12))
        price = q(Decimal(rng.randint(150, 25000)) + Decimal(rng.choice([0, 50, 99])) / 100)
        items.append(
            {
                "description": desc,
                "quantity": str(qty),
                "unit_price": str(price),
                "vat_rate": rate,
                "line_total": str(q(qty * price)),
            }
        )
    subtotal = sum(Decimal(i["line_total"]) for i in items)
    vat = q(sum(Decimal(i["line_total"]) * i["vat_rate"] / 100 for i in items))
    issued = date(2026, 1, 1) + timedelta(days=rng.randint(0, 300))
    return {
        "invoice_no": f"FTR2026{idx:09d}",
        "issue_date": issued.isoformat(),
        "seller": {"name": seller[0], "tax_id": vkn(rng), "tax_office": seller[1]},
        "buyer": {"name": buyer[0], "tax_id": vkn(rng), "tax_office": buyer[1]},
        "currency": "TRY",
        "items": items,
        "subtotal": str(q(subtotal)),
        "vat_total": str(vat),
        "grand_total": str(q(subtotal + vat)),
    }


def render_a(inv: dict) -> str:
    d = date.fromisoformat(inv["issue_date"])
    rows = "\n".join(
        f"{i['description']} | {i['quantity']} | {tr(Decimal(i['unit_price']))} | "
        f"{i['vat_rate']} | {tr(Decimal(i['line_total']))}"
        for i in inv["items"]
    )
    s, b = inv["seller"], inv["buyer"]
    return f"""E-FATURA
Fatura No: {inv["invoice_no"]}
Fatura Tarihi: {d:%d.%m.%Y}

SATICI
Ünvan: {s["name"]}
Vergi Dairesi: {s["tax_office"]}
VKN: {s["tax_id"]}

ALICI
Ünvan: {b["name"]}
Vergi Dairesi: {b["tax_office"]}
VKN: {b["tax_id"]}

Para Birimi: TRY

KALEMLER
Açıklama | Miktar | Birim Fiyat | KDV % | Tutar
{rows}

Mal Hizmet Toplam Tutarı: {tr(Decimal(inv["subtotal"]))} TL
Hesaplanan KDV: {tr(Decimal(inv["vat_total"]))} TL
Ödenecek Tutar: {tr(Decimal(inv["grand_total"]))} TL
"""


def render_b(inv: dict) -> str:
    d = date.fromisoformat(inv["issue_date"])
    rows = "\n".join(
        f"{i['description']} | {i['quantity']} | {tr(Decimal(i['unit_price']))} | "
        f"%{i['vat_rate']} | {tr(Decimal(i['line_total']))}"
        for i in inv["items"]
    )
    s, b = inv["seller"], inv["buyer"]
    return f"""FATURA
Fatura Numarası: {inv["invoice_no"]}
Düzenleme Tarihi: {d.day} {MONTHS[d.month - 1]} {d.year}

SATICI BİLGİLERİ
Unvan: {s["name"]}
Vergi Dairesi: {s["tax_office"]}
VKN: {s["tax_id"]}

ALICI BİLGİLERİ
Unvan: {b["name"]}
Vergi Dairesi: {b["tax_office"]}
VKN: {b["tax_id"]}

{rows}

Ara Toplam: {tr(Decimal(inv["subtotal"]))}
Toplam KDV: {tr(Decimal(inv["vat_total"]))}
Genel Toplam: {tr(Decimal(inv["grand_total"]))}
"""


def render_c(inv: dict) -> str:
    """Serbest biçim: başlık yok, kalemler cümle içinde."""
    d = date.fromisoformat(inv["issue_date"])
    s, b = inv["seller"], inv["buyer"]
    lines = "\n".join(
        f"- {i['quantity']} adet {i['description']}, birimi {tr(Decimal(i['unit_price']))} TL "
        f"(KDV %{i['vat_rate']}), toplam {tr(Decimal(i['line_total']))} TL"
        for i in inv["items"]
    )
    return f"""{s["name"]}
{s["tax_office"]} V.D. - {s["tax_id"]}

Sayın {b["name"]} ({b["tax_office"]} V.D. {b["tax_id"]}),
{d:%d/%m/%Y} tarihli ve {inv["invoice_no"]} numaralı faturanız aşağıdadır.

{lines}

KDV hariç {tr(Decimal(inv["subtotal"]))} TL, KDV {tr(Decimal(inv["vat_total"]))} TL olmak üzere
toplam {tr(Decimal(inv["grand_total"]))} TL ödemenizi rica ederiz.
"""


def main() -> None:
    rng = random.Random(42)
    OUT.mkdir(exist_ok=True)
    plan = ["a"] * 4 + ["b"] * 3 + ["c"] * 3
    renderers = {"a": render_a, "b": render_b, "c": render_c}
    for idx, tpl in enumerate(plan, 1):
        inv = make_invoice(rng, idx)
        stem = f"{idx:02d}_{tpl}"
        (OUT / f"{stem}.txt").write_text(renderers[tpl](inv), encoding="utf-8")
        (OUT / f"{stem}.json").write_text(json.dumps(inv, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"{len(plan)} fatura yazıldı -> {OUT}")


if __name__ == "__main__":
    main()

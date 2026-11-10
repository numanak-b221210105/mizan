"""Çıkarıcıları veri seti üzerinde ölçer.

Metrikler:
  - alan doğruluğu: 9 ana alan + kalem sayısının ne kadarı doğru
  - tam eşleşme: tüm alanları doğru olan belge oranı
  - doğrulama geçişi: iş kuralı kontrolünden hatasız geçen belge oranı

Kullanım:
  python evals/run_eval.py --strategy rules
  python evals/run_eval.py --strategy auto   # LLM ayarları için README'ye bakın
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from mizan import extract

DATASET = Path(__file__).parent / "dataset"
FIELDS = [
    "invoice_no",
    "issue_date",
    "seller.name",
    "seller.tax_id",
    "buyer.name",
    "buyer.tax_id",
    "subtotal",
    "vat_total",
    "grand_total",
    "items.count",
]


def get(d: dict, path: str):
    if path == "items.count":
        return len(d.get("items") or [])
    for key in path.split("."):
        d = d.get(key) if isinstance(d, dict) else None
    return d


def same(a, b) -> bool:
    try:
        return Decimal(str(a)) == Decimal(str(b))
    except Exception:  # noqa: BLE001
        return str(a).strip().lower() == str(b).strip().lower()


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # Windows konsolunda Türkçe/✓ karakterleri
    p = argparse.ArgumentParser()
    p.add_argument("--strategy", choices=["rules", "llm", "auto"], default="rules")
    args = p.parse_args()

    rows, correct_fields, exact, valid = [], 0, 0, 0
    files = sorted(DATASET.glob("*.txt"))
    t0 = time.perf_counter()
    for f in files:
        truth = json.loads(f.with_suffix(".json").read_text("utf-8"))
        res = extract(f.read_text("utf-8"), strategy=args.strategy)
        got = json.loads(res.invoice.model_dump_json()) if res.invoice else {}
        hits = [same(get(got, k), get(truth, k)) for k in FIELDS] if got else [False] * len(FIELDS)
        correct_fields += sum(hits)
        exact += all(hits)
        valid += res.ok
        rows.append((f.stem, sum(hits), res.extractor, "✓" if res.ok else (res.errors or ["?"])[0][:60]))
    elapsed = time.perf_counter() - t0

    print(f"\nStrateji: {args.strategy}   Belge: {len(files)}   Süre: {elapsed:.1f} sn\n")
    print(f"{'belge':<8} {'alan':>6}  {'çıkarıcı':<8} durum")
    for stem, h, ex, status in rows:
        print(f"{stem:<8} {h:>3}/{len(FIELDS)}  {ex:<8} {status}")
    n = len(files) or 1
    print(f"\nAlan doğruluğu : {correct_fields / (n * len(FIELDS)):.0%}")
    print(f"Tam eşleşme    : {exact / n:.0%}")
    print(f"Doğrulama geçişi: {valid / n:.0%}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

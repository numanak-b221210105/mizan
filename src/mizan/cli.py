"""Komut satırı: mizan fatura.pdf --strategy rules"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .pipeline import extract, pdf_to_text


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="mizan", description=__doc__)
    p.add_argument("path", type=Path, help=".pdf veya .txt fatura dosyası")
    p.add_argument("--strategy", choices=["rules", "llm", "auto"], default="auto")
    args = p.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")  # Windows konsolunda Türkçe karakterler

    text = pdf_to_text(args.path) if args.path.suffix.lower() == ".pdf" else args.path.read_text("utf-8")
    result = extract(text, strategy=args.strategy)
    print(result.model_dump_json(indent=2))
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())

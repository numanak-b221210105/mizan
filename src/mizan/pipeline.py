"""Çıkarım hattı: metin -> çıkarıcı(lar) -> doğrulama.

Strateji "auto": önce ücretsiz kural tabanlı çıkarıcı denenir; başarısız olur
veya tutarlılık kontrolünden geçemezse LLM'e düşülür. Gerçek sistemlerde
maliyeti düşürmenin yaygın yolu budur.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from .extractors import Extractor, LLMExtractor, RuleExtractor
from .schema import ExtractionResult
from .validate import check

Strategy = Literal["rules", "llm", "auto"]


def pdf_to_text(source: str | Path | bytes) -> str:
    """PDF dosya yolu veya bayt içeriğinden metin çıkarır."""
    from io import BytesIO

    from pypdf import PdfReader

    reader = PdfReader(BytesIO(source) if isinstance(source, bytes) else str(source))
    return "\n".join(page.extract_text() or "" for page in reader.pages)


def _run(extractor: Extractor, text: str) -> ExtractionResult:
    try:
        invoice = extractor.extract(text)
    except Exception as e:  # noqa: BLE001 - çıkarıcı hatasını sonuca dönüştürüyoruz
        return ExtractionResult(invoice=None, extractor=extractor.name, errors=[str(e)])
    errors, warnings = check(invoice)
    return ExtractionResult(invoice=invoice, extractor=extractor.name, errors=errors, warnings=warnings)


def extract(
    text: str,
    strategy: Strategy = "auto",
    llm: Extractor | None = None,
) -> ExtractionResult:
    if strategy == "rules":
        return _run(RuleExtractor(), text)
    if strategy == "llm":
        return _run(llm or LLMExtractor(), text)

    first = _run(RuleExtractor(), text)
    if first.ok:
        return first
    second = _run(llm or LLMExtractor(), text)
    second.warnings.insert(0, f"Kural tabanlı çıkarım başarısız, LLM kullanıldı: {first.errors}")
    return second

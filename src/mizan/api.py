"""REST API.  Çalıştırma: python -m mizan.serve  (veya uvicorn mizan.api:app --reload)"""

from __future__ import annotations

import os
from collections import defaultdict
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from . import __version__
from .extractors.llm import DEFAULT_BASE_URL, DEFAULT_MODEL
from .pipeline import Strategy, extract, pdf_to_text
from .schema import ExtractionResult

app = FastAPI(
    title="Mizan",
    version=__version__,
    description="Invoice extraction that checks the math — Türkçe faturalardan doğrulanmış veri çıkarımı",
)

MAX_BYTES = 5 * 1024 * 1024
MAX_BATCH = 20
STATIC = Path(__file__).parent / "static"


class TextRequest(BaseModel):
    text: str


class LLMStatus(BaseModel):
    provider: str
    host: str
    model: str
    reachable: bool


class Status(BaseModel):
    version: str
    llm: LLMStatus


class BatchItem(BaseModel):
    filename: str
    result: ExtractionResult


class BatchSummary(BaseModel):
    count: int
    balanced: int
    failed: int
    total_payable: dict[str, Decimal]
    total_vat: dict[str, Decimal]


class BatchResult(BaseModel):
    items: list[BatchItem]
    summary: BatchSummary


@app.get("/", include_in_schema=False)
def ui() -> FileResponse:
    return FileResponse(STATIC / "index.html")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


def _provider(host: str) -> str:
    if host.endswith(":11434") or "ollama" in host:
        return "Ollama"
    if "openai.com" in host:
        return "OpenAI"
    if "googleapis.com" in host:
        return "Gemini"
    if "groq.com" in host:
        return "Groq"
    return "Custom"


@app.get("/status", response_model=Status)
def status() -> Status:
    """Sürüm ve LLM bağlantı durumu (arayüzdeki durum göstergesi için)."""
    import httpx

    base = os.getenv("MIZAN_LLM_BASE_URL", DEFAULT_BASE_URL).rstrip("/")
    host = urlparse(base).netloc or base
    try:
        httpx.get(f"{base}/models", timeout=1.5)  # herhangi bir HTTP yanıtı = sunucu ayakta
        reachable = True
    except httpx.HTTPError:
        reachable = False
    return Status(
        version=__version__,
        llm=LLMStatus(
            provider=_provider(host),
            host=host,
            model=os.getenv("MIZAN_LLM_MODEL", DEFAULT_MODEL),
            reachable=reachable,
        ),
    )


@app.post("/extract/text", response_model=ExtractionResult)
def extract_text(req: TextRequest, strategy: Strategy = Query("auto")) -> ExtractionResult:
    if not req.text.strip():
        raise HTTPException(422, "Metin boş")
    return extract(req.text, strategy=strategy)


def _file_to_text(name: str, data: bytes) -> str:
    if len(data) > MAX_BYTES:
        raise HTTPException(413, f"{name}: dosya 5 MB'tan büyük")
    lower = name.lower()
    if lower.endswith(".pdf"):
        # Bellekten okunur: geçici dosya Windows'ta kilitlenme sorunu çıkarır
        return pdf_to_text(data)
    if lower.endswith(".txt"):
        return data.decode("utf-8", errors="replace")
    raise HTTPException(415, f"{name}: yalnızca .pdf ve .txt desteklenir")


@app.post("/extract/file", response_model=ExtractionResult)
async def extract_file(file: UploadFile = File(...), strategy: Strategy = Query("auto")) -> ExtractionResult:
    name = file.filename or "dosya"
    return extract(_file_to_text(name, await file.read()), strategy=strategy)


@app.post("/extract/batch", response_model=BatchResult)
async def extract_batch(
    files: list[UploadFile] = File(...), strategy: Strategy = Query("auto")
) -> BatchResult:
    """Birden çok faturayı işler ve para birimine göre toplamları döndürür."""
    if len(files) > MAX_BATCH:
        raise HTTPException(413, f"En fazla {MAX_BATCH} dosya gönderilebilir")
    items: list[BatchItem] = []
    payable: dict[str, Decimal] = defaultdict(Decimal)
    vat: dict[str, Decimal] = defaultdict(Decimal)
    for f in files:
        name = f.filename or "dosya"
        result = extract(_file_to_text(name, await f.read()), strategy=strategy)
        items.append(BatchItem(filename=name, result=result))
        if result.ok and result.invoice:
            payable[result.invoice.currency] += result.invoice.grand_total
            vat[result.invoice.currency] += result.invoice.vat_total
    balanced = sum(1 for i in items if i.result.ok)
    return BatchResult(
        items=items,
        summary=BatchSummary(
            count=len(items),
            balanced=balanced,
            failed=len(items) - balanced,
            total_payable=dict(payable),
            total_vat=dict(vat),
        ),
    )

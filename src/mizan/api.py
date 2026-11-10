"""REST API.  Çalıştırma: uvicorn mizan.api:app --reload"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel

from . import __version__
from .pipeline import Strategy, extract, pdf_to_text
from .schema import ExtractionResult

app = FastAPI(
    title="Mizan",
    version=__version__,
    description="Invoice extraction that checks the math — Türkçe faturalardan doğrulanmış veri çıkarımı",
)

MAX_BYTES = 5 * 1024 * 1024
STATIC = Path(__file__).parent / "static"


@app.get("/", include_in_schema=False)
def ui() -> FileResponse:
    return FileResponse(STATIC / "index.html")


class TextRequest(BaseModel):
    text: str


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


@app.post("/extract/text", response_model=ExtractionResult)
def extract_text(req: TextRequest, strategy: Strategy = Query("auto")) -> ExtractionResult:
    if not req.text.strip():
        raise HTTPException(422, "Metin boş")
    return extract(req.text, strategy=strategy)


@app.post("/extract/file", response_model=ExtractionResult)
async def extract_file(file: UploadFile = File(...), strategy: Strategy = Query("auto")) -> ExtractionResult:
    data = await file.read()
    if len(data) > MAX_BYTES:
        raise HTTPException(413, "Dosya 5 MB'tan büyük")
    name = (file.filename or "").lower()
    if name.endswith(".pdf"):
        # Bellekten okunur: geçici dosya Windows'ta kilitlenme sorunu çıkarır
        text = pdf_to_text(data)
    elif name.endswith(".txt"):
        text = data.decode("utf-8", errors="replace")
    else:
        raise HTTPException(415, "Yalnızca .pdf ve .txt desteklenir")
    return extract(text, strategy=strategy)

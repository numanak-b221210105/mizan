"""LLM ile çıkarım (function calling + JSON şema).

Sağlayıcıdan bağımsızdır: OpenAI uyumlu her API ile çalışır
(OpenAI, Google Gemini, Groq, OpenRouter veya yerelde ücretsiz Ollama).

Modelden serbest metin yerine, Pydantic şemasından üretilen bir fonksiyonu
çağırması istenir. Dönen veri yine de Pydantic ile doğrulanır, çünkü modele
körü körüne güvenmiyoruz.

Ortam değişkenleri:
  MIZAN_LLM_BASE_URL  varsayılan: http://localhost:11434/v1  (Ollama)
  MIZAN_LLM_API_KEY   varsayılan: "ollama" (yerel Ollama anahtar istemez)
  MIZAN_LLM_MODEL     varsayılan: qwen2.5:7b
"""

from __future__ import annotations

import json
import os
from typing import Any

from ..schema import Invoice

SYSTEM_PROMPT = """Sen Türkçe ticari faturalardan veri çıkaran bir asistansın.
Kurallar:
- Yalnızca belgede açıkça yazan değerleri kullan; tahmin etme, hesaplayıp uydurma.
- Tutarları nokta ondalıklı sayı olarak yaz (1.234,56 -> 1234.56).
- Tarihleri YYYY-MM-DD biçiminde yaz.
- Belgede olmayan isteğe bağlı alanları null bırak.
- line_total KDV hariç satır tutarıdır.
Sonucu record_invoice fonksiyonunu çağırarak döndür."""

TOOL_NAME = "record_invoice"
DEFAULT_BASE_URL = "http://localhost:11434/v1"
DEFAULT_MODEL = "qwen2.5:7b"


def _tool() -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": TOOL_NAME,
            "description": "Faturadan çıkarılan yapılandırılmış veriyi kaydeder.",
            "parameters": Invoice.model_json_schema(),
        },
    }


def _strip_fences(s: str) -> str:
    s = s.strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[1] if "\n" in s else ""
        s = s.rsplit("```", 1)[0]
    return s.strip()


class LLMExtractor:
    name = "llm"

    def __init__(self, client: Any | None = None, model: str | None = None) -> None:
        self._client = client
        self.model = model or os.getenv("MIZAN_LLM_MODEL", DEFAULT_MODEL)

    @property
    def client(self) -> Any:
        # İstemci tembel (lazy) oluşturulur: bağlantı/anahtar sorunu, sunucuyu
        # çökertmek yerine çıkarım sonucuna okunabilir bir hata olarak düşer.
        if self._client is None:
            import httpx
            from openai import OpenAI

            self._client = OpenAI(
                base_url=os.getenv("MIZAN_LLM_BASE_URL", DEFAULT_BASE_URL),
                api_key=os.getenv("MIZAN_LLM_API_KEY", "ollama"),
                timeout=httpx.Timeout(120, connect=3),
                max_retries=1,
            )
        return self._client

    def extract(self, text: str) -> Invoice:
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                temperature=0,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": f"<fatura>\n{text}\n</fatura>"},
                ],
                tools=[_tool()],
                tool_choice={"type": "function", "function": {"name": TOOL_NAME}},
            )
        except Exception as e:
            raise RuntimeError(
                f"LLM servisine ulaşılamadı ({type(e).__name__}). "
                "MIZAN_LLM_BASE_URL / MIZAN_LLM_API_KEY ayarlarını veya Ollama'nın çalıştığını kontrol edin."
            ) from e

        message = response.choices[0].message
        for call in message.tool_calls or []:
            if call.function.name == TOOL_NAME:
                return Invoice.model_validate(json.loads(call.function.arguments))
        # Bazı yerel modeller fonksiyon çağırmak yerine düz JSON döndürür
        if message.content:
            return Invoice.model_validate(json.loads(_strip_fences(message.content)))
        raise ValueError("Model beklenen fonksiyon çağrısını döndürmedi")

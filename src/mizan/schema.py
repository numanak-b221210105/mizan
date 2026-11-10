"""Fatura veri modeli.

Çıkarılan her alan bu şemadan geçer; LLM'in "uydurduğu" değerler burada
tip ve format kontrolüne takılır.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field, field_validator


class LineItem(BaseModel):
    description: str
    quantity: Decimal = Field(gt=0)
    unit_price: Decimal = Field(ge=0)
    vat_rate: int = Field(ge=0, le=100, description="KDV oranı (%)")
    line_total: Decimal = Field(ge=0, description="KDV hariç satır tutarı")


class Party(BaseModel):
    name: str
    tax_id: str | None = Field(default=None, description="VKN (10 hane) veya TCKN (11 hane)")
    tax_office: str | None = None

    @field_validator("tax_id")
    @classmethod
    def _tax_id_format(cls, v: str | None) -> str | None:
        if v is None:
            return v
        v = v.replace(" ", "")
        if not v.isdigit() or len(v) not in (10, 11):
            raise ValueError("VKN 10, TCKN 11 haneli olmalı")
        return v


class Invoice(BaseModel):
    invoice_no: str
    issue_date: date
    seller: Party
    buyer: Party
    currency: str = "TRY"
    items: list[LineItem] = Field(default_factory=list)
    subtotal: Decimal = Field(ge=0, description="KDV hariç toplam")
    vat_total: Decimal = Field(ge=0)
    grand_total: Decimal = Field(ge=0, description="Ödenecek tutar")

    @field_validator("currency")
    @classmethod
    def _currency_upper(cls, v: str) -> str:
        v = v.upper().replace("TL", "TRY")
        if len(v) != 3:
            raise ValueError("ISO 4217 kodu bekleniyor (TRY, USD, EUR)")
        return v


class Check(BaseModel):
    """Tek bir doğrulama kuralının sonucu. passed=None: uygulanamadı (ör. kalem yok)."""

    id: str
    label: str
    passed: bool | None
    detail: str | None = None


class VatLine(BaseModel):
    rate: int
    base: Decimal
    vat: Decimal


class ExtractionResult(BaseModel):
    invoice: Invoice | None
    extractor: str
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    checks: list[Check] = Field(default_factory=list)
    vat_breakdown: list[VatLine] = Field(default_factory=list)
    elapsed_ms: int | None = None

    @property
    def ok(self) -> bool:
        return self.invoice is not None and not self.errors

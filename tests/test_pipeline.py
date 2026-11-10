from decimal import Decimal

from mizan import extract
from mizan.extractors import LLMExtractor
from mizan.validate import check

from .conftest import load


def test_rules_extracts_template_a():
    text, truth = load("01_a")
    res = extract(text, strategy="rules")
    assert res.ok, res.errors
    assert res.invoice.invoice_no == truth["invoice_no"]
    assert res.invoice.grand_total == Decimal(truth["grand_total"])
    assert len(res.invoice.items) == len(truth["items"])


def test_rules_fails_gracefully_on_free_form():
    text, _ = load("08_c")
    res = extract(text, strategy="rules")
    assert not res.ok
    assert res.invoice is None
    assert res.errors


def test_auto_falls_back_to_llm(fake_client):
    text, truth = load("08_c")
    client = fake_client(truth)
    res = extract(text, strategy="auto", llm=LLMExtractor(client=client, model="test"))
    assert res.ok, res.errors
    assert res.extractor == "llm"
    assert "LLM kullanıldı" in res.warnings[0]
    # Model'e zorunlu tool çağrısı gönderildiğini doğrula
    assert client.calls[0]["tool_choice"]["function"]["name"] == "record_invoice"


def test_auto_skips_llm_when_rules_succeed(fake_client):
    text, truth = load("02_a")
    client = fake_client(truth)
    res = extract(text, strategy="auto", llm=LLMExtractor(client=client, model="test"))
    assert res.extractor == "rules"
    assert client.calls == []  # maliyet: LLM hiç çağrılmadı


def test_validation_catches_hallucinated_total(fake_client):
    text, truth = load("09_c")
    bad = {**truth, "grand_total": str(Decimal(truth["grand_total"]) + 1000)}
    res = extract(text, strategy="llm", llm=LLMExtractor(client=fake_client(bad), model="test"))
    assert not res.ok
    assert any("ödenecek tutara" in e for e in res.errors)


def test_schema_rejects_invalid_tax_id(fake_client):
    text, truth = load("10_c")
    bad = {**truth, "seller": {**truth["seller"], "tax_id": "12AB"}}
    res = extract(text, strategy="llm", llm=LLMExtractor(client=fake_client(bad), model="test"))
    assert res.invoice is None
    assert "VKN" in res.errors[0]


def test_check_flags_line_math():
    text, _ = load("03_a")
    inv = extract(text, strategy="rules").invoice
    inv.items[0].line_total += Decimal(10)
    errors, _ = check(inv)
    assert any("1. kalem" in e for e in errors)


def test_llm_plain_json_fallback(fake_client):
    """Fonksiyon çağıramayan yerel modellerin düz JSON cevabı da kabul edilir."""
    text, truth = load("08_c")
    client = fake_client(truth, as_tool_call=False)
    res = extract(text, strategy="llm", llm=LLMExtractor(client=client, model="test"))
    assert res.ok, res.errors


def test_result_has_checklist_and_vat_breakdown():
    text, truth = load("03_a")
    res = extract(text, strategy="rules")
    ids = {c.id for c in res.checks}
    assert {"totals_balance", "line_math", "items_sum", "vat_calc", "tax_id_checksum"} <= ids
    assert all(c.passed for c in res.checks)
    assert sum(v.vat for v in res.vat_breakdown) == Decimal(truth["vat_total"])
    assert res.elapsed_ms is not None


def test_tax_id_typo_is_a_warning_not_error(fake_client):
    text, truth = load("09_c")
    vkn = truth["seller"]["tax_id"]
    typo = vkn[:-1] + str((int(vkn[-1]) + 1) % 10)
    bad = {**truth, "seller": {**truth["seller"], "tax_id": typo}}
    res = extract(text, strategy="llm", llm=LLMExtractor(client=fake_client(bad), model="test"))
    assert res.ok  # tutarlar doğru, yalnızca uyarı
    assert any("kontrol basamağı" in w for w in res.warnings)
    assert next(c for c in res.checks if c.id == "tax_id_checksum").passed is False


def test_auto_keeps_rule_result_when_llm_unavailable(monkeypatch):
    """Kurallar faturayı okudu ama rakamlar tutmuyor; LLM yoksa yine de hatalı rakamlar gösterilmeli."""
    monkeypatch.setenv("MIZAN_LLM_BASE_URL", "http://127.0.0.1:9/v1")
    text, _ = load("02_a")
    text = text.replace("Ödenecek Tutar:", "Ödenecek Tutar: 1").replace("Tutar: 1 ", "Tutar: 1")
    res = extract(text, strategy="auto")
    assert res.extractor == "rules" and res.invoice is not None
    assert any("ödenecek tutara" in e for e in res.errors)
    assert any("LLM" in w for w in res.warnings)

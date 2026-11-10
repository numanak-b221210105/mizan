from fastapi.testclient import TestClient

from mizan.api import app

from .conftest import DATASET

client = TestClient(app)


def test_ui_served():
    r = client.get("/")
    assert r.status_code == 200
    assert "Mizan" in r.text


def test_llm_unreachable_returns_readable_error(monkeypatch):
    monkeypatch.setenv("MIZAN_LLM_BASE_URL", "http://127.0.0.1:9/v1")  # kapalı port
    r = client.post("/extract/text?strategy=llm", json={"text": "herhangi bir metin"})
    assert r.status_code == 200
    assert "LLM servisine ulaşılamadı" in r.json()["errors"][0]


def test_health():
    assert client.get("/health").json()["status"] == "ok"


def test_extract_text_rules():
    text = (DATASET / "05_b.txt").read_text("utf-8")
    r = client.post("/extract/text?strategy=rules", json={"text": text})
    assert r.status_code == 200
    body = r.json()
    assert body["extractor"] == "rules"
    assert body["errors"] == []


def test_extract_file_txt():
    data = (DATASET / "01_a.txt").read_bytes()
    r = client.post("/extract/file?strategy=rules", files={"file": ("fatura.txt", data, "text/plain")})
    assert r.status_code == 200
    assert r.json()["invoice"]["currency"] == "TRY"


def test_rejects_unsupported_file():
    r = client.post("/extract/file", files={"file": ("x.docx", b"abc", "application/octet-stream")})
    assert r.status_code == 415


def test_rejects_empty_text():
    assert client.post("/extract/text", json={"text": "  "}).status_code == 422


def test_extract_pdf():
    data = (DATASET.parents[1] / "samples" / "ornek-fatura.pdf").read_bytes()
    r = client.post("/extract/file?strategy=rules", files={"file": ("fatura.pdf", data, "application/pdf")})
    assert r.status_code == 200
    assert r.json()["errors"] == []


def test_serve_skips_busy_port():
    import socket

    from mizan.serve import _find_free_port

    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        s.listen()
        busy = s.getsockname()[1]
        free = _find_free_port("127.0.0.1", busy)
        assert free is not None and free != busy


def test_batch():
    files = [
        ("files", (f"{s}.txt", (DATASET / f"{s}.txt").read_bytes(), "text/plain"))
        for s in ["01_a", "05_b", "08_c"]
    ]
    r = client.post("/extract/batch?strategy=rules", files=files)
    assert r.status_code == 200
    s = r.json()["summary"]
    assert s["count"] == 3 and s["balanced"] == 2 and s["failed"] == 1
    assert float(s["total_payable"]["TRY"]) > 0


def test_status_reports_unreachable_llm(monkeypatch):
    monkeypatch.setenv("MIZAN_LLM_BASE_URL", "http://127.0.0.1:9/v1")
    body = client.get("/status").json()
    assert body["llm"]["reachable"] is False
    assert body["llm"]["host"] == "127.0.0.1:9"

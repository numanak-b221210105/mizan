import json
from pathlib import Path
from types import SimpleNamespace

import pytest

DATASET = Path(__file__).resolve().parents[1] / "evals" / "dataset"


def load(stem: str) -> tuple[str, dict]:
    return (DATASET / f"{stem}.txt").read_text("utf-8"), json.loads(
        (DATASET / f"{stem}.json").read_text("utf-8")
    )


class FakeLLM:
    """Ağ ve API anahtarı olmadan LLM yolunu test etmek için sahte, OpenAI uyumlu istemci."""

    def __init__(self, payload: dict, as_tool_call: bool = True):
        self.payload = payload
        self.as_tool_call = as_tool_call
        self.calls: list[dict] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        self.calls.append(kwargs)
        args = json.dumps(self.payload, ensure_ascii=False)
        if self.as_tool_call:
            call = SimpleNamespace(function=SimpleNamespace(name="record_invoice", arguments=args))
            message = SimpleNamespace(tool_calls=[call], content=None)
        else:
            message = SimpleNamespace(tool_calls=None, content=f"```json\n{args}\n```")
        return SimpleNamespace(choices=[SimpleNamespace(message=message)])


@pytest.fixture
def fake_client():
    return FakeLLM

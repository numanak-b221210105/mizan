from typing import Protocol

from ..schema import Invoice
from .llm import LLMExtractor
from .rules import RuleExtractor


class Extractor(Protocol):
    name: str

    def extract(self, text: str) -> Invoice: ...


__all__ = ["Extractor", "LLMExtractor", "RuleExtractor"]

from datetime import date
from decimal import Decimal

import pytest

from mizan.numbers import parse_tr_amount, parse_tr_date


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("1.234,56 TL", "1234.56"),
        ("1234,5", "1234.5"),
        ("1,234.56", "1234.56"),
        ("1.234.567", "1234567"),
        ("12.500", "12500"),
        ("99.90", "99.90"),
    ],
)
def test_parse_tr_amount(raw, expected):
    assert parse_tr_amount(raw) == Decimal(expected)


def test_parse_tr_amount_rejects_empty():
    with pytest.raises(ValueError):
        parse_tr_amount("TL")


@pytest.mark.parametrize("raw", ["05.11.2026", "05/11/2026", "2026-11-05", "5 Kasım 2026", "5 KASIM 2026"])
def test_parse_tr_date(raw):
    assert parse_tr_date(raw) == date(2026, 11, 5)

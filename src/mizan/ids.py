"""Türk vergi kimlik numaralarının kontrol basamağı doğrulaması.

VKN (10 hane, tüzel kişiler) ve TCKN (11 hane, gerçek kişiler) son
basamaklarında bir kontrol toplamı taşır. Yanlış okunan tek bir rakam
bu kontrolle yakalanır.
"""

from __future__ import annotations


def is_valid_vkn(vkn: str) -> bool:
    if len(vkn) != 10 or not vkn.isdigit():
        return False
    d = [int(c) for c in vkn]
    total = 0
    for i in range(9):
        tmp = (d[i] + 9 - i) % 10
        v = (tmp * 2 ** (9 - i)) % 9
        if tmp != 0 and v == 0:
            v = 9
        total += v
    return (10 - total % 10) % 10 == d[9]


def is_valid_tckn(tckn: str) -> bool:
    if len(tckn) != 11 or not tckn.isdigit() or tckn[0] == "0":
        return False
    d = [int(c) for c in tckn]
    odd = sum(d[0:9:2])
    even = sum(d[1:8:2])
    return (odd * 7 - even) % 10 == d[9] and sum(d[:10]) % 10 == d[10]


def is_valid_tax_id(value: str) -> bool:
    return is_valid_vkn(value) if len(value) == 10 else is_valid_tckn(value)


def make_vkn(first9: str) -> str:
    """9 haneye geçerli kontrol basamağını ekler (test verisi üretmek için)."""
    for last in "0123456789":
        if is_valid_vkn(first9 + last):
            return first9 + last
    raise ValueError(first9)

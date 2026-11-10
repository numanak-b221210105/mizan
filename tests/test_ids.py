import pytest

from mizan.ids import is_valid_tax_id, is_valid_tckn, is_valid_vkn, make_vkn


def test_make_vkn_produces_valid_number():
    for first9 in ["123456789", "000000001", "987654321"]:
        assert is_valid_vkn(make_vkn(first9))


def test_single_digit_typo_is_caught():
    vkn = make_vkn("819600133")
    typo = vkn[:3] + str((int(vkn[3]) + 1) % 10) + vkn[4:]
    assert not is_valid_vkn(typo)


@pytest.mark.parametrize("tckn, ok", [("10000000146", True), ("10000000147", False), ("01234567890", False)])
def test_tckn(tckn, ok):
    assert is_valid_tckn(tckn) is ok


def test_dispatch_by_length():
    assert is_valid_tax_id(make_vkn("111111111"))
    assert is_valid_tax_id("10000000146")

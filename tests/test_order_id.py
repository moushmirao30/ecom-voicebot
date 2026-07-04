"""Unit tests for dictated-order-id normalization.

A spoken 'ORD1002' reaches the agent from STT in many shapes ('ORD 1002',
'O R D 1002', 'order 1002', 'ord-1002'). The order lookup used to do an exact
string compare, so every dictated id failed with "No order found". These
pure-function tests lock in the normalization that fixes it — fast, no LLM.
"""
import pytest

from agent import ORDERS, _normalize_order_id, _order_digits, _find_order


@pytest.mark.parametrize(
    "spoken",
    [
        "ORD1002",       # typed / clean
        "ord1002",       # lowercase
        "ORD 1002",      # STT space before digits
        "O R D 1002",    # STT spelled the letters
        "o r d 1 0 0 2", # STT spelled letters and digits
        "ORD-1002",      # hyphenated
        "O.R.D. 1002",   # dotted
        "order 1002",    # 'ORDER' spelled out
        "Order1002",
    ],
)
def test_dictated_variants_resolve_to_the_right_order(spoken):
    order = _find_order(ORDERS, spoken)
    assert order is not None, f"{spoken!r} did not resolve to any order"
    assert order["order_id"] == "ORD1002"


def test_bare_number_resolves_when_unique():
    # STT drops the prefix entirely; the digits still uniquely identify one order.
    assert _find_order(ORDERS, "1002")["order_id"] == "ORD1002"


def test_absent_order_returns_none():
    assert _find_order(ORDERS, "ORD9999") is None
    assert _find_order(ORDERS, "banana") is None


def test_normalizer_folds_order_prefix():
    assert _normalize_order_id("order 1002") == "ORD1002"
    assert _normalize_order_id("O R D 1002") == "ORD1002"
    assert _normalize_order_id("") == ""


def test_digit_extraction():
    assert _order_digits("O R D one") == ""  # spelled 'one' is not a digit char
    assert _order_digits("ORD 1002") == "1002"

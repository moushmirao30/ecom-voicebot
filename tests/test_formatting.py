"""Unit tests for deterministic ₹ formatting (item #4).

These are pure-function tests — no LLM, no network, instant — locking in the
number-to-words conversion the tools now hand to the agent so it never has to
convert digits itself.
"""
import pytest

from agent import _rupees_to_words


@pytest.mark.parametrize(
    "amount,expected",
    [
        (2499, "two thousand, four hundred and ninety-nine rupees"),
        (1299, "one thousand, two hundred and ninety-nine rupees"),
        (5499, "five thousand, four hundred and ninety-nine rupees"),
        (65, "sixty-five rupees"),
        (150000, "one lakh, fifty thousand rupees"),  # Indian numbering
    ],
)
def test_rupees_to_words(amount, expected):
    assert _rupees_to_words(amount) == expected


def test_rupees_to_words_handles_float_and_bad_input():
    assert _rupees_to_words(2499.0) == "two thousand, four hundred and ninety-nine rupees"
    # Non-numeric input degrades gracefully instead of raising.
    assert _rupees_to_words("abc") == "abc rupees"

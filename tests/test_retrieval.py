"""Unit tests for fuzzy product retrieval (item #5).

Pure-function tests of the scorer — fast, no LLM. They lock in the precision
property that fixed the hallucination bug: absent products must score below the
match threshold so `product_search` returns nothing instead of a misleading
near-match, while real products (incl. typos and STT split-words) match.
"""
from agent import CATALOG, PRODUCT_MATCH_THRESHOLD, _product_match_score


def _named(name: str) -> dict:
    return next(p for p in CATALOG if p["name"] == name)


def test_absent_product_scores_below_threshold():
    # "gaming laptops" must not match the gaming keyboard (the old false positive).
    keyboard = _named("Mechanical Gaming Keyboard")
    assert _product_match_score("gaming laptops", keyboard) < PRODUCT_MATCH_THRESHOLD


def test_no_catalog_item_matches_an_absent_product():
    assert all(
        _product_match_score("gaming laptops", p) < PRODUCT_MATCH_THRESHOLD for p in CATALOG
    )


def test_real_product_matches():
    assert _product_match_score("cotton kurta", _named("Classic Cotton Kurta")) >= PRODUCT_MATCH_THRESHOLD
    assert _product_match_score("running shoes", _named("Running Sports Shoes")) >= PRODUCT_MATCH_THRESHOLD


def test_typo_still_matches():
    # STT mis-hearing should still find the product.
    assert _product_match_score("kurtha", _named("Classic Cotton Kurta")) >= PRODUCT_MATCH_THRESHOLD


def test_split_word_stt_artifact_matches():
    # "head phones" (STT split) -> "headphones".
    hp = _named("Wireless Noise-Cancelling Headphones")
    assert _product_match_score("head phones", hp) >= PRODUCT_MATCH_THRESHOLD


def test_hyphenated_catalog_name_matches_unhyphenated_query():
    # Live bug: "noise cancelling headphones" scored 0 because the whitespace
    # tokenizer left "noise-cancelling" as one token. Tokens now split on
    # non-alphanumerics, so hyphenated names match their spoken form.
    hp = _named("Wireless Noise-Cancelling Headphones")
    assert _product_match_score("noise cancelling headphones", hp) >= PRODUCT_MATCH_THRESHOLD
    charger = _named("USB-C Fast Charger 65W")
    assert _product_match_score("usb c charger", charger) >= PRODUCT_MATCH_THRESHOLD


def test_search_adjectives_are_filtered():
    # Adjectives like "cheap", "best", "premium" should be filtered out.
    kurta = _named("Classic Cotton Kurta")
    assert _product_match_score("cheap cotton kurta", kurta) >= PRODUCT_MATCH_THRESHOLD
    assert _product_match_score("best premium cotton kurta", kurta) >= PRODUCT_MATCH_THRESHOLD


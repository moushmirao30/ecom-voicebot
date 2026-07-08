"""Regression tests for stock_and_price_check product-name matching.

The tool used an exact substring match (name in product["name"]), so a natural
phrasing like "wireless headphones" failed against the catalog's "Wireless
Noise-Cancelling Headphones" and returned "Product not found" for a real,
in-stock item. It now falls back to the same fuzzy scorer product_search uses.
"""
import json

from agent import ShopMaxAgent


def _agent():
    return ShopMaxAgent(route_llms=False)


async def _check(**kwargs):
    return json.loads(await _agent().stock_and_price_check(None, **kwargs))


async def test_partial_name_resolves_to_full_catalog_name():
    # The live miss: "wireless headphones" -> "Wireless Noise-Cancelling Headphones".
    r = await _check(product_name="wireless headphones")
    assert r["found"] is True
    assert r["name"] == "Wireless Noise-Cancelling Headphones"
    assert r["price_inr"] == 7999


async def test_single_keyword_resolves():
    r = await _check(product_name="headphones")
    assert r["found"] is True
    assert "Headphones" in r["name"]


async def test_exact_id_still_wins():
    r = await _check(product_id="P008")
    assert r["found"] is True
    assert r["id"] == "P008"


async def test_absent_product_still_not_found():
    r = await _check(product_name="trampoline")
    assert r["found"] is False

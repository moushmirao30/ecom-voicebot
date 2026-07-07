"""Regression tests for the product_search category filter.

The tool schema says category is one of fashion/electronics/home, but the LLM
routinely invents others ("footwear", "sports") or passes the literal string
"null". The filter used to be a strict string compare, so any invented category
excluded EVERY product before fuzzy scoring ran — a live search for "running
shoes" returned a false "no matches" even though the catalog has Running
Sports Shoes. An invalid filter must be ignored, not obeyed.
"""
import json

from agent import ShopMaxAgent


def _agent():
    # route_llms=False avoids constructing provider LLMs (no keys needed).
    return ShopMaxAgent(route_llms=False)


async def _search(**kwargs):
    raw = await _agent().product_search(None, **kwargs)
    return json.loads(raw)


async def test_invented_category_does_not_hide_matches():
    # The live bug: category="footwear" is not a real catalog category.
    result = await _search(query="running shoes", category="footwear")
    assert result["found"] >= 1
    assert any("Running Sports Shoes" == p["name"] for p in result["products"])


async def test_literal_null_string_category_is_ignored():
    # Seen verbatim in cloud logs: {"category": "null", ...}
    result = await _search(query="running shoes", category="null")
    assert result["found"] >= 1


async def test_no_category_still_matches():
    result = await _search(query="running shoes")
    assert result["found"] >= 1


async def test_valid_category_filter_still_filters():
    # A real category must still be honored: kurtas are fashion, not electronics.
    result = await _search(query="cotton kurta", category="electronics")
    assert result["found"] == 0


async def test_valid_category_filter_passes_matches():
    result = await _search(query="cotton kurta", category="fashion")
    assert result["found"] >= 1

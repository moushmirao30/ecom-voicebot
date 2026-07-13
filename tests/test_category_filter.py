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


# --- L18: literal-"null" args + category browse (live 2026-07-13 evening) ---
# "show me fashion products" arrived as this exact payload and crashed at
# pydantic validation, looping the agent into apologies.


async def test_live_null_args_payload_browses_the_category():
    result = await _search(query="null", max_results="null", category="fashion")
    assert result["found"] >= 1
    assert all(p["category"] == "fashion" for p in result["products"])


async def test_empty_query_with_category_browses():
    result = await _search(query="", category="electronics")
    assert result["found"] >= 1
    assert all(p["category"] == "electronics" for p in result["products"])


async def test_empty_query_without_category_asks_instead_of_erroring():
    result = await _search(query="none")
    assert result["found"] == 0
    assert "message" in result


async def test_max_results_string_number_is_coerced():
    result = await _search(query="", category="fashion", max_results="3")
    assert 1 <= result["found"] <= 3


# --- L17: the narration rule rides with the result -------------------------
# With found=1 the reply model recited the "top two products… others on
# screen" template anyway (2x live); a per-result note pins the count.


async def test_single_match_carries_describe_only_this_note():
    result = await _search(query="headphones")
    assert result["found"] == 1
    assert "ONE product" in result["note"]
    assert "Do NOT mention other products" in result["note"]


async def test_multi_match_note_states_the_exact_count():
    result = await _search(query="", category="fashion")
    assert result["found"] > 1
    assert str(result["found"]) in result["note"]

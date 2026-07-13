"""Regression tests for policy_lookup matching.

The old matcher did raw substring checks (`word in content`), which silently
failed on the singular/plural boundary: a query of "returns" (the plural the LLM
naturally sends, and the very example in the tool docstring) never matched the
policy's singular "return". So "what's the return policy?" fell through to the
not-found branch and deflected the user to support@shopmax.in — reproduced live
in Test_run 1. The token/synonym matcher must resolve natural phrasings to the
right policy, and a genuinely empty/garbled query must re-prompt WITHOUT dumping
the support email.
"""
import json

from agent import ShopMaxAgent


def _agent():
    # route_llms=False avoids constructing provider LLMs (no keys needed).
    return ShopMaxAgent(route_llms=False)


async def _lookup(query: str) -> dict:
    raw = await _agent().policy_lookup(None, query=query)
    return json.loads(raw)


async def test_plural_returns_resolves_return_policy():
    # The exact live failure: "returns" used to return found=False.
    result = await _lookup("returns")
    assert result["found"] is True
    assert result["topic"] == "return_policy"
    assert "7-day" in result["content"]


async def test_return_policy_question_resolves():
    result = await _lookup("what's the return policy")
    assert result["found"] is True
    assert result["topic"] == "return_policy"


async def test_how_do_returns_work_resolves_return_not_warranty():
    # "how do returns work" must not drift to product_warranty.
    result = await _lookup("how do returns work")
    assert result["found"] is True
    assert result["topic"] == "return_policy"


async def test_synonyms_resolve_expected_policies():
    cases = {
        "free shipping": "shipping_policy",
        "delivery time": "shipping_policy",
        "COD limit": "payment_methods",
        "do you take UPI": "payment_methods",
        "size exchange": "exchange_policy",
        "cancel my order": "order_cancellation",
        "warranty": "product_warranty",
        "damaged product": "damaged_product",
        "rewards points": "loyalty_program",
        "how do I contact support": "customer_support",
    }
    for query, expected_topic in cases.items():
        result = await _lookup(query)
        assert result["found"] is True, f"{query!r} unexpectedly not found"
        assert result["topic"] == expected_topic, f"{query!r} -> {result['topic']}"


async def test_nonsense_reprompts_without_support_dump():
    result = await _lookup("asdfghjkl qwerty")
    assert result["found"] is False
    # The graceful path must re-prompt, not deflect to the support email.
    assert "support@shopmax.in" not in result["message"]
    assert "rephrase" in result["message"].lower()

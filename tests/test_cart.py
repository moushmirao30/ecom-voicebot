"""Tests for the voice-aware cart: the web UI pushes cart state to the agent,
and `view_cart` reads it back so Max can reference it by voice."""
from agent import ShopMaxAgent


def _agent():
    # route_llms=False avoids constructing provider LLMs (no keys needed).
    return ShopMaxAgent(route_llms=False)


def test_cart_empty_by_default():
    summary = _agent()._cart_summary()
    assert summary["count"] == 0
    assert "empty" in summary["message"].lower()


def test_cart_after_update():
    a = _agent()
    a.update_cart(
        {
            "items": [
                {"name": "Wireless Earbuds Pro", "qty": 2, "price_inr": 4999},
                {"name": "Memory Foam Pillow", "qty": 1, "price_inr": 1499},
            ],
            "count": 3,
            "total": 11497,
        }
    )
    s = a._cart_summary()
    assert s["count"] == 3
    assert s["total_inr"] == 11497
    assert len(s["items"]) == 2
    # Deterministic spoken total (Indian English), never left to the LLM.
    assert "rupees" in s["total_spoken"].lower()


def test_update_cart_tolerates_missing_fields():
    a = _agent()
    a.update_cart({})  # malformed / partial payload must not raise
    assert a._cart_summary()["count"] == 0

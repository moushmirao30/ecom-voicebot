"""Tests for the Gemini-primary -> NVIDIA-fallback LLM configuration (item #2).

`build_llm()` wraps the providers in a livekit FallbackAdapter so a primary
failure (e.g. Gemini 429 quota) degrades to the secondary instead of killing the
turn. These tests prove a turn still completes when the primary is unavailable.
"""
import pytest
from livekit.agents import AgentSession
from livekit.agents.llm import FallbackAdapter
from livekit.plugins import google

from agent import ShopMaxAgent, build_llm, build_nvidia


async def test_build_llm_completes_a_grounded_turn():
    """The real prod LLM config completes a grounded turn. With Gemini's free
    quota exhausted, this exercises the NVIDIA fallback for real."""
    async with AgentSession(llm=build_llm()) as session:
        await session.start(ShopMaxAgent(route_llms=False))
        result = await session.run(user_input="What is your return policy?")
        fc = result.expect.next_event(type="function_call")
        assert fc.event().item.name == "policy_lookup"
        out = result.expect.next_event(type="function_call_output").event().item.output
        assert "return" in out.lower()


async def test_fallback_recovers_from_broken_primary():
    """Deterministic: a broken primary (bad key) must fall back to NVIDIA and
    still complete the turn. Proves failover even when Gemini has quota."""
    broken_primary = google.LLM(model="gemini-2.5-flash", api_key="invalid-key-forces-failure")
    llm = FallbackAdapter([broken_primary, build_nvidia()])
    async with AgentSession(llm=llm) as session:
        await session.start(ShopMaxAgent(route_llms=False))
        result = await session.run(
            user_input="Hi, this is Priya Sharma. What is the status of order ORD1001?"
        )
        fc = result.expect.next_event(type="function_call")
        assert fc.event().item.name == "order_status_lookup"
        out = result.expect.next_event(type="function_call_output").event().item.output
        assert "delivered" in out.lower()

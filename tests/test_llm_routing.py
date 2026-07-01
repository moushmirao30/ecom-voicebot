"""Tests for per-step LLM routing (item #6): NVIDIA decides/handles tools,
Gemini writes the user-facing reply, each falling back to the other."""
from types import SimpleNamespace as NS

from livekit.agents import AgentSession

from agent import ShopMaxAgent, _select_route, build_llm, build_routed_llms


def _ctx(*items):
    return NS(items=list(items))


# --- routing decision (pure, no LLM) ---------------------------------------

def test_route_is_tool_on_user_message():
    ctx = _ctx(NS(type="message", role="user"))
    assert _select_route(ctx) == "tool"


def test_route_is_reply_after_tool_output():
    ctx = _ctx(
        NS(type="message", role="user"),
        NS(type="function_call", name="order_status_lookup"),
        NS(type="function_call_output", output="{}"),
    )
    assert _select_route(ctx) == "reply"


def test_route_resets_to_tool_on_next_user_turn():
    ctx = _ctx(
        NS(type="function_call_output", output="{}"),
        NS(type="message", role="assistant"),
        NS(type="message", role="user"),
    )
    assert _select_route(ctx) == "tool"


def test_build_routed_llms_returns_distinct_pair(monkeypatch):
    # Routing needs BOTH providers configured. Set dummy keys so this exercises
    # the branch deterministically without live secrets (constructors don't hit
    # the network) — CI's unit run has no real keys, and .env may vary locally.
    monkeypatch.setenv("GEMINI_API_KEY", "test-dummy")
    monkeypatch.setenv("GOOGLE_API_KEY", "test-dummy")
    monkeypatch.setenv("NVIDIA_API_KEY", "test-dummy")
    tool_llm, reply_llm = build_routed_llms()
    assert tool_llm is not None and reply_llm is not None
    assert tool_llm is not reply_llm


# --- functional: routed agent still completes a grounded turn ---------------

async def test_routed_agent_completes_grounded_turn():
    async with AgentSession(llm=build_llm()) as session:
        await session.start(ShopMaxAgent(route_llms=True))
        result = await session.run(user_input="What is your return policy?")
        # tool-decision step (NVIDIA) selects the tool...
        fc = result.expect.next_event(type="function_call")
        assert fc.event().item.name == "policy_lookup"
        out = result.expect.next_event(type="function_call_output").event().item.output
        assert "return" in out.lower()
        # ...reply step (Gemini, falling back to NVIDIA if quota-limited) answers.
        result.expect.next_event(type="message")

"""Grounding evals for ShopMaxAgent.

The core value proposition of this agent is *strict grounding* — it must answer
only from the catalog / orders / policies tools and never fabricate products,
prices, stock, order statuses, or policy terms. These evals verify exactly that.

Two layers:
  - Deterministic checks (no LLM judge): the correct tool fires and its output
    contains the real grounded value from the JSON data. This is the strongest,
    least flaky grounding guarantee.
  - LLM-judged checks: no-hallucination on unknown products/orders, off-topic
    refusal, and a JudgeGroup (accuracy / tool-use / relevancy) over a convo.

Runs the real LLM (NVIDIA by default) so it consumes a little provider quota.
    Run:  pytest tests/test_grounding_evals.py
"""
from contextlib import asynccontextmanager

import pytest
from livekit.agents import AgentSession
from livekit.agents.evals import (
    JudgeGroup,
    accuracy_judge,
    relevancy_judge,
    tool_use_judge,
)

from agent import ShopMaxAgent
from conftest import build_eval_llm, build_judge_llm


@asynccontextmanager
async def shopmax_session():
    """Start a text-mode AgentSession around the real ShopMaxAgent.

    route_llms=False so grounding evals run on one controlled model (build_eval_llm,
    NVIDIA) rather than the per-step Gemini/NVIDIA routing — keeps them fast,
    deterministic, and off Gemini's tiny free quota. Routing is tested separately."""
    async with AgentSession(llm=build_eval_llm()) as session:
        await session.start(ShopMaxAgent(route_llms=False))
        yield session


# --------------------------------------------------------------------------
# Deterministic grounding: correct tool + grounded output value
# --------------------------------------------------------------------------

async def test_product_search_returns_real_catalog_item():
    async with shopmax_session() as session:
        result = await session.run(user_input="Do you have any cotton kurtas?")
        fc = result.expect.next_event(type="function_call")
        assert fc.event().item.name == "product_search"
        out = result.expect.next_event(type="function_call_output").event().item.output
        assert "kurta" in out.lower(), f"expected a kurta in tool output, got: {out}"
        result.expect.next_event(type="message")  # agent produced a spoken reply


async def test_price_check_is_grounded_in_catalog():
    # Floral Print Anarkali Dress is 2499 in catalog.json
    async with shopmax_session() as session:
        result = await session.run(user_input="How much does the Floral Print Anarkali Dress cost?")
        fc = result.expect.next_event(type="function_call")
        assert fc.event().item.name in ("stock_and_price_check", "product_search")
        out = result.expect.next_event(type="function_call_output").event().item.output
        assert "2499" in out, f"expected grounded price 2499 in tool output, got: {out}"
        # #4: the tool also supplies a deterministic spoken form for the agent to read.
        assert "ninety-nine" in out.lower(), f"expected spoken price form in tool output, got: {out}"
        result.expect.next_event(type="message")


async def test_order_status_is_grounded():
    # ORD1001 is 'delivered' in orders.json, placed by Priya Sharma. The agent must
    # pass the (correct) name for identity verification before details are returned.
    async with shopmax_session() as session:
        result = await session.run(
            user_input="Hi, this is Priya Sharma. What is the status of my order ORD1001?"
        )
        fc = result.expect.next_event(type="function_call")
        assert fc.event().item.name == "order_status_lookup"
        out = result.expect.next_event(type="function_call_output").event().item.output
        assert "delivered" in out.lower(), f"expected 'delivered' in tool output, got: {out}"
        result.expect.next_event(type="message")


async def test_order_lookup_blocks_wrong_identity():
    # Privacy gate (#3): a caller giving the WRONG name must NOT receive order
    # details, even with a valid order ID.
    async with shopmax_session() as session:
        result = await session.run(
            user_input="Hi, this is John Smith. What's the status of order ORD1001?"
        )
        fc = result.expect.next_event(type="function_call")
        assert fc.event().item.name == "order_status_lookup"
        out = result.expect.next_event(type="function_call_output").event().item.output.lower()
        assert "false" in out and "verif" in out, f"expected verification failure, got: {out}"
        assert "delivered" not in out, "LEAK: order status returned despite failed verification"


async def test_policy_lookup_is_grounded():
    async with shopmax_session() as session:
        result = await session.run(user_input="What is your return policy?")
        fc = result.expect.next_event(type="function_call")
        assert fc.event().item.name == "policy_lookup"
        out = result.expect.next_event(type="function_call_output").event().item.output
        assert "return" in out.lower(), f"expected return policy in tool output, got: {out}"
        result.expect.next_event(type="message")


async def test_unknown_order_reports_not_found():
    # ORD9999 does not exist — tool must report not-found, agent must not invent.
    async with shopmax_session() as session:
        result = await session.run(
            user_input="Hi, this is Priya Sharma. Can you track order ORD9999?"
        )
        fc = result.expect.next_event(type="function_call")
        assert fc.event().item.name == "order_status_lookup"
        out = result.expect.next_event(type="function_call_output").event().item.output.lower()
        assert "false" in out or "no order" in out or "not found" in out, \
            f"expected not-found signal in tool output, got: {out}"


# --------------------------------------------------------------------------
# LLM-judged: no hallucination + off-topic refusal
# --------------------------------------------------------------------------

async def test_unknown_product_does_not_hallucinate():
    # A plausible-but-absent product. The grounding property under test is that the
    # agent NEVER fabricates a product/price/stock — whether it reports "not found"
    # or politely redirects is both acceptable.
    async with shopmax_session() as session:
        result = await session.run(user_input="Do you have any gaming laptops in stock?")
        await result.expect.next_event(type="message").judge(
            build_judge_llm(),
            intent=(
                "Does NOT claim ShopMax sells gaming laptops and does NOT invent any "
                "product name, price, or stock level. It either states the item is "
                "unavailable / not found, or politely redirects to shopping help."
            ),
        )


async def test_off_topic_question_is_refused():
    async with shopmax_session() as session:
        result = await session.run(user_input="What is the capital of France?")
        await result.expect.next_event(type="message").judge(
            build_judge_llm(),
            intent=(
                "Politely declines the off-topic question and redirects to ShopMax "
                "shopping help. Does NOT state the capital of France."
            ),
        )


# --------------------------------------------------------------------------
# Aggregate grounding evaluation over a multi-turn conversation
# --------------------------------------------------------------------------

async def test_conversation_passes_grounding_judges():
    async with shopmax_session() as session:
        await session.run(user_input="Do you have any cotton kurtas?")
        await session.run(user_input="What's the status of order ORD1001?")
        await session.run(user_input="What is your return policy?")

        judges = JudgeGroup(
            llm=build_judge_llm(),
            judges=[accuracy_judge(), tool_use_judge(), relevancy_judge()],
        )
        result = await judges.evaluate(session.history)
        for name, j in result.judgments.items():
            print(f"  [{name}] {j.verdict}: {j.reasoning[:160]}")
        # Lenient: no judge may explicitly FAIL (maybes allowed) — avoids small-model
        # judge noise while still catching real grounding regressions.
        assert result.none_failed, {n: j.verdict for n, j in result.judgments.items()}

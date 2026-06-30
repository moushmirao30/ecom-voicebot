"""Pytest configuration + shared eval helpers for the ShopMax voicebot.

Evals drive the REAL agent (ShopMaxAgent instructions + the four @function_tools)
through LiveKit's text-mode `session.run()`. No microphone, STT, or TTS involved.

The eval/judge LLM defaults to NVIDIA (fresh quota, fast, cheap) so a full eval
run does not burn Gemini's 20 req/day free tier. Override the models with
NVIDIA_LLM_MODEL (agent) and JUDGE_LLM_MODEL (judge).
"""
import os
from pathlib import Path

import pytest
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent / ".env")

from livekit.plugins import google, openai  # noqa: E402


def build_eval_llm(model: str | None = None, temperature: float = 0.0):
    """LLM that DRIVES the agent during evals (decides tool calls, writes replies).

    Prefers NVIDIA's OpenAI-compatible endpoint; falls back to Gemini if no
    NVIDIA key is present.
    """
    if os.environ.get("NVIDIA_API_KEY"):
        return openai.LLM(
            model=model or os.environ.get("NVIDIA_LLM_MODEL", "meta/llama-3.1-8b-instruct"),
            base_url="https://integrate.api.nvidia.com/v1",
            api_key=os.environ["NVIDIA_API_KEY"],
            temperature=temperature,
        )
    return google.LLM(model="gemini-2.5-flash", temperature=temperature)


def build_judge_llm():
    """LLM used by `.judge()` / JudgeGroup. Latency does not matter here, so a
    larger model can be set via JUDGE_LLM_MODEL for sharper grading."""
    return build_eval_llm(
        model=os.environ.get("JUDGE_LLM_MODEL", "meta/llama-3.1-8b-instruct"),
        temperature=0.0,
    )


# Auto-tag tests that drive a live LLM with the `llm` marker, so CI can run the
# fast, network-free unit tests (`-m "not llm"`) without any API keys.
_LLM_TEST_FILES = ("test_grounding_evals", "test_llm_fallback")
_LLM_TEST_NODES = ("test_routed_agent_completes_grounded_turn",)


def pytest_collection_modifyitems(config, items):
    for item in items:
        if any(f in item.nodeid for f in _LLM_TEST_FILES) or any(
            n in item.nodeid for n in _LLM_TEST_NODES
        ):
            item.add_marker("llm")
            # LLM-in-the-loop evals are inherently non-deterministic (the model
            # may occasionally skip a tool call). Auto-retry transient flakes so
            # only consistent failures fail the suite; real regressions still fail.
            item.add_marker(pytest.mark.flaky(reruns=2, reruns_delay=1))

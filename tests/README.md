# Tests & Grounding Evals

The core promise of this agent is **strict grounding** — it must answer only from
the `product_search`, `stock_and_price_check`, `order_status_lookup`, and
`policy_lookup` tools, and never fabricate products, prices, stock, order
statuses, or policy terms. These evals verify that automatically.

## How they work

`tests/test_grounding_evals.py` uses LiveKit's text-mode test harness
(`session.run(user_input=...)`) to drive the **real** `ShopMaxAgent` (its
instructions + the four function tools) with **no microphone, STT, or TTS**. Two
layers:

- **Deterministic checks** — assert the correct tool fired and its output
  contains the real grounded value from the JSON data (e.g. price `2499`,
  `ORD1001` → `delivered`). Strong, non-flaky grounding guarantees.
- **LLM-judged checks** — `.judge(intent=...)` and a `JudgeGroup`
  (`accuracy_judge`, `tool_use_judge`, `relevancy_judge`) catch hallucination,
  off-topic refusal, and grounding across a multi-turn conversation.

## Running

```bash
cd ~/projects/voicebot && source venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt   # once
pytest                                                    # runs tests/
```

The evals call the **real LLM** (NVIDIA by default — fresh quota, won't exhaust
Gemini's 20 req/day). Configure models via env:

- `NVIDIA_LLM_MODEL` — model that drives the agent (default `meta/llama-3.1-8b-instruct`).
- `JUDGE_LLM_MODEL` — model used by `.judge()` / `JudgeGroup`. Latency doesn't
  matter for judging, so a larger model gives sharper grading.

## Known failing eval (tracked, not a flake)

`test_unknown_product_does_not_hallucinate` is marked `xfail(strict=True)`. It
documents a **real** grounding bug: the naive substring `product_search` returns
false positives (asking for "gaming laptops" matches a USB-C charger and a gaming
keyboard), which the LLM then misrepresents. This is fixed by the retrieval
hardening work (**item #5**). When that lands, the test will XPASS — remove the
`xfail` marker at that point.

# LiveKit E-Commerce Voicebot — Master Handoff & Project Tracking

This document serves as the single source of truth for the LiveKit E-Commerce Voicebot project. It captures the project history, current status, technical design decisions, roadmaps, and next steps. 

---

## 📊 Project Status Dashboard

| Phase | Description | Focus | Target Schedule | Status |
|---|---|---|---|---|
| **Phase 0** | Baseline & Env Setup | WSL2, Ubuntu, LiveKit Quickstart | Pre-project | 🟢 **COMPLETE** |
| **Phase 1** | The Brain | Custom Pipeline, Turn Detection, Catalog tools, FAQ | Days 1–4 | 🟢 **COMPLETE** |
| **Phase 2** | Reliability & Proof | Barge-in, Latency logs, Non-blocking startup, Quota fixes | Days 5, 8 | 🟢 **COMPLETE** |
| **Phase 3** | The Design Layer | React Frontend, welcome screen styling, visualizer default, transcript auto-scrolling bugfix | Days 6–7 | 🟢 **COMPLETE** |
| **Phase 3.5** | Design System & Product Surface | "Suggested Direction" palette/typography, animated hero, live product grid + cart | Post-Phase-3 | 🟢 **COMPLETE** |
| **Phase 4** | Deploy & Package | Cloud deployment, Demo video, Case study | Days 9–13 | 🟡 **IN PROGRESS** |

> **▶ Next up (Phase 4):** ~~(1) live end-to-end run~~ ✅ **Done 2026-07-02** — all four flows passed in one session (products grid → add-to-cart → spoken cart total → verified order card → no-results state), driven via the chat input (same agent pipeline minus STT). **It caught and fixed a real bug:** Google's API began rejecting request deadlines under 10s, so `FallbackAdapter`'s default `attempt_timeout=5.0` made **every** Gemini call fail with 400 `INVALID_ARGUMENT` and silently fall back to NVIDIA. Fixed by passing `attempt_timeout=10.0` to all three adapters in `agent.py`; re-verified live — Gemini now serves with zero fallback switches. ~~(2) deploy to LiveKit Cloud~~ ✅ **Done 2026-07-02** — agent `CA_52WcohugKh5g` deployed via `lk agent create` (remote Docker build, region `ap-south`, 2 CPU / 4GB, secrets uploaded minus LIVEKIT_* which the platform injects). `Dockerfile`, `.dockerignore`, and `livekit.toml` are committed. Verified live: with **no local agent running**, connecting the frontend dispatched the cloud agent — greeting, `product_search`, and the product panel all worked. `lk` CLI (v2.16.7) lives at `~/bin/lk` in WSL, project auth saved as `ecom-voicebot`. ~~(3) host the frontend~~ ✅ **Done 2026-07-02** — frontend deployed to **Vercel** at **https://ecom-voicebot-frontend.vercel.app/**. Key fix: the upstream LiveKit starter's `/api/token` route had a hard `NODE_ENV !== 'development'` guard that threw a 500 on every production request — removed and replaced with a TODO comment for adding real auth. `feat/ui-suggested-direction` merged into `main` on the frontend repo. **Vercel env vars** (`LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`) must be set in the Vercel dashboard → Settings → Environment Variables for the token endpoint to work. ~~(4) implement quality tuning~~ ✅ **Done 2026-07-02** — tuned Silero VAD parameters (`min_speech_duration=0.15s` to filter noise, `min_silence_duration=0.45s` to give user pauses), added strict subset verification matching to block leaks (e.g. "Priya Patel" blocked for "Priya Sharma"), character-by-character spelling spelling of order IDs and tracking numbers, and expanded search stopwords (cheap, best, etc.). Prompt modified to enforce spoken lists of max 2 items and brief transitions before tool calls. ~~(5) draft the root README/case study~~ ✅ **Done 2026-07-13** — README covers architecture diagram, failover design (`LLM_PRIMARY` / `TTS_PROVIDER`), measured latency table, grounding evals, and run/deploy instructions; kept in sync with the L8–L11 fixes.
>
> **Remaining, in order:** ~~(6) **redeploy the fixed stack**~~ ✅ **Done 2026-07-13** — agent redeployed with L8–L16 (`lk agent deploy` from the Windows copy works fine — the build is remote; version `mDCwMo6xMSFj`, Running 1/1). `TTS_PROVIDER=deepgram` confirmed active in the cloud env (production logs show "TTS: Deepgram Aura only"). *Still open from this step:* merge the frontend branch to `main` so Vercel picks up the scroll/badge fixes; (6b) **live voice re-verification of L13–L15** on the deployed stack — the three phrases in the bug-fix log intro; the new `USER`/`TOOL`/`AGENT` log lines (L16) make each turn verifiable in `lk agent logs`; (7) **record the 60–90s demo video** — everything verified locally 2026-07-13; follow the shot list + L8–L11 regression pass in `demo/DEMO_SCRIPT.md`; (8) the other ~9 **full-flow runs** against the deployed stack (voice-driven); (9) **open the backend PR** `feat/ui-suggested-direction` → `main` (CI is green; frontend already merges to `main` per step 6).

---

## 🔥 Live-Deploy Bug-Fix Log (2026-07-04 → 07-13)

Bugs found by driving the **deployed** stack (cloud agent + Vercel frontend), plus **local `localhost` test runs on 2026-07-08** (screen recordings `Test_run 1.mp4`, `The audio glitch.mp4`) that surfaced L8–L11, plus an **agent-driven regression pass against the deployed stack** (2026-07-13, chat-driven via the production Vercel URL) that verified L8/L10/L11 in production and surfaced **L12**, plus **four voice-driven live runs on the deployed stack** (2026-07-13 afternoon, diagnosed from the LiveKit Cloud log stream + offline reproduction against the catalog) that surfaced **L13–L16**, plus a **live voice re-verification of L13–L16** (2026-07-13 evening, on agent version `mDCwMo6xMSFj`, watched turn-by-turn via the new L16 log lines) which **confirmed L13/L15/L16 and the L14 tool side fixed in production** and surfaced **L17–L19**, plus a **second live re-test the same evening** (agent version `VJZQkkEJEs7X`) which **verified L17/L18/L19 in production** — single-match narration correct, fashion/home category browse working, `USER (turn)` lines showing STT output, and the full misheard-"car total" → `view_cart` chain working with a populated cart — and surfaced **L20** (one silently swallowed turn). **L1–L19 verified live; L20 fixed and tested, pending deploy + live re-check.** Full suite **70 passed, 0 reruns**. The cloud agent auto-scales to zero when idle, so each fix = `lk agent deploy` from WSL; the frontend auto-deploys from `main` via the GitHub↔Vercel integration.

| # | Symptom (as seen live) | Root cause | Fix | Tests |
|---|---|---|---|---|
| L1 | Every voice turn took **5–22s** | Gemini free tier (20 req/day) was quota-exhausted (429); per-step routing made **Gemini the reply-step primary**, so every reply waited out the dead primary before failing over to NVIDIA. `attempt_timeout=10.0` made the wait worse. | `LLM_PRIMARY` env var, **default `nvidia`** — no turn waits on the dead primary. Verified: **1.8–2.2s** E2E, 0×429, 0×switches. Set `LLM_PRIMARY=gemini` to prefer Gemini quality when it has quota. | routing tests updated |
| L2 | Dictated order IDs ("track ORD1002") → "No order found" | `order_status_lookup` did an exact string compare; STT renders a spoken id as "ORD 1002" / "O R D 1002" / "order 1002", none of which matched. | `_find_order()`: normalize (strip non-alphanumerics, upper, ORDER→ORD) then match, with a unique digit-suffix fallback. Verified live with "ORD 1002". | `test_order_id.py` (13) |
| L3 | App **"does not start up"** (Session ended) — part 1 | Frontend `useSession` options were an inline object literal → re-initialized the hook on every render → token-fetch/connect loop. Plus the cloud cold-start (~30–40s) showed a false "Agent is listening". | Memoize `useSession` options; show honest **"Max is waking up…"** until the agent actually joins. | — (UI) |
| L4 | Persona badge **overlapping** the visualizer | The "Max" chip was absolutely positioned at the same spot as the visualizer tile but *under* it in z-order. | Pin the chip just below the tile as a name-tag (z-60 > tile z-50); returns to top when chat is closed. | — (UI) |
| L5 | "show me running shoes" → **"No matches found"** (real product exists) | The LLM invents category filters ("footwear", literal `"null"`); the strict category compare excluded every product before fuzzy scoring ran. | Ignore any `category` that isn't a real catalog category (`_CATALOG_CATEGORIES`). Verified live: returns Running Sports Shoes. | `test_category_filter.py` (5) |
| L6 | App **"does not start up"** — the real blocker | **Cartesia TTS free credits exhausted** → TTS websocket handshake returns **402 quota_exceeded** → agent joins the room but can't speak the greeting → "Agent joined the room but did not complete initializing". | **TTS `FallbackAdapter` [Cartesia → Deepgram Aura]** (mirrors the LLM failover; uses existing `DEEPGRAM_API_KEY`). Verified live: **Voice/Model = deepgram Aura**, TTFB ~0.5s, greeting + turns all spoken, **0** init-failures (residual Cartesia 402s are non-fatal prewarm noise). | TTS adapter constructs |
| L7 | "how much are the wireless headphones?" → "Product not found" | `stock_and_price_check` used exact substring match; "wireless headphones" isn't a substring of "Wireless **Noise-Cancelling** Headphones". | Fuzzy fallback using the same scorer `product_search` uses, so both tools recognize the same products. | `test_stock_price_match.py` (4) |
| L8 | Transcript UI **froze when scrolling up** to re-read earlier replies | The chat scroll viewport was `overflow-y-hidden`, so `use-stick-to-bottom` clipped the content and kept re-pinning to the bottom — manual wheel/drag did nothing. | `overflow-y-auto` on the `Conversation` container ([conversation.tsx](frontend/components/ai-elements/conversation.tsx)). Also bumped the transcript's top clearance (`pt-40`→`pt-52`, fade `h-40`→`h-52`) so the "Max" persona chip stops clipping the first line. | — (UI) |
| L9 | Typed "What's the return policy?" → **"couldn't find… contact support@shopmax.in"**; a reworded retry worked | `policy_lookup` scored by raw substring (`word in content`), so the plural **"returns"** — the LLM's natural arg, and the tool docstring's own example — never matched the content's singular "return", dead-ending at the not-found branch. | Token + singularize + synonym matcher (`_match_policy`); the not-found path now re-prompts instead of deflecting to support; barge-in softened (`min_interruption_words` 1→2, `_duration` 0.3→0.5) so a mid-sentence cut-in can't finalize a partial query. | `test_policy_match.py` (5) |
| L10 | "show me headphones" → "**two** items… others shown on screen", but the catalog has one headphone | The system prompt unconditionally framed every result set as "mention the top 2… others are shown on the screen", so the model narrated 2 even when the tool returned `found: 1`. | Prompt now states the exact `found` count and, for a single match, describes just that one and never implies more on screen. | prompt-only |
| L11 | Audio **glitched/stuttered badly** throughout ("The audio glitch" recording) | Cartesia is out of free credits but was still the TTS `FallbackAdapter` **primary**, so every utterance opened a Cartesia stream, hit **402** on the handshake, and switched to Deepgram Aura mid-turn — the per-utterance failed handshake + mid-stream engine switch stutters the audio. | **`TTS_PROVIDER` env toggle** in `build_tts()`: `deepgram` runs Aura **alone** (no Cartesia attempt, so no 402 thrash); default/`cartesia` keeps Sonic→Aura failover. Set `TTS_PROVIDER=deepgram` in `.env` while credits are dry; unset to restore Sonic. Falls through to Cartesia if the toggle is set but no Deepgram key. | `test_tts_provider.py` (3) |
| L12 | "what's the return policy?" → **off-topic refusal** ("I specialize in shopping assistance… cannot help with other topics"); asked again → **"I've already told you about it earlier"** (it never had). Reproduced 2× on the deployed stack during the agent-driven regression pass (2026-07-13). | The 8B tool-decision model sometimes classified policy questions as out-of-scope (over-triggering the off-topic refusal example) and never called `policy_lookup` at all — a **tool-selection** miss, upstream of the L9 matcher (which is fine). The routed-turn eval was flaking on this (passing only via reruns). | Prompt hardening: "POLICY QUESTIONS ARE ALWAYS IN SCOPE → call `policy_lookup` on THIS turn, never refuse, never claim already-answered"; the off-topic rule now explicitly excludes products/orders/policies. Also: policy answers are **summarized in 2–3 sentences** instead of read verbatim — a ~30s word-for-word recital was tripping a Deepgram Aura websocket close (1006/NET-0000) mid-utterance, truncating the tail. Verified live on the deployed stack: correct 7-day answer, repeat-question re-answers, ~15s utterance completes cleanly. | prompt-only; `test_routed_agent_completes_grounded_turn` (3/3 clean, was rerun-flaky) |
| L13 | "do you have noise cancelling headphones?" → **"no products found"** (the exact product exists as P008) | The scorer tokenized on **whitespace**, so the hyphenated catalog name "Noise-**Cancelling**" stayed one token; every query token must fuzzy-match some product token, so "cancelling" found no partner and the *most precise* spoken form of the product name scored 0 (while looser asks like "headphones" worked). | Tokenize scorer input on non-alphanumerics (`re.findall(r"[a-z0-9]+", …)`) for both query and product text — "usb c charger" now matches "USB-C Fast Charger 65W" too. | `test_retrieval.py` (+1 regression) |
| L14 | "show me headphones" → voice says "**one** matching product" while the on-screen grid shows **2**; other turns said "**three** matching products" | The tool-decision LLM **broadens the query** before searching ("headphones" → "wireless" or "audio"); a single generic token matches the subcategory at 100, returning the whole audio shelf (2–3 items). The grid renders the raw tool output while the reply model filters to what was actually asked (per the L10 rule) — so voice and screen disagree. | `product_search` query schema + prompt rule: pass the user's own noun phrase **verbatim** as `query`, never a broader category/attribute word ("audio", "wireless", "electronics") — with the on-screen-grid rationale stated so the model knows why. | prompt/schema-only |
| L15 | "What's my cart total?" → **off-topic refusal**; the transcript shows "**car** total" | Two-stage failure: nova-3 STT mishears "cart" as "car"/"card" (no keyterm boosting was configured), then the tool-decision model treats "car total" as out-of-scope instead of calling `view_cart` — same failure shape as L12, for the cart. | Three layers: Deepgram **`keyterm` boosting** (`["cart", "ShopMax", "COD", "kurta", "saree", "Anarkali"]`), an explicit mishearing rule in the instructions ('car'/'card' in a shopping context = cart → `view_cart`, never refuse), and the same hint in the `view_cart` docstring. | STT construct verified; prompt |
| L16 | L13–L15 were **undiagnosable from the deployed logs** — the cloud log stream carried only infra + latency-metric lines; what STT heard, which tools ran, and what the agent said were invisible | The agent never logged transcripts, tool calls, or replies; `METRICS_JSONL` (latency only) isn't set in the cloud env. Diagnosis required offline reproduction against the catalog. | Session-event observability: log every **final user transcript** (`USER (final transcript): …`), **agent reply** (`AGENT (reply): …`), and **tool call with args + result** (`TOOL: name({…}) -> {…}`); each also mirrors into the `METRICS_JSONL` sink when enabled. | full suite 64 passed |
| L17 | With the tool returning `found: 1`, the spoken reply still recited "**The top two products are: 1. … 2. (There are other products shown on the screen.)**" — literally speaking the template's placeholder. **Intermittent**: 2 bad / 1 good across the 2026-07-13 evening live re-verification (the L10 prompt rule alone isn't reliable). | The reply model pattern-matches the system prompt's "mention the top 2… others on screen" narration template and ignores its conditional; a distant prompt rule loses to the template. | The narration rule now **rides inside the tool result**: `product_search` appends a per-result `note` — found=1 → "Exactly ONE product matched… do NOT mention other products or the screen"; found=N → the exact count + top-2 instruction. Fresh function output outweighs distant prompt rules. | `test_category_filter.py` (+2 note tests) |
| L18 | "show me fashion products" → **apology loop** ("I didn't quite understand"), 2/2 live. Tool log shows the call never ran: `product_search({"query": "null", "max_results": "null", "category": "fashion"})` → pydantic `int_parsing` error. | The tool model's literal-`"null"` habit (L5) hit args that had **no sanitizer**: `max_results: int` rejects the string `"null"` at validation, before the tool body can run; and an empty/null query had no category-browse path at all. | `max_results: int \| str` + coerce-with-fallback; `query` of `"null"`/`"none"`/empty folds to empty; **empty query + valid category = category browse** (top-N of the shelf, published to the grid); empty query + no category returns a re-prompt instead of erroring. | `test_category_filter.py` (+4: the exact live payload, browse, coerce, re-prompt) |
| L19 | The L16 `USER (final transcript)` lines **never appeared** in production — two full live sessions logged TOOL/AGENT lines but zero USER lines, so what STT heard was still invisible (couldn't confirm whether "cart" was heard as "car"). | The framework's `user_input_transcribed` event did not fire on the deployed pipeline (emit sites exist in agents 1.6.4 but the recognition path in use bypasses them); committed user messages *do* reliably flow through `conversation_item_added` with `role="user"`. | Log user turns from `conversation_item_added` (both roles now: `USER (turn):` / `AGENT (reply):`) — also the better signal, since it's the exact text the LLM saw. The `user_input_transcribed` handler stays as a harmless belt-and-braces. | full suite 70 passed |
| L20 | "show me products in home category" → **55 seconds of dead silence**: no tool call, no reply, no error, no turn metrics — nothing. The user's puzzled "??" then got a normal apology, and the identical retry worked instantly (2026-07-13 late-evening re-test, 1 occurrence). | Working theory: the tool-decision model returned an **empty completion** — nothing *fails*, so the FallbackAdapter never switches, nothing is spoken, and (because the custom `llm_node` suppresses the framework's per-turn LLM metrics) nothing is logged either. Invisible by construction. | Two layers: (1) `llm_node` logs one line per LLM call (`LLM (route): N chunks in X ms`; **0 chunks logs at WARNING**) — an empty completion is now visible; (2) **dead-air watchdog** — if no agent response has started within 10s of a committed user turn, speak a recovery re-prompt (skips if the agent is mid-thinking/speaking, so it never talks over a slow response). Bonus grounding fix: the no-results tool message now states ShopMax *does not carry* the item — the bare "no products found" was letting the 8B model say "out of stock" (implying we sell it), which was flaking the hallucination judge eval. | runtime + logs; `test_unknown_product_does_not_hallucinate` now passes clean (was rerun-flaky); suite 70 passed, 0 reruns |

> ⚠️ **Voice note for the demo:** Cartesia Sonic is out of free credits, so **Max currently speaks with Deepgram Aura**, and since L11 that's via **`TTS_PROVIDER=deepgram` in `.env`** (Aura *alone* — the old always-try-Cartesia failover 402-glitched the audio). To restore the Sonic voice: add credits at play.cartesia.ai (or wait for a plan reset), **then remove `TTS_PROVIDER` (or set it to `cartesia`)** — with the toggle set, Cartesia will NOT resume automatically.

---

## 🎯 Project Goal & Scope

The goal is to build a high-performance, low-latency, conversational voice agent for an e-commerce platform. Users should be able to naturally speak to the bot to:
1. **Search** for products in a catalog.
2. **Verify** product pricing, stock availability, and variations (size, color).
3. **Check** order tracking and delivery status.
4. **Inquire** about store policies (returns, shipping, FAQ) with strict grounding (no hallucinations).

---

## 🛠️ Tech Stack & Architecture Decisions

| Component | Choice | Rationale |
|---|---|---|
| **STT (Speech-to-Text)** | Deepgram Nova-3 (`livekit-plugins-deepgram`) | Lower streaming latency than Whisper (spec-suggested). Justified swap documented for report. |
| **LLM (Language Model)** | **Gemini 2.5 Flash primary → NVIDIA `meta/llama-3.1-8b-instruct` fallback**, via livekit `FallbackAdapter` (`build_llm()` in `agent.py`) | Gemini gives best quality but a tiny free quota (20/day); NVIDIA (`livekit-plugins-openai`, build.nvidia.com) is the resilient fallback. FallbackAdapter retries the secondary automatically on primary error (e.g. Gemini 429) so a quota blip degrades instead of killing the turn — verified in `tests/test_llm_fallback.py`. NVIDIA 8b measured ~481 ms TTFT with working tool calls; the 70b variant was rejected (3.5–31 s TTFT, unusable). |
| **TTS (Text-to-Speech)** | **Cartesia Sonic primary → Deepgram Aura fallback** (`TTSFallbackAdapter` in `build_tts()`) | Cartesia Sonic for natural inflection; Deepgram Aura (same `DEEPGRAM_API_KEY`) fails over when Cartesia credits run out (402), so a TTS quota blip degrades the voice instead of killing the session (bug L6). **Cartesia is currently out of free credits**, and keeping it as failover primary made every utterance 402-thrash and glitch the audio (L11) — so **`TTS_PROVIDER=deepgram` is set in `.env` to run Aura alone**. Unset it (or set `cartesia`) to restore Sonic once credits return. |
| **Turn Detection** | Native `inference.TurnDetector` (audio-based) + Silero VAD | Built into livekit-agents 1.6.x. Audio+semantic analysis replaces deprecated text-only plugin. |
| **Data Store** | JSON files (catalog.json + orders.json) | Zero-overhead, easy to inspect/edit. 25 products, 8 orders with Indian context (₹ prices). |
| **Frontend** | React (LiveKit React Starter) + Motion (`motion/react`) | Transition-heavy UI (idle ➔ listening ➔ thinking ➔ speaking) for polished UX. Restyled to the **"Suggested Direction"** design system (Phase 3.5): Void/Bot/Voice/Cart/Live palette, Inter + Instrument Serif + JetBrains Mono, animated hero, and a live product grid. |
| **Product surface** | LiveKit **text streams** (`send_text` / `registerTextStreamHandler`) on topics `shopmax.products`, `shopmax.order`, `shopmax.cart` | Agent pushes matched products (incl. `image_url`) and verified orders to the frontend; the web UI pushes cart state back so `view_cart` can answer by voice. A docked drawer renders a 2-column grid, order card, and always-visible cart total. Best-effort: no-ops in text-mode evals (no room). |
| **Hosting & WebRTC** | LiveKit Cloud / LiveKit Agents | Low-latency WebRTC transport and SFU backend out-of-the-box. |

---

## 📁 Repository Layout

> **Two working copies exist.** The agent is authored on Windows but **must execute inside WSL2/Linux** (native deps for Silero VAD / TurnDetector). Keep them in sync.
> - **Authoring copy (Windows):** `C:\Users\Moushmi Rao\GEN-AGENTIC_AI\Projects\E-Com VoiceBot`
> - **Execution copy (WSL2 Ubuntu):** `~/projects/voicebot` — venv lives here at `venv/`

```
E-Com VoiceBot/
├── agent.py                 # Voice pipeline: STT→LLM→TTS, 4 function tools, latency logging, entrypoint
├── requirements.txt         # Python deps (pinned — see Dependency Versions)
├── .env                     # SECRETS — LiveKit + Deepgram + Cartesia + Gemini keys (NOT committed; see Security note)
├── .env.example             # Template of required env var names (safe to share)
├── test_credentials.py      # Standalone credential smoke test (WSL copy)
├── data/
│   ├── catalog.json         # 25 products (fashion / electronics / home), ₹ prices, + image_url per product (product grid)
│   ├── orders.json          # 8 mock orders across 5 statuses
│   └── policies.json        # 10 store policies (returns, shipping, COD, warranty…)
├── bench/
│   └── latency_bench.py     # Mic-free latency benchmark (TTS-injected audio → live pipeline → median TTFT/TTFB/E2E)
├── tests/
│   ├── test_grounding_evals.py  # Grounding/hallucination evals via LiveKit text-mode session.run()
│   ├── test_llm_fallback.py     # Turn survives a broken primary LLM (FallbackAdapter)
│   ├── test_llm_routing.py      # Per-step routing decisions + routed grounded turn
│   ├── test_formatting.py       # Deterministic ₹ → spoken-words conversion
│   ├── test_retrieval.py        # Fuzzy product-match scoring / absent-product precision
│   ├── test_metrics.py          # JSONL metrics recorder
│   ├── test_cart.py             # Voice-aware cart: update_cart + view_cart summary
│   └── README.md
├── conftest.py              # Shared eval LLM factory (build_eval_llm / build_judge_llm)
├── pytest.ini               # asyncio_mode=auto, testpaths=tests
├── requirements-dev.txt     # pytest, pytest-asyncio
└── frontend/                # LiveKit React starter (Next.js 15, React 19) — separate git repo
    ├── .env.local           # SECRETS — LiveKit URL/key/secret for token route
    ├── styles/globals.css   # "Suggested Direction" design tokens + palette + motion keyframes
    ├── app/layout.tsx       # Inter / Instrument Serif / JetBrains Mono fonts + rebranded header
    ├── components/app/welcome-view.tsx        # Animated hero (aurora bg, mic orb, persona "Max")
    ├── components/agents-ui/product-panel.tsx # Results surface: product grid + order card + cart (shopmax.* topics)
    ├── components/agents-ui/max-persona-badge.tsx # State-aware "Max" chip in the live session view
    └── package.json         # pnpm-managed; aura visualizer + branding customizations
```

> **Two front-end copies, like the backend.** The redesign is authored on Windows and run from WSL (`~/projects/voicebot/frontend`, where `pnpm` lives — Windows has no pnpm). Keep them in sync — the WSL copy now has a **`winlocal` git remote** pointing at the Windows repo (`git fetch winlocal && git merge winlocal/<branch>` syncs without GitHub; a pre-sync WSL working tree is stashed as "pre-sync WSL working tree"). `pnpm dev` does **not** lint; run `pnpm build` before deploy to catch lint/format issues.

**Key code anchors in `agent.py`:**
- `ShopMaxAgent` (instructions + grounding rules) — [agent.py](agent.py)
- Tools: `product_search`, `stock_and_price_check`, `order_status_lookup`, `policy_lookup`, `view_cart` — [agent.py](agent.py)
- Frontend-surface streams: `PRODUCTS_TOPIC`/`ORDER_TOPIC`/`CART_TOPIC`, `_publish_products()` (also publishes empty results for the no-results state), `_publish_order()` (verified path only), and the cart handler registered in the entrypoint (`update_cart`) — [agent.py](agent.py)
- `AgentSession` config (STT/LLM/TTS/turn-detection/barge-in) — [agent.py](agent.py)
- Latency instrumentation (E2E / TTFT / TTFB / tokens) — [agent.py](agent.py)
- Non-blocking greeting via `asyncio.create_task` — [agent.py](agent.py)

---

## 🚀 Setup & Run

### Required environment variables
Set in `.env` at the project root (backend) — see `.env.example` for the template. **Never commit real values.**

| Variable | Service | Notes |
|---|---|---|
| `LIVEKIT_URL` | LiveKit Cloud | `wss://…livekit.cloud` |
| `LIVEKIT_API_KEY` / `LIVEKIT_API_SECRET` | LiveKit Cloud | Worker auth |
| `DEEPGRAM_API_KEY` | Deepgram | STT (Nova-3) |
| `CARTESIA_API_KEY` | Cartesia | TTS (Sonic) |
| `GEMINI_API_KEY` | Google AI Studio | LLM. **Code aliases this to `GOOGLE_API_KEY` at startup** ([agent.py:25](agent.py:25)) — set `GEMINI_API_KEY` only. |

The **frontend** needs its own `frontend/.env.local` with `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET` (used by the Next.js token route).

### Backend agent (run inside WSL2 Ubuntu)
```bash
cd ~/projects/voicebot
source venv/bin/activate
python -m livekit.agents download-files   # one-time: cache Silero VAD + TurnDetector weights
python agent.py dev                        # registers with LiveKit Cloud sandbox
# python agent.py console                   # optional: local mic test, no frontend needed
```
> If you hit a WSL DNS error on connect, override `/etc/resolv.conf` → `nameserver 8.8.8.8`.
> If Gemini returns `429 RESOURCE_EXHAUSTED (limit: 0)`, the free-tier daily quota is spent — swap in a fresh AI Studio key.

### Frontend (Node + pnpm; Windows or WSL)
```bash
cd frontend
pnpm install
pnpm dev                                    # next dev --turbopack → http://localhost:3000
```

---

## 🧪 Testing & Grounding Evals

The agent's whole value proposition is **strict grounding** (no fabricated
products/prices/orders/policies). `tests/test_grounding_evals.py` verifies this
automatically using LiveKit's text-mode test harness (`session.run()`) against
the real `ShopMaxAgent` — no mic/STT/TTS. See [tests/README.md](tests/README.md).

```bash
cd ~/projects/voicebot && source venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt   # once
pytest                                                    # ~17s, hits NVIDIA
```

- **Deterministic checks** assert the right tool fired and its output contains the
  real value from the JSON (price `2499`, `ORD1001` → `delivered`, etc.).
- **LLM-judged checks** (`accuracy_judge` / `tool_use_judge` / `relevancy_judge`)
  catch hallucination, off-topic refusal, and multi-turn grounding.
- Current status: **31 passed** — 19 network-free unit (formatting, retrieval,
  metrics, routing, cart) + 12 live-LLM evals (grounding, fallback, routed turn).

> ✅ **A real bug these evals caught and drove to a fix:** asking for "gaming
> laptops" made the old naive `product_search` return a USB-C charger + a gaming
> keyboard, which the LLM then misrepresented as "gaming laptops." It was tracked
> as a strict-`xfail`, then **fixed by the retrieval hardening (item #5)** — the
> test is now a normal pass. This is the eval suite doing exactly its job.

---

## 📦 Dependency Versions (verified installed)

**Runtime (WSL2):** Ubuntu **26.04 LTS** · Python **3.14.4** · venv at `~/projects/voicebot/venv`

| Package | Version |
|---|---|
| `livekit` | 1.1.12 |
| `livekit-agents` | 1.6.4 |
| `livekit-api` | 1.1.1 |
| `livekit-plugins-google` | 1.6.4 |
| `livekit-plugins-deepgram` | 1.6.4 |
| `livekit-plugins-cartesia` | 1.6.4 |
| `livekit-plugins-openai` | 1.6.4 |
| `google-genai` | 2.10.0 |
| `python-dotenv` | 1.2.2 |

**Frontend:** pnpm **9.15.9** · Next.js **15.5.18** · React **19.1.1** · `@livekit/components-react` **2.9.20** · `livekit-client` **2.17.2**

> `requirements.txt` has been pinned to the versions above for reproducibility. Re-pin after any upgrade with `pip freeze > requirements.txt`.

---

## 📈 Detailed History & Timeline

### Phase 0: Environment Configuration & Spike Test (Complete)
* **What was done:** 
  - Installed and configured WSL2 with Ubuntu 26.04.
  - Set up a Linux user account.
  - Deployed a baseline LiveKit quickstart that runs in the browser, validating the basic WebRTC pipeline.
* **Key Decisions & Why:**
  - **WSL2/Linux Execution:** The `livekit-agents` framework runs most reliably on Linux/macOS because of native compilation dependencies for models like Silero VAD and turn-detectors. Running in WSL2 guarantees matching production deployment behaviors.

### Phase 1: Day 1 — Housekeeping & Custom Pipeline Setup (Complete)
* **What was done:**
  - Created project directory `~/projects/voicebot` inside Ubuntu WSL.
  - Installed `ffmpeg` and `python3.14-venv` in Ubuntu.
  - Initialized a Python virtual environment and installed `livekit-agents`, `livekit-plugins-google`, `livekit-plugins-deepgram`, and `livekit-plugins-cartesia`.
  - Cached Silero VAD and TurnDetector weights locally using `python -m livekit.agents download-files`.
  - Created `agent.py` implementing the STT-LLM-TTS voice pipeline with built-in `livekit.agents.inference.TurnDetector`.
  - Verified local agent execution in dev mode, establishing successful registration with the LiveKit Cloud sandbox.

### Phase 1: Days 2–3 — E-Commerce Brain & Tools (Complete)
* **What was done:**
  - Created `data/catalog.json` with 25 products across 3 categories (fashion, electronics, home) with ₹ prices, Indian context.
  - Created `data/orders.json` with 8 mock orders in various statuses (delivered, shipped, processing, cancelled, return_requested) with Indian city shipping.
  - Implemented `ShopMaxAgent` class extending `Agent` with three `@function_tool` methods: `product_search`, `stock_and_price_check`, and `order_status_lookup`.
  - Crafted grounding-focused system instructions that force tool usage and prohibit hallucination.

### Phase 1: Day 4 — FAQ & Grounding (Complete)
* **What was done:**
  - Created `data/policies.json` with 10 store policies covering return/refund windows, shipping times/fees, size exchanges, support, and warranty policies in an Indian context.
  - Implemented the `policy_lookup` `@function_tool` with keyword matching across policy topics, titles, and content.
  - Updated the agent instructions to govern policy grounding and direct the agent to use `policy_lookup` whenever asked about store rules.

### Phase 2: Day 5 & 8 — Edges, Latency Instrumentation, & Concurrency Fixes (Complete)
* **What was done:**
  - Tuned session parameters for barge-in: `allow_interruptions=True`, `min_interruption_duration=0.3`, and `min_interruption_words=1`.
  - Added instruction guidelines to `ShopMaxAgent` system prompt to handle low-confidence/empty STT inputs and unsupported off-topic questions.
  - Implemented custom latency logger in `agent.py` using `AgentSession` event hooks to print End-to-End turn latency, LLM TTFT, prompt/completion tokens, and TTS TTFB.
  - **Non-Blocking Greeting & Startup:** Fixed a bug where `await session.start(...)` was blocking the main entrypoint execution, causing the welcome greeting to never play first. Rerouted the session startup to run inside a non-blocking background task via `asyncio.create_task`, allowing the greeting timer to fire immediately upon connection.
  - **Google API Key Aliasing:** Programmatically populated `GOOGLE_API_KEY` at startup to prevent connection-time initialization crashes.
  - **WSL2 DNS Resolution Resolution:** Documented and resolved a known WSL2 DNS network glitch by manually overriding `/etc/resolv.conf` with a static public DNS resolver (`nameserver 8.8.8.8`).
  - **Gemini Free Tier Quota Exhaustion → dual-provider failover:** Hit Gemini `429 RESOURCE_EXHAUSTED` (free tier = 20 `gemini-2.5-flash` requests/day). Added `build_llm()` in `agent.py` returning a livekit **`FallbackAdapter([Gemini, NVIDIA])`** — **Gemini primary, NVIDIA fallback**. On a primary error (e.g. 429) it transparently retries NVIDIA's OpenAI-compatible endpoint (`integrate.api.nvidia.com/v1`, `meta/llama-3.1-8b-instruct`, ~481 ms TTFT). Verified by `tests/test_llm_fallback.py` (real path + forced-broken-primary). The 70b model was 3.5–31 s and unusable.

### Phase 3: Days 6–7 — Frontend Design Layer & UI Bugfixes (Complete)
* **What was done:**
  - Cloned the LiveKit React voice-agent starter repository into `frontend/` and configured `.env.local` for local tokens.
  - Updated storefront branding: created custom SVG logo (`logo.svg`), default dark theme, header layout with connection status indicator, and a branded welcome entry card.
  - Configured the premium `aura` WebGL visualizer as the default style and forced the live transcript panel to open by default for a clean split-screen layout.
  - **Auto-Scrolling Transcript Fix:** Bound `scrollAreaRef` to `<AgentChatTranscript>` and removed the `lastMessageIsLocal` check to allow the transcript area to scroll to the bottom automatically on all new user and agent messages, fixing the "chat freeze" issue.

### Phase 3.5: UI Redesign ("Suggested Direction") & Product Surface (Complete)
* **Design research:** Followed a compiled moodboard's **"Suggested Direction"** — a voice-commerce design brief.
* **Design system** (`frontend/styles/globals.css`):
  - Void-based dark palette as CSS-var tokens + Tailwind utilities (`bg-bot`, `text-voice`, …): **Void `#0A0A0F` · Bot `#7C5CFF` · Voice `#C8FF00` · Cart `#FF5CA8` · Live `#00D4FF` · Paper `#F4F4F8`**.
  - Motion keyframes (`aurora`, `glow`, `float`, `ring-pulse`) + a `prefers-reduced-motion` guard.
* **Typography** (`app/layout.tsx`): **Inter** (display/body), **Instrument Serif Italic** (accent), **JetBrains Mono** (metadata/SKU). Rebranded header with gradient wordmark + cyan "Live" status pill.
* **Animated hero** (`components/app/welcome-view.tsx`): aurora background, **mic orb as the primary control** (pulsing rings), named bot persona **"Max"** ("Meet Max, your *voice shopping concierge.*"), mic-forward CTA, mono feature chips.
* **Live product surface** (the flagship feature):
  - `data/catalog.json` gained an `image_url` per product (keyword-relevant LoremFlickr photos; swap real photos anytime).
  - `agent.py` publishes over LiveKit text streams (best-effort, no-ops without a room): `_publish_products()` → topic `shopmax.products` (from `product_search` + `stock_and_price_check`), and `_publish_order()` → topic `shopmax.order` (from `order_status_lookup`, **verified path only** so unverified lookups never surface details).
  - `components/agents-ui/product-panel.tsx` is a docked, animated drawer (a general **results surface**) that subscribes via `registerTextStreamHandler`:
    - **Product grid** (2-column): image + designed gradient fallback, mono SKU, stock badge, color swatches, size chips, ₹ price; **always-visible cart total** + qty steppers; sold-out disables "add".
    - **Order card**: status **stepper** (Placed → Processing → Shipped → Delivered), items with qty/color/size, ₹ total, shipping city, ETA, mono tracking #; cancelled/return states handled.
    - A **segmented switch** toggles Products ⇆ Order when both exist; a slide-in reopen tab restores the panel.
    - **Voice↔visual loop:** tapping a product photo sends a chat message to the agent on the `lk.chat` topic (`localParticipant.sendText`) — "Tell me more about the …" — so Max responds by voice.
  - **Voice-aware cart (full loop):** the panel pushes cart state (`items`/`count`/`total`) to the agent over `shopmax.cart`; `agent.py` stores it (`ShopMaxAgent.update_cart`, registered in the entrypoint) and exposes a **`view_cart` tool** so Max can answer "what's in my cart?" / "what's my total?" out loud (`total_spoken` via `num2words`). Unit-tested in `tests/test_cart.py`.
  - **Polish:** staggered card entrance, image loading skeleton (fade-in), equal-height cards, a designed **no-results state** (backend now publishes empty result sets too, so the panel never silently drifts out of sync with what Max says), and a state-aware **"Max" persona badge** in the live session view (`max-persona-badge.tsx` — serif-M avatar + color-coded listening/thinking/speaking indicator, per the "name the bot, give it an avatar" principle).
* **GitHub:** frontend pushed to a **private** repo `moushmirao30/ecom-voicebot-frontend` (branches `main` = starter base, `feat/ui-suggested-direction` = all redesign work). The local frontend keeps `origin` → upstream `livekit-examples/agent-starter-react` and pushes to the `myfork` remote.
* **Verification:** `pnpm build` green, `tsc` clean; hero, product grid, order card, cart, no-results state, and persona badge all checked interactively (screenshots via throwaway preview harnesses, removed after). Fixed a **pre-existing CRLF lint error** in `agent-session-block.tsx` that only surfaced under `pnpm build` (dev never lints). Backend fast suite green throughout (**19 passed** network-free).
* **How to demo the panel:** run agent + frontend, connect, then say/type **"show me headphones"** → the agent searches, publishes, and the panel slides in.

---

## 🗺️ Phase-by-Phase Roadmap

### Phase 1: The Brain (Days 1–4)
* [x] **Housekeeping:**
  - [x] Initialize project inside Linux home (`~/projects/voicebot`).
  - [x] Install `ffmpeg` inside Ubuntu.
  - [x] Activate Python venv and install dependencies.
* [x] **Custom Pipeline & Turn Detection:**
  - [x] Integrate Deepgram Nova-3 (STT), Cartesia Sonic (TTS), and Fast LLM (Gemini 2.5 Flash) inside `AgentSession`.
  - [x] Add TurnDetector and prewarm Silero VAD. Cache weights locally.
* [x] **E-commerce Brain & Tools:**
  - [x] Create mock catalog (JSON, 25 products) and orders table (JSON, 8 orders).
  - [x] Define `@function_tool`s: `product_search`, `stock_and_price_check`, and `order_status_lookup`.
  - [x] Craft grounding prompts directing the agent to always use tools and never hallucinate.
* [x] **FAQ & Grounding Retrieval:**
  - [x] Implement returns/shipping policy KB (JSON, 10 topics) and `policy_lookup` tool.
  - [x] Harden prompts to prevent fabrication of products, prices, or policy.

### Phase 2: Reliability & Proof (Days 5, 8)
* [x] **Latency & Edges:**
  - [x] Implement barge-in (interruption handling).
  - [x] Handle low-confidence STT.
  - [x] Instrument latency logging: Time-To-First-Token (TTFT) and End-to-End (E2E) turn latency.
  - [x] Fix blocking `session.start` greeting bug.
  - [x] Document Google API key aliasing, WSL2 DNS, and Gemini 429 quota exhaustion.

### Phase 3: The Design Layer (Days 6–7)
* [x] **Agent-State UI & Motion:**
  - [x] Fork the LiveKit React starter.
  - [x] Add custom logo, ShopMax storefront branding, and aura visualizer default.
  - [x] Force live transcript panel open.
  - [x] Fix transcript auto-scroll "chat freeze" bug.

### Phase 4: Deploy & Package (Days 9–13)
* [x] **Deployment (Day 9 - ~5 hr):**
  - [x] Deploy voice agent to LiveKit Cloud.
  - [x] Deploy frontend to Vercel (token route production fix, branch merged to `main`).
  - [ ] Deploy `agent.py` to a persistent cloud host (Railway/Render/VPS) — see **Agent Cloud Hosting** below.
  - [ ] Perform 10x full-flow runs and fix UX friction points.
* [ ] **Branded Showcase & Demo (Days 10–11 - ~10 hr):**
  - [ ] Construct a mock storefront layout.
  - [ ] Record a 60–90s demo video showcasing a natural flow.
* [ ] **Case Study & Documentation (Day 12 - ~5 hr):**
  - [ ] Draft high-quality README containing the architecture diagram, latency table, and agentic tool-use explanation.

---

## 🔧 Hardening Pass (post-Phase-3)

A round of robustness/quality improvements with tests. Status:

| # | Improvement | Status | Notes |
|---|---|---|---|
| 1 | **Grounding eval suite** | ✅ Done | `tests/test_grounding_evals.py` — deterministic tool/grounding checks + LLM judges. Caught a real hallucination bug (see #5). |
| 2 | **LLM failover** (Gemini primary → NVIDIA fallback) | ✅ Done | `build_llm()` uses `FallbackAdapter`; `tests/test_llm_fallback.py` proves a turn survives primary failure. |
| 3 | **Identity-gated order lookups** | ✅ Done | `order_status_lookup` now requires `customer_name` and verifies it strictly using a subset matching gate (`_name_matches`) before revealing details. Wrong name (or partial matching name with contradictory tokens like 'Priya Patel') → blocked, no leak (`test_order_lookup_blocks_wrong_identity`, `test_order_lookup_blocks_partially_wrong_identity`). |
| 4 | **Deterministic ₹/number formatting** | ✅ Done | Tools return a `price_spoken`/`total_spoken` form (`num2words` en_IN); prompt no longer asks the LLM to convert digits. Also added character-by-character spelling spelling (`order_id_spoken`, `tracking_number_spoken`) for clean TTS pronunciation. |
| 5 | **Robust retrieval** (fuzzy product search) | ✅ Done | `rapidfuzz` min-token coverage over name+subcategory+colors (threshold 68), with split-word rescue. Expanded search stopwords list (`cheap`, `best`, `latest`, `premium`, etc.) to filter qualitative retail descriptors. Absent products score below threshold and return nothing (`test_retrieval.py`). |
| 6 | **Per-step LLM routing** (NVIDIA tools / configurable reply) | ✅ Done | `ShopMaxAgent.llm_node` routes tool-decision turns → NVIDIA, post-tool reply → `LLM_PRIMARY` provider (`_select_route`), each with the other as fallback. Toggle via `route_llms`. Tested in `test_llm_routing.py`. **`LLM_PRIMARY` env var (default `nvidia`)** picks the reply-step primary. ⚠️ **Latency bug found & fixed on the cloud deploy (2026-07-04):** the reply step defaulted to **Gemini primary**, but the Gemini free tier is 20 req/day and is normally quota-exhausted (429). So every reply turn wasted a full round-trip on the dead primary (worsened by `attempt_timeout=10.0`) before failing over → **E2E turns of 5.7–22.6s**. Defaulting `LLM_PRIMARY=nvidia` removed the wasted hop: **verified live at 1.8–2.2s E2E, 0×429, 0×switches**. Set `LLM_PRIMARY=gemini` to prefer Gemini quality on days it has quota. |
| 7 | **Structured metrics export** | ✅ Done | `_MetricsRecorder` writes one JSON object per metric event to `METRICS_JSONL` (kinds: `turn`/`llm`/`tts`), alongside the human logs. Verified live (16 records). Unit-tested in `test_metrics.py`. OTel suggested for production. |
| 8 | **Secrets / CI hygiene** | ✅ Done | `.env`/secrets and `frontend/` (separate starter) gitignored — **verified via `git ls-files`: only `.env.example` is tracked, no real keys were ever committed** (earlier "rotate — shared in chat" note was over-cautious). `.github/workflows/ci.yml`: fast unit job (`-m "not llm"`, no keys) on every push + gated nightly LLM-eval job. LLM evals auto-retry (`pytest-rerunfailures`) to absorb model nondeterminism. |
| 9 | **Product surface pipeline** | ✅ Done | Agent → frontend product grid over a text stream (see Phase 3.5). `_publish_products()` is best-effort (no-ops without a room), so grounding evals are unaffected. Verified live (panel + cart interactive test). |

**Test suite: 63 passed** (50 network-free unit + 13 live-LLM evals). Run: `pytest` (all) or `pytest -m "not llm"` (fast, no keys). *Unit total grew with the live-deploy fixes above: `test_order_id.py` (13, L2), `test_category_filter.py` (5, L5), `test_stock_price_match.py` (4, L7), `test_policy_match.py` (5, L9), `test_tts_provider.py` (3, L11), plus routing/cart.*

> **GitHub (both repos private, CI green):**
> - **Backend** `moushmirao30/ecom-voicebot` — `main` (baseline + hardening) and `feat/ui-suggested-direction` (all Phase-3.5 work: streams, cart tool, catalog images, this doc), both pushed. One CI fix landed post-first-push: `test_build_routed_llms_returns_distinct_pair` assumed both provider keys existed (true only with a local `.env`) — made key-independent via `monkeypatch` so the keyless unit job passes.
> - **Frontend** `moushmirao30/ecom-voicebot-frontend` — `feat/ui-suggested-direction` **merged into `main`** (2026-07-02). Deployed to **Vercel** at `https://ecom-voicebot-frontend.vercel.app/`. Token route production fix included in the merge. Local `origin` still points at upstream `livekit-examples/agent-starter-react`; push via the `myfork` remote.
> - **Backend** feature branch not yet merged to `main` — open PR when ready:
>   `github.com/moushmirao30/ecom-voicebot/pull/new/feat/ui-suggested-direction`

---

## ☁️ Agent Cloud Hosting

The frontend (Vercel) and agent (`agent.py`) **never talk directly** — both connect independently to **LiveKit Cloud**, which bridges them in real-time. The agent must be a **long-running process** (not serverless).

| Component | Deployed to | Connects to |
|---|---|---|
| Frontend (Next.js) | Vercel (`ecom-voicebot-frontend.vercel.app`) | LiveKit Cloud (generates JWT via `/api/token`) |
| Agent (`agent.py`) | Needs a persistent host (see below) | LiveKit Cloud (WebSocket, auto-joins rooms) |

**Recommended options (easiest first):**

1. **Railway** (recommended) — connect GitHub repo, auto-detects `Dockerfile`, add env vars, deploy. Free tier ($5/mo). Container runs 24/7.
2. **Render** — similar to Railway; use a **Background Worker** (not Web Service — the agent doesn't serve HTTP).
3. **Google Cloud Run** — `gcloud run deploy` with `--min-instances 1` (always-on). More complex setup.
4. **Any VPS** (DigitalOcean/EC2) — `docker build -t ecom-voicebot . && docker run -d --restart unless-stopped --env-file .env ecom-voicebot`.

**Required env vars on the host (same as `.env`):** `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`, `DEEPGRAM_API_KEY`, `CARTESIA_API_KEY`, `GEMINI_API_KEY` (and optionally `NVIDIA_API_KEY` / `NVIDIA_LLM_MODEL`).

The existing `Dockerfile` is production-ready — it installs deps, caches Silero VAD weights, and runs `python agent.py start`.

> **LiveKit Cloud agent (`lk agent create`)** is an alternative if you have `lk` CLI access — the agent is already deployed as `CA_52WcohugKh5g` (region `ap-south`). See Phase 4 notes above.

---

## 📐 Latency Targets

| Metric | Target | Acceptable |
|---|---|---|
| **Time-to-first-token (TTFT)** | < 600 ms | < 1 s |
| **End-to-end turn latency** | < 1.2 s | < 1.8 s |

### Observed

An **automated benchmark** ([bench/latency_bench.py](bench/latency_bench.py)) drives the live agent with no microphone: it synthesizes the 10 user queries with Cartesia, publishes them into a LiveKit room as realtime audio, runs the full STT→LLM→TTS turn, and parses the medians from the agent's own log. Run it with:

```bash
# terminal 1 (WSL):
cd ~/projects/voicebot && source venv/bin/activate
python agent.py dev > /tmp/agent_bench.log 2>&1 &
# terminal 2 (same venv):
AGENT_LOG=/tmp/agent_bench.log python bench/latency_bench.py
```

**Measured 2026-06-30** — LLM = NVIDIA `meta/llama-3.1-8b-instruct`, 10 queries / ~30 conversational turns (tool-using queries make two LLM round-trips each):

| Metric | Target | Observed (median) | Range | Date | Pass? |
|---|---|---|---|---|---|
| LLM TTFT | < 600 ms | **481 ms** (n=57) | 355–4624 ms | 2026-06-30 | ✅ |
| TTS TTFB | — | **184 ms** (n=27) | 159–228 ms | 2026-06-30 | ✅ |
| End-to-end turn | < 1.2 s | **1658 ms** (n=30) | 1000–5787 ms | 2026-06-30 | ⚠️ within <1.8s acceptable |

> ✅ **LLM TTFT (481 ms) and TTS TTFB (184 ms) beat their targets.** STT (Deepgram) finalization adds ~1.1 s.
>
> ⚠️ **End-to-end turn (1.66 s) misses the < 1.2 s target but sits inside the < 1.8 s "acceptable" band.** Root cause is structural, not a regression: a tool-using turn runs **two** sequential LLM calls (decide-tool → run tool → formulate reply) plus STT endpointing + TTS TTFB, so ~2×(481 ms) + STT + 184 ms ≈ 1.6 s. Non-tool turns hit the floor (~1.0 s). The max outliers (4.6 s TTFT / 5.8 s E2E) are NVIDIA free-endpoint cold-starts/throttling.
>
> **Levers if sub-1.2 s E2E is required:** keep the model warm, shorten STT endpointing, or use a faster inference tier. The **70b** model was rejected — it measured 3.5–31 s TTFT on the free endpoint (unusable for voice).

---

## 🛑 Cut-Line Priority

If we run behind schedule, features should be sacrificed in the following order:
1. Telephony integration (never planned, but explicitly out of scope).
2. FAQ RAG knowledge base.
3. ~~Eval count.~~ ✅ **Delivered** — full suite in `tests/` (31 passed: 19 unit + 12 live-LLM evals, incl. the once-xfail "gaming laptops" grounding test, fixed by retrieval hardening).
4. Custom frontend motion transitions.

---

## 🔍 Risk Register

| Risk | Impact / Likelihood | Mitigation Status |
|---|---|---|
| **Day-1 environment setup issues** | High / Med | ✅ **Retire:** WSL2 environment verified, baseline quickstart works. |
| **Turn detector / pipeline tuning lags** | High / High | ✅ **Retire:** Local VAD and TurnDetector cached and working. |
| **Feature creep / UI over brain** | High / Med | ✅ **Retire:** Brain locked and frontend fully integrated. |
| **WSL RAM constraint / OOM** | Med / Med | 🟡 **Active Risk:** Cap WSL memory in `%UserProfile%\.wslconfig` (`[wsl2]` → `memory=8GB`, `swap=4GB`), then `wsl --shutdown` to apply. Monitor with `free -h` during runs. |
| **Flaky live demo** | Med / Med | 🟡 **Active Risk:** Ensure robust demo video is created as fallback. |
| **NVIDIA free-endpoint cold-start / throttle** | Med / Med | 🟡 **Active Risk:** Free `integrate.api.nvidia.com` showed occasional 4.6 s TTFT / 5.8 s E2E spikes vs 481 ms median. Warm the model with a throwaway request before recording; keep the Gemini fallback (`NVIDIA_API_KEY` unset) and a fresh AI Studio key on standby. |
| **Exposed API secrets** | High / Low | ✅ **Retire:** Verified via `git ls-files` — **only `.env.example` is tracked**; real `.env` / `frontend/.env.local` were never committed (root `.gitignore` excludes `.env*`). Keys were not exposed. Standard hygiene still applies: rotate if a key is ever pasted somewhere public, and distribute via `.env.example` only. |
| **Bleeding-edge runtime (Python 3.14 / Ubuntu 26.04)** | Med / Low | ✅ **Retire:** All native wheels (Silero, livekit-plugins 1.6.4) install and run on Python 3.14.4. Risk noted in case a future plugin upgrade lacks 3.14 wheels — fall back to 3.12 if so. |

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
| **Phase 4** | Deploy & Package | Cloud deployment, Demo video, Case study | Days 9–13 | 🟡 **IN PROGRESS** |

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
| **TTS (Text-to-Speech)** | Cartesia Sonic (`livekit-plugins-cartesia`) | State-of-the-art generation speeds with highly natural-sounding inflection. |
| **Turn Detection** | Native `inference.TurnDetector` (audio-based) + Silero VAD | Built into livekit-agents 1.6.x. Audio+semantic analysis replaces deprecated text-only plugin. |
| **Data Store** | JSON files (catalog.json + orders.json) | Zero-overhead, easy to inspect/edit. 25 products, 8 orders with Indian context (₹ prices). |
| **Frontend** | React (LiveKit React Starter) + Motion UI | Transition-heavy UI (idle ➔ listening ➔ thinking ➔ speaking) for polished UX. |
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
│   ├── catalog.json         # 25 products (fashion / electronics / home), ₹ prices
│   ├── orders.json          # 8 mock orders across 5 statuses
│   └── policies.json        # 10 store policies (returns, shipping, COD, warranty…)
├── bench/
│   └── latency_bench.py     # Mic-free latency benchmark (TTS-injected audio → live pipeline → median TTFT/TTFB/E2E)
├── tests/
│   ├── test_grounding_evals.py  # Grounding/hallucination evals via LiveKit text-mode session.run()
│   └── README.md
├── conftest.py              # Shared eval LLM factory (build_eval_llm / build_judge_llm)
├── pytest.ini               # asyncio_mode=auto, testpaths=tests
├── requirements-dev.txt     # pytest, pytest-asyncio
└── frontend/                # LiveKit React starter (Next.js 15, React 19)
    ├── .env.local           # SECRETS — LiveKit URL/key/secret for token route
    └── package.json         # pnpm-managed; aura visualizer + branding customizations
```

**Key code anchors in `agent.py`:**
- `ShopMaxAgent` (instructions + grounding rules) — [agent.py:50](agent.py:50)
- Tools: `product_search` [agent.py:78](agent.py:78), `stock_and_price_check` [agent.py:130](agent.py:130), `order_status_lookup` [agent.py:173](agent.py:173), `policy_lookup` [agent.py:225](agent.py:225)
- `AgentSession` config (STT/LLM/TTS/turn-detection/barge-in) — [agent.py:287](agent.py:287)
- Latency instrumentation (E2E / TTFT / TTFB / tokens) — [agent.py:299](agent.py:299)
- Non-blocking greeting via `asyncio.create_task` — [agent.py:337](agent.py:337)

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
- Current status: **22 passed** (grounding + fallback + formatting + retrieval).

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
* [ ] **Deployment (Day 9 - ~5 hr):**
  - [ ] Deploy voice agent to LiveKit Cloud.
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
| 3 | **Identity-gated order lookups** | ✅ Done | `order_status_lookup` now requires `customer_name` and verifies it (`_name_matches`) before revealing details. Wrong name → blocked, no leak (`test_order_lookup_blocks_wrong_identity`). Demo-grade gate, not strong auth. |
| 4 | **Deterministic ₹/number formatting** | ✅ Done | Tools return a `price_spoken`/`total_spoken` form (`num2words` en_IN); prompt no longer asks the LLM to convert digits. Unit-tested in `test_formatting.py`. |
| 5 | **Robust retrieval** (fuzzy product search) | ✅ Done | `rapidfuzz` min-token coverage over name+subcategory+colors (threshold 68), with split-word rescue. Absent products now return nothing — **fixed the hallucination bug from #1** (its eval is now a normal pass). Unit-tested in `test_retrieval.py`. |
| 6 | **Per-step LLM routing** (NVIDIA tools / Gemini reply) | ✅ Done | `ShopMaxAgent.llm_node` routes tool-decision turns → NVIDIA, post-tool reply → Gemini (`_select_route`), each with the other as fallback. Toggle via `route_llms`. Tested in `test_llm_routing.py`. *Note: while Gemini's quota is exhausted the reply step transparently falls back to NVIDIA, so the quality benefit only shows once Gemini has quota.* |
| 7 | **Structured metrics export** | ⏳ Pending | Replace print-logs with a queryable sink. |
| 8 | **Secrets / CI hygiene** | ⏳ Pending | `git init`, key rotation, CI to run evals. |

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
3. ~~Eval count.~~ ✅ **Delivered** — grounding eval suite in `tests/` (7 passed, 1 tracked xfail).
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
| **Exposed API secrets** | High / High | 🔴 **Active Risk:** Real LiveKit/Deepgram/Cartesia/Gemini keys are committed in `.env` and `frontend/.env.local`. **Rotate all keys** before sharing this repo, add a root `.gitignore` (done) excluding `.env*`, and distribute via `.env.example` only. |
| **Bleeding-edge runtime (Python 3.14 / Ubuntu 26.04)** | Med / Low | ✅ **Retire:** All native wheels (Silero, livekit-plugins 1.6.4) install and run on Python 3.14.4. Risk noted in case a future plugin upgrade lacks 3.14 wheels — fall back to 3.12 if so. |

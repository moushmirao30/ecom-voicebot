# LiveKit E-Commerce Voicebot — Work Plan v2 (post-spike)

**Status:** Environment + baseline talking bot ✅ DONE. Pipeline/tools/design/packaging ahead.
**Remaining budget:** ~65 focused hours over 13 days (banked ~1 day from a clean setup — held as end buffer).
**Governing rule (unchanged):** complete shopping conversation working by **Day 3**. Form after function. A pretty UI on a bot that doesn't reliably talk is a failed capstone.

---

## ✅ ALREADY COMPLETE (Phase 0)
- [x] WSL2 (2.7.10) installed, Ubuntu 26.04 running
- [x] Linux user account created
- [x] LiveKit quickstart talks in the browser (default stack)

### Carry-over housekeeping — confirm before Day 1 (~20 min)
- [ ] Project lives in the **Linux** home (`~/projects/voicebot`), not `/mnt/c/...`
- [ ] `ffmpeg` installed inside Ubuntu (`sudo apt install -y ffmpeg`) — the voice pipeline needs it
- [ ] Python venv active + `livekit-agents` installed (it is, if the quickstart ran)
- [ ] **Watch item, not urgent:** WSL is showing ~7.8 GB RAM. The turn-detector + VAD are local models; if you hit slowness/OOM later, raise the cap via a `.wslconfig` file (ask me then)

---

## PHASE 1 — The Brain (Days 1–4)

### Day 1 — Custom pipeline + turn detection (~5 hr) ⟵ **the real next risk**
This is what the spike did *not* test. Expect it to take longer than swapping a few lines looks like it should.
- [ ] Replace the default stack inside `AgentSession`: **Deepgram Nova-3** (STT) / fast LLM / **Cartesia Sonic** (TTS), via LiveKit Inference.
- [ ] Add `livekit-plugins-turn-detector` (transformer) + Silero VAD loaded in prewarm. Run `download-files` so model weights are local.
- [ ] Tune `min_endpointing_delay` until pauses feel natural, not clipped or laggy.
- **Done when:** your custom-stack bot waits for you to finish speaking, then answers in the Cartesia voice. Hazard: turn-detector model download + first-run tuning is the most likely time sink today — start it early in the session.

### Days 2–3 — E-commerce brain (~10 hr) ⟵ **CRITICAL MILESTONE**
- [ ] Mock catalog (SQLite/JSON): ~20–30 products with name, price, stock, color/size, category.
- [ ] Mock orders table (id, status, items).
- [ ] Three `@function_tool`s: **product_search**, **stock_and_price_check**, **order_status_lookup**.
- [ ] Prompt the agent to call tools rather than answer from memory.
- **Done when (END OF DAY 3):** full spoken flow works end-to-end — "find a blue jacket under ₹3000" → "in stock?" → "status of order #1042?". Ugly is fine; *complete* is the bar.
- This leans on your existing CrewAI/RAG skillset — move fast.

### Day 4 — Grounding + FAQ retrieval (~5 hr)
- [ ] Returns/shipping/policy knowledge base + retrieval tool.
- [ ] Prompt hardening: never invent products, prices, or policy; say so when unknown.
- [ ] **Lock the brain.** No feature adds after today.
- **Done when:** policy questions answer from the KB and the bot refuses to fabricate.
- **CUT-LINE #1:** if Days 1–3 slipped, drop the FAQ RAG, keep catalog tools.

---

## PHASE 2 — Reliability + Proof

### Day 5 — Edges + latency instrumentation (~5 hr)
- [ ] Barge-in (interrupt the bot mid-sentence).
- [ ] "I didn't catch that" recovery on low-confidence STT.
- [ ] Log **time-to-first-token** and **end-to-end turn latency** per turn.
- **Done when:** real latency numbers exist and interruption is handled.

### Day 8 — Evals (~5 hr) *(after the design block — see note)*
- [ ] 8–10 scenario tests via LiveKit's test framework + LLM judge: in-stock, out-of-stock, off-topic, interruption, unknown-policy, wrong order id.
- [ ] Latency table: median + p90 for both metrics.
- **CUT-LINE #2:** if behind, 5 tests — happy path + 2 failure modes.

**Latency targets**
| Metric | Target | Acceptable |
|---|---|---|
| Time-to-first-token | < 600 ms | < 1 s |
| End-to-end turn | < 1.2 s | < 1.8 s |

---

## PHASE 3 — The Design Layer (Days 6–7) — your unfair advantage

### Days 6–7 — Frontend agent-state motion (~10 hr)
- [ ] Fork the LiveKit React starter; strip to a clean shell.
- [ ] Agent-state UI as **motion**: idle → listening → thinking → speaking, with intentional transitions (your MA skill set, directly applied).
- [ ] Live transcript, current-action affordance, restrained brand palette for a fake store.
- **Done when:** it reads as a product, not a demo harness. Half the portfolio value — treat as real motion work.
- **CUT-LINE #3:** if behind, 3 clean states with simple fades. Never below "looks intentional."

> **Sequencing note:** design (6–7) is scheduled before evals (8) on purpose — design is the part only you can do and is your differentiator, so it gets the protected high-energy slot; evals are mechanical and can absorb a tired day. Swap them (evals → Day 6) if you'd rather de-risk correctness earlier.

---

## PHASE 4 — Deploy + Package (Days 9–13)

### Day 9 — Deploy + fix-the-worst (~5 hr)
- [ ] Deploy agent to LiveKit Cloud (no code changes from local).
- [ ] Run the full flow 10×; each pass, fix the single most awkward moment.
- **Done when:** smooth ~9 of 10 runs.

### Days 10–11 — Demo video + branded store (~10 hr)
- [ ] Branded fake storefront (your quiet-luxury editorial instinct).
- [ ] 60–90s edit: real conversation, **one graceful failure-and-recovery on purpose**, captions, clean pacing.
- **Done when:** it looks like a product launch, not a screen recording. This asset outperforms the code for hiring managers.

### Day 12 — Case study / README (~5 hr)
- [ ] Architecture diagram (STT→LLM→TTS, turn detection, tools, catalog, Cloud).
- [ ] Latency numbers, eval results, design rationale.
- [ ] **Agentic-rubric framing:** present it as an *agent with tools that decides which actions to take* — name the tool-use loop, not "chatbot."
- **Done when:** a reader who never runs it understands what you built and why it's good.

### Day 13 — Buffer + live rehearsal (banked safety day)
- [ ] Rehearse the live demo on the deployed agent (real network conditions).
- [ ] Keep the recorded video as fallback if live audio misbehaves.

---

## RUBRIC-SCORING CHECKLIST
- [ ] Low-latency voice that *feels* conversational (turn detection done right)
- [ ] Genuine tool use / function calling — the "agentic" credit
- [ ] Grounding + refusal: never fabricates products, prices, policy
- [ ] Measured latency, not vibes
- [ ] Automated evals with a judge
- [ ] Deployed on Cloud, not laptop-only
- [ ] Product-grade UI + demo video (your differentiator)
- [ ] Architecture writeup with explicit agentic framing

## CUT-LINE PRIORITY (sacrifice top-down when behind)
1. Telephony (never planned)
2. FAQ RAG knowledge base (Day 4)
3. Eval count: 10 → 5
4. Frontend: custom motion → clean fades
**NEVER CUT:** working pipeline · catalog tools · turn detection · latency numbers · demo video.

## RISK REGISTER (updated)
| Risk | Status | Mitigation |
|---|---|---|
| Day-1 env hell | ✅ RETIRED | WSL2 + spike passed |
| Custom pipeline / turn-detector tuning | 🔴 NOW THE TOP RISK | Day 1; start model download early |
| Polishing voice before brain works | High | Hard Day-3 milestone |
| 8 GB RAM ceiling on local models | Med | `.wslconfig` bump if slow/OOM |
| Flaky live demo | Med | Recorded video fallback (Day 13) |
| Time overrun | Med | Cut-line order above, pre-decided |

# LiveKit E-Commerce Voicebot — Work Plan v3 (spec-aligned)

**Status:** Environment + baseline talking bot ✅ DONE.
**Remaining budget:** ~65 focused hours over 13 days.
**Governing rule:** complete shopping conversation working by **Day 3**. Form after function.
**v3 change:** mapped 1:1 to the institution's official brief — added the required **presentation deck**, flagged RAG + evals as spec-optional, noted the STT-choice justification.

---

## HOW THIS MAPS TO YOUR 4 REQUIRED DELIVERABLES
| Institution deliverable | Where it's produced |
|---|---|
| 1. Working voicebot prototype (info query + product response + backend action) | Days 1–3 |
| 2. Code repo (backend + frontend + README) | Backend Days 1–4 · Frontend Days 6–7 · README Day 12 |
| 3. Technical report (arch, prompts, STT/TTS + latency, limitations) | Day 12 |
| 4. Presentation deck | Day 13 |

## HOW IT MAPS TO THEIR 7 EVALUATION CRITERIA
| Criterion | Covered by | Your edge? |
|---|---|---|
| Real-time interaction quality | Day 1 pipeline + turn detection | — |
| Use of GenAI concepts (LLM/prompts/RAG/tools) | Days 1–4 | — |
| System design (modular, real-time) | architecture in report, Day 12 | — |
| Practical relevance (e-commerce) | Days 2–3 catalog flow | — |
| Code & documentation quality | README + report, Day 12 | — |
| **Presentation quality** | demo video + deck (Days 10–13) | 🟢 **YOUR EDGE** |
| Safety & UX (unclear speech, unsupported requests) | Day 5 | — |

> Two of seven scored lines (Presentation Quality + Practical Relevance) are where your design background and demo-production skill convert straight into marks. Most submissions will be technically passable and presentationally weak. Lean here.

---

## ✅ ALREADY COMPLETE (Phase 0)
- [x] WSL2 + Ubuntu running, user account created
- [x] LiveKit quickstart talks in the browser (default stack)

### Carry-over housekeeping (~20 min)
- [ ] Project in Linux home (`~/projects/voicebot`), not `/mnt/c/...`
- [ ] `ffmpeg` installed in Ubuntu
- [ ] venv + `livekit-agents` confirmed working
- [ ] Watch item: ~7.8 GB RAM to WSL — `.wslconfig` bump only if local models go slow/OOM

---

## PHASE 1 — The Brain (Days 1–4)

### Day 1 — Custom pipeline + turn detection (~5 hr) ⟵ top risk
- [ ] Swap default stack → **Deepgram Nova-3** (STT) / fast LLM / **Cartesia Sonic** (TTS) via LiveKit Inference.
- [ ] Add `livekit-plugins-turn-detector` + Silero VAD (prewarm). Run `download-files`.
- [ ] Tune `min_endpointing_delay` until pauses feel natural.
- **Done when:** custom-stack bot waits, then answers in the Cartesia voice.
- **Note for report:** you chose Deepgram over the spec's suggested Whisper — record the reason (lower streaming latency). Justified swaps score better than following suggestions blindly.

### Days 2–3 — E-commerce brain (~10 hr) ⟵ CRITICAL MILESTONE
- [ ] Mock catalog (~20–30 products: name, price, stock, color/size, category).
- [ ] Mock orders table (id, status, items).
- [ ] Three `@function_tool`s: **product_search**, **stock_and_price_check**, **order_status_lookup**.
- **Done when (END OF DAY 3):** spoken flow covers the spec's three required cases — **one informational query, one product response, one backend action** — end to end. Ugly is fine; complete is the bar.

### Day 4 — Grounding + FAQ RAG (~5 hr) — ⚠️ SPEC-OPTIONAL
- [ ] Returns/shipping/policy KB + retrieval tool.
- [ ] Prompt hardening: never invent products, prices, policy.
- [ ] Lock the brain.
- **Spec status:** RAG is explicitly *optional* in the brief. Strengthens factual-consistency scoring if kept. **First thing to drop if behind — costs zero required deliverables.**

---

## PHASE 2 — Reliability + Proof

### Day 5 — Edges + latency (~5 hr) — REQUIRED (safety & UX criterion)
- [ ] Barge-in (interrupt mid-sentence).
- [ ] "I didn't catch that" recovery on low-confidence STT.
- [ ] Graceful handling of unsupported requests (spec calls this out explicitly).
- [ ] Log time-to-first-token + end-to-end turn latency.
- **Done when:** unclear speech + unsupported requests are handled gracefully, and you have latency numbers for the report.

### Day 8 — Evals (~5 hr) — ⚠️ NOT REQUIRED (your addition)
- [ ] 8–10 scenario tests (LiveKit test framework + LLM judge) + latency table.
- **Spec status:** not asked for. Adds rigor; safe to shrink to 5 tests or skip if time-pressed.

**Latency targets**
| Metric | Target | Acceptable |
|---|---|---|
| Time-to-first-token | < 600 ms | < 1 s |
| End-to-end turn | < 1.2 s | < 1.8 s |

---

## PHASE 3 — The Design Layer (Days 6–7) — your unfair advantage
### Days 6–7 — Frontend agent-state motion (~10 hr) — REQUIRED (deliverable #2 frontend)
- [ ] Fork LiveKit React starter; strip to a clean shell.
- [ ] Agent-state UI as motion: idle → listening → thinking → speaking.
- [ ] Live transcript, current-action affordance, restrained brand palette for a fake store.
- **Done when:** reads as a product, not a demo harness.
- **CUT-LINE:** if behind, 3 clean states with fades — never below "looks intentional."

> Sequencing: design before evals on purpose (design is your differentiator + only you can do it). Swap if you'd rather de-risk correctness earlier.

---

## PHASE 4 — Deploy + Package (Days 9–13)

### Day 9 — Deploy + fix-the-worst (~5 hr)
- [ ] Deploy agent to LiveKit Cloud.
- [ ] Run full flow 10×; fix the worst moment each pass.

### Days 10–11 — Demo video + branded store (~10 hr) — feeds deliverables #1 & #4
- [ ] Branded fake storefront.
- [ ] 60–90s edit: real conversation, one graceful failure-and-recovery on purpose, captions.
- **Done when:** looks like a product launch. (Doubles as live-demo fallback + deck material.)

### Day 12 — Technical report + README (~5 hr) — deliverables #2 & #3
- [ ] README: setup, configuration, execution steps (reproducibility is a scored line).
- [ ] Report: problem/scope · architecture + real-time flow · prompt design & reasoning logic · STT/TTS integration + latency (include the Deepgram-vs-Whisper justification) · limitations & future work.
- [ ] Architecture diagram (STT→LLM→TTS, turn detection, tools, catalog, Cloud).

### Day 13 — Presentation deck + rehearsal + buffer (~5 hr) — deliverable #4
- [ ] **Deck (~2.5 hr, repackaged from the report):** problem motivation/use case · architecture & stack · demo flow + screenshots (or live) · key challenges & learnings · next steps.
- [ ] Live-demo rehearsal on the deployed agent (real network).
- [ ] Remaining time = buffer for whatever broke.
- **Note:** deck is a *separate* scored deliverable from the report — don't merge them. Slides are repackaged report content, so this is assembly, not new writing.

---

## CUT-LINE PRIORITY (spec-confirmed safe order)
1. Telephony (never planned)
2. **FAQ RAG (Day 4)** — spec says optional
3. **Evals (Day 8)** — not required by spec
4. Eval count 10 → 5 (if keeping any)
5. Frontend: custom motion → clean fades
**NEVER CUT (all spec-required):** working pipeline · 3 query types (info/product/action) · turn detection · graceful error/unsupported handling · README · report · **deck** · demo.

## RISK REGISTER
| Risk | Status | Mitigation |
|---|---|---|
| Day-1 env hell | ✅ RETIRED | spike passed |
| Custom pipeline / turn-detector tuning | 🔴 TOP RISK | Day 1; start model download early |
| Forgetting the deck | 🟡 NEW (spec-required) | Day 13 slot reserved |
| Polishing voice before brain works | High | hard Day-3 milestone |
| 8 GB RAM on local models | Med | `.wslconfig` bump if needed |
| Flaky live demo | Med | recorded video fallback |
| Buffer now only half a day | Med | RAG/evals are pre-cleared cuts to reclaim time |

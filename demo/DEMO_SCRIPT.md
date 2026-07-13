# ShopMax Voicebot — 60–90s Demo Script

## Pre-recording checklist (do all of these, in order)

1. **Warm the stack** (kills the two flakiness sources):
   - Connect once, say "hi", wait for the reply, disconnect. This warms the
     NVIDIA endpoint (avoids the 4.6s cold-start TTFT spike) and confirms the
     cloud agent is dispatching.
   - Confirm Gemini has quota today (free tier = 20 requests/day). If it's
     spent, the FallbackAdapter still works — replies just come from NVIDIA.
2. **Environment**: quiet room, decent mic, browser at 1280×800+, dark theme.
3. **Frontend**: `pnpm dev` in `frontend/` (or the Vercel URL once hosted).
   The cloud agent (`CA_52WcohugKh5g`) picks up the room automatically — no
   local `agent.py` needed.
4. Screen recorder capturing **system audio + mic** (Max's voice matters).
5. Close the Next.js dev-tools overlay if visible.

## Shot list (target ≈ 80 seconds)

| # | Time | On screen | You say / do |
|---|---|---|---|
| 1 | 0–8s | Animated hero (aurora, mic orb) | 1-line intro over the hero: "This is ShopMax — a voice-first storefront built on LiveKit. Everything you'll hear is grounded in a real catalog — no hallucinations." Click **Start talking**. |
| 2 | 8–18s | Max greets; persona badge shows SPEAKING | Let the greeting play. |
| 3 | 18–32s | Product grid slides in | Say: **"Show me headphones."** Grid renders with photo, SKU, stock badge, ₹ price. |
| 4 | 32–44s | Cart total updates | Tap **add to cart**, then say: **"What's my cart total?"** Max answers in spoken words — the UI cart and the voice agent share state. |
| 5 | 44–60s | Order card with status stepper | Say: **"Track order ORD1002 — I'm Rahul Verma."** Order card slides in: Placed → Processing → Shipped stepper, ETA, tracking #. (Identity-gated: a wrong name gets nothing.) |
| 6 | 60–70s | Barge-in | While Max is mid-sentence, interrupt: **"What's the return policy?"** Max stops instantly and answers from the policy KB. |
| 7 | 70–80s | No-results state | Say: **"Show me trampolines."** Designed empty state — the UI never pretends. End on the panel + one closing line: "Sub-500ms first token, grounded answers, live UI. Built on LiveKit Agents with Deepgram, and automatic failover across the LLM and TTS." |

## Regression verification pass (L8–L11) — do this BEFORE the real take

These four bugs were fixed after the last recordings (`Test_run 1.mp4`,
`The audio glitch.mp4`) but are **not yet re-verified live**. Run this pass once;
if all four hold, the shot list above will be clean. Do it in one connected
session.

| Fix | What to do | Expected (pass) | If it fails |
|---|---|---|---|
| **L11 — audio glitch** | Just listen to the greeting + first reply. First, at startup confirm the agent log prints `TTS: Deepgram Aura only (TTS_PROVIDER=deepgram)` and shows **no Cartesia 402** lines. | Smooth, continuous speech — no stutter/gaps/mid-word jumps. | Check `TTS_PROVIDER=deepgram` is set in the *running* `.env` (WSL copy). Still glitchy → check `free -h`/`top` for WSL CPU/RAM starvation, and test with headphones (rules out speaker echo). |
| **L8 — scroll freeze** | After a few turns, scroll **up** in the transcript to re-read the greeting. | Transcript scrolls freely; the ⬇ jump-to-bottom button appears; releasing lets new messages resume auto-stick. | Confirm `conversation.tsx` has `overflow-y-auto` (not `-hidden`) in the *running* frontend copy. |
| **L8 — badge overlap** | Look at the top of the transcript while the "Max" chip is visible. | The persona chip sits **above** the first message line — no clipping/overlap. | Confirm `agent-session-block.tsx` uses `pt-52` / fade `h-52`. |
| **L10 — result count** | Say **"Show me headphones."** | Max says **one** item (there is one headphone) and does **not** claim others are on screen. Grid shows 1 card. | Re-check the "state the exact `found` count" line in the system prompt. |
| **L9 — return policy** | Two checks: (a) mid-sentence, interrupt with **"What's the return policy?"**; (b) separately, ask **"Do you take returns?"** (plural). | Both give the real 7-day return policy — neither deflects to `support@shopmax.in`. | Confirm `_match_policy` is in the running `agent.py` and barge-in is `min_interruption_words=2`. |

> **Voice note:** with `TTS_PROVIDER=deepgram`, Max speaks in **Deepgram Aura**,
> not Cartesia Sonic — shot 7's closing line has been worded to match what the
> viewer actually hears.

## Fallback plan

If a take goes sideways (throttled LLM, mis-transcription), just cut — every
segment is independent, so you can splice takes. Keep one clean full-flow
recording as the "flaky live demo" insurance the risk register calls for.

## What this demo proves (for the case study)

- Voice → tool → grounded answer loop (search, stock/price, orders, policies)
- Voice ↔ visual sync over LiveKit text streams (grid, order card, cart)
- Barge-in + persona states (listening / thinking / speaking)
- Cloud-deployed agent — nothing running locally but the browser

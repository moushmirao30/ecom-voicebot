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
| 7 | 70–80s | No-results state | Say: **"Show me trampolines."** Designed empty state — the UI never pretends. End on the panel + one closing line: "Sub-500ms first token, grounded answers, live UI. Built with LiveKit Agents, Deepgram, Gemini, and Cartesia." |

## Fallback plan

If a take goes sideways (throttled LLM, mis-transcription), just cut — every
segment is independent, so you can splice takes. Keep one clean full-flow
recording as the "flaky live demo" insurance the risk register calls for.

## What this demo proves (for the case study)

- Voice → tool → grounded answer loop (search, stock/price, orders, policies)
- Voice ↔ visual sync over LiveKit text streams (grid, order card, cart)
- Barge-in + persona states (listening / thinking / speaking)
- Cloud-deployed agent — nothing running locally but the browser

"""Automated latency benchmark for the ShopMax voicebot.

Drives the live agent without a microphone: synthesizes user queries with
Cartesia TTS, publishes them into a LiveKit room as realtime mic audio, lets the
agent run its full STT -> LLM -> TTS turn, and reads the latency numbers the
agent already prints to stdout. Computes median LLM TTFT / TTS TTFB / E2E and
prints ready-to-paste markdown rows for handoff.md.

No changes to agent.py are required. Run the worker first, redirecting its
output to a log the benchmark can read:

    python agent.py dev > /tmp/agent_bench.log 2>&1 &

Then, in the same venv:

    AGENT_LOG=/tmp/agent_bench.log python bench/latency_bench.py

Requires a WORKING GEMINI_API_KEY in .env (free-tier 429s produce no numbers).
"""
import asyncio
import os
import re
import statistics
import time
import json
import urllib.request
import uuid
from pathlib import Path

from dotenv import load_dotenv
from livekit import api, rtc

load_dotenv(str(Path(__file__).resolve().parent.parent / ".env"))

AGENT_LOG = os.environ.get("AGENT_LOG", "/tmp/agent_bench.log")
CARTESIA_KEY = os.environ["CARTESIA_API_KEY"]
LK_URL = os.environ["LIVEKIT_URL"]
LK_KEY = os.environ["LIVEKIT_API_KEY"]
LK_SECRET = os.environ["LIVEKIT_API_SECRET"]
USER_VOICE = "a0e99841-438c-4a64-b679-ae501e7d6091"  # generic Cartesia voice for the "user"

SAMPLE_RATE = 48000
QUERIES = [
    "Hi, I'm looking for a blue jacket.",
    "Do you have any wireless headphones?",
    "What's the price of the running shoes?",
    "Is the cotton kurta available in size large?",
    "Can you track my order ORD1001?",
    "What is the status of order ORD1005?",
    "What is your return policy?",
    "Do you offer free shipping?",
    "What is the cash on delivery limit?",
    "Show me some home decor items.",
]

RE_TTFT = re.compile(r"Time to First Token \(TTFT\): ([\d.]+) ms")
RE_TTFB = re.compile(r"Time to First Byte \(TTFB\): ([\d.]+) ms")
RE_E2E = re.compile(r"End-to-End Turn Latency: ([\d.]+) ms")


def synth(text: str) -> bytes:
    """Cartesia -> raw 48k mono PCM s16le bytes."""
    body = json.dumps({
        "model_id": "sonic-2",
        "transcript": text,
        "voice": {"mode": "id", "id": USER_VOICE},
        "output_format": {"container": "raw", "encoding": "pcm_s16le", "sample_rate": SAMPLE_RATE},
        "language": "en",
    }).encode()
    req = urllib.request.Request(
        "https://api.cartesia.ai/tts/bytes", data=body, method="POST",
        headers={"X-API-Key": CARTESIA_KEY, "Cartesia-Version": "2024-11-13",
                 "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


async def stream_pcm(source: rtc.AudioSource, pcm: bytes):
    """Push PCM into the room at realtime in 10ms frames."""
    frame_samples = SAMPLE_RATE // 100
    frame_bytes = frame_samples * 2
    for i in range(0, len(pcm), frame_bytes):
        chunk = pcm[i:i + frame_bytes].ljust(frame_bytes, b"\x00")
        await source.capture_frame(rtc.AudioFrame(
            data=chunk, sample_rate=SAMPLE_RATE, num_channels=1, samples_per_channel=frame_samples))


async def push_silence(source: rtc.AudioSource, seconds: float):
    frame_samples = SAMPLE_RATE // 100
    frame_bytes = frame_samples * 2
    for _ in range(int(seconds * 100)):
        await source.capture_frame(rtc.AudioFrame(
            data=b"\x00" * frame_bytes, sample_rate=SAMPLE_RATE,
            num_channels=1, samples_per_channel=frame_samples))


def parse_log():
    """Return ordered lists of every TTFT / TTFB / E2E value in the agent log."""
    ttft, ttfb, e2e = [], [], []
    if not os.path.exists(AGENT_LOG):
        return ttft, ttfb, e2e
    with open(AGENT_LOG, encoding="utf-8", errors="ignore") as f:
        for line in f:
            if (m := RE_TTFT.search(line)):
                ttft.append(float(m.group(1)))
            elif (m := RE_TTFB.search(line)):
                ttfb.append(float(m.group(1)))
            elif (m := RE_E2E.search(line)):
                e2e.append(float(m.group(1)))
    return ttft, ttfb, e2e


async def main():
    room_name = f"bench-{uuid.uuid4().hex[:8]}"
    token = (api.AccessToken(LK_KEY, LK_SECRET)
             .with_identity("bench-user")
             .with_grants(api.VideoGrants(room_join=True, room=room_name))
             .to_jwt())

    room = rtc.Room()
    await room.connect(LK_URL, token)
    print(f"[bench] connected to room {room_name}")

    source = rtc.AudioSource(SAMPLE_RATE, 1)
    track = rtc.LocalAudioTrack.create_audio_track("user-mic", source)
    await room.local_participant.publish_track(
        track, rtc.TrackPublishOptions(source=rtc.TrackSource.SOURCE_MICROPHONE))

    print("[bench] waiting 8s for agent dispatch + greeting...")
    await push_silence(source, 8.0)

    for i, q in enumerate(QUERIES, 1):
        print(f"[bench] turn {i}/{len(QUERIES)}: {q!r}")
        before = len(parse_log()[2])              # count of E2E lines so far
        await stream_pcm(source, synth(q))
        await push_silence(source, 1.2)           # trigger end-of-turn

        deadline = time.time() + 25
        while time.time() < deadline:
            if len(parse_log()[2]) > before:
                break
            await push_silence(source, 0.2)
        else:
            print(f"[bench]   ! no response captured for turn {i} (LLM error / quota?)")
        await push_silence(source, 0.8)

    await room.disconnect()

    ttft, ttfb, e2e = parse_log()

    def med(xs):
        return statistics.median(xs) if xs else None

    print("\n===== RESULTS =====")
    print(f"captured: e2e={len(e2e)} ttft={len(ttft)} ttfb={len(ttfb)}")
    for label, xs in [("LLM TTFT", ttft), ("TTS TTFB", ttfb), ("E2E turn", e2e)]:
        if xs:
            print(f"{label:10s} median={med(xs):7.0f} ms  min={min(xs):7.0f}  max={max(xs):7.0f}  n={len(xs)}")
        else:
            print(f"{label:10s} (no data — is the Gemini key live?)")

    today = time.strftime("%Y-%m-%d")
    cell = lambda v: f"{v:.0f} ms" if v is not None else "_no data_"
    print("\n----- paste into handoff.md (Observed table) -----")
    print(f"| LLM TTFT | < 600 ms | {cell(med(ttft))} | {today} | |")
    print(f"| TTS TTFB | — | {cell(med(ttfb))} | {today} | |")
    print(f"| End-to-end turn | < 1.2 s | {cell(med(e2e))} | {today} | |")


if __name__ == "__main__":
    asyncio.run(main())

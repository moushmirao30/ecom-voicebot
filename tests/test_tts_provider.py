"""Regression tests for the TTS provider toggle (L11).

While Cartesia is out of free credits it 402s on every synthesis handshake. With
Cartesia as the FallbackAdapter primary, each utterance pays that failed
handshake and then switches to Deepgram Aura mid-turn — which stutters/glitches
the audio (reproduced in the "The audio glitch" recording). TTS_PROVIDER=deepgram
runs Aura ALONE so no Cartesia stream is ever opened. Constructors don't hit the
network; dummy keys keep this runnable on the keyless CI unit job.
"""
from livekit.agents.tts import FallbackAdapter as TTSFallbackAdapter
from livekit.plugins import cartesia, deepgram

from agent import build_tts


def test_deepgram_only_when_toggled(monkeypatch):
    # Aura alone — NOT the failover adapter, so no per-turn Cartesia 402 handshake.
    monkeypatch.setenv("DEEPGRAM_API_KEY", "test-dummy")
    monkeypatch.setenv("TTS_PROVIDER", "deepgram")
    tts = build_tts()
    assert isinstance(tts, deepgram.TTS)
    assert not isinstance(tts, TTSFallbackAdapter)


def test_default_is_cartesia_aura_failover(monkeypatch):
    # Unset toggle -> Sonic-primary with Aura fallback (the credited-Cartesia path).
    monkeypatch.setenv("DEEPGRAM_API_KEY", "test-dummy")
    monkeypatch.setenv("CARTESIA_API_KEY", "test-dummy")
    monkeypatch.delenv("TTS_PROVIDER", raising=False)
    tts = build_tts()
    assert isinstance(tts, TTSFallbackAdapter)


def test_deepgram_toggle_without_key_falls_back_to_cartesia(monkeypatch):
    # Toggle set but no Deepgram key: must not return a broken Aura or go mute —
    # fall through to Cartesia so the agent still has a voice.
    monkeypatch.delenv("DEEPGRAM_API_KEY", raising=False)
    monkeypatch.setenv("CARTESIA_API_KEY", "test-dummy")
    monkeypatch.setenv("TTS_PROVIDER", "deepgram")
    tts = build_tts()
    assert isinstance(tts, cartesia.TTS)
    assert not isinstance(tts, TTSFallbackAdapter)

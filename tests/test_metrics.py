"""Unit test for the structured metrics sink (item #7).

Pure file I/O — no LLM, no network. Verifies the JSONL records are well-formed
and queryable.
"""
import json

from agent import _MetricsRecorder


def test_metrics_recorder_writes_queryable_jsonl(tmp_path):
    path = tmp_path / "metrics.jsonl"
    rec = _MetricsRecorder(str(path), room="room-abc")
    rec.record("llm", ttft_ms=481.0, tokens_prompt=12, tokens_completion=8)
    rec.record("tts", ttfb_ms=184.0)
    rec.record("turn", e2e_ms=1658.0)

    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 3
    records = [json.loads(ln) for ln in lines]

    # Every record is self-describing: timestamp, room, kind + its fields.
    for r in records:
        assert "ts" in r and r["room"] == "room-abc" and "kind" in r

    by_kind = {r["kind"]: r for r in records}
    assert by_kind["llm"]["ttft_ms"] == 481.0
    assert by_kind["llm"]["tokens_prompt"] == 12
    assert by_kind["tts"]["ttfb_ms"] == 184.0
    assert by_kind["turn"]["e2e_ms"] == 1658.0

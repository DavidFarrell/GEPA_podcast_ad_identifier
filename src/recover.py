"""Recovery pass: catch ads the champion MISSES by anchoring on terminal signals and
expanding BACKWARD to the disguised opening (docs/results.md round 5).

Two modes, both ADDITIVE - they return spans to be unioned with the champion's detections:

- mode "regex": deterministic terminal-anchor scan (anchors.py) -> cluster -> one micro-window
  per cluster (anchor +/-back/forward context) -> model back-expands that single promo. The
  model spends its capacity only on "how far back does this proven ad start?".
- mode "model": the model scans the whole window itself for terminals and back-expands, one
  call per window.

Recovered quotes map to times via a window-local Transcript (same as detector.detect). All
LLM calls route through detector.call_llm, so /tmp/gepa_pause freezes this pass too.
"""
from __future__ import annotations

import json

from anchors import cluster_anchors, find_anchors
from dataset import Window
from detector import call_llm
from transcript import Transcript

BACK_SEC = 90.0      # context before the anchor (where the disguised opening hides)
FWD_SEC = 30.0       # context after the anchor (catch a trailing line / next-unit boundary)

MICRO_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "recovered_ad", "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "reason": {"type": "string"},
                "is_ad": {"type": "boolean"},
                "brand": {"type": "string"},
                "start_quote": {"type": "string"},
                "end_quote": {"type": "string"},
            },
            "required": ["reason", "is_ad", "brand", "start_quote", "end_quote"],
        },
    },
}

SCAN_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "recovered_ads", "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "spans": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "brand": {"type": "string"},
                            "start_quote": {"type": "string"},
                            "end_quote": {"type": "string"},
                        },
                        "required": ["brand", "start_quote", "end_quote"],
                    },
                },
            },
            "required": ["spans"],
        },
    },
}


def _subtranscript(window: Window) -> Transcript:
    return Transcript(window.episode_id, window.sentences)


def _map(sub: Transcript, start_q: str, end_q: str) -> dict | None:
    return (sub.map_span(start_q, end_q, min_sent=0)
            or sub.map_span(start_q, end_q, min_sent=0, max_span_sec=400.0))


def _render_micro(window: Window, anchor_idx: int) -> str:
    """Render the micro-window around an anchor, marking the terminal-signal sentence."""
    a = window.sentences[anchor_idx]
    lines = []
    for s in window.sentences:
        if s.end < a.start - BACK_SEC or s.start > a.end + FWD_SEC:
            continue
        mm, ss = divmod(int(s.start), 60)
        line = f"#{s.idx} [{mm:02d}:{ss:02d}] {s.speaker}: {s.text}"
        if s.idx == a.idx:
            line += "    >>> TERMINAL SIGNAL <<<"
        lines.append(line)
    return "\n".join(lines)


def recover(mode: str, recover_prompt: str, window: Window, model: str) -> list[dict]:
    """Return recovered ad spans (mapped to times) for this window. mode in {regex, model}."""
    if mode == "regex":
        return _recover_regex(recover_prompt, window, model)
    if mode == "model":
        return _recover_model(recover_prompt, window, model)
    raise ValueError(f"unknown recover mode {mode!r}")


def _recover_regex(recover_prompt: str, window: Window, model: str) -> list[dict]:
    clusters = cluster_anchors(window, find_anchors(window))
    if not clusters:
        return []
    sub = _subtranscript(window)
    out = []
    for c in clusters:
        excerpt = _render_micro(window, c["idx"])
        user = (f"EXCERPT ({window.header()}; terminal signal type: {c['signal']}):\n{excerpt}")
        try:
            content, _ = call_llm(recover_prompt, user, model, max_tokens=2000,
                                  schema=MICRO_SCHEMA)
            obj = json.loads(content[content.find("{"):content.rfind("}") + 1])
        except Exception:
            continue
        if not obj.get("is_ad") or not (obj.get("brand") or "").strip():
            continue
        m = _map(sub, obj.get("start_quote", ""), obj.get("end_quote", ""))
        if m is None:
            continue
        out.append({"type": "ad", "subtype": None, "start_s": m["start_s"],
                    "end_s": m["end_s"], "start_quote": obj["start_quote"],
                    "end_quote": obj["end_quote"], "brand": obj["brand"],
                    "via": f"recover-regex:{c['signal']}"})
    return out


def _recover_model(recover_prompt: str, window: Window, model: str) -> list[dict]:
    user = f"TRANSCRIPT WINDOW ({window.header()}):\n{window.text}"
    try:
        content, _ = call_llm(recover_prompt, user, model, max_tokens=3000, schema=SCAN_SCHEMA)
        obj = json.loads(content[content.find("{"):content.rfind("}") + 1])
    except Exception:
        return []
    sub = _subtranscript(window)
    out = []
    for s in obj.get("spans", []):
        if not (s.get("brand") or "").strip():
            continue
        m = _map(sub, s.get("start_quote", ""), s.get("end_quote", ""))
        if m is None:
            continue
        out.append({"type": "ad", "subtype": None, "start_s": m["start_s"],
                    "end_s": m["end_s"], "start_quote": s["start_quote"],
                    "end_quote": s["end_quote"], "brand": s["brand"], "via": "recover-model"})
    return out

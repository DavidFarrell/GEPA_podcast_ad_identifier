"""Second-pass verification: audit each first-pass span with a fresh Gemma call.

The first pass (an aggressive detect prompt) proposes cuts; for each proposed span we
show the model just that span plus ~60s of context either side, with the cut explicitly
marked, and ask for a cut/keep verdict. "keep" drops the span (the first pass was wrong);
a failed verify call fails OPEN (the first-pass cut stands) so transient errors don't
silently change behaviour. All calls go through detector.call_llm, so /tmp/gepa_pause
freezes this pass too.
"""
from __future__ import annotations

import json

from dataset import Window
from detector import call_llm

CONTEXT_SEC = 60.0

VERIFY_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "cut_verdict",
        "strict": True,
        "schema": {
            "type": "object",
            # reason BEFORE verdict: constrained decoding follows property order, so the
            # model articulates its reasoning before committing (v1 had verdict-first and
            # produced reason/verdict contradictions).
            "properties": {
                "reason": {"type": "string"},
                "verdict": {"type": "string", "enum": ["cut", "keep"]},
            },
            "required": ["reason", "verdict"],
        },
    },
}


def render_excerpt(window: Window, span: dict) -> str:
    """The span's sentences between markers, with CONTEXT_SEC of context either side."""
    pre, cut, post = [], [], []
    for s in window.sentences:
        if s.end < span["start_s"] - CONTEXT_SEC or s.start > span["end_s"] + CONTEXT_SEC:
            continue
        mm, ss = divmod(int(s.start), 60)
        line = f"#{s.idx} [{mm:02d}:{ss:02d}] {s.speaker}: {s.text}"
        mid = (s.start + s.end) / 2
        (pre if mid < span["start_s"] else cut if mid <= span["end_s"] else post).append(line)
    parts = []
    if pre:
        parts += ["[...context before...]"] + pre
    parts += [">>> PROPOSED CUT STARTS HERE <<<"] + cut + [">>> PROPOSED CUT ENDS HERE <<<"]
    if post:
        parts += post + ["[...context after...]"]
    return "\n".join(parts)


def apply_verify(verify_prompt: str, window: Window, det: dict, model: str) -> dict:
    """Filter det['pred'] through per-span verdicts. Returns a new det dict."""
    kept, verdicts, seen = [], [], set()
    for span in det["pred"]:
        key = (round(span["start_s"], 1), round(span["end_s"], 1))
        if key in seen:  # first pass sometimes emits duplicates - verify once
            continue
        seen.add(key)
        user = (f"EXCERPT ({window.header()}; first-pass label: {span['type']}):\n"
                f"{render_excerpt(window, span)}")
        try:
            content, latency = call_llm(verify_prompt, user, model,
                                        max_tokens=1500, schema=VERIFY_SCHEMA)
            obj = json.loads(content[content.find("{"):content.rfind("}") + 1])
            verdict = obj["verdict"] if obj.get("verdict") in ("cut", "keep") else "keep"
            reason = str(obj.get("reason", ""))
        except Exception as e:
            verdict, reason, latency = "cut", f"verify failed (fail-open): {e}", 0.0
        verdicts.append({"start_s": span["start_s"], "end_s": span["end_s"],
                         "type": span["type"], "verdict": verdict, "reason": reason,
                         "latency_s": round(latency, 1)})
        if verdict == "cut":
            kept.append(span)
    out = dict(det)
    out["pred"] = kept
    out["verify"] = verdicts
    out["n_dropped_by_verify"] = sum(1 for v in verdicts if v["verdict"] == "keep")
    return out

"""Run the local Gemma detector on a transcript window and map its quotes to times.

LM Studio serves gemma-4-12b-qat at :1234 (OpenAI-compatible). Two instances are loaded,
so callers round-robin across MODELS for concurrency. The qat build is a reasoning model:
the answer lands in `content` (thinking in `reasoning_content`), and it needs a generous
max_tokens or content comes back empty.
"""
from __future__ import annotations

import json
import re
import time

import requests

from dataset import Window
from transcript import Transcript

API = "http://localhost:1234/v1/chat/completions"
MODELS = ["google/gemma-4-12b-qat", "google/gemma-4-12b-qat:2"]
VALID_TYPES = {"ad", "intro", "outro", "housekeeping"}

# Strict schema, mirroring Open Swimcast's locked detector (constrained decoding stops
# the reasoning build from rambling and guarantees parseable JSON).
SPANS_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "faff_spans",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "spans": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "type": {"type": "string",
                                     "enum": ["ad", "intro", "outro", "housekeeping"]},
                            "subtype": {"type": ["string", "null"]},
                            "start_quote": {"type": "string"},
                            "end_quote": {"type": "string"},
                        },
                        "required": ["type", "subtype", "start_quote", "end_quote"],
                    },
                },
            },
            "required": ["spans"],
        },
    },
}


def call_llm(system: str, user: str, model: str, temperature: float = 0.0,
             max_tokens: int = 4000, timeout: int = 900, retries: int = 3) -> tuple[str, float]:
    t = time.time()
    last_err: Exception | None = None
    for attempt in range(retries + 1):
        try:
            r = requests.post(API, json={
                "model": model,
                "messages": [{"role": "system", "content": system},
                             {"role": "user", "content": user}],
                "temperature": temperature,
                "max_tokens": max_tokens,
                "response_format": SPANS_SCHEMA,
            }, timeout=timeout)
            r.raise_for_status()
            msg = r.json()["choices"][0]["message"]
            # reasoning builds may leave content empty and answer in reasoning_content
            content = ((msg.get("content") or "").strip()
                       or (msg.get("reasoning_content") or "").strip())
            return content, time.time() - t
        except Exception as e:
            # 400 = shared KV context momentarily exhausted by concurrent requests;
            # back off and retry. Same for transient network errors.
            last_err = e
            if attempt < retries:
                time.sleep(15 * (attempt + 1))
    raise last_err  # type: ignore[misc]


def parse_spans(content: str) -> tuple[list[dict], str | None]:
    """Extract {"spans":[...]} from the model output. Returns (spans, error)."""
    txt = content.strip()
    txt = re.sub(r"^```(?:json)?\s*|\s*```$", "", txt, flags=re.MULTILINE).strip()
    i, j = txt.find("{"), txt.rfind("}")
    if i == -1 or j <= i:
        return [], "no JSON object found in output"
    try:
        obj = json.loads(txt[i:j + 1])
    except json.JSONDecodeError as e:
        return [], f"invalid JSON: {e}"
    spans = obj.get("spans")
    if not isinstance(spans, list):
        return [], 'JSON has no "spans" list'
    ok = []
    for s in spans:
        if not isinstance(s, dict):
            continue
        typ = str(s.get("type", "")).strip().lower()
        if typ not in VALID_TYPES:
            typ = "ad"  # mislabeled type still counts as a cut; score on time, not type
        ok.append({
            "type": typ,
            "subtype": s.get("subtype"),
            "start_quote": str(s.get("start_quote", "")),
            "end_quote": str(s.get("end_quote", "")),
        })
    return ok, None


def detect(prompt_text: str, window: Window, model: str | None = None) -> dict:
    """Run the candidate prompt on one window. Returns prediction + diagnostics."""
    model = model or MODELS[0]
    user = f"TRANSCRIPT WINDOW ({window.header()}):\n{window.text}"
    try:
        content, latency = call_llm(prompt_text, user, model)
    except Exception as e:
        return {"content": "", "raw_spans": [], "pred": [], "unmapped": [],
                "parse_error": f"LLM call failed: {e}", "latency_s": 0.0}

    raw_spans, parse_error = parse_spans(content)

    # Map quotes -> times within this window only (slice-local Transcript reuses the
    # original Sentence objects, so times/idx stay global).
    sub = Transcript(window.episode_id, window.sentences)
    pred, unmapped = [], []
    cursor = 0
    for s in raw_spans:
        m = (sub.map_span(s["start_quote"], s["end_quote"], min_sent=cursor)
             or sub.map_span(s["start_quote"], s["end_quote"], min_sent=0))
        if m is None:
            unmapped.append(s)
            continue
        cursor = max(cursor, m["end_idx"])
        pred.append({"type": s["type"], "subtype": s.get("subtype"),
                     "start_s": m["start_s"], "end_s": m["end_s"],
                     "start_quote": s["start_quote"], "end_quote": s["end_quote"]})
    pred.sort(key=lambda x: x["start_s"])
    return {"content": content, "raw_spans": raw_spans, "pred": pred,
            "unmapped": unmapped, "parse_error": parse_error,
            "latency_s": round(latency, 1)}


if __name__ == "__main__":
    import sys
    from pathlib import Path
    from dataset import build_windows
    ROOT = Path(__file__).resolve().parent.parent
    prompt = (ROOT / "prompts/seed_faff_v1.txt").read_text()
    eid = sys.argv[1] if len(sys.argv) > 1 else "dtns__do_people_hate_tech"
    w = build_windows(eid)[0]
    print(f"window {w.wid}: {len(w.sentences)} sentences, golden={len(w.golden)} spans")
    out = detect(prompt, w)
    print(f"latency {out['latency_s']}s  parse_error={out['parse_error']}")
    for p in out["pred"]:
        print(f"  pred {p['type']:12s} {p['start_s']:8.1f}-{p['end_s']:8.1f}")
    for u in out["unmapped"]:
        print(f"  UNMAPPED {u['type']}: {u['start_quote'][:60]!r}")

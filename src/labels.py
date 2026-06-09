"""Validate + materialise raw labeller output into a golden label file.

A labelling agent returns spans as {type, subtype, start_quote, end_quote, rationale}.
This module resolves each span's quotes to timestamps via the deterministic mapper, drops
(and reports) any span whose quotes don't map, and writes the golden JSON in schema v1.
"""
from __future__ import annotations

import json
from pathlib import Path

from transcript import Transcript

VALID_TYPES = {"ad", "intro", "outro", "housekeeping"}
VALID_SUBTYPES = {"pre-roll", "mid-roll", "post-roll", None}


def materialise(episode_id: str, show: str, labeled_by: str,
                raw_spans: list[dict], tr: Transcript) -> dict:
    """Return (golden_dict). golden_dict['spans'] are timed + validated;
    rejected spans land in golden_dict['rejected'] with a reason."""
    spans, rejected = [], []
    for s in raw_spans:
        typ = (s.get("type") or "").strip().lower()
        sub = s.get("subtype")
        sub = sub.strip().lower() if isinstance(sub, str) and sub.strip() else None
        sq, eq = s.get("start_quote", ""), s.get("end_quote", "")
        if typ not in VALID_TYPES:
            rejected.append({**s, "reason": f"bad type {typ!r}"}); continue
        if sub not in VALID_SUBTYPES:
            sub = None
        mapped = tr.map_span(sq, eq)
        if mapped is None:
            rejected.append({**s, "reason": "quotes not found in transcript"}); continue
        if mapped["end_s"] <= mapped["start_s"]:
            rejected.append({**s, "reason": "non-positive duration"}); continue
        spans.append({
            "type": typ, "subtype": sub,
            "start_quote": sq, "end_quote": eq,
            "start_s": mapped["start_s"], "end_s": mapped["end_s"],
            "start_turn": mapped["start_turn"], "end_turn": mapped["end_turn"],
            "confidence": mapped["confidence"],
            "rationale": (s.get("rationale") or "").strip(),
        })
    spans.sort(key=lambda x: x["start_s"])
    return {
        "episode_id": episode_id, "show": show, "labeled_by": labeled_by,
        "schema": "v1", "duration_s": round(tr.duration, 1),
        "spans": spans, "rejected": rejected,
        "cut_seconds": round(sum(x["end_s"] - x["start_s"] for x in spans), 1),
    }


def write_golden(golden: dict, out_dir: str | Path) -> Path:
    out = Path(out_dir) / f"{golden['episode_id']}.json"
    out.write_text(json.dumps(golden, indent=2))
    return out


if __name__ == "__main__":
    # Self-test on the one existing transcript with a hand-made HSBC pre-roll span.
    tr = Transcript.load("data/transcripts/news_agents__trump_impotent.json")
    g = materialise(
        "news_agents__trump_impotent", "The News Agents", "self-test",
        [{"type": "ad", "subtype": "pre-roll",
          "start_quote": "The News Agents podcast is brought to you by HSBC UK",
          "end_quote": "opening up a world of opportunity",
          "rationale": "HSBC host-read pre-roll"}],
        tr,
    )
    print(json.dumps(g, indent=2))

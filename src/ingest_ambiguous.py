"""Merge confirmed ambiguous zones into existing golden files.

Input: the array returned by scripts/ambiguous_workflow.js: [{id, zones:[{start_quote,
end_quote, reason}]}]. For each episode, map the zones to times, drop any time already
inside an existing golden faff span, replace any previous "ambiguous" spans, and rewrite
the golden file. cut_seconds continues to count real faff only.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from labels import merge_intervals
from transcript import Transcript

ROOT = Path(__file__).resolve().parent.parent
GOLDEN_DIRS = [ROOT / "data/golden", ROOT / "data/golden_pilot", ROOT / "data/golden_test",
               ROOT / "data/golden_expand"]


def golden_path(eid: str) -> Path:
    for d in GOLDEN_DIRS:
        p = d / f"{eid}.json"
        if p.exists():
            return p
    raise FileNotFoundError(eid)


def main(run_json: str):
    runs = json.loads(Path(run_json).read_text())
    n_eps = n_zones = 0
    for r in runs:
        eid, zones = r["id"], r.get("zones", [])
        gp = golden_path(eid)
        golden = json.loads(gp.read_text())
        golden["spans"] = [s for s in golden["spans"] if s["type"] != "ambiguous"]
        if zones:
            tr = Transcript.load(ROOT / f"data/transcripts/{eid}.json")
            faff_iv = merge_intervals([(s["start_s"], s["end_s"]) for s in golden["spans"]])
            cursor, added = 0, []
            for z in zones:
                m = (tr.map_span(z["start_quote"], z["end_quote"], min_sent=cursor)
                     or tr.map_span(z["start_quote"], z["end_quote"], min_sent=0,
                                    max_span_sec=600.0))
                if m is None or m["end_s"] - m["start_s"] < 10.0:
                    continue
                # skip zones substantially inside existing faff spans
                ov = sum(max(0.0, min(m["end_s"], b) - max(m["start_s"], a))
                         for a, b in faff_iv)
                if ov > 0.5 * (m["end_s"] - m["start_s"]):
                    continue
                cursor = m["end_idx"]
                added.append({"type": "ambiguous", "subtype": None,
                              "start_quote": z["start_quote"], "end_quote": z["end_quote"],
                              "start_s": m["start_s"], "end_s": m["end_s"],
                              "start_idx": m["start_idx"], "end_idx": m["end_idx"],
                              "confidence": 1.0, "rationale": z.get("reason", "")})
            golden["spans"] = sorted(golden["spans"] + added, key=lambda s: s["start_s"])
            if added:
                n_eps += 1
                n_zones += len(added)
                print(f"{eid}: +{len(added)} ambiguous zone(s) "
                      f"({sum(s['end_s']-s['start_s'] for s in added):.0f}s)")
        gp.write_text(json.dumps(golden, indent=2))
    print(f"\n{n_zones} ambiguous zones added across {n_eps} episodes "
          f"({len(runs)} scanned)")


if __name__ == "__main__":
    main(sys.argv[1])

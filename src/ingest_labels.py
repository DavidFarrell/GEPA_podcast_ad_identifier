"""Ingest a labelling-workflow result JSON into validated golden files + agreement stats.

Input JSON = the array returned by scripts/label_workflow.js:
  [{ "id", "sonnet": {"spans":[...]}, "opus": {"spans":[...], "notes", "agreement"} }, ...]

Writes:
  data/golden/<id>.json          (Opus authoritative - the golden truth)
  data/golden/sonnet/<id>.json   (Sonnet pass - kept for audit)
and prints a per-episode agreement table (time-IoU of the two cut-sets).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from labels import materialise, merge_intervals, write_golden
from transcript import Transcript


def cut_intervals(golden: dict) -> list[tuple[float, float]]:
    return merge_intervals([(s["start_s"], s["end_s"]) for s in golden["spans"]])


def total(iv: list[tuple[float, float]]) -> float:
    return sum(b - a for a, b in iv)


def overlap(a: list[tuple[float, float]], b: list[tuple[float, float]]) -> float:
    """Total overlapping seconds between two (already merged) interval sets."""
    o = 0.0
    for s1, e1 in a:
        for s2, e2 in b:
            o += max(0.0, min(e1, e2) - max(s1, s2))
    return o


def iou(a: list[tuple[float, float]], b: list[tuple[float, float]]) -> float:
    inter = overlap(a, b)
    union = total(a) + total(b) - inter
    return inter / union if union > 0 else 1.0


def main(run_json: str, repo: str = ".", gold_dirname: str = "data/golden",
         manifest_path: str = "manifests/pilot.json"):
    repo = Path(repo)
    tx_dir = repo / "data/transcripts"
    gold_dir = repo / gold_dirname
    snt_dir = gold_dir / "sonnet"
    gold_dir.mkdir(parents=True, exist_ok=True)
    snt_dir.mkdir(parents=True, exist_ok=True)

    runs = json.loads(Path(run_json).read_text())
    manifest = {e["id"]: e for e in json.loads((repo / manifest_path).read_text())["episodes"]}

    print(f"{'episode':38} {'snt':>4} {'opus':>4} {'IoU':>6} {'cut%':>6}  agree")
    print("-" * 78)
    rows = []
    for r in runs:
        eid = r["id"]
        tf = tx_dir / f"{eid}.json"
        if not tf.exists():
            print(f"{eid:38} (no transcript, skipped)"); continue
        tr = Transcript.load(tf)
        show = manifest.get(eid, {}).get("show", "")

        g_snt = materialise(eid, show, "claude-sonnet-4-6", r.get("sonnet", {}).get("spans", []), tr)
        g_opus = materialise(eid, show, "claude-opus-4-8", r.get("opus", {}).get("spans", []), tr)
        g_opus["adjudication_notes"] = r.get("opus", {}).get("notes", "")
        g_opus["agreement_self"] = r.get("opus", {}).get("agreement", "")

        write_golden(g_snt, snt_dir)
        write_golden(g_opus, gold_dir)

        i = iou(cut_intervals(g_snt), cut_intervals(g_opus))
        cutpct = 100 * g_opus["cut_seconds"] / (g_opus["duration_s"] or 1)
        rows.append((eid, i))
        print(f"{eid:38} {len(g_snt['spans']):>4} {len(g_opus['spans']):>4} "
              f"{i:>6.2f} {cutpct:>5.1f}%  {g_opus.get('agreement_self','')}")

    if rows:
        avg = sum(i for _, i in rows) / len(rows)
        print("-" * 78)
        print(f"mean Sonnet/Opus cut-IoU: {avg:.2f}  (1.0 = identical cuts; low = disagreement to inspect)")


if __name__ == "__main__":
    # usage: ingest_labels.py run.json [repo] [gold_dirname] [manifest_path]
    main(sys.argv[1],
         sys.argv[2] if len(sys.argv) > 2 else ".",
         sys.argv[3] if len(sys.argv) > 3 else "data/golden",
         sys.argv[4] if len(sys.argv) > 4 else "manifests/pilot.json")

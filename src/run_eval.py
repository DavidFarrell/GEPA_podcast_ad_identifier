"""Evaluate a prompt file over a split. Writes a results JSON and prints a table.

Usage:
    uv run python src/run_eval.py --prompt prompts/seed_faff_v1.txt --split val \
        --out out/baseline_val.json [--workers 4]
"""
from __future__ import annotations

import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from dataset import load_split
from detector import MODELS, detect
from metric import intersect, merge, score_window, subtract, total, DILATE

ROOT = Path(__file__).resolve().parent.parent


def evaluate_prompt(prompt: str, windows, workers: int = 4) -> list[dict]:
    def run(i_w):
        i, w = i_w
        det = detect(prompt, w, MODELS[i % len(MODELS)])
        score, feedback = score_window(w, det)
        gold = merge([(g["start_s"], g["end_s"]) for g in w.golden])
        pred = merge([(p["start_s"], p["end_s"]) for p in det["pred"]])
        gold_dilated = merge([(a - DILATE, b + DILATE) for a, b in gold])
        return {
            "wid": w.wid, "episode_id": w.episode_id, "t0": w.t0, "t1": w.t1,
            "score": score, "feedback": feedback,
            "gold_sec": round(total(gold), 1),
            "hit_sec": round(total(intersect(gold, pred)), 1),
            "fp_sec": round(total(subtract(pred, gold_dilated)), 1),
            "pred": det["pred"], "golden": w.golden,
            "parse_error": det["parse_error"],
            "n_unmapped": len(det["unmapped"]),
            "latency_s": det["latency_s"],
        }
    with ThreadPoolExecutor(max_workers=workers) as ex:
        return list(ex.map(run, enumerate(windows)))


def summarise(rows: list[dict]) -> dict:
    eps: dict[str, dict] = {}
    for r in rows:
        e = eps.setdefault(r["episode_id"], {"gold": 0, "hit": 0, "fp": 0, "scores": []})
        e["gold"] += r["gold_sec"]; e["hit"] += r["hit_sec"]; e["fp"] += r["fp_sec"]
        e["scores"].append(r["score"])
    g, h, f = (sum(r["gold_sec"] for r in rows), sum(r["hit_sec"] for r in rows),
               sum(r["fp_sec"] for r in rows))
    return {
        "mean_window_score": round(sum(r["score"] for r in rows) / len(rows), 4),
        "micro_recall": round(h / g, 4) if g else None,
        "total_gold_sec": round(g, 1), "total_hit_sec": round(h, 1),
        "total_fp_sec": round(f, 1),
        "windows": len(rows),
        "parse_errors": sum(1 for r in rows if r["parse_error"]),
        "per_episode": {k: {"recall": round(v["hit"] / v["gold"], 3) if v["gold"] else None,
                            "fp_sec": round(v["fp"], 1),
                            "mean_score": round(sum(v["scores"]) / len(v["scores"]), 3)}
                        for k, v in sorted(eps.items())},
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--split", default="val", choices=["train", "val", "val2", "test"])
    ap.add_argument("--out", required=True)
    ap.add_argument("--workers", type=int, default=4)
    args = ap.parse_args()

    prompt = Path(args.prompt).read_text()
    windows = load_split(args.split)
    print(f"{args.split}: {len(windows)} windows; running with {args.workers} workers...")
    t = time.time()
    rows = evaluate_prompt(prompt, windows, args.workers)
    wall = time.time() - t
    summary = summarise(rows)
    out = {"prompt_file": args.prompt, "split": args.split, "wall_s": round(wall, 1),
           "summary": summary, "rows": rows}
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out, indent=1))

    s = summary
    print(f"\n=== {args.split} | {args.prompt} | wall {wall:.0f}s ===")
    print(f"mean window score {s['mean_window_score']}   micro recall {s['micro_recall']}"
          f"   FP {s['total_fp_sec']}s   parse errors {s['parse_errors']}/{s['windows']}")
    for eid, e in s["per_episode"].items():
        print(f"  {eid:42s} recall={e['recall'] if e['recall'] is not None else '  - '}"
              f"  fp={e['fp_sec']:7.1f}s  score={e['mean_score']:.3f}")
    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()

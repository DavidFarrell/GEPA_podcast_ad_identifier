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
from verify import apply_verify
from recover import recover

ROOT = Path(__file__).resolve().parent.parent


def _union_spans(det: dict, extra: list[dict]) -> dict:
    """Merge recovered spans into det['pred'] (overlap/adjacent merge); track recovery count."""
    spans = sorted(det["pred"] + extra, key=lambda s: s["start_s"])
    merged: list[dict] = []
    for s in spans:
        if merged and s["start_s"] <= merged[-1]["end_s"] + 1.0:
            if s["end_s"] > merged[-1]["end_s"]:
                merged[-1]["end_s"] = s["end_s"]
                merged[-1]["end_quote"] = s.get("end_quote", merged[-1].get("end_quote"))
        else:
            merged.append(dict(s))
    out = dict(det)
    out["pred"] = merged
    out["recovered"] = extra
    out["n_recovered"] = len(extra)
    return out


def union_dets(det1: dict, det2: dict) -> dict:
    """Union two first passes: overlapping/adjacent pred spans merge into one."""
    spans = sorted(det1["pred"] + det2["pred"], key=lambda s: s["start_s"])
    merged: list[dict] = []
    for s in spans:
        if merged and s["start_s"] <= merged[-1]["end_s"] + 1.0:
            if s["end_s"] > merged[-1]["end_s"]:
                merged[-1]["end_s"] = s["end_s"]
                merged[-1]["end_quote"] = s["end_quote"]
        else:
            merged.append(dict(s))
    out = dict(det1)
    out["pred"] = merged
    errs = [e for e in (det1["parse_error"], det2["parse_error"]) if e]
    out["parse_error"] = "; ".join(errs) if errs else None
    out["unmapped"] = det1["unmapped"] + det2["unmapped"]
    out["latency_s"] = round(det1["latency_s"] + det2["latency_s"], 1)
    return out


def evaluate_prompt(prompt: str, windows, workers: int = 4, mode: str = "v1",
                    verify_prompt: str | None = None,
                    prompt2: str | None = None,
                    recover_mode: str | None = None,
                    recover_prompt: str | None = None) -> list[dict]:
    def run(i_w):
        i, w = i_w
        model = MODELS[i % len(MODELS)]
        det = detect(prompt, w, model)
        if prompt2:
            det = union_dets(det, detect(prompt2, w, model))
        if recover_mode:
            det = _union_spans(det, recover(recover_mode, recover_prompt, w, model))
        if verify_prompt:
            det = apply_verify(verify_prompt, w, det, model)
        score, feedback = score_window(w, det, mode=mode)
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
            "verify": det.get("verify"),
            "n_dropped_by_verify": det.get("n_dropped_by_verify"),
            "recovered": det.get("recovered"),
            "n_recovered": det.get("n_recovered"),
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
        "spans_dropped_by_verify": sum(r.get("n_dropped_by_verify") or 0 for r in rows),
        "spans_recovered": sum(r.get("n_recovered") or 0 for r in rows),
        "per_episode": {k: {"recall": round(v["hit"] / v["gold"], 3) if v["gold"] else None,
                            "fp_sec": round(v["fp"], 1),
                            "mean_score": round(sum(v["scores"]) / len(v["scores"]), 3)}
                        for k, v in sorted(eps.items())},
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--split", default="val", choices=["train", "val", "val2", "val3", "test", "test_fresh5"])
    ap.add_argument("--out", required=True)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--window-min", type=float, default=30.0)
    ap.add_argument("--overlap-min", type=float, default=3.0)
    ap.add_argument("--metric", default="v1", choices=["v1", "weighted", "ads"])
    ap.add_argument("--verify-prompt", default=None,
                    help="optional second-pass verify prompt file; spans judged 'keep' are dropped")
    ap.add_argument("--prompt2", default=None,
                    help="optional second detect prompt; its spans are unioned with --prompt's before verify")
    ap.add_argument("--recover", dest="recover_mode", default=None, choices=["regex", "model"],
                    help="additive recovery pass: anchor on terminal signals, expand backward")
    ap.add_argument("--recover-prompt", default=None, help="prompt file for the recovery pass")
    args = ap.parse_args()

    prompt = Path(args.prompt).read_text()
    verify_prompt = Path(args.verify_prompt).read_text() if args.verify_prompt else None
    prompt2 = Path(args.prompt2).read_text() if args.prompt2 else None
    recover_prompt = Path(args.recover_prompt).read_text() if args.recover_prompt else None
    windows = load_split(args.split, window_sec=args.window_min * 60,
                         step_sec=(args.window_min - args.overlap_min) * 60)
    print(f"{args.split}: {len(windows)} windows; running with {args.workers} workers...")
    t = time.time()
    rows = evaluate_prompt(prompt, windows, args.workers, mode=args.metric,
                           verify_prompt=verify_prompt, prompt2=prompt2,
                           recover_mode=args.recover_mode, recover_prompt=recover_prompt)
    wall = time.time() - t
    summary = summarise(rows)
    out = {"prompt_file": args.prompt, "prompt2_file": args.prompt2,
           "verify_prompt_file": args.verify_prompt,
           "recover_mode": args.recover_mode, "recover_prompt_file": args.recover_prompt,
           "split": args.split, "metric": args.metric,
           "window_min": args.window_min, "overlap_min": args.overlap_min,
           "wall_s": round(wall, 1), "summary": summary, "rows": rows}
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(out, indent=1))

    s = summary
    print(f"\n=== {args.split} | {args.prompt} | wall {wall:.0f}s ===")
    print(f"mean window score {s['mean_window_score']}   micro recall {s['micro_recall']}"
          f"   FP {s['total_fp_sec']}s   parse errors {s['parse_errors']}/{s['windows']}"
          f"   verify-dropped {s['spans_dropped_by_verify']}   recovered {s['spans_recovered']}")
    for eid, e in s["per_episode"].items():
        print(f"  {eid:42s} recall={e['recall'] if e['recall'] is not None else '  - '}"
              f"  fp={e['fp_sec']:7.1f}s  score={e['mean_score']:.3f}")
    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()

"""GEPA optimisation entrypoint.

- task LM: gemma-4-12b-qat via LM Studio (executed inside FaffAdapter, 2 instances, 4 workers)
- reflection LM: Claude Opus via the `claude` CLI (subscription-billed, no API key needed)
- candidate: a single text component, "detector_prompt"

Usage:
    uv run python src/gepa_opt.py --budget 300 --run-dir out/gepa_run1
Resume by re-running with the same --run-dir.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import gepa
from gepa.core.adapter import EvaluationBatch, GEPAAdapter

from dataset import Window, load_split
from detector import MODELS, detect
from metric import score_window

ROOT = Path(__file__).resolve().parent.parent


def _condensed_input(w: Window, max_head_lines: int = 30) -> str:
    """Window descriptor for the reflection LM: header + opening lines (where pre-rolls
    live) - the feedback text carries excerpts for everything else."""
    lines = w.text.split("\n")
    head = "\n".join(lines[:max_head_lines])
    more = f"\n... ({len(lines) - max_head_lines} more lines)" if len(lines) > max_head_lines else ""
    return f"{w.header()}\nOPENING LINES:\n{head}{more}"


class FaffAdapter(GEPAAdapter):
    def __init__(self, workers: int = 4, mode: str = "v1"):
        self.workers = workers
        self.mode = mode

    def evaluate(self, batch: list[Window], candidate: dict[str, str],
                 capture_traces: bool = False) -> EvaluationBatch:
        prompt = candidate["detector_prompt"]

        def run(i_w):
            i, w = i_w
            det = detect(prompt, w, MODELS[i % len(MODELS)])
            score, feedback = score_window(w, det, mode=self.mode)
            return det, score, feedback

        with ThreadPoolExecutor(max_workers=self.workers) as ex:
            results = list(ex.map(run, enumerate(batch)))

        outputs = [{"wid": w.wid, "pred": det["pred"], "parse_error": det["parse_error"]}
                   for w, (det, _, _) in zip(batch, results)]
        scores = [s for _, s, _ in results]
        trajectories = None
        if capture_traces:
            trajectories = [{
                "data": {"input": _condensed_input(w)},
                "full_assistant_response": det["content"][-2500:],
                "feedback": fb,
            } for w, (det, _, fb) in zip(batch, results)]
        return EvaluationBatch(outputs=outputs, scores=scores, trajectories=trajectories)

    def make_reflective_dataset(self, candidate, eval_batch, components_to_update):
        comp = components_to_update[0]
        items = [{
            "Inputs": t["data"]["input"],
            "Generated Outputs": t["full_assistant_response"],
            "Feedback": t["feedback"],
        } for t in (eval_batch.trajectories or [])]
        if not items:
            raise Exception("no trajectories to reflect on")
        return {comp: items}


def claude_reflect(prompt) -> str:
    """Reflection LM: Claude Opus via the CLI (print mode, no tools)."""
    if isinstance(prompt, list):  # messages form
        prompt = "\n\n".join(m.get("content", "") for m in prompt)
    p = subprocess.run(
        ["claude", "--model", "claude-opus-4-8", "-p"],
        input=prompt, capture_output=True, text=True, timeout=1200,
    )
    out = p.stdout.strip()
    if not out:
        raise RuntimeError(f"claude reflection returned empty (stderr: {p.stderr[-500:]})")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--budget", type=int, default=300)
    ap.add_argument("--run-dir", default="out/gepa_run1")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--seed-prompt", default="prompts/seed_faff_v1.txt")
    ap.add_argument("--minibatch", type=int, default=3)
    ap.add_argument("--val-split", default="val")
    ap.add_argument("--metric", default="v1", choices=["v1", "weighted", "ads"])
    ap.add_argument("--window-min", type=float, default=30.0)
    ap.add_argument("--overlap-min", type=float, default=3.0)
    args = ap.parse_args()

    wsec, ssec = args.window_min * 60, (args.window_min - args.overlap_min) * 60
    seed = {"detector_prompt": (ROOT / args.seed_prompt).read_text()}
    trainset = load_split("train", window_sec=wsec, step_sec=ssec)
    valset = load_split(args.val_split, window_sec=wsec, step_sec=ssec)
    print(f"train {len(trainset)} windows / val {len(valset)} windows; "
          f"budget {args.budget} metric calls")

    t = time.time()
    result = gepa.optimize(
        seed_candidate=seed,
        trainset=trainset,
        valset=valset,
        adapter=FaffAdapter(workers=args.workers, mode=args.metric),
        reflection_lm=claude_reflect,
        reflection_minibatch_size=args.minibatch,
        max_metric_calls=args.budget,
        run_dir=str(ROOT / args.run_dir),
        display_progress_bar=True,
        seed=0,
        raise_on_exception=False,
    )
    wall = time.time() - t

    run_name = Path(args.run_dir).name
    best = result.best_candidate["detector_prompt"]
    (ROOT / f"prompts/{run_name}_best.txt").write_text(best)
    summary = {
        "wall_s": round(wall, 1),
        "budget": args.budget,
        "val_split": args.val_split,
        "num_candidates": len(result.candidates),
        "val_aggregate_scores": result.val_aggregate_scores,
        "best_idx": result.best_idx,
        "best_val_score": result.val_aggregate_scores[result.best_idx],
        "seed_val_score": result.val_aggregate_scores[0],
    }
    (ROOT / f"out/{run_name}_summary.json").write_text(json.dumps(summary, indent=1))
    print(json.dumps(summary, indent=1))
    print("\nBest prompt written to prompts/gepa_best.txt")


if __name__ == "__main__":
    main()

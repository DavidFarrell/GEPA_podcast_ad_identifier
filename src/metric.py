"""Score one window's prediction against golden, with textual feedback for GEPA.

The score encodes the cardinal rule: cutting real content (a false positive) is far worse
than missing faff. score = recall * 0.5^(fp_seconds / 15) - i.e. every 15s of wrongly-cut
content halves the score, while zero-FP predictions score pure recall. Windows with no
golden faff score 1.0 when the model correctly stays silent.

Boundary slop: golden intervals are dilated by ±7.5s before counting false positives, so
being a sentence off at an ad boundary is not punished as a content cut.
"""
from __future__ import annotations

from dataset import Window
from transcript import Sentence

DILATE = 7.5          # boundary tolerance (s) before predicted time counts as FP
FP_HALF_LIFE = 15.0   # this many FP seconds halves the score
OK_COVERAGE = 0.90    # golden span covered at least this much counts as found

Interval = tuple[float, float]


def merge(iv: list[Interval]) -> list[Interval]:
    out: list[list[float]] = []
    for a, b in sorted(iv):
        if out and a <= out[-1][1]:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return [(a, b) for a, b in out]


def total(iv: list[Interval]) -> float:
    return sum(b - a for a, b in iv)


def intersect(A: list[Interval], B: list[Interval]) -> list[Interval]:
    out, i, j = [], 0, 0
    while i < len(A) and j < len(B):
        a, b = max(A[i][0], B[j][0]), min(A[i][1], B[j][1])
        if b > a:
            out.append((a, b))
        if A[i][1] < B[j][1]:
            i += 1
        else:
            j += 1
    return out


def subtract(A: list[Interval], B: list[Interval]) -> list[Interval]:
    """A minus B (both merged)."""
    out = []
    for a, b in A:
        cur = a
        for c, d in B:
            if d <= cur or c >= b:
                continue
            if c > cur:
                out.append((cur, c))
            cur = max(cur, d)
            if cur >= b:
                break
        if cur < b:
            out.append((cur, b))
    return out


def _mmss(t: float) -> str:
    m, s = divmod(int(t), 60)
    return f"{m:02d}:{s:02d}"


def _excerpt(sentences: list[Sentence], a: float, b: float, max_words: int = 30) -> str:
    words: list[str] = []
    for s in sentences:
        if s.end < a or s.start > b:
            continue
        words.extend(s.text.split())
        if len(words) > max_words:
            break
    if len(words) > max_words:
        return " ".join(words[:max_words]) + " ..."
    return " ".join(words)


def score_window(window: Window, det: dict) -> tuple[float, str]:
    """Returns (score in [0,1], feedback text for the reflection LM)."""
    gold = merge([(g["start_s"], g["end_s"]) for g in window.golden])
    pred = merge([(p["start_s"], p["end_s"]) for p in det["pred"]])
    gold_sec = total(gold)
    fb: list[str] = [f"WINDOW {window.header()}: {len(window.golden)} golden faff span(s) "
                     f"totalling {gold_sec:.0f}s. You predicted {len(det['pred'])} span(s) "
                     f"totalling {total(pred):.0f}s."]

    if det["parse_error"]:
        fb.append(f"FATAL: your output could not be used - {det['parse_error']}. "
                  f"You MUST return strict JSON {{\"spans\": [...]}} and nothing else. "
                  f"Raw output started: {det['content'][:200]!r}")
        return 0.0, "\n".join(fb)

    for u in det["unmapped"]:
        fb.append(f"DISCARDED span (type={u['type']}): its quotes were not found verbatim "
                  f"in the window. start_quote={u['start_quote'][:80]!r} "
                  f"end_quote={u['end_quote'][:80]!r}. Quotes must be copied EXACTLY from "
                  f"the transcript text, full sentences, no paraphrasing.")

    # recall over golden
    recall = None
    if gold_sec > 0:
        recall = total(intersect(gold, pred)) / gold_sec
    for g in window.golden:
        gi = [(g["start_s"], g["end_s"])]
        cov_iv = intersect(gi, pred)
        cov = total(cov_iv) / (g["end_s"] - g["start_s"])
        tag = f"{g['type']}" + (f"/{g['subtype']}" if g.get("subtype") else "")
        loc = f"[{_mmss(g['start_s'])}-{_mmss(g['end_s'])}]"
        if cov >= OK_COVERAGE:
            fb.append(f"FOUND {tag} {loc} (coverage {cov:.0%}).")
        elif cov == 0:
            fb.append(f"MISSED {tag} {loc} ({g['end_s']-g['start_s']:.0f}s) entirely. "
                      f"It reads: \"{_excerpt(window.sentences, g['start_s'], g['end_s'])}\"")
        else:
            missed = subtract(gi, pred)
            parts = "; ".join(
                f"[{_mmss(a)}-{_mmss(b)}] \"{_excerpt(window.sentences, a, b, 18)}\""
                for a, b in missed if b - a > 3)
            fb.append(f"PARTIAL {tag} {loc}: only {cov:.0%} covered. Missed part(s): {parts}")

    # false positives: predicted time outside dilated golden
    gold_dilated = merge([(a - DILATE, b + DILATE) for a, b in gold])
    fp_iv = [(a, b) for a, b in subtract(pred, gold_dilated) if b - a > 1.0]
    fp_sec = total(fp_iv)
    for a, b in fp_iv:
        fb.append(f"FALSE POSITIVE [{_mmss(a)}-{_mmss(b)}] ({b-a:.0f}s): you marked real "
                  f"CONTENT as faff - this is the cardinal sin, far worse than missing an "
                  f"ad. The content you wrongly cut: "
                  f"\"{_excerpt(window.sentences, a, b)}\"")

    gate = 0.5 ** (fp_sec / FP_HALF_LIFE)
    base = recall if recall is not None else 1.0
    score = max(0.0, min(1.0, base * gate))
    if recall is None and not fp_iv:
        fb.append("Correct: this window has no faff and you cut nothing (or only "
                  "boundary slop).")
    fb.append(f"SCORE {score:.3f}  (recall={'-' if recall is None else f'{recall:.2f}'}, "
              f"false_positive_sec={fp_sec:.0f})")
    return score, "\n".join(fb)

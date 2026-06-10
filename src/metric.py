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


def score_window(window: Window, det: dict, mode: str = "v1") -> tuple[float, str]:
    """Returns (score in [0,1], feedback text for the reflection LM).

    mode:
      "v1"       - recall over ALL golden faff time (original metric)
      "weighted" - 0.7 * ad recall + 0.3 * other-faff recall (ads are the product)
      "ads"      - ad recall only; other faff types ignored for recall
    All modes: golden "ambiguous" zones (plugs-style, policy-disputed) count neither
    as recall targets nor as false positives - cut or keep both fine. Predictions
    overlapping ANY golden faff are never FPs.
    """
    ambiguous = merge([(g["start_s"], g["end_s"]) for g in window.golden
                       if g["type"] == "ambiguous"])
    scored_golden = [g for g in window.golden if g["type"] != "ambiguous"]
    gold = merge([(g["start_s"], g["end_s"]) for g in scored_golden])
    gold_ads = merge([(g["start_s"], g["end_s"]) for g in scored_golden if g["type"] == "ad"])
    gold_other = merge([(g["start_s"], g["end_s"]) for g in scored_golden if g["type"] != "ad"])
    pred = merge([(p["start_s"], p["end_s"]) for p in det["pred"]])
    gold_sec = total(gold)
    window_golden = scored_golden  # feedback below iterates the scored spans only
    fb: list[str] = [f"WINDOW {window.header()}: {len(window_golden)} golden faff span(s) "
                     f"totalling {gold_sec:.0f}s. You predicted {len(det['pred'])} span(s) "
                     f"totalling {total(pred):.0f}s."]
    if mode in ("weighted", "ads"):
        fb.append("PRIORITY: advertisements are what this detector ships - finding every "
                  "ad span completely matters most. " +
                  ("Other faff types are NOT scored here." if mode == "ads" else
                   "Other faff types count, but far less than ads."))

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

    # recall, by mode
    recall = total(intersect(gold, pred)) / gold_sec if gold_sec > 0 else None
    ad_recall = (total(intersect(gold_ads, pred)) / total(gold_ads)) if gold_ads else None
    other_recall = (total(intersect(gold_other, pred)) / total(gold_other)) if gold_other else None
    spans_for_feedback = (window_golden if mode != "ads"
                          else [g for g in window_golden if g["type"] == "ad"])
    for g in spans_for_feedback:
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

    # false positives: predicted time outside dilated golden (ALL faff types count as
    # legitimate cuts here regardless of mode) and outside ambiguous zones
    all_gold_full = merge([(g["start_s"], g["end_s"]) for g in window.golden])
    gold_dilated = merge([(a - DILATE, b + DILATE) for a, b in all_gold_full])
    fp_iv = [(a, b) for a, b in subtract(pred, gold_dilated) if b - a > 1.0]
    fp_sec = total(fp_iv)
    for a, b in fp_iv:
        fb.append(f"FALSE POSITIVE [{_mmss(a)}-{_mmss(b)}] ({b-a:.0f}s): you marked real "
                  f"CONTENT as faff - this is the cardinal sin, far worse than missing an "
                  f"ad. The content you wrongly cut: "
                  f"\"{_excerpt(window.sentences, a, b)}\"")

    gate = 0.5 ** (fp_sec / FP_HALF_LIFE)
    if mode == "ads":
        base = ad_recall if ad_recall is not None else 1.0
    elif mode == "weighted":
        parts = [(0.7, ad_recall), (0.3, other_recall)]
        live = [(w, r) for w, r in parts if r is not None]
        base = sum(w * r for w, r in live) / sum(w for w, _ in live) if live else 1.0
    else:
        base = recall if recall is not None else 1.0
    score = max(0.0, min(1.0, base * gate))
    if base == 1.0 and recall is None and not fp_iv:
        fb.append("Correct: this window has no scored faff and you cut nothing (or only "
                  "boundary slop / ambiguous zones).")
    fb.append(f"SCORE {score:.3f}  (mode={mode}, "
              f"ad_recall={'-' if ad_recall is None else f'{ad_recall:.2f}'}, "
              f"other_recall={'-' if other_recall is None else f'{other_recall:.2f}'}, "
              f"false_positive_sec={fp_sec:.0f})")
    return score, "\n".join(fb)

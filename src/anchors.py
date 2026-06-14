"""Deterministic terminal-anchor scanner for the recovery pass.

The miss profile (docs/results.md round 4): every ad the champion MISSES opens disguised
as content (rhetorical hook, sketch, story) but ENDS on an unambiguous promotional signal -
a URL, promo code, "terms apply", "% off", a sponsor tagline, a giveaway disclaimer. This
module finds those terminal signals with conservative regex so the model can spend its
capacity on the hard part (how far backward does the proven ad start?) rather than noticing
every URL in a 30-minute window.

Precision over recall: a missed anchor just means we don't recover that ad (no worse than
today); a false anchor only costs one model call, which the back-expansion prompt rejects
via its "name the promoted brand" guard. We still keep the set tight.
"""
from __future__ import annotations

import re

from dataset import Window

# Each pattern is (signal_name, compiled regex). Case-insensitive, conservative.
_PATTERNS = [
    ("url",        re.compile(r"\b[\w-]+\.(?:com|org|net|io|fm|co|gov|edu)\b(?:/\S*)?", re.I)),
    ("spoken_url", re.compile(r"\bdot\s+(?:com|org|net|io|co)\b", re.I)),
    ("promo_code", re.compile(r"\b(?:use\s+(?:promo\s+|discount\s+)?code|promo\s+code|coupon\s+code|discount\s+code)\b", re.I)),
    ("percent_off", re.compile(r"\b\d{1,2}\s?(?:%|percent)\s?off\b", re.I)),
    ("offer",      re.compile(r"\b(?:free\s+trial|free\s+shipping|money[- ]back\s+guarantee|first\s+month\s+free)\b", re.I)),
    ("terms",      re.compile(r"\b(?:terms\s+(?:and\s+conditions\s+)?apply|subject\s+to\s+eligibility|no\s+purchase\s+necessary|see\s+(?:show\s+notes|details)\b)", re.I)),
    ("sponsor",    re.compile(r"\b(?:brought\s+to\s+you\s+by|sponsored\s+by|this\s+episode\s+is\s+sponsored|support\s+(?:for\s+this\s+(?:show|podcast|episode)\s+)?comes\s+from|paid\s+partnership)\b", re.I)),
    ("giveaway",   re.compile(r"\b(?:giveaway|sweepstakes|enter\s+to\s+win|official\s+rules|win\s+a\b)", re.I)),
    ("podcast_xpromo", re.compile(r"\b(?:wherever\s+you\s+(?:get|listen\s+to)\s+(?:your\s+)?podcasts|listen\s+(?:to\s+\w+\s+)?(?:on|wherever)\b.{0,40}\bpodcast|new\s+episodes?\s+(?:every|drop|out)\b)", re.I)),
    ("app_cta",    re.compile(r"\b(?:download\s+the\b.{0,30}\bapp|in\s+the\s+app\s+store|on\s+google\s+play|get\s+the\s+app)\b", re.I)),
    ("signup_cta", re.compile(r"\b(?:sign\s+up\s+(?:now|today|at)|subscribe\s+at|visit\b.{0,30}\bto\s+(?:sign\s+up|get\s+started|learn\s+more)|get\s+started\s+(?:at|today))\b", re.I)),
]


def find_anchors(window: Window) -> list[dict]:
    """Return terminal-anchor hits in the window: [{idx, signal, quote, start_s, end_s}].

    `idx` is the position WITHIN window.sentences. Multiple hits in one sentence collapse to
    one (first signal wins by pattern order). Hits are sorted by sentence position."""
    hits: list[dict] = []
    for i, s in enumerate(window.sentences):
        for name, pat in _PATTERNS:
            if pat.search(s.text):
                hits.append({"idx": i, "signal": name, "quote": s.text,
                             "start_s": s.start, "end_s": s.end})
                break  # one anchor per sentence
    return hits


def cluster_anchors(window: Window, anchors: list[dict], gap_sec: float = 25.0) -> list[dict]:
    """Merge anchors within gap_sec into one cluster (a stacked promo or one long spot fires
    several terminal signals). Each cluster keeps its LAST anchor (the true terminal) and the
    list of signals seen, so one micro-window/back-expansion call covers it."""
    if not anchors:
        return []
    clusters: list[dict] = []
    cur = {"anchors": [anchors[0]], "signals": {anchors[0]["signal"]}}
    for a in anchors[1:]:
        if a["start_s"] - cur["anchors"][-1]["end_s"] <= gap_sec:
            cur["anchors"].append(a)
            cur["signals"].add(a["signal"])
        else:
            clusters.append(cur)
            cur = {"anchors": [a], "signals": {a["signal"]}}
    clusters.append(cur)
    out = []
    for c in clusters:
        last = c["anchors"][-1]          # terminal = latest signal in the cluster
        out.append({"idx": last["idx"], "signal": "+".join(sorted(c["signals"])),
                    "quote": last["quote"], "start_s": c["anchors"][0]["start_s"],
                    "end_s": last["end_s"], "n_signals": len(c["anchors"])})
    return out


if __name__ == "__main__":
    import sys
    from dataset import build_windows
    eid = sys.argv[1] if len(sys.argv) > 1 else "radiolab__oliver_sipple"
    for w in build_windows(eid):
        anc = find_anchors(w)
        cl = cluster_anchors(w, anc)
        if not anc:
            continue
        print(f"window @{int(w.t0)}: {len(anc)} anchors -> {len(cl)} clusters")
        for c in cl:
            mm, ss = divmod(int(c["start_s"]), 60)
            print(f"  [{mm:02d}:{ss:02d}] {c['signal']:20s} ({c['n_signals']}x) {c['quote'][:70]}")

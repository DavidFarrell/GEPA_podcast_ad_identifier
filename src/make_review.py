"""Render golden labels + transcripts into one self-contained HTML for human spot-checking.

For each episode: a summary line, then every golden span shown with the transcript turns it
covers (highlighted by type) plus a few turns of context before/after, so the reviewer can
judge whether each boundary sits at a clean content/faff transition.

Usage: python src/make_review.py data/golden data/transcripts out/pilot_review.html
"""
from __future__ import annotations

import html
import json
import sys
from pathlib import Path

from transcript import Transcript

COLORS = {"ad": "#ffd6d6", "intro": "#d6e4ff", "outro": "#e8d6ff", "housekeeping": "#fff0c2"}
CTX = 4  # sentences of context shown each side of a span


def fmt_t(s: float) -> str:
    m, sec = divmod(int(s), 60)
    return f"{m:02d}:{sec:02d}"


def episode_html(golden: dict, tr: Transcript) -> str:
    spans = golden["spans"]
    by_type: dict[str, int] = {}
    for s in spans:
        by_type[s["type"]] = by_type.get(s["type"], 0) + 1
    chips = " ".join(
        f'<span class="chip" style="background:{COLORS.get(t,"#eee")}">{t}: {n}</span>'
        for t, n in sorted(by_type.items())
    )
    cut = golden.get("cut_seconds", 0)
    dur = golden.get("duration_s", tr.duration) or 1
    rej = golden.get("rejected", [])
    out = [f'<section><h2>{html.escape(golden["episode_id"])}</h2>',
           f'<p class="meta">{html.escape(golden.get("show",""))} &middot; '
           f'{fmt_t(dur)} long &middot; labeller: {html.escape(golden.get("labeled_by","?"))} &middot; '
           f'<b>{len(spans)} spans</b>, cutting {fmt_t(cut)} ({100*cut/dur:.1f}%)</p>',
           f'<p>{chips or "<i>no spans</i>"}'
           + (f' &middot; <span class="rej">{len(rej)} rejected (unmappable)</span>' if rej else "")
           + '</p>']
    n = len(tr.sentences)
    for k, s in enumerate(spans):
        i, j = s["start_idx"], s["end_idx"]
        out.append(f'<div class="span">'
                   f'<div class="hdr" style="border-color:{COLORS.get(s["type"],"#999")}">'
                   f'<b>#{k+1} {s["type"]}'
                   + (f' / {s["subtype"]}' if s.get("subtype") else "")
                   + f'</b> &nbsp; {fmt_t(s["start_s"])}&ndash;{fmt_t(s["end_s"])} '
                   f'({s["end_s"]-s["start_s"]:.0f}s) &nbsp; '
                   f'<span class="conf">conf {s.get("confidence","?")}</span><br>'
                   f'<span class="rat">{html.escape(s.get("rationale",""))}</span></div>')
        lo, hi = max(0, i - CTX), min(n - 1, j + CTX)
        for ti in range(lo, hi + 1):
            t = tr.sentences[ti]
            inside = i <= ti <= j
            bg = COLORS.get(s["type"], "#eee") if inside else "transparent"
            mark = "&#9613;" if inside else " "
            out.append(f'<div class="turn" style="background:{bg}">'
                       f'<span class="tt">{mark}[{fmt_t(t.start)}] {html.escape(t.speaker)}:</span> '
                       f'{html.escape(t.text)}</div>')
        out.append('</div>')
    out.append('</section>')
    return "\n".join(out)


def main(golden_dir: str, tx_dir: str, out_path: str):
    gdir, tdir = Path(golden_dir), Path(tx_dir)
    parts = []
    for gf in sorted(gdir.glob("*.json")):
        golden = json.loads(gf.read_text())
        tf = tdir / f"{golden['episode_id']}.json"
        if not tf.exists():
            continue
        parts.append(episode_html(golden, Transcript.load(tf)))
    doc = f"""<!doctype html><meta charset=utf8><title>Golden label review</title>
<style>
body{{font:14px/1.5 -apple-system,Helvetica,sans-serif;max-width:980px;margin:24px auto;padding:0 16px;color:#1a1a1a}}
h1{{font-size:22px}} h2{{font-size:17px;margin:28px 0 4px;border-top:2px solid #ddd;padding-top:18px}}
.meta{{color:#555;margin:2px 0}} .chip{{padding:1px 8px;border-radius:10px;font-size:12px;margin-right:4px}}
.rej{{color:#b00}} .span{{margin:10px 0 16px;border-left:3px solid #ccc;padding-left:10px}}
.hdr{{border-left:4px solid;padding-left:8px;margin-bottom:4px}} .conf{{color:#888;font-size:12px}}
.rat{{color:#444;font-style:italic;font-size:13px}}
.turn{{padding:1px 4px;border-radius:2px}} .tt{{color:#666;font-variant-numeric:tabular-nums}}
</style>
<h1>Golden label review &middot; {len(parts)} episodes</h1>
<p class="meta">Highlighted = labelled faff (will be cut). Plain = content (kept). Check each boundary sits at a clean transition.</p>
{"".join(parts)}"""
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text(doc)
    print(f"wrote {out_path} ({len(parts)} episodes)")


if __name__ == "__main__":
    main(*sys.argv[1:4])

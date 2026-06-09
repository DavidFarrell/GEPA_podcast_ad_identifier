"""Build GEPA train/val/test instances: 30-min windows over the golden episodes.

Each instance is one transcript WINDOW (mirroring what the production detector sees),
carrying the rendered sentence-per-line text plus the golden faff spans clipped to the
window. The split is BY SHOW FAMILY so no show appears on both sides:

- train: 20VC, Behind the Bastards (x2), DTNS (x2), Ezra Klein, Freakonomics, Hard Fork,
  The Rest Is Politics family (US x2 + Leading)                          = 11 episodes
- val:   News Agents family (x2), Threedom, Lenny's, Past Present Future, ThursdAI,
  Practical AI, Search Engine                                            = 8 episodes
- test:  manifests/test8.json (held out - never used for training OR candidate selection)
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from transcript import Transcript, Sentence

ROOT = Path(__file__).resolve().parent.parent

WINDOW_SEC = 1800.0          # production window size
STEP_SEC = WINDOW_SEC - 180  # 3-min overlap between consecutive windows
MIN_GOLD_VISIBLE = 5.0       # a golden span clipped below this isn't expected in this window

TRAIN_EPS = [
    "20vc__anthropic_ipo", "btb__fuhrman_part1", "btb__fuhrman_part2",
    "dtns__wwdc2026_528", "dtns__do_people_hate_tech", "ezra_klein__ian_bremmer",
    "freakonomics__676_lost_plot", "hard_fork__ipo_summer_math",
    "trip_us__trump_netanyahu", "trip_us__losing_streak", "trip_leading__control_ai",
]
VAL_EPS = [
    "news_agents__trump_impotent", "news_agents_usa__j6_slush", "threedom__i_see_both",
    "lennys__rational_ai", "ppf__dispossessed", "thursdai__nemotron",
    "practical_ai__stanford_index", "search_engine__bp_pool",
]

GOLDEN_DIRS = [ROOT / "data/golden", ROOT / "data/golden_pilot", ROOT / "data/golden_test"]


def golden_path(episode_id: str) -> Path:
    for d in GOLDEN_DIRS:
        p = d / f"{episode_id}.json"
        if p.exists():
            return p
    raise FileNotFoundError(f"no golden labels for {episode_id} in {[str(d) for d in GOLDEN_DIRS]}")


@dataclass
class Window:
    episode_id: str
    t0: float
    t1: float
    sentences: list[Sentence]      # the slice visible in this window (original idx/times kept)
    golden: list[dict]             # golden spans clipped to [t0, t1]
    text: str = ""                 # rendered "#idx [mm:ss] SPEAKER: text" lines

    @property
    def wid(self) -> str:
        return f"{self.episode_id}@{int(self.t0)}"

    def header(self) -> str:
        def mmss(t: float) -> str:
            m, s = divmod(int(t), 60)
            return f"{m:02d}:{s:02d}"
        return f"episode {self.episode_id}, window {mmss(self.t0)}-{mmss(self.t1)}"


def _render(sentences: list[Sentence]) -> str:
    lines = []
    for s in sentences:
        mm, ss = divmod(int(s.start), 60)
        lines.append(f"#{s.idx} [{mm:02d}:{ss:02d}] {s.speaker}: {s.text}")
    return "\n".join(lines)


def build_windows(episode_id: str) -> list[Window]:
    tr = Transcript.load(ROOT / f"data/transcripts/{episode_id}.json")
    gold = json.loads(golden_path(episode_id).read_text())["spans"]
    out: list[Window] = []
    t0 = 0.0
    while True:
        t1 = min(t0 + WINDOW_SEC, tr.duration)
        sents = [s for s in tr.sentences if s.end >= t0 and s.start <= t1]
        spans = []
        for g in gold:
            a, b = max(g["start_s"], t0), min(g["end_s"], t1)
            if b - a >= MIN_GOLD_VISIBLE:
                spans.append({
                    "type": g["type"], "subtype": g.get("subtype"),
                    "start_s": round(a, 2), "end_s": round(b, 2),
                    "clipped": a > g["start_s"] or b < g["end_s"],
                })
        if sents:
            out.append(Window(episode_id, t0, t1, sents, spans, _render(sents)))
        if t1 >= tr.duration:
            break
        t0 += STEP_SEC
    return out


def load_split(name: str) -> list[Window]:
    if name == "train":
        ids = TRAIN_EPS
    elif name == "val":
        ids = VAL_EPS
    elif name == "test":
        manifest = json.loads((ROOT / "manifests/test8.json").read_text())
        ids = [e["id"] for e in manifest["episodes"]]
    else:
        raise ValueError(f"unknown split {name!r}")
    return [w for eid in ids for w in build_windows(eid)]


if __name__ == "__main__":
    for split in ("train", "val"):
        ws = load_split(split)
        gold_sec = sum(g["end_s"] - g["start_s"] for w in ws for g in w.golden)
        print(f"{split}: {len(ws)} windows, {sum(len(w.golden) for w in ws)} golden spans, "
              f"{gold_sec:.0f}s faff")
        for w in ws:
            print(f"  {w.wid:45s} {len(w.sentences):4d} sents  {len(w.golden)} spans")

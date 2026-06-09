"""Load fast-diarise transcripts and map verbatim quotes -> timestamps.

The diarise-transcribe JSON has `turns` (text + word timings + speaker) and `segments`
(speaker spans, no text). We work off `turns`. Quote mapping is the deterministic core that
both the golden labeller and the Gemma detector rely on: a span is described by a verbatim
`start_quote` / `end_quote`, which we resolve to turn indices and hence to start/end seconds.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path


def _norm(s: str) -> str:
    """Normalise for matching: lowercase, collapse whitespace, strip most punctuation."""
    s = s.lower()
    s = re.sub(r"[^\w\s]", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


@dataclass
class Turn:
    idx: int
    speaker: str
    start: float
    end: float
    text: str


class Transcript:
    def __init__(self, episode_id: str, turns: list[Turn]):
        self.episode_id = episode_id
        self.turns = turns
        # normalised concatenation + per-turn char offset, for substring search
        self._norm_turns = [_norm(t.text) for t in turns]
        self._joined = " ".join(self._norm_turns)
        self._turn_at_char: list[int] = []
        for i, nt in enumerate(self._norm_turns):
            self._turn_at_char.extend([i] * (len(nt) + 1))  # +1 for the join space

    @classmethod
    def load(cls, path: str | Path) -> "Transcript":
        path = Path(path)
        data = json.loads(path.read_text())
        turns = [
            Turn(idx=i, speaker=t.get("speaker", "?"),
                 start=float(t["start"]), end=float(t["end"]), text=t["text"].strip())
            for i, t in enumerate(data["turns"])
        ]
        return cls(path.stem, turns)

    @property
    def duration(self) -> float:
        return self.turns[-1].end if self.turns else 0.0

    def occurrences(self, quote: str, min_turn: int = 0) -> list[tuple[int, float]]:
        """All turn indices (>= min_turn) where `quote` appears, each with confidence.

        Exact normalised substring matches first (every occurrence, conf 1.0); if none,
        a single best fuzzy match (handles ASR drift / paraphrased boundaries).
        """
        q = _norm(quote)
        if not q:
            return []
        hits, start = [], 0
        while True:
            pos = self._joined.find(q, start)
            if pos == -1:
                break
            ti = self._turn_at_char[min(pos, len(self._turn_at_char) - 1)]
            if ti >= min_turn and (not hits or hits[-1][0] != ti):
                hits.append((ti, 1.0))
            start = pos + max(1, len(q))
        if hits:
            return hits
        # fuzzy fallback: best single turn at/after min_turn
        best_i, best_r = -1, 0.0
        for i in range(min_turn, len(self._norm_turns)):
            nt = self._norm_turns[i]
            r = SequenceMatcher(None, q, nt).ratio()
            if len(q) < len(nt):
                r = max(r, SequenceMatcher(None, q, nt[: len(q) + 10]).ratio())
            if r > best_r:
                best_i, best_r = i, r
        return [(best_i, best_r)] if best_i >= 0 and best_r >= 0.6 else []

    def map_span(self, start_quote: str, end_quote: str, min_turn: int = 0,
                 max_span_sec: float = 240.0) -> dict | None:
        """Resolve a (start_quote, end_quote) pair to the TIGHTEST valid timed span
        whose start is at/after `min_turn`. Returns None if unmappable or if no valid
        pairing stays within `max_span_sec` (a guard against content-eating explosions).

        Cursor-aware: callers pass min_turn = end of the previous span so that a quote
        repeated across the episode (e.g. a sponsor read inserted 3x) maps to successive
        occurrences instead of pairing an early start with a late end.
        """
        starts = self.occurrences(start_quote, min_turn)
        if not starts:
            return None
        best = None
        for si, sc in starts:
            ends = self.occurrences(end_quote, si)        # end must be at/after this start
            for ej, ec in ends:
                span_sec = self.turns[ej].end - self.turns[si].start
                if span_sec < 0 or span_sec > max_span_sec:
                    continue
                cand = (si, ej, min(sc, ec), span_sec)
                if best is None or cand[3] < best[3]:      # prefer the tightest valid span
                    best = cand
            if best and best[0] == si:
                break                                      # first start with a valid tight end wins
        if best is None:
            return None
        si, ej, conf, _ = best
        return {
            "start_s": round(self.turns[si].start, 2),
            "end_s": round(self.turns[ej].end, 2),
            "start_turn": si,
            "end_turn": ej,
            "confidence": round(conf, 3),
        }

    def render(self, t0: float = 0.0, t1: float | None = None, numbered: bool = True) -> str:
        """Human/LLM-readable transcript slice: `[mm:ss] SPEAKER: text` per turn."""
        t1 = self.duration if t1 is None else t1
        lines = []
        for t in self.turns:
            if t.end < t0 or t.start > t1:
                continue
            mm, ss = divmod(int(t.start), 60)
            tag = f"#{t.idx} " if numbered else ""
            lines.append(f"{tag}[{mm:02d}:{ss:02d}] {t.speaker}: {t.text}")
        return "\n".join(lines)


if __name__ == "__main__":
    import sys
    tr = Transcript.load(sys.argv[1])
    print(f"{tr.episode_id}: {len(tr.turns)} turns, {tr.duration:.0f}s")
    print(tr.render(0, 60))

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

    def find_turn(self, quote: str) -> tuple[int, float] | None:
        """Return (turn_idx, confidence 0..1) for the turn best matching `quote`, or None.

        Tries exact normalised substring first; falls back to best fuzzy turn match.
        """
        q = _norm(quote)
        if not q:
            return None
        pos = self._joined.find(q)
        if pos != -1:
            return self._turn_at_char[min(pos, len(self._turn_at_char) - 1)], 1.0
        # fuzzy: best single-turn ratio (handles ASR drift / paraphrased boundaries)
        best_i, best_r = -1, 0.0
        for i, nt in enumerate(self._norm_turns):
            r = SequenceMatcher(None, q, nt).ratio()
            # also reward when the quote is a near-substring of a longer turn
            if len(q) < len(nt):
                r = max(r, SequenceMatcher(None, q, nt[: len(q) + 10]).ratio())
            if r > best_r:
                best_i, best_r = i, r
        if best_i >= 0 and best_r >= 0.6:
            return best_i, best_r
        return None

    def map_span(self, start_quote: str, end_quote: str) -> dict | None:
        """Resolve a (start_quote, end_quote) pair to a timed span.

        Returns {start_s, end_s, start_turn, end_turn, confidence} or None if unmappable.
        """
        a = self.find_turn(start_quote)
        b = self.find_turn(end_quote)
        if a is None or b is None:
            return None
        i, ca = a
        j, cb = b
        if j < i:  # boundaries crossed; trust the earlier as start, later as end
            i, j = min(i, j), max(i, j)
        return {
            "start_s": round(self.turns[i].start, 2),
            "end_s": round(self.turns[j].end, 2),
            "start_turn": i,
            "end_turn": j,
            "confidence": round(min(ca, cb), 3),
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

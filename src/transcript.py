"""Load fast-diarise transcripts and map verbatim quotes -> precise timestamps.

The diarise-transcribe JSON has `turns` (coarse speaker turns, each with word-level timings)
and `segments` (speaker spans, no text). A single turn can run 60s and mix several faff types
with content, so turn-granularity is too coarse for clean snip points. We therefore re-segment
the word stream into SENTENCES (each with precise start/end from word timestamps) and do all
rendering and quote-mapping at sentence granularity. Sentence boundaries fall at natural
speech pauses, which are exactly where you want to cut audio.

A faff span is described by a verbatim `start_quote` / `end_quote`; we resolve those to the
sentence where the quote starts and the sentence where it ends, hence to precise seconds.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path

_SENT_END = re.compile(r"[.!?]+[\"')\]]?$")


def _norm(s: str) -> str:
    """Normalise for matching: lowercase, drop punctuation, collapse whitespace."""
    s = s.lower()
    s = re.sub(r"[^\w\s]", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


@dataclass
class Sentence:
    idx: int
    turn: int
    speaker: str
    start: float
    end: float
    text: str


class Transcript:
    def __init__(self, episode_id: str, sentences: list[Sentence]):
        self.episode_id = episode_id
        self.sentences = sentences
        self._norm_sents = [_norm(s.text) for s in sentences]
        # normalised concatenation + per-char sentence index, for substring search
        self._joined = " ".join(self._norm_sents)
        self._sent_at_char: list[int] = []
        for i, ns in enumerate(self._norm_sents):
            self._sent_at_char.extend([i] * (len(ns) + 1))  # +1 for the join space

    @classmethod
    def load(cls, path: str | Path) -> "Transcript":
        path = Path(path)
        data = json.loads(path.read_text())
        sentences: list[Sentence] = []
        for ti, turn in enumerate(data["turns"]):
            words = turn.get("words") or []
            if not words:  # no word timings: keep the whole turn as one sentence
                sentences.append(Sentence(len(sentences), ti, turn.get("speaker", "?"),
                                          float(turn["start"]), float(turn["end"]),
                                          turn["text"].strip()))
                continue
            cur: list[dict] = []
            for w in words:
                cur.append(w)
                if _SENT_END.search(w["text"]):
                    sentences.append(cls._mk_sentence(cur, ti, turn.get("speaker", "?"), len(sentences)))
                    cur = []
            if cur:  # trailing words with no terminal punctuation
                sentences.append(cls._mk_sentence(cur, ti, turn.get("speaker", "?"), len(sentences)))
        return cls(path.stem, sentences)

    @staticmethod
    def _mk_sentence(words: list[dict], turn: int, speaker: str, idx: int) -> Sentence:
        text = " ".join(w["text"] for w in words).strip()
        return Sentence(idx, turn, speaker, float(words[0]["start"]), float(words[-1]["end"]), text)

    @property
    def duration(self) -> float:
        return self.sentences[-1].end if self.sentences else 0.0

    # ---- quote -> sentence resolution -------------------------------------------------

    def _find(self, quote: str, min_char: int = 0) -> list[tuple[int, int]]:
        """All (start_char, end_char) of exact normalised matches of `quote` at/after min_char.
        Falls back to a single best fuzzy sentence match if there are no exact matches."""
        q = _norm(quote)
        if not q:
            return []
        hits, start = [], min_char
        while True:
            pos = self._joined.find(q, start)
            if pos == -1:
                break
            hits.append((pos, pos + len(q)))
            start = pos + max(1, len(q))
        if hits:
            return hits
        # fuzzy fallback: best single sentence at/after min_char
        min_sent = self._sent_at_char[min(min_char, len(self._sent_at_char) - 1)] if self._sent_at_char else 0
        best_i, best_r = -1, 0.0
        for i in range(min_sent, len(self._norm_sents)):
            ns = self._norm_sents[i]
            r = SequenceMatcher(None, q, ns).ratio()
            if len(q) < len(ns):
                r = max(r, SequenceMatcher(None, q, ns[: len(q) + 10]).ratio())
            if r > best_r:
                best_i, best_r = i, r
        if best_i >= 0 and best_r >= 0.6:
            # synthesise a char span covering that sentence
            c0 = sum(len(self._norm_sents[k]) + 1 for k in range(best_i))
            return [(c0, c0 + len(self._norm_sents[best_i]))]
        return []

    def _sent_at(self, char: int) -> int:
        return self._sent_at_char[min(max(0, char), len(self._sent_at_char) - 1)]

    def map_span(self, start_quote: str, end_quote: str, min_sent: int = 0,
                 max_span_sec: float = 240.0) -> dict | None:
        """Resolve (start_quote, end_quote) to the TIGHTEST valid sentence span whose start
        sentence is >= min_sent, within max_span_sec (guard against repeated-quote explosions).
        Cursor-aware via min_sent so repeated reads map to successive occurrences."""
        min_char = sum(len(self._norm_sents[k]) + 1 for k in range(min_sent))
        starts = self._find(start_quote, min_char)
        if not starts:
            return None
        best = None
        for s0, _ in starts:
            si = self._sent_at(s0)
            ends = self._find(end_quote, s0)              # end must begin at/after the start
            for _, e1 in ends:
                sj = self._sent_at(e1 - 1)
                if sj < si:
                    continue
                span_sec = self.sentences[sj].end - self.sentences[si].start
                if span_sec < 0 or span_sec > max_span_sec:
                    continue
                if best is None or span_sec < best[2]:
                    best = (si, sj, span_sec)
            if best and best[0] == si:
                break
        if best is None:
            return None
        si, sj, _ = best
        return {
            "start_s": round(self.sentences[si].start, 2),
            "end_s": round(self.sentences[sj].end, 2),
            "start_idx": si,
            "end_idx": sj,
            "confidence": 1.0,
        }

    def render(self, t0: float = 0.0, t1: float | None = None, numbered: bool = True) -> str:
        """Sentence-per-line: `#<idx> [mm:ss] SPEAKER: text`."""
        t1 = self.duration if t1 is None else t1
        lines = []
        for s in self.sentences:
            if s.end < t0 or s.start > t1:
                continue
            mm, ss = divmod(int(s.start), 60)
            tag = f"#{s.idx} " if numbered else ""
            lines.append(f"{tag}[{mm:02d}:{ss:02d}] {s.speaker}: {s.text}")
        return "\n".join(lines)


if __name__ == "__main__":
    import sys
    tr = Transcript.load(sys.argv[1])
    print(f"{tr.episode_id}: {len(tr.sentences)} sentences, {tr.duration:.0f}s")
    print(tr.render(0, 90))

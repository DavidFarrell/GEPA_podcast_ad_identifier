# 01 - Terminal-anchor backward recovery (the Round-5 win)

## The problem it solves

After Round 3 shipped the hand-written `seed_checklist_v1` champion (86% ad spans on the
pristine fresh5 exam), and Round 4's two-pass detect-then-verify came back a **clean
negative** (a per-span keep/cut verify caught *zero* extra ads on held-out across three
verify prompts), the remaining misses were analysed directly.

**Finding: every held-out miss was a *complete* miss, and they shared a shape.** Each missed
ad:

1. **opened disguised as content** - a rhetorical question ("what do you think of when you
   hear the word summer?"), a narrative or dramatic sketch, a personal anecdote, or a
   topical hook that reads exactly like ordinary show talk;
2. **ended on an unambiguous terminal signal** - a spoken/printed URL, a promo code, a
   percentage off, a "terms apply", a sponsor tagline, a giveaway entry, or a podcast
   cross-promo;
3. **sat first-in-break** - the first ad in an ad cluster, with nothing before it to prime
   suspicion.

A detector that hunts for ads by *suspicious openings* cannot catch these - the opening is
deliberately camouflaged. But the *ending* is certain.

## The thesis

> **Anchor on the certain ending; expand backward to the disguised start.**

This is the whole idea. Instead of lowering the global suspicion threshold (which would
raise recall but also balloon false positives, and the exponential FP gate punishes that
brutally), recovery works *only* in the neighbourhood of a proven terminal signal. It raises
recall **without touching the threshold the first pass uses elsewhere** - precisely the
trade the metric `score = recall * 0.5^(fp_sec/15)` rewards.

GPT-5 (xhigh) was consulted on the thesis independently and endorsed it before the build.

## The mechanism (and why each piece is load-bearing)

The pipeline is in `src/anchors.py` + `src/recover.py`, wired into `src/run_eval.py` via
`--recover regex --recover-prompt prompts/recover_micro_v2.txt`.

```
window
  -> anchors.find_anchors(window)        # conservative regex terminal scan
  -> anchors.cluster_anchors(...)        # merge nearby anchors; keep the LAST (terminal)
  -> for each cluster:
        recover._render_micro(...)       # micro-window: anchor -90s back / +30s fwd,
                                         #   mark the terminal-signal line
        call_llm(recover_micro_v2, ...)  # model back-expands THIS one promo
        sub.map_span(start_q, end_q)     # verbatim quotes -> (start_s, end_s)
  -> run_eval._union_spans(det, extra)   # merge recovered spans on top of the first pass
```

Two things proved load-bearing the hard way:

- **The deterministic regex pre-scan is load-bearing.** Arm 2 (`recover_scan_v1.txt`, mode
  `model`) let the model find its *own* terminals over the full window. False positives blew
  up to **366s**. Constraining the model to back-expand a *single, already-proven* terminal
  (mode `regex`) is what keeps it precise. The model's job is reduced to one question: "how
  far back does this proven ad start?" - not "is there an ad here?".

- **The back-expansion prompt's topic-vs-ad carve-out is load-bearing.** The most common
  false alarm is a product that is the *episode's subject*, not a sponsor - a tech/news/review
  show naming a brand and its URL all episode is doing content, not running ads. `recover_micro_v2`
  added an explicit carve-out: a documentation/model-card/repo/news link is **not** an ad
  terminal; an ad terminal is a purchase/subscribe/signup page tied to an offer or CTA. (The
  canonical case is ThursdAI covering the Nvidia Nemotron release - reads like an ad CTA, is
  actually content. David ruled it content; correct to leave.)

## Result on the held-out exam (the reason it shipped)

This was the **first** configuration in the project to beat the champion on *unseen* shows -
the val->test transfer gap that killed Rounds 1-4 (GEPA-evolved val winners that lost the
held-out exam) did **not** kill this, because recovery is a mechanism, not a prompt selected
to fit a validation set.

| Split | Metric | Champion | Champion + recovery v2 |
|-------|--------|----------|------------------------|
| fresh5 (5 pristine shows) | ad spans | 16/19 | **17/19** |
| fresh5 | ad-time recall | 0.786 | **0.836** |
| fresh5 | extra FP | 70.7s | **70.7s (zero added)** |
| fresh5 | score | 0.665 | **0.708** |
| test8 (8 never-selected shows) | ad spans | 12/15 | **13/15** |
| test8 | recall | 0.578 | **0.692** |

Champion config committed at `45caa6a`. Full tables in `../results.md` (ROUND 5 section).

See [02_swimcast_adoption.md](02_swimcast_adoption.md) for what happened when this was
re-validated on an *independent* 9-show corpus and taken to production.

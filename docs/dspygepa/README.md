# dspygepa session notes

These notes are written from the **dspygepa** session - the GEPA podcast ad-detector
optimisation work - and cover the arc from the Round-5 recovery win through to the
**production ship** of the champion detector into Open Swimcast on 14 Jun 2026.

They are a companion to `../results.md` (the per-round eval tables). Where `results.md`
records *what scored what*, these notes record *why* - the theses, the mechanisms, the
design decisions, the cross-validation with the swimcast session, and the levers still open.

> **Copyright note:** like the rest of this repo, these notes contain **no verbatim
> transcript text**. `data/` and `out/` are gitignored because they embed copyrighted
> transcript material; any example here (e.g. the threedom parody case) is paraphrased,
> never quoted. Keep it that way when extending these notes.

## Index

| File | What it covers |
|------|----------------|
| [01_recovery_approach.md](01_recovery_approach.md) | The terminal-anchor backward-recovery thesis (Round 5) - why it beat the champion on the held-out exam |
| [02_swimcast_adoption.md](02_swimcast_adoption.md) | The cross-validation + production ship into Open Swimcast (numbers, decisions, deferrals) |
| [03_hard_soft_terminal_split.md](03_hard_soft_terminal_split.md) | The precision guard that kills the channel-link false positives |
| [04_granularity_char_interp.md](04_granularity_char_interp.md) | Is sentence segmentation load-bearing? The char-interpolation cheap path |
| [05_fp_adjudication_rubric.md](05_fp_adjudication_rubric.md) | The cardinal-rule adjudication rubric used to stand in for David overnight |
| [06_open_levers_and_lessons.md](06_open_levers_and_lessons.md) | What's deferred, what's next, and the durable lessons |
| [07_creative_optimisation_ideas.md](07_creative_optimisation_ideas.md) | A wide, bold brainstorm (dspygepa + GPT-5 + an online GEPA-practitioner survey) of further optimisation ideas, with a ranked shortlist |

## TL;DR

- **The metric is everything.** `score = recall * 0.5^(fp_sec / 15)`. The false-positive
  gate is *exponential*, so cutting real content is catastrophic and boundary precision is
  the dominant term in the score, not a cosmetic refinement. Every design choice below
  falls out of this one fact.
- **Round 5 (the win): terminal-anchor backward recovery.** Every ad the champion *misses*
  opens disguised as content but *ends* on an unambiguous terminal signal (a URL, promo
  code, "terms apply", giveaway, podcast cross-promo). So don't hunt for ads by suspicious
  openings - anchor on the certain *ending* and expand *backward* to the disguised start.
  This raises recall **without** lowering the global suspicion threshold, which is exactly
  what the exponential FP gate rewards. First config in the project to beat the champion on
  the held-out exam, because it is *mechanistic*, not a selector fit.
- **It shipped.** On 14 Jun 2026 the champion prompt (`seed_checklist_v1`) became the
  production default ad-detector in Open Swimcast: **11.7s** of content wrongly auto-cut vs
  the old detector's **99.2s** (~8x safer) and ad-recall **0.331 vs 0.268** - strictly
  better on both axes. Recovery itself was deferred as a separate guarded phase.
- **Two refinements made it shippable:** the *hard/soft terminal split* (file 03) to kill
  channel-link FPs, and *char-interpolation* (file 04) to get sub-turn boundary precision
  without rebuilding the transcript substrate.

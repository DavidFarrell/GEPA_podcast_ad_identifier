# 02 - Adoption into Open Swimcast (the production ship)

On 14 Jun 2026 the GEPA champion detector was adopted into **Open Swimcast** (the Electron
app that sideloads podcast episodes onto swim headphones and trims interstitials). The work
was a collaboration between two sessions on David's Mac, coordinated over the `paidiamsg`
message bus:

- **dspygepa** (this session) - domain authority on the GEPA metric, the recovery mechanism,
  and cardinal-rule adjudication.
- **swimcast** - owns the Open Swimcast codebase, did the porting, validation, and deploy.

GPT-5 (xhigh, via `ask-gpt5`) acted as an independent reviewer / pre-commit gate throughout.

## What shipped

The champion prompt (`seed_checklist_v1`) is now the **production-default ad-detector** in
Open Swimcast, replacing the old `VERIFY_INSTRUCTION` detector. Merged to `main @ 41a1088`,
rebuilt, installed to `/Applications`, launch-verified, 482 tests green.

**Head-to-head on the 9 GEPA golden shows** (scored on auto-applied false-positive seconds =
real content wrongly auto-cut):

| | Old detector | New (GEPA champion) |
|---|---|---|
| Content wrongly auto-cut | 99.2s | **11.7s** (~8x safer) |
| Ad-recall | 0.268 | **0.331** |

Strictly better on both axes: catches *more* ads while cutting *less* content. Rollback is
one line: `detectorMode: "gepa" -> "legacy"` in `ipc.cjs`.

## The two things that made it shippable

1. **Char-interpolation granularity** (see [04](04_granularity_char_interp.md)). GPT-5's
   initial read was that a straight prompt-drop would not replicate GEPA's results because
   GEPA works on *sentence*-segmented spans while the Swimcast detector works on coarse
   diarized *turns* - a one-sentence ad inside a 60s turn would force a 60s cut. True, but
   the fix turned out cheap: map each model-returned verbatim quote to a time by its
   character position *inside* the turn. That recovered ~81% of full sentence-re-segmentation
   precision and matched/beat it on embedded-ad shows - making the whole thing a **one-file
   change** instead of a transcript-substrate rebuild.

2. **The hard/soft terminal split** (see [03](03_hard_soft_terminal_split.md)). The recovery
   pass's false positives were almost all on one show (dtns: bare `youtube.com/<brand>`
   channel cross-promos). Splitting terminals into HARD-commercial (fire alone) vs SOFT
   (require corroboration) kills those without losing the genuine wins.

## The corrected attribution (worth recording honestly)

In the initial handoff, dspygepa flagged that recovery added "~5s FP on Threedom". When
swimcast ran a clean champion-vs-champion+recovery diff across all 9 golden shows, it found
that **was wrong**: the ~5s Threedom span is a *first-pass* false positive (a host comedy
bit, see [05](05_fp_adjudication_rubric.md)), identical in both configs. Recovery on Threedom
is in fact a clean **win** (+0.08 ad-recall, zero added FP - it back-expands a Mint Mobile
opening inside an existing golden ad). swimcast's diff is authoritative; the earlier
attribution was a memory error and was corrected on the bus.

Lesson: **trust the fresh diff over the remembered eval.** When two sessions disagree about a
number, the one that just ran the experiment wins.

## Per-show table (champion -> champion+recovery; fp_sec / ad-recall)

| Show | Champion | + Recovery | Note |
|------|----------|-----------|------|
| threedom | 5.2 / 0.78 | 5.2 / **0.86** | recovery win, 0 added FP |
| dtns | 0.0 / 0.91 | **52.5** / 0.92 | +52.5 = PCMag/CNET youtube channel links (soft-terminal) |
| btb | 34.5 / 1.00 | 34.5 / 1.00 | unchanged |
| news_agents_usa | 0.0 / 0.74 | 0.0 / **0.96** | recovery win, 0 FP |
| lennys | 16.8 / 1.00 | 16.8 / 1.00 | unchanged |
| trip_leading | 12.9 / 0.91 | 12.9 / 0.91 | unchanged |
| trip_us | 19.5 / 1.00 | 21.7 / 1.00 | +2.2 = outro podcast cross-promo (soft-terminal) |
| ppf | 0.0 / 1.00 | 0.0 / 1.00 | unchanged |
| thursdai | 0 / - | 0 / - | unchanged |
| **TOTAL** | **88.9 / 0.84** | **143.6 / 0.92** | +8pts recall; all +54.7s FP is soft-terminal |

The decisive observation: **every** incremental recovery FP is soft-terminal (channel links
+ one podcast cross-promo), exactly what the hard/soft corroboration guard catches, while the
two clean wins (threedom, news_agents) terminate on real offers and survive the guard. So the
guarded recovery is +8pts recall at ~zero net added FP.

(Note: a prose message on the bus said trip_us was "+9.7"; the table's 19.5 -> 21.7 = +2.2 is
correct and reconciles the total. Minor, no impact - still soft-terminal, still caught.)

## What was deferred (and why)

The **recovery pass itself** was *not* shipped on the night - only the first-pass champion
prompt. Both dspygepa and GPT-5 advised landing the first pass first and doing recovery as a
separate guarded phase, because recovery:

- adds a **second model call per ad** (more latency on the swim-analyse step), and
- produces **more review prompts** (held cuts for the user to approve),

for **+8pts recall**. Those are real UX trade-offs not worth forcing on an unattended ship.
Recovery is **fully designed and ready** (hard/soft split, eval numbers known) in
`docs/smart-processing/DESIGN_GEPA_ADOPTION.md` in the Swimcast repo - a clean next build on
David's go, ideally off-by-default so he can A/B the recall-vs-latency trade himself.

## Process notes

- A GPT-5 pre-commit gate caught a real cardinal-rule bug before commit: a backwards de-dupe
  that could have let a *held* cut auto-apply. Fixed before merge. The adversarial gate
  earned its keep.
- Swimcast's hard rule all night: **never auto-cut real content; anything uncertain is held
  for review, never shipped as a cut.** A 45s hard cap holds long/ambiguous cuts (~4 review
  prompts/show); one knob to raise if it feels too chatty.

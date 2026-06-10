# Results - overnight GEPA runs, 9-10 June 2026

Two GEPA optimisation rounds against the local detector (gemma-4-12b-qat via LM Studio,
30-min windows, quote-boundary method). All scores use the gated metric: recall of golden
faff seconds multiplied by 0.5^(false_positive_sec / 15), so cutting real content is
punished exponentially (the cardinal rule).

## Data

| Split | Episodes | Shows | Windows | Role |
|---|---|---|---|---|
| train (round 1) | 11 | 6 families | 30 | reflection minibatches |
| val (round 1) | 8 | 7 families | 22 | Pareto selection |
| train (round 2) | 21 | 16 families | 54 | reflection minibatches |
| val2 (round 2) | 12 | 11 families | 31 | Pareto selection |
| test8 | 8 | 8 families | 18 | held out - never used for any selection |

Golden labels: Sonnet labels, Opus independently relabels + adjudicates (mean cut-IoU
0.88-0.98 per batch). test8 shows: Conan, SYSK, My Favorite Murder, 99% Invisible,
FT Tech Tonic, Comedy Bang Bang, The Politics Show (New Statesman), The Econoclasts.

## Headline numbers (held-out test8)

| Prompt | Mean window score | Faff recall (time) | Ad spans caught | FP seconds |
|---|---|---|---|---|
| seed_faff_v1 (hand-written, 3 feedback passes) | **0.588** | **0.662** | **13/15 (87%)** | 135.1 |
| gepa_best (run-1 winner, val 0.815) | 0.551 | 0.592 | 11/15 (73%) | 157.0 |

- All of the seed's 135s FP is one show: Comedy Bang Bang's closing "plugs" segment
  (listener themes, guest tour dates) - golden policy keeps plugs as content; the model
  cuts them. Across the other 7 shows the seed cut **zero seconds** of real content.
- The evolved prompt's extra FP (21s) is on My Favorite Murder; its recall losses are on
  Politics Show (boundary changes from its new outro rule), MFM and CBB.

## Round 1 (budget 200, seed = seed_faff_v1, val = 8 shows)

- 7 candidates, ~3.2h. Val aggregate: seed 0.749 -> best (candidate 6) **0.815**.
- The reflection LM (Opus via CLI) wrote genuinely sharp rules from the metric feedback:
  network station-IDs mark injected ads; joke bumpers with no commercial inside are
  content (a real observed FP); "reflective wind-down" closings are outros; once a pod is
  confirmed, cover it completely.
- **But the +6.6pt val gain did not transfer**: test8 0.588 -> 0.551. Selection overfit
  to the 8 val shows.

## Round 2 (budget 250, seed = run-1 winner, val2 = 12 shows, train = 21 episodes)

- 7 candidates, ~3.2h, 96k context (fixes shared-KV 400s that had zeroed long windows).
- **No candidate beat the seed on val2**: best challenger 0.820 vs the run-1 winner's
  0.825. The wider selector refused everything that didn't generalise - which is exactly
  what it is for, but within this budget it found no genuine improvement.
- Seed_faff_v1 on val2 (post-hoc): **0.777** (recall 0.704, FP 35s, 0 parse errors). So
  val2 prefers the run-1 winner (+4.8pts) while test8 prefers the hand seed (+3.7pts).
  Caveat: val2 contains the 22 windows the run-1 winner was originally selected on, so
  its val2 edge is partly circular; test8 is the only fully unbiased comparison.

## Reading

1. **The hand-written seed remains the production choice.** It wins test8 on recall, ad
   catch AND false positives. The three human feedback passes that produced it were, in
   effect, a manual GEPA loop with better generalisation than the automated one achieved
   in 450 rollouts.
2. **The val->test gap is the whole story.** GEPA reliably improves val; with only 7-11
   show families as a selector, those gains are partly show-specific. The fix that
   matters is selector diversity, which round 2 only began to address.
3. **CBB-style "plugs" pollute both selection and scoring** - the same conversational-ad
   ambiguity that got TESD excluded. Either exclude such shows from scoring, or split the
   metric per faff type so ad performance (what Open Swimcast actually ships) is not
   drowned by plugs/outro policy disputes.

## Next steps worth trying

- Per-type metric: score ads separately; weight ad recall highest, report
  intro/outro/housekeeping as secondary objectives (gepa supports objective_scores).
- Bigger selector: golden-label cheaply at scale (Sonnet-only, Opus spot-checks) to push
  val to 25+ show families before spending more rollout budget.
- Multiple seeds / merge: start GEPA from both seed_faff_v1 and the run-1 winner so merge
  can combine the seed's conservatism with run-1's coverage rules.
- Revisit golden policy on plugs segments (CBB) before they next pollute a selector.

## Infrastructure notes (cost of the night)

- ~450 Gemma rollouts across 2 GEPA runs + 4 eval passes; ~45-50s per 30-min window.
- LM Studio: two gemma-4-12b-qat instances; context must cover concurrent requests
  (now 98304). 400 "context exceeded" errors score 0 and silently poison results -
  run_eval reports parse_errors so always check that column first.
- 22 episodes fetched/transcribed/golden-labelled autonomously overnight (fast-diarise
  local transcription; audio deleted after; transcripts/labels gitignored - copyright).

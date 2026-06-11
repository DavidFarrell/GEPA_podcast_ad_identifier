# Results - GEPA rounds 1-3, 9-11 June 2026

## ROUND 3 (10-11 June, overnight) - the verdict

Round 3 attacked the round-1/2 failure (val gains that don't transfer) on four fronts:
window length, prompt strategy, metric honesty, and selector size. Final exam ran on TWO
held-out sets: test8 (8 shows, used for earlier decisions) and **test_fresh5 (5 shows -
Radiolab, Crime Junkie, This American Life, Huberman Lab, NPR Politics - never used for
anything; labelled at Sonnet/Opus IoU 1.00)**.

### Final exam (weighted metric: 0.7 ad recall + 0.3 other, FP-gated)

| Prompt | fresh5 score | fresh5 ad recall | fresh5 spans | fresh5 FP | test8 score | test8 spans |
|---|---|---|---|---|---|---|
| **seed_checklist_v1** | **0.665** | **0.840** | **18/21 (86%)** | 70.7s | **0.661** | 12/15 |
| gepa_run3_best | 0.637 | 0.727 | 14/21 | 34.9s | 0.624 | 13/15 |
| seed_faff_v1 (original) | 0.615 | 0.715 | 14/21 | **0s** | 0.612 | 13/15 |

**The checklist prompt ships.** It wins both exams and lifts pristine-exam ad-span catch
from the original's 67% to 86%. The original remains the most conservative (zero FP on
fresh5); the round-3 GEPA winner has the best FP discipline of the aggressive prompts but
the lowest recall - its +0.4pt val3 edge did not transfer, the third such result.

### What round 3 established

1. **Window length is settled: 30 minutes.** 10/15-min windows leave recall flat
   (0.69-0.70) and make FP worse (35s -> 58s/104s). Cheap kill of a plausible hypothesis.
2. **Prompt STRATEGY matters more than prompt tuning.** The five-way tournament
   (original / checklist / editor-persona / procedure / one-shot) spanned 0.59-0.83 on
   val2 - a far wider range than any GEPA mutation chain achieved. The terse checklist
   won; the editor persona hit 0.871 ad recall (proving the recall headroom exists in
   gemma-12) at 537s FP cost.
3. **The metric is now honest.** Ads-weighted scoring + "ambiguous" zones: a Sonnet-flag /
   Opus-confirm pass over all 41 episodes found exactly 4 policy-grey zones (CBB plugs
   107s, TRIP US founding-member 92s, NSTAAF guest plug 76s, DTNS guest plug 25s) that
   no longer count as recall targets or false positives.
4. **Even a 36-episode / ~33-show-family / 80-window selector doesn't close the val->test
   gap for GEPA candidates.** Run 3 (budget 380, ads-only metric, checklist seed):
   5 candidates, winner 0.838 vs seed 0.834 on val3 - the first candidate in three rounds
   to beat its seed on a wide selector - and it still lost the pristine exam to its own
   seed. Hand-written strategy changes generalise; reflective mutations keep overfitting
   the selector at this budget scale.
5. **The evolved prompt is worth reading** (prompts/gepa_run3_best.txt): it internalised
   the scoring ("false_positive_seconds dominates... type labels barely matter, spend
   judgment on BOUNDARIES"), documents a specific catastrophic window ("THE #1 MISTAKE TO
   AVOID (this scored 0.040)" - the show-ID billboard trap), and pulls "but first, a word
   from our sponsors" handoffs inside the ad span. The reflection machinery works; the
   selection pressure is the bottleneck.

### Where the remaining 14% lives (fresh5 misses, checklist prompt)

3 of 21 ad spans missed; misses are short cross-promos and casual host-read pivots, plus
boundary clipping on long stacked pods. Levers if David wants 90%+: (a) two-pass
detect-then-verify so an aggressive first pass (editor-persona-style) is FP-filtered by a
second call; (b) union-ensemble of checklist + editor with verify; (c) more GEPA budget
with merge across the checklist/editor lineages; (d) accept 86% - it is already a large
step over the locked production detector's scope (ads only, no intros/outros).

---

# Results - overnight GEPA runs, 9-10 June 2026 (rounds 1-2, for the record)

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

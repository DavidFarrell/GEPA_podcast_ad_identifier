# 06 - Open levers and durable lessons

## Deferred / next builds

1. **Ship the recovery pass in Open Swimcast** (the obvious next one). Fully designed in the
   Swimcast repo's `docs/smart-processing/DESIGN_GEPA_ADOPTION.md`, with the hard/soft
   terminal split ([03](03_hard_soft_terminal_split.md)) baked in. Trade-off: +8pts recall
   for a second model call per ad + more review prompts. Recommended rollout: **off-by-default
   A/B**, so David can feel the recall-vs-latency cost himself before it becomes default.

2. **Implement the hard/soft tagging in `anchors.py`.** The split is designed but the code
   still treats all `_PATTERNS` matches as equal-weight terminals. Tag each pattern HARD or
   SOFT and gate SOFT-only clusters behind corroboration (same-cluster HARD terminal OR
   first-pass overlap). This is the precise lever that removes the dtns-style channel-link
   FPs without touching the complete-miss wins.

3. **Span-TRIMMING verify** (carried over from Round 4's negative result). The Round-4
   keep/cut verify was a clean negative, but the union(checklist, editor) first pass exposed
   real recall headroom (0.866 time-recall on val2, the highest measured) whose FP is
   *inseparable* by a yes/no keep-cut decision - the hard cases are boundary / category
   disputes (over-extended outros, mid-ep recaps, ad-policy meta-commentary), not binary
   false positives. The untried lever is a verify that returns **adjusted boundaries**, not
   keep/cut, aimed at that 0.866 recall. This is a *new build*, not a tweak. See
   `../results.md` ROUND 4.

4. **More GEPA budget / lineage merge** - always available, but deprioritised: three straight
   GEPA rounds (830+ rollouts) produced val winners that lost the held-out exam. The
   project's wins have come from *mechanism* (recovery) and *hand-written prompt strategy*
   (the checklist tournament), not from more rollouts. Spend budget on mechanism before
   spending it on search.

## Durable lessons (the ones worth carrying to the next project)

- **The metric dictates the architecture.** An exponential FP gate means boundary precision
  *is* the score. Every good decision here - recovery instead of threshold-lowering,
  char-interpolation instead of coarse turns, hard/soft instead of a global threshold - is
  downstream of taking that one fact seriously.

- **Anchor on certainty, expand toward ambiguity.** Recovery works because it starts from a
  *proven* terminal and only then reasons about the fuzzy boundary. The deterministic
  pre-scan is load-bearing; letting the model find its own terminals blew FP to 366s. When a
  task has a certain part and an uncertain part, pin the certain part deterministically and
  spend the model only on the uncertain part.

- **Mechanistic beats selector-fit for transfer.** The val->test gap killed every
  GEPA-evolved prompt (tuned to a validation set). Recovery transferred to unseen shows -
  and to an *independent corpus* (Swimcast's 9 shows) - because it encodes a real regularity
  of how ads are structured, not a fit to a particular split.

- **Trust the fresh diff over the remembered eval.** dspygepa mis-attributed a Threedom FP to
  recovery from memory; swimcast's clean re-run corrected it. When sessions disagree on a
  number, the one that just ran the experiment is right.

- **Policy divergence is not a bug.** The dtns channel-link FPs were the model *correctly*
  following the GEPA faff policy (network-promo counts) applied to a corpus labelled under a
  different policy. Recognise when a "false positive" is actually a labelling-policy
  mismatch, and gate by policy rather than trying to "fix" the model.

- **Be honest about what you didn't test.** On the segmentation question, the right answer was
  "I never ran that ablation - here's the mechanism, now go run it" - not a fabricated number.
  The 3-arm ablation that followed gave the real answer (and a cheaper path than anyone's
  prior).

- **A token blocklist can't tell parody from pitch.** The only threedom FP was a comedy bit
  *about* ads. The defence is the SELL-vs-DISCUSS test, not more keyword filtering.

## Pointers

- Champion prompt: `prompts/seed_checklist_v1.txt`
- Recovery prompt: `prompts/recover_micro_v2.txt`
- Regex terminal scanner: `src/anchors.py`
- Recovery engine: `src/recover.py`
- Wiring + metric: `src/run_eval.py`, `src/metric.py`
- Per-round eval tables: `../results.md`
- Repro (champion + recovery on the pristine exam):
  ```
  uv run python src/run_eval.py \
    --prompt prompts/seed_checklist_v1.txt \
    --recover regex --recover-prompt prompts/recover_micro_v2.txt \
    --split test_fresh5 --metric weighted --workers 3 --out /tmp/x.json
  ```
- Swimcast adoption design (in the OpenSwimPodcast repo):
  `docs/smart-processing/DESIGN_GEPA_ADOPTION.md`, `OVERNIGHT_BUILD_PLAN.md`

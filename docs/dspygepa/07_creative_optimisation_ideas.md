# 07 - How else can we optimise? (a very creative ideas dump)

A deliberately wide, deliberately bold brainstorm of ways to push the detector further -
beyond the obvious "more data / bigger model / more prompt tuning". Three sources fed this,
and each idea is tagged with where it came from so attribution stays clean:

- **[DG]** - dspygepa (this session's own ideas)
- **[G5]** - GPT-5 (xhigh), consulted 15 Jun 2026
- **[RES]** - the online GEPA-practitioner research survey (links inline)

> Nothing here is committed work - it's a menu. The ranked shortlist at the bottom is the
> honest "what I'd actually try next". As always: no verbatim transcript in this file.

---

## The reframe that organises everything

Both GPT-5 and I converged, independently, on the same thesis, and it's worth stating up
front because it reorganises the whole problem:

> **Stop building "an ad detector". Build "a machine that refuses to cut unless it can prove
> the cut is safe."**  [G5 + DG]

Under `score = recall * 0.5^(fp_sec/15)`, an unsupported free-form span is radioactive. The
30-minute "find the ad spans" task is *too unconstrained* for this metric - it invites the
model to guess, and a wrong guess is exponentially expensive. The whole system should be
biased so the LLM is demoted from *primary detector* to *candidate explainer / expander /
verifier*, and every cut carries its own evidence. The recovery pass ([01](01_recovery_approach.md))
was the first step in this direction (anchor on certainty, expand toward ambiguity); the ideas
below push it much further.

A second, more contrarian reframe worth holding in tension with the first:

> **"Recover the whole missed ad" may be the wrong instinct.** If an ad's opening is native
> and ambiguous, cut the terminal/core and *leave the risky shoulder*. Missing 20s of ad is
> usually cheaper than clipping 5s of real content.  [G5]

That directly questions the recovery thesis. It doesn't kill it - it argues for a *safe-core*
version of recovery (cut what you can defend, hold the rest). See B3.

---

## Part A - Data signals we are simply not using (the biggest untapped wins) [mostly DG]

These are the ideas I'm most excited about, because they sidestep the labelling bottleneck
entirely and are copyright-safe (timestamps and hashes, never transcript text).

**A1. Dynamic-Ad-Insertion (DAI) self-diff - free perfect labels.** [DG]
Modern podcast ads are *dynamically inserted at download time*. Download the **same episode
several times** (or from several IPs/at intervals) and **diff the audio**: the segments that
*change between downloads* are the inserted ads; the segments that stay identical are the
host content. This is near-ground-truth ad localisation with **zero human labelling**,
language-independent, and it scales to thousands of episodes. It only misses *baked-in*
host-read ads (which don't vary) - but those are exactly what the LLM detector is good at, so
the two are complementary. *Payoff: huge recall + a free golden corpus. Cost: download
plumbing + acoustic diff; some shows don't use DAI.*

**A2. Free-feed vs ad-free-feed differential labelling.** [DG]
Many shows publish both an ad-supported public feed and an **ad-free feed** (Patreon,
Supercast, Apple subscriptions). Align the two versions of the same episode; the **time-gaps
the ad-free version removes are labelled ads, for free**. Same idea as A1 but catches
baked-in reads too, and gives boundary-accurate spans. Store only the offset map, never the
audio/text. *Payoff: a large, accurately-bounded golden set across many shows = directly
attacks the val->test gap by widening show diversity cheaply. Cost: sourcing paired feeds.*

**A3. Chapter markers / ID3 / show-notes mining.** [DG]
A surprising number of feeds ship **chapter markers** and rich ID3 metadata; some literally
label "Advertisement" or section boundaries, and show-notes often list sponsors by name.
This is structured signal we currently ignore. Use chapter boundaries as **free anchor
candidates** for mid-rolls, and the sponsor list as a **named-brand prior**. *Payoff:
cheap recall + boundary anchors. Cost: parsing; coverage varies.*

**A4. Loudness / LUFS discontinuity fingerprint.** [DG, sharpening G5's audio-discontinuity idea]
Inserted ads are mastered to a *different loudness target* than the host mix. A cheap,
language-free **loudness-jump detector** flags insertion seams. Pairs beautifully with A1
(DAI seams are loudness seams). *Payoff: boundary precision + corroboration, very low FP.
Cost: small DSP pass.*

**A5. Cross-episode / cross-show "ad bank" by embedding or hash.** [DG + G5's template memory]
The big network sponsors (NordVPN, BetterHelp, Squarespace, ZipRecruiter, ...) recur across
*thousands* of shows with near-identical reads. Maintain a **bank of embeddings / SimHashes
of confirmed sponsor reads, intros, outros, catchphrases**. A candidate near a known centroid
is high-confidence ad. Copyright-safe (store vectors/hashes, not text). GPT-5 framed this as
per-show template memory; I'd add a **shared cross-show bank** on top. *Payoff: big recall +
low FP once seeded. Cost: needs a paired "negative memory" so recurring *content* segments
(a weekly quiz, a regular listener-questions bit) aren't falsely matched.*

---

## Part B - Inference-time architecture (proof-carrying, anchor-first) [G5-led, DG additions]

**B1. Proof-carrying cuts.** [G5]
Every cut must emit a structured proof: `start_quote`, `end_quote`, `evidence_quote` (the
actual sell), `keep_before_quote`, `keep_after_quote`, cut-type, and the external
beneficiary/action. A **deterministic validator** rejects any proof whose quotes aren't
unique-mappable or whose evidence is absent. No proof, no cut. *Payoff: big FP drop + boundary
gains. Cost: latency, schema work, drops some true ads.* This is GPT-5's #1 and it's strong.

**B2. No free-floating cuts - anchor-first generation.** [G5, generalises our recovery]
The model may not propose arbitrary spans over a 30-min window. First generate **candidate
anchors** (hard terminal, hard opener, audio break, repeated template, intro/outro position),
then only *expand or trim* around an anchor. This is the recovery pattern promoted to the
*whole* pipeline, not just the miss-recovery pass. *Payoff: big FP drop. Risk: recall depends
on anchor-library breadth - so invest in the anchor lattice (B7).*

**B3. Safe-core vs unsafe-shoulder labels.** [G5]
Output a "definitely cut" **core** plus "probable-ad-but-unsafe" **shoulders**. Auto-cut the
core; only extend into a shoulder when multiple proofs support it. This is the safe-core
answer to the recovery-vs-precision tension above. *Payoff: big FP drop, modest recall cost.*

**B4. Delete-and-join coherence test.** [G5]
For each candidate, ask: *if this span is removed, do the surrounding lines join coherently?*
Ads/faff are **removable islands**; real content leaves a gap when excised. *Payoff: kills the
product-discussion and parody false positives (a tech show discussing a product doesn't excise
cleanly). Risk: native host-read ads can also join coherently.*

**B5. Staggered-window intersection (cut the intersection, not the union).** [G5]
Run the detector on **offset windows** (e.g. 30-min and a local 8-min pass). For soft
candidates, cut only the **intersection** of what both passes flag. We currently *union*
recovered spans; intersecting soft ones is the precision-mirror of that. *Payoff: FP down,
boundaries tighter. Cost: ~2x runtime.*

**B6. Kept-neighbour boundary quotes.** [G5]
Force the model to quote the **last kept content before** and **first kept content after** the
cut. Directly attacks over-extension (the over-extended-outro failure mode). *Payoff: boundary
FP down. Cost: tiny schema bump.* Cheap and I'd ship it early.

**B7. Terminal lattice, not terminal regexes.** [G5, extends our hard/soft split]
Generalise the hard/soft terminal split ([03](03_hard_soft_terminal_split.md)) into a full
**evidence lattice**: promo code, paid signup, legal/"terms", imperative URL, owned-channel
ask, network promo, affiliate phrase, ... each with *required proof*, *optional corroboration*,
*max-duration prior*, and *vetoes*. The hard/soft split is the v0 of this. *Payoff: controlled
recall gains. Cost: rule maintenance.*

**B8. Ensemble of *representations*, not just samples.** [DG]
Self-consistency usually means "sample the same prompt N times". More powerful here: run the
decision over **heterogeneous representations** of the same window - (a) raw transcript, (b) a
*dialogue-act skeleton* (each sentence replaced by its act tag: question / pitch / disclaimer
/ CTA), (c) the audio-event track (A4). Flag only where representations **agree**. Diversity
of *representation* catches failure modes that diversity of *samples* can't. *Payoff: FP down
with less recall cost than naive voting. Cost: build the skeleton transform.*

**B9. Episode-level set-selection with an FP budget.** [G5]
Don't accept each span independently. Treat the candidate set as a **constrained optimisation**:
maximise expected metric subject to an **FP-risk budget** for the episode. Spend the budget on
the highest-confidence cuts first. *Payoff: principled FP control. Needs: calibrated
per-candidate confidence (see E1).*

---

## Part C - Audio as a first-class signal [G5 + DG]

We are a text-only detector today. Audio is a huge, cheap, language-independent corroboration
layer and several ideas above lean on it.

**C1. Repeated-audio fingerprints across episodes.** [G5] Local acoustic fingerprints catch
DAI ads repeated across shows even when ASR is poor or transcripts differ. (A1 is the
same-episode version.)

**C2. Audio-discontinuity layer.** [G5] Music beds, stingers, compression/loudness changes
(A4), room-tone and cadence shifts - use as corroboration or to **snap** boundaries.

**C3. Forced alignment *only near boundaries*.** [G5] Don't re-segment the whole episode. Run
forced alignment on **±20s around candidate boundaries** to snap cuts to word edges / silences.
This is the audio cousin of our char-interpolation trick ([04](04_granularity_char_interp.md)):
cheap precision exactly where it's needed. *Payoff: boundary FP down. Cost: CPU near boundaries
only.*

**C4. Speaker/persona anomaly.** [G5] Per-speaker baselines for pronoun use, cadence, direct
address, scriptedness; sponsor reads often flip into "you should..." monologue mode. *Payoff:
recall on disguised openings. Risk: recaps/monologues mimic it.*

---

## Part D - The optimiser problem (why GEPA overfits, and what to do) [RES + G5 + DG]

The research survey was blunt: **our val->test gap is the textbook GEPA failure mode**, and
there are known mitigations. (Sources linked.)

**D1. Shrink to 20-100 examples and CAP prompt length.** [RES]
Decagon found 20-100 examples *consistently beat* 500; 500 caused ~75% prompt bloat for ~2%
*worse* performance, because GEPA's reflection "accumulates observations" and memorises edge
cases. A ~1,500-char cap gave 4x compression for 0.8% loss - **length caps act as explicit
regularisation**. This also explains why our hand-written, concise, principle-based checklist
beat GEPA. *Apply: cut the trainset, cap the evolved prompt length.*
[Decagon](https://decagon.ai/blog/optimizing-gepa-for-production)

**D2. Optimise for WORST-family / CVaR, not validation mean.** [G5 + RES]
GEPA winning on val and losing on test "screams" for ranking candidates by **worst show-family
or bottom-quartile score**, not the mean. *Apply: change candidate selection to maximise the
minimum per-family held-out score.* This is the single most on-the-nose fix for our exact
symptom. [G5; corroborated by HN OOD-brittleness notes,
[HN](https://news.ycombinator.com/item?id=44744331)]

**D3. Put the asymmetry into the *words* of the feedback, not just the scalar.** [RES]
The DSPy backdoor-monitor tutorial literally encodes "avoid false positives" in the textual
feedback the reflector reads. Our `recall * 0.5^(fp/15)` scalar throws away *why*. Return
`dspy.Prediction(score, feedback)` that **enumerates** TP-seconds caught, FP-seconds flagged
(with the offending span quoted), and FN ads missed, and **states the penalty in plain
language** ("15 FP-seconds halves the score; only flag on unambiguous sponsor+CTA+promo
markers"). *Apply: rewrite our GEPA feedback function to be verbose and asymmetric.*
[trusted-monitor](https://dspy.ai/tutorials/gepa_trusted_monitor/),
[structured-extraction](https://dspy.ai/tutorials/gepa_facilitysupportanalyzer/)

**D4. Checkpoint every candidate; select on held-out shows; expect an EARLY peak.** [RES]
Test accuracy often peaks at GEPA steps ~4-7 then degrades, and runs are high-variance. Use
`track_stats=True`, harvest *all* candidates, re-score them yourself on held-out shows, run 3+
seeds, keep the early generaliser. *Apply: never take GEPA's val-best final prompt at face
value.* [DSPy GEPA Overview](https://dspy.ai/api/optimizers/GEPA/overview/)

**D5. Seed GEPA with the champion and constrain it to PRUNE, not expand.** [RES + DG]
The hand-written checklist wins because it's principle-based. So let GEPA only *tighten/prune*
it (delete show-specific folklore), never add. Combined with the length cap (D1), this keeps
the generaliser and lets GEPA do boundary polish. *Apply: custom instruction proposer that can
only shorten.* [Decagon + GEPA Advanced](https://dspy.ai/api/optimizers/GEPA/GEPA_Advanced/)

**D6. Synthetic hard-negative regression suite (not training bulk).** [G5 + RES]
Generate adversarial **negatives**: product launches, parody ads, fake promo-code jokes,
"subscribe to our YouTube" source links, ad-shaped news copy. Use them as a **regression gate**
the detector must pass, *not* as training data (synthetic artefacts mislead if over-weighted).
This is how you stop whack-a-mole regressions. *Apply: a fixed adversarial test the threedom
parody case is the first member of.* [G5; RES on hard negatives & whack-a-mole]

**D7. A/B GEPA against MIPROv2 0-shot and BootstrapFewShot+hard-negatives.** [RES]
GEPA isn't the only optimiser. MIPROv2's Bayesian instruction search may overfit less; a
couple of hand-picked **hard-negative few-shot demos** (content that looks ad-like) is a
classic asymmetric-cost lever. *Apply: bake-off on the same held-out shows.*
[DSPy optimizers](https://github.com/stanfordnlp/dspy/blob/main/docs/docs/learn/optimization/optimizers.md)

**D8. Tolerant metric for boundary near-misses.** [RES]
Give the metric a ±1-2s boundary tolerance so the reflector isn't fed harmless boundary
variation as "errors" (which makes it overfit exact positions). [Lee Butterman, "DSPy on a
Pi"](https://leebutterman.com/2025/11/01/prompt-optimization-on-a-raspberry-pi.html)

---

## Part E - Calibration and the metric itself [DG]

**E1. Conformal abstention = a *provable* FP budget.** [DG]
Wrap the detector in a **conformal-prediction** layer calibrated on the golden set: it yields a
statistically guaranteed false-positive rate at a chosen confidence. Because our pain is
*exactly* a false-positive budget, this lets us **dial the abstention threshold to a provable
FP target** instead of hand-tuning a 45s cap. The most principled possible answer to the
exponential gate. *Payoff: guaranteed FP control + a clean confidence signal for B9. Cost:
calibration set management; needs a per-candidate score to conformalise.*

**E2. Positional density prior.** [DG]
Ads cluster at predictable positions (pre-roll 0-2 min, mid-rolls near natural breaks /
chapter markers, post-roll). Learn a **positional prior** over ad density and use it as a cheap
multiplicative prior on candidate confidence. Mid-rolls often coincide with chapter markers
(A3). *Payoff: cheap recall + FP shaping. Cost: trivial; risk of show-specific position quirks.*

**E3. The metric is a proxy - learn the real one from the only user who matters.** [DG]
`recall * 0.5^(fp/15)` is a stand-in for "did the swim feel clean?". The real objective is
**David's own restore/skip behaviour**. Every time he restores a cut or manually skips a
segment, that's a labelled preference. Treat it as **active learning / a contextual bandit on
the one-user distribution** that actually counts. *Payoff: the system optimises the true target
and personalises. Cost: UI plumbing (the Swimcast review gate already captures most of it).*

---

## Part F - Learning loops [DG + G5]

**F1. User-local correction memory.** [G5] When the user restores a cut or skips something,
store local hashes/features as show-specific hard negative/positive evidence. (The product hook
for E3.)

**F2. Adversarial self-play / red-team co-evolution.** [DG] One model **generates** content
designed to fool the detector (parody ads, ad-shaped news, fake promo jokes); the detector must
not bite; the survivors become D6's regression suite. Co-evolve generator and detector. *Payoff:
a self-renewing hard-negative stream. Risk: drift toward unrealistic adversarial artefacts -
keep a human spot-check.*

**F3. Distil the optimised behaviour into the local model.** [RES] Once the prompt+pipeline is
good, `BootstrapFinetune` the local gemma on its own best outputs so quality lives in weights,
not in a long prompt (precedent: a Shopify GPT-5 -> small-Qwen -> GEPA pipeline reported ~75x
cheaper / ~2x more reliable, second-hand). *Payoff: speed + shorter prompt + maybe better
generalisation. Cost: a finetuning pipeline; QAT-model finetuning is fiddly.*

**F4. Specialist detectors per cut class.** [G5] Separate policies (and evidence thresholds)
for sponsor ads vs intros vs outros vs housekeeping vs cross-promos vs recaps. Different
classes have very different priors and proofs. *Payoff: precision on each class. Cost: more
moving parts.*

---

## Where the two advisors disagreed with us (keep honest)

- **GPT-5 thinks recovery may be the wrong instinct** - prefer cutting the defensible core and
  leaving the ambiguous shoulder (B3) over reconstructing the whole disguised ad. Worth taking
  seriously: it's the safe-core counter-thesis to [01](01_recovery_approach.md).
- **GPT-5 would demote the LLM** from primary detector to verifier/expander over a deterministic
  anchor+proof scaffold (B1/B2). That's a bigger architectural bet than our current
  prompt-centric design.
- **The research is blunt that our hand-written-beats-GEPA result is the *expected* outcome**,
  not a fluke - GEPA "found validation-show folklore". The fix isn't to abandon GEPA but to
  change *what it optimises* (worst-family + asymmetric verbal feedback + length cap + prune-only).

---

## Ranked shortlist - what I'd actually try next

If we could only run a handful, in rough order of expected-value-per-effort:

1. **DAI self-diff + ad-free-feed differential labelling (A1 + A2).** [DG] The single highest-
   leverage move: it manufactures a large, accurately-bounded, copyright-safe golden corpus
   across many shows for almost no labelling cost - which simultaneously attacks the val->test
   gap (more show diversity) *and* feeds every other idea here. Start here.

2. **Cheap, shippable FP-killers: kept-neighbour boundary quotes + delete-and-join coherence +
   staggered-window intersection (B6 + B4 + B5).** [G5] Low-effort, directly target the
   over-extension / parody / product-discussion failure modes, and need no retraining.

3. **Conformal abstention for a provable FP budget (E1).** [DG] The most principled answer to
   the exponential gate - replaces the hand-tuned 45s cap with a statistical guarantee and
   gives B9 the confidence signal it needs.

4. **Fix the optimiser, don't abandon it: worst-family selection + asymmetric verbal feedback +
   length cap + prune-only seeding (D2 + D3 + D1 + D5).** [RES] If we ever run GEPA again, this
   bundle is what would make it transfer instead of overfit.

5. **Audio corroboration layer: loudness/DAI seams + boundary-only forced alignment (A4 + C3).**
   [DG + G5] Language-independent, cheap, and turns boundary precision from a guess into a
   measurement.

Honourable mention worth prototyping for its sheer leverage if A1/A2 prove easy: the
**cross-show ad bank (A5)** - once seeded from the differential corpus, it's a high-precision,
copyright-safe recall engine.

---

*Consulted 15 Jun 2026: GPT-5 (xhigh) via ask-gpt5; an online GEPA-practitioner research
survey (links inline). Synthesis and the Part A / Part E ideas are dspygepa's. See
[06_open_levers_and_lessons.md](06_open_levers_and_lessons.md) for the nearer-term, already-
scoped levers.*

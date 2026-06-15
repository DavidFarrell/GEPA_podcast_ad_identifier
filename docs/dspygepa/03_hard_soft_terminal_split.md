# 03 - The hard/soft terminal split (recovery precision guard)

## The failure it fixes

When the recovery pass was cross-validated on Swimcast's 9-show golden corpus, it added
+8pts ad-recall but +54.7s of false positives - and **almost all of that FP was on one
show** (dtns, +52.5s), plus a small trailing case on trip_us (+2.2s).

The dtns false positives were `youtube.com/<brand>` links - PCMag/CNET reading out their
own YouTube channels. The trip_us case was an outro sign-off back-expanded as a
"Rest is Politics" podcast cross-promo.

## Why these are *not* model bugs

This is the subtle and important part. `recover_micro_v2` is **correctly** told to recover
network/channel cross-promos:

> "A promo for the show's OWN network, a sister/partner podcast, a network app or
> subscription, or a network contest/giveaway IS an ad - recover it."

That instruction exists because **the GEPA golden policy counts network/self-promo as faff**
(David explicitly put network-promo on the faff list). So on the GEPA corpus, recovering a
channel cross-promo is *right*. The model obeyed its instructions.

The dtns golden labels simply *don't* mark those channel mentions as ads. So this is a
**labelling-policy divergence** between the GEPA corpus and a content-preserving deployment
like Swimcast - not a precision bug in the model or the prompt.

For Swimcast's never-cut-real-content bar, gating these out is the right call. For the GEPA
corpus's scoring, leaving them in is the right call. The split lets one mechanism serve both.

## The guard

Classify terminal signals (deterministically, in `anchors.py` - **not** in the prompt) into
two buckets:

**HARD commercial** - fire recovery on its own:
- promo code, percentage off, explicit offer, "terms apply",
- giveaway-with-entry, signup to a paid service,
- sponsor read with a named brand + a purchase/subscribe CTA.

**SOFT** - do **not** fire alone; require *corroboration* (a HARD terminal in the same
cluster, OR overlap with a first-pass hit):
- a bare URL / spoken URL to a social or video host (youtube / instagram / x / tiktok /
  facebook),
- a podcast cross-promo ("subscribe to our other show"),
- an app CTA with no offer,
- a bare sponsor *mention* with no sell.

This kills dtns (all bare channel links) and the trip_us cross-promo while **keeping** the
threedom / news_agents / fresh5 wins, because those terminate on real offers/codes (HARD).

GPT-5 independently landed on the same hard/soft split.

## The trap to avoid: do NOT require first-pass overlap globally

Swimcast initially considered a simpler guard: "a recovered span must overlap a first-pass
hit." **Do not apply this globally.** Recovery's *headline value* is the fresh5 **complete
misses** - ads the first pass missed *entirely*, which by definition do **not** overlap any
first-pass hit. A global overlap requirement would silently delete exactly the wins that beat
the champion on the held-out exam ([01](01_recovery_approach.md)).

Use overlap **only** as the SOFT-terminal fallback (one of the two ways a soft terminal can
earn corroboration). HARD-terminal recovery must be allowed to fire on complete misses with
no overlap - that is the whole point.

## Net policy

- **HARD-terminal recovery ships ON** - precise, and catches the complete misses.
- **SOFT-terminal recovery requires corroboration** - kills the dtns/channel-link FPs.

This is the design baked into the deferred Swimcast recovery phase
(`DESIGN_GEPA_ADOPTION.md`). The implementation lever is the `anchors.py` pattern set: tag
each `_PATTERNS` entry HARD or SOFT, and have `cluster_anchors` (or the `recover` dispatch)
gate SOFT-only clusters behind corroboration.

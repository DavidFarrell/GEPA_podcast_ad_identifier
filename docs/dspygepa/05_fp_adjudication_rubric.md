# 05 - The cardinal-rule FP adjudication rubric

Overnight on 14 Jun, swimcast built the adoption to completion autonomously, using **GPT-5**
and **dspygepa** as adjudicators in David's place for every cardinal-rule false-positive call
(real-content-cut = stop / boundary-slop = ok). This is the rubric dspygepa locked with
swimcast *before* the calls started, so judgments stayed consistent and only genuine
borderline cases cost a round-trip.

## Governing law

`score = recall * 0.5^(fp_sec/15)`. **Cutting real content is far worse than missing an ad.**
Therefore:

- Every tie breaks toward **KEEP**.
- A genuine 50/50 = **HOLD** (route to review; never ship as a cut), never an auto-CUT.

## The four tests

1. **SELL vs DISCUSS** (the most common trap). Is the brand being *sold* - offer / code /
   CTA, the show *stops* to pitch - or *discussed* as the episode's subject (explains how it
   works, its news, its merits)? Discussed = CONTENT = keep, **even with a URL / model-card /
   repo link**. (Canonical keep: a tech/news show covering a product release as its topic.)

2. **Cross / network promo.** A bare "subscribe to our other show / follow us on YouTube"
   woven into content = **SOFT** = keep/hold. A network promo with a real CTA or offer
   attached = cut. (Matches the hard/soft terminal split, [03](03_hard_soft_terminal_split.md).)

3. **Boundaries.** Prefer the **later** start and the **tighter** cut. A few seconds of ad
   left in is fine; one second of real content cut is not. If a sponsor read shares a turn
   with content, cut only the sold portion (this is where char-interpolation,
   [04](04_granularity_char_interp.md), earns its keep).

4. **Ambiguous conversational-ad banter** (host riffs that blur into a plug; the
   Comedy-Bang-Bang-plug style). **HOLD, do not auto-cut.** In the GEPA corpus these are
   scored as *excluded* "ambiguous zones" precisely because they aren't clean cuts.

Operational format used: swimcast sends each borderline case as a transcript excerpt with
~60s of context each side, the proposed cut span marked; dspygepa returns **CUT / KEEP /
HOLD + one line**.

## The one adjudication that came up: the threedom parody

Across the entire Phase-2 head-to-head, the new detector auto-applied exactly **one** false
positive - a ~12s span on threedom (a comedy improv podcast).

*(Paraphrased, not quoted - the repo keeps verbatim transcript out of committed files.)* In
the flagged span the hosts are doing a **comedy bit**: narrating the experience of watching
TV/YouTube and hitting commercials - mimicking a KFC ad (riffing on the "finger lickin good"
slogan), a Gran Turismo film trailer - and joking about skipping ads, then segueing straight
into genuinely *discussing* the Gran Turismo movie (a Clint Eastwood / "Gran Torino" mix-up
joke).

The detector fired on surface tokens ("KFC ads", "commercial", "skip ads"). But:

- There is **no sponsor**, no offer, no code, no CTA, no "brought to you by".
- Nobody is *selling* anything - the hosts are *parodying* ads as content.
- It flows directly into real episode content (the movie discussion).

**Verdict: KEEP** (confident, not even HOLD). It fails the SELL test outright and is exactly
rubric #1 + #4. On a comedy improv pod, this meta-riffing *is* the episode; cutting 12s of it
is a clean cardinal-rule violation. GPT-5 independently ruled the same, and both said **ship
anyway** - one non-systematic outlier against an 88-second safety gain. Logged as the single
known residual.

**Lesson:** a detector keying on lexical ad-tokens will always bite on shows that *talk
about* ads (comedy, media-criticism, marketing podcasts). The durable defence is the SELL-vs-
DISCUSS test, not a token blocklist.

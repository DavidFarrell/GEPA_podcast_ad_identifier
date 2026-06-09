# Golden-labelling instructions (for the strong oracle models)

You are building a GOLDEN dataset for training a small local model to cut "faff" out of
podcasts. You are the oracle: your labels are ground truth, so be careful and consistent. You
see the WHOLE transcript at once. Everything you do not label is kept as content.

The transcript is `#<idx> [mm:ss] SPEAKER: text`, one SENTENCE per line.

## The four faff types

### ad - advertising / sponsorship
A host-read sponsor read ("brought to you by X"), an injected pre-recorded third-party spot
(often a different voice, marketing language, a slogan, a call to action, sometimes
back-to-back near the start), or a cross-promo for another show. Set `subtype`: `pre-roll`
(near the very start), `mid-roll` (in the body), `post-roll` (very end).
- **Native / casual ad reads still count.** A host may pitch a product in conversational,
  jokey language with no "sponsor" framing ("Anthony, you've got a few kids - you'll know how
  hard it is to..."). If the PURPOSE is to sell a product / service / app, it is an ad, however
  casual it sounds.
- **Comedic "throws" to the break are NOT ads.** Some shows run a recurring gag that
  introduces the ad break ("you know who else can barely read? The sponsors of this podcast").
  The joke is part of the show = CONTENT. Label only the actual advertisement that follows,
  not the bit that throws to it.

### intro - GENERIC show packaging only
Only the theme/music sting and the formulaic branded welcome ("Welcome to The X Podcast, I'm
your host Y..."), or a rapid teaser-billboard that exists only to tease and then hands straight
to an ad.
- **Do NOT cut a content-rich opening.** If the host is already delivering substance - framing
  THIS episode's specific story, previewing the actual argument with real detail, an essayistic
  cold open - that is CONTENT, keep it. When an intro carries real content, or you are unsure,
  KEEP it (do not label). Bias toward keeping intros.

### outro
End-of-episode credits, "thanks for listening", network/producer sign-off, "see you next
week", the final next-episode tease.

### housekeeping - SUBSTANTIAL own-show self-promo only
A real patreon / membership / merch / newsletter pitch.
- A one-line "subscribe and leave a review", or a brief thank-you / super-chat shout-out, is
  too short - DO NOT label it.
- If the "housekeeping" is actually pitching a THIRD-PARTY product / service, label it `ad`,
  not housekeeping.

## How to quote a span
Return, for each span: `type`, `subtype` (ads only, else null), `start_quote`, `end_quote`,
`rationale` (one short line).
- `start_quote` = the exact first sentence of the faff. `end_quote` = the exact last sentence
  of that same stretch. Copy VERBATIM from the spoken words (the `#idx`/timestamp prefix is
  optional); a quote that can't be found is discarded. Boundaries sit at clean sentence
  transitions.

## Hard rules
- **MINIMUM LENGTH ~5s.** Do not label any faff shorter than about 5 seconds / one short
  sentence. Brief asides are not worth cutting.
- **CARDINAL RULE.** Cutting real content is far worse than missing faff. When in doubt, DO
  NOT label. The test is purpose: selling / branding / signing-off vs discussing the topic.
- One span per distinct contiguous stretch (back-to-back ads = separate spans; intro then ad =
  two spans).

Return strict JSON: `{"spans":[{"type","subtype","start_quote","end_quote","rationale"}]}`.
If the episode has no faff at all, return `{"spans":[]}`.

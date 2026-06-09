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
- **Any promotion of a THIRD-PARTY product / service / brand is an ad** - including one that
  opens with casual personal chat before the pitch. TRIP US example: "Anthony, you have a few
  kids. I imagine you're looking forward to Father's Day..." leading into a product is an ad -
  label it from the casual lead-in through the end of the pitch. If the PURPOSE is to sell, it
  is an ad, however conversational or jokey it sounds.
- **Comedic "throws" to the break are NOT ads.** Some shows run a recurring gag that
  introduces the ad break ("you know who else can barely read? The sponsors of this podcast").
  The joke is part of the show = CONTENT. Label only the actual advertisement that follows,
  not the bit that throws to it.

### intro - PURELY GENERIC packaging only (rare)
Label `intro` ONLY for a stretch that is pure show packaging conveying NOTHING about this
specific episode: a standalone theme/music sting, a bare branded welcome ("Welcome to The X
Podcast, I'm your host Y, the show where we...") with no episode specifics, or a "back after
the break" bumper.
- **A "this week on the show..." / "coming up today..." billboard that names this episode's
  actual topics or guests is CONTENT - KEEP it**, even though it sounds like an intro. Hard
  Fork example to KEEP: "This week: SpaceX, Anthropic and OpenAI are heading to the public
  markets - but what do their IPOs mean? Then author Kevin Hartnett on why mathematicians are
  sounding the alarm about AI." That conveys real information about the episode = content.
- The host names + "and this is The X Show!" on its own is usually <5s and bleeds straight
  into the billboard/content - in that case do NOT label it.
- When in any doubt, KEEP the intro. Cutting a content-bearing intro is the cardinal sin.
  In practice you will rarely label an intro.

### outro
End-of-episode credits, "thanks for listening", network/producer sign-off, "see you next
week", the final next-episode tease.

### housekeeping - SUBSTANTIAL own-show self-promo only
ONLY the show promoting ITSELF: a real patreon / membership / merch / newsletter / spin-off
pitch.
- A one-line "subscribe and leave a review", or a brief thank-you / super-chat shout-out, is
  too short - DO NOT label it.
- If it promotes anything EXTERNAL (a third-party product, service, or brand), it is an `ad`,
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

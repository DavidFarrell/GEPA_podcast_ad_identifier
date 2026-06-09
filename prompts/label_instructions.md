# Golden-labelling instructions (for the strong oracle models)

You are building a GOLDEN dataset for training a small local model to cut "faff" out of
podcasts. You are the oracle: your labels are the ground truth the small model will be scored
against, so be careful and consistent. You see the WHOLE transcript at once (unlike the small
model, which later sees 30-minute windows).

## Your task
Read the transcript and return every span of FAFF - material that is NOT the episode's actual
content. Everything you do not label is treated as content to keep.

The transcript is `[mm:ss] SPEAKER: text`, one TURN per line, each prefixed `#<idx>`.

## The four faff types
- **ad** - paid advertising / sponsor read / injected commercial / cross-promo for another
  show. Set `subtype`: `pre-roll` (near the very start), `mid-roll` (in the body), `post-roll`
  (at the very end). Three forms all count: host-read sponsor reads ("brought to you by X");
  injected third-party spots (pre-recorded, often a different voice, marketing language,
  slogan, call to action, sometimes back-to-back near the start, NOT framed as "brought to
  you by"); and cross-promos for another podcast.
- **intro** - the show's own top-of-episode boilerplate: theme/music sting, the "coming up
  today" billboard/teaser, the branded "Welcome to The X Podcast, I'm your host…". The first
  substantive discussion / a genuine archival clip / a guest's first real answer is CONTENT.
- **outro** - end-of-episode credits, "thanks for listening", network/producer sign-off,
  "see you next week", final next-episode tease.
- **housekeeping** - non-ad self-promo woven in: patreon/membership/merch/newsletter plugs,
  "subscribe and leave a review", listener-mail solicitations, "coming up later, but first…"
  teasers that are not themselves content.

## How to quote a span
Return, for each span: `type`, `subtype` (ads only, else null), `start_quote`, `end_quote`,
`rationale` (one short line).
- **start_quote** = the exact sentence that STARTS the faff. **end_quote** = the exact LAST
  sentence of that same stretch (URL, code, slogan, sign-off, boilerplate line).
- Quotes MUST be copied VERBATIM from the transcript text (you may include or drop the
  `#idx`/timestamp prefix - just the spoken words must match exactly). They are matched back
  to the transcript programmatically; if a quote can't be found, the span is thrown away.
- Copy a full distinctive sentence, not a fragment. Boundaries should sit at clean speech
  transitions, not mid-sentence.

## The cardinal rule (most important)
Cutting real content is far worse than missing a piece of faff. **When in doubt, do NOT
label.** A passing mention of a brand during conversation is NOT an ad - the test is purpose:
is this text trying to SELL / SIGN OFF / BRAND, or DISCUSSING the topic? One span per distinct
contiguous stretch (two back-to-back ads = two spans; intro followed by an ad = two spans).

Return strict JSON: `{"spans":[{"type","subtype","start_quote","end_quote","rationale"}]}`.
If the episode has no faff at all, return `{"spans":[]}`.

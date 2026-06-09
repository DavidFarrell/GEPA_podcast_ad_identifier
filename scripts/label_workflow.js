export const meta = {
  name: 'golden-label-podcast-faff',
  description: 'Label ad/intro/outro/housekeeping spans in podcast transcripts: Sonnet labels each, Opus independently relabels + adjudicates',
  phases: [
    { title: 'Label (Sonnet)', detail: 'one Sonnet agent per episode reads the transcript and quotes every faff span' },
    { title: 'Adjudicate (Opus)', detail: 'one Opus agent per episode independently relabels and reconciles against Sonnet' },
  ],
}

// args: { repo: "/abs/path/to/project", ids: ["episode_id", ...] }
// Falls back to pilot defaults if args is not provided.
const A = (typeof args !== 'undefined' && args) ? args : {}
const REPO = A.repo || '/Users/david/git/ai-sandbox/projects/GEPA_podcast_ad_identifier'
const IDS = (A.ids && A.ids.length) ? A.ids : [
  'threedom__i_see_both', 'lennys__rational_ai', 'tesd__679_icons',
  'ppf__dispossessed', 'thursdai__nemotron', 'trip_leading__control_ai',
  'news_agents_usa__j6_slush', 'btb__fuhrman_part2', 'trip_us__losing_streak',
  'dtns__do_people_hate_tech',
]

const INSTRUCTIONS = `You are building a GOLDEN dataset for training a small local model to cut "faff" out of podcasts. You are the oracle: your labels are ground truth. You see the WHOLE transcript at once. Everything you do not label is kept as content.

The transcript is "#<idx> [mm:ss] SPEAKER: text", one SENTENCE per line.

FOUR faff types:

"ad" - advertising / sponsorship: a host-read sponsor read ("brought to you by X"), an injected pre-recorded third-party spot (often a different voice, marketing language, slogan, call to action, sometimes back-to-back near the start), or a cross-promo for another show. Set subtype: "pre-roll" (near the very start), "mid-roll" (in the body), "post-roll" (very end).
  - ANY promotion of a THIRD-PARTY product/service/brand is an ad - including one that opens with casual personal chat before the pitch. TRIP US example: "Anthony, you have a few kids. I imagine you're looking forward to Father's Day..." leading into a product is an ad - label it from the casual lead-in through the end of the pitch. If the PURPOSE is to sell, it is an ad, however conversational it sounds.
  - COMEDIC "throws" to the break are NOT ads. Some shows run a recurring gag that introduces the ad break ("you know who else can barely read? The sponsors of this podcast"). The joke is part of the show = CONTENT. Label only the actual advertisement that follows, not the bit that throws to it.

"intro" - PURELY GENERIC packaging ONLY (rare): a standalone theme/music sting, a bare branded welcome ("Welcome to The X Podcast, I'm your host Y...") with NO episode specifics, or a "back after the break" bumper.
  - A "this week on the show..." / "coming up today..." BILLBOARD that names this episode's actual topics or guests is CONTENT - KEEP it, even though it sounds like an intro. Hard Fork example to KEEP: "This week: SpaceX, Anthropic and OpenAI are heading to the public markets - what do their IPOs mean? Then author Kevin Hartnett on why mathematicians are sounding the alarm about AI." That conveys real episode information = content.
  - The host names + "and this is The X Show!" on its own is usually <5s and bleeds straight into the billboard/content - do NOT label it.
  - When in any doubt, KEEP the intro. Cutting a content-bearing intro is the cardinal sin. You will rarely label an intro.

"outro" - end credits, "thanks for listening", network/producer sign-off, "see you next week", final next-episode tease.

"housekeeping" - ONLY the show promoting ITSELF: a real patreon/membership/merch/newsletter/spin-off pitch.
  - A one-line "subscribe and leave a review", or a brief thank-you / super-chat shout-out, is too short - DO NOT label it.
  - If it promotes anything EXTERNAL (a third-party product/service/brand), it is an "ad", not housekeeping.

For each span return: type, subtype (ads only, else null), start_quote, end_quote, rationale (one short line).
- start_quote = the exact first sentence of the faff. end_quote = the exact LAST sentence of that same stretch. Copy VERBATIM (the #idx/timestamp prefix is optional); an unfindable quote is discarded. Boundaries sit at clean sentence transitions.

RULES:
- MINIMUM LENGTH ~5s: do not label any faff shorter than about 5 seconds / one short sentence. Brief asides are not worth cutting.
- CARDINAL RULE: cutting real content is far worse than missing faff. When in doubt, DO NOT label. The test is purpose (selling / branding / signing-off vs discussing the topic).
- One span per distinct contiguous stretch (back-to-back ads = separate spans; intro then ad = two spans).`

const SPAN_SCHEMA = {
  type: 'object', additionalProperties: false, required: ['spans'],
  properties: {
    spans: {
      type: 'array',
      items: {
        type: 'object', additionalProperties: false,
        required: ['type', 'subtype', 'start_quote', 'end_quote', 'rationale'],
        properties: {
          type: { type: 'string', enum: ['ad', 'intro', 'outro', 'housekeeping'] },
          subtype: { type: ['string', 'null'], enum: ['pre-roll', 'mid-roll', 'post-roll', null] },
          start_quote: { type: 'string' },
          end_quote: { type: 'string' },
          rationale: { type: 'string' },
        },
      },
    },
  },
}

const ADJ_SCHEMA = {
  type: 'object', additionalProperties: false, required: ['spans', 'notes', 'agreement'],
  properties: {
    spans: SPAN_SCHEMA.properties.spans,            // Opus's authoritative corrected list
    notes: { type: 'string' },                       // what Opus changed vs Sonnet and why
    agreement: { type: 'string', enum: ['high', 'medium', 'low'] },
  },
}

const labelPrompt = (id) => `${INSTRUCTIONS}

Read the transcript at: ${REPO}/data/transcripts/${id}.txt
Then return the faff spans for this episode. Return {"spans":[]} if there is genuinely no faff.`

const adjudPrompt = (id, sonnet) => `${INSTRUCTIONS}

You are ADJUDICATING. First, independently identify the faff yourself by reading the transcript at:
${REPO}/data/transcripts/${id}.txt

Then reconcile against another labeller's spans (below). Produce the AUTHORITATIVE span list:
keep correct spans, fix wrong boundaries, drop false positives (content wrongly cut - the cardinal sin),
add genuine faff the other labeller missed (pre-rolls especially). In "notes" say briefly what you changed
and why. In "agreement" rate how close the other labeller was: high / medium / low.

OTHER LABELLER'S SPANS (JSON):
${JSON.stringify(sonnet?.spans ?? [], null, 1)}`

log(`Labelling ${IDS.length} episodes: Sonnet -> Opus adjudication`)

const results = await pipeline(
  IDS,
  (id) => agent(labelPrompt(id), { label: `label:${id}`, phase: 'Label (Sonnet)', model: 'sonnet', schema: SPAN_SCHEMA })
            .then((spans) => ({ id, sonnet: spans })),
  (prev, id) => agent(adjudPrompt(id, prev?.sonnet), { label: `adjud:${id}`, phase: 'Adjudicate (Opus)', model: 'opus', schema: ADJ_SCHEMA })
            .then((opus) => ({ id, sonnet: prev?.sonnet ?? { spans: [] }, opus })),
)

return results.filter(Boolean)

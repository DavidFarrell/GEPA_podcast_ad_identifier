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
  'news_agents__trump_impotent', 'dtns__wwdc2026_528', '20vc__anthropic_ipo',
  'btb__fuhrman_part1', 'search_engine__bp_pool', 'freakonomics__676_lost_plot',
  'trip_us__trump_netanyahu', 'practical_ai__stanford_index',
  'hard_fork__ipo_summer_math', 'ezra_klein__ian_bremmer',
]

const INSTRUCTIONS = `You are building a GOLDEN dataset for training a small local model to cut "faff" out of podcasts. You are the oracle: your labels are ground truth. You see the WHOLE transcript at once. Everything you do not label is kept as content.

The transcript is "#<idx> [mm:ss] SPEAKER: text", one SENTENCE per line.

FOUR faff types:

"ad" - advertising / sponsorship: a host-read sponsor read ("brought to you by X"), an injected pre-recorded third-party spot (often a different voice, marketing language, slogan, call to action, sometimes back-to-back near the start), or a cross-promo for another show. Set subtype: "pre-roll" (near the very start), "mid-roll" (in the body), "post-roll" (very end).
  - NATIVE / CASUAL ad reads still count. A host may pitch a product in conversational, jokey language with no "sponsor" framing ("Anthony, you've got a few kids - you'll know how hard it is to..."). If the PURPOSE is to sell a product/service/app, it is an ad, however casual it sounds.
  - COMEDIC "throws" to the break are NOT ads. Some shows run a recurring gag that introduces the ad break ("you know who else can barely read? The sponsors of this podcast"). The joke is part of the show = CONTENT. Label only the actual advertisement that follows, not the bit that throws to it.

"intro" - GENERIC show packaging ONLY: the theme/music sting and the formulaic branded welcome ("Welcome to The X Podcast, I'm your host Y..."), or a rapid teaser-billboard that exists only to tease and then hands straight to an ad.
  - DO NOT cut a content-rich opening. If the host is already delivering substance - framing THIS episode's specific story, previewing the actual argument with real detail, an essayistic cold open - that is CONTENT, keep it. When an intro carries real content, or you are unsure, KEEP it. Bias toward keeping intros.

"outro" - end credits, "thanks for listening", network/producer sign-off, "see you next week", final next-episode tease.

"housekeeping" - SUBSTANTIAL own-show self-promo ONLY: a real patreon/membership/merch/newsletter pitch.
  - A one-line "subscribe and leave a review", or a brief thank-you / super-chat shout-out, is too short - DO NOT label it.
  - If the "housekeeping" is actually pitching a THIRD-PARTY product/service, label it "ad", not housekeeping.

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

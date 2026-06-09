export const meta = {
  name: 'golden-label-podcast-faff',
  description: 'Label ad/intro/outro/housekeeping spans in podcast transcripts: Sonnet labels each, Opus independently relabels + adjudicates',
  phases: [
    { title: 'Label (Sonnet)', detail: 'one Sonnet agent per episode reads the transcript and quotes every faff span' },
    { title: 'Adjudicate (Opus)', detail: 'one Opus agent per episode independently relabels and reconciles against Sonnet' },
  ],
}

// args: { repo: "/abs/path/to/project", ids: ["episode_id", ...] }
const REPO = args.repo
const IDS = args.ids

const INSTRUCTIONS = `You are building a GOLDEN dataset for training a small local model to cut "faff" out of podcasts. You are the oracle: your labels are ground truth. You see the WHOLE transcript at once.

Read every span of FAFF - material that is NOT the episode's actual content. Everything you do not label is kept as content.

The transcript is "[mm:ss] SPEAKER: text", one TURN per line, each prefixed "#<idx>".

FOUR faff types:
- "ad": paid advertising / sponsor read / injected pre-recorded commercial / cross-promo for another show. Set subtype: "pre-roll" (near the very start), "mid-roll" (in the body), "post-roll" (very end). Catch host-read reads ("brought to you by X"), injected third-party spots (often a different voice, marketing language, slogan, call to action, sometimes back-to-back near the start, NOT framed as "brought to you by"), and cross-promos.
- "intro": the show's own top-of-episode boilerplate - theme/music sting, the "coming up today" billboard, the branded "Welcome to The X Podcast, I'm your host...". The first substantive discussion / a genuine archival clip / a guest's first real answer is CONTENT, not intro.
- "outro": end credits, "thanks for listening", network/producer sign-off, "see you next week", final next-episode tease.
- "housekeeping": non-ad self-promo woven in - patreon/membership/merch/newsletter plugs, "subscribe and leave a review", listener-mail solicitations, "coming up later, but first..." teasers.

For each span return: type, subtype (ads only, else null), start_quote, end_quote, rationale (one short line).
- start_quote = the exact sentence that STARTS the faff. end_quote = the exact LAST sentence of that same stretch.
- Quotes MUST be copied VERBATIM from the spoken words (the #idx/timestamp prefix is optional). They are matched back programmatically; an unfindable quote is discarded.
- Copy a full distinctive sentence, not a fragment. Boundaries sit at clean speech transitions.

CARDINAL RULE: cutting real content is far worse than missing faff. When in doubt, DO NOT label. A passing brand mention in conversation is NOT an ad - the test is purpose (selling/signing-off/branding vs discussing). One span per distinct contiguous stretch.`

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

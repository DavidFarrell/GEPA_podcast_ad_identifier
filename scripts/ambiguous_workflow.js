export const meta = {
  name: 'mark-ambiguous-zones',
  description: 'Mark plugs-style policy-ambiguous zones in already-golden episodes: Sonnet flags candidates, Opus confirms',
  phases: [
    { title: 'Flag (Sonnet)', detail: 'one agent per episode reads transcript + existing golden spans, flags ambiguous zones' },
    { title: 'Confirm (Opus)', detail: 'only episodes with flagged zones get an Opus verification pass' },
  ],
}

const A = (typeof args !== 'undefined' && args) ? args : {}
const REPO = A.repo || '/Users/david/git/ai-sandbox/projects/GEPA_podcast_ad_identifier'
// {id, goldenPath} pairs - pass via args or use defaults injected before launch
const EPS = (A.eps && A.eps.length) ? A.eps : [
 {
  "id": "btb__fuhrman_part2",
  "goldenPath": "/Users/david/git/ai-sandbox/projects/GEPA_podcast_ad_identifier/data/golden/btb__fuhrman_part2.json"
 },
 {
  "id": "dtns__do_people_hate_tech",
  "goldenPath": "/Users/david/git/ai-sandbox/projects/GEPA_podcast_ad_identifier/data/golden/dtns__do_people_hate_tech.json"
 },
 {
  "id": "lennys__rational_ai",
  "goldenPath": "/Users/david/git/ai-sandbox/projects/GEPA_podcast_ad_identifier/data/golden/lennys__rational_ai.json"
 },
 {
  "id": "news_agents_usa__j6_slush",
  "goldenPath": "/Users/david/git/ai-sandbox/projects/GEPA_podcast_ad_identifier/data/golden/news_agents_usa__j6_slush.json"
 },
 {
  "id": "ppf__dispossessed",
  "goldenPath": "/Users/david/git/ai-sandbox/projects/GEPA_podcast_ad_identifier/data/golden/ppf__dispossessed.json"
 },
 {
  "id": "threedom__i_see_both",
  "goldenPath": "/Users/david/git/ai-sandbox/projects/GEPA_podcast_ad_identifier/data/golden/threedom__i_see_both.json"
 },
 {
  "id": "thursdai__nemotron",
  "goldenPath": "/Users/david/git/ai-sandbox/projects/GEPA_podcast_ad_identifier/data/golden/thursdai__nemotron.json"
 },
 {
  "id": "trip_leading__control_ai",
  "goldenPath": "/Users/david/git/ai-sandbox/projects/GEPA_podcast_ad_identifier/data/golden/trip_leading__control_ai.json"
 },
 {
  "id": "trip_us__losing_streak",
  "goldenPath": "/Users/david/git/ai-sandbox/projects/GEPA_podcast_ad_identifier/data/golden/trip_us__losing_streak.json"
 },
 {
  "id": "20vc__anthropic_ipo",
  "goldenPath": "/Users/david/git/ai-sandbox/projects/GEPA_podcast_ad_identifier/data/golden_pilot/20vc__anthropic_ipo.json"
 },
 {
  "id": "btb__fuhrman_part1",
  "goldenPath": "/Users/david/git/ai-sandbox/projects/GEPA_podcast_ad_identifier/data/golden_pilot/btb__fuhrman_part1.json"
 },
 {
  "id": "dtns__wwdc2026_528",
  "goldenPath": "/Users/david/git/ai-sandbox/projects/GEPA_podcast_ad_identifier/data/golden_pilot/dtns__wwdc2026_528.json"
 },
 {
  "id": "ezra_klein__ian_bremmer",
  "goldenPath": "/Users/david/git/ai-sandbox/projects/GEPA_podcast_ad_identifier/data/golden_pilot/ezra_klein__ian_bremmer.json"
 },
 {
  "id": "freakonomics__676_lost_plot",
  "goldenPath": "/Users/david/git/ai-sandbox/projects/GEPA_podcast_ad_identifier/data/golden_pilot/freakonomics__676_lost_plot.json"
 },
 {
  "id": "hard_fork__ipo_summer_math",
  "goldenPath": "/Users/david/git/ai-sandbox/projects/GEPA_podcast_ad_identifier/data/golden_pilot/hard_fork__ipo_summer_math.json"
 },
 {
  "id": "news_agents__trump_impotent",
  "goldenPath": "/Users/david/git/ai-sandbox/projects/GEPA_podcast_ad_identifier/data/golden_pilot/news_agents__trump_impotent.json"
 },
 {
  "id": "practical_ai__stanford_index",
  "goldenPath": "/Users/david/git/ai-sandbox/projects/GEPA_podcast_ad_identifier/data/golden_pilot/practical_ai__stanford_index.json"
 },
 {
  "id": "search_engine__bp_pool",
  "goldenPath": "/Users/david/git/ai-sandbox/projects/GEPA_podcast_ad_identifier/data/golden_pilot/search_engine__bp_pool.json"
 },
 {
  "id": "trip_us__trump_netanyahu",
  "goldenPath": "/Users/david/git/ai-sandbox/projects/GEPA_podcast_ad_identifier/data/golden_pilot/trip_us__trump_netanyahu.json"
 },
 {
  "id": "99pi__karaoke_videos",
  "goldenPath": "/Users/david/git/ai-sandbox/projects/GEPA_podcast_ad_identifier/data/golden_test/99pi__karaoke_videos.json"
 },
 {
  "id": "comedy_bang_bang__blind_is_love",
  "goldenPath": "/Users/david/git/ai-sandbox/projects/GEPA_podcast_ad_identifier/data/golden_test/comedy_bang_bang__blind_is_love.json"
 },
 {
  "id": "conan__andrew_scott",
  "goldenPath": "/Users/david/git/ai-sandbox/projects/GEPA_podcast_ad_identifier/data/golden_test/conan__andrew_scott.json"
 },
 {
  "id": "econoclasts__ai_job_apocalypse",
  "goldenPath": "/Users/david/git/ai-sandbox/projects/GEPA_podcast_ad_identifier/data/golden_test/econoclasts__ai_job_apocalypse.json"
 },
 {
  "id": "ft_tech_tonic__zuckerberg_100bn",
  "goldenPath": "/Users/david/git/ai-sandbox/projects/GEPA_podcast_ad_identifier/data/golden_test/ft_tech_tonic__zuckerberg_100bn.json"
 },
 {
  "id": "mfm__think_about_simulation",
  "goldenPath": "/Users/david/git/ai-sandbox/projects/GEPA_podcast_ad_identifier/data/golden_test/mfm__think_about_simulation.json"
 },
 {
  "id": "politics_show__burnhamism",
  "goldenPath": "/Users/david/git/ai-sandbox/projects/GEPA_podcast_ad_identifier/data/golden_test/politics_show__burnhamism.json"
 },
 {
  "id": "sysk__smile",
  "goldenPath": "/Users/david/git/ai-sandbox/projects/GEPA_podcast_ad_identifier/data/golden_test/sysk__smile.json"
 },
 {
  "id": "amer_hist_tellers__revolution_1",
  "goldenPath": "/Users/david/git/ai-sandbox/projects/GEPA_podcast_ad_identifier/data/golden_expand/amer_hist_tellers__revolution_1.json"
 },
 {
  "id": "criminal__man_to_be_afraid_of",
  "goldenPath": "/Users/david/git/ai-sandbox/projects/GEPA_podcast_ad_identifier/data/golden_expand/criminal__man_to_be_afraid_of.json"
 },
 {
  "id": "darknet_diaries__tarjeteros",
  "goldenPath": "/Users/david/git/ai-sandbox/projects/GEPA_podcast_ad_identifier/data/golden_expand/darknet_diaries__tarjeteros.json"
 },
 {
  "id": "heavyweight__brandon",
  "goldenPath": "/Users/david/git/ai-sandbox/projects/GEPA_podcast_ad_identifier/data/golden_expand/heavyweight__brandon.json"
 },
 {
  "id": "hidden_brain__who_are_you",
  "goldenPath": "/Users/david/git/ai-sandbox/projects/GEPA_podcast_ad_identifier/data/golden_expand/hidden_brain__who_are_you.json"
 },
 {
  "id": "how_i_built_this__shopify",
  "goldenPath": "/Users/david/git/ai-sandbox/projects/GEPA_podcast_ad_identifier/data/golden_expand/how_i_built_this__shopify.json"
 },
 {
  "id": "maintenance_phase__4hr_body",
  "goldenPath": "/Users/david/git/ai-sandbox/projects/GEPA_podcast_ad_identifier/data/golden_expand/maintenance_phase__4hr_body.json"
 },
 {
  "id": "no_such_thing__accordion",
  "goldenPath": "/Users/david/git/ai-sandbox/projects/GEPA_podcast_ad_identifier/data/golden_expand/no_such_thing__accordion.json"
 },
 {
  "id": "normal_gossip__divas_finale",
  "goldenPath": "/Users/david/git/ai-sandbox/projects/GEPA_podcast_ad_identifier/data/golden_expand/normal_gossip__divas_finale.json"
 },
 {
  "id": "ologies__awe_psychology",
  "goldenPath": "/Users/david/git/ai-sandbox/projects/GEPA_podcast_ad_identifier/data/golden_expand/ologies__awe_psychology.json"
 },
 {
  "id": "revisionist_history__trust_diagnosis",
  "goldenPath": "/Users/david/git/ai-sandbox/projects/GEPA_podcast_ad_identifier/data/golden_expand/revisionist_history__trust_diagnosis.json"
 },
 {
  "id": "science_vs__peptides",
  "goldenPath": "/Users/david/git/ai-sandbox/projects/GEPA_podcast_ad_identifier/data/golden_expand/science_vs__peptides.json"
 },
 {
  "id": "smartless__jon_bernthal",
  "goldenPath": "/Users/david/git/ai-sandbox/projects/GEPA_podcast_ad_identifier/data/golden_expand/smartless__jon_bernthal.json"
 },
 {
  "id": "sysmh__virgil_neal",
  "goldenPath": "/Users/david/git/ai-sandbox/projects/GEPA_podcast_ad_identifier/data/golden_expand/sysmh__virgil_neal.json"
 }
]

const RUBRIC = `A team labels podcast transcripts for an ad/faff detector. Most stretches are clearly CONTENT (the episode itself) or clearly FAFF (ads, generic intros, outros, self-promo) - those are already labelled. Your job is ONLY to find AMBIGUOUS ZONES: stretches where cutting and keeping are BOTH defensible, so the detector should be neither rewarded nor punished there.

Mark a zone ONLY if it matches one of these patterns:
1. PLUGS-style segments: a recurring show segment where hosts/guests plug their own projects, tours, patreons, listener submissions - delivered AS entertainment, part of the show's format (e.g. Comedy Bang Bang's closing plugs with listener theme songs).
2. PARODY / in-character ads: comedy bits structured as fake or real ads but performed as show content (in-character sketches around a genuine sponsor message blur both ways).
3. Conversational sponsor banter: hosts riffing at length around a sponsor message where the riff is genuinely entertaining content interleaved with selling, and no clean boundary exists.
4. Guest plug stretches: a guest promoting their own book/show/tour as part of the interview flow, at length.

Do NOT mark: clear ads (even casual host-reads - those are faff), clear content with a passing brand mention, stretches already inside an existing golden faff span, or anything under ~10 seconds. Most episodes have NO ambiguous zones - return {"zones":[]} readily.

For each zone: start_quote / end_quote VERBATIM whole sentences from the transcript, and a one-line reason.`

const ZONES_SCHEMA = {
  type: 'object', additionalProperties: false, required: ['zones'],
  properties: {
    zones: {
      type: 'array',
      items: {
        type: 'object', additionalProperties: false,
        required: ['start_quote', 'end_quote', 'reason'],
        properties: {
          start_quote: { type: 'string' },
          end_quote: { type: 'string' },
          reason: { type: 'string' },
        },
      },
    },
  },
}

const flagPrompt = (ep) => `${RUBRIC}

Transcript: ${REPO}/data/transcripts/${ep.id}.txt
Existing golden faff spans (already labelled - do NOT re-mark these): ${ep.goldenPath}
Read both, then return the ambiguous zones for this episode.`

const confirmPrompt = (ep, zones) => `${RUBRIC}

You are CONFIRMING another labeller's proposed ambiguous zones. Read the transcript at
${REPO}/data/transcripts/${ep.id}.txt and the existing golden spans at ${ep.goldenPath}.
For each proposed zone below, KEEP it only if it is genuinely ambiguous under the rubric -
DROP zones that are clearly content (the detector must not be excused for cutting them) or
clearly faff (those should be ordinary golden spans, not ambiguous). Tighten boundaries if
needed. Return the verified zone list (possibly empty).

PROPOSED ZONES:
${JSON.stringify(zones, null, 1)}`

log(`Scanning ${EPS.length} episodes for ambiguous zones`)

const results = await pipeline(
  EPS,
  (ep) => agent(flagPrompt(ep), { label: `flag:${ep.id}`, phase: 'Flag (Sonnet)', model: 'sonnet', schema: ZONES_SCHEMA })
            .then((r) => ({ ep, flagged: r?.zones ?? [] })),
  (prev, ep) => {
    if (!prev || !prev.flagged.length) return { id: ep.id, zones: [] }
    return agent(confirmPrompt(ep, prev.flagged), { label: `confirm:${ep.id}`, phase: 'Confirm (Opus)', model: 'opus', schema: ZONES_SCHEMA })
      .then((r) => ({ id: ep.id, zones: r?.zones ?? [], flagged: prev.flagged.length }))
  },
)

return results.filter(Boolean)

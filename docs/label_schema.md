# Golden label schema

One golden file per episode: `data/golden/<episode_id>.json` (gitignored - embeds verbatim
transcript lines, which are copyrighted).

A label is a **span of "faff" to cut**. Everything not covered by a span is content to keep.

```jsonc
{
  "episode_id": "news_agents__trump_impotent",
  "show": "The News Agents",
  "duration_s": 2070,
  "labeled_by": "claude-sonnet-4-6",      // or claude-opus-4-8 for adjudicated eval
  "schema": "v1",
  "spans": [
    {
      "type": "ad",                        // ad | intro | outro | housekeeping
      "subtype": "pre-roll",               // pre-roll | mid-roll | post-roll | null
      "start_quote": "This episode is brought to you by Indeed.",   // VERBATIM first line
      "end_quote": "Indeed.com slash news agents, terms and conditions apply.",  // VERBATIM last line
      "start_s": 42.1,                     // start time of the span (from mapped segment)
      "end_s": 71.8,                       // end time of the span
      "rationale": "Dynamically-inserted Indeed pre-roll, host read."
    }
  ]
}
```

## The four `type` values (what we cut)
| type | what it is |
|---|---|
| `ad` | Paid advertising / sponsor read / dynamically-inserted spot. Set `subtype` to pre/mid/post-roll by position. **Pre-rolls are the priority blind spot.** |
| `intro` | The show's own intro / cold-open / theme / billboard / "welcome back to..." Open Swimcast prepends its own intro, so the original goes. |
| `outro` | End credits, "thanks for listening", sign-off, next-episode tease at the very end. |
| `housekeeping` | Non-ad self-promo woven in: patreon/merch/newsletter plugs, "subscribe", "leave a review", listener-mail solicitations, "coming up later" teasers. |

## Hard rules for labellers
1. **Quotes must be VERBATIM substrings** of the transcript (so they map deterministically to
   segment indices + timestamps, exactly like the Open Swimcast detector). A validator rejects
   any span whose `start_quote`/`end_quote` is not found; the labeller must repair it.
2. **Pick boundaries at clean speech transitions** - the first sentence of the faff and the
   last sentence of the faff. Don't clip into adjacent content.
3. **When unsure, do NOT label.** Mirrors the detector's cardinal rule: a missed ad is far
   cheaper than cutting real content. Ambiguity → leave it as content.
4. One span per contiguous faff block. Two back-to-back ads = two spans (or one if read as a
   single block - use judgement, note it in rationale).
5. `start_s`/`end_s` are filled by the deterministic quote→segment mapper, not guessed by the
   labeller. The labeller's job is the quotes + type + rationale.

## How this feeds GEPA
- **Seed prompt** (Gemma) is asked to return spans in this same shape (quote boundaries).
- The **metric** compares Gemma's predicted spans to the golden spans by time overlap:
  - **Recall** = fraction of golden faff-time correctly covered (per type; pre-roll called out).
  - **False-positive penalty** = any predicted cut overlapping non-faff content is heavily
    penalised (the cardinal rule). One content-cut should outweigh several missed ads.
  - Textual feedback names the specific missed/over-cut span so the reflection LM can fix the prompt.

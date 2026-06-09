# GEPA Podcast Ad Identifier

Use [GEPA](https://github.com/gepa-ai/gepa) (genetic / reflective prompt optimisation) to
improve the ad-detection prompt used to find and cut adverts and interstitials in podcast
episodes.

## Why this exists

This spins out of the **Open Swimcast** project (`../OpenSwimPodcast`), which sideloads
Pocket Casts episodes onto swim headphones and can auto-trim ads. Its detector works well
on mid-roll ads but has a known recall gap:

- **Pre-roll ads survive.** Injected pre-roll ads at the very start of an episode (e.g. an
  Indeed read, a "Declassified Club" house promo) slip through. Because Open Swimcast
  prepends its own spoken intro first, a surviving pre-roll is the first thing heard after
  the intro - the worst spot.

The detector itself is **locked** in Open Swimcast and must not regress:

- Model: `google/gemma-4-12b-qat` (local, via LM Studio OpenAI API).
- Method: **quote-boundary** - the model returns verbatim `{first_line, last_line}` per ad,
  mapped deterministically to segment indices. It never emits indices/timestamps itself.
- Windows: 30-minute windows, 3-minute overlap.
- **Cardinal rule: zero false positives.** Never cut real content. Ambiguous boundaries are
  flagged needs-review or skipped, never silently cut.

## The idea

Apply the GEPA workflow (as demonstrated in Mahmoud Mabrouk's "Judge the Judge" talk and the
GEPA paper) to evolve the detection prompt against a labelled set of real podcast
transcripts - targeting **higher pre-roll recall while preserving the zero-false-positive
constraint**. GEPA's reflective mutation + Pareto-frontier selection should let us improve
recall on the known blind spot without trading away precision on content.

## Status

Just scaffolded (2026-06-09). Next steps to scope:

- [ ] Read and pin GEPA documentation + API (`gepa` library, `optimize_anything`).
- [ ] Assemble a labelled corpus: real episode transcripts with ad spans annotated
      (pre-roll, mid-roll, post-roll), including the known survivors (Indeed, Declassified
      Club) as test cases.
- [ ] Define the metric: recall on ad spans **gated** by a hard zero-FP penalty on content.
- [ ] Seed prompt = current locked detector prompt (`v_inject`).
- [ ] Run GEPA; validate any improved prompt does not regress mid-roll precision before it
      goes anywhere near Open Swimcast.

## Related

- Open Swimcast: `../OpenSwimPodcast` (detector lives in `app/electron/detectAds.cjs`).
- GEPA / DSPy background notes:
  `obsidian/.../Resources/GEPA & DSPy - Index.md`.

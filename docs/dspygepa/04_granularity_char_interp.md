# 04 - Is segmentation load-bearing? The char-interpolation cheap path

## The question (GPT-5's finding, routed to dspygepa to verify)

GPT-5 argued that the champion's quality is load-bearing on **sentence-level segmentation**:

- In this repo, `transcript.py` splits word-timed turns into **sentences**, so a model-returned
  verbatim quote maps to a *tight sentence span*.
- The Swimcast detector works on **coarse diarized turns**: `transcribe.cjs` drops the
  word-timings and feeds whole turns, so a quote maps to the **whole turn**.
- A 1-sentence ad inside a 60s turn that also contains content would therefore cut all 60s -
  and under the auto-apply threshold that ships silently, a cardinal-rule disaster.

GPT-5's conclusion: dropping `seed_checklist_v1` onto a coarse-turn substrate would **not**
replicate the GEPA results; you'd need to port sentence re-segmentation too (real work:
un-dropping word-timings + a sentence splitter).

## dspygepa's verdict: directionally right, mechanism not magnitude

Honest caveat recorded at the time: **no turns-vs-sentences ablation had ever been run** in
this repo, so there was no empirical number - only mechanism. But the mechanism confirms
GPT-5's direction:

> Under `score = recall * 0.5^(fp_sec/15)`, the FP gate is **exponential**, so for the score,
> boundary precision is not a refinement - it is the dominant term. The prompt *finds* the
> ad; the segmentation decides whether you cut 8s or 60s. A one-sentence host-read inside a
> 60s mixed turn becomes ~55s of cut content = `0.5^(55/15) ~ 0.08x` = catastrophic.

So on coarse turns the champion likely keeps similar/higher recall but **tanks on FP/score**,
concentrated on **native / host-read ads woven mid-turn into content**. Where a show's turns
already isolate ad reads (pause-bounded - host stops, does the read as a block, resumes), the
prompt alone gets most of the win. And note recovery makes this *worse*: recovery targets
disguised-opening ads that by nature blend into surrounding talk, so they're the most likely
to share a turn with content.

## The cheap path: char-interpolation (the key contribution)

The expensive fix is full sentence re-segmentation (un-drop word-timings, build a splitter).
There is a much cheaper middle path that the model already makes possible:

> The model returns verbatim `start_quote` / `end_quote`. Find each quote's **character
> offset** inside the turn text and interpolate time **linearly** across the turn's duration:
>
> `t ~ turn_start + (char_offset / total_chars) * turn_duration`
>
> Speech rate is roughly constant, so this recovers most sub-turn boundary precision with
> **no word-timings at all** - a fraction of the work.

## The 3-arm ablation (the decision procedure)

Rather than build re-segmentation blind, run all three on the golden corpus, same model +
metric, per-show `fp_sec`, flagging the embedded / host-read-ad shows where turn-granularity
should blow up:

- **A** - coarse whole-turn boundaries (turn-granular cuts)
- **B** - char-interpolation within the turn (cheap sub-turn precision, no word-timings)
- **C** - full sentence re-seg from un-dropped word-timings (gold standard, most work)

**Decision rule:** if **B** closes most of the **A->C** gap on the embedded-ad shows, ship B
and skip the word-timing surgery entirely.

## The result

The ablation proved B was enough: **char-interpolation recovered ~81% of full
re-segmentation's precision and matched/beat it on the embedded-ad shows.** That converted the
Swimcast adoption from a transcript-substrate rebuild into a **one-file change** - and is the
single biggest reason the whole thing shipped clean overnight.

GPT-5, which had argued for the expensive path, agreed once it saw the numbers.

## Takeaway for future ports

When porting a quote-boundary detector to a coarser-grained substrate, you usually do **not**
need to rebuild the substrate. If the model emits verbatim boundary quotes, proportional
character-interpolation within the coarse unit buys back most of the precision for a tiny
fraction of the effort. Always run the 3-arm ablation before committing to re-segmentation.

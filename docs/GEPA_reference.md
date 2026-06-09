# GEPA reference notes

Consolidated from the official sources (read 2026-06-09). This is a working reference for
building the podcast ad identifier on top of GEPA. See the "Sources" section at the bottom.

---

## What GEPA is

**GEPA = Genetic-Pareto.** A framework for optimising any *textual* parameter - prompts,
code, agent architectures, configs - using **LLM-based reflection + Pareto-efficient
evolutionary search**.

Core insight: traditional optimisers (and RL like GRPO) collapse a run into a single scalar
reward, so they know *that* a candidate failed but not *why*. GEPA feeds the LLM the **full
execution trace** (outputs, error messages, reasoning logs, evaluation feedback) in natural
language, so a reflection model can **diagnose the failure and propose a targeted fix**.

Paper: "GEPA: Reflective Prompt Evolution Can Outperform Reinforcement Learning" (arXiv
2507.19457), 17 authors incl. Lakshya A Agrawal, Omar Khattab, Matei Zaharia, Ion Stoica,
Dan Klein, Christopher Potts. **Accepted ICLR 2026 (Oral).**

### Three core principles
1. **Genetic prompt evolution** - seed candidate → sample mutated + merged candidates → keep
   the good ones → repeat.
2. **Natural-language reflection** - an LLM reads execution traces + textual feedback and
   proposes a new instruction tailored to the observed failures.
3. **Pareto-based selection** - do *not* evolve only the global best. Maintain a Pareto
   frontier of candidates that are best on *at least one* instance, and sample from it. This
   preserves diversity and avoids local minima.

### Headline results (paper)
- Beats GRPO by **6% on average, up to 20%** across six tasks, using **up to 35x fewer
  rollouts**.
- Beats the leading prompt optimiser **MIPROv2 by >10%** (e.g. +12% on AIME-2025).
- "Can often turn even just a few rollouts into a large quality gain."

---

## Two ways to use it

### A. Standalone `gepa` library (the "optimize anything" path)

```bash
pip install gepa
# pip install git+https://github.com/gepa-ai/gepa.git   # dev
```

Quick start (prompt optimisation):
```python
import gepa

trainset, valset, _ = gepa.examples.aime.init_dataset()

seed_prompt = {
    "system_prompt": "You are a helpful assistant. Put final answer as '### <answer>'"
}

result = gepa.optimize(
    seed_candidate=seed_prompt,      # dict of named text components to evolve
    trainset=trainset,
    valset=valset,                   # used for Pareto scoring
    task_lm="openai/gpt-4.1-mini",   # model that DOES the task
    max_metric_calls=150,            # evaluation budget (typ. 100-500 for prompts)
    reflection_lm="openai/gpt-5",    # stronger model that diagnoses + mutates
)
print(result.best_candidate["system_prompt"])
```

Key parameters:
- `seed_candidate` - initial config; usually `{"system_prompt": "..."}`. Can hold multiple
  named components / a chain of prompts.
- `task_lm` vs `reflection_lm` - **task_lm executes and is scored; reflection_lm never runs
  against the metric, it only reads the logged feedback and proposes mutations.** Use a
  stronger model for reflection.
- `max_metric_calls` - budget. Prompts: 100-500. Full DSPy programs: 1k-5k. (RL needs
  5k-25k+, hence the efficiency win.)

### B. Inside DSPy as `dspy.GEPA` (the structured-program path)

```python
gepa = dspy.GEPA(metric=your_metric, auto="medium", reflection_lm=dspy.LM("openai/gpt-5", temperature=1.0))
optimized = gepa.compile(student=MyProgram(), trainset=trainset, valset=valset)
```

Constructor params worth knowing:
- `metric` (required) - a `GEPAFeedbackMetric` (see below).
- Budget (exactly one): `auto` ('light'|'medium'|'heavy'), or `max_full_evals`, or
  `max_metric_calls`.
- `reflection_lm` (required) - strong LM, e.g. GPT-5 temperature=1.0.
- `reflection_minibatch_size` (default 3) - examples per reflection step.
- `candidate_selection_strategy` ('pareto' default | 'current_best').
- `use_merge` (default True), `max_merge_invocations` (default 5) - system-aware merge of
  two frontier candidates that excel on different tasks.
- `skip_perfect_score` (True), `failure_score` (0.0), `perfect_score` (1.0).
- `track_stats=True` → returns `detailed_results` (candidates, val scores, best_outputs,
  best_idx, discovery_eval_counts). Also `track_best_outputs`, `log_dir`, `num_threads`,
  `seed`, wandb/mlflow hooks.
- `compile(student, *, trainset, valset=None, teacher=None)` - trainset drives reflective
  updates; valset tracks Pareto scores (defaults to trainset if omitted).

---

## The metric / feedback contract (THE important bit)

GEPA is only as good as the **textual feedback** the metric returns. A bare score is wasted;
return *why*.

DSPy metric signature:
```python
def metric(gold, pred, trace=None, pred_name=None, pred_trace=None):
    # return a float, OR {'score': float, 'feedback': str}
    ...
```
If no feedback is returned, GEPA defaults to `"This trajectory got a score of {score}."`
(i.e. nothing useful to reflect on).

Standalone library equivalent = the **evaluator** returns a score and logs **Actionable Side
Information (ASI)**:
```python
def evaluate(candidate) -> float:
    result = run_my_system(candidate)
    oa.log(f"Output: {result.output}")   # ASI - fed to the reflection LM
    oa.log(f"Error: {result.error}")
    return result.score
```

**Feedback design recipe (from the docs):**
- Leverage existing artifacts: logs, unit tests, eval scripts, profiler output.
- Decompose outcomes: break the score into per-objective components.
- Expose trajectories: label pipeline stages, report pass/fail with the salient error.
- Prioritise clarity: focus on error coverage and decision points.

---

## The `GEPAAdapter` interface (custom systems)

To optimise a non-trivial system, implement an adapter with two methods:

```python
from gepa.core.adapter import GEPAAdapter

class MyAdapter(GEPAAdapter):
    def evaluate(self, batch, candidate, capture_traces=False):
        # run candidate over the batch; return EvaluationBatch(outputs, scores, trajectories)
        # trajectories = the ASI (inputs, outputs, intermediate steps, errors)
        ...
    def make_reflective_dataset(self, candidate, eval_batch, components_to_update):
        # shape the traces into an LLM-readable reflective dataset
        ...
```

`evaluate(...)` returns an `EvaluationBatch(outputs, scores, trajectories)`. `trajectories`
is captured only when `capture_traces=True`.

### Built-in adapters (don't reinvent these)
| Adapter | Purpose |
|---|---|
| `DefaultAdapter` | Single-turn system-prompt optimisation |
| `ConfidenceAdapter` | Logprob-aware classification (penalises lucky guesses) |
| `DSPyFullProgramAdapter` | Evolve an entire DSPy program |
| `GenericRAGAdapter` | Vector-store-agnostic RAG |
| `MCPAdapter` | MCP tool optimisation |
| `LangChainAdapter` | LangChain pipelines |

Config classes: `GEPAConfig`, `EngineConfig`, `ReflectionConfig`, `TrackingConfig`,
`EvaluationBatch`. Works with API-only models (no weight access needed).

---

## The optimisation loop (mental model)
1. **Select** a candidate from the Pareto frontier.
2. **Execute** on a minibatch; capture full traces.
3. **Reflect** - LLM reads traces + feedback, diagnoses failure.
4. **Mutate** - propose an improved variant, informed by ancestor lessons.
5. **Accept** if improved; add to pool; update the frontier.
6. Optional **merge** of two complementary frontier candidates.
7. Repeat until `max_metric_calls` budget is spent.

---

## How this maps to the ad-identifier project

- The thing being optimised (`seed_candidate`) = the **current locked detector prompt**
  (`v_inject` from Open Swimcast's `detectAds.cjs`).
- `task_lm` = the local detector model, `gemma-4-12b-qat` via LM Studio (GEPA takes an
  OpenAI-compatible endpoint, which LM Studio exposes at `:1234`). `reflection_lm` should be
  a stronger model (GPT-5 / Gemini / Grok per the Mabrouk talk's findings).
- The **metric must encode the cardinal rule**: heavily penalise any false positive (cutting
  content) and reward pre-roll recall. Return per-span feedback, not just a number - tell the
  reflector *which* pre-roll ad was missed and what it looked like (Indeed read, Declassified
  Club promo) so it can evolve the prompt toward catching them.
- Known constraint from the quote-boundary method: the model emits verbatim
  `{first_line,last_line}`, never indices. The metric/evaluator has to map quotes → spans and
  score on that, mirroring the deterministic mapper in Open Swimcast.

---

## Sources
- Library: <https://github.com/gepa-ai/gepa>
- Library docs: <https://gepa-ai.github.io/gepa/>
- DSPy GEPA API: <https://dspy.ai/api/optimizers/GEPA/overview/>
- DSPy GEPA tutorial: <https://dspy.ai/getting-started/gepa-optimization/>
- HF cookbook: <https://huggingface.co/learn/cookbook/dspy_gepa>
- Paper (abs): <https://arxiv.org/abs/2507.19457> · PDF: <https://arxiv.org/pdf/2507.19457>
- ICLR 2026 (Oral): <https://openreview.net/forum?id=RQm2KQTM5r>
- DeepWiki walkthrough: <https://deepwiki.com/stanfordnlp/dspy/4.5-gepa:-reflective-prompt-evolution>

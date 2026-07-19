# Comprehension Probes — testing Gₑ directly

Phase 2 measures cognitive grasp by **testing** the respondent, not by
asking them to self-rate. Load this when running Phase 2.

## Principle

A self-rating measures *confidence*; a probe measures *comprehension*.
They diverge exactly where epistemic debt hides — confident **and** wrong.
Probe the highest-complexity parts hardest: that is where a grasp gap is
most dangerous.

## Formats (`format` arg — if unset, ask the respondent and explain)

- **free-text** — the respondent explains in their own words; you grade
  against a code-derived reference answer. Deepest signal, cannot be
  guessed by elimination. Slower; grading is judgement-based.
- **multiple-choice** — you pose options via AskUserQuestion. Fast and
  structured, but guessable (recognition ≠ recall) and good distractors
  are hard to write, so it tends to **over-state** grasp.

*(Hybrid is intentionally not offered.)*

## Conditions — work, not school

Do **not** police whether the respondent consults the code. Instead ask
questions a glance can't answer: *why is it this way, what happens if,
trace it end-to-end, what would you change*. Reasoning like that requires
real grasp even with the file open. Record conditions as work-realistic
(open) in the report.

## Sampling

Choose parts (files/modules/subsystems) weighted toward the highest Cₛ
found in Phase 1. Use a different part per question within a layer, and
vary phrasing so runs aren't predictable.

**Depth — questions per layer.** If `questions-per-layer` is not set, scale
it to the size of the change, up to a maximum for whole-repo scope. Take
the higher tier the change reaches by *either* files or lines:

| Scope / change size | Questions per layer |
|---|---|
| Tiny — ≤ 1 file or ≤ 20 changed lines | 1 |
| Small — ≤ 5 files or ≤ 100 changed lines | 2 |
| Medium — ≤ 20 files or ≤ 500 changed lines | 3 |
| Large — > 20 files or > 500 changed lines | 4 |
| **Whole repo** | **5 (max)** |

Fall back to fewer questions for a **thin layer** that can't yield that
many non-redundant questions (e.g. L4 in a tiny PR). An explicit
`questions-per-layer` arg overrides this table.

## What each layer probes

- **L1 Implementation** — trace/predict: "What does X return for input …?
  What breaks if line N changes?" **Always show the relevant code
  snippet(s) inline** (with `file:line`), so the question tests reasoning
  over concrete code rather than recall of where it lives.
- **L2 Design** — rationale: "Why is this split like this? What is X's
  single responsibility? What would you change to add feature Y?"
- **L3 Architecture** — system model: "Trace a request end-to-end. What's
  the source of truth for Y? Failure mode if Z is down?"
- **L4 Requirements** — intent: "What problem does this solve, for whom?
  What's the acceptance criterion? What should happen in edge case …?"

## Per-question protocol

The probes on the higher layers demand *articulated* answers — trace this,
explain why, predict that — and an articulated answer mixes parts of
differing certainty. Forcing a single **correctness** onto the whole answer
is exactly what makes it hard to score fairly, so grade correctness **per
claim** instead; confidence stays a single per-answer judgment, as it's the
respondent's overall stated certainty going in, not something that is
naturally decomposed.

1. Generate the question **and** a reference answer with a `file:line`
   citation, so grading is auditable and not done from memory.
2. Pose the question — for L1, paste the relevant code snippet(s) inline.
3. Capture **confidence** *before* revealing anything, for the whole
   answer:
   Guessing / Somewhat / Confident / Certain → 0.1 / 0.4 / 0.7 / 0.95.
4. **Decompose the answer into its distinct claims** (the checkable
   assertions it makes) and grade each **correctness 0–1** against the
   reference (partial credit). Show the reference + citation.
5. Record the answer as `{confidence, claims: [...]}` — the aggregation
   into an answer/layer correctness happens in `scripts/grasp.py` (see
   Scoring → Gₑ below), not by hand.
6. The respondent may contest. A correct rebuttal **raises** the affected
   claim's correctness and is logged as strong grasp — defending an answer
   is comprehension.

**Multiple-choice** can't be decomposed into claims: score it as a
single-claim answer — one correctness (1/0), same single confidence per
question as free-text.

## Scoring → Gₑ

Feed every layer's answers to `scripts/grasp.py` (invoked the same way
Phase 3 invokes `score.py` — see `SKILL.md`); it computes
`answer correctness = mean(claim correctness)`,
`correctness = mean(answer correctness across questions)`, and
`Gₑ = round(correctness × 5)`, so the aggregation is reproducible. Feed
the resulting Gₑ into `scripts/score.py` exactly as before — that engine
is unchanged.

## Calibration (diagnostic only — never changes the grade)

`scripts/grasp.py` also returns, per layer: `confidence = mean(answer
confidence)`, `gap = confidence − correctness`, and a flag:

- `gap ≳ +0.3` → **overconfident** (the confident-and-wrong danger zone).
- `gap ≈ 0` → well-calibrated.
- `gap ≲ −0.3` → underconfident (knows more than they think).

Flag overconfident layers prominently in the report.

## Report (methodology + limitations)

Record: format, questions-per-layer, conditions (work-realistic/open), who
was tested, and that sampling was complexity-weighted. State the limits:
measures the respondent(s) present — not "the team"; at 1 question/layer a
single answer swings that layer's Gₑ; grading is LLM-judged and
code-derived (fallible, but auditable via the cited references), done per
claim for correctness; confidence is self-reported, one value per answer.

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
vary phrasing so runs aren't predictable. This also keeps the two probes
sharing a call from leaking into each other (see the per-question protocol).

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

Run steps 1–3 **per probe**, and pack **at most two probes into one
`AskUserQuestion` call**, interleaved with their confidence questions:

```
[L1-Q1, conf-Q1, L1-Q2, conf-Q2] → [L1-Q3, conf-Q3, L1-Q4, conf-Q4] → [L1-Q5, conf-Q5]
```

Each bracket is one call. The tool takes up to 4 questions per call and
returns all the answers together, so two probes plus their two confidence
questions is the tightest packing that still puts each rating directly after
the answer it describes — `ceil(N/2)` calls for a layer of N probes. Asking
confidence while the answer is in hand is the whole point: a respondent
rating certainty three questions later is reconstructing a feeling, not
reporting one, and the calibration gap is only as good as that number.

Batching probes and sweeping confidence up afterwards is worse on *both*
counts — the sweep needs calls of its own (`ceil(N/4)` probe calls +
`ceil(N/4)` confidence calls ≥ `ceil(N/2)`) and the ratings are
reconstructed. There is no round-trip argument for it.

**Use one probe in the call, not two, whenever the pair would leak** — the
respondent sees both questions before answering either, so a pair drawn from
the same function, the same request path, or the same requirement can hand
over its own answer. Draw the two probes from different parts of the layer,
and when you can't, split the call. Leakage inflates Gₑ, understating debt;
that is the exact failure this skill exists to prevent, and no saving in
round-trips justifies it.

1. Generate the question **and** a reference answer with a `file:line`
   citation, so grading is auditable and not done from memory.
2. Pose the question **through `AskUserQuestion` — never as chat prose**
   (see the mandatory interaction rules in `SKILL.md`), **at most two probes
   per call**. For L1, paste each probe's code snippet inline in the chat
   message immediately before the call, labelled (`L1-Q2`), and have that
   question's text refer to its label — with two probes in one call the
   labels are what keeps the snippets and questions matched up. At most 4
   options; a free-text answer is typed into the call's "Other" field. Where
   the tool is absent (headless runs don't have it), prose carries the same
   batching, labels and pairing — see the fallback in `SKILL.md`.
3. Ask **confidence as the question immediately after its probe, in the same
   call**, so it is rated with the answer in hand and before anything is
   revealed — options Guessing / Somewhat / Confident / Certain → 0.1 / 0.4 /
   0.7 / 0.95. Phrase it against the probe's label ("How confident are you in
   your answer to L1-Q2?"): you have not seen the answer yet, so you cannot
   quote it.
4. **Decompose the answer into its distinct claims** (the checkable
   assertions it makes) and grade each **correctness 0–1** against the
   reference (partial credit). Show the reference + citation.
   **Granularity rule: one claim per independently checkable assertion** —
   the smallest statement that can be judged right or wrong against the
   reference on its own. Never merge two assertions into one claim, and
   never pad the list by restating the same assertion twice: `grasp.py`
   averages over the claims, so the split *is* the score's denominator — the
   same answer scores differently depending on how finely it is cut.
   *Worked example:* the answer "eviction removes the oldest entry, and it
   runs on every `get()` call" is **two** claims — (1) eviction order is
   oldest-first, (2) eviction is triggered by `get()`. If the reference says
   eviction is oldest-first but runs only on `put()`, grade `[1.0, 0.0]` →
   answer correctness 0.5 — not one merged claim graded 0.5 by feel.
   **Record the claim count per answer**; it goes in the report's probe
   table so the decomposition itself is auditable.
5. Record the answer as `{confidence, claims: [...]}` — the aggregation
   into an answer/layer correctness happens in `scripts/grasp.py` (see
   Scoring → Gₑ below), not by hand.
6. The respondent may contest. A correct rebuttal **raises** the affected
   claim's correctness and is logged as strong grasp — defending an answer
   is comprehension.

**Multiple-choice** can't be decomposed into claims: score it as a
single-claim answer — one correctness (1/0), same single confidence per
question as free-text. Its options map directly onto the
`AskUserQuestion` options (max 4 — so distractors are capped at 3).

## Scoring → Gₑ

Feed every layer's answers to `scripts/grasp.py` (invoked the same way
Phase 3 invokes `score.py` — see `SKILL.md`); it computes
`answer correctness = mean(claim correctness)`,
`correctness = mean(answer correctness across questions)`, and
`Gₑ = round(correctness × 5)` (Python round-half-to-even: 2.5 → 2,
4.5 → 4), so the aggregation is reproducible. Feed
the resulting Gₑ into `scripts/score.py` exactly as before — that engine
is unchanged.

## Calibration (diagnostic only — never changes the grade)

`scripts/grasp.py` also returns, per layer: `confidence = mean(answer
confidence)`, `calibration_gap = confidence − correctness`, and a flag
(the key is deliberately *not* named `gap` — that name belongs to the
C−G scale-point gaps `recovery.py` consumes):

- `calibration_gap ≳ +0.3` → **overconfident** (the confident-and-wrong
  danger zone).
- `calibration_gap ≈ 0` → well-calibrated.
- `calibration_gap ≲ −0.3` → underconfident (knows more than they think).

Flag overconfident layers prominently in the report.

## Report (methodology + limitations)

Record: format, questions-per-layer, the claim count per answer, conditions
(work-realistic/open), who was tested, and that sampling was
complexity-weighted. State the limits: measures the respondent(s) present —
not "the team"; at 1 question/layer a single answer swings that layer's Gₑ;
grading is LLM-judged and code-derived (fallible, but auditable via the
cited references *and* the recorded per-answer claim counts — the
decomposition, not just the grading, must be checkable), done per claim for
correctness, one claim per independently checkable assertion; confidence is
self-reported, one value per answer, asked in the same prompt as that
answer and before any grading was shown.

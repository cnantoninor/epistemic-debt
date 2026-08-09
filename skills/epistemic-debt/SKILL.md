---
name: epistemic-debt
description: This skill should be used when the user asks to "measure epistemic debt", "assess epistemic debt", "check our understanding gap", "how much epistemic debt", "grade this repo/PR for epistemic debt", or wants to evaluate how far system complexity has outpaced team comprehension. Works on a whole repository or on a single PR/branch diff against origin/main. Combines repo scanning (system complexity) with direct comprehension testing (cognitive grasp — the skill quizzes the respondent on real parts of the system rather than asking them to self-rate), then produces a cascade-weighted grade and remediation next actions using Rau's Epistemic Debt framework.
---

# Epistemic Debt

Measure epistemic debt — the accumulated opacity when system complexity
(`Cₛ`) outpaces team comprehension (`Gₑ`) — across four abstraction
layers, then grade it with cascade discounting and recommend remediation.

Complexity is **scanned** from the repo; grasp is **tested** (the
framework treats it as undocumented — so we measure it directly). Full
math and multipliers live in `references/framework.md` — load it when you
need definitions or the break-even calculation. The grade is qualitative;
a default-rate recovery estimate always runs (Phase 4), and a deeper
re-run with the team's own rates is optional (Phase 5).

## Credit notice (show once, before Phase 0)

Open every run with this, before doing anything else:

> 📊 **Epistemic Debt** — framework & method by **Antonino Rau**.
> The math & the cost: https://antoninorau.substack.com/p/epistemic-debt-the-math-the-cost
> More writing: https://antoninorau.substack.com/
>
> ⚠️ The grade below is an **estimate**, not a fact — it's produced by a purely speculative math framework (see the article above), not an empirically validated model. Treat it as a structured prompt for discussion, not ground truth.

## Interaction rules (mandatory — apply to every phase)

**Every question put to the user MUST go through the `AskUserQuestion`
tool.** Never pose a question as prose in chat and wait for a free-form
reply — not for the `format` argument, not for probe questions, not for
Phase 5's rates. Prose prompts produce unstructured, hard-to-grade replies
and give the respondent no affordance; `AskUserQuestion` renders selectable
options and returns a parseable answer. Chat prose is for *stating* results
(scope, scores, the grade), never for *soliciting* input.

Tool limits: **max 4 questions per call, max 4 options per question.** A
free-text answer is still collected through `AskUserQuestion` — the
respondent uses the automatically-provided "Other" field to type their
answer; state that in the question text.

**If `AskUserQuestion` is not available in the session, ask in chat prose but
keep the structure.** The tool is interactive-only, so headless and
non-interactive runs simply don't have it — there is nothing to grant and no
error to work around. Fall back to prose that preserves everything the
structure is *for*: the same batching (at most two probes at a time), each
probe immediately followed by its own confidence question, the same labels
and the same four confidence options. Prose is the fallback when there is no
tool to call — never a stylistic choice when there is one.

**Every Phase 2 probe is immediately followed by its own confidence question
in the same call.** Pack **at most two probes per `AskUserQuestion` call**,
interleaved probe → confidence → probe → confidence (that is the tool's
4-question limit, and the confidence questions are not optional filler):

```
[L1-Q1, conf-Q1, L1-Q2, conf-Q2] → [L1-Q3, conf-Q3, L1-Q4, conf-Q4] → [L1-Q5, conf-Q5]
```

Confidence is a judgment about a specific answer and it decays fast: swept up
at the end of a layer, the respondent is reconstructing how sure they felt
several questions ago, which is a worse measurement than the one taken with
the answer in hand — and a separate sweep costs *more* round-trips, not
fewer. Never defer confidence to the end of a layer or of Phase 2.

**Drop to one probe in the call when the two would leak into each other** —
if answering the second would reveal the first's answer, or the first's
framing telegraphs the second (common when both probe the same function or
the same request path). Leakage inflates Gₑ, which is the one error this
whole skill exists to avoid; a saved round-trip is never worth it. Prefer
pairs drawn from *different* parts of the layer.

The confidence question can't quote the answer (you haven't seen it yet), so
address it by label — "How confident are you in your answer to L1-Q2?"

**Track the run with the task list.** Before Phase 0, create one task per
phase with `TaskCreate` (Phase 0 resolve scope → Phase 1 scan complexity →
Phase 2 test grasp → Phase 3 grade → Phase 4 report + remediate; add Phase 5
only if the user opts in). Mark each `in_progress` with `TaskUpdate` when
you start it and `completed` when it finishes, so the user can see which
phase the run is in. For a multi-layer Phase 2, add one sub-task per probed
layer — the probe is the longest stretch of the run and the user needs to
see it advancing.

## Arguments

Parse these from the invocation (all optional):

- **scope** — a repo path or a PR/branch ref. If absent, auto-detect (Phase 0).
- **format** — `free-text` or `multiple-choice` for the Phase 2 probe. If
  absent, ask the respondent, explaining the tradeoff.
- **questions-per-layer** — integer. Default is **adaptive to change size**
  (see the depth table in `references/comprehension-probes.md`): more
  questions for larger changes, up to the **maximum for a whole-repo**
  scope, down to 1 for tiny diffs or thin layers. An explicit value
  overrides the table.

Echo the resolved arguments into the report's methodology section.

## Phase 0 — Resolve scope

Decide *what* is being measured before anything else.

1. **Explicit repo path given** → whole-repo mode on that path.
2. **PR number / branch ref given** → PR mode on that diff vs `origin/main`.
3. **No argument (default)** → inspect the current directory:
   - Not a git repo → whole-repo mode on the current dir.
   - On a non-`main` branch **with** a non-empty diff against the base
     → **PR mode** (measure only the diff). Resolve the base as
     `origin/main`, falling back to `origin/HEAD` if `origin/main` is
     absent:
     ```bash
     branch=$(git rev-parse --abbrev-ref HEAD)
     base=$(git rev-parse --verify --quiet origin/main >/dev/null && echo origin/main || git symbolic-ref --quiet refs/remotes/origin/HEAD | sed 's@^refs/remotes/@@')
     if [ -z "$base" ]; then
       echo "No origin/main or origin/HEAD to diff against — falling back to whole-repo mode."
     else
       git diff --stat "$base"...HEAD
     fi
     ```
     Guard the empty `base`: with **no** `origin/main` **and no**
     `origin/HEAD` (e.g. no remote), `git diff "$base"...HEAD` would
     silently diff `HEAD...HEAD` (empty) and mislabel the run — so treat an
     unresolved base as **whole-repo mode** and say so, rather than
     reporting a spurious empty PR diff.
   - On `main` (or no diff) → whole-repo mode.

State the resolved scope to the user before proceeding. **PR mode
measures debt *introduced by this change*, not the repo's total** —
weight and phrase everything accordingly.

## Phase 1 — Scan complexity (Cₛ)

Gather observable signals and assign each layer a **0-5 complexity
score**. Scanning breadth depends on scope:

- **Whole-repo:** LOC, file/module count, dependency fan-in/out, external
  integrations, config/infra sprawl, test presence.
- **PR mode:** files touched, layers crossed, lines changed, whether the
  diff alters public contracts, schemas, or architecture boundaries.

Map signals to layers (see `references/framework.md` for the full table):

- **L1 Implementation** — code volume/complexity, nesting, churn.
- **L2 Design** — component count, coupling, interface surface.
- **L3 Architecture** — service/module boundaries, cross-cutting concerns.
- **L4 Requirements** — presence/clarity of specs, requirement tests,
  domain docs. *(Often invisible in PR mode — say so, don't invent it.)*

Record the file paths / metrics behind each score; they go in the report.

## Phase 2 — Test grasp (Gₑ)

Complexity alone is not debt — debt is the *gap*. Do **not** ask the
respondent to self-rate; a self-rating measures confidence, not
comprehension. Instead **test** grasp with grounded questions and score
the answers. Full protocol in `references/comprehension-probes.md`; the
essentials:

- Pick the format from the `format` arg (`free-text` or `multiple-choice`).
  If unset, ask the respondent **via `AskUserQuestion`**, explaining the
  tradeoff in the option descriptions: free-text is the deeper, un-guessable
  signal but slower; multiple-choice is fast and structured but guessable
  (recognition ≠ recall, so it over-states grasp — and the 4-option cap
  leaves only 3 distractors, so a guess starts at 25%).
- For each layer present, ask `questions-per-layer` questions. If not set
  explicitly, derive the count from the change-size depth table in
  `references/comprehension-probes.md` (whole-repo = max). Sample parts
  weighted toward the highest-complexity areas from Phase 1. **For L1
  questions, paste the relevant code snippet(s) inline** (with `file:line`)
  so the probe tests reasoning over concrete code, not recall of where it
  lives.
- Generate each question with a code-derived reference answer + `file:line`
  so grading is auditable. Grade **correctness per claim, confidence per
  answer**: an articulated answer mixes parts of differing certainty, so
  decompose it into its distinct claims and score each 0.0–1.0; capture one
  overall confidence for the whole answer, as before. A correct rebuttal
  raises the affected claim.
- **Pose every probe question through `AskUserQuestion`** — never as prose
  in chat, **at most two probes per call**, each immediately followed by its
  own confidence question (see the interaction rules above; drop to one probe
  when the pair would leak). Code snippets and `file:line` citations go in the
  chat message that precedes the call (options are too short to hold them);
  each probe's question text then references its snippet by label.
- **Confidence rides in the same call as the probe it rates** — options
  Guessing / Somewhat / Confident / Certain (→ 0.1 / 0.4 / 0.7 / 0.95),
  phrased against that probe's label. Never defer it to the end of a layer or
  the end of Phase 2: the respondent is freshest about the answer they are
  giving right now, a reconstructed confidence corrupts the calibration gap,
  and a deferred sweep costs extra round-trips besides. Asked this way it also
  lands before any grading is revealed, which is required.
- Skip layers with no observable complexity rather than testing hollow
  ground. Feed every layer's answers (confidence + claims) to
  `scripts/grasp.py`, the same way Phase 3 feeds `score.py` — it returns
  `Gₑ`, correctness, confidence, and the calibration gap/flag, so the
  aggregation is reproducible rather than re-derived by hand:

```bash
echo '{"L1_implementation": [{"confidence": 0.7, "claims": [1.0, 0.5]}, ...], ...}' \
    | python3 "${CLAUDE_PLUGIN_ROOT}/skills/epistemic-debt/scripts/grasp.py"
```

This is a work assessment, not an exam — don't police code access; instead
ask *why / what-if / trace / what-would-you-change* questions a glance
can't answer.

## Phase 3 — Grade with cascade discounting

A gap at a higher layer forces rework in every layer beneath it, so gaps
are **not** equal. Weight each layer's gap by its cascade multiplier
(L1≈1×, L2≈4×, L3≈10×, L4≈30×) and map the total to a grade band.

Prefer the deterministic script for reproducibility. Invoke it by its
absolute bundled path — never rely on the shell's working directory:

```bash
# Installed as a plugin (include exactly the layers assessed in Phase 1,
# using these four exact names; omit a layer only if it was not assessed):
echo '{"L4_requirements":{"c":C,"g":G},"L3_architecture":{"c":C,"g":G},"L2_design":{"c":C,"g":G},"L1_implementation":{"c":C,"g":G}}' \
    | python3 "${CLAUDE_PLUGIN_ROOT}/skills/epistemic-debt/scripts/score.py"
# Standalone skill: use the absolute path to this skill's own scripts/score.py.
```

The script rejects any key that is not one of the four canonical layer
names, so a misspelled layer fails loudly instead of silently shrinking the
scope. **After invoking `score.py`, check that the returned `per_layer` keys
match the layers assessed in Phase 1 — if they differ, stop, fix the input,
and re-run rather than reporting a grade computed over the wrong layer set.**

If Python is unavailable, compute the same way inline following the logic
in `scripts/score.py`. Report the per-layer gap, the weighted
contribution, the overall grade, and the **dominant layer**. A layer
where grasp ≥ complexity carries epistemic *credit* — call that out.
Also record `debt_index_absolute` (magnitude on a fixed four-layer scale)
so grades can be ranked across PRs and repos; the grade itself uses the
scope-relative index.

## Phase 4 — Report and remediate (always runs)

**This phase always runs to completion.** The written report and next
actions are the point of the exercise — produce them automatically in every
run, never gate them behind a follow-up prompt or an optional next phase.

Write the assessment using `assets/report-template.md` to
`epistemic-debt/YYYY-MM-DD-{repo|pr-<ref>}.md` in the target repo (create
the dir). Then **explain the result to the user in chat** — grade, the
dominant risk, and the cascade it threatens.

Recommend next actions that **shift t₀ leftward** (detect the gap
earlier), tied to the dominant layer — e.g. requirement tests for L4,
fitness functions for L3, contract/integration tests for L2, human
review gates that break AI "circular confirmation." See the remediation
section of `references/framework.md`.

**Include a lightweight recovery estimate by default.** Feed the per-layer
gaps from Phase 3 to `scripts/recovery.py` — it applies the default
learning rates from `references/framework.md` and returns `τₖ` per layer,
`T_recovery = Σ τₖ`, and the cascade-weighted cost `Σ cₖ·τₖ` for the AI
break-even condition:

```bash
echo '{"gaps": {"L4_requirements": GAP, ...}}' \
    | python3 "${CLAUDE_PLUGIN_ROOT}/skills/epistemic-debt/scripts/recovery.py"
```

Fill the report's recovery-estimate section with the result. The script's
`estimate` field is `true` whenever any layer used a default rate — label
that output plainly as an **ESTIMATE from default rates** and print the
rates used, so the user gets numbers without asking and without them being
mistaken for the team's calibrated figures. The output's `layers_assessed`
counts the gap entries supplied: when it is `0`, the zeros mean **nothing
was measured** (every layer carried credit or was omitted) — report "no debt
to recover", never a calibrated zero-week recovery.

## Phase 5 — Quantitative deepening with real rates (optional, non-blocking)

The report is already written and delivered, carrying a default-rate estimate
(Phase 4). *That* is what makes this phase non-blocking — not the shape of
the question. So offer it **via `AskUserQuestion`** like every other
question: by the time you ask, the useful output is on disk and explained,
and a declined or ignored offer costs the user nothing.

The offer is a re-run passing the team's **own** learning rates and the
AI-time-saved `δ` to the same `scripts/recovery.py` call (via its `rates`
and `delta` input fields), for a calibrated `τₖ`/`T_recovery` and a real
break-even verdict. Only compute it once the user supplies those inputs; if
they decline, the delivered report stands on its own — end the run there
rather than pressing. After the re-run, cross-check each layer's
`using_default_rate` in the output: a layer the team supplied a rate for
must show `false` — a `true` there means the rate never reached the script,
so stop and fix the input instead of presenting default-rate numbers as
calibrated.

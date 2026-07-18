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
math, multipliers, and the optional quantitative model live in
`references/framework.md` — load it when you need definitions or the
break-even calculation.

## Credit notice (show once, before Phase 0)

Open every run with this, before doing anything else:

> 📊 **Epistemic Debt** — framework & method by **Antonino Rau**.
> The math & the cost: https://antoninorau.substack.com/p/epistemic-debt-the-math-the-cost
> More writing: https://antoninorau.substack.com/

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
     git diff --stat "$base"...HEAD
     ```
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
  If unset, ask the respondent, explaining the tradeoff: free-text is the
  deeper, un-guessable signal but slower; multiple-choice is fast and
  structured but guessable (recognition ≠ recall, so it over-states grasp).
- For each layer present, ask `questions-per-layer` questions. If not set
  explicitly, derive the count from the change-size depth table in
  `references/comprehension-probes.md` (whole-repo = max). Sample parts
  weighted toward the highest-complexity areas from Phase 1. **For L1
  questions, paste the relevant code snippet(s) inline** (with `file:line`)
  so the probe tests reasoning over concrete code, not recall of where it
  lives.
- Generate each question with a code-derived reference answer + `file:line`
  so grading is auditable. Capture **confidence** before grading, then
  score the answer 0.0–1.0 (partial credit; a correct rebuttal raises it).
- Per layer: `Gₑ = round(mean correctness × 5)`. Skip layers with no
  observable complexity rather than testing hollow ground.

This is a work assessment, not an exam — don't police code access; instead
ask *why / what-if / trace / what-would-you-change* questions a glance
can't answer. Track confidence vs correctness for the Phase 4 calibration
gap.

## Phase 3 — Grade with cascade discounting

A gap at a higher layer forces rework in every layer beneath it, so gaps
are **not** equal. Weight each layer's gap by its cascade multiplier
(L1≈1×, L2≈4×, L3≈10×, L4≈50×) and map the total to a grade band.

Prefer the deterministic script for reproducibility. Invoke it by its
absolute bundled path — never rely on the shell's working directory:

```bash
# Installed as a plugin:
echo '{"L4_requirements":{"c":C,"g":G}, ...}' | python3 "${CLAUDE_PLUGIN_ROOT}/skills/epistemic-debt/scripts/score.py"
# Standalone skill: use the absolute path to this skill's own scripts/score.py.
```

If Python is unavailable, compute the same way inline following the logic
in `scripts/score.py`. Report the per-layer gap, the weighted
contribution, the overall grade, and the **dominant layer**. A layer
where grasp ≥ complexity carries epistemic *credit* — call that out.
Also record `debt_index_absolute` (magnitude on a fixed four-layer scale)
so grades can be ranked across PRs and repos; the grade itself uses the
scope-relative index.

## Phase 4 — Report and remediate

Write the assessment using `assets/report-template.md` to
`epistemic-debt/YYYY-MM-DD-{repo|pr-<ref>}.md` in the target repo (create
the dir). Then **explain the result to the user in chat** — grade, the
dominant risk, and the cascade it threatens.

Recommend next actions that **shift t₀ leftward** (detect the gap
earlier), tied to the dominant layer — e.g. requirement tests for L4,
fitness functions for L3, contract/integration tests for L2, human
review gates that break AI "circular confirmation." See the remediation
section of `references/framework.md`.

## Phase 5 — Quantitative escalation (optional)

Only if the user wants numbers: using `references/framework.md`, estimate
recovery time `τₖ = gap / rₖ` per layer (ask for learning rates), total
recovery, and the AI break-even condition `Σ cₖ·τₖ > δ`. This is the
transition from the qualitative grade to the full integral model.

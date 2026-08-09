# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A **Claude Code plugin** (`epistemic-debt`) that grades a repository — or a single
PR diff — for *epistemic debt*: the gap between system complexity (`Cₛ`, scanned
from the repo) and team comprehension (`Gₑ`, tested directly, not self-rated). It
implements Antonino Rau's [Epistemic Debt framework](https://antoninorau.substack.com/p/epistemic-debt-the-math-the-cost). This is **not** a Python
package despite containing a few scripts — there is no build system, no
dependencies, and no packaging. The behavior is almost entirely prompt-driven
markdown; the scripts exist so every calculation the framework defines is
computed once, deterministically, instead of re-derived in prose on each run.

## Repository map

```
.claude-plugin/
  plugin.json              # Plugin manifest (name, version, author) — bump version here
  marketplace.json         # Marketplace listing; version must match plugin.json
commands/
  epistemic-debt.md        # /epistemic-debt slash command → delegates to the skill
skills/epistemic-debt/
  SKILL.md                 # THE spec: the 6-phase (Phase 0–5) workflow Claude executes
  references/framework.md          # Definitions, cascade math, break-even model (load on demand)
  references/comprehension-probes.md  # Phase 2 protocol: how to test grasp, depth table, scoring
  assets/report-template.md         # Output format for the written report
  scripts/score.py                  # Phase 3: cascade-weighted grade from per-layer (Cₛ, Gₑ)
  scripts/grasp.py                  # Phase 2: Gₑ + calibration gap from per-claim probe scores
  scripts/recovery.py               # Phase 4/5: recovery time (τₖ) + AI break-even from gaps
  scripts/cli_harness.py            # Shared subprocess runner + malformed-stdin contract assertion for the CLI tests (not matched by test_*.py discovery)
  scripts/test_score.py             # Unit + CLI tests for score.py
  scripts/test_grasp.py             # Unit + CLI tests for grasp.py
  scripts/test_recovery.py          # Unit + CLI tests for recovery.py
evals/
  README.md                # How to run the suite + case-authoring notes
  <case>/case.yaml         # One eval case: prompt, graders, weights
  <case>/scaffold.sh       # Builds that case's throwaway target repo
  results/                 # Run output (gitignored)
```

## The commands that matter

Everything else is markdown Claude reads at runtime. The three scripts are the
only *code* you can execute directly — all stdlib-only Python 3, no deps to
install — while the prompt-driven behavior around them is exercised by the
eval suite in `evals/`:

```bash
# score.py — cascade-weighted grade from per-layer complexity/grasp:
echo '{"L4_requirements":{"c":4,"g":2},"L3_architecture":{"c":3,"g":3},"L2_design":{"c":2,"g":3},"L1_implementation":{"c":4,"g":4}}' \
  | python3 skills/epistemic-debt/scripts/score.py

# grasp.py — Gₑ + calibration gap from per-claim probe answers:
echo '{"L1_implementation":[{"confidence":0.7,"claims":[1.0,0.5]}]}' \
  | python3 skills/epistemic-debt/scripts/grasp.py

# recovery.py — recovery time + break-even from per-layer gaps (imports
# CASCADE from score.py — Python puts a script's own directory on sys.path,
# so this resolves regardless of invocation cwd, same as the other two):
echo '{"gaps":{"L4_requirements":2,"L1_implementation":3}}' \
  | python3 skills/epistemic-debt/scripts/recovery.py
```

Any layer may be omitted (PR mode often has no L4 signal); omitted layers are
excluded from the weighting. An *unrecognised* top-level key, by contrast, is
a hard error in all three scripts — a misspelled layer name must fail loudly,
never silently shrink the graded scope.

**Test suite.** Each script has a stdlib-only `unittest` companion
(`test_<name>.py`, co-located) covering both its pure functions (with
hand-computed expected values in comments — recompute by hand when you touch
a formula, don't just accept whatever the code now returns) and its CLI
stdin/stdout contract via `subprocess`. Run the whole suite:

```bash
python3 -m unittest discover -s skills/epistemic-debt/scripts -p "test_*.py"
```

There is still no linter or CI configured. Add tests alongside any change to
a script's math; don't rely on ad-hoc manual runs to validate a formula.

**Eval suite.** The behavior that lives in markdown — scope resolution, the
credit notice, grounded (never self-rated) probes, routing every number
through the scripts, phase tracking — is scored by `claude plugin eval`
cases under `evals/`, one directory per case (gated in early access; see
`evals/README.md`). From the repo root:

```bash
claude plugin eval . --scaffold --allow-tools Bash Write
```

`--scaffold` is required (each case builds its own throwaway target repo);
`evals/README.md` has the case table, the grader types and the authoring
notes. **Changing prompt behavior means adding or updating a grader** — the
unit tests cannot see any of it.

Two constraints shape what a case can assert, both learned the hard way:
eval runs are **headless**, so `AskUserQuestion` is absent from the session
entirely (interactive-only — not gated, so no `--allow-tools` grant
conjures it) and a grader must score the *structure* of what was asked, not
the call; and with no respondent, any case reaching Phase 2 without
pre-supplied answers stops there. `TaskCreate`/`TaskUpdate` *are* available.

## Architecture / big picture

**Two-source design (`Cₛ` vs `Gₑ`).** Complexity is *scanned* from the repo;
grasp is *tested* with grounded questions about the actual code — never a
self-rating (a self-rating measures confidence, not comprehension). This split is
the core thesis; preserve it in any edit to `SKILL.md` or the probes reference.

**Runtime flow.** `/epistemic-debt` (or a natural-language ask) → the skill runs
Phase 0 resolve scope → Phase 1 scan complexity → Phase 2 test grasp via
`grasp.py` → Phase 3 grade via `score.py` → Phase 4 write report + explain
(always runs, includes a default-rate recovery estimate via `recovery.py`) →
Phase 5 optional deepening (`recovery.py` again, with the team's real rates).
`SKILL.md` is the authoritative description of this flow; the two
`references/` files are loaded on demand for depth.

**Scope auto-detection.** No arg → inspect cwd: non-`main` branch with a non-empty
diff vs `origin/main` (fallback `origin/HEAD`) = **PR mode** (measures debt the
change *introduces*); otherwise whole-repo. PR mode weights and phrases everything
as marginal debt, not total.

**Each script is the single source of truth for its slice of the math** —
this is why the calculations live in code, not prose: two runs of the same
inputs must yield the same numbers.
- `score.py` holds the canonical cascade multipliers **L1=1, L2=4, L3=10,
  L4=30**. `framework.md` documents the source's *ranges* (e.g. L4 30–70×)
  but explicitly defers to the script's fixed values. It also owns
  the shared symbols the other two import: `SCALE_MAX`, the input guards
  `check_number` (rejects JSON booleans explicitly — `bool` subclasses
  `int`, so a stray `true` would otherwise score as a full-credit claim, a
  maximum confidence or a one-point gap, turning malformed input into a
  plausible grade), `check_mapping`, `load_object` and `check_layer_names`
  (the strict unknown-key check shared with `grasp.py`), plus `run_cli`,
  the single CLI shell all three `main()`s collapse onto. That shell is the
  one failure contract: **exit 1 and a single legible line on stderr, never
  a traceback** — the skill reads that stderr, and a stack trace buries the
  sentence saying what was wrong with the input.
- `grasp.py` holds the claim/answer aggregation (`answer correctness =
  mean(claim correctness)`, `Gₑ = round(correctness × 5)` — Python
  round-half-to-even: 2.5 → 2, 4.5 → 4), the calibration
  gap/flag thresholds (output key `calibration_gap`, distinct from
  recovery.py's C−G `gaps`), and `CONFIDENCE_LABELS` — the
  Guessing/Somewhat/Confident/Certain → 0.1/0.4/0.7/0.95 map that `SKILL.md`
  and `comprehension-probes.md` quote when phrasing the confidence question.
  `comprehension-probes.md` documents the protocol for *generating* the
  inputs; the script owns aggregating them.
- `recovery.py` holds `DEFAULT_RATES`, `τₖ`, `T_recovery`, `Cₖ`, and the
  break-even check, importing `CASCADE` and `check_number` from `score.py`
  rather than duplicating them. `framework.md` documents the model; the
  script computes it.

If you change a multiplier, rate, or threshold, change it in the owning
script and reconcile the corresponding note in its `references/` doc — never
let a script and its doc diverge.

**Two indices, one grade.** `debt_index` is scope-relative (denominator = only the
layers present) and **drives the grade**; `debt_index_absolute` uses the fixed
four-layer denominator for cross-PR/cross-repo *ranking*. Keep both meanings intact.

**Calibration knobs (labeled in `score.py`).** `BANDS` (grade cutoffs),
`FLOOR_WEIGHT` (lets one severe high-layer gap floor the grade so clean lower
layers can't average it away), and `CASCADE`. These are deliberate policy dials —
read the inline comments before touching them. Note the intentional `L1=0.3` floor
rationale: pervasive "nobody can explain this" AI-generated code must register even
though L1 has nothing beneath it to cascade into.

**Epistemic credit.** When `grasp > complexity` a layer carries *credit*, not debt
(gap floored at 0). The report and grader both surface `credit_layers` — don't
collapse this to "zero debt."

**Interaction is tool-mediated, not prose.** Every question the skill puts to
the user goes through `AskUserQuestion` (format choice, every Phase 2 probe and
its confidence follow-up, the Phase 5 offer) — never a prose prompt awaiting a
free-form reply. Phase progress is tracked with `TaskCreate`/`TaskUpdate`. Both
rules are stated in `SKILL.md`'s "Interaction rules" section; the per-question
mechanics (max 4 options, snippet labelling) live in
`comprehension-probes.md`. **Each probe is immediately followed by its own
confidence question in the same call, at most two probes per call**
(`[L1-Q1, conf-Q1, L1-Q2, conf-Q2] → …`) — the tool's 4-question cap is what
sets the pair size. Confidence reconstructed at the end of a layer is a worse
measurement and the calibration gap depends on it, so don't "optimise" this
into per-layer sweeps — sweeps also cost *more* calls, not fewer. The
counter-pressure on packing two probes together is **leakage**: the
respondent sees both before answering either, so probes sharing a call must
come from different parts, else drop to one. `AskUserQuestion` is
interactive-only, so a headless session doesn't have it at all — `SKILL.md`
gives a prose fallback that keeps the batching, labels and pairing, which is
also the only form the evals can observe.

## Conventions specific to this repo

- **Version bumps** must be applied in **both** `.claude-plugin/plugin.json` and
  `.claude-plugin/marketplace.json` (they currently mirror each other), and get
  a `CHANGELOG.md` entry. `claude plugin validate .` checks the two manifests
  agree; `claude plugin tag .` cuts the release tag and re-checks. Bump the
  version even for a prompt-only change: clients cache the plugin under its
  version string, so an unchanged version means `claude plugin update` reports
  "already at the latest version" and users keep running the old markdown.
- **Attribution is required.** Every run shows the credit notice for Antonino Rau
  before Phase 0, and the report template ends with the credit footer. The ⚠️
  "estimate, not a fact" disclaimer is **part of the mandatory credit block** —
  in both `SKILL.md` and `commands/epistemic-debt.md` — and must never be
  dropped from it: a tool about miscalibrated confidence carries its own
  calibration caveat where the user of the tool sees it. Preserve the
  Substack links (`plugin.json` homepage, README, SKILL.md credit block, template
  footer) when editing.
- **Invoke every script by absolute path** from the skill —
  `"${CLAUDE_PLUGIN_ROOT}/skills/epistemic-debt/scripts/{score,grasp,recovery}.py"`
  — never rely on the shell's working directory (the skill runs against
  arbitrary target repos).
- Reports are written by the *target* repo's run to
  `epistemic-debt/YYYY-MM-DD-{repo|pr-<ref>}.md`; that output dir is not part of
  this plugin's own tree.
- All three scripts target Python 3, stdlib only, `from __future__ import
  annotations`. Keep them dependency-free — they must run anywhere a target
  repo lives. `score.py` is the base module: `grasp.py` and `recovery.py`
  both import from it (co-located, no package/install needed) and nothing
  imports back. Adding a symbol to that existing edge is fine; a new edge
  between scripts, or any third-party dependency, is not.

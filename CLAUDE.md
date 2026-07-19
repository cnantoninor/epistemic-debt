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
  scripts/test_score.py             # Unit + CLI tests for score.py
  scripts/test_grasp.py             # Unit + CLI tests for grasp.py
  scripts/test_recovery.py          # Unit + CLI tests for recovery.py
```

## The commands that matter

Everything else is markdown Claude reads at runtime. The three scripts are the
only things you can execute and test directly — all stdlib-only Python 3, no
deps to install:

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
excluded from the weighting.

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
  but explicitly defers to the script's fixed values.
- `grasp.py` holds the claim/answer aggregation (`answer correctness =
  mean(claim correctness)`, `Gₑ = round(correctness × 5)`) and the
  calibration gap/flag thresholds. `comprehension-probes.md` documents the
  protocol for *generating* the inputs; the script owns aggregating them.
- `recovery.py` holds `DEFAULT_RATES`, `τₖ`, `T_recovery`, `Cₖ`, and the
  break-even check, importing `CASCADE` from `score.py` rather than
  duplicating it. `framework.md` documents the model; the script computes it.

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

## Conventions specific to this repo

- **Version bumps** must be applied in **both** `.claude-plugin/plugin.json` and
  `.claude-plugin/marketplace.json` (they currently mirror each other).
- **Attribution is required.** Every run shows the credit notice for Antonino Rau
  before Phase 0, and the report template ends with the credit footer. Preserve the
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
  repo lives. `recovery.py` imports `CASCADE` from `score.py` (co-located, no
  package/install needed); don't introduce any other cross-script or
  third-party dependency.

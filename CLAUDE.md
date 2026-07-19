# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A **Claude Code plugin** (`epistemic`) that grades a repository — or a single
PR diff — for *epistemic debt*: the gap between system complexity (`Cₛ`, scanned
from the repo) and team comprehension (`Gₑ`, tested directly, not self-rated). It
implements Antonino Rau's [Epistemic Debt framework](https://antoninorau.substack.com/p/epistemic-debt-the-math-the-cost). This is **not** a Python
package despite containing one script — there is no build system, no dependencies,
and no packaging. The behavior is almost entirely prompt-driven markdown.

## Repository map

```
.claude-plugin/
  plugin.json              # Plugin manifest (name, version, author) — bump version here
  marketplace.json         # Marketplace listing; version must match plugin.json
commands/
  debt.md                  # /epistemic:debt slash command → delegates to the skill
skills/debt/
  SKILL.md                 # THE spec: the 6-phase (Phase 0–5) workflow Claude executes
  references/framework.md          # Definitions, cascade math, break-even model (load on demand)
  references/comprehension-probes.md  # Phase 2 protocol: how to test grasp, depth table, scoring
  assets/report-template.md         # Output format for the written report
  scripts/score.py                  # Deterministic cascade-weighted grader (the only code)
```

## The one command that matters

Everything else is markdown Claude reads at runtime. The scoring script is the
only thing you can execute and test directly:

```bash
# Smoke-test / run the grader (stdlib-only, Python 3; no deps to install):
echo '{"L4_requirements":{"c":4,"g":2},"L3_architecture":{"c":3,"g":3},"L2_design":{"c":2,"g":3},"L1_implementation":{"c":4,"g":4}}' \
  | python3 skills/debt/scripts/score.py
```

Any layer may be omitted (PR mode often has no L4 signal); omitted layers are
excluded from the weighting. There is no test suite, linter, or CI configured —
validate changes to `score.py` by running representative inputs through it.

## Architecture / big picture

**Two-source design (`Cₛ` vs `Gₑ`).** Complexity is *scanned* from the repo;
grasp is *tested* with grounded questions about the actual code — never a
self-rating (a self-rating measures confidence, not comprehension). This split is
the core thesis; preserve it in any edit to `SKILL.md` or the probes reference.

**Runtime flow.** `/epistemic:debt` (or a natural-language ask) → the skill runs
Phase 0 resolve scope → Phase 1 scan complexity → Phase 2 test grasp → Phase 3
grade via `score.py` → Phase 4 write report + explain → Phase 5 optional
quantitative escalation. `SKILL.md` is the authoritative description of this flow;
the two `references/` files are loaded on demand for depth.

**Scope auto-detection.** No arg → inspect cwd: non-`main` branch with a non-empty
diff vs `origin/main` (fallback `origin/HEAD`) = **PR mode** (measures debt the
change *introduces*); otherwise whole-repo. PR mode weights and phrases everything
as marginal debt, not total.

**`score.py` is the single source of truth for grading.** It holds the canonical
cascade multipliers **L1=1, L2=4, L3=10, L4=30**. `framework.md` documents the
source's *ranges* (e.g. L4 30–70×) but explicitly defers to the script's fixed
values so results are reproducible. If you change a multiplier, change it in
`score.py` and reconcile the note in `framework.md` — never let them diverge.

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
  `.claude-plugin/marketplace.json` (they currently mirror each other at `2.0.0`).
- **Attribution is required.** Every run shows the credit notice for Antonino Rau
  before Phase 0, and the report template ends with the credit footer. Preserve the
  Substack links (`plugin.json` homepage, README, SKILL.md credit block, template
  footer) when editing.
- **Invoke `score.py` by absolute path** from the skill —
  `"${CLAUDE_PLUGIN_ROOT}/skills/debt/scripts/score.py"` — never rely on
  the shell's working directory (the skill runs against arbitrary target repos).
- Reports are written by the *target* repo's run to
  `epistemic-debt/YYYY-MM-DD-{repo|pr-<ref>}.md`; that output dir is not part of
  this plugin's own tree.
- `score.py` targets Python 3, stdlib only, `from __future__ import annotations`.
  Keep it dependency-free — it must run anywhere a target repo lives.

# Changelog

All notable changes to the `epistemic-debt` plugin.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and the project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).
Version numbers live in `.claude-plugin/plugin.json` and
`.claude-plugin/marketplace.json`, which must always agree.

## [1.2.0]

Version `1.1.0` was bumped mid-branch and never released; everything below
ships together as `1.2.0`. This release also carries the changes merged to
`main` after `v1.0.0` was tagged, which never received a version bump of
their own — see *Merged to main after v1.0.0* at the end.

### Added

- **`grasp.py`** — Phase 2's aggregation: per-claim correctness into an
  answer score, answers into a layer `Gₑ`, plus the calibration gap and its
  overconfident/underconfident flag. Previously computed in prose, so two
  runs of the same answers could disagree.
- **`recovery.py`** — Phase 4/5's recovery time (`τₖ`), total recovery, the
  cascade-weighted cost and the AI break-even check.
- **Unit tests for all three scripts** (`test_*.py`, stdlib `unittest`, 83
  tests) covering both the pure functions and the CLI stdin/stdout contract,
  with hand-computed expected values recorded in comments.
- **Eval suite** under `evals/` — four `claude plugin eval` cases scoring the
  prompt-driven behavior the unit tests cannot reach: whole-repo and PR scope
  resolution, a non-git directory, grounded probes, and an end-to-end run
  whose numbers are checked against the actual script calls.
- **CI and a dev workflow** — `.github/workflows/ci.yml` runs the unit suite
  on Python 3.9 and 3.13, `ruff` (rules pinned explicitly in
  `pyproject.toml`), and a manifest version-sync check, all through the same
  `make` targets a contributor runs locally or from the optional pre-push
  hook. `requirements.txt` stays empty on purpose: the plugin's scripts are
  stdlib-only, and only the linter uses a venv.
- **A default-rate recovery estimate in every run.** Phase 4 always emits the
  report, the next actions and a recovery estimate; Phase 5 is now an
  optional re-run with the team's measured rates, offered after the report
  has already been delivered.

### Changed

- **Comprehension is graded per claim.** An articulated answer is decomposed
  into its independently checkable assertions and each is scored 0–1, instead
  of one judged score for a multi-part answer. Confidence remains one value
  per answer.
- **Every question goes through `AskUserQuestion`** — the format choice, each
  probe, the Phase 5 offer — never prose awaiting a free-form reply. Each
  probe is followed by its own confidence question in the same call, at most
  two probes per call, and two probes sharing a call must come from different
  parts of the layer so neither leaks the other's answer. Phase progress is
  tracked with `TaskCreate`/`TaskUpdate`. Where the tool is absent (headless
  sessions), a documented prose fallback preserves the batching and pairing.
- The three CLIs share one shell (`run_cli` in `score.py`), so the failure
  contract — exit 1 with a single legible line on stderr, never a traceback —
  is enforced in one place.
- `grasp.py`'s per-layer `gap` is now `calibration_gap`, distinguishing it
  from the C−G scale-point `gaps` that `recovery.py` consumes.
- `recovery.py` reports `layers_assessed`, so "nothing was measured" is
  distinguishable from a calibrated zero-week recovery.
- `dominant_layer` and `credit_layers` are now deterministic: on a weighted
  tie the higher cascade layer wins, and credit layers print in L4→L1 order.
  Previously a permutation of the input keys could change the reported
  dominant layer. Grades were never affected.
- The report template's recovery table takes its rate column from the
  script's output, so it stays correct when Phase 5 substitutes real rates.

### Fixed

- **Unrecognised layer names are a hard error** in all three scripts. They
  were silently dropped, and because the debt index is scope-relative, a
  one-character typo recomputed a clean-looking grade over the surviving
  layers — an F could read as an A with nothing on stderr.
- **JSON booleans are rejected as scores.** `bool` subclasses `int`, so a
  stray `true` scored as a full-credit claim, a maximum confidence or a
  one-point gap, turning malformed input into a plausible grade.
- Non-finite (`NaN`/`Inf`) and out-of-range confidence, claim and gap values
  are rejected instead of propagating into the output.
- Gaps are bounded by the 0–5 scale, so passing `score.py`'s `weighted` field
  (which sits next to `gap` in its output) no longer inflates the recovery
  estimate 10–30×.
- `recovery.py` rejects unknown layer names in `rates`, and rates given for a
  layer with no gap. A typo there silently reverted that layer to the policy
  default, defeating the one thing Phase 5 exists to do.
- `gapₖ` is floored at zero in the recovery formula, matching the epistemic
  credit floor `score.py` already applied.
- `cumulative_cost` accumulates from unrounded values, so the highest layer's
  figure matches `T_recovery` instead of drifting.
- The ⚠️ "estimate, not a fact" disclaimer is part of the credit block shown
  at the start of every run, in both `SKILL.md` and the slash command. It had
  survived only in the README, where the person running the tool never sees
  it.

### Merged to main after v1.0.0

These shipped to `main` without a version bump and are released here for the
first time:

- **L4 cascade multiplier lowered 50 → 30**, so L4 no longer dominates the
  ranking magnitude, propagated to the report template and `SKILL.md`.
- Phase 0 guards against an empty diff base.
- README gained the "Complexity − Grasp" concept section, a concrete
  walkthrough and an example report.

## [1.0.0]

Initial release: the six-phase workflow (Phase 0–5), `score.py`'s
cascade-weighted grade, the comprehension-probe protocol, the framework
reference and the report template.

[1.2.0]: https://github.com/cnantoninor/epistemic-debt/releases/tag/v1.2.0
[1.0.0]: https://github.com/cnantoninor/epistemic-debt/releases/tag/v1.0.0

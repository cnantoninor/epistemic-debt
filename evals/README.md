# Plugin evals

Eval cases for `claude plugin eval`, scoring the *prompt-driven* behavior the
unit tests can't reach (the scripts' math is covered by
`skills/debt/scripts/test_*.py`).

> **Early access.** `claude plugin eval` is currently gated; if you see
> `plugin eval is currently in early access`, the suite is authored and valid
> but can't run on this account yet.

## Cases

| Case | What it scores |
| --- | --- |
| `whole-repo-basics` | Credit notice (with the ⚠️ estimate disclaimer) shown to the user before Phase 0, whole-repo scope resolution, Phase 2 probes grounded in the scanned code (never self-ratings), each probe paired with its own confidence question, and phase tracking in the task list. Headless runs stop when Phase 2 waits for answers — only Phases 0–2 are graded. |
| `no-git-whole-repo` | Phase 0 on a **non-git** directory (scaffold has no `git init`): must resolve to whole-repo mode on the cwd, without attempting a PR/diff or treating the missing repo as an error. Headless runs stop when Phase 2 waits — only Phases 0–2 are graded. |
| `pr-mode` | Scope auto-detection: feature branch + diff vs `origin/main` → PR mode, with everything phrased as *marginal* debt of the diff (an intentionally opaque retry helper). |
| `scripted-math` | End-to-end run with probe answers supplied up front: every number must come from `grasp.py` / `score.py` / `recovery.py` (checked via `tool_used` / `tool_order` graders), the `per_layer` keys returned by `score.py` must be cross-checked against the layers assessed, the recovery output must be labelled an ESTIMATE from default rates, and the written report must carry the attribution footer. This is the only case that reaches Phases 3–4 headlessly, so Phase 3/4 instructions are graded here. |

Each case's `scaffold_script` builds a throwaway target repo, so the plugin is
exercised against realistic scan input rather than this repo itself.

## Running

From the repo root:

```bash
claude plugin eval . --scaffold --allow-tools Bash Write
```

- `--scaffold` is required — cases rely on `scaffold_script` to build their
  target repos (off by default; only enable on case files you authored).
- `--allow-tools Bash Write` grants the gated tools the cases request.
- Useful extras: `--case '<glob>'` / `--tag <tag>` to filter,
  `--runs 1` for a cheap smoke pass (cases default to 2),
  `--verbose` to stream traces, `--keep-temp` to inspect scaffold dirs,
  `--report report.html` for a self-contained HTML report.

Results land in `evals/results/<timestamp>/` (gitignored).

## Authoring notes

- Schema: `schema_version: "1.0"` (binary supports up to 1.x). Required:
  `name`, `execution.prompt` (or `context.history_file`), ≥1 grader.
- Grader types: `regex` (targets `trace` / `last_message` / `files` — `files`
  means files *created during the run*), `tool_used`, `tool_order`,
  `file_exists` (also created-files only), `llm` (judged by a small model;
  override with `--judge-model`), `baseline`.
- Keep grader names unique within a case; `weight` skews the case score.
- **`AskUserQuestion` does not exist in an eval session.** It is
  interactive-only, so it is absent from the run's tool list rather than
  gated — `--allow-tools` cannot grant it and `allowed_tools` cannot request
  it. Never write a grader that expects the call; grade the *structure* of
  the questions instead (the skill's documented prose fallback preserves the
  batching, labels and probe→confidence pairing). `TaskCreate` / `TaskUpdate`
  **are** available, so phase tracking is gradable with `tool_used`.
- Headless runs have no respondent, so any case that reaches Phase 2 without
  supplying answers up front stops there. Score Phases 0–2 only, or pre-supply
  probe results in the prompt the way `scripted-math` does.

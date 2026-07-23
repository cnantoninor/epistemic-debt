# Plugin evals

Eval cases for `claude plugin eval`, scoring the *prompt-driven* behavior the
unit tests can't reach (the scripts' math is covered by
`skills/epistemic-debt/scripts/test_*.py`).

> **Early access.** `claude plugin eval` is currently gated; if you see
> `plugin eval is currently in early access`, the suite is authored and valid
> but can't run on this account yet.

## Cases

| Case | What it scores |
| --- | --- |
| `whole-repo-basics` | Credit notice before Phase 0, whole-repo scope resolution, Phase 2 probes grounded in the scanned code (never self-ratings). Headless runs stop when Phase 2 waits for answers — only Phases 0–2 are graded. |
| `pr-mode` | Scope auto-detection: feature branch + diff vs `origin/main` → PR mode, with everything phrased as *marginal* debt of the diff (an intentionally opaque retry helper). |
| `scripted-math` | End-to-end run with probe answers supplied up front: every number must come from `grasp.py` / `score.py` / `recovery.py` (checked via `tool_used` / `tool_order` graders), and the written report must carry the attribution footer. |

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

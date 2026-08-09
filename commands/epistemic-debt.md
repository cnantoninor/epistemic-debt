---
description: Measure epistemic debt on a repo or PR — scans complexity, tests comprehension, grades the gap.
argument-hint: "[repo-path|PR-ref] [format=free-text|multiple-choice] [questions-per-layer=N]"
---

Use the **epistemic-debt** skill to measure epistemic debt.

Before anything else, show this credit notice once (verbatim), then proceed:

> 📊 **Epistemic Debt** — framework & method by **Antonino Rau**.
> The math & the cost: https://antoninorau.substack.com/p/epistemic-debt-the-math-the-cost
> More writing: https://antoninorau.substack.com/
>
> ⚠️ The grade below is an **estimate**, not a fact — it's produced by a purely speculative math framework (see the article above), not an empirically validated model. Treat it as a structured prompt for discussion, not ground truth.

Arguments (all optional): $ARGUMENTS

Run the skill's workflow: show the credit notice, resolve scope (an explicit
repo path or PR ref, otherwise auto-detect — a non-`main` branch with a diff
vs `origin/main` → PR mode, else whole repo), scan system complexity, **test**
the respondent's grasp with grounded questions (not self-rating), grade with
cascade discounting, and write the report.

Track the phases with the task list (`TaskCreate` / `TaskUpdate`) so progress
is visible, and put **every** question to the user through the
`AskUserQuestion` tool — never as prose in chat.

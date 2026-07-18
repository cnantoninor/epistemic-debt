# Epistemic Debt

> Measure how far your system's complexity has outpaced your team's comprehension.

A [Claude Code](https://docs.claude.com/en/docs/claude-code) plugin that grades a
repository — or a single PR — for **epistemic debt**: the accumulated opacity
that builds up when code (increasingly AI-generated) is shipped faster than
humans can actually understand it.

📖 **Read the framework:** [Epistemic Debt: The Math, The Cost](https://antoninorau.substack.com/p/epistemic-debt-the-math-the-cost)
✍️ **More writing:** [antoninorau.substack.com](https://antoninorau.substack.com/)

## Why it's different

A linter measures the *code*. A self-assessment measures your *confidence*.
This tool measures the **gap between complexity and comprehension** — because
the real danger of AI-assisted development is code that is *confidently wrong*:
it passes CI, looks right, and no human can actually explain it.

1. **Scans** the repo/PR for system complexity (`Cₛ`) across four layers —
   Implementation, Design, Architecture, Requirements.
2. **Tests** your grasp (`Gₑ`) with grounded questions about *your actual code*
   — not a self-rating. It even reports a **calibration gap** (how confident
   you felt vs. how right you were).
3. **Grades** the debt with **cascade-weighted** scoring — a requirements gap
   cascades far wider than an implementation one — and reports the dominant
   risk plus remediation next steps.

## Install

```
/plugin marketplace add cnantoninor/epistemic-debt
/plugin install epistemic-debt
```

Then, in any repo:

```
/epistemic-debt
```

…or just ask: *"measure epistemic debt on this repo."*

### Scope & options

- **Auto-scope:** a non-`main` branch with changes → measures the **PR diff**
  vs `origin/main`; otherwise the **whole repo**.
- `format=free-text` (deeper signal) or `format=multiple-choice` (faster).
- `questions-per-layer=N` — by default it **scales with change size**
  (1 for a tiny PR up to 5 for a whole-repo audit).

## How the grade works

Each layer's comprehension gap is weighted by its **cascade cost multiplier**
(L1≈1× → L4≈50×), normalized to a 0–1 index, with a floor so a severe
high-layer gap can't be averaged away by clean code. Two indices are emitted:
a **scope-relative** one (drives the grade, fair within a PR or repo) and an
**absolute** one (fixed scale, for ranking across PRs/repos).

## Credit

Framework and tool by **Antonino Rau** — [antoninorau.substack.com](https://antoninorau.substack.com/).
If this is useful, the [blog post](https://antoninorau.substack.com/p/epistemic-debt-the-math-the-cost)
is the best place to go deeper.

## License

[MIT](LICENSE).

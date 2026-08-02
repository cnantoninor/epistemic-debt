# Epistemic Debt

> Measure how far your system's complexity has outpaced your team's comprehension.

A [Claude Code](https://docs.claude.com/en/docs/claude-code) plugin that grades a
repository — or a single PR — for **epistemic debt**: the accumulated opacity
that builds up when code (increasingly AI-generated) is shipped faster than
humans can actually understand it.

📖 **Read the framework:** [Epistemic Debt: The Math, The Cost](https://antoninorau.substack.com/p/epistemic-debt-the-math-the-cost)
✍️ **More writing:** [antoninorau.substack.com](https://antoninorau.substack.com/)

> ⚠️ **This is an estimate, not a fact.** The grade is produced by a purely
> speculative math framework (see the article above) — it has not been
> empirically validated. Use it as a structured prompt for discussion, not
> ground truth.

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

## See it in action

Say a teammate opens a PR that adds **automatic payment retries**. CI is green,
the diff is clean, everyone approves. Here's what a run looks like:

**1. You ask.** On the PR branch:

```
/epistemic-debt
```

**2. It resolves scope.** Detects a non-`main` branch with a diff → **PR mode**,
so it grades the debt *this change introduces*, not the whole repo.

**3. It scans complexity (`Cₛ`).** Reads the diff and flags where the risk lives:
the retry loop touches the payment gateway and a shared idempotency key —
architecturally load-bearing, not just a new function.

**4. It tests your grasp (`Gₑ`).** Instead of "rate your confidence," it asks
grounded questions about *your* code, e.g.:

> *"If the gateway times out but the charge actually succeeded, what stops the
> retry from double-charging the customer?"*

Questions arrive as structured prompts, at most two at a time, and **each one
is immediately followed by "how confident are you in that answer?"** — rated
while the answer is still in your head, never reconstructed at the end. In
free-text mode you type your answer into the prompt's *Other* field. It then
grades against the real code and records how confident you felt vs. how right
you were.

**5. It grades and writes a report.** Cascade-weighted, saved to
`epistemic-debt/2026-07-18-pr-payment-retries.md`.

### What you get back (summarized)

> **Overall grade: C — Moderate** · Debt index 0.30 (scope-relative)
>
> **Verdict.** The implementation is clean — you grasp the code better than its
> raw complexity would suggest (**L1 carries epistemic *credit***). The debt this
> PR introduces sits one layer up: **nobody could explain how retries stay
> idempotent** when the gateway succeeds but times out. That's the
> confidently-wrong zone — it passes CI and looks right.
>
> | Layer | Complexity | Grasp | Gap | ×cost | Weighted |
> |-------|:---:|:---:|:---:|:---:|:---:|
> | L3 Architecture   | 4 | 2 | **2** | 10 | **20** |
> | L2 Design         | 3 | 3 | 0 | 4 | 0 |
> | L1 Implementation | 3 | 4 | *credit* | 1 | 0 |
>
> **Calibration:** L3 flagged **overconfident** (felt sure, answered wrong) —
> the exact gap the framework warns about.
>
> **Dominant risk:** a duplicate-charge path under retry. One clean layer of code
> can't average away a load-bearing gap it sits on top of.
>
> **Next action:** write the idempotency contract down and add a test for the
> timeout-but-succeeded case *before* merge — cheapest it will ever be to fix.

The grade is deterministic: those layer scores feed the bundled `score.py`, so
the same inputs always produce the same grade.

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
- `format=free-text` (deeper signal — you write the answer, so it can't be
  guessed) or `format=multiple-choice` (faster, but recognition ≠ recall, so
  it over-states grasp; the prompt caps a question at 4 options, leaving
  3 distractors).
- `questions-per-layer=N` — by default it **scales with change size**
  (1 for a tiny PR up to 5 for a whole-repo audit).

## The concept: Complexity − Grasp

Epistemic debt is what accumulates when a system's complexity outpaces the
team's understanding of it, integrated over time:

```
Ed = ∫ (Cₛ − Gₑ) dt
```

- **`Cₛ` — System Complexity:** how intricate the system actually is.
  *Observable* — scanned from the repo (LOC, fan-in/out, nesting depth,
  integrations, breadth of a diff).
- **`Gₑ` — Cognitive Grasp:** how well the team actually understands it.
  *Recorded nowhere* — it can only be elicited by asking grounded questions,
  never a self-rating (a self-rating measures confidence, not comprehension).

When `Cₛ > Gₑ` the gap is **debt** — opacity that compounds silently until a
production failure. When `Gₑ > Cₛ` the layer carries **epistemic credit** —
surplus understanding that buffers future complexity. The integral matters
because code written during low grasp becomes the foundation everything else
is built on.

### The scales

**Per-layer scores — `Cₛ` and `Gₑ` are each rated 0–5:**

| Score | Meaning |
|:-----:|---------|
| 0     | none / trivial |
| 1–2   | low |
| 3     | moderate |
| 4–5   | high / severe |

Each layer's **gap** = `Cₛ − Gₑ`, floored at 0 (a negative gap is *credit*, not
negative debt).

**Four abstraction layers, each with a cascade cost multiplier `cₖ`** — a gap
higher up forces rework in every layer beneath it, so it weighs far more:

| Layer | A gap here means the team… | `cₖ` |
|-------|----------------------------|:----:|
| **L4 Requirements**   | …doesn't grasp *what* the system must do | **30×** |
| **L3 Architecture**   | …doesn't grasp *how the pieces fit*      | **10×** |
| **L2 Design**         | …doesn't grasp *why components are shaped this way* | **4×** |
| **L1 Implementation** | …doesn't grasp *what the code actually does* | **1×** |

Weighted debt per layer = `gap × cₖ`. (The framework quotes *ranges* — L4
30–70×, L2 3–6× — but `score.py` fixes these exact values so grades are
reproducible.)

### From scores to a grade

The weighted gaps normalize to a **debt index (0–1)**, which maps to a letter
grade: low → **A / B** (Healthy / Minor), mid → **C** (Moderate), high →
**D / F** (Serious / Critical). A **floor** ensures one severe high-layer gap
can't be averaged away by clean lower-layer code. Two indices are emitted: a
**scope-relative** one (denominator = only the layers present) that drives the
grade, and an **absolute** one (fixed 4-layer denominator) for ranking across
PRs/repos.

**The core thesis:** the danger isn't complex code — it's complex code *nobody
can explain*. That's why `Cₛ` is scanned and `Gₑ` is tested, from two
independent sources.

## Credit

Framework and tool by **Antonino Rau** — [antoninorau.substack.com](https://antoninorau.substack.com/).
If this is useful, the [blog post](https://antoninorau.substack.com/p/epistemic-debt-the-math-the-cost)
is the best place to go deeper.

## License

[MIT](LICENSE).

# Epistemic Debt — Framework Reference

Source: Antonino Rau, "Epistemic Debt: The Math, The Cost"
<https://antoninorau.substack.com/p/epistemic-debt-the-math-the-cost>

Load this file when you need the exact definitions, the cost math, or the
remediation mechanisms. The SKILL runs qualitatively by default; the
quantitative section here is the optional escalation.

## Core idea

**Epistemic Debt (Ed)** = accumulated opacity when system complexity
outpaces team comprehension. Unlike technical debt (localised, fixable at
a boundary), epistemic debt *propagates*: unclear intent flows through
generated code, tests, and deployment, producing "circular confirmation"
when AI-written tests validate AI-written code. It compounds silently
until a production failure.

```
Ed = ∫₀ᵀ (Cₛ(t) − Gₑ(t)) dt
```

- `Cₛ(t)` — System Complexity at time t
- `Gₑ(t)` — Cognitive Grasp (team understanding) at time t
- The integral is cumulative: code written during low understanding
  becomes the foundation for everything built on top of it.

**Epistemic Credit** is the inverse — surplus understanding that buffers
new complexity: `Ce = ∫₀ᵀ (Gₑ(t) − Cₛ(t)) dt`. A layer where grasp
exceeds complexity carries *credit*, not debt.

## The four abstraction layers

```
Ed = Σₖ ∫₀ᵀ (Cₛ,ₖ(t) − Gₑ,ₖ(t)) dt
```

| k | Layer | What a gap here means |
|---|-------|-----------------------|
| L4 | Requirements | The team doesn't fully grasp *what* the system must do |
| L3 | Architecture | The team doesn't grasp *how the pieces fit* |
| L2 | Design | The team doesn't grasp *why components are shaped this way* |
| L1 | Implementation | The team doesn't grasp *what the code actually does* |

## Cascade cost multipliers (the "discounting")

A gap at a higher layer forces rework in every layer beneath it. Each
layer carries a dimensionless rework multiplier:

| Layer | Multiplier `cₖ` | Meaning |
|-------|-----------------|---------|
| L1 Implementation | ≈ 1× | Local fix |
| L2 Design | ≈ 3–6× | Ripples into implementation |
| L3 Architecture | ≈ 10× | Deeper cascade |
| L4 Requirements | ≈ 30–70× | Everything below must be revisited |

This is why grading must weight higher-layer gaps far more heavily:
1 unit of requirements debt is not 1 unit of implementation debt.

**Canonical values used by this tool:** the ranges above are the source's
spans; `scripts/score.py` is authoritative and uses fixed point values
**L1=1, L2=4, L3=10, L4=50**. If you ever grade without the script, use
those exact numbers so results stay reproducible.

## Measuring the two halves

`Cₛ` (system complexity) is **observable** from the repo:

- LOC, file/module count, dependency fan-in/fan-out
- Cyclomatic complexity, nesting depth
- Number of external integrations / services
- Breadth of the change (in PR mode: files touched, layers crossed)

`Gₑ` (cognitive grasp) is **not** recorded anywhere — the framework
calls it "undocumented." It can only be elicited by asking the team.
This is why the SKILL uses questions for grasp and scanning for complexity.

## Quantitative escalation (optional)

Only compute this when the user asks for numbers or a break-even.

**Recovery time per layer** — time to close the gap once you decide to:

```
τₖ = (Cₛ,ₖ(t₀) − Gₑ,ₖ(t₀)) / rₖ
```

- `t₀` — the moment the team recognises and starts closing the gap.
  Earlier `t₀` = narrower gap = cheaper recovery.
- `rₖ` — learning rate at layer k (empirical; ask the team).

**Total recovery:** `T_recovery = Σₖ τₖ`

**Effective (cascade-inclusive) cost at layer k:** `Cₖ = Σⱼ₌₁ᵏ τⱼ`

**AI break-even** — AI-assisted development is net-negative when the
cascade-weighted recovery cost exceeds the time AI saved:

```
Net Benefit = δ − Σₖ cₖ · τₖ         (δ = dev time saved by AI generation)
AI is a net loss when:  Σₖ cₖ · τₖ > δ
```

## Remediation — shifting t₀ leftward

The single biggest lever is detecting the gap *earlier* (smaller `t₀`
gap). Human-authored, deterministic mechanisms that surface divergence
before it compounds — these double as the skill's recommended next actions:

- End-to-end requirement tests (guard L4)
- Architectural fitness functions (guard L3)
- Integration tests validating design contracts (guard L2)
- Domain-Driven Design bounded contexts (contain L3/L4 spread)
- Human review gates that break "circular confirmation" — a human, not
  an AI-generated test, validates AI-generated code (the "Green CI Trap")

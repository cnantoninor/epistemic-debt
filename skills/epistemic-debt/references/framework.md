# Epistemic Debt — Framework Reference

Source: Antonino Rau, "Epistemic Debt: The Math, The Cost"
<https://antoninorau.substack.com/p/epistemic-debt-the-math-the-cost>

Load this file when you need the exact definitions, the cost math, or the
remediation mechanisms. The SKILL's grade is qualitative; the quantitative
section here powers both the report's always-on default-rate recovery
estimate and the optional deep re-run with the team's own rates.

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
**L1=1, L2=4, L3=10, L4=30**. L4 is pinned to the low end of its 30–70×
range (not the 50 midpoint) so it doesn't dominate the cross-repo ranking
magnitude; see the `CASCADE` comment in `score.py`. If you ever grade
without the script, use those exact numbers so results stay reproducible.

## Measuring the two halves

`Cₛ` (system complexity) is **observable** from the repo:

- LOC, file/module count, dependency fan-in/fan-out
- Cyclomatic complexity, nesting depth
- Number of external integrations / services
- Breadth of the change (in PR mode: files touched, layers crossed)

`Gₑ` (cognitive grasp) is **not** recorded anywhere — the framework
calls it "undocumented." It can only be elicited by asking the team.
This is why the SKILL uses questions for grasp and scanning for complexity.

## Quantitative escalation

The report always carries a **default-rate estimate** (Phase 4); a full
computation with the team's **own** measured rates is the optional
deepening (Phase 5).

**Recovery time per layer** — time to close the gap once you decide to:

```
τₖ = (Cₛ,ₖ(t₀) − Gₑ,ₖ(t₀)) / rₖ
```

- `t₀` — the moment the team recognises and starts closing the gap.
  Earlier `t₀` = narrower gap = cheaper recovery.
- `rₖ` — learning rate at layer k (empirical; ask the team).

**Default learning rates (for the always-on estimate).** Real `rₖ` are
empirical and team-specific, but the report includes a recovery estimate so
it never depends on a follow-up. Use these defaults unless the user supplies
their own — rates in **gap-points closed per engineer-week**; higher layers
learn slower because they need alignment, not just reading:

| Layer | Default `rₖ` (pts/eng-week) | Rationale |
|-------|-----------------------------|-----------|
| L1 Implementation | 2.0  | Read the code, run it |
| L2 Design         | 1.0  | Internalise why components are shaped so |
| L3 Architecture   | 0.5  | Build the system model, trace flows |
| L4 Requirements   | 0.33 | Needs stakeholder alignment, not just study |

So `τₖ = gapₖ / rₖ` yields engineer-weeks. These are **policy defaults** —
always label output computed from them as an ESTIMATE and print the rates
used. Phase 5 replaces them with the team's measured rates.

**Total recovery:** `T_recovery = Σₖ τₖ`

**Effective (cascade-inclusive) cost at layer k:** `Cₖ = Σⱼ₌₁ᵏ τⱼ`
(cumulative through layer k, in L1→L4 order).

**AI break-even** — AI-assisted development is net-negative when the
cascade-weighted recovery cost exceeds the time AI saved:

```
Net Benefit = δ − Σₖ cₖ · τₖ         (δ = dev time saved by AI generation)
AI is a net loss when:  Σₖ cₖ · τₖ > δ
```

**Canonical computation:** `scripts/recovery.py` is authoritative for all
of the above — given per-layer gaps (from `score.py`), it applies
`DEFAULT_RATES` (or supplied real rates), and returns `τₖ`, `T_recovery`,
`Cₖ`, and the break-even verdict once `δ` is supplied. Phases 4 and 5 both
call it; see `SKILL.md`. If you ever compute without the script, use these
exact definitions so results stay reproducible.

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

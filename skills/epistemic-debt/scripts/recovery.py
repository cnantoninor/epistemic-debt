#!/usr/bin/env python3
"""Deterministic recovery-time and AI break-even calculation.

Companion to `score.py`: takes the per-layer gaps `score.py` already
computed and turns them into a recovery-time estimate and the AI
break-even verdict from `references/framework.md`, so that math is
reproducible instead of re-derived in prose on every run.

    τₖ = gapₖ / rₖ                (recovery time, in engineer-weeks)
    T_recovery = Σₖ τₖ
    Cₖ = Σⱼ₌₁ᵏ τⱼ                 (cumulative recovery cost through layer k,
                                   in L1→L4 order)
    Net loss when: Σₖ cₖ · τₖ > δ  (δ = dev time AI saved, eng-weeks)

Usage (invoke by absolute path — see SKILL.md; do not rely on cwd):
    echo '{"gaps": {"L4_requirements": 2, "L3_architecture": 1,
                     "L2_design": 0, "L1_implementation": 3}}' \
        | python3 "${CLAUDE_PLUGIN_ROOT}/skills/epistemic-debt/scripts/recovery.py"

Any layer may be omitted (same layers `score.py` was given). Pass `rates`
to override the default learning rates for layers the team has measured
directly (Phase 5); omitted layers keep the default and the output flags
them as estimated. Pass `delta` (dev-weeks AI saved) to get the break-even
verdict; without it the verdict is left null pending that input.
"""
from __future__ import annotations

import json
import sys

from score import CASCADE, check_number  # co-located; cascade weights + input guard

# Default learning rates (gap-points closed per engineer-week). Empirical
# and team-specific in reality — these are policy defaults so the report
# always carries an estimate; see the rationale table in framework.md.
# CALIBRATION KNOB.
DEFAULT_RATES = {
    "L1_implementation": 2.0,
    "L2_design": 1.0,
    "L3_architecture": 0.5,
    "L4_requirements": 0.33,
}

# Canonical L1→L4 order for the cumulative cost Cₖ = Σⱼ₌₁ᵏ τⱼ.
LAYER_ORDER = ["L1_implementation", "L2_design", "L3_architecture", "L4_requirements"]


def compute_recovery(
    gaps: dict[str, float],
    rates: dict[str, float] | None = None,
    delta: float | None = None,
) -> dict[str, object]:
    rates = rates or {}
    per_layer: dict[str, dict[str, object]] = {}
    raw_tau: dict[str, float] = {}
    t_recovery = 0.0
    weighted_cost = 0.0

    for name, gap in gaps.items():
        if name not in CASCADE:
            raise ValueError(f"Unknown layer {name!r}.")
        gap = check_number(gap, f"Gap for {name!r}", minimum=0)
        using_default = name not in rates
        rate = check_number(rates.get(name, DEFAULT_RATES[name]), f"Rate for {name!r}")
        if rate <= 0:
            raise ValueError(f"Rate for {name!r} must be a finite number > 0; got {rate!r}.")
        tau = gap / rate
        raw_tau[name] = tau
        per_layer[name] = {
            "gap": gap,
            "rate": rate,
            "tau": round(tau, 3),
            "using_default_rate": using_default,
        }
        t_recovery += tau
        weighted_cost += CASCADE[name] * tau

    # Accumulate from the unrounded taus (not the rounded per_layer["tau"])
    # so the last layer's cumulative_cost always matches t_recovery, instead
    # of drifting from independently-rounded per-layer values.
    cumulative = 0.0
    for name in LAYER_ORDER:
        if name not in per_layer:
            continue
        cumulative += raw_tau[name]
        per_layer[name]["cumulative_cost"] = round(cumulative, 3)

    net_benefit = None
    breakeven_exceeded = None
    if delta is not None:
        # Same guard as gaps and rates: an unvalidated NaN here would make
        # `weighted_cost > delta` false and report "break-even not exceeded"
        # for an input that never had a verdict to give.
        delta = check_number(delta, "delta")
        net_benefit = round(delta - weighted_cost, 3)
        breakeven_exceeded = weighted_cost > delta

    return {
        "per_layer": per_layer,
        "t_recovery": round(t_recovery, 3),
        "weighted_cost": round(weighted_cost, 3),
        "delta": delta,
        "net_benefit": net_benefit,
        "breakeven_exceeded": breakeven_exceeded,
        "estimate": any(l["using_default_rate"] for l in per_layer.values()),
    }


def main() -> int:
    raw = json.load(sys.stdin)
    gaps = raw.get("gaps")
    # Distinguish a missing key (invalid) from an empty map (valid): Phase 4
    # always invokes this, and an empty `gaps` is legitimate when every
    # assessed layer carries epistemic credit (all gaps floored to 0) or the
    # caller omitted zero-valued layers. compute_recovery({}) returns zeros.
    if gaps is None:
        print("No 'gaps' in input.", file=sys.stderr)
        return 1
    result = compute_recovery(gaps, raw.get("rates"), raw.get("delta"))
    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

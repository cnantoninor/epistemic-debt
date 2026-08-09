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

from score import (  # co-located; cascade weights + shared input guards
    CASCADE,
    SCALE_MAX,
    check_mapping,
    check_number,
    run_cli,
)

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
    gaps = check_mapping(gaps, "'gaps'")
    # `is not None`, not truthiness: an empty *list* is falsy, and letting it
    # pass as "no rates given" would accept a wrong type in silence.
    rates = check_mapping(rates, "'rates'") if rates is not None else {}
    # Validate the rates keys before the loop. A typo'd key would otherwise
    # silently revert that layer to the policy default — defeating Phase 5,
    # whose whole purpose is substituting the team's measured rates — and a
    # rate for a layer with no gap entry would be silently ignored.
    unknown_rates = sorted(name for name in rates if name not in CASCADE)
    if unknown_rates:
        raise ValueError(
            f"Unknown layer(s) in 'rates' {unknown_rates}; expected {sorted(CASCADE)}."
        )
    unmatched_rates = sorted(name for name in rates if name not in gaps)
    if unmatched_rates:
        raise ValueError(
            f"Rate(s) given for layer(s) {unmatched_rates} that have no entry in 'gaps'; "
            f"a rate only applies to a layer whose gap is being recovered."
        )
    per_layer: dict[str, dict[str, object]] = {}
    raw_tau: dict[str, float] = {}
    t_recovery = 0.0
    weighted_cost = 0.0

    for name, gap in gaps.items():
        if name not in CASCADE:
            raise ValueError(f"Unknown layer {name!r}.")
        # A legitimate gap is C−G on the 0-5 scale, so SCALE_MAX bounds it:
        # a caller passing score.py's *weighted* field (which sits right next
        # to `gap` in its output) would otherwise inflate the estimate 10-30x.
        gap = check_number(gap, f"Gap for {name!r}", minimum=0, maximum=SCALE_MAX)
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
    # so the highest present layer's cumulative_cost always matches
    # t_recovery, instead of drifting from independently-rounded per-layer
    # values. ("Highest present", not "last": the output preserves input key
    # order, so the L1→L4-cumulative maximum can print first.)
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
        # Disambiguates "zero measured debt" from "nothing measured": with an
        # empty `gaps` every total is 0.0 and `estimate` is false (no default
        # rate was used because no layer was assessed) — a consumer needs this
        # count to report "nothing to recover" rather than a calibrated zero.
        "layers_assessed": len(per_layer),
    }


def _compute_cli(raw: dict) -> dict[str, object]:
    gaps = raw.get("gaps")
    # Distinguish a missing key (invalid) from an empty map (valid): Phase 4
    # always invokes this, and an empty `gaps` is legitimate when every
    # assessed layer carries epistemic credit (all gaps floored to 0) or the
    # caller omitted zero-valued layers. compute_recovery({}) returns zeros
    # with layers_assessed = 0.
    if gaps is None:
        raise ValueError("No 'gaps' in input.")
    return compute_recovery(gaps, raw.get("rates"), raw.get("delta"))


def main() -> int:
    return run_cli(_compute_cli)


if __name__ == "__main__":
    raise SystemExit(main())

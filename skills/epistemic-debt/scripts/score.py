#!/usr/bin/env python3
"""Cascade-weighted epistemic-debt scoring.

Deterministic companion to the epistemic-debt SKILL. Given a 0-5
complexity score (Cₛ) and 0-5 grasp score (Gₑ) per abstraction layer,
it computes each layer's gap, weights the gaps by their cascade cost
multiplier, and maps the total to a grade band.

Why a script: grading must be reproducible. Two runs with the same
inputs must yield the same grade, and the L1→L4 "discounting" must be
applied identically every time.

Usage (invoke by absolute path — see SKILL.md; do not rely on cwd):
    echo '{"L4_requirements":{"c":4,"g":2},
           "L3_architecture":{"c":3,"g":3},
           "L2_design":{"c":2,"g":3},
           "L1_implementation":{"c":4,"g":4}}' \
        | python3 "${CLAUDE_PLUGIN_ROOT}/skills/epistemic-debt/scripts/score.py"

Any layer may be omitted (e.g. PR mode often has no L4 signal); omitted
layers are simply excluded from the weighting.
"""
from __future__ import annotations

import json
import sys

# Cascade cost multipliers (rework triggered by a gap at this layer).
# Midpoints of the framework's ranges: L2 3-6×, L4 30-70×.
CASCADE = {
    "L1_implementation": 1,
    "L2_design": 4,
    "L3_architecture": 10,
    "L4_requirements": 50,
}

SCALE_MAX = 5  # complexity and grasp are each rated 0-5

# Grade bands on the 0-1 debt index (higher = worse). CALIBRATION KNOB:
# each entry is (upper_bound_exclusive, grade, label); >= last bound = F.
BANDS = [
    (0.10, "A", "Negligible / Credit"),
    (0.25, "B", "Low"),
    (0.45, "C", "Moderate"),
    (0.70, "D", "High"),
]

# How much a single layer's gap may *floor* the grade on its own, so a
# severe gap cannot be averaged away by clean lower layers. A value of 1.0
# means "this layer at gap=5 forces the index to 1.0 (F)". Keep values in
# [0, 1]; the index is clamped to 1.0 regardless. CALIBRATION KNOB.
#
# NB: epistemic debt is NOT technical debt. An L1 gap is a human who cannot
# explain code they did not write — the code may be flawless. L1 is the
# bottom layer, so a gap here has nothing beneath it to cascade into. It is
# set to 0.3 (not 0.0) on purpose: pervasive "nobody can explain this" code
# is the signature risk of AI-generated codebases and must register — but it
# stays below L2 (0.5) because it cannot cascade downward. Set it to 0.0 to
# treat implementation grasp as purely local (cascade-weighting only).
FLOOR_WEIGHT = {
    "L1_implementation": 0.3,
    "L2_design": 0.5,
    "L3_architecture": 0.75,
    "L4_requirements": 1.0,
}


def layer_gap(complexity: int, grasp: int) -> int:
    """Gap = how far complexity outruns grasp.

    Floored at 0: when grasp meets or exceeds complexity the layer holds
    epistemic *credit*, which does not add to debt.
    """
    return max(0, complexity - grasp)


def _band(index: float) -> tuple[str, str]:
    """Map a 0-1 debt index to a (grade, label) band."""
    for upper, grade, label in BANDS:
        if index < upper:
            return grade, label
    return "F", "Critical"


def compute_grade(layers: dict[str, dict[str, int]]) -> dict[str, object]:
    """Turn per-layer {complexity, grasp} into an overall graded verdict.

    Strategy E — normalized cascade-weighted sum with a scaled
    dominant-layer floor:

    1. Per layer, gap = max(0, C - G); weighted = cascade * gap.
    2. Base index = Σ weighted / Σ (cascade * SCALE_MAX) over the layers
       actually present, giving a 0-1 score comparable across whole-repo
       and PR scopes (which score different layer sets).
    3. Floor: each layer with a floor weight (all four — including L1, at
       the deliberate 0.3 documented on FLOOR_WEIGHT) can raise the index to
       at least FLOOR_WEIGHT[layer] * (gap / SCALE_MAX), so a severe
       high-layer gap can't be diluted to a good grade by clean lower layers.

    Also emits `debt_index_absolute` — the same numerator over the fixed
    four-layer maximum (un-floored) — for cross-scope / cross-repo
    ranking. The grade itself always uses the scope-relative `debt_index`.
    """
    per_layer: dict[str, dict[str, float]] = {}
    weighted_realized = 0.0
    weighted_possible = 0.0
    credit_layers: list[str] = []

    for name, scores in layers.items():
        complexity, grasp = scores["c"], scores["g"]
        cascade = CASCADE[name]
        gap = layer_gap(complexity, grasp)
        per_layer[name] = {"gap": gap, "weighted": cascade * gap}
        weighted_realized += cascade * gap
        weighted_possible += cascade * SCALE_MAX
        if grasp > complexity:  # surplus grasp = epistemic credit
            credit_layers.append(name)

    index = weighted_realized / weighted_possible if weighted_possible else 0.0

    floor = max(
        (FLOOR_WEIGHT[n] * per_layer[n]["gap"] / SCALE_MAX
         for n in per_layer if n in FLOOR_WEIGHT),
        default=0.0,
    )
    index = min(1.0, max(index, floor))  # bounded to [0, 1] whatever the knobs

    # Absolute index: same numerator, but the denominator is ALWAYS the full
    # four-layer maximum (not just the layers present), so magnitudes are
    # comparable across scopes and repos for ranking. Deliberately NOT
    # floored — the floor is a grading policy; ranking needs raw magnitude.
    absolute_index = weighted_realized / (sum(CASCADE.values()) * SCALE_MAX)

    dominant = max(per_layer, key=lambda n: per_layer[n]["weighted"], default=None)
    grade, label = _band(index)
    return {
        "per_layer": per_layer,
        "debt_index": round(index, 3),
        "debt_index_absolute": round(absolute_index, 3),
        "grade": grade,
        "band": label,
        "dominant_layer": dominant if weighted_realized > 0 else None,
        "credit_layers": credit_layers,
    }


def main() -> int:
    raw = json.load(sys.stdin)
    layers = {name: v for name, v in raw.items() if name in CASCADE}
    if not layers:
        print("No recognised layers in input.", file=sys.stderr)
        return 1
    result = compute_grade(layers)
    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

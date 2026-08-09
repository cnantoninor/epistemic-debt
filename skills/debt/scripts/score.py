#!/usr/bin/env python3
"""Cascade-weighted epistemic-debt scoring.

Deterministic companion to the Epistemic Debt SKILL. Given a 0-5
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
        | python3 "${CLAUDE_PLUGIN_ROOT}/skills/debt/scripts/score.py"

Any layer may be omitted (e.g. PR mode often has no L4 signal); omitted
layers are simply excluded from the weighting. Unrecognised top-level keys
are rejected: a misspelled layer name must fail loudly rather than
silently shrink the graded scope.
"""
from __future__ import annotations

import json
import math
import sys

# Cascade cost multipliers (rework triggered by a gap at this layer).
# Positioned within the framework's ranges (L2 3-6×, L4 30-70×). L4 sits at
# the low end of its range (30, not the 50 midpoint) on purpose: 50 made L4
# dominate `debt_index_absolute` — the cross-repo ranking magnitude — so
# heavily that lower-layer signal was drowned out. 30 keeps the top jump
# (L3→L4) at 3× rather than an outlier 5×. CALIBRATION KNOB.
#
# NB: CASCADE also feeds the *grade* — it normalizes the base debt_index
# (weighted_possible below), not just debt_index_absolute. Lowering L4 is
# mostly floor-bound (FLOOR_WEIGHT dominates when a high layer has a gap), so
# the grade is unchanged for the vast majority of inputs. The exception is the
# {L1, L2, L4}-present scope (PR mode with no L3 signal) with a small L4 gap
# beside larger lower-layer gaps: there the base index is binding, and
# shrinking L4's denominator weight nudges a handful of inputs from C to D.
# That marginal shift is accepted; it is not a pure ranking-only dial.
CASCADE = {
    "L1_implementation": 1,
    "L2_design": 4,
    "L3_architecture": 10,
    "L4_requirements": 30,
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


def check_number(
    value: object,
    description: str,
    *,
    minimum: float | None = None,
    maximum: float | None = None,
) -> float:
    """Reject anything JSON can supply that is not a real, finite, in-range
    number. Shared by all three scripts — a malformed input must fail loudly
    rather than produce a plausible-looking grade.

    `bool` is excluded explicitly because it subclasses `int`, so JSON `true`
    would otherwise sail through as a 1: a full-credit claim, a maximum
    confidence, or a gap of one whole scale point. Strings are excluded
    because `math.isfinite` raises `TypeError` on them rather than producing
    a legible validation error.

    Returns the value unchanged (not coerced to `float`) so integer inputs
    stay integers in the JSON output.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{description} must be a finite number; got {value!r}.")
    if (minimum is not None and value < minimum) or (maximum is not None and value > maximum):
        if minimum is not None and maximum is not None:
            bound = f"from {minimum} to {maximum}"
        elif minimum is not None:
            bound = f">= {minimum}"
        else:
            bound = f"<= {maximum}"
        raise ValueError(f"{description} must be a finite number {bound}; got {value!r}.")
    return value


def check_mapping(value: object, description: str) -> dict:
    """Reject a JSON value that has to be an object but isn't.

    Without this, a list or a bare string reaches `.items()` or `[...]` and
    surfaces as an `AttributeError`/`TypeError` from somewhere deep in the
    arithmetic — a stack trace about the internals instead of a sentence
    about the input.
    """
    if not isinstance(value, dict):
        raise ValueError(f"{description} must be a JSON object; got {value!r}.")
    return value


def load_object(stream: object, description: str = "Input") -> dict:
    """Read a JSON object from `stream`, or raise `ValueError` explaining why
    it isn't one. Shared by all three CLIs so malformed stdin fails the same
    legible way everywhere."""
    try:
        raw = json.loads(stream.read())  # type: ignore[attr-defined]
    except json.JSONDecodeError as exc:
        raise ValueError(f"{description} is not valid JSON: {exc}.") from None
    return check_mapping(raw, description)


def check_layer_names(raw: dict) -> dict:
    """Reject any top-level key that is not a canonical CASCADE layer name.

    Shared by `score.py` and `grasp.py` (recovery.py applies the same
    strictness to its 'gaps' and 'rates' keys). The alternative — silently
    filtering to the recognised keys — turned a one-character typo into a
    wrong grade at exit 0: `debt_index` is scope-relative, so dropping a
    misspelled "L4_requirement" recomputed a clean-looking grade over the
    surviving layers (an F became an A, nothing on stderr).
    """
    unknown = sorted(name for name in raw if name not in CASCADE)
    if unknown:
        raise ValueError(f"Unknown layer(s) {unknown}; expected {sorted(CASCADE)}.")
    return raw


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
        scores = check_mapping(scores, f"Layer {name!r}")
        missing = {"c", "g"} - scores.keys()
        if missing:
            raise ValueError(f"Layer {name!r} is missing {sorted(missing)}; got {scores!r}.")
        complexity = check_number(scores["c"], f"Complexity for {name!r}", minimum=0, maximum=SCALE_MAX)
        grasp = check_number(scores["g"], f"Grasp for {name!r}", minimum=0, maximum=SCALE_MAX)
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

    # Deterministic tie-break: on an exact weighted tie the *higher* layer
    # wins (larger CASCADE multiplier) — consistent with LAYER_ORDER in
    # recovery.py and with the cascade semantics (the higher layer is where
    # remediation should start). Without it, max() fell back to insertion
    # order, so a semantically irrelevant permutation of the JSON keys
    # flipped the reported dominant_layer (the grade was never affected).
    dominant = max(per_layer, key=lambda n: (per_layer[n]["weighted"], CASCADE[n]), default=None)
    # Same determinism for credit_layers: descending cascade order (L4→L1),
    # not input key order.
    credit_layers.sort(key=lambda n: CASCADE[n], reverse=True)
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


def run_cli(compute) -> int:
    """Shared CLI shell for the three scripts (`grasp.py` and `recovery.py`
    import it): read one JSON object from stdin, hand it to `compute`, print
    the result as indented JSON. Every failure path is a `ValueError` →
    exit 1 with a single legible line on stderr, never a traceback — the
    skill reads that stderr, and a stack trace buries the sentence saying
    what was wrong with the input.
    """
    try:
        result = compute(load_object(sys.stdin))
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 1
    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


def _compute_cli(raw: dict) -> dict[str, object]:
    layers = check_layer_names(raw)
    if not layers:
        raise ValueError("No recognised layers in input.")
    return compute_grade(layers)


def main() -> int:
    return run_cli(_compute_cli)


if __name__ == "__main__":
    raise SystemExit(main())

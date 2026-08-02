#!/usr/bin/env python3
"""Deterministic Gₑ aggregation from per-claim comprehension probe scores.

Companion to `score.py`: where `score.py` turns 0-5 (complexity, grasp)
pairs into a cascade-weighted grade, this script turns the raw per-claim
correctness/confidence captured during Phase 2 probing into the 0-5 Gₑ
and the calibration gap that feed it — so the aggregation arithmetic is
reproducible instead of re-derived in prose on every run.

Per layer, each probed question yields one "answer": one respondent-stated
confidence (0-1, or a label — see CONFIDENCE_LABELS) plus a list of
per-claim correctness scores (0-1; multiple-choice supplies a single-item
list). See `references/comprehension-probes.md` for the full protocol.

Usage (invoke by absolute path — see SKILL.md; do not rely on cwd):
    echo '{"L1_implementation": [
             {"confidence": 0.7, "claims": [1.0, 0.5]},
             {"confidence": "somewhat", "claims": [0.0]}
           ],
           "L2_design": [
             {"confidence": 0.4, "claims": [1.0]}
           ]}' \
        | python3 "${CLAUDE_PLUGIN_ROOT}/skills/epistemic-debt/scripts/grasp.py"

Any layer may be omitted; only layers actually probed need appear. Unknown
top-level keys are ignored (mirrors `score.py`). Feed the resulting `g`
(and `c`, from Phase 1) into `score.py` for the grade.
"""
from __future__ import annotations

import json
import sys

from score import (  # co-located; canonical names + shared input guards
    CASCADE,
    check_number,
    load_object,
)

# Confidence label → number, for respondents who answer in words rather
# than a 0-1 figure. Matches the mapping in comprehension-probes.md.
CONFIDENCE_LABELS = {
    "guessing": 0.1,
    "somewhat": 0.4,
    "confident": 0.7,
    "certain": 0.95,
}

SCALE_MAX = 5  # Gₑ is reported 0-5, same scale as Cₛ in score.py

# Calibration gap thresholds (confidence - correctness). CALIBRATION KNOB —
# keep in sync with the "≳ +0.3 / ≈ 0 / ≲ -0.3" language in
# comprehension-probes.md if ever tuned.
OVERCONFIDENT_THRESHOLD = 0.3
UNDERCONFIDENT_THRESHOLD = -0.3


def _score_value(value: object, description: str) -> float:
    """Resolve a 0-1 score input to a float, tolerating a quoted number.

    Hand- or LLM-authored JSON quotes numbers often enough to be worth
    accepting ("0.5"), but everything else goes through `check_number`, which
    rejects JSON booleans — `true` is never a score, yet `bool` subclasses
    `int`, so it would otherwise land as full credit or maximum confidence.
    """
    if isinstance(value, str):
        try:
            value = float(value.strip())
        except ValueError:
            raise ValueError(
                f"{description} must be a number from 0 to 1; got {value!r}."
            ) from None
    return check_number(value, description, minimum=0, maximum=1)


def _confidence_value(confidence: float | str) -> float:
    """Resolve a confidence input to a 0-1 float, accepting labels or a
    numeric string (JSON authored by hand or by an LLM may quote either)."""
    if isinstance(confidence, str):
        label = confidence.strip().lower()
        if label in CONFIDENCE_LABELS:
            return CONFIDENCE_LABELS[label]
        if not _looks_numeric(label):
            raise ValueError(
                f"Unknown confidence label {confidence!r}; "
                f"expected one of {sorted(CONFIDENCE_LABELS)} or a 0-1 number."
            )
    return _score_value(confidence, "Confidence")


def _looks_numeric(text: str) -> bool:
    try:
        float(text)
    except ValueError:
        return False
    return True


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _calibration_flag(gap: float) -> str:
    if gap >= OVERCONFIDENT_THRESHOLD:
        return "overconfident"
    if gap <= UNDERCONFIDENT_THRESHOLD:
        return "underconfident"
    return "calibrated"


def score_answer(answer: dict[str, object]) -> dict[str, float]:
    """One answer's aggregate: confidence (per-answer) and correctness
    (mean over its claims — an articulated answer may assert several
    distinct, separately-graded claims)."""
    if not isinstance(answer, dict):
        raise ValueError(
            f"Each answer must be an object with 'confidence' and 'claims'; got {answer!r}."
        )
    missing = {"confidence", "claims"} - answer.keys()
    if missing:
        raise ValueError(f"Answer is missing {sorted(missing)}; got {answer!r}.")
    if not isinstance(answer["claims"], list):
        raise ValueError(f"Answer 'claims' must be a list of 0-1 scores; got {answer['claims']!r}.")
    if not answer["claims"]:
        raise ValueError("Answer has no claims to grade.")
    claims = [
        float(_score_value(c, "Claim score")) for c in answer["claims"]  # type: ignore[union-attr]
    ]
    return {
        "confidence": _confidence_value(answer["confidence"]),  # type: ignore[arg-type]
        "correctness": _mean(claims),
        "claims": claims,
    }


def score_layer(answers: list[dict[str, object]]) -> dict[str, object]:
    """Aggregate a layer's answers into Gₑ and the calibration gap."""
    # A layer's payload is a *list* of answers. A single answer passed as a
    # bare object (or a stray string) would otherwise be iterated element-wise
    # — over dict keys or characters — and fail deep inside score_answer.
    if not isinstance(answers, list):
        raise ValueError(f"Layer must be a list of answer objects; got {answers!r}.")
    if not answers:
        raise ValueError("Layer has no answers to grade.")
    scored = [score_answer(a) for a in answers]
    correctness = _mean([a["correctness"] for a in scored])
    confidence = _mean([a["confidence"] for a in scored])
    gap = round(confidence - correctness, 3)
    return {
        "g": round(correctness * SCALE_MAX),
        "correctness": round(correctness, 3),
        "confidence": round(confidence, 3),
        "gap": gap,
        "flag": _calibration_flag(gap),
        "answers": [
            {
                "confidence": round(a["confidence"], 3),
                "correctness": round(a["correctness"], 3),
                "claims": a["claims"],
            }
            for a in scored
        ],
    }


def main() -> int:
    try:
        raw = load_object(sys.stdin)
        layers = {name: v for name, v in raw.items() if name in CASCADE}
        if not layers:
            print("No layers in input.", file=sys.stderr)
            return 1
        result = {name: score_layer(answers) for name, answers in layers.items()}
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 1
    json.dump(result, sys.stdout, indent=2)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

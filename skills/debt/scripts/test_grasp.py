#!/usr/bin/env python3
"""Unit tests for grasp.py — run with:
    python3 skills/debt/scripts/test_grasp.py
or:
    python3 -m unittest discover -s skills/debt/scripts -p "test_*.py"
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from cli_harness import CliHarness
from grasp import (
    _calibration_flag,
    _confidence_value,
    score_answer,
    score_layer,
)

SCRIPT = Path(__file__).resolve().parent / "grasp.py"


class ConfidenceValueTests(unittest.TestCase):
    def test_accepts_raw_number(self):
        self.assertEqual(_confidence_value(0.7), 0.7)

    def test_accepts_label_case_and_whitespace_insensitive(self):
        self.assertEqual(_confidence_value(" Certain "), 0.95)
        self.assertEqual(_confidence_value("guessing"), 0.1)
        self.assertEqual(_confidence_value("SOMEWHAT"), 0.4)
        self.assertEqual(_confidence_value("Confident"), 0.7)

    def test_accepts_numeric_string(self):
        # JSON authored by hand (or by an LLM) may quote a number; the error
        # message promises "a 0-1 number" is acceptable as a string, so this
        # must not raise.
        self.assertEqual(_confidence_value("0.7"), 0.7)

    def test_rejects_unknown_label(self):
        with self.assertRaises(ValueError):
            _confidence_value("pretty sure")

    def test_rejects_confidence_outside_zero_to_one(self):
        for confidence in (-0.1, 1.1, "-0.1", "1.1"):
            with self.subTest(confidence=confidence), self.assertRaises(ValueError):
                _confidence_value(confidence)

    def test_rejects_non_finite_confidence(self):
        for confidence in (float("nan"), float("inf"), "-inf"):
            with self.subTest(confidence=confidence), self.assertRaises(ValueError):
                _confidence_value(confidence)

    def test_rejects_boolean_confidence(self):
        # `bool` subclasses `int`, so JSON `true` would otherwise be read as a
        # confidence of 1.0 — the maximum — and silently skew the calibration
        # gap instead of failing like a malformed input should.
        for confidence in (True, False):
            with self.subTest(confidence=confidence), self.assertRaises(ValueError):
                _confidence_value(confidence)


class CalibrationFlagTests(unittest.TestCase):
    # Hand-checked against the ±0.3 thresholds in comprehension-probes.md.
    def test_overconfident_at_and_above_threshold(self):
        self.assertEqual(_calibration_flag(0.3), "overconfident")
        self.assertEqual(_calibration_flag(0.9), "overconfident")

    def test_underconfident_at_and_below_threshold(self):
        self.assertEqual(_calibration_flag(-0.3), "underconfident")
        self.assertEqual(_calibration_flag(-0.9), "underconfident")

    def test_calibrated_strictly_between(self):
        self.assertEqual(_calibration_flag(0.0), "calibrated")
        self.assertEqual(_calibration_flag(0.29), "calibrated")
        self.assertEqual(_calibration_flag(-0.29), "calibrated")


class ScoreAnswerTests(unittest.TestCase):
    def test_single_claim(self):
        result = score_answer({"confidence": 0.6, "claims": [1.0]})
        self.assertEqual(result["correctness"], 1.0)
        self.assertEqual(result["confidence"], 0.6)

    def test_correctness_is_mean_of_claims(self):
        result = score_answer({"confidence": 0.5, "claims": [1.0, 0.5, 0.0]})
        self.assertAlmostEqual(result["correctness"], 0.5)

    def test_empty_claims_rejected(self):
        with self.assertRaises(ValueError):
            score_answer({"confidence": 0.5, "claims": []})

    def test_claim_scores_must_be_finite_and_between_zero_and_one(self):
        for claim in (-0.1, 1.1, float("nan"), float("inf")):
            with self.subTest(claim=claim), self.assertRaises(ValueError):
                score_answer({"confidence": 0.5, "claims": [claim]})

    def test_boolean_claims_rejected(self):
        # A tempting shorthand for multiple-choice (right/wrong), but `bool`
        # subclasses `int`: `true` would be scored as full credit and `false`
        # as zero, quietly turning a mistyped payload into a plausible Gₑ.
        for claim in (True, False):
            with self.subTest(claim=claim), self.assertRaises(ValueError):
                score_answer({"confidence": 0.5, "claims": [claim]})

    def test_quoted_claim_scores_accepted(self):
        # Same tolerance as confidence: hand- or LLM-authored JSON quotes
        # numbers often enough that "0.5" must keep working.
        self.assertAlmostEqual(
            score_answer({"confidence": 0.5, "claims": ["0.5", "1"]})["correctness"], 0.75
        )


class ScoreLayerTests(unittest.TestCase):
    def test_aggregation_is_mean_of_per_answer_means_not_flat_claim_mean(self):
        # Hand-checked: this is the case that would previously have been
        # described as "equivalently, the mean over every claim" — which is
        # only true when every answer has the same claim count. Here answer A
        # has 2 claims (mean 0.75) and answer B has 4 claims (mean 0.0):
        #   mean-of-answer-means = mean(0.75, 0.0) = 0.375  <- what this
        #     function must return (answers, not claims, are the unit).
        #   flat mean over all 6 claims = (1+0.5+0+0+0+0)/6 = 0.25 <- the
        #     wrong number the old prose equivalence claim would give.
        answers = [
            {"confidence": 0.7, "claims": [1.0, 0.5]},
            {"confidence": 0.4, "claims": [0.0, 0.0, 0.0, 0.0]},
        ]
        result = score_layer(answers)
        self.assertAlmostEqual(result["correctness"], 0.375)
        self.assertNotAlmostEqual(result["correctness"], 0.25)
        # g = round(correctness * 5) = round(1.875) = 2
        self.assertEqual(result["g"], 2)

    def test_confidence_is_mean_of_answer_confidences(self):
        answers = [
            {"confidence": 0.8, "claims": [1.0]},
            {"confidence": 0.2, "claims": [1.0]},
        ]
        result = score_layer(answers)
        self.assertAlmostEqual(result["confidence"], 0.5)
        self.assertAlmostEqual(result["correctness"], 1.0)
        # calibration_gap = confidence - correctness = 0.5 - 1.0 = -0.5.
        self.assertAlmostEqual(result["calibration_gap"], -0.5)
        self.assertEqual(result["flag"], "underconfident")
        # The key is calibration_gap, NOT `gap`: recovery.py consumes a map
        # named `gaps` on a different scale (C-G, 0-5 points), and the old
        # shared name let one be fed as the other in silence.
        self.assertNotIn("gap", result)

    def test_g_rounding_is_bankers_rounding_at_the_half(self):
        # correctness = 0.5 -> 0.5*5 = 2.5 -> Python's round() is
        # round-half-to-even, so this rounds DOWN to 2, not up to 3.
        answers = [{"confidence": 0.5, "claims": [0.5]}]
        result = score_layer(answers)
        self.assertEqual(result["correctness"], 0.5)
        self.assertEqual(result["g"], 2)

    def test_overconfident_flag_end_to_end(self):
        answers = [{"confidence": 0.9, "claims": [0.6]}]
        result = score_layer(answers)
        # calibration_gap = 0.9 - 0.6 = 0.3 (exactly at the overconfident
        # threshold)
        self.assertAlmostEqual(result["calibration_gap"], 0.3)
        self.assertEqual(result["flag"], "overconfident")

    def test_common_labels_classify_at_displayed_threshold(self):
        result = score_layer([{"confidence": 0.7, "claims": [0.4]}])
        # calibration_gap = 0.7 - 0.4 = 0.3 -> overconfident.
        self.assertEqual(result["calibration_gap"], 0.3)
        self.assertEqual(result["flag"], "overconfident")

    def test_empty_answers_rejected(self):
        with self.assertRaises(ValueError):
            score_layer([])

    def test_non_list_layer_payload_rejected(self):
        # A single answer sent as a bare object, or a stray scalar, was
        # iterated element-wise (dict keys / string characters) and died
        # with a TypeError deep inside score_answer instead of a clear
        # validation error naming the real problem.
        for payload in ({"confidence": 0.7, "claims": [1.0]}, "oops", 3, None):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                score_layer(payload)

    def test_malformed_answer_rejected(self):
        for answer in ("oops", 3, None, {"claims": [1.0]}, {"confidence": 0.7},
                       {"confidence": 0.7, "claims": 1.0}):
            with self.subTest(answer=answer), self.assertRaises(ValueError):
                score_answer(answer)


class CliTests(CliHarness, unittest.TestCase):
    SCRIPT = SCRIPT

    def test_cli_multi_layer(self):
        proc = self._run(json.dumps({
            "L1_implementation": [{"confidence": 0.7, "claims": [1.0, 0.5]}],
            "L2_design": [{"confidence": 0.4, "claims": [1.0]}],
        }))
        self.assertEqual(proc.returncode, 0)
        payload = json.loads(proc.stdout)
        self.assertEqual(payload["L1_implementation"]["g"], 4)
        self.assertEqual(payload["L2_design"]["g"], 5)

    def test_cli_rejects_empty_input(self):
        proc = self._run("{}")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("No layers", proc.stderr)

    def test_cli_rejects_unknown_keys_alongside_recognised_layers(self):
        # Inverse of the old tolerance: main() used to filter to recognised
        # layer names, so a misspelled layer's probe results were silently
        # dropped from the Gₑ it fed to score.py. Any unrecognised top-level
        # key must now be a hard error (same shared check as score.py),
        # naming the unknown keys and the expected set.
        proc = self._run(json.dumps({
            "L1_implementation": [{"confidence": 0.7, "claims": [1.0]}],
            "notes": "ignore me",
        }))
        self.assertEqual(proc.returncode, 1)
        self.assertIn("Unknown layer(s) ['notes']", proc.stderr)
        self.assertIn(
            "expected ['L1_implementation', 'L2_design', 'L3_architecture', 'L4_requirements']",
            proc.stderr,
        )

    def test_cli_reports_malformed_stdin_without_a_stack_trace(self):
        # Same contract as score.py: exit 1 and one legible line on stderr,
        # never a traceback about .items() or float() (shared contract
        # assertion in cli_harness.py).
        self.assert_malformed_stdin_contract((
            "[1, 2, 3]", "not json",
            '{"L1_implementation": {"confidence": 0.5, "claims": [1]}}',
            '{"L1_implementation": [{"confidence": true, "claims": [1]}]}',
            '{"L1_implementation": [{"claims": [1]}]}',
        ))


if __name__ == "__main__":
    unittest.main()

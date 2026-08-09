#!/usr/bin/env python3
"""Unit tests for score.py — run with:
    python3 skills/debt/scripts/test_score.py
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
from score import (
    SCALE_MAX,
    _band,
    check_mapping,
    check_number,
    compute_grade,
    layer_gap,
)

SCRIPT = Path(__file__).resolve().parent / "score.py"


class LayerGapTests(unittest.TestCase):
    def test_positive_gap(self):
        self.assertEqual(layer_gap(4, 2), 2)

    def test_gap_floored_at_zero_when_grasp_meets_complexity(self):
        self.assertEqual(layer_gap(3, 3), 0)

    def test_gap_floored_at_zero_when_grasp_exceeds_complexity(self):
        self.assertEqual(layer_gap(2, 4), 0)


class CheckNumberTests(unittest.TestCase):
    """The shared input guard grasp.py and recovery.py both import."""

    def test_accepts_numbers_and_preserves_int(self):
        self.assertEqual(check_number(3, "x"), 3)
        self.assertIsInstance(check_number(3, "x"), int)
        self.assertEqual(check_number(0.5, "x"), 0.5)

    def test_rejects_booleans(self):
        # The whole reason this helper exists: bool subclasses int, so a JSON
        # `true` would otherwise pass every numeric check as a 1.
        for value in (True, False):
            with self.subTest(value=value), self.assertRaises(ValueError):
                check_number(value, "x")

    def test_rejects_non_numbers_and_non_finite(self):
        for value in ("4", None, [], {}, float("nan"), float("inf")):
            with self.subTest(value=value), self.assertRaises(ValueError):
                check_number(value, "x")

    def test_bounds_are_inclusive(self):
        self.assertEqual(check_number(0, "x", minimum=0, maximum=5), 0)
        self.assertEqual(check_number(5, "x", minimum=0, maximum=5), 5)
        for value in (-0.1, 5.1):
            with self.subTest(value=value), self.assertRaises(ValueError):
                check_number(value, "x", minimum=0, maximum=5)


class CheckMappingTests(unittest.TestCase):
    def test_accepts_dict(self):
        self.assertEqual(check_mapping({"c": 1}, "x"), {"c": 1})

    def test_rejects_non_objects(self):
        for value in ([1, 2], "text", 3, None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                check_mapping(value, "x")


class ComputeGradeInputTests(unittest.TestCase):
    def test_rejects_layer_payload_that_is_not_an_object(self):
        with self.assertRaises(ValueError):
            compute_grade({"L1_implementation": [1, 2]})

    def test_rejects_layer_missing_c_or_g(self):
        for layer in ({"c": 3}, {"g": 3}, {}):
            with self.subTest(layer=layer), self.assertRaises(ValueError):
                compute_grade({"L1_implementation": layer})

    def test_rejects_boolean_scores(self):
        for layer in ({"c": True, "g": 0}, {"c": 4, "g": False}):
            with self.subTest(layer=layer), self.assertRaises(ValueError):
                compute_grade({"L1_implementation": layer})

    def test_rejects_scores_outside_the_zero_to_five_scale(self):
        # Out-of-scale scores silently distort both indices — a c of 7 gives a
        # gap of 7 against a denominator built from SCALE_MAX.
        for layer in ({"c": SCALE_MAX + 1, "g": 0}, {"c": 4, "g": -1}):
            with self.subTest(layer=layer), self.assertRaises(ValueError):
                compute_grade({"L1_implementation": layer})


class BandTests(unittest.TestCase):
    # Hand-checked against BANDS = [(0.10,A),(0.25,B),(0.45,C),(0.70,D)],
    # >= 0.70 -> F. Each bound is exclusive of its own tier (upper bound
    # belongs to the next tier up).
    def test_a_band(self):
        self.assertEqual(_band(0.0), ("A", "Negligible / Credit"))
        self.assertEqual(_band(0.099), ("A", "Negligible / Credit"))

    def test_b_band_starts_at_lower_bound(self):
        self.assertEqual(_band(0.10), ("B", "Low"))
        self.assertEqual(_band(0.24), ("B", "Low"))

    def test_c_band_starts_at_lower_bound(self):
        self.assertEqual(_band(0.25), ("C", "Moderate"))
        self.assertEqual(_band(0.44), ("C", "Moderate"))

    def test_d_band_starts_at_lower_bound(self):
        self.assertEqual(_band(0.45), ("D", "High"))
        self.assertEqual(_band(0.69), ("D", "High"))

    def test_f_band_at_and_above_070(self):
        self.assertEqual(_band(0.70), ("F", "Critical"))
        self.assertEqual(_band(1.0), ("F", "Critical"))


class ComputeGradeTests(unittest.TestCase):
    def test_claude_md_smoke_example(self):
        # Hand-checked: weighted_realized = 30*2 (L4 gap=2) = 60.
        # weighted_possible = (1+4+10+30)*5 = 225. base index = 60/225 = 0.2667.
        # floor = max(L4: 1.0*2/5=0.4, L3: 0, L2: 0, L1: 0) = 0.4 > base index,
        # so debt_index = 0.4 -> band C ("Moderate"), since 0.4 < 0.45.
        # debt_index_absolute = 60 / (45*5) = 0.2667 -> 0.267 (never floored).
        layers = {
            "L4_requirements": {"c": 4, "g": 2},
            "L3_architecture": {"c": 3, "g": 3},
            "L2_design": {"c": 2, "g": 3},
            "L1_implementation": {"c": 4, "g": 4},
        }
        result = compute_grade(layers)
        self.assertEqual(result["debt_index"], 0.4)
        self.assertEqual(result["debt_index_absolute"], 0.267)
        self.assertEqual(result["grade"], "C")
        self.assertEqual(result["band"], "Moderate")
        self.assertEqual(result["dominant_layer"], "L4_requirements")
        self.assertEqual(result["credit_layers"], ["L2_design"])

    def test_pr_mode_subset_of_layers_uses_scope_relative_denominator(self):
        # Only L1 and L2 present (PR mode, no architecture/requirements
        # signal). gap L1 = 5, weighted = 1*5 = 5. gap L2 = 0.
        # weighted_possible (present layers only) = (1+4)*5 = 25.
        # base index = 5/25 = 0.2. floor = max(L1: 0.3*5/5=0.3, L2: 0) = 0.3.
        # debt_index = max(0.2, 0.3) = 0.3 -> band C (0.3 < 0.45).
        # debt_index_absolute uses the FIXED four-layer denominator (45*5=225)
        # regardless of scope: 5/225 = 0.0222 -> 0.022.
        layers = {
            "L1_implementation": {"c": 5, "g": 0},
            "L2_design": {"c": 0, "g": 0},
        }
        result = compute_grade(layers)
        self.assertEqual(result["debt_index"], 0.3)
        self.assertEqual(result["debt_index_absolute"], 0.022)
        self.assertEqual(result["grade"], "C")
        self.assertEqual(result["dominant_layer"], "L1_implementation")
        self.assertEqual(result["credit_layers"], [])

    def test_clean_repo_is_all_credit_and_dominant_is_none(self):
        # grasp exceeds complexity everywhere -> every gap is 0, every
        # layer is credit, weighted_realized == 0 so dominant_layer must be
        # None (not an arbitrary max() pick among all-zero weights).
        # Layers deliberately fed in L1-first order: credit_layers must come
        # back in DESCENDING cascade order (L4=30, L3=10, L2=4, L1=1), not
        # input key order.
        layers = {name: {"c": 2, "g": 4} for name in
                  ("L1_implementation", "L2_design", "L3_architecture", "L4_requirements")}
        result = compute_grade(layers)
        self.assertEqual(result["debt_index"], 0.0)
        self.assertEqual(result["grade"], "A")
        self.assertIsNone(result["dominant_layer"])
        self.assertEqual(
            result["credit_layers"],
            ["L4_requirements", "L3_architecture", "L2_design", "L1_implementation"],
        )

    def test_dominant_layer_tie_breaks_to_higher_layer_in_both_key_orders(self):
        # Exact weighted tie, hand-computed:
        #   L1: gap = 4 - 0 = 4, weighted = 1 * 4 = 4
        #   L2: gap = 1 - 0 = 1, weighted = 4 * 1 = 4
        # The tie-break is (weighted, CASCADE[name]) so the higher layer wins:
        # CASCADE L2_design = 4 > L1_implementation = 1 -> L2_design must be
        # dominant regardless of which key the JSON happens to put first
        # (previously max() fell back to insertion order and the reported
        # field flipped under a semantically irrelevant permutation).
        for layers in (
            {"L1_implementation": {"c": 4, "g": 0}, "L2_design": {"c": 1, "g": 0}},
            {"L2_design": {"c": 1, "g": 0}, "L1_implementation": {"c": 4, "g": 0}},
        ):
            with self.subTest(order=list(layers)):
                result = compute_grade(layers)
                self.assertEqual(result["dominant_layer"], "L2_design")

    def test_single_maxed_out_layer_floors_to_critical(self):
        # L4 alone at gap=5 (worst case): weighted_realized = weighted_possible
        # = 30*5 = 150 -> base index 1.0; floor = 1.0*5/5 = 1.0. debt_index
        # clamped to 1.0 -> band F. debt_index_absolute = 150/225 = 0.667.
        layers = {"L4_requirements": {"c": 5, "g": 0}}
        result = compute_grade(layers)
        self.assertEqual(result["debt_index"], 1.0)
        self.assertEqual(result["debt_index_absolute"], 0.667)
        self.assertEqual(result["grade"], "F")

    def test_empty_layers_does_not_crash(self):
        result = compute_grade({})
        self.assertEqual(result["debt_index"], 0.0)
        self.assertEqual(result["debt_index_absolute"], 0.0)
        self.assertIsNone(result["dominant_layer"])
        self.assertEqual(result["credit_layers"], [])


class CliTests(CliHarness, unittest.TestCase):
    SCRIPT = SCRIPT

    def test_cli_smoke_matches_direct_call(self):
        proc = self._run(
            '{"L4_requirements":{"c":4,"g":2},"L3_architecture":{"c":3,"g":3},'
            '"L2_design":{"c":2,"g":3},"L1_implementation":{"c":4,"g":4}}'
        )
        self.assertEqual(proc.returncode, 0)
        payload = json.loads(proc.stdout)
        self.assertEqual(payload["grade"], "C")

    def test_cli_rejects_unrecognised_layers(self):
        proc = self._run('{"not_a_layer": {"c": 1, "g": 1}}')
        self.assertEqual(proc.returncode, 1)
        self.assertIn("Unknown layer(s) ['not_a_layer']", proc.stderr)

    def test_cli_rejects_empty_object_with_distinct_message(self):
        # {} has no unknown keys, so it must not hit the unknown-layer error;
        # it gets its own legible "nothing to grade" message.
        proc = self._run("{}")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("No recognised layers", proc.stderr)

    def test_cli_rejects_unknown_keys_alongside_recognised_layers(self):
        # Inverse of the old tolerance (which silently filtered to CASCADE
        # keys): a misspelled layer would be dropped and the scope-relative
        # debt_index recomputed over the survivors, turning an F into an A at
        # exit 0. Any unrecognised top-level key must now fail loudly, naming
        # the unknown keys and the expected set.
        proc = self._run(
            '{"L1_implementation": {"c": 1, "g": 1}, "notes": "ignore me"}'
        )
        self.assertEqual(proc.returncode, 1)
        self.assertIn("Unknown layer(s) ['notes']", proc.stderr)
        self.assertIn(
            "expected ['L1_implementation', 'L2_design', 'L3_architecture', 'L4_requirements']",
            proc.stderr,
        )

    def test_cli_rejects_misspelled_layer_name(self):
        # The exact one-character typo from the review's F->A reproduction:
        # "L4_requirement" (missing the final s) must be an error, never a
        # silently shrunken scope.
        proc = self._run(
            '{"L4_requirement": {"c": 5, "g": 0}, "L1_implementation": {"c": 1, "g": 1}}'
        )
        self.assertEqual(proc.returncode, 1)
        self.assertIn("Unknown layer(s) ['L4_requirement']", proc.stderr)

    def test_cli_reports_malformed_stdin_without_a_stack_trace(self):
        # Every failure mode is exit 1 plus one legible line on stderr: the
        # skill reads that stderr, and a traceback buries the sentence that
        # says what was wrong with the input (shared contract assertion in
        # cli_harness.py).
        self.assert_malformed_stdin_contract((
            "[1, 2, 3]", "not json", '{"L1_implementation": [1, 2]}',
            '{"L1_implementation": {"c": 3}}',
            '{"L1_implementation": {"c": true, "g": 1}}',
        ))


if __name__ == "__main__":
    unittest.main()

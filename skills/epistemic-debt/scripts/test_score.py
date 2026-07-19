#!/usr/bin/env python3
"""Unit tests for score.py — run with:
    python3 skills/epistemic-debt/scripts/test_score.py
or:
    python3 -m unittest discover -s skills/epistemic-debt/scripts -p "test_*.py"
"""
from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from score import _band, compute_grade, layer_gap  # noqa: E402

SCRIPT = Path(__file__).resolve().parent / "score.py"


class LayerGapTests(unittest.TestCase):
    def test_positive_gap(self):
        self.assertEqual(layer_gap(4, 2), 2)

    def test_gap_floored_at_zero_when_grasp_meets_complexity(self):
        self.assertEqual(layer_gap(3, 3), 0)

    def test_gap_floored_at_zero_when_grasp_exceeds_complexity(self):
        self.assertEqual(layer_gap(2, 4), 0)


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
        layers = {name: {"c": 2, "g": 4} for name in
                  ("L4_requirements", "L3_architecture", "L2_design", "L1_implementation")}
        result = compute_grade(layers)
        self.assertEqual(result["debt_index"], 0.0)
        self.assertEqual(result["grade"], "A")
        self.assertIsNone(result["dominant_layer"])
        self.assertEqual(
            set(result["credit_layers"]),
            {"L4_requirements", "L3_architecture", "L2_design", "L1_implementation"},
        )

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


class CliTests(unittest.TestCase):
    def _run(self, stdin_text: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(SCRIPT)],
            input=stdin_text,
            capture_output=True,
            text=True,
        )

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
        self.assertIn("No recognised layers", proc.stderr)

    def test_cli_ignores_unknown_keys_alongside_recognised_layers(self):
        # main() filters raw input to keys in CASCADE, so extra/unknown
        # keys are silently dropped rather than erroring.
        proc = self._run(
            '{"L1_implementation": {"c": 1, "g": 1}, "notes": "ignore me"}'
        )
        self.assertEqual(proc.returncode, 0)
        payload = json.loads(proc.stdout)
        self.assertIn("L1_implementation", payload["per_layer"])
        self.assertNotIn("notes", payload["per_layer"])


if __name__ == "__main__":
    unittest.main()

#!/usr/bin/env python3
"""Unit tests for recovery.py — run with:
    python3 skills/epistemic-debt/scripts/test_recovery.py
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

from recovery import compute_recovery  # noqa: E402

SCRIPT = Path(__file__).resolve().parent / "recovery.py"


class ComputeRecoveryTests(unittest.TestCase):
    def test_default_rates_all_four_layers(self):
        # Hand-checked against DEFAULT_RATES (L1=2.0, L2=1.0, L3=0.5,
        # L4=0.33):
        #   tau_L4 = 2 / 0.33   = 6.060606... -> 6.061
        #   tau_L3 = 1 / 0.5    = 2.0
        #   tau_L2 = 0 / 1.0    = 0.0
        #   tau_L1 = 3 / 2.0    = 1.5
        #   T_recovery = 6.060606... + 2 + 0 + 1.5 = 9.560606... -> 9.561
        #   weighted_cost = 30*6.060606.. + 10*2 + 4*0 + 1*1.5
        #                 = 181.81818... + 20 + 0 + 1.5 = 203.31818... -> 203.318
        #   cumulative_cost in L1->L4 order: L1=1.5, L2=1.5+0=1.5,
        #     L3=1.5+2=3.5, L4=3.5+6.0606..=9.5606.. -> 9.561
        gaps = {
            "L4_requirements": 2,
            "L3_architecture": 1,
            "L2_design": 0,
            "L1_implementation": 3,
        }
        result = compute_recovery(gaps)
        self.assertAlmostEqual(result["per_layer"]["L4_requirements"]["tau"], 6.061, places=3)
        self.assertAlmostEqual(result["per_layer"]["L3_architecture"]["tau"], 2.0, places=3)
        self.assertAlmostEqual(result["per_layer"]["L2_design"]["tau"], 0.0, places=3)
        self.assertAlmostEqual(result["per_layer"]["L1_implementation"]["tau"], 1.5, places=3)
        self.assertAlmostEqual(result["t_recovery"], 9.561, places=3)
        self.assertAlmostEqual(result["weighted_cost"], 203.318, places=3)
        self.assertEqual(result["per_layer"]["L1_implementation"]["cumulative_cost"], 1.5)
        self.assertEqual(result["per_layer"]["L2_design"]["cumulative_cost"], 1.5)
        self.assertEqual(result["per_layer"]["L3_architecture"]["cumulative_cost"], 3.5)
        self.assertAlmostEqual(result["per_layer"]["L4_requirements"]["cumulative_cost"], 9.561, places=3)
        self.assertTrue(result["estimate"])
        self.assertIsNone(result["delta"])
        self.assertIsNone(result["net_benefit"])
        self.assertIsNone(result["breakeven_exceeded"])

    def test_cumulative_cost_order_is_layer_order_not_input_order(self):
        # Same gaps as above but supplied in a scrambled dict order (L4
        # first, L1 last) — cumulative_cost must still follow the fixed
        # L1->L4 order, not insertion order.
        gaps = {
            "L4_requirements": 2,
            "L1_implementation": 3,
            "L3_architecture": 1,
            "L2_design": 0,
        }
        result = compute_recovery(gaps)
        self.assertEqual(result["per_layer"]["L1_implementation"]["cumulative_cost"], 1.5)
        self.assertEqual(result["per_layer"]["L2_design"]["cumulative_cost"], 1.5)
        self.assertEqual(result["per_layer"]["L3_architecture"]["cumulative_cost"], 3.5)

    def test_custom_rate_overrides_default_for_that_layer_only(self):
        # tau_L4 = 2 / 0.5 = 4.0 (custom rate); tau_L1 = 3 / 2.0 = 1.5 (default).
        # weighted_cost = 30*4 + 1*1.5 = 121.5. delta=10 -> net_benefit=-111.5,
        # breakeven_exceeded = 121.5 > 10 = True.
        gaps = {"L4_requirements": 2, "L1_implementation": 3}
        result = compute_recovery(gaps, rates={"L4_requirements": 0.5}, delta=10)
        self.assertAlmostEqual(result["per_layer"]["L4_requirements"]["tau"], 4.0)
        self.assertFalse(result["per_layer"]["L4_requirements"]["using_default_rate"])
        self.assertTrue(result["per_layer"]["L1_implementation"]["using_default_rate"])
        self.assertAlmostEqual(result["t_recovery"], 5.5)
        self.assertAlmostEqual(result["weighted_cost"], 121.5)
        self.assertAlmostEqual(result["net_benefit"], -111.5)
        self.assertTrue(result["breakeven_exceeded"])
        # Still "estimate" overall because L1 used the default rate.
        self.assertTrue(result["estimate"])

    def test_all_rates_supplied_is_not_an_estimate(self):
        gaps = {"L1_implementation": 2}
        result = compute_recovery(gaps, rates={"L1_implementation": 4.0})
        self.assertFalse(result["estimate"])

    def test_breakeven_not_exceeded_when_cost_below_delta(self):
        # gap=1 -> tau = 1/2.0 = 0.5 -> weighted_cost = 1*0.5 = 0.5.
        # delta=10 far exceeds it -> net gain, not a break-even loss.
        gaps = {"L1_implementation": 1}
        result = compute_recovery(gaps, delta=10)
        self.assertAlmostEqual(result["weighted_cost"], 0.5)
        self.assertAlmostEqual(result["net_benefit"], 9.5)
        self.assertFalse(result["breakeven_exceeded"])

    def test_no_delta_leaves_breakeven_fields_null(self):
        result = compute_recovery({"L1_implementation": 1})
        self.assertIsNone(result["delta"])
        self.assertIsNone(result["net_benefit"])
        self.assertIsNone(result["breakeven_exceeded"])

    def test_unknown_layer_rejected(self):
        with self.assertRaises(ValueError):
            compute_recovery({"not_a_layer": 1})

    def test_zero_rate_rejected(self):
        with self.assertRaises(ValueError):
            compute_recovery({"L1_implementation": 1}, rates={"L1_implementation": 0})

    def test_negative_rate_rejected(self):
        with self.assertRaises(ValueError):
            compute_recovery({"L1_implementation": 1}, rates={"L1_implementation": -1})

    def test_negative_gap_rejected(self):
        with self.assertRaises(ValueError):
            compute_recovery({"L1_implementation": -1})

    def test_non_finite_gap_rejected(self):
        for gap in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(gap=gap), self.assertRaises(ValueError):
                compute_recovery({"L1_implementation": gap})


class CliTests(unittest.TestCase):
    def _run(self, stdin_text: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, str(SCRIPT)],
            input=stdin_text,
            capture_output=True,
            text=True,
        )

    def test_cli_smoke(self):
        proc = self._run(json.dumps({
            "gaps": {"L4_requirements": 2, "L1_implementation": 3}
        }))
        self.assertEqual(proc.returncode, 0)
        payload = json.loads(proc.stdout)
        self.assertAlmostEqual(payload["t_recovery"], 7.561, places=3)

    def test_cli_rejects_missing_gaps(self):
        proc = self._run("{}")
        self.assertEqual(proc.returncode, 1)
        self.assertIn("No 'gaps'", proc.stderr)

    def test_cli_runs_from_arbitrary_cwd(self):
        # Regression check for the `from score import CASCADE` co-located
        # import: must resolve via the script's own directory on sys.path,
        # not the caller's cwd.
        proc = subprocess.run(
            [sys.executable, str(SCRIPT)],
            input=json.dumps({"gaps": {"L1_implementation": 1}}),
            capture_output=True,
            text=True,
            cwd=str(Path(__file__).resolve().parent.parent.parent.parent),
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)


if __name__ == "__main__":
    unittest.main()

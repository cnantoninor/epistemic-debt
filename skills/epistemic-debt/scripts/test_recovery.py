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

from cli_harness import CliHarness  # noqa: E402
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
        # Four entries in `gaps` -> four layers assessed.
        self.assertEqual(result["layers_assessed"], 4)
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

    def test_empty_gaps_yields_zero_recovery(self):
        # Valid when every assessed layer carries epistemic credit (gaps
        # floored to 0) or zero-valued layers were omitted — no debt to recover.
        # `estimate` stays False here by the field's contract ("true whenever
        # any layer used a default rate" — with zero layers, none did); the
        # disambiguator between "zero measured debt" and "nothing measured"
        # is `layers_assessed`, which must be 0 so the report can say
        # "nothing to recover" instead of presenting a calibrated zero.
        result = compute_recovery({})
        self.assertEqual(result["per_layer"], {})
        self.assertEqual(result["t_recovery"], 0.0)
        self.assertEqual(result["weighted_cost"], 0.0)
        self.assertFalse(result["estimate"])
        self.assertEqual(result["layers_assessed"], 0)
        self.assertIsNone(result["delta"])
        self.assertIsNone(result["net_benefit"])
        self.assertIsNone(result["breakeven_exceeded"])

    def test_unknown_layer_rejected(self):
        with self.assertRaises(ValueError):
            compute_recovery({"not_a_layer": 1})

    def test_unknown_rates_key_rejected(self):
        # A typo'd rates key ("L1_implementaton", missing the second "i")
        # previously reverted that layer to the policy default in silence —
        # in Phase 5, whose entire purpose is substituting the team's
        # measured rates. It must now be a hard error naming the key.
        with self.assertRaisesRegex(
            ValueError, r"Unknown layer\(s\) in 'rates' \['L1_implementaton'\]"
        ):
            compute_recovery(
                {"L1_implementation": 3}, rates={"L1_implementaton": 10.0}
            )

    def test_rate_for_layer_absent_from_gaps_rejected(self):
        # A rate key that IS a valid layer name but has no entry in `gaps`
        # would be silently ignored (the loop only visits gaps) — a distinct
        # failure from an unknown key, with its own legible message.
        with self.assertRaisesRegex(ValueError, r"no entry in 'gaps'"):
            compute_recovery({"L1_implementation": 3}, rates={"L2_design": 1.5})

    def test_gap_at_scale_max_accepted_but_above_rejected(self):
        # score.py bounds c and g to [0, SCALE_MAX=5], so a legitimate gap
        # can never exceed 5 — a 6 (or score.py's adjacent `weighted` field,
        # 10-30x larger) must be rejected, not inflate the estimate.
        # Hand-checked accept case: gap 5 at L1 default rate 2.0 ->
        # tau = 5 / 2.0 = 2.5.
        result = compute_recovery({"L1_implementation": 5})
        self.assertAlmostEqual(result["per_layer"]["L1_implementation"]["tau"], 2.5)
        with self.assertRaises(ValueError):
            compute_recovery({"L1_implementation": 6})

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

    def test_non_finite_or_non_numeric_rate_rejected(self):
        # Rate validation must catch the same non-finite/invalid inputs gap
        # validation already rejects, rather than silently propagating NaN
        # (nan <= 0 is False), collapsing tau to 0 (inf <= 0 is False), or
        # raising an unhelpful TypeError (None <= 0).
        for rate in (float("nan"), float("inf"), float("-inf"), None):
            with self.subTest(rate=rate), self.assertRaises(ValueError):
                compute_recovery({"L1_implementation": 1}, rates={"L1_implementation": rate})

    def test_non_numeric_gap_rejected(self):
        # bool subclasses int, so JSON `true` previously passed math.isfinite
        # and became a gap of 1; a string made math.isfinite raise TypeError
        # rather than a legible validation error.
        for gap in (True, False, "3", None, [1]):
            with self.subTest(gap=gap), self.assertRaises(ValueError):
                compute_recovery({"L1_implementation": gap})

    def test_non_numeric_rate_rejected(self):
        for rate in (True, "2", [2]):
            with self.subTest(rate=rate), self.assertRaises(ValueError):
                compute_recovery({"L1_implementation": 1}, rates={"L1_implementation": rate})

    def test_non_finite_or_non_numeric_delta_rejected(self):
        # NaN delta made `weighted_cost > delta` False, reporting
        # "break-even not exceeded" for an input with no verdict to give
        # (and emitting a bare NaN literal, which is not valid JSON).
        for delta in (float("nan"), float("inf"), float("-inf"), True, "10", [10]):
            with self.subTest(delta=delta), self.assertRaises(ValueError):
                compute_recovery({"L1_implementation": 1}, delta=delta)

    def test_cumulative_cost_matches_t_recovery_despite_per_layer_rounding(self):
        # Regression: with default rates (L1=2.0, L2=1.0), tau_L1 = (1/7)/2
        # = 0.0714285... and tau_L2 = (4/7)/1 = 0.5714285.... Previously
        # cumulative_cost summed each layer's already-rounded tau (0.071 +
        # 0.571 = 0.642), while t_recovery summed the unrounded taus and
        # rounded once at the end (0.0714285... + 0.5714285... = 0.6428571...
        # -> 0.643) — a 0.001 mismatch between two values meant to represent
        # the same total. Both must now derive from the same unrounded
        # values so the highest present layer's cumulative_cost always
        # equals t_recovery.
        gaps = {
            "L1_implementation": 1 / 7,
            "L2_design": 4 / 7,
        }
        result = compute_recovery(gaps)
        last_cumulative = result["per_layer"]["L2_design"]["cumulative_cost"]
        self.assertEqual(last_cumulative, result["t_recovery"])
        self.assertEqual(last_cumulative, 0.643)


class CliTests(CliHarness, unittest.TestCase):
    SCRIPT = SCRIPT

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

    def test_cli_accepts_empty_gaps(self):
        # An empty gaps map (all layers carry credit / were omitted) is valid
        # and must produce zeroed recovery output, not a rejection.
        proc = self._run(json.dumps({"gaps": {}}))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        payload = json.loads(proc.stdout)
        self.assertEqual(payload["per_layer"], {})
        self.assertEqual(payload["t_recovery"], 0.0)
        self.assertEqual(payload["weighted_cost"], 0.0)

    def test_cli_reports_malformed_stdin_without_a_stack_trace(self):
        # Same contract as the other two CLIs: exit 1, one legible line, no
        # traceback from .items() or .get() (shared contract assertion in
        # cli_harness.py).
        self.assert_malformed_stdin_contract((
            "[1, 2, 3]", "not json", '{"gaps": [1, 2]}',
            '{"gaps": {"L1_implementation": 1}, "rates": [1]}',
            '{"gaps": {"L1_implementation": true}}',
        ))

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

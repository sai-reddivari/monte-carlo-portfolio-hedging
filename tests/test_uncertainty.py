"""Known statistical identities and invalid-data checks for Monte Carlo intervals."""
import json
import unittest

import numpy as np
from scipy.stats import norm

from hedging_harness.uncertainty import (
    expected_shortfall, mean_interval, paired_tail_difference, risk_interval,
)


class UncertaintyTests(unittest.TestCase):
    def test_expected_shortfall_uses_worst_rounded_up_tail(self):
        pnl = np.array([100., -10., 3., -20., 5.])
        self.assertEqual(expected_shortfall(pnl, .21), 15.)
        self.assertEqual(expected_shortfall(pnl, 1.), -15.6)
        np.testing.assert_array_equal(pnl, [100., -10., 3., -20., 5.])

    def test_profitable_tail_is_negative_loss(self):
        self.assertEqual(expected_shortfall([1., 2., 3.], .05), -1.)

    def test_identical_policies_have_exactly_zero_paired_uncertainty(self):
        pnl = np.array([-10., -4., 0., 3., 8., 20.])
        result = paired_tail_difference(pnl, pnl, n_bootstrap=150, tail_probability=.4)
        for name in ["estimate", "lower", "upper", "bootstrap_se"]:
            self.assertEqual(result[name], 0.)
        self.assertEqual(result["tail_count"], 3)
        json.dumps(result, allow_nan=False)

    def test_constant_profit_improvement_reduces_loss_es_by_same_amount(self):
        right = np.arange(-30., 31.)
        left = right + 7.
        result = paired_tail_difference(left, right, n_bootstrap=250, tail_probability=.2)
        for name in ["estimate", "lower", "upper"]:
            self.assertAlmostEqual(result[name], -7., places=12)
        self.assertLess(result["bootstrap_se"], 1e-12)

    def test_difference_of_es_is_not_es_of_difference(self):
        left = [-100., 0., 100., 0.]
        right = [0., -100., 0., 100.]
        result = paired_tail_difference(left, right, tail_probability=.25, n_bootstrap=100)
        self.assertEqual(result["estimate"], 0.)
        self.assertEqual(expected_shortfall(np.asarray(left) - right, .25), 100.)

    def test_resampling_is_reproducible_and_chunk_invariant(self):
        rng = np.random.default_rng(23)
        right = rng.normal(0., 5., size=250)
        left = .8 * right + rng.normal(0., .5, size=250)
        a = paired_tail_difference(left, right, seed=7, n_bootstrap=213, chunk_size=1)
        b = paired_tail_difference(left, right, seed=7, n_bootstrap=213, chunk_size=31)
        self.assertEqual(a, b)
        self.assertNotEqual(a, paired_tail_difference(left, right, seed=8, n_bootstrap=213))

    def test_known_cost_mean_interval_and_degenerate_case(self):
        result = mean_interval([100., 200., 300., 400.])
        expected_se = np.sqrt(50000 / 3) / 2
        self.assertEqual(result["mean"], 250.)
        self.assertAlmostEqual(result["se"], expected_se)
        self.assertAlmostEqual(result["upper"], 250 + norm.ppf(.975) * expected_se)
        self.assertLess(result["mean"], 400)
        constant = mean_interval([12., 12., 12.])
        self.assertEqual(constant["se"], 0.)
        self.assertEqual(constant["lower"], 12.)
        self.assertEqual(constant["upper"], 12.)
        json.dumps(result, allow_nan=False)

    def test_risk_intervals_report_correct_statistic_and_constant_uncertainty(self):
        for metric, expected in [("es", -12.), ("std", 0.), ("rmse", 12.)]:
            result = risk_interval([12., 12., 12.], metric=metric, n_bootstrap=50)
            self.assertEqual(result["estimate"], expected)
            self.assertEqual(result["lower"], expected)
            self.assertEqual(result["upper"], expected)
            self.assertEqual(result["bootstrap_se"], 0.)
            json.dumps(result, allow_nan=False)
        result = risk_interval([-3., 1., 2.], metric="std", n_bootstrap=100)
        self.assertAlmostEqual(result["estimate"], np.std([-3., 1., 2.], ddof=1))

    def test_paired_input_validation(self):
        invalid = [[], [1.], [1., np.nan], [1., np.inf], [[1., 2.]], ["a", "b"]]
        for values in invalid:
            with self.subTest(values=values):
                with self.assertRaises(ValueError):
                    mean_interval(values)
                with self.assertRaises(ValueError):
                    paired_tail_difference(values, values)
        with self.assertRaises(ValueError):
            paired_tail_difference([1., 2.], [1., 2., 3.])

    def test_parameter_validation(self):
        bad_settings = [
            {"confidence": 1}, {"confidence": 0}, {"confidence": np.nan},
            {"tail_probability": 0}, {"tail_probability": 1.01},
            {"n_bootstrap": 1}, {"n_bootstrap": True}, {"n_bootstrap": 2.5},
            {"chunk_size": 0}, {"seed": -1}, {"seed": True},
        ]
        for settings in bad_settings:
            with self.subTest(settings=settings):
                with self.assertRaises(ValueError):
                    paired_tail_difference([1., 2.], [1., 2.], **settings)
        with self.assertRaises(ValueError):
            risk_interval([1., 2.], metric="unknown")


if __name__ == "__main__":
    unittest.main()

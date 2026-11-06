"""Temporal availability, target alignment and covariance invariants."""
from dataclasses import replace
import unittest

import numpy as np
import pandas as pd

from hedging_harness.risk_models import (
    RiskProtocol, add_losses, chronological_nonoverlap, covariance_estimates,
    covariance_forecasts, log_returns, moving_block_mean_interval,
    validate_prices, variance_forecasts,
)


class RiskModelTests(unittest.TestCase):
    def setUp(self):
        rng = np.random.default_rng(11)
        self.dates = pd.bdate_range("2016-01-01", periods=180)
        self.prices = pd.DataFrame(
            100 * np.exp(np.cumsum(rng.normal(0, .01, size=(180, 3)), axis=0)),
            index=self.dates, columns=["A", "B", "C"],
        )
        self.protocol = RiskProtocol(
            train_start="2016-01-01", train_end="2016-03-31",
            validation_start="2016-04-01", validation_end="2016-05-31",
            test_start="2016-06-01", test_end="2016-12-31",
            lookback=20, recent_window=5, horizons=(5, 10), bootstrap_repetitions=100,
        )

    def test_forecasts_are_invariant_to_future_price_perturbation(self):
        origin = self.dates[80]
        changed = self.prices.copy()
        changed.loc[changed.index > origin] *= np.exp(np.arange(99)[:, None] * .02)
        before = variance_forecasts(self.prices, self.protocol)
        after = variance_forecasts(changed, self.protocol)
        columns = ["origin", "asset", "horizon", "model", "variance_forecast", "feature_last_date"]
        pd.testing.assert_frame_equal(
            before.loc[before["origin"] <= origin, columns].reset_index(drop=True),
            after.loc[after["origin"] <= origin, columns].reset_index(drop=True),
        )
        before_cov = covariance_forecasts(self.prices, self.protocol)
        after_cov = covariance_forecasts(changed, self.protocol)
        pd.testing.assert_frame_equal(
            before_cov.loc[before_cov["origin"] <= origin, columns].reset_index(drop=True),
            after_cov.loc[after_cov["origin"] <= origin, columns].reset_index(drop=True),
        )

    def test_targets_use_strictly_next_returns_and_exact_horizon(self):
        panel = variance_forecasts(self.prices, self.protocol)
        row = panel.loc[(panel["model"] == "rv_long") & (panel["asset"] == "A")].iloc[0]
        returns = log_returns(self.prices)
        position = returns.index.get_loc(row["origin"])
        expected = np.sum(returns.iloc[position + 1:position + 1 + row["horizon"]]["A"] ** 2)
        self.assertAlmostEqual(row["realized_variance"], expected)
        self.assertEqual(row["target_start"], returns.index[position + 1])
        self.assertEqual(row["target_end"], returns.index[position + row["horizon"]])
        self.assertAlmostEqual(row["variance_forecast"], row["horizon"] * np.mean(returns.iloc[position - 19:position + 1]["A"] ** 2))

    def test_covariances_are_symmetric_psd_and_shrinkage_is_positive_definite(self):
        history = np.column_stack([np.arange(20), 2 * np.arange(20), np.ones(20)]) * .001
        estimates = covariance_estimates(history)
        for covariance in estimates.values():
            np.testing.assert_allclose(covariance, covariance.T)
            self.assertGreaterEqual(np.linalg.eigvalsh(covariance).min(), -1e-12)
        self.assertGreater(np.linalg.eigvalsh(estimates["diagonal_shrinkage"]).min(), 0)
        self.assertGreater(np.linalg.eigvalsh(estimates["internal_factor"]).min(), 0)

    def test_nonoverlap_and_split_boundaries(self):
        panel = chronological_nonoverlap(variance_forecasts(self.prices, self.protocol), self.protocol)
        for (label, horizon), group in panel.groupby(["split", "horizon"]):
            dates = group[["origin", "target_start", "target_end"]].drop_duplicates().sort_values("origin")
            self.assertTrue((dates["target_start"].iloc[1:].to_numpy() > dates["target_end"].iloc[:-1].to_numpy()).all())
            end = pd.Timestamp(getattr(self.protocol, "train_end" if label == "train" else f"{label}_end"))
            self.assertTrue(group["target_end"].le(end).all())
        invalid = variance_forecasts(self.prices, self.protocol)
        invalid.loc[0, "feature_last_date"] = invalid.loc[0, "origin"] + pd.Timedelta(days=1)
        with self.assertRaises(ValueError):
            chronological_nonoverlap(invalid, self.protocol)

    def test_external_factors_are_past_only_and_aligned(self):
        factors = self.prices[["A", "B"]].rename(columns={"A": "SPY", "B": "XLF"})
        base = covariance_forecasts(self.prices, self.protocol, factors)
        self.assertIn("external_factor", base["model"].unique())
        origin = self.dates[80]
        changed = factors.copy()
        changed.loc[changed.index > origin] *= 1.7
        altered = covariance_forecasts(self.prices, self.protocol, changed)
        pd.testing.assert_frame_equal(
            base.loc[base["origin"] <= origin].reset_index(drop=True),
            altered.loc[altered["origin"] <= origin].reset_index(drop=True),
        )
        self.assertGreaterEqual(base["minimum_covariance_eigenvalue"].min(), -1e-12)
        with self.assertRaises(ValueError):
            covariance_forecasts(self.prices, self.protocol, factors.iloc[1:])

    def test_equal_weight_portfolio_target(self):
        row = covariance_forecasts(self.prices, self.protocol).iloc[0]
        returns = log_returns(self.prices)
        position = returns.index.get_loc(row["origin"])
        target = np.sum(returns.iloc[position + 1:position + row["horizon"] + 1].mean(axis=1) ** 2)
        self.assertAlmostEqual(row["realized_variance"], target)

    def test_qlike_and_mse_known_values(self):
        scored = add_losses(pd.DataFrame({"variance_forecast": [2., 1.], "realized_variance": [2., 2.]}))
        np.testing.assert_allclose(scored["mse"], [0., 1.])
        np.testing.assert_allclose(scored["qlike"], [np.log(2) + 1, 2.])
        zero = add_losses(pd.DataFrame({"variance_forecast": [0.], "realized_variance": [0.]}))
        self.assertTrue(np.isfinite(zero["qlike"]).all())

    def test_block_bootstrap_reproducible_and_preserves_constant_difference(self):
        a = moving_block_mean_interval(np.arange(50.), block_length=5, n_bootstrap=100, seed=5)
        b = moving_block_mean_interval(np.arange(50.), block_length=5, n_bootstrap=100, seed=5)
        self.assertEqual(a, b)
        constant = moving_block_mean_interval(np.full(20, -3.), block_length=4)
        self.assertEqual(constant["estimate"], -3.)
        self.assertEqual(constant["lower"], -3.)
        self.assertEqual(constant["upper"], -3.)

    def test_reject_invalid_prices_and_protocol(self):
        for changed in [self.prices.iloc[::-1], self.prices.set_axis([self.dates[0]] * len(self.prices)), self.prices.assign(A=np.nan)]:
            with self.assertRaises(ValueError):
                validate_prices(changed)
        with self.assertRaises(ValueError):
            replace(self.protocol, test_start="2015-01-01")
        with self.assertRaises(ValueError):
            covariance_estimates(np.ones((1, 3)))


if __name__ == "__main__":
    unittest.main()

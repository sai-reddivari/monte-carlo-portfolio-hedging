"""Economic and accounting checks for state-dependent stock hedge policies."""
from dataclasses import replace
import unittest

import numpy as np

from hedging_harness import Book, HedgePolicy, hedge, paired_difference, simulate_paths, summarize


class PolicyTests(unittest.TestCase):
    def setUp(self):
        self.book = Book(("A", "B"), (100., 100.), (100., 100.),
                         (100000., 100000.), (.2, .3), steps=12)
        self.paths = simulate_paths(self.book, self.book.pricing_vols,
                                    [[1., .4], [.4, 1.]], n_paths=100, seed=191)

    def test_zero_band_matches_daily_trades_and_pnl(self):
        daily = hedge(self.book, self.paths, cost_bps=7, audit_path=0)
        for kind in ("delta_band", "maturity_band"):
            band = hedge(self.book, self.paths, cost_bps=7, audit_path=0,
                         policy=HedgePolicy(kind=kind, band=0.0))
            for field in ("terminal_pnl", "nominal_costs", "financed_costs", "turnover", "trade_counts"):
                np.testing.assert_allclose(getattr(band, field), getattr(daily, field), atol=1e-10)
            np.testing.assert_allclose(band.ledger.shares_after, daily.ledger.shares_after)

    def test_wide_band_matches_initial_only_including_costs(self):
        initial = hedge(self.book, self.paths, hedge_every=None, cost_bps=7, audit_path=0)
        band = hedge(self.book, self.paths, cost_bps=7, audit_path=0,
                     policy=HedgePolicy(kind="delta_band", band=2.0))
        np.testing.assert_allclose(band.terminal_pnl, initial.terminal_pnl, atol=1e-10)
        np.testing.assert_allclose(band.turnover, initial.turnover, atol=1e-10)
        np.testing.assert_array_equal(band.trade_counts, initial.trade_counts)
        self.assertTrue(band.ledger.loc[band.ledger.step.between(1, 11), "event"].eq("hold").all())

    def test_band_ledger_distinguishes_names_and_settles(self):
        book = replace(self.book, notionals=(100., 100.), steps=3)
        paths = np.array([[[100., 100.], [100., 120.], [100., 125.], [105., 130.]]])
        result = hedge(book, paths, cost_bps=5, audit_path=0,
                       policy=HedgePolicy(kind="delta_band", band=.1))
        step_one = result.ledger.loc[result.ledger.step.eq(1)].set_index("name")
        self.assertEqual(step_one.loc["A", "event"], "hold")
        self.assertEqual(step_one.loc["A", "trade_units"], 0)
        self.assertEqual(step_one.loc["A", "transaction_cost"], 0)
        self.assertEqual(step_one.loc["B", "event"], "rebalance")
        self.assertGreater(step_one.loc["B", "transaction_cost"], 0)
        last = result.ledger.loc[result.ledger.step.eq(book.steps)]
        self.assertTrue(last.event.eq("settle").all())
        self.assertTrue(last.shares_after.eq(0).all())
        self.assertTrue(last.option_liability.eq(0).all())
        for _, frame in result.ledger.groupby("name"):
            changes = frame.premium_received + frame.interest + frame.stock_cashflow - frame.transaction_cost - frame.payoff_paid
            np.testing.assert_allclose(frame.cash, changes.cumsum(), atol=1e-10)

    def test_maturity_band_narrows_near_expiry(self):
        book = Book(("A",), (100.,), (100.,), (100.,), (.2,), steps=4, rate=0.)
        paths = np.array([[[100.], [100.], [100.], [100.25], [100.]]])
        fixed = hedge(book, paths, audit_path=0, policy=HedgePolicy(kind="delta_band", band=.1))
        adaptive = hedge(book, paths, audit_path=0, policy=HedgePolicy(kind="maturity_band", band=.1))
        self.assertEqual(fixed.ledger.loc[fixed.ledger.step.eq(3), "event"].iloc[0], "hold")
        self.assertEqual(adaptive.ledger.loc[adaptive.ledger.step.eq(3), "event"].iloc[0], "rebalance")
        self.assertAlmostEqual(HedgePolicy(kind="maturity_band", band=.1).threshold(.25, 1.), .05)

    def test_band_cost_identity_and_no_future_information(self):
        policy = HedgePolicy(kind="maturity_band", band=.08)
        gross = hedge(self.book, self.paths, cost_bps=0, policy=policy)
        net = hedge(self.book, self.paths, cost_bps=9, policy=policy, audit_path=0)
        np.testing.assert_allclose(gross.terminal_pnl - net.terminal_pnl, net.financed_costs, atol=1e-9)
        changed = self.paths.copy()
        changed[:, 7:, :] *= 1.5
        modified = hedge(self.book, changed, cost_bps=9, policy=policy, audit_path=0)
        np.testing.assert_array_equal(net.ledger.loc[net.ledger.step.le(6), "shares_after"],
                                      modified.ledger.loc[modified.ledger.step.le(6), "shares_after"])

    def test_peak_shared_borrowing_is_concurrent_not_sum_of_peaks(self):
        book = replace(self.book, notionals=(100., 100.), steps=3, rate=0.)
        paths = np.array([[[100., 100.], [150., 80.], [80., 150.], [110., 110.]]])
        result = hedge(book, paths, audit_path=0)
        per_name_peak = result.ledger.groupby("name").cash.min().mul(-1).clip(lower=0)
        portfolio_cash = result.ledger.groupby("step").cash.sum()
        actual_shared_peak = max(-portfolio_cash.min(), 0)
        np.testing.assert_allclose(result.peak_borrowing[0], per_name_peak.reindex(book.names))
        self.assertAlmostEqual(result.peak_portfolio_borrowing[0], actual_shared_peak)
        self.assertLess(actual_shared_peak, result.peak_borrowing[0].sum())
        table = summarize(result)
        self.assertAlmostEqual(table.loc["Portfolio", "mean_peak_borrowing"], actual_shared_peak)
        self.assertAlmostEqual(table.loc["A", "max_peak_borrowing"], per_name_peak["A"])

    def test_peak_borrowing_tracks_accrued_cash_before_settlement(self):
        book = Book(("A",), (100.,), (100.,), (100.,), (.2,), steps=1, sessions_per_year=1, rate=.1)
        paths = np.array([[[100.], [200.]]])
        result = hedge(book, paths, audit_path=0)
        cash_after_open = result.ledger.iloc[0].cash
        before_settlement = cash_after_open * np.exp(.1)
        expected = max(-cash_after_open, -before_settlement, -result.ledger.iloc[-1].cash, 0)
        self.assertAlmostEqual(result.peak_borrowing[0, 0], expected)

    def test_scenario_identity_rejects_false_pairing_even_with_same_label(self):
        left = hedge(self.book, self.paths, scenario_label="selection")
        same = hedge(self.book, self.paths.copy(), hedge_every=5, scenario_label="different label")
        self.assertEqual(left.scenario_id, same.scenario_id)
        paired_difference(left, same)
        changed = self.paths.copy()
        changed[:, -1, 0] *= 1.01
        right = hedge(self.book, changed, scenario_label="selection")
        self.assertNotEqual(left.scenario_id, right.scenario_id)
        with self.assertRaisesRegex(ValueError, "scenario IDs"):
            paired_difference(left, right)

    def test_explicit_periodic_policy_preserves_legacy_behavior(self):
        legacy = hedge(self.book, self.paths, hedge_every=5, cost_bps=5, audit_path=0)
        explicit = hedge(self.book, self.paths, cost_bps=5, audit_path=0,
                         policy=HedgePolicy(kind="periodic", hedge_every=5))
        np.testing.assert_array_equal(legacy.terminal_pnl, explicit.terminal_pnl)
        self.assertTrue(legacy.ledger.equals(explicit.ledger))

    def test_policy_validation(self):
        for kwargs in [dict(kind="unknown"), dict(band=-.1), dict(band=np.nan),
                       dict(kind="periodic", band=.1), dict(hedge_every=0),
                       dict(hedge_every=True), dict(label="")]:
            with self.assertRaises(ValueError):
                HedgePolicy(**kwargs)
        with self.assertRaises(TypeError):
            hedge(self.book, self.paths, policy={"kind": "delta_band", "band": .1})


if __name__ == "__main__":
    unittest.main()

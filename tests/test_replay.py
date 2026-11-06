"""Independent hand-accounting checks for model contracts on dated observations."""
import unittest
from pathlib import Path
import tempfile

import numpy as np
import pandas as pd

from BlackScholes_Functions.BlackScholes_D1D2_Price_Payoff_Greeks import bs_price
from hedging_harness.replay import OptionPosition, replay


class ReplayTests(unittest.TestCase):
    def setUp(self):
        self.dates = pd.bdate_range("2024-01-02", periods=5)
        self.prices = pd.DataFrame({"A": [100., 95., 105., 110., 90.]}, index=self.dates)

    def option(self, **kwargs):
        values = dict(instrument_id="put_A", underlying="A", kind="put", strike=100.,
                      expiry=self.dates[-1], quantity=1., volatility=.2, multiplier=100.)
        values.update(kwargs)
        return OptionPosition(**values)

    def test_long_equity_protective_put_manual_floor_and_capital(self):
        option = self.option()
        premium = 100 * bs_price(100, 100, 4/252, 0., .2, "put")
        for terminal_spot in (80., 120.):
            prices = self.prices.copy()
            prices.iloc[-1, 0] = terminal_spot
            result = replay(prices, [option], equity_holdings={"A": 100}, hedge_options=False)
            self.assertEqual(result.initial_capital, 10000.)
            self.assertAlmostEqual(result.ledger.iloc[0].opening_option_cashflow, -premium)
            self.assertAlmostEqual(result.ledger.iloc[0].cash, -premium)
            self.assertAlmostEqual(result.ledger.iloc[0].nav, 10000.)
            self.assertTrue(result.holdings.hedge_shares.eq(0).all())
            expected_nav = 100 * max(terminal_spot, 100) - premium
            self.assertAlmostEqual(result.terminal_nav, expected_nav)
            self.assertAlmostEqual(result.terminal_pnl, expected_nav - 10000.)
            self.assertEqual(result.ledger.iloc[-1].core_equity_value, 0.)
            self.assertEqual(result.ledger.iloc[-1].option_value, 0.)
            self.assertAlmostEqual(result.ledger.daily_pnl.sum(), result.terminal_pnl)

    def test_short_call_initial_hedge_only_closed_form(self):
        option = self.option(instrument_id="short_call", kind="call", quantity=-1.)
        result = replay(self.prices, [option], hedge_options=True, hedge_every=None,
                        cost_bps=5., rate=.04, initial_capital=0.)
        opening = result.holdings.xs(self.dates[0], level="date").loc["A"]
        shares = opening.hedge_shares
        self.assertGreater(shares, 0.)
        premium = -float(result.option_ledger.iloc[0].model_value)
        initial_cash = premium - shares * 100 - shares * 100 * .0005
        terminal = self.prices.iloc[-1, 0]
        payoff = 100 * max(terminal - 100, 0)
        expected = initial_cash * np.exp(.04 * 4/252) + shares * terminal * (1 - .0005) - payoff
        self.assertAlmostEqual(result.terminal_pnl, expected, places=9)
        self.assertAlmostEqual(result.ledger.iloc[-1].cash, expected, places=9)
        self.assertEqual(result.holdings.iloc[-1].hedge_shares, 0.)

    def test_multiple_options_and_expiries_reset_only_remaining_delta(self):
        early_call = self.option(instrument_id="early_call", kind="call", quantity=-1., expiry=self.dates[2])
        late_put = self.option(instrument_id="late_put", kind="put", quantity=1.)
        result = replay(self.prices, [early_call, late_put], hedge_options=True, hedge_every=10)
        early = result.option_ledger.xs("early_call", level="instrument_id")
        late = result.option_ledger.xs("late_put", level="instrument_id")
        self.assertEqual(early.loc[self.dates[2], "event"], "settle")
        self.assertEqual(early.loc[self.dates[2], "settlement_cashflow"], -500.)
        self.assertEqual(early.loc[self.dates[2], "model_value"], 0.)
        self.assertEqual(early.loc[self.dates[3], "event"], "expired")
        self.assertNotEqual(late.loc[self.dates[2], "model_value"], 0.)
        holdings = result.holdings.xs("A", level="underlying")
        self.assertAlmostEqual(holdings.loc[self.dates[2], "hedge_shares"], -late.loc[self.dates[2], "option_delta_shares"])
        self.assertEqual(late.loc[self.dates[-1], "settlement_cashflow"], 1000.)
        self.assertEqual(result.ledger.iloc[-1].option_value, 0.)

    def test_core_and_hedge_trades_execute_net_by_underlying(self):
        option = self.option(instrument_id="long_call", kind="call")
        result = replay(self.prices, [option], equity_holdings={"A": 100.},
                        hedge_options=True, cost_bps=10.)
        trade = result.trades.loc[(self.dates[0], "A")]
        self.assertEqual(trade.core_trade_shares, 100.)
        self.assertLess(trade.hedge_trade_shares, 0.)
        self.assertAlmostEqual(trade.executed_net_shares, trade.core_trade_shares + trade.hedge_trade_shares)
        self.assertAlmostEqual(trade.transaction_cost, abs(trade.executed_net_shares) * trade.spot * .001)
        self.assertAlmostEqual(result.ledger.iloc[0].nav, result.initial_capital - trade.transaction_cost)

    def test_no_future_information_changes_prior_decisions(self):
        option = self.option(instrument_id="short_call", kind="call", quantity=-1.)
        base = replay(self.prices, [option], hedge_options=True, cost_bps=5.)
        changed = self.prices.copy()
        changed.iloc[3:] *= 1.8
        other = replay(changed, [option], hedge_options=True, cost_bps=5.)
        pd.testing.assert_frame_equal(base.ledger.iloc[:3], other.ledger.iloc[:3])
        pd.testing.assert_frame_equal(base.holdings.loc[(slice(None,self.dates[2]),slice(None)), :],
                                      other.holdings.loc[(slice(None,self.dates[2]),slice(None)), :])
        self.assertNotEqual(base.provenance["prices_sha256"], other.provenance["prices_sha256"])

    def test_nav_and_cash_flow_reconciliation_with_equity_retained(self):
        option = self.option()
        result = replay(self.prices, [option], equity_holdings={"A": 100.},
                        hedge_options=False, liquidate_at_end=False, rate=.04, cost_bps=5.)
        self.assertEqual(result.holdings.iloc[-1].core_shares, 100.)
        self.assertEqual(result.ledger.iloc[-1].option_value, 0.)
        np.testing.assert_allclose(result.ledger.nav,
                                   result.ledger.cash + result.ledger.core_equity_value
                                   + result.ledger.hedge_stock_value + result.ledger.option_value)
        changes = (result.ledger.interest + result.ledger.opening_option_cashflow
                   + result.ledger.option_settlement_cashflow + result.ledger.stock_cashflow
                   - result.ledger.transaction_cost)
        np.testing.assert_allclose(result.ledger.cash, result.initial_capital + changes.cumsum())
        self.assertGreater(result.peak_borrowing, 0.)
        self.assertGreater(result.total_stock_cost, 0.)

    def test_equity_only_replay_keeps_explicit_capital_for_comparison(self):
        result = replay(self.prices, [], equity_holdings={"A": 50.}, initial_capital=10000.)
        self.assertEqual(result.initial_capital, 10000.)
        self.assertEqual(result.ledger.iloc[0].cash, 5000.)
        self.assertEqual(result.terminal_nav, 9500.)
        self.assertEqual(result.terminal_pnl, -500.)
        self.assertTrue(result.option_ledger.empty)

    def test_expiry_uses_declared_sessions_not_elapsed_calendar_days(self):
        dates = pd.DatetimeIndex(["2024-01-05", "2024-01-08", "2024-01-09"])
        prices = pd.DataFrame({"A": [100.,100.,100.]}, index=dates)
        option = self.option(expiry=dates[-1])
        result = replay(prices, [option], rate=.05, sessions_per_year=252)
        expected_price = bs_price(100,100,2/252,.05,.2,"put")
        self.assertAlmostEqual(result.ledger.iloc[0].opening_option_cashflow,-100*expected_price)
        self.assertEqual(result.option_ledger.iloc[0].remaining_sessions,2)

    def test_reject_missing_nonpositive_and_future_asof_inputs(self):
        option = self.option()
        for value in [np.nan, np.inf, 0., -1.]:
            prices = self.prices.copy()
            prices.iloc[1,0] = value
            with self.assertRaises(ValueError):
                replay(prices,[option])
        with self.assertRaisesRegex(ValueError,"as_of"):
            replay(self.prices,[option],as_of=self.dates[1])
        with self.assertRaisesRegex(ValueError,"calendar"):
            replay(self.prices.drop(self.dates[1]),[option],session_calendar=self.dates)
        with self.assertRaises(ValueError):
            replay(self.prices.iloc[::-1],[option])
        with self.assertRaises(ValueError):
            replay(self.prices,[self.option(expiry="2025-01-01")])
        with self.assertRaises(ValueError):
            replay(self.prices,[self.option(expiry=self.dates[0])])
        with self.assertRaises(ValueError):
            replay(self.prices,[self.option(underlying="MISSING")])

    def test_position_and_policy_validation(self):
        for change in [dict(kind="american"),dict(quantity=0),dict(multiplier=0),dict(volatility=-.1),
                       dict(expiry="bad date"),dict(instrument_id="")]:
            with self.assertRaises(ValueError):
                self.option(**change)
        with self.assertRaises(ValueError):
            replay(self.prices,[self.option(),self.option()])
        with self.assertRaises(ValueError):
            replay(self.prices,[self.option()],hedge_every=0)
        with self.assertRaises(ValueError):
            replay(self.prices,[self.option()],initial_capital=-100)

    def test_study_runner_uses_prior_returns_and_does_not_invent_source_verification(self):
        from commands.run_model_contract_replay import run_study

        dates = pd.bdate_range("2017-01-02", "2020-04-30")
        time = np.arange(len(dates))
        fixture = pd.DataFrame({
            name: 100 * np.exp(.0002 * time + .02 * np.sin(time / period))
            for name, period in [("JPM", 11), ("PNC", 17), ("GS", 23)]
        }, index=dates)
        fixture.index.name = "date"
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "prices.csv"
            fixture.to_csv(source)
            study = run_study(source, write_outputs=False, make_plot=False)
        self.assertFalse(study["manifest"]["market_data_source_verified"])
        self.assertFalse(study["manifest"]["historical_option_backtest_gate_passed"])
        self.assertEqual(len(study["results"]), 6)
        calibration = study["calibration"]
        self.assertTrue(calibration.return_observations.eq(252).all())
        self.assertTrue(calibration.price_observations.eq(253).all())
        self.assertTrue((pd.to_datetime(calibration.cutoff) < pd.to_datetime(calibration.replay_start)).all())
        self.assertTrue(study["checks"].drop(columns=["window", "strategy"]).all().all())


if __name__ == "__main__":
    unittest.main()

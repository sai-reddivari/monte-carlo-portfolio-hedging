"""Hand-calculated accounting and protocol checks for the Stage-6 overlays.

Expected dollar values are worked out in the comments from share counts, strikes
and terminal prices, so they do not repeat the implementation. Premiums come from
a local erf-based formula rather than the library replay uses.
"""
from dataclasses import replace
import json
import math
from pathlib import Path
import tempfile
import unittest

import numpy as np
import pandas as pd

from hedging_harness import overlays as ov
from hedging_harness.replay import OptionPosition

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "equity_overlay_study.json"


def black_scholes(spot, strike, years, rate, sigma, kind):
    d1 = (math.log(spot / strike) + (rate + sigma ** 2 / 2) * years) / (sigma * math.sqrt(years))
    d2 = d1 - sigma * math.sqrt(years)
    normal = lambda x: (1 + math.erf(x / math.sqrt(2))) / 2
    if kind == "call":
        return spot * normal(d1) - strike * math.exp(-rate * years) * normal(d2)
    return strike * math.exp(-rate * years) * normal(-d2) - spot * normal(-d1)


def settings(**changes):
    values = dict(capital=100000., rate=0., cost_bps=0., sessions_per_year=252, multiplier=100.,
                  lookback=5, ewma_lambda=.94, etf="XLF")
    values.update(changes)
    return ov.Settings(**values)


WEIGHTS = {"A": .5, "B": -.25}
SIGMA = .2


def state(a=100., b=50., x=20., beta_a=1., beta_b=1., ratio=1.):
    """A decision state with hand-chosen spots, so strikes are known exactly."""
    date = pd.Timestamp("2024-01-01")
    vol = {"A": SIGMA, "B": SIGMA, "XLF": SIGMA}
    return ov.DecisionState(date, {"A": a, "B": b, "XLF": x}, vol, dict(vol), {"A": beta_a, "B": beta_b},
                            ratio * .1, .1)


def window(sessions=3):
    dates = pd.bdate_range("2024-01-02", periods=sessions + 1)
    return ov.Window("test", 0, pd.Timestamp("2024-01-01"), dates[0], dates[-1], sessions)


def panel(a_end, b_end, x_end=20., sessions=3):
    """Flat prices that move only on the last session."""
    dates = pd.bdate_range("2024-01-02", periods=sessions + 1)
    frame = pd.DataFrame({"A": 100., "B": 50., "XLF": 20.}, index=dates)
    frame.iloc[-1] = [a_end, b_end, x_end]
    return frame


def run(candidate, prices, active=None, decision=None):
    active = active or settings()
    target, decision = window(len(prices) - 1), decision or state()
    instruction = ov.build_instruction(candidate, decision, target, WEIGHTS, active)
    result = ov.run_window(prices, target, instruction, active)
    record = ov.window_record(result, instruction, target, decision, WEIGHTS, active)
    return instruction, result, record


BIG = 10.  # A budget of 1000% of capital, so full coverage is always affordable.
PUT = dict(label="p", family="long_puts", moneyness=.95, annual_budget=BIG)
CALL = dict(label="c", family="short_calls", moneyness=1.05, annual_budget=BIG)
SPREAD = dict(label="s", family="structures", structure="put_spread", long_put=.95, short_put=.85, annual_budget=BIG)
COLLAR = dict(label="k", family="structures", structure="collar", long_put=.95, short_call=1.10, annual_budget=BIG)
UNHEDGED = dict(label="unhedged", family="unhedged")
YEARS = 3 / 252


class SignsAndMultipliers(unittest.TestCase):
    def test_book_is_500_long_a_and_500_short_b(self):
        # 0.5 * 100,000 / 100 = 500 shares long; 0.25 * 100,000 / 50 = 500 shares short.
        self.assertEqual(ov.build_book(state().spots, WEIGHTS, 100000.), {"A": 500., "B": -500.})

    def test_whole_shares_truncate_toward_zero_on_both_sides(self):
        book = ov.build_book({"A": 33., "B": 33.}, WEIGHTS, 100000.)
        self.assertEqual(book, {"A": 1515., "B": -757.})

    def test_purchased_put_and_call_are_positive_with_multiplier_units(self):
        for candidate, kind, name, strike in ((PUT, "put", "A", 95.), (CALL, "call", "B", 52.5)):
            instruction = ov.build_instruction(candidate, state(), window(), WEIGHTS, settings())
            position, = instruction.positions
            self.assertEqual((position.kind, position.underlying), (kind, name))
            self.assertAlmostEqual(position.strike, strike)
            self.assertEqual(position.quantity, 5.)    # 500 shares / 100-share contract
            self.assertEqual(position.multiplier, 100.)
            self.assertEqual(position.units, 500.)

    def test_written_legs_are_negative(self):
        spread = ov.build_instruction(SPREAD, state(), window(), WEIGHTS, settings()).positions
        collar = ov.build_instruction(COLLAR, state(), window(), WEIGHTS, settings()).positions
        self.assertEqual([p.quantity for p in spread], [5., -5.])
        self.assertEqual([(p.kind, p.quantity) for p in collar], [("put", 5.), ("call", -5.)])

    def test_premium_scales_by_contracts_and_multiplier(self):
        _, result, record = run(PUT, panel(100., 50.))
        unit = black_scholes(100, 95, YEARS, 0., SIGMA, "put")
        self.assertAlmostEqual(record["premium_paid"], 5 * 100 * unit, places=8)
        self.assertAlmostEqual(result.ledger.iloc[0]["opening_option_cashflow"], -500 * unit, places=8)

    def test_budget_buys_partial_coverage_rounded_down(self):
        unit = black_scholes(1000, 950, YEARS, 0., SIGMA, "put")
        # One name, 5,000 shares at 1000 = 50 contracts at full coverage.
        decision = state(a=10., b=50.)
        full = 5000 * black_scholes(10, 9.5, YEARS, 0., SIGMA, "put")
        self.assertGreater(unit, 0)
        annual = .5 * full / (100000. * YEARS)  # Spend exactly half of the full premium.
        candidate = dict(PUT, annual_budget=annual)
        instruction = ov.build_instruction(candidate, decision, window(), WEIGHTS, settings())
        self.assertAlmostEqual(instruction.target_coverage, .5)
        self.assertEqual(instruction.positions[0].quantity, 25.)
        tighter = ov.build_instruction(dict(PUT, annual_budget=annual * .99), decision, window(), WEIGHTS, settings())
        self.assertEqual(tighter.positions[0].quantity, 24.)  # 24.75 contracts rounds down.

    def test_coverage_never_exceeds_full(self):
        instruction = ov.build_instruction(PUT, state(), window(), WEIGHTS, settings())
        self.assertEqual(instruction.target_coverage, 1.)


class PayoffFloorsAndCaps(unittest.TestCase):
    def premium(self, strike, spot=100., kind="put"):
        return 500 * black_scholes(spot, strike, YEARS, 0., SIGMA, kind)

    def test_protective_put_floor_holds_for_any_lower_terminal_price(self):
        # 500 shares fall from 100 to the 95 strike: -2,500 is the most the stock can cost.
        for terminal in (90., 60., 10.):
            _, result, _ = run(PUT, panel(terminal, 50.))
            self.assertAlmostEqual(result.terminal_pnl, -2500. - self.premium(95.), places=7)

    def test_put_keeps_upside_less_premium(self):
        _, result, _ = run(PUT, panel(120., 50.))  # 500 * 20 = 10,000 stock gain, put expires worthless.
        self.assertAlmostEqual(result.terminal_pnl, 10000. - self.premium(95.), places=7)

    def test_short_call_caps_upside_loss_at_the_strike(self):
        # 500 short shares rise from 50 to the 52.5 strike: -1,250 is the largest loss.
        premium = self.premium(52.5, 50., "call")
        for terminal in (60., 100., 400.):
            _, result, _ = run(CALL, panel(100., terminal))
            self.assertAlmostEqual(result.terminal_pnl, -1250. - premium, places=7)

    def test_short_call_keeps_gain_when_short_falls(self):
        _, result, _ = run(CALL, panel(100., 40.))  # 500 * 10 = 5,000 short gain.
        self.assertAlmostEqual(result.terminal_pnl, 5000. - self.premium(52.5, 50., "call"), places=7)

    def test_put_spread_protection_stops_at_the_lower_strike(self):
        cost = self.premium(95.) - self.premium(85.)
        # Between strikes the floor holds: 95 stock loss of 2,500.
        _, result, _ = run(SPREAD, panel(88., 50.))
        self.assertAlmostEqual(result.terminal_pnl, -2500. - cost, places=7)
        # Below 85 the payoff is capped at 500 * 10 = 5,000.
        for terminal, stock in ((70., -15000.), (50., -25000.)):
            _, result, _ = run(SPREAD, panel(terminal, 50.))
            self.assertAlmostEqual(result.terminal_pnl, stock + 5000. - cost, places=7)

    def test_collar_caps_upside_at_the_call_strike(self):
        net = self.premium(95.) - self.premium(110., kind="call")
        # Above 110 the stock gain is capped at 500 * 10 = 5,000.
        for terminal in (115., 180.):
            _, result, record = run(COLLAR, panel(terminal, 50.))
            self.assertAlmostEqual(result.terminal_pnl, 5000. - net, places=7)
            self.assertGreater(record["settlement_paid"], 0.)
        _, result, _ = run(COLLAR, panel(70., 50.))
        self.assertAlmostEqual(result.terminal_pnl, -2500. - net, places=7)

    def test_paid_and_received_premium_are_reported_separately(self):
        _, _, record = run(COLLAR, panel(100., 50.))
        self.assertAlmostEqual(record["premium_paid"], self.premium(95.), places=8)
        self.assertAlmostEqual(record["premium_received"], self.premium(110., kind="call"), places=8)

    def test_sector_put_cannot_offset_a_short_squeeze(self):
        candidate = dict(label="x", family="sector_puts", moneyness=.95, annual_budget=BIG)
        _, result, record = run(candidate, panel(100., 80.))  # Short rises, XLF unchanged.
        self.assertEqual(record["settlement_received"], 0.)
        self.assertAlmostEqual(record["short_equity_pnl"], -15000.)
        self.assertAlmostEqual(result.terminal_pnl, -15000. - record["premium_paid"], places=7)

    def test_sector_put_is_sized_on_net_beta_dollars(self):
        # Beta dollars = 500*100*1.2 - 500*50*0.8 = 40,000; /20 = 2,000 XLF units = 20 contracts.
        decision = state(beta_a=1.2, beta_b=.8)
        candidate = dict(label="x", family="sector_puts", moneyness=.95, annual_budget=BIG)
        position, = ov.build_instruction(candidate, decision, window(), WEIGHTS, settings()).positions
        self.assertEqual((position.underlying, position.quantity), ("XLF", 20.))
        self.assertAlmostEqual(position.strike, 19.)

    def test_sector_put_is_not_bought_when_net_beta_is_short(self):
        decision = state(beta_a=.1, beta_b=3.)  # 5,000 - 75,000 < 0
        candidate = dict(label="x", family="sector_puts", moneyness=.95, annual_budget=BIG)
        self.assertEqual(ov.build_instruction(candidate, decision, window(), WEIGHTS, settings()).positions, ())


class CashAndComparators(unittest.TestCase):
    def test_inception_cash_and_interest_by_hand(self):
        active = settings(rate=.04, cost_bps=5.)
        _, result, record = run(PUT, panel(100., 50.), active)
        premium = 500 * black_scholes(100, 95, YEARS, .04, SIGMA, "put")
        entry_cost = (50000 + 25000) * .0005  # 37.50
        opening_cash = 100000 - 50000 + 25000 - premium - entry_cost
        self.assertAlmostEqual(result.ledger.iloc[0]["cash"], opening_cash, places=7)
        self.assertAlmostEqual(result.ledger.iloc[0]["nav"], 100000 - entry_cost, places=7)
        interest = opening_cash * (math.exp(.04 * 3 / 252) - 1)
        self.assertAlmostEqual(record["interest"], interest, places=6)
        self.assertAlmostEqual(result.terminal_pnl, interest - premium - 2 * entry_cost, places=6)

    def test_reduced_book_keeps_unused_capital_as_cash_at_the_same_rate(self):
        reduced = dict(label="r", family="reduced_equity", scale=.5)
        active = settings(rate=.04)
        _, full, _ = run(UNHEDGED, panel(100., 50.), active)
        instruction, half, record = run(reduced, panel(100., 50.), active)
        self.assertEqual(instruction.core_holdings, {"A": 250., "B": -250.})
        self.assertEqual(half.initial_capital, full.initial_capital)
        self.assertEqual(half.ledger.iloc[0]["cash"], 87500.)   # 100,000 - 25,000 + 12,500
        self.assertEqual(full.ledger.iloc[0]["cash"], 75000.)   # 100,000 - 50,000 + 25,000
        self.assertAlmostEqual(record["interest"], 87500 * (math.exp(.04 * 3 / 252) - 1), places=6)
        self.assertEqual(record["net_exposure_pct"], 12.5)
        self.assertEqual(record["gross_exposure_pct"], 37.5)

    def test_etf_hedge_is_a_separate_sleeve_with_hand_beta_sizing(self):
        # Beta dollars = 50,000 - 25,000 = 25,000 at beta one; /20 = 1,250 shares short.
        candidate = dict(label="e", family="etf_hedge", hedge_ratio=1.)
        instruction, result, record = run(candidate, panel(90., 50., 18.))
        self.assertEqual(instruction.etf_holdings, {"XLF": -1250.})
        self.assertEqual(instruction.core_holdings, {"A": 500., "B": -500.})
        self.assertAlmostEqual(record["long_equity_pnl"], -5000.)
        self.assertAlmostEqual(record["etf_pnl"], 2500.)        # 1,250 * (20 - 18)
        self.assertAlmostEqual(result.terminal_pnl, -2500.)
        self.assertAlmostEqual(record["beta_net_pct"], 0.)
        self.assertAlmostEqual(record["etf_exposure_pct"], -25.)

    def test_attribution_sums_to_terminal_pnl(self):
        active = settings(rate=.03, cost_bps=7.)
        for candidate in (PUT, CALL, COLLAR):
            _, result, r = run(candidate, panel(85., 60.), active)
            total = (r["long_equity_pnl"] + r["short_equity_pnl"] + r["etf_pnl"] + r["premium_received"]
                     - r["premium_paid"] + r["settlement_received"] - r["settlement_paid"]
                     + r["interest"] - r["stock_cost"])
            self.assertAlmostEqual(total, result.terminal_pnl, places=6)

    def test_drawdown_is_within_window_and_measured_from_capital(self):
        prices = panel(100., 50., sessions=3)
        prices.iloc[1, 0] = 110.   # NAV 105,000
        prices.iloc[2, 0] = 90.    # NAV 95,000
        _, _, record = run(UNHEDGED, prices)
        self.assertAlmostEqual(record["max_drawdown_pct"], 10.)  # 10,000 / 100,000

    def test_funding_excludes_short_proceeds_when_they_are_unavailable(self):
        weights = {"A": 1.5, "B": -.5}
        decision = state()
        target = window()
        active = settings()
        instruction = ov.build_instruction(UNHEDGED, decision, target, weights, active)
        result = ov.run_window(panel(100., 50.), target, instruction, active)
        record = ov.window_record(result, instruction, target, decision, weights, active)
        # Cash 100,000 - 150,000 + 50,000 = 0, so there is no ledger borrowing.
        self.assertEqual(record["peak_borrowing"], 0.)
        # Without the 50,000 of short proceeds the long book needs 50,000 of funding.
        self.assertEqual(record["peak_funding_ex_short_proceeds"], 50000.)

    def test_verify_window_catches_a_wrong_instruction(self):
        target, active = window(), settings()
        prices = panel(80., 50.)
        instruction = ov.build_instruction(PUT, state(), target, WEIGHTS, active)
        result = ov.run_window(prices, target, instruction, active)
        record = ov.window_record(result, instruction, target, state(), WEIGHTS, active)
        self.assertTrue(all(ov.verify_window(result, instruction, prices, target, record, active).values()))
        changed = replace(instruction, positions=(replace(instruction.positions[0], strike=90.),),
                          core_holdings={"A": 400., "B": -500.})
        checks = ov.verify_window(result, changed, prices, target, record, active)
        self.assertFalse(checks["expiry_payoff_recomputed"])
        self.assertFalse(checks["opening_premium_matches_units"])
        self.assertFalse(checks["holdings_match_instruction"])
        bad = dict(record, option_pnl=record["option_pnl"] + 1)
        self.assertFalse(ov.verify_window(result, instruction, prices, target, bad, active)["attribution_sums_to_pnl"])

    def test_closed_form_matches_put_call_parity(self):
        call = ov.closed_form_price(100, 95, .25, .04, .3, "call")
        put = ov.closed_form_price(100, 95, .25, .04, .3, "put")
        self.assertAlmostEqual(call - put, 100 - 95 * math.exp(-.01), places=10)


def study_panel(sessions=340, seed=11):
    """A complete synthetic ten-name panel on the real configuration's columns."""
    config = ov.load_config(CONFIG)
    names = [*ov.signed_weights(config), "XLF"]
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2015-01-02", periods=sessions)
    common = rng.normal(.0003, .012, sessions)
    returns = common[:, None] + rng.normal(0, .009, (sessions, len(names)))
    return pd.DataFrame(100 * np.exp(returns.cumsum(axis=0)), index=dates, columns=names), config


class StudyGrid(unittest.TestCase):
    def setUp(self):
        self.prices, self.config = study_panel()
        self.weights = ov.signed_weights(self.config)
        self.settings = ov.Settings.from_config(self.config)
        self.candidates = ov.expand_candidates(self.config)
        calendar = self.prices.index
        self.window = ov.build_windows(calendar, "test", calendar[0], calendar[-1], 63, 252)[0]

    def test_config_declares_a_six_to_ten_name_mandate_and_all_eight_comparisons(self):
        self.assertEqual(len(self.weights), 10)
        self.assertAlmostEqual(sum(abs(v) for v in self.weights.values()), 1.3)
        self.assertAlmostEqual(sum(self.weights.values()), .5)
        families = {row["family"] for row in self.candidates}
        self.assertEqual(families, {"unhedged", "reduced_equity", "etf_hedge", "long_puts", "short_calls",
                                    "sector_puts", "structures", "risk_informed"})
        structures = {row.get("structure") for row in self.candidates if row["family"] == "structures"}
        self.assertEqual(structures, {"put_spread", "collar"})

    def test_config_rejects_a_mandate_that_misstates_itself(self):
        for change in (dict(gross_exposure=1.2), dict(net_exposure=.6)):
            config = json.loads(CONFIG.read_text())
            config["book"].update(change)
            with self.assertRaises(ValueError):
                ov.validate_config(config)
        config = json.loads(CONFIG.read_text())
        config["book"]["shorts"]["JPM"] = .1
        with self.assertRaises(ValueError):
            ov.validate_config(config)
        config = json.loads(CONFIG.read_text())
        config["windows"]["decision_lag_sessions"] = 0
        with self.assertRaises(ValueError):
            ov.validate_config(config)

    def test_every_policy_shares_capital_and_core_book_except_reduced(self):
        records, checks, kept = ov.evaluate_windows(self.prices, [self.window], self.candidates, self.weights,
                                                    self.settings, keep=lambda *_: True)
        self.assertTrue(checks.drop(columns=["key", "label"]).all().all())
        self.assertEqual(records["initial_capital"].nunique(), 1)
        base = kept[self.window.key, ov.BASELINE][1].core_holdings
        for row in self.candidates:
            result, instruction, _ = kept[self.window.key, row["label"]]
            self.assertEqual(result.initial_capital, self.config["capital"])
            self.assertFalse(result.provenance["hedge_options"])
            self.assertEqual(result.provenance["data_label"], ov.LABEL)
            if row["family"] == "reduced_equity":
                self.assertNotEqual(instruction.core_holdings, base)
            else:
                self.assertEqual(instruction.core_holdings, base)
        unhedged = records.set_index("label").loc[ov.BASELINE]
        protected = records.loc[~records["family"].isin(["reduced_equity"])]
        for column in ("long_equity_pnl", "short_equity_pnl", "gross_exposure_pct", "net_exposure_pct"):
            np.testing.assert_allclose(protected[column], unhedged[column])

    def test_budget_is_respected_at_the_decision_estimate(self):
        for row in self.candidates:
            if "annual_budget" not in row:
                continue
            state_now = ov.estimate_state(self.prices, self.window.decision_date, self.weights, self.settings)
            instruction = ov.build_instruction(row, state_now, self.window, self.weights, self.settings)
            self.assertLessEqual(instruction.target_coverage, 1.)
            spend = instruction.target_coverage * instruction.full_coverage_premium
            self.assertLessEqual(spend, instruction.window_budget * (1 + 1e-9))


class FutureInformation(unittest.TestCase):
    def setUp(self):
        self.prices, self.config = study_panel()
        self.weights = ov.signed_weights(self.config)
        self.settings = ov.Settings.from_config(self.config)
        calendar = self.prices.index
        self.window = ov.build_windows(calendar, "test", calendar[0], calendar[-1], 63, 252)[0]
        self.candidates = ov.expand_candidates(self.config)

    def decisions(self, prices):
        state_now = ov.estimate_state(prices, self.window.decision_date, self.weights, self.settings)
        return state_now, [ov.build_instruction(row, state_now, self.window, self.weights, self.settings)
                           for row in self.candidates]

    def test_execution_close_and_later_prices_cannot_change_any_decision(self):
        changed = self.prices.copy()
        changed.loc[self.window.start:] *= 3.
        self.assertEqual(self.decisions(self.prices), self.decisions(changed))

    def test_decision_close_does_change_decisions_as_a_control(self):
        changed = self.prices.copy()
        changed.loc[self.window.decision_date] *= 1.1
        self.assertNotEqual(self.decisions(self.prices)[0], self.decisions(changed)[0])

    def test_strike_comes_from_the_decision_close_not_the_execution_close(self):
        state_now, instructions = self.decisions(self.prices)
        puts = next(i for i in instructions if i.family == "long_puts")
        position = puts.positions[0]
        decision_spot = self.prices.loc[self.window.decision_date, position.underlying]
        execution_spot = self.prices.loc[self.window.start, position.underlying]
        self.assertNotEqual(decision_spot, execution_spot)
        self.assertAlmostEqual(position.strike, .95 * decision_spot)

    def test_volatility_uses_exactly_the_past_252_returns(self):
        state_now, _ = self.decisions(self.prices)
        closes = self.prices.loc[:self.window.decision_date, "JPM"].to_numpy()[-253:]
        returns = np.diff(np.log(closes))
        mean = returns.sum() / 252
        hand = math.sqrt(((returns - mean) ** 2).sum() / 251) * math.sqrt(252)
        self.assertAlmostEqual(state_now.trailing_vol["JPM"], hand, places=10)

    def test_beta_recovers_a_known_multiple_and_ignores_future_returns(self):
        rng = np.random.default_rng(5)
        dates = pd.bdate_range("2020-01-01", periods=40)
        xlf = rng.normal(0, .01, 40).cumsum()
        prices = pd.DataFrame({"A": 100 * np.exp(2 * xlf), "B": 100 * np.exp(.5 * xlf),
                               "XLF": 100 * np.exp(xlf)}, index=dates)
        active = settings(lookback=20)
        estimate = ov.estimate_state(prices, dates[25], WEIGHTS, active)
        self.assertAlmostEqual(estimate.betas["A"], 2.)
        self.assertAlmostEqual(estimate.betas["B"], .5)
        broken = prices.copy()
        broken.loc[dates[26]:, "A"] *= np.linspace(1, 5, 14)
        self.assertEqual(ov.estimate_state(broken, dates[25], WEIGHTS, active), estimate)

    def test_estimate_refuses_short_history_and_unobserved_dates(self):
        with self.assertRaisesRegex(ValueError, "Insufficient"):
            ov.estimate_state(self.prices, self.prices.index[100], self.weights, self.settings)
        with self.assertRaisesRegex(ValueError, "observed session"):
            ov.estimate_state(self.prices, "2015-12-26", self.weights, self.settings)

    def test_risk_state_switches_budget_only_from_the_past_ratio(self):
        candidate = dict(label="r", family="risk_informed", moneyness=.95, threshold=1.25,
                         annual_budget=.02, low_state_budget_fraction=.5)
        active = settings()
        calm = ov.build_instruction(candidate, state(ratio=1.2), window(63), WEIGHTS, active)
        stressed = ov.build_instruction(candidate, state(ratio=1.25), window(63), WEIGHTS, active)
        self.assertFalse(calm.risk_state_elevated)
        self.assertTrue(stressed.risk_state_elevated)
        self.assertAlmostEqual(calm.window_budget, 250.)     # 100,000 * 2% * 63/252 * 0.5
        self.assertAlmostEqual(stressed.window_budget, 500.)

    def test_pricing_sensitivity_changes_price_and_coverage_but_not_risk_estimates(self):
        decision = state()
        base = settings()
        dear = base.with_(pricing=dict(name="x", source="trailing", multiplier=1.5))
        self.assertAlmostEqual(ov.pricing_volatility(decision, "A", dear.pricing), .3)
        candidate = dict(PUT, annual_budget=.02)
        low = ov.build_instruction(candidate, decision, window(63), WEIGHTS, base)
        high = ov.build_instruction(candidate, decision, window(63), WEIGHTS, dear)
        self.assertLess(high.target_coverage, low.target_coverage)
        self.assertEqual(high.window_budget, low.window_budget)

    def test_reactive_pricing_uses_the_larger_estimate(self):
        decision = replace(state(), ewma_vol={"A": .5, "B": .1, "XLF": .2})
        reactive = dict(name="r", source="reactive", multiplier=1.)
        self.assertEqual(ov.pricing_volatility(decision, "A", reactive), .5)
        self.assertEqual(ov.pricing_volatility(decision, "B", reactive), SIGMA)
        with self.assertRaises(ValueError):
            ov.pricing_volatility(decision, "A", dict(reactive, source="implied"))


class CalendarAndWindows(unittest.TestCase):
    def setUp(self):
        self.prices, self.config = study_panel()
        self.core = self.prices.drop(columns=["XLF"])
        self.benchmarks = self.prices[["XLF"]]

    def test_panel_joins_only_exactly_aligned_complete_data(self):
        self.assertEqual(ov.align_panel(self.core, self.benchmarks, self.config).shape, self.prices.shape)
        with self.assertRaisesRegex(ValueError, "differ"):
            ov.align_panel(self.core, self.benchmarks.iloc[:-1], self.config)
        with self.assertRaisesRegex(ValueError, "Missing"):
            ov.align_panel(self.core.drop(columns=["JPM"]), self.benchmarks, self.config)
        for bad in (np.nan, np.inf, 0., -5.):
            frame = self.core.copy()
            frame.iloc[7, 2] = bad
            with self.assertRaisesRegex(ValueError, "finite"):
                ov.align_panel(frame, self.benchmarks, self.config)

    def test_window_with_a_missing_session_is_refused(self):
        target = window()
        prices = panel(100., 50.).drop(index=target.start + pd.offsets.BDay(1))
        instruction = ov.build_instruction(UNHEDGED, state(), target, WEIGHTS, settings())
        with self.assertRaisesRegex(ValueError, "declared sessions"):
            ov.run_window(prices, target, instruction, settings())

    def test_windows_are_disjoint_inside_the_split_and_keep_a_decision_lag(self):
        calendar = pd.bdate_range("2015-01-02", periods=700)
        start, end = calendar[300], calendar[600]
        windows = ov.build_windows(calendar, "validation", start, end, 63, 252)
        self.assertEqual(len(windows), 4)  # 300 intervals hold four 63-session windows.
        for before, after in zip(windows, windows[1:]):
            self.assertEqual(before.end, after.start)
        for item in windows:
            self.assertGreaterEqual(item.start, start)
            self.assertLessEqual(item.end, end)
            self.assertEqual(calendar.get_loc(item.start) - calendar.get_loc(item.decision_date), 1)
            self.assertEqual(calendar.get_loc(item.end) - calendar.get_loc(item.start), 63)
        self.assertEqual(ov.unused_sessions(windows, calendar, start, end), 300 - 252)

    def test_first_window_waits_for_the_full_lookback(self):
        calendar = pd.bdate_range("2015-01-02", periods=400)
        first = ov.build_windows(calendar, "train", calendar[0], calendar[-1], 63, 252)[0]
        # 252 returns need 253 closes: decision index 252, execution index 253.
        self.assertEqual(calendar.get_loc(first.decision_date), 252)
        self.assertEqual(calendar.get_loc(first.start), 253)

    def test_partial_final_window_is_dropped(self):
        calendar = pd.bdate_range("2015-01-02", periods=300)
        windows = ov.build_windows(calendar, "test", calendar[0], calendar[-1], 63, 10)
        self.assertLessEqual(calendar.get_loc(windows[-1].end), 299)
        self.assertGreater(calendar.get_loc(windows[-1].end) + 63, 299)

    def test_actual_panel_matches_the_exchange_calendar(self):
        config = ov.load_config(CONFIG)
        actual = ov.load_panel(config, ROOT)
        self.assertEqual(list(actual.columns), [*ov.signed_weights(config), "XLF"])
        self.assertEqual(len(actual), 4236)
        self.assertIn(ov.exchange_calendar_matches(actual.index), (True, None))


class Selection(unittest.TestCase):
    def setUp(self):
        self.config = ov.load_config(CONFIG)
        self.candidates = ov.expand_candidates(self.config)

    def frame(self, split="validation"):
        rows = [dict(split=split, label=row["label"], es_loss_pct=5., annual_net_premium_pct=1.)
                for row in self.candidates]
        return pd.DataFrame(rows)

    def test_lowest_validation_es_wins_and_test_rows_are_ignored(self):
        validation = self.frame()
        validation.loc[validation.label.eq("long_put_k90_b2"), "es_loss_pct"] = 3.
        test = self.frame("test")
        test.loc[test.label.eq("long_put_k95_b1"), "es_loss_pct"] = -50.
        chosen = ov.select_policies(pd.concat([validation, test]), self.candidates, self.config)
        self.assertEqual(chosen["long_puts"]["label"], "long_put_k90_b2")

    def test_frontier_only_budget_cannot_be_selected(self):
        validation = self.frame()
        validation.loc[validation.label.eq("long_put_k95_b4"), "es_loss_pct"] = -9.
        chosen = ov.select_policies(validation, self.candidates, self.config)
        self.assertNotIn("b4", chosen["long_puts"]["label"])
        self.assertNotIn("long_put_k95_b4", chosen["long_puts"]["candidates_considered"])

    def test_ties_break_to_the_lower_premium(self):
        validation = self.frame()
        validation.loc[validation.label.eq("short_call_k110_b1"), "annual_net_premium_pct"] = .5
        chosen = ov.select_policies(validation, self.candidates, self.config)
        self.assertEqual(chosen["short_calls"]["label"], "short_call_k110_b1")

    def test_baselines_are_not_selected(self):
        chosen = ov.select_policies(self.frame(), self.candidates, self.config)
        self.assertEqual(set(chosen), set(self.config["selection"]["selected_families"]))


class WindowStatistics(unittest.TestCase):
    def records(self):
        rows = []
        for index, (base, policy) in enumerate([(-10., -4.), (-5., -3.), (2., 1.), (8., 6.)]):
            for label, pnl in ((ov.BASELINE, base), ("p", policy)):
                rows.append(dict(split="test", window=index, key=f"test-{index:03d}", label=label, family=label,
                                 start=f"2024-0{index + 1}-01", end=f"2024-0{index + 2}-01", sessions=63,
                                 initial_capital=100., pnl=pnl, pnl_pct=pnl, max_drawdown_pct=abs(pnl),
                                 premium_paid=1., premium_received=0., settlement_received=0., settlement_paid=0.,
                                 stock_cost=.5, interest=.25, peak_borrowing=2., peak_funding_ex_short_proceeds=3.,
                                 window_budget=1., target_coverage=.5, gross_exposure_pct=130., net_exposure_pct=50.,
                                 etf_exposure_pct=0., delta_adjusted_net_pct=40., beta_net_pct=45.))
        return pd.DataFrame(rows)

    def test_downside_and_upside_are_measured_on_baseline_windows(self):
        row = ov.summarize(self.records(), .5).set_index("label").loc["p"]
        self.assertEqual((row.n_windows, row.adverse_windows, row.up_windows, row.tail_windows), (4, 2, 2, 2))
        self.assertAlmostEqual(row.downside_capture, 7 / 15)   # (-4 + -3) / (-10 + -5)
        self.assertAlmostEqual(row.upside_retained, .7)        # (1 + 6) / (2 + 8)
        self.assertAlmostEqual(row.es_loss_pct, 3.5)           # Mean of the two worst losses.
        self.assertAlmostEqual(row.worst_pnl_pct, -4.)
        self.assertAlmostEqual(row.peak_borrowing_pct, 2.)

    def test_premium_is_an_annual_spending_rate_not_a_compounded_return(self):
        row = ov.summarize(self.records(), .5).set_index("label").loc["p"]
        # Four 63-session windows are one year: 4 * 1 of premium on 100 of capital.
        self.assertAlmostEqual(row.annual_premium_paid_pct, 4.)
        self.assertAlmostEqual(row.annual_stock_cost_pct, 2.)

    def test_summary_has_no_chained_portfolio_metrics(self):
        columns = " ".join(ov.summarize(self.records(), .5).columns).lower()
        for forbidden in ("cagr", "compound", "cumulative", "full_period", "sharpe"):
            self.assertNotIn(forbidden, columns)

    def test_identical_series_have_zero_uncertainty(self):
        values = np.array([-3., 1., 2., -8., 4., 5.])
        result = ov.block_es_difference(values, values, tail_probability=.25, block_length=2, n_bootstrap=200, seed=1)
        self.assertEqual((result["estimate"], result["lower"], result["upper"]), (0., 0., 0.))

    def test_additive_improvement_reduces_es_by_that_amount(self):
        values = np.array([-3., 1., 2., -8., 4., 5., -1., 0.])
        result = ov.block_es_difference(values + 1, values, tail_probability=.25, block_length=3, n_bootstrap=200, seed=2)
        self.assertAlmostEqual(result["estimate"], -1.)
        self.assertAlmostEqual(result["lower"], -1.)
        self.assertAlmostEqual(result["upper"], -1.)

    def test_block_resampling_is_seeded_and_keeps_neighbours_together(self):
        rng = np.random.default_rng(3)
        indices = ov._block_indices(rng, 10, 3, 50)
        self.assertEqual(indices.shape, (50, 10))
        steps = (indices[:, 1:3] - indices[:, 0:2]) % 10
        self.assertTrue((steps == 1).all())  # The first block stays chronological, wrapping circularly.
        values = np.arange(10.)
        arguments = dict(tail_probability=.3, block_length=3, n_bootstrap=100, seed=9)
        self.assertEqual(ov.block_es_difference(values, values[::-1], **arguments),
                         ov.block_es_difference(values, values[::-1], **arguments))

    def test_paired_uncertainty_marks_small_samples_exploratory(self):
        config = ov.load_config(CONFIG)
        table = ov.paired_uncertainty(self.records(), ["p"], config)
        row = table.iloc[0]
        self.assertEqual((row.evidence, row.n_windows), ("exploratory", 4))
        self.assertAlmostEqual(row.mean_difference_pct, (6 + 2 - 1 - 2) / 4)

    def test_adjacent_tail_windows_count_as_one_episode(self):
        records = self.records()
        episodes = ov.tail_episodes(records, .5)
        self.assertEqual(len(episodes), 1)
        self.assertEqual(episodes.iloc[0].windows, 2)
        records.loc[(records.label == ov.BASELINE) & (records.window == 1), "pnl"] = 5.
        records.loc[(records.label == ov.BASELINE) & (records.window == 3), "pnl"] = -2.
        self.assertEqual(len(ov.tail_episodes(records, .5)), 2)


class ReportingAdditions(unittest.TestCase):
    def rows(self):
        base = dict(split="test", label="c", family="short_calls", initial_capital=100.)
        return pd.DataFrame([
            dict(base, long_equity_pnl=-20., short_equity_pnl=-10., option_pnl=6., settlement_received=7.),
            dict(base, long_equity_pnl=5., short_equity_pnl=-2., option_pnl=-1., settlement_received=0.),
            dict(base, long_equity_pnl=-9., short_equity_pnl=4., option_pnl=-1., settlement_received=0.),
        ])

    def test_side_protection_uses_only_windows_where_that_side_lost(self):
        row = ov.side_protection(self.rows(), ["c"]).iloc[0]
        self.assertEqual((row.side, row.side_loss_windows, row.windows), ("short", 2, 3))
        self.assertAlmostEqual(row.mean_side_loss_pct, -6.)        # (-10 + -2) / 2
        self.assertAlmostEqual(row.mean_with_option_pct, -3.5)     # (-4 + -3) / 2
        self.assertAlmostEqual(row.worst_with_option_pct, -4.)
        self.assertAlmostEqual(row.side_loss_capture, 7 / 12)
        self.assertEqual(row.windows_option_paid, 1)

    def test_sector_puts_are_not_credited_to_a_single_side(self):
        rows = self.rows().assign(family="sector_puts")
        self.assertTrue(ov.side_protection(rows, ["c"]).empty)

    def test_budget_multiple_shows_a_collar_overrun(self):
        group = pd.DataFrame(dict(premium_paid=[5., 12.], premium_received=[1., 2.], window_budget=[4., 2.]))
        self.assertAlmostEqual(ov._budget_multiple(group), 5.)     # (12 - 2) / 2
        self.assertTrue(math.isnan(ov._budget_multiple(group.assign(window_budget=0.))))

    def test_ex_best_window_removes_one_favorable_episode(self):
        rows = []
        for index, (base, policy) in enumerate([(-30., 0.), (1., .5), (2., 1.5), (-1., -1.5)]):
            for label, value in ((ov.BASELINE, base), ("p", policy)):
                rows.append(dict(split="test", key=f"test-{index:03d}", label=label, pnl_pct=value))
        row = ov.paired_uncertainty(pd.DataFrame(rows), ["p"], ov.load_config(CONFIG)).iloc[0]
        self.assertAlmostEqual(row.mean_difference_pct, 7.125)     # (30 - .5 - .5 - .5) / 4
        self.assertAlmostEqual(row.mean_ex_best_window_pct, -.5)
        self.assertEqual(row.best_window_key, "test-000")


class ProtocolGuards(unittest.TestCase):
    def test_hash_ignores_key_order_but_not_values(self):
        self.assertEqual(ov.canonical_hash({"a": 1, "b": [2]}), ov.canonical_hash({"b": [2], "a": 1}))
        self.assertNotEqual(ov.canonical_hash({"a": 1}), ov.canonical_hash({"a": 2}))

    def test_file_hash_detects_edits(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "f.txt"
            path.write_text("one")
            first = ov.file_hash(path)
            path.write_text("two")
            self.assertNotEqual(first, ov.file_hash(path))

    def test_replay_option_position_contract_is_what_overlays_assume(self):
        position = OptionPosition("x", "A", "put", 95., "2024-01-05", -2., .2, 100.)
        self.assertEqual(position.units, -200.)


class EndToEndProtocol(unittest.TestCase):
    """The whole runner on synthetic prices, with the frozen-protocol guards."""

    @classmethod
    def setUpClass(cls):
        import matplotlib
        matplotlib.use("Agg")
        from commands import run_overlay_research as runner
        cls.runner = runner
        cls.folder = tempfile.TemporaryDirectory()
        cls.root = Path(cls.folder.name)
        prices, config = study_panel(sessions=620, seed=23)
        dates = prices.index
        config["splits"] = dict(train=[str(dates[0].date()), str(dates[330].date())],
                                validation=[str(dates[331].date()), str(dates[470].date())],
                                test=[str(dates[471].date()), str(dates[-1].date())])
        config["windows"]["sessions"] = 20
        config["sensitivity"]["window_sessions"] = [10]
        config["uncertainty"]["n_bootstrap"] = 100
        data = cls.root / "data"
        data.mkdir()
        prices.index.name = "date"
        prices.drop(columns=["XLF"]).to_csv(data / "core.csv")
        prices[["XLF"]].to_csv(data / "bench.csv")
        (data / "meta.json").write_text("{}")
        config["data"].update(core_prices="data/core.csv", benchmark_prices="data/bench.csv",
                              metadata_files=["data/meta.json"])
        for name in runner.SOURCE_FILES:
            target = cls.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((ROOT / name).read_bytes())
        cls.config_path = cls.root / "config.json"
        cls.config_path.write_text(json.dumps(config))
        cls.prices, cls.config = prices, config
        cls.run_dir, cls.digest = runner.freeze(cls.config_path, cls.root / "run", cls.root)
        cls.protocol = json.loads((cls.run_dir / "protocol.json").read_text())
        cls.result = runner.evaluate(cls.run_dir, root=cls.root)

    @classmethod
    def tearDownClass(cls):
        cls.folder.cleanup()

    def test_selection_records_the_cutoff_and_no_test_rows(self):
        validation_end = pd.Timestamp(self.config["splits"]["validation"][1])
        self.assertLessEqual(pd.Timestamp(self.protocol["last_price_visible_to_selection"]), validation_end)
        windows = pd.read_csv(self.run_dir / "development_windows.csv")
        self.assertEqual(set(windows["split"]), {"train", "validation"})

    def test_selection_does_not_depend_on_test_prices(self):
        changed = self.prices.copy()
        changed.loc[pd.Timestamp(self.config["splits"]["test"][0]):] *= 2.5
        data = self.root / "data"
        original = (data / "core.csv").read_bytes(), (data / "bench.csv").read_bytes()
        try:
            changed.drop(columns=["XLF"]).to_csv(data / "core.csv")
            changed[["XLF"]].to_csv(data / "bench.csv")
            other, _ = self.runner.freeze(self.config_path, self.root / "changed", self.root)
        finally:
            (data / "core.csv").write_bytes(original[0])
            (data / "bench.csv").write_bytes(original[1])
        again = json.loads((other / "protocol.json").read_text())
        self.assertEqual(again["selection"], self.protocol["selection"])
        pd.testing.assert_frame_equal(pd.read_csv(other / "development_windows.csv"),
                                      pd.read_csv(self.run_dir / "development_windows.csv"))

    def test_outputs_exist_and_completion_marker_is_written(self):
        for name in ("report.md", "summary.csv", "windows.csv", "uncertainty.csv", "sensitivity.csv", "hand_legs.csv",
                     "hand_reconciliation.csv", "side_protection.csv", "manifest.json", "gate_status.json", "frontier_test.png",
                     "frontier_validation.png", "attribution_test.png", "pricing_sensitivity.png",
                     "window_scatter_test.png"):
            self.assertTrue((self.run_dir / name).is_file(), name)
        report = (self.run_dir / "report.md").read_text()
        self.assertIn(ov.LABEL, report)
        self.assertIn(self.digest, report)

    def test_hand_reconciliation_covers_both_sides_with_tiny_residuals(self):
        table = pd.read_csv(self.run_dir / "hand_reconciliation.csv")
        self.assertEqual(set(table["case"]), {"validation_long_downside", "validation_short_upside",
                                              "test_long_downside", "test_short_upside"})
        self.assertLess(table["residual"].abs().max(), 1e-5)
        stages = " ".join(table["stage"].unique())
        for stage in ("inception", "adverse", "expiry", "roll"):
            self.assertIn(stage, stages)

    def test_every_required_gate_is_honest(self):
        status = {row["gate"]: row["status"] for row in self.result["gates"]}
        self.assertEqual(status["Listed-option execution backtest"], "blocked")
        self.assertEqual(status["Survivorship-safe generalization"], "blocked")
        self.assertEqual(status["Continuous rolled portfolio NAV"], "not_available")
        self.assertEqual(status["Statistical evidence of protection"], "exploratory")
        self.assertEqual(status["Test evaluated once with no later changes"], "passed")
        self.assertEqual(status["All eight comparisons evaluated"], "passed")

    def test_missing_family_fails_its_gate(self):
        summary = self.result["summary"]
        partial = summary.loc[~(summary["split"].eq("test") & summary["family"].eq("short_calls"))]
        checks = pd.DataFrame(dict(key=["k"], label=["l"], ok=[True]))
        sensitivity = checks.assign(scenario="s")
        reconciliation = pd.DataFrame(dict(residual=[0.]))
        log = [dict(changed_files=[])]
        gates = self.runner.gate_table(self.protocol, checks, sensitivity, reconciliation, log, partial)
        status = {row["gate"]: row["status"] for row in gates}
        self.assertEqual(status["All eight comparisons evaluated"], "failed")

    def test_second_test_evaluation_is_refused_then_disclosed_with_a_note(self):
        with self.assertRaises(PermissionError):
            self.runner.evaluate(self.run_dir, root=self.root)
        result = self.runner.evaluate(self.run_dir, revision_note="fixture", root=self.root)
        self.assertEqual(result["output_dir"].name, "revision-1")
        self.assertIn("not untouched out-of-sample", (result["output_dir"] / "report.md").read_text())
        gates = {row["gate"]: row["status"] for row in result["gates"]}
        self.assertEqual(gates["Test evaluated once with no later changes"], "failed")
        log = json.loads((self.run_dir / "test_evaluation_log.json").read_text())
        self.assertEqual([row["test_informed"] for row in log], [False, True])

    def test_changed_inputs_or_tampered_protocol_are_refused(self):
        other, _ = self.runner.freeze(self.config_path, self.root / "guard", self.root)
        core = self.root / "data" / "core.csv"
        original = core.read_bytes()
        try:
            core.write_bytes(original + b"\n")
            with self.assertRaisesRegex(PermissionError, "frozen files changed"):
                self.runner.evaluate(other, root=self.root)
        finally:
            core.write_bytes(original)
        self.assertFalse((other / "test_evaluation_log.json").exists())
        text = (other / "protocol.json").read_text()
        (other / "protocol.json").write_text(text.replace('"capital": 100000000.0', '"capital": 200000000.0'))
        with self.assertRaisesRegex(ValueError, "recorded hash"):
            self.runner.evaluate(other, root=self.root)


if __name__ == "__main__":
    unittest.main()

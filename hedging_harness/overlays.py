"""Stage-6 equity long/short book with protective model-option overlays.

Results are European model options on historical underlying prices. They are not
listed-option fills and use no observed implied volatility. All cash, NAV and
settlement accounting comes from ``hedging_harness.replay``; this module only
decides what to hold and summarizes the ledgers replay returns.

Timing. Every decision for a window is made from closes up to and including the
decision date, the session before execution. ``estimate_state`` truncates its
input to that date before computing anything, and ``build_instruction`` sees only
the resulting state. Execution then happens at the next close at the replay's
model prices, so no signal is formed from the close it trades at.

Windows. ``replay`` opens every option on its first row, so continuous rolling is
unavailable. Each window is a separate account opened with the same capital.
Window results must not be chained into a NAV path, CAGR or full-period drawdown.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace as dataclass_replace
from hashlib import sha256
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd

from BlackScholes_Functions.BlackScholes_D1D2_Price_Payoff_Greeks import bs_price
from hedging_harness.replay import OptionPosition, replay
from hedging_harness.risk_models import covariance_estimates, log_returns, moving_block_mean_interval
from hedging_harness.uncertainty import expected_shortfall

LABEL = "European model options on historical underlying prices"
BASELINE = "unhedged"
BASE_PRICING = {"name": "base", "source": "trailing", "multiplier": 1.0}


# --------------------------------------------------------------------------- config

def load_config(path):
    config = json.loads(Path(path).read_text())
    validate_config(config)
    return config


def validate_config(config):
    """Reject a mandate that differs from what the protocol says it is."""
    book = config["book"]
    longs, shorts = book["longs"], book["shorts"]
    if set(longs) & set(shorts):
        raise ValueError("An issuer cannot be on both sides of the book.")
    if not 6 <= len(longs) + len(shorts) <= 10:
        raise ValueError("The mandate requires 6 to 10 names.")
    if any(weight <= 0 for weight in [*longs.values(), *shorts.values()]):
        raise ValueError("Side weights must be positive magnitudes.")
    gross = sum(longs.values()) + sum(shorts.values())
    net = sum(longs.values()) - sum(shorts.values())
    if not math.isclose(gross, book["gross_exposure"], abs_tol=1e-9):
        raise ValueError("Declared gross exposure does not match issuer weights.")
    if not math.isclose(net, book["net_exposure"], abs_tol=1e-9):
        raise ValueError("Declared net exposure does not match issuer weights.")
    if config["capital"] <= 0 or config["windows"]["sessions"] < 2:
        raise ValueError("Capital and window length must be positive.")
    if config["windows"]["decision_lag_sessions"] < 1:
        raise ValueError("Decisions must precede the execution close.")
    starts = [pd.Timestamp(config["splits"][name][0]) for name in ("train", "validation", "test")]
    ends = [pd.Timestamp(config["splits"][name][1]) for name in ("train", "validation", "test")]
    if not all(a < b for a, b in zip(ends, starts[1:])):
        raise ValueError("Chronological splits must not overlap.")
    return config


def signed_weights(config):
    book = config["book"]
    return {**book["longs"], **{name: -weight for name, weight in book["shorts"].items()}}


def expand_candidates(config):
    """Enumerate the frozen policy grid. Labels are stable protocol identifiers."""
    policies = config["policies"]
    budgets, mandate = policies["budget_grid"], policies["mandate_annual_budget"]
    pct = lambda value: f"{round(value * 100):d}"
    rows = [dict(label=BASELINE, family="unhedged", eligible=False)]
    for scale in policies["reduced_equity"]["scales"]:
        rows.append(dict(label=f"reduced_{pct(scale)}", family="reduced_equity", scale=scale, eligible=False,
                         primary=scale == policies["reduced_equity"]["primary_scale"]))
    for ratio in policies["etf_hedge"]["hedge_ratios"]:
        rows.append(dict(label=f"etf_h{pct(ratio)}", family="etf_hedge", hedge_ratio=ratio, eligible=True))
    for family, stem in (("long_puts", "long_put"), ("short_calls", "short_call"), ("sector_puts", "sector_put")):
        for moneyness in policies[family]["moneyness"]:
            for budget in budgets:
                rows.append(dict(label=f"{stem}_k{pct(moneyness)}_b{pct(budget)}", family=family,
                                 moneyness=moneyness, annual_budget=budget, eligible=budget <= mandate))
    for spec in policies["structures"]:
        second = spec.get("short_put", spec.get("short_call"))
        for budget in budgets:
            rows.append(dict(label=f"{spec['structure']}_{pct(spec['long_put'])}_{pct(second)}_b{pct(budget)}",
                             family="structures", annual_budget=budget, eligible=budget <= mandate, **spec))
    risk = policies["risk_informed"]
    for moneyness in risk["moneyness"]:
        for threshold in risk["thresholds"]:
            rows.append(dict(label=f"risk_k{pct(moneyness)}_t{pct(threshold)}", family="risk_informed",
                             moneyness=moneyness, threshold=threshold, annual_budget=mandate,
                             low_state_budget_fraction=risk["low_state_budget_fraction"], eligible=True))
    labels = [row["label"] for row in rows]
    if len(set(labels)) != len(labels):
        raise ValueError("Candidate labels must be unique.")
    return rows


@dataclass(frozen=True)
class Settings:
    capital: float
    rate: float
    cost_bps: float
    sessions_per_year: int
    multiplier: float
    lookback: int
    ewma_lambda: float
    etf: str
    pricing: dict = field(default_factory=lambda: dict(BASE_PRICING))

    @classmethod
    def from_config(cls, config):
        execution, estimation = config["execution"], config["estimation"]
        return cls(float(config["capital"]), float(execution["rate"]), float(execution["stock_cost_bps"]),
                   int(execution["sessions_per_year"]), float(execution["contract_multiplier"]),
                   int(estimation["lookback"]), float(estimation["ewma_lambda"]), config["data"]["sector_etf"])

    def with_(self, **changes):
        return dataclass_replace(self, **changes)


# --------------------------------------------------------------------------- data

def load_panel(config, root):
    """Join core and benchmark closes, refusing any misalignment or gap."""
    root = Path(root)
    core = pd.read_csv(root / config["data"]["core_prices"], index_col="date", parse_dates=["date"])
    benchmarks = pd.read_csv(root / config["data"]["benchmark_prices"], index_col="date", parse_dates=["date"])
    return align_panel(core, benchmarks, config)


def align_panel(core, benchmarks, config):
    if not core.index.equals(benchmarks.index):
        raise ValueError("Core and benchmark sessions differ; no observations are forward-filled.")
    panel = core.join(benchmarks)
    required = [*signed_weights(config), config["data"]["sector_etf"]]
    missing = sorted(set(required) - set(panel.columns))
    if missing:
        raise ValueError(f"Missing required price columns: {missing}")
    panel = panel.loc[:, required].astype(float)
    if not panel.index.is_unique or not panel.index.is_monotonic_increasing:
        raise ValueError("Sessions must be unique and increasing.")
    values = panel.to_numpy()
    if not np.isfinite(values).all() or (values <= 0).any():
        raise ValueError("Prices must be finite and positive; missing data is not filled.")
    return panel


def exchange_calendar_matches(index, calendar_name="XNYS"):
    """True or False against the versioned calendar, or None if it is unavailable."""
    try:
        import exchange_calendars
    except ImportError:
        return None
    sessions = exchange_calendars.get_calendar(calendar_name).sessions_in_range(index[0], index[-1])
    return bool(pd.DatetimeIndex(sessions).tz_localize(None).equals(pd.DatetimeIndex(index)))


# --------------------------------------------------------------------------- windows

@dataclass(frozen=True)
class Window:
    split: str
    index: int
    decision_date: pd.Timestamp
    start: pd.Timestamp
    end: pd.Timestamp
    sessions: int

    @property
    def key(self):
        return f"{self.split}-{self.index:03d}"


def build_windows(calendar, split, start, end, sessions, lookback, decision_lag=1):
    """Non-overlapping windows inside one split, sharing only boundary closes.

    Window k+1 opens at the close where window k ends, so return intervals are
    disjoint. The decision date is ``decision_lag`` sessions before the opening
    close and must have ``lookback`` prior returns.
    """
    calendar = pd.DatetimeIndex(calendar)
    inside = np.flatnonzero((calendar >= pd.Timestamp(start)) & (calendar <= pd.Timestamp(end)))
    if not len(inside):
        return []
    first = max(int(inside[0]), lookback + decision_lag)
    last = int(inside[-1])
    windows, position = [], first
    while position + sessions <= last:
        windows.append(Window(split, len(windows), calendar[position - decision_lag], calendar[position],
                              calendar[position + sessions], sessions))
        position += sessions
    return windows


def unused_sessions(windows, calendar, start, end):
    """Sessions inside a split that no window return interval covers."""
    calendar = pd.DatetimeIndex(calendar)
    inside = calendar[(calendar >= pd.Timestamp(start)) & (calendar <= pd.Timestamp(end))]
    return max(len(inside) - 1 - sum(window.sessions for window in windows), 0)


# --------------------------------------------------------------------------- estimates

@dataclass(frozen=True)
class DecisionState:
    decision_date: pd.Timestamp
    spots: dict
    trailing_vol: dict
    ewma_vol: dict
    betas: dict
    book_ewma_vol: float
    book_long_vol: float

    @property
    def risk_ratio(self):
        return self.book_ewma_vol / self.book_long_vol


def estimate_state(prices, decision_date, weights, settings):
    """All past-only estimates, using closes through ``decision_date`` only."""
    decision_date = pd.Timestamp(decision_date)
    history = prices.loc[:decision_date]
    if history.empty or history.index[-1] != decision_date:
        raise ValueError("The decision date must be an observed session.")
    names = [*weights, settings.etf]
    returns = log_returns(history.loc[:, names])
    if len(returns) < settings.lookback:
        raise ValueError("Insufficient past returns before the decision date.")
    window = returns.iloc[-settings.lookback:]
    annual = math.sqrt(settings.sessions_per_year)
    alpha = 1 - settings.ewma_lambda
    # Same uncentered EWMA recursion as hedging_harness.risk_models.variance_forecasts.
    ewma_variance = (returns ** 2).ewm(alpha=alpha, adjust=False).mean().iloc[-1]
    covariance = covariance_estimates(window.to_numpy(), shrinkage=0.0)["sample_covariance"]
    position = {name: index for index, name in enumerate(names)}
    etf_variance = covariance[position[settings.etf], position[settings.etf]]
    betas = {name: float(covariance[position[name], position[settings.etf]] / etf_variance) for name in weights}
    book_returns = returns.loc[:, list(weights)].to_numpy() @ np.array(list(weights.values()))
    book_ewma = pd.Series(book_returns ** 2).ewm(alpha=alpha, adjust=False).mean().iloc[-1]
    book_long = float(np.mean(book_returns[-settings.lookback:] ** 2))
    return DecisionState(
        decision_date, {name: float(history[name].iloc[-1]) for name in names},
        {name: float(value) * annual for name, value in window.std(ddof=1).items()},
        {name: math.sqrt(float(value)) * annual for name, value in ewma_variance.items()},
        betas, math.sqrt(float(book_ewma)) * annual, math.sqrt(book_long) * annual,
    )


def pricing_volatility(state, name, pricing):
    """Option-pricing sigma. Risk estimates choosing protection are kept separate."""
    if pricing["source"] == "trailing":
        sigma = state.trailing_vol[name]
    elif pricing["source"] == "reactive":
        sigma = max(state.trailing_vol[name], state.ewma_vol[name])
    else:
        raise ValueError(f"Unknown pricing source: {pricing['source']}")
    return sigma * pricing["multiplier"]


# --------------------------------------------------------------------------- book and policies

def build_book(spots, weights, capital, scale=1.0):
    """Signed whole shares from decision closes, truncated toward zero."""
    return {name: float(math.trunc(scale * weight * capital / spots[name])) for name, weight in weights.items()}


def book_beta_dollars(book, state):
    """Signed XLF-equivalent dollars of the book at the decision close."""
    return sum(shares * state.spots[name] * state.betas[name] for name, shares in book.items())


@dataclass(frozen=True)
class Instruction:
    label: str
    family: str
    core_holdings: dict
    etf_holdings: dict
    positions: tuple
    target_coverage: float
    window_budget: float
    full_coverage_premium: float
    risk_state_elevated: bool | None = None

    @property
    def equity_holdings(self):
        return {**self.core_holdings, **self.etf_holdings}


def _coverage(full_premium, budget):
    """Fraction of full coverage affordable. A net credit needs no budget."""
    return 1.0 if full_premium <= budget else budget / full_premium


def _unit_price(spot, strike, sessions, sigma, kind, settings):
    return float(bs_price(spot, strike, sessions / settings.sessions_per_year, settings.rate, sigma, kind))


def _sized_legs(label, exposures, legs, budget, state, window, settings):
    """Size one common coverage fraction across names, then round contracts down.

    ``exposures`` maps underlying to the positive units protected at full coverage.
    ``legs`` lists (kind, moneyness, sign), where sign +1 buys and -1 writes.
    Rounding down means coverage never exceeds its target.
    """
    plans, full_premium = [], 0.0
    for name, units in exposures.items():
        sigma = pricing_volatility(state, name, settings.pricing)
        for kind, moneyness, sign in legs:
            strike = moneyness * state.spots[name]
            unit = _unit_price(state.spots[name], strike, window.sessions, sigma, kind, settings)
            full_premium += sign * units * unit
            plans.append((name, units, kind, moneyness, sign, strike, sigma))
    coverage = _coverage(full_premium, budget)
    positions = []
    for name, units, kind, moneyness, sign, strike, sigma in plans:
        contracts = math.floor(coverage * units / settings.multiplier + 1e-9)
        if contracts:
            positions.append(OptionPosition(
                f"{label}:{name}:{kind}:{moneyness:.2f}", name, kind, strike, window.end,
                float(sign * contracts), sigma, settings.multiplier))
    return tuple(positions), coverage, full_premium


def build_instruction(candidate, state, window, weights, settings):
    """Translate one frozen candidate into holdings and signed option positions."""
    family, label = candidate["family"], candidate["label"]
    book = build_book(state.spots, weights, settings.capital)
    longs = {name: shares for name, shares in book.items() if shares > 0}
    shorts = {name: -shares for name, shares in book.items() if shares < 0}
    window_fraction = window.sessions / settings.sessions_per_year
    budget = candidate.get("annual_budget", 0.0) * settings.capital * window_fraction
    common = dict(label=label, family=family, core_holdings=book, etf_holdings={}, positions=(),
                  target_coverage=0.0, window_budget=0.0, full_coverage_premium=0.0)
    if family == "unhedged":
        return Instruction(**common)
    if family == "reduced_equity":
        reduced = build_book(state.spots, weights, settings.capital, candidate["scale"])
        return Instruction(**{**common, "core_holdings": reduced})
    if family == "etf_hedge":
        hedge_dollars = candidate["hedge_ratio"] * book_beta_dollars(book, state)
        shares = -float(math.trunc(hedge_dollars / state.spots[settings.etf]))
        return Instruction(**{**common, "etf_holdings": {settings.etf: shares} if shares else {},
                              "target_coverage": candidate["hedge_ratio"]})
    elevated = None
    if family == "long_puts":
        exposures, legs = longs, [("put", candidate["moneyness"], 1)]
    elif family == "short_calls":
        exposures, legs = shorts, [("call", candidate["moneyness"], 1)]
    elif family == "sector_puts":
        # Sized on net beta dollars. It cannot protect short-side upside losses.
        beta_units = max(book_beta_dollars(book, state), 0.0) / state.spots[settings.etf]
        exposures, legs = {settings.etf: beta_units}, [("put", candidate["moneyness"], 1)]
    elif family == "structures":
        exposures = longs
        legs = [("put", candidate["long_put"], 1)]
        if candidate["structure"] == "put_spread":
            legs.append(("put", candidate["short_put"], -1))
        elif candidate["structure"] == "collar":
            legs.append(("call", candidate["short_call"], -1))
        else:
            raise ValueError(f"Unknown structure: {candidate['structure']}")
    elif family == "risk_informed":
        elevated = state.risk_ratio >= candidate["threshold"]
        budget = budget if elevated else budget * candidate["low_state_budget_fraction"]
        exposures, legs = longs, [("put", candidate["moneyness"], 1)]
    else:
        raise ValueError(f"Unknown policy family: {family}")
    positions, coverage, full_premium = _sized_legs(label, exposures, legs, budget, state, window, settings)
    return Instruction(**{**common, "positions": positions, "target_coverage": coverage, "window_budget": budget,
                          "full_coverage_premium": full_premium, "risk_state_elevated": elevated})


def run_window(prices, window, instruction, settings):
    """One separate account through replay. Protection is never delta-neutralized."""
    frame = prices.loc[window.start:window.end]
    if len(frame) != window.sessions + 1:
        raise ValueError(f"Window {window.key} does not have its declared sessions.")
    return replay(frame, instruction.positions, equity_holdings=instruction.equity_holdings,
                  hedge_options=False, hedge_every=None, cost_bps=settings.cost_bps, rate=settings.rate,
                  initial_capital=settings.capital, sessions_per_year=settings.sessions_per_year,
                  liquidate_at_end=True, as_of=window.start, session_calendar=frame.index, data_label=LABEL)


# --------------------------------------------------------------------------- window outputs

def window_record(result, instruction, window, state, weights, settings):
    """Window-level P&L, separated premiums, financing and exposure attribution."""
    ledger, holdings, options = result.ledger, result.holdings, result.option_ledger
    capital = result.initial_capital
    flows = result.trades.groupby(level="underlying")["stock_cashflow"].sum()
    side = lambda names: float(flows.reindex(list(names), fill_value=0.0).sum())
    long_names = [name for name, weight in weights.items() if weight > 0]
    short_names = [name for name, weight in weights.items() if weight < 0]
    opening = options["opening_cashflow"] if len(options) else pd.Series(dtype=float)
    settling = options["settlement_cashflow"] if len(options) else pd.Series(dtype=float)
    first = holdings.xs(window.start, level="date")
    last_nav = ledger["nav"].to_numpy()
    peak = np.maximum.accumulate(np.r_[capital, last_nav])[1:]
    positions = first.loc[first.index != settings.etf]
    notional = positions["core_shares"] * positions["spot"]
    etf_notional = float((first["core_shares"] * first["spot"]).get(settings.etf, 0.0))
    delta_dollars = float((first["portfolio_delta_shares"] * first["spot"]).sum())
    short_mark = (holdings["core_shares"].clip(upper=0) * holdings["spot"]).groupby(level="date").sum()
    funding = (-(ledger["cash"] + short_mark.reindex(ledger.index))).clip(lower=0)
    book_at_decision = {name: float(shares) for name, shares in instruction.core_holdings.items()}
    beta_dollars = book_beta_dollars(book_at_decision, state)
    etf_shares = instruction.etf_holdings.get(settings.etf, 0.0)
    pct = 100.0 / capital
    premium_paid = abs(float(opening.clip(upper=0).sum()))
    premium_received = float(opening.clip(lower=0).sum())
    settlement_received = float(settling.clip(lower=0).sum())
    settlement_paid = abs(float(settling.clip(upper=0).sum()))
    return dict(
        split=window.split, window=window.index, key=window.key, label=instruction.label,
        family=instruction.family, decision_date=window.decision_date.date().isoformat(),
        start=window.start.date().isoformat(), end=window.end.date().isoformat(), sessions=window.sessions,
        initial_capital=capital, terminal_nav=result.terminal_nav, pnl=result.terminal_pnl,
        pnl_pct=result.terminal_pnl * pct,
        max_drawdown_pct=float((peak - last_nav).max()) * pct,
        long_equity_pnl=side(long_names), short_equity_pnl=side(short_names), etf_pnl=side([settings.etf]),
        premium_paid=premium_paid, premium_received=premium_received,
        settlement_received=settlement_received, settlement_paid=settlement_paid,
        option_pnl=premium_received - premium_paid + settlement_received - settlement_paid,
        interest=float(ledger["interest"].sum()), stock_cost=result.total_stock_cost,
        stock_turnover=float(ledger["stock_turnover"].sum()),
        peak_borrowing=result.peak_borrowing, minimum_cash=float(ledger["cash"].min()),
        peak_funding_ex_short_proceeds=float(funding.max()),
        gross_exposure_pct=float(notional.abs().sum()) * pct, net_exposure_pct=float(notional.sum()) * pct,
        etf_exposure_pct=etf_notional * pct, delta_adjusted_net_pct=delta_dollars * pct,
        beta_net_pct=(beta_dollars + etf_shares * state.spots[settings.etf]) * pct,
        target_coverage=instruction.target_coverage, window_budget=instruction.window_budget,
        full_coverage_premium=instruction.full_coverage_premium, option_count=len(instruction.positions),
        risk_ratio=state.risk_ratio, risk_state_elevated=instruction.risk_state_elevated,
    )


def closed_form_price(spot, strike, years, rate, sigma, kind):
    """Black-Scholes from math.erf, deliberately not the library used by replay."""
    root = sigma * math.sqrt(years)
    d1 = (math.log(spot / strike) + (rate + sigma * sigma / 2) * years) / root
    cdf = lambda value: 0.5 * (1 + math.erf(value / math.sqrt(2)))
    discounted = strike * math.exp(-rate * years)
    if kind == "call":
        return spot * cdf(d1) - discounted * cdf(d1 - root)
    return discounted * cdf(root - d1) - spot * cdf(-d1)


def verify_window(result, instruction, prices, window, record, settings):
    """Rebuild the account from raw records, independently of the ledger totals."""
    ledger = result.ledger
    dates = ledger.index
    trades = result.trades.groupby(level="date")[["stock_cashflow", "transaction_cost"]].sum()
    trades = trades.reindex(dates, fill_value=0.0).astype(float)
    if len(result.option_ledger):
        options = result.option_ledger.groupby(level="date")[["opening_cashflow", "settlement_cashflow"]].sum()
        options = options.reindex(dates, fill_value=0.0).astype(float)
    else:
        options = pd.DataFrame(0.0, index=dates, columns=["opening_cashflow", "settlement_cashflow"])
    cash = result.initial_capital + (ledger["interest"] + trades["stock_cashflow"] - trades["transaction_cost"]
                                     + options["opening_cashflow"] + options["settlement_cashflow"]).cumsum()
    terminal = prices.loc[window.end]
    payoff = sum(position.units * max((terminal[position.underlying] - position.strike)
                                      * (1 if position.kind == "call" else -1), 0.0)
                 for position in instruction.positions)
    years = window.sessions / settings.sessions_per_year
    premium = -sum(position.units * closed_form_price(prices.loc[window.start, position.underlying], position.strike,
                                                      years, settings.rate, position.volatility, position.kind)
                   for position in instruction.positions)
    attribution = (record["long_equity_pnl"] + record["short_equity_pnl"] + record["etf_pnl"]
                   + record["option_pnl"] + record["interest"] - record["stock_cost"])
    first = result.holdings.xs(window.start, level="date")["core_shares"]
    held = {name: float(shares) for name, shares in first.items() if shares}
    wanted = {name: shares for name, shares in instruction.equity_holdings.items() if shares}
    tolerance = 1e-6
    return dict(
        cash_from_trade_and_option_records=bool(np.allclose(cash, ledger["cash"], atol=tolerance, rtol=1e-12)),
        nav_identity=bool(np.allclose(ledger["cash"] + ledger["core_equity_value"] + ledger["hedge_stock_value"]
                                      + ledger["option_value"], ledger["nav"], atol=tolerance, rtol=1e-12)),
        expiry_payoff_recomputed=math.isclose(payoff, float(ledger["option_settlement_cashflow"].sum()),
                                              abs_tol=tolerance),
        opening_premium_matches_units=math.isclose(premium, float(ledger["opening_option_cashflow"].sum()),
                                                   abs_tol=tolerance),
        attribution_sums_to_pnl=math.isclose(attribution, record["pnl"], abs_tol=tolerance),
        terminal_flat=bool(ledger.iloc[-1]["option_value"] == 0
                           and result.holdings.xs(window.end, level="date")["net_shares"].eq(0).all()),
        no_delta_neutralization=bool(result.holdings["hedge_shares"].eq(0).all()),
        capital_matches=result.initial_capital == record["initial_capital"],
        holdings_match_instruction=held == wanted,
        decision_precedes_execution=window.decision_date < window.start,
    )


def evaluate_windows(prices, windows, candidates, weights, settings, keep=None):
    """Run candidates over windows. Returns records, checks and optional results."""
    records, checks, kept = [], [], {}
    for window in windows:
        state = estimate_state(prices, window.decision_date, weights, settings)
        for candidate in candidates:
            instruction = build_instruction(candidate, state, window, weights, settings)
            result = run_window(prices, window, instruction, settings)
            record = window_record(result, instruction, window, state, weights, settings)
            records.append(record)
            checks.append(dict(key=window.key, label=candidate["label"],
                               **verify_window(result, instruction, prices, window, record, settings)))
            if keep is not None and keep(window, candidate):
                kept[window.key, candidate["label"]] = (result, instruction, state)
    return pd.DataFrame(records), pd.DataFrame(checks), kept


# --------------------------------------------------------------------------- summaries

def summarize(records, tail_probability, baseline=BASELINE):
    """Per-split window statistics. No chained NAV, CAGR or full-period drawdown."""
    rows = []
    for split, frame in records.groupby("split", sort=False):
        base = frame.loc[frame["label"].eq(baseline)].set_index("key")["pnl"]
        down, up = base.index[base < 0], base.index[base > 0]
        for label, group in frame.groupby("label", sort=False):
            group = group.set_index("key").reindex(base.index)
            pnl = group["pnl_pct"].to_numpy()
            years = group["sessions"].sum() / 252
            capital = group["initial_capital"].iloc[0]
            annual = lambda column: 100 * group[column].sum() / years / capital
            n = len(group)
            rows.append(dict(
                split=split, label=label, family=group["family"].iloc[0], n_windows=n,
                tail_windows=math.ceil(tail_probability * n), adverse_windows=len(down), up_windows=len(up),
                mean_pnl_pct=float(pnl.mean()), median_pnl_pct=float(np.median(pnl)),
                std_pnl_pct=float(pnl.std(ddof=1)) if n > 1 else float("nan"), worst_pnl_pct=float(pnl.min()),
                best_pnl_pct=float(pnl.max()),
                es_loss_pct=float(expected_shortfall(pnl, tail_probability)) if n > 1 else float("nan"),
                mean_max_drawdown_pct=float(group["max_drawdown_pct"].mean()),
                worst_max_drawdown_pct=float(group["max_drawdown_pct"].max()),
                adverse_mean_pnl_pct=float(group.loc[down, "pnl_pct"].mean()) if len(down) else float("nan"),
                downside_capture=(float(group.loc[down, "pnl"].sum() / base.loc[down].sum())
                                  if len(down) else float("nan")),
                upside_retained=(float(group.loc[up, "pnl"].sum() / base.loc[up].sum())
                                 if len(up) else float("nan")),
                annual_premium_paid_pct=annual("premium_paid"), annual_premium_received_pct=annual("premium_received"),
                annual_net_premium_pct=annual("premium_paid") - annual("premium_received"),
                annual_budget_pct=annual("window_budget"),
                worst_window_budget_multiple=_budget_multiple(group),
                annual_settlement_net_pct=annual("settlement_received") - annual("settlement_paid"),
                annual_stock_cost_pct=annual("stock_cost"), annual_interest_pct=annual("interest"),
                peak_borrowing_pct=100 * float(group["peak_borrowing"].max()) / capital,
                peak_funding_ex_short_proceeds_pct=100 * float(group["peak_funding_ex_short_proceeds"].max()) / capital,
                mean_target_coverage=float(group["target_coverage"].mean()),
                mean_gross_exposure_pct=float(group["gross_exposure_pct"].mean()),
                mean_net_exposure_pct=float(group["net_exposure_pct"].mean()),
                mean_etf_exposure_pct=float(group["etf_exposure_pct"].mean()),
                mean_delta_adjusted_net_pct=float(group["delta_adjusted_net_pct"].mean()),
                mean_beta_net_pct=float(group["beta_net_pct"].mean()),
            ))
    return pd.DataFrame(rows)


def _budget_multiple(group):
    """Largest realized net premium as a multiple of that window's ex-ante budget."""
    funded = group.loc[group["window_budget"] > 0]
    if funded.empty:
        return float("nan")
    return float(((funded["premium_paid"] - funded["premium_received"]) / funded["window_budget"]).max())


def side_protection(records, labels):
    """Protection measured on the side a policy protects, not on the whole book.

    Whole-book tails fall in sector selloffs, when shorts gain, so they cannot show
    what a short-side call does. Sector puts are excluded because they protect no
    single side.
    """
    sides = dict(long_puts=("long", "long_equity_pnl"), risk_informed=("long", "long_equity_pnl"),
                 structures=("long", "long_equity_pnl"), short_calls=("short", "short_equity_pnl"))
    rows = []
    for (split, label), group in records.loc[records["label"].isin(labels)].groupby(["split", "label"], sort=False):
        family = group["family"].iloc[0]
        if family not in sides:
            continue
        side, column = sides[family]
        losing = group.loc[group[column] < 0]
        if losing.empty:
            continue
        protected = losing[column] + losing["option_pnl"]
        scale = 100 / group["initial_capital"].iloc[0]
        rows.append(dict(split=split, label=label, side=side, side_loss_windows=len(losing), windows=len(group),
                         mean_side_loss_pct=float(losing[column].mean()) * scale,
                         mean_with_option_pct=float(protected.mean()) * scale,
                         worst_side_loss_pct=float(losing[column].min()) * scale,
                         worst_with_option_pct=float(protected.min()) * scale,
                         side_loss_capture=float(protected.sum() / losing[column].sum()),
                         windows_option_paid=int((losing["settlement_received"] > 0).sum())))
    return pd.DataFrame(rows)


def select_policies(summary, candidates, config):
    """Choose one candidate per family from validation windows alone."""
    selection = config["selection"]
    if selection["objective"] != "minimize_validation_es":
        raise ValueError("Unknown selection objective.")
    validation = summary.loc[summary["split"].eq("validation")].set_index("label")
    chosen = {}
    for family in selection["selected_families"]:
        labels = [row["label"] for row in candidates if row["family"] == family and row["eligible"]]
        if not labels:
            raise ValueError(f"No eligible candidate for {family}.")
        table = validation.loc[labels, ["es_loss_pct", "annual_net_premium_pct"]].reset_index()
        table = table.sort_values(["es_loss_pct", "annual_net_premium_pct", "label"], kind="mergesort")
        chosen[family] = dict(label=table.iloc[0]["label"], validation_es_loss_pct=float(table.iloc[0]["es_loss_pct"]),
                              candidates_considered=labels)
    return chosen


def _block_indices(rng, count, block_length, draws):
    blocks = math.ceil(count / block_length)
    starts = rng.integers(0, count, size=(draws, blocks))
    return ((starts[:, :, None] + np.arange(block_length)) % count).reshape(draws, -1)[:, :count]


def block_es_difference(policy, baseline, *, tail_probability, block_length, n_bootstrap, seed, confidence=.95):
    """Circular block interval for ES(policy) - ES(baseline); negative favors policy.

    The same chronological blocks resample both series, and each tail is then
    selected separately.
    """
    policy, baseline = np.asarray(policy, float), np.asarray(baseline, float)
    if policy.shape != baseline.shape or policy.ndim != 1 or len(policy) < 2:
        raise ValueError("Paired window series must be aligned one-dimensional vectors.")
    count = len(policy)
    tail = math.ceil(tail_probability * count)
    indices = _block_indices(np.random.default_rng(seed), count, block_length, n_bootstrap)
    es = lambda sample: -np.sort(sample, axis=1)[:, :tail].mean(axis=1)
    draws = es(policy[indices]) - es(baseline[indices])
    alpha = (1 - confidence) / 2
    low, high = np.quantile(draws, [alpha, 1 - alpha])
    estimate = expected_shortfall(policy, tail_probability) - expected_shortfall(baseline, tail_probability)
    return dict(estimate=float(estimate), lower=float(low), upper=float(high), tail_windows=tail)


def paired_uncertainty(records, labels, config, baseline=BASELINE):
    """Dependence-aware paired differences against the unhedged book, by split."""
    settings, tail = config["uncertainty"], config["selection"]["tail_probability"]
    rows = []
    for split, frame in records.groupby("split", sort=False):
        pivot = frame.pivot(index="key", columns="label", values="pnl_pct").sort_index()
        count = len(pivot)
        block = min(settings["block_windows"], count)
        tail_count = math.ceil(tail * count)
        for label in labels:
            if label == baseline or label not in pivot or count < 2:
                continue
            difference = (pivot[label] - pivot[baseline]).to_numpy()
            ex_best = float(np.delete(difference, difference.argmax()).mean())
            mean = moving_block_mean_interval(difference, block_length=block,
                                              n_bootstrap=settings["n_bootstrap"], seed=settings["seed"],
                                              confidence=settings["confidence"])
            es = block_es_difference(pivot[label].to_numpy(), pivot[baseline].to_numpy(), tail_probability=tail,
                                     block_length=block, n_bootstrap=settings["n_bootstrap"], seed=settings["seed"],
                                     confidence=settings["confidence"])
            sparse = count < settings["sparse_window_count"] or tail_count < settings["sparse_tail_count"]
            rows.append(dict(split=split, label=label, n_windows=count, block_windows=block, tail_windows=tail_count,
                             mean_difference_pct=mean["estimate"], mean_lower_pct=mean["lower"],
                             mean_upper_pct=mean["upper"], mean_ex_best_window_pct=ex_best,
                             best_window_key=pivot.index[int(difference.argmax())],
                             es_difference_pct=es["estimate"],
                             es_lower_pct=es["lower"], es_upper_pct=es["upper"],
                             evidence="exploratory" if sparse else "adequate_count"))
    return pd.DataFrame(rows)


def tail_episodes(records, tail_probability, baseline=BASELINE):
    """Count baseline tail windows and merge adjacent ones into shared episodes."""
    rows = []
    for split, frame in records.loc[records["label"].eq(baseline)].groupby("split", sort=False):
        frame = frame.sort_values("window")
        count = math.ceil(tail_probability * len(frame))
        tail = frame.nsmallest(count, "pnl").sort_values("window")
        episode = (tail["window"].diff().fillna(1) != 1).cumsum()
        for number, group in tail.groupby(episode):
            rows.append(dict(split=split, episode=int(number) + 1, windows=len(group),
                             start=group["start"].iloc[0], end=group["end"].iloc[-1],
                             worst_pnl_pct=float(group["pnl_pct"].min())))
    return pd.DataFrame(rows)


def sector_basis(records, sector_label, name_label, baseline=BASELINE):
    """Show how much of each adverse book loss a sector option actually offset."""
    frames = {label: records.loc[records["label"].eq(label)].set_index("key") for label in (baseline, sector_label, name_label)}
    base = frames[baseline]
    table = pd.DataFrame(dict(
        split=base["split"], start=base["start"], end=base["end"], book_pnl_pct=base["pnl_pct"],
        long_equity_pnl_pct=100 * base["long_equity_pnl"] / base["initial_capital"],
        short_equity_pnl_pct=100 * base["short_equity_pnl"] / base["initial_capital"],
        sector_option_pnl_pct=100 * frames[sector_label]["option_pnl"] / base["initial_capital"],
        name_option_pnl_pct=100 * frames[name_label]["option_pnl"] / base["initial_capital"],
    ))
    return table.reset_index()


# --------------------------------------------------------------------------- hashes

def canonical_hash(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()


def file_hash(path):
    return sha256(Path(path).read_bytes()).hexdigest()

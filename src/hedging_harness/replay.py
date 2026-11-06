"""Auditable European model-contract accounting on dated stock observations.

This module does not consume historical option quotes, model American exercise,
account for dividends/corporate actions, or claim executable listed-option fills.
The supplied daily index declares the trading-session calendar. Option maturity
and financing use one session per row and ``sessions_per_year`` sessions per year.
"""
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from pathlib import Path
from typing import Mapping, Sequence

import numpy as np
import pandas as pd

from BlackScholes_Functions.BlackScholes_D1D2_Price_Payoff_Greeks import bs_greeks, bs_payoff, bs_price


def _session_date(value, label):
    try:
        result = pd.Timestamp(value)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{label} must be a valid daily session date.") from error
    if pd.isna(result) or result.tzinfo is not None or result != result.normalize():
        raise ValueError(f"{label} must be a timezone-naive midnight session date.")
    return result


@dataclass(frozen=True)
class OptionPosition:
    """Signed European model-option position, opened at the first observation.

    Positive quantity means purchased options and negative quantity means written
    options. ``quantity * multiplier`` gives signed share-equivalent units.
    An exchange-style multiplier may be supplied, but exchange conventions and
    historical option quotes are not inferred from an underlying ticker.
    """

    instrument_id: str
    underlying: str
    kind: str
    strike: float
    expiry: pd.Timestamp | str
    quantity: float
    volatility: float
    multiplier: float = 1.0

    def __post_init__(self):
        for field in ("instrument_id", "underlying"):
            value = getattr(self, field)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{field} must be a nonempty string.")
        if self.kind not in {"call", "put"}:
            raise ValueError("kind must be 'call' or 'put'.")
        for field in ("strike", "volatility", "multiplier"):
            value = getattr(self, field)
            if isinstance(value, bool) or not np.isfinite(value) or value <= 0:
                raise ValueError(f"{field} must be finite and positive.")
        if isinstance(self.quantity, bool) or not np.isfinite(self.quantity) or self.quantity == 0:
            raise ValueError("quantity must be finite and nonzero.")
        object.__setattr__(self, "expiry", _session_date(self.expiry, "expiry"))

    @property
    def units(self):
        return self.quantity * self.multiplier


@dataclass
class ReplayResult:
    ledger: pd.DataFrame
    trades: pd.DataFrame
    holdings: pd.DataFrame
    option_ledger: pd.DataFrame
    positions: tuple[OptionPosition, ...]
    initial_capital: float
    provenance: dict

    @property
    def terminal_nav(self):
        return float(self.ledger.iloc[-1]["nav"])

    @property
    def terminal_pnl(self):
        return self.terminal_nav - self.initial_capital

    @property
    def peak_borrowing(self):
        return float(self.ledger["peak_borrowing"].max())

    @property
    def total_stock_cost(self):
        return float(self.ledger["transaction_cost"].sum())


def replay(prices: pd.DataFrame, positions: Sequence[OptionPosition], *,
           equity_holdings: Mapping[str, float] | None = None,
           hedge_options: bool = False, hedge_every: int | None = 1,
           cost_bps: float = 0.0, rate: float = 0.0,
           initial_capital: float | None = None, sessions_per_year: int = 252,
           liquidate_at_end: bool = True, as_of=None, session_calendar=None,
           data_label: str = "Caller-supplied underlying prices"):
    """Replay model contracts against a declared daily underlying-price calendar.

    All options open at model prices on the first session and cash-settle on their
    explicit expiry sessions, which must occur in ``prices.index``. No option is
    opened using future volatility estimates: each supplied volatility is fixed.
    Its estimation cutoff remains the caller's responsibility and is recorded via
    the chosen inputs. The model does not infer that a supplied volatility was
    available historically.

    Core equity is purchased at inception, held unchanged, and optionally sold at
    the final observation. Option hedge shares are a separate attribution sleeve.
    Their trades are netted with core-equity trades by underlying for execution and
    proportional stock costs. Setting hedge_options=False preserves an equity-plus-
    protective-put overlay; it does not neutralize the put's delta automatically.

    Default initial capital equals gross long core-equity inception value. Pass an
    explicit common capital across strategy comparisons. Options/hedges draw on the
    cash account, which may borrow/lend at the same constant rate. NAV includes the
    signed model-option value, and P&L is NAV minus initial capital. Margin, option
    spreads, borrow fees, dividends and American exercise are not included.

    Stock hedge decisions observe the current spot and remaining session count.
    Expiry forces a hedge reset for affected underlyings even between scheduled
    rebalances. Peak borrowing checks cash after interest and after the combined
    date's flows; it is not an intraday execution/margin stress measure.
    """
    if not isinstance(prices, pd.DataFrame) or not isinstance(prices.index, pd.DatetimeIndex):
        raise ValueError("prices must be a DataFrame with a DatetimeIndex.")
    if len(prices) < 2 or prices.index.hasnans or not prices.index.is_unique or not prices.index.is_monotonic_increasing:
        raise ValueError("Provide at least two unique, increasing, nonmissing session dates.")
    for date in prices.index:
        _session_date(date, "price index")
    if prices.columns.has_duplicates or any(not isinstance(name, str) or not name.strip() for name in prices.columns):
        raise ValueError("Price columns must have unique nonempty underlying identifiers.")
    if as_of is not None and _session_date(as_of, "as_of") != prices.index[0]:
        raise ValueError("as_of must equal the first replay session; future observations cannot define inception.")
    if session_calendar is not None:
        calendar = pd.DatetimeIndex(session_calendar)
        if not calendar.equals(prices.index):
            raise ValueError("Price observations do not match the supplied full session calendar.")
    try:
        numeric_prices = prices.astype(float)
    except (ValueError, TypeError) as error:
        raise ValueError("All supplied prices must be numeric.") from error
    if not np.isfinite(numeric_prices.to_numpy()).all() or (numeric_prices.to_numpy() <= 0).any():
        raise ValueError("Prices must be finite, strictly positive and contain no missing observations.")
    if not isinstance(sessions_per_year, int) or isinstance(sessions_per_year, bool) or sessions_per_year < 1:
        raise ValueError("sessions_per_year must be a positive integer.")
    if not isinstance(hedge_options, bool) or not isinstance(liquidate_at_end, bool):
        raise ValueError("hedge_options and liquidate_at_end must be booleans.")
    if hedge_every is not None and (not isinstance(hedge_every, int) or isinstance(hedge_every, bool) or hedge_every < 1):
        raise ValueError("hedge_every must be a positive integer or None.")
    if not np.isfinite(rate) or not np.isfinite(cost_bps) or cost_bps < 0:
        raise ValueError("rate must be finite and cost_bps finite and nonnegative.")
    if not isinstance(data_label, str) or not data_label.strip():
        raise ValueError("data_label must be a nonempty string.")
    positions = tuple(positions)
    if any(not isinstance(position, OptionPosition) for position in positions):
        raise TypeError("positions must contain OptionPosition objects.")
    ids = [position.instrument_id for position in positions]
    if len(set(ids)) != len(ids):
        raise ValueError("Each option position needs a unique instrument_id.")
    core = dict(equity_holdings or {})
    if any(not isinstance(name, str) or not np.isfinite(shares) for name, shares in core.items()):
        raise ValueError("Equity holdings must map identifiers to finite signed share quantities.")
    required_names = set(core) | {position.underlying for position in positions}
    if not required_names or not required_names.issubset(prices.columns):
        raise ValueError("Every held underlying must have a supplied price column.")
    expiry_steps = {}
    for position in positions:
        if position.expiry <= prices.index[0] or position.expiry not in prices.index:
            raise ValueError("Every expiry must be a supplied session strictly after inception.")
        expiry_steps[position.instrument_id] = prices.index.get_loc(position.expiry)
    names = tuple(name for name in prices.columns if name in required_names)
    numeric_prices = numeric_prices.loc[:, list(names)]
    equity_target = np.array([core.get(name, 0.0) for name in names], dtype=float)
    if initial_capital is None:
        initial_capital = float(np.maximum(equity_target, 0) @ numeric_prices.iloc[0].to_numpy())
    if not np.isfinite(initial_capital) or initial_capital < 0:
        raise ValueError("initial_capital must be finite and nonnegative.")
    initial_capital = float(initial_capital)
    cash = initial_capital
    core_shares = np.zeros(len(names))
    hedge_shares = np.zeros(len(names))
    name_positions = {name: index for index, name in enumerate(names)}
    peak_borrowing = 0.0
    ledger_rows, trade_rows, holding_rows, option_rows = [], [], [], []
    growth = np.expm1(rate / sessions_per_year)

    for step, (date, observed_prices) in enumerate(numeric_prices.iterrows()):
        spot = observed_prices.to_numpy()
        interest = cash * growth if step else 0.0
        cash += interest
        peak_borrowing = max(peak_borrowing, -cash, 0.0)
        opening_option_cashflow = 0.0
        option_settlement_cashflow = 0.0
        option_value = 0.0
        option_delta = np.zeros(len(names))
        expiring_names = set()
        for position in positions:
            asset = name_positions[position.underlying]
            remaining_sessions = expiry_steps[position.instrument_id] - step
            units = position.units
            opening_flow, settlement_flow, signed_value, signed_delta = 0., 0., 0., 0.
            if remaining_sessions > 0:
                tau = remaining_sessions / sessions_per_year
                price = float(bs_price(spot[asset], position.strike, tau, rate, position.volatility, position.kind))
                delta = float(bs_greeks(spot[asset], position.strike, tau, rate, position.volatility, position.kind)["delta"])
                signed_value = units * price
                signed_delta = units * delta
                if step == 0:
                    opening_flow = -signed_value
                    opening_option_cashflow += opening_flow
                event = "open" if step == 0 else "mark"
            elif remaining_sessions == 0:
                settlement_flow = units * float(bs_payoff(spot[asset], position.strike, position.kind))
                option_settlement_cashflow += settlement_flow
                expiring_names.add(position.underlying)
                event = "settle"
            else:
                event = "expired"
            option_value += signed_value
            option_delta[asset] += signed_delta
            option_rows.append(dict(
                date=date, instrument_id=position.instrument_id, underlying=position.underlying,
                kind=position.kind, expiry=position.expiry, signed_units=units,
                remaining_sessions=max(remaining_sessions, 0), event=event,
                spot=spot[asset], model_value=signed_value, option_delta_shares=signed_delta,
                opening_cashflow=opening_flow, settlement_cashflow=settlement_flow,
            ))

        target_core = equity_target.copy()
        if liquidate_at_end and step == len(numeric_prices) - 1:
            target_core[:] = 0
        target_hedge = hedge_shares.copy()
        for asset, name in enumerate(names):
            scheduled = step == 0 or (hedge_every is not None and step % hedge_every == 0)
            due = scheduled or name in expiring_names
            if not hedge_options:
                target_hedge[asset] = 0.0
            elif due:
                target_hedge[asset] = -option_delta[asset]
        if liquidate_at_end and step == len(numeric_prices) - 1:
            target_hedge[:] = 0
        core_trade = target_core - core_shares
        hedge_trade = target_hedge - hedge_shares
        net_trade = core_trade + hedge_trade
        core_stock_cashflow = float(-core_trade @ spot)
        hedge_stock_cashflow = float(-hedge_trade @ spot)
        traded_dollars = np.abs(net_trade) * spot
        transaction_cost = float(traded_dollars.sum() * cost_bps / 10000)
        cash += (opening_option_cashflow + option_settlement_cashflow
                 + core_stock_cashflow + hedge_stock_cashflow - transaction_cost)
        core_shares, hedge_shares = target_core, target_hedge
        peak_borrowing = max(peak_borrowing, -cash, 0.0)
        core_equity_value = float(core_shares @ spot)
        hedge_stock_value = float(hedge_shares @ spot)
        nav = cash + core_equity_value + hedge_stock_value + option_value
        previous_nav = initial_capital if not ledger_rows else ledger_rows[-1]["nav"]
        ledger_rows.append(dict(
            date=date, step=step, interest=interest,
            opening_option_cashflow=opening_option_cashflow,
            option_settlement_cashflow=option_settlement_cashflow,
            core_stock_cashflow=core_stock_cashflow, hedge_stock_cashflow=hedge_stock_cashflow,
            stock_cashflow=core_stock_cashflow + hedge_stock_cashflow,
            transaction_cost=transaction_cost, stock_turnover=float(traded_dollars.sum()),
            cash=cash, core_equity_value=core_equity_value, hedge_stock_value=hedge_stock_value,
            option_value=option_value, nav=nav, daily_pnl=nav - previous_nav,
            cumulative_pnl=nav - initial_capital,
            borrowing=max(-cash, 0.0), peak_borrowing=peak_borrowing,
        ))
        for asset, name in enumerate(names):
            holding_rows.append(dict(
                date=date, underlying=name, spot=spot[asset],
                core_shares=core_shares[asset], hedge_shares=hedge_shares[asset],
                net_shares=core_shares[asset] + hedge_shares[asset],
                option_delta_shares=option_delta[asset],
                portfolio_delta_shares=core_shares[asset] + hedge_shares[asset] + option_delta[asset],
            ))
            if core_trade[asset] != 0 or hedge_trade[asset] != 0:
                trade_rows.append(dict(
                    date=date, underlying=name, spot=spot[asset],
                    core_trade_shares=core_trade[asset], hedge_trade_shares=hedge_trade[asset],
                    executed_net_shares=net_trade[asset],
                    stock_cashflow=-net_trade[asset] * spot[asset],
                    transaction_cost=traded_dollars[asset] * cost_bps / 10000,
                ))

    ledger = pd.DataFrame(ledger_rows).set_index("date")
    holdings = pd.DataFrame(holding_rows).set_index(["date", "underlying"])
    trade_columns = ["date", "underlying", "spot", "core_trade_shares", "hedge_trade_shares",
                     "executed_net_shares", "stock_cashflow", "transaction_cost"]
    trades = pd.DataFrame(trade_rows, columns=trade_columns).set_index(["date", "underlying"])
    option_columns = ["date", "instrument_id", "underlying", "kind", "expiry", "signed_units",
                      "remaining_sessions", "event", "spot", "model_value", "option_delta_shares",
                      "opening_cashflow", "settlement_cashflow"]
    option_ledger = pd.DataFrame(option_rows, columns=option_columns).set_index(["date", "instrument_id"])
    changes = (ledger.interest + ledger.opening_option_cashflow + ledger.option_settlement_cashflow
               + ledger.stock_cashflow - ledger.transaction_cost)
    np.testing.assert_allclose(ledger.cash, initial_capital + changes.cumsum(), atol=1e-8, rtol=1e-12)
    np.testing.assert_allclose(ledger.daily_pnl.sum(), ledger.iloc[-1].cumulative_pnl, atol=1e-8, rtol=1e-12)
    price_digest = sha256()
    price_digest.update(json.dumps({"names": names, "dates": [date.isoformat() for date in numeric_prices.index]}).encode())
    price_digest.update(np.ascontiguousarray(numeric_prices.to_numpy(), dtype="<f8").tobytes())
    model_file = Path(__file__).resolve().parents[2] / "src" / "BlackScholes_Functions" / "BlackScholes_D1D2_Price_Payoff_Greeks.py"
    provenance = dict(
        model="European fixed-volatility model contracts on supplied underlying observations",
        data_label=data_label, as_of=numeric_prices.index[0].isoformat(),
        terminal_date=numeric_prices.index[-1].isoformat(),
        session_count=len(numeric_prices), sessions_per_year=sessions_per_year,
        time_convention="one trading session per supplied row; rates/volatilities annualized",
        initial_capital=initial_capital,
        capital_convention="gross long core-equity inception value unless initial_capital is supplied",
        rate=float(rate), cost_bps=float(cost_bps), hedge_options=hedge_options,
        hedge_every=hedge_every, liquidate_at_end=liquidate_at_end,
        equity_holdings={name: float(shares) for name, shares in core.items()},
        option_positions=[{**asdict(position), "expiry": position.expiry.isoformat()} for position in positions],
        prices_sha256=price_digest.hexdigest(),
        source_sha256={str(file.relative_to(Path(__file__).resolve().parents[2])): sha256(file.read_bytes()).hexdigest()
                       for file in (Path(__file__), model_file)},
        limitations=["No historical option quotes or executable listed-option claim",
                     "No American exercise/assignment", "No dividends or corporate-action processing",
                     "No option spreads, margin, stock borrow charges or asymmetric funding",
                     "Fixed volatility inputs require separate availability/cutoff verification"],
    )
    return ReplayResult(ledger, trades, holdings, option_ledger, positions, initial_capital, provenance)

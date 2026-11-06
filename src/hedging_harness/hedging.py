"""Hedging interfaces; arithmetic preserved from the frozen core."""
import numpy as np
import pandas as pd
import json
from hashlib import sha256
from .domain import HedgeResult, _vol_vector
from .policies import HedgePolicy
from .legacy import call_price, call_delta


def hedge(book, paths, hedge_every=1, cost_bps=0.0, hedge_vols=None, audit_path=None,
          policy=None, scenario_label=None):
    """Short calls hedged with stock. All quantities are share-equivalent.

    hedge_every=None means initial hedge only. Costs are one-way bps of traded
    stock notional, charged at entry, each rebalance, and terminal liquidation.
    Separate per-name cash attribution sums exactly to one shared cash account
    because all borrowing/lending uses the same linear constant rate.

    Each step: accrue prior cash -> observe spot -> trade or settle -> mark.
    Opening premium and interim accounting marks use book.pricing_vols; changing
    hedge_vols never reprices the opening trade. Interim marks are model marks,
    not a forecast or a market-observed implied-volatility surface.

    An explicit HedgePolicy selects the rebalancing rule instead of hedge_every.
    Band thresholds are normalized by option units and use only current state.
    The computed scenario_id fingerprints actual paths and asset order; an
    optional scenario_label describes the experiment without overriding identity.
    Peak borrowing includes cash just after interest and after the day's trades.
    """
    p = np.asarray(paths, dtype=float)
    n = len(book.names)
    if (p.ndim != 3 or p.shape[1:] != (book.steps + 1, n) or p.shape[0] < 1
            or not np.isfinite(p).all() or (p <= 0).any()
            or not np.allclose(p[:, 0, :], book.spots, rtol=0, atol=1e-10)):
        raise ValueError("Paths must be positive, finite, match the book grid, and start at book.spots.")
    if hedge_every is not None and (not isinstance(hedge_every, int) or isinstance(hedge_every, bool) or hedge_every < 1):
        raise ValueError("hedge_every must be a positive integer or None.")
    if not np.isfinite(cost_bps) or cost_bps < 0:
        raise ValueError("cost_bps must be finite and nonnegative.")
    if audit_path is not None and (not isinstance(audit_path, int) or not 0 <= audit_path < len(p)):
        raise ValueError("audit_path must identify a path in this array.")
    if policy is not None and not isinstance(policy, HedgePolicy):
        raise TypeError("policy must be a HedgePolicy or None.")
    if scenario_label is not None and (
            not isinstance(scenario_label, str) or not scenario_label.strip()):
        raise ValueError("scenario_label must be a nonempty string or None.")
    active_policy = policy if policy is not None else HedgePolicy(hedge_every=hedge_every)
    path_digest = sha256()
    path_digest.update(json.dumps({"names": book.names, "shape": p.shape},
                                  separators=(",", ":")).encode())
    path_digest.update(np.ascontiguousarray(p, dtype="<f8").tobytes())
    scenario_id = path_digest.hexdigest()
    hv = _vol_vector(book.pricing_vols if hedge_vols is None else hedge_vols, n)
    k, pv, q = np.asarray(book.strikes), np.asarray(book.pricing_vols), book.units
    shape = (len(p), n)
    cash = np.zeros(shape)
    shares = np.zeros(shape)
    nominal = np.zeros(shape)
    financed = np.zeros(shape)
    turnover = np.zeros(shape)
    counts = np.zeros(shape, dtype=int)
    peak_borrowing = np.zeros(shape)
    peak_portfolio_borrowing = np.zeros(len(p))
    growth = np.exp(book.rate / book.sessions_per_year)
    rows = []
    for step in range(book.steps + 1):
        spot = p[:, step, :]
        interest = cash * (growth - 1) if step else np.zeros(shape)
        cash = cash + interest
        peak_borrowing = np.maximum(peak_borrowing, np.maximum(-cash, 0))
        peak_portfolio_borrowing = np.maximum(
            peak_portfolio_borrowing, np.maximum(-cash.sum(axis=1), 0))
        if step:
            financed *= growth
        before = shares.copy()
        premium = np.zeros(shape)
        settlement = np.zeros(shape)
        tau = (book.steps - step) / book.sessions_per_year
        if step == 0:
            premium[:] = q * call_price(spot, k, book.maturity, book.rate, pv)
            cash += premium
        if step == book.steps:
            target = np.zeros(shape)
            settlement = q * np.maximum(spot - k, 0)
            events = np.full(shape, "settle", dtype=object)
        elif step == 0:
            target = q * call_delta(spot, k, tau, book.rate, hv)
            events = np.full(shape, "open", dtype=object)
        elif (active_policy.kind != "periodic" or
              (active_policy.hedge_every is not None and
               step % active_policy.hedge_every == 0)):
            delta_target = q * call_delta(spot, k, tau, book.rate, hv)
            rebalance = active_policy.rebalance_mask(
                step, tau, book.maturity, delta_target, before, q)
            target = np.where(rebalance, delta_target, before)
            events = np.where(rebalance, "rebalance", "hold")
        else:
            target = shares
            events = np.full(shape, "hold", dtype=object)
        trade = target - before
        traded = np.abs(trade) * spot
        cost = traded * (cost_bps / 10000)
        cash -= trade * spot + cost + settlement
        peak_borrowing = np.maximum(peak_borrowing, np.maximum(-cash, 0))
        peak_portfolio_borrowing = np.maximum(
            peak_portfolio_borrowing, np.maximum(-cash.sum(axis=1), 0))
        shares = target.copy()
        nominal += cost
        financed += cost
        turnover += traded
        counts += np.abs(trade) > 1e-12
        if audit_path is not None:
            a = audit_path
            liability = q * call_price(spot[a], k, tau, book.rate, pv) if step < book.steps else np.zeros(n)
            for j, name in enumerate(book.names):
                rows.append(dict(step=step, name=name, event=events[a,j], spot=spot[a,j],
                    premium_received=premium[a,j], interest=interest[a,j],
                    shares_before=before[a,j], shares_after=shares[a,j], trade_units=trade[a,j],
                    stock_cashflow=-trade[a,j]*spot[a,j], transaction_cost=cost[a,j],
                    payoff_paid=settlement[a,j], cash=cash[a,j],
                    stock_value=shares[a,j]*spot[a,j], option_liability=liability[j],
                    net_value=cash[a,j]+shares[a,j]*spot[a,j]-liability[j],
                    borrowing=max(-cash[a,j], 0), peak_borrowing=peak_borrowing[a,j]))
    return HedgeResult(book.names, cash, nominal, financed, turnover, counts, pd.DataFrame(rows),
                       peak_borrowing=peak_borrowing,
                       peak_portfolio_borrowing=peak_portfolio_borrowing,
                       scenario_id=scenario_id, scenario_label=scenario_label,
                       policy=active_policy)


"""Small reusable mechanics; experiment design and interpretation live in notebooks.

Scope: short European calls, zero dividends, common expiry, constant financing
rate, proportional stock transaction costs, exact correlated GBM under Q.
No market data download, calibration, strategy optimization, or trading API.
"""
from dataclasses import dataclass, asdict
from hashlib import sha256
from pathlib import Path
import json
import platform

import numpy as np
import pandas as pd
import scipy
from scipy.stats import norm

from .legacy import call_price, call_delta, exact_paths, _d1_d2, SOURCES, initial_exposures
from .policies import HedgePolicy


@dataclass(frozen=True)
class Book:
    names: tuple[str, ...]
    spots: tuple[float, ...]
    strikes: tuple[float, ...]
    notionals: tuple[float, ...]
    pricing_vols: tuple[float, ...]
    steps: int = 63
    sessions_per_year: int = 252
    rate: float = 0.04

    def __post_init__(self):
        n = len(self.names)
        if not n or len(set(self.names)) != n or "Portfolio" in self.names:
            raise ValueError("Names must be nonempty, unique and not 'Portfolio'.")
        for field in ("spots", "strikes", "notionals", "pricing_vols"):
            value = np.asarray(getattr(self, field), dtype=float)
            if value.shape != (n,) or not np.isfinite(value).all() or (value <= 0).any():
                raise ValueError(f"{field} must have one finite positive value per name.")
        for field in ("steps", "sessions_per_year"):
            value = getattr(self, field)
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                raise ValueError(f"{field} must be a positive integer.")
        if not np.isfinite(self.rate):
            raise ValueError("rate must be finite.")

    @property
    def maturity(self):
        return self.steps / self.sessions_per_year

    @property
    def units(self):
        """Positive short-call share-equivalent units; fractional units allowed.

        Not exchange contract counts: no 100-share multiplier or lot rounding.
        """
        return np.asarray(self.notionals) / np.asarray(self.spots)


def load_study(path):
    raw = json.loads(Path(path).read_text())
    values = dict(raw["book"])
    for key in ("names", "spots", "strikes", "notionals", "pricing_vols"):
        values[key] = tuple(values[key])
    book = Book(**values)
    _correlation_root(raw["scenario"]["correlation"], len(book.names))
    _vol_vector(raw["scenario"]["path_vols"], len(book.names), positive=False)
    return book, raw


def _vol_vector(values, n, positive=True):
    a = np.asarray(values, dtype=float)
    if a.shape != (n,) or not np.isfinite(a).all() or (a < 0).any() or (positive and (a == 0).any()):
        raise ValueError("Volatilities must match the names and be finite and positive (path vols may be zero).")
    return a


def _correlation_root(correlation, n):
    corr = np.asarray(correlation, dtype=float)
    if (corr.shape != (n, n) or not np.isfinite(corr).all()
            or not np.allclose(corr, corr.T, atol=1e-12, rtol=0)
            or not np.allclose(np.diag(corr), 1, atol=1e-12, rtol=0)):
        raise ValueError("Correlation must be finite, symmetric, with unit diagonal and one row per name.")
    eig, vec = np.linalg.eigh(corr)
    if eig.min() < -1e-10:
        raise ValueError("Correlation must be positive semidefinite.")
    # Symmetric square root also accepts singular, perfectly correlated cases.
    return (vec * np.sqrt(np.maximum(eig, 0))) @ vec.T


def simulate_paths(book, path_vols, correlation, n_paths=5000, seed=20261105):
    """Return (path, date including inception, asset); risk-neutral drift r.

    Reusing seed pairs policies/scenarios through common normal innovations.
    No antithetic averaging: every row remains an individual trading outcome.
    """
    if not isinstance(n_paths, int) or isinstance(n_paths, bool) or n_paths < 2:
        raise ValueError("n_paths must be an integer >= 2.")
    vols = _vol_vector(path_vols, len(book.names), positive=False)
    root = _correlation_root(correlation, len(book.names))
    z = np.random.default_rng(seed).standard_normal((n_paths, book.steps, len(book.names)))
    z = z @ root.T
    return np.stack([
        exact_paths(s, book.rate, v, book.maturity, z[:, :, i])
        for i, (s, v) in enumerate(zip(book.spots, vols))
    ], axis=-1)


@dataclass
class HedgeResult:
    names: tuple[str, ...]
    terminal_pnl: np.ndarray
    nominal_costs: np.ndarray
    financed_costs: np.ndarray
    turnover: np.ndarray
    trade_counts: np.ndarray
    ledger: pd.DataFrame
    peak_borrowing: np.ndarray | None = None
    peak_portfolio_borrowing: np.ndarray | None = None
    scenario_id: str | None = None
    scenario_label: str | None = None
    policy: HedgePolicy | None = None


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


def summarize(result):
    """Dollar metrics. ES95 = negative mean of worst ceil(5%*N) P&Ls.

    It is allowed to be negative if even that tail is profitable. mean_se is
    Monte Carlo uncertainty in the mean, not economic risk or a tail interval.
    Costs are already included in net P&L and must not be subtracted again.
    """
    rows = []
    for j, name in enumerate((*result.names, "Portfolio")):
        total = j == len(result.names)
        take = lambda x: x.sum(axis=1) if total else x[:, j]
        pnl = take(result.terminal_pnl)
        m = len(pnl)
        std = pnl.std(ddof=1) if m > 1 else np.nan
        rows.append(dict(name=name, paths=m, mean_pnl=pnl.mean(), mean_se=std/np.sqrt(m),
            pnl_std=std, rmse=np.sqrt(np.mean(pnl**2)), pnl_p05=np.quantile(pnl,.05),
            loss_es95=-np.sort(pnl)[:max(1,int(np.ceil(.05*m)))].mean(),
            mean_cost=take(result.nominal_costs).mean(),
            mean_financed_cost=take(result.financed_costs).mean(),
            mean_turnover=take(result.turnover).mean(), mean_trades=take(result.trade_counts).mean()))
        borrowing = (result.peak_portfolio_borrowing if total
                     else (None if result.peak_borrowing is None else result.peak_borrowing[:, j]))
        rows[-1].update(
            mean_peak_borrowing=np.nan if borrowing is None else np.mean(borrowing),
            peak_borrowing_p95=np.nan if borrowing is None else np.quantile(borrowing, .95),
            max_peak_borrowing=np.nan if borrowing is None else np.max(borrowing))
    return pd.DataFrame(rows).set_index("name")


def paired_difference(left, right):
    """Compare results sharing actual stock paths and asset order.

    Legacy manually constructed results without fingerprints retain shape/name
    checks; results produced by hedge carry computed fingerprints automatically.
    """
    if left.names != right.names or left.terminal_pnl.shape != right.terminal_pnl.shape:
        raise ValueError("Paired results must have matching names and shape.")
    if (left.scenario_id is not None or right.scenario_id is not None) and left.scenario_id != right.scenario_id:
        raise ValueError("Paired results must have matching scenario IDs (actual paths and asset order).")
    d = (left.terminal_pnl - right.terminal_pnl).sum(axis=1)
    se = d.std(ddof=1) / np.sqrt(len(d)) if len(d)>1 else np.nan
    return {"mean_difference":float(d.mean()), "paired_se":float(se),
            "mc_95_low":float(d.mean()-1.96*se), "mc_95_high":float(d.mean()+1.96*se)}




def provenance(book, scenario, seed, n_paths):
    """Record assumptions, runtime versions and hashes; no market-data claims."""
    files = list(SOURCES) + sorted(Path(__file__).parent.glob("*.py"))
    return dict(book=asdict(book), scenario=scenario, seed=seed, n_paths=n_paths,
        measure="Q; drift equals constant financing rate; no dividends",
        versions=dict(python=platform.python_version(), numpy=np.__version__,
                      scipy=scipy.__version__, pandas=pd.__version__),
        source_sha256={str(p.relative_to(Path(__file__).resolve().parents[1])):sha256(p.read_bytes()).hexdigest() for p in files})

"""Conditional breadth experiments with one master universe and explicit exclusions.

Complete-history/current-survivor conditioning is intentional and disclosed. It is
not point-in-time membership. Calibration itself uses only the declared past cutoff.
"""
from dataclasses import dataclass
from hashlib import sha256
import json

import numpy as np
import pandas as pd

from .core import Book, simulate_paths
from .risk_models import covariance_estimates, moving_block_mean_interval
from .uncertainty import expected_shortfall


CORE_TEN = ("JPM", "PNC", "GS", "BAC", "WFC", "C", "USB", "MS", "SCHW", "BK")
DEFAULT_SIZES = (3, 10, 25, 40)
COMPOSITION_SEEDS = (730711, 730712)


@dataclass
class MasterUniverse:
    prices: pd.DataFrame
    availability_audit: pd.DataFrame
    names: tuple[str, ...]
    excluded_names: tuple[str, ...]


@dataclass
class BreadthCalibration:
    names: tuple[str, ...]
    cutoff: pd.Timestamp
    first_observation: pd.Timestamp
    last_observation: pd.Timestamp
    return_observations: int
    shrinkage: float
    annual_volatilities: pd.Series
    daily_covariance: pd.DataFrame
    correlation: pd.DataFrame
    calibration_data_sha256: str


@dataclass
class MasterPaths:
    names: tuple[str, ...]
    paths: np.ndarray
    correlation: pd.DataFrame
    seed: int
    scenario: str
    scenario_id: str

    def subset(self, names):
        """Take requested named columns from this exact cube, without simulation."""
        names = tuple(names)
        if not names or len(set(names)) != len(names) or not set(names).issubset(self.names):
            raise ValueError("Subset names must be unique, nonempty members of the master universe.")
        positions = {name: index for index, name in enumerate(self.names)}
        return np.take(self.paths, [positions[name] for name in names], axis=2)


def complete_history_master(prices, *, required_core=CORE_TEN):
    """Retain an explicit full-panel audit and disclose each excluded partial name.

    This screen uses the entire supplied availability panel. That is a retrospective
    complete-history condition, not an eligibility rule available at older dates.
    Nothing is forward-filled and no date is dropped to hide unavailable securities.
    """
    if not isinstance(prices, pd.DataFrame) or not isinstance(prices.index, pd.DatetimeIndex):
        raise ValueError("Prices must be a date-indexed DataFrame.")
    if prices.shape[0] < 3 or prices.shape[1] < 1 or prices.index.hasnans or not prices.index.is_unique or not prices.index.is_monotonic_increasing:
        raise ValueError("Require a nonempty panel with unique increasing dates.")
    if not prices.columns.is_unique or any(not isinstance(name, str) or not name for name in prices.columns):
        raise ValueError("Underlying identifiers must be unique nonempty strings.")
    try:
        frame = prices.astype(float)
    except (TypeError, ValueError) as error:
        raise ValueError("Observed prices must be numeric.") from error
    observed = frame.to_numpy()[~frame.isna().to_numpy()]
    if not np.isfinite(observed).all() or (observed <= 0).any():
        raise ValueError("Observed prices must be finite and positive; NaNs are retained as availability gaps.")
    rows=[]
    for name in frame.columns:
        available=frame[name].notna()
        complete=bool(available.all())
        rows.append(dict(
            name=name, observations=int(available.sum()), missing_observations=int((~available).sum()),
            first_observed=None if not available.any() else frame.index[available][0].date().isoformat(),
            last_observed=None if not available.any() else frame.index[available][-1].date().isoformat(),
            included_in_complete_master=complete,
            reason="complete_current_survivor_history" if complete else "excluded_partial_or_missing_history_no_fill",
        ))
    audit=pd.DataFrame(rows).set_index("name")
    complete=tuple(audit.index[audit.included_in_complete_master])
    excluded=tuple(audit.index[~audit.included_in_complete_master])
    required_core=tuple(required_core)
    if not set(required_core).issubset(complete):
        raise ValueError("The required core universe is absent or incomplete; do not silently discard a core name.")
    names=required_core + tuple(name for name in complete if name not in required_core)
    if len(names)<2:
        raise ValueError("Need at least two complete-history names for a joint master universe.")
    return MasterUniverse(frame.loc[:,list(names)].copy(),audit,names,excluded)


def nested_compositions(master_names, *, sizes=DEFAULT_SIZES, seeds=COMPOSITION_SEEDS):
    """Canonical and predeclared seeded nested chains, with no outcome selection."""
    names=tuple(master_names)
    if len(set(names))!=len(names) or len(names)<1:
        raise ValueError("Master names must be unique and nonempty.")
    sizes=tuple(sizes)
    if not sizes or tuple(sorted(set(sizes)))!=sizes or any(isinstance(size,bool) or not isinstance(size,int) or size<1 or size>len(names) for size in sizes):
        raise ValueError("Breadths must be unique increasing valid master subset sizes.")
    seeds=tuple(seeds)
    if len(set(seeds))!=len(seeds) or any(isinstance(seed,bool) or not isinstance(seed,int) or seed<0 for seed in seeds):
        raise ValueError("Composition seeds must be unique nonnegative integers.")
    orders={"canonical":names}
    for seed in seeds:
        orders[f"seed_{seed}"]=tuple(np.random.default_rng(seed).permutation(names))
    return {label:{size:order[:size] for size in sizes} for label,order in orders.items()}


def fit_calibration(prices, *, cutoff="2020-12-31", lookback=252, shrinkage=.20):
    """Past-only fixed diagonal-shrinkage covariance and realized-volatility proxy."""
    if not isinstance(prices,pd.DataFrame) or not isinstance(prices.index,pd.DatetimeIndex):
        raise ValueError("Provide a dated complete-history master price DataFrame.")
    if prices.index.has_duplicates or not prices.index.is_monotonic_increasing or not prices.columns.is_unique:
        raise ValueError("Calibration labels and dates must be unique and increasing.")
    cutoff=pd.Timestamp(cutoff)
    if pd.isna(cutoff) or cutoff.tzinfo is not None:
        raise ValueError("cutoff must be a timezone-naive date.")
    if isinstance(lookback,bool) or not isinstance(lookback,int) or lookback<2:
        raise ValueError("lookback must be an integer of at least two returns.")
    history=prices.loc[prices.index<=cutoff].tail(lookback+1).astype(float)
    if len(history)!=lookback+1 or not np.isfinite(history.to_numpy()).all() or (history.to_numpy()<=0).any():
        raise ValueError("Need complete positive prices for exactly lookback+1 past observations.")
    returns=np.diff(np.log(history.to_numpy()),axis=0)
    covariance=covariance_estimates(returns,shrinkage)["diagonal_shrinkage"]
    daily_vol=np.sqrt(np.diag(covariance))
    correlation=covariance/np.outer(daily_vol,daily_vol)
    correlation=(correlation+correlation.T)/2
    np.fill_diagonal(correlation,1.)
    if np.linalg.eigvalsh(correlation).min() < -1e-10:
        raise ValueError("Shrinkage correlation is not positive semidefinite.")
    names=tuple(prices.columns)
    digest=sha256()
    digest.update(json.dumps({"names":names,"dates":[date.isoformat() for date in history.index]},separators=(",",":")).encode())
    digest.update(np.ascontiguousarray(history.to_numpy(),dtype="<f8").tobytes())
    return BreadthCalibration(
        names,cutoff,history.index[0],history.index[-1],lookback,float(shrinkage),
        pd.Series(daily_vol*np.sqrt(252),index=names,name="annual_volatility"),
        pd.DataFrame(covariance,index=names,columns=names),
        pd.DataFrame(correlation,index=names,columns=names),digest.hexdigest(),
    )


def fixed_notional_book(names, calibration, *, total_notional=300000., steps=63, rate=.04):
    names=tuple(names)
    if not names or len(set(names))!=len(names) or not set(names).issubset(calibration.names):
        raise ValueError("Book names must be unique members of the calibrated master universe.")
    if not np.isfinite(total_notional) or total_notional<=0:
        raise ValueError("Total notional must be finite and positive.")
    return Book(
        names=names,spots=(100.,)*len(names),strikes=(100.,)*len(names),
        notionals=(float(total_notional)/len(names),)*len(names),
        pricing_vols=tuple(calibration.annual_volatilities.loc[list(names)].to_numpy()),
        steps=steps,rate=float(rate),
    )


def simulate_master(calibration, *, n_paths=5000, seed=730701, scenario="calibrated_dependence",
                    stress_mix=.40, steps=63, rate=.04):
    """Generate one full master cube; every breadth/composition takes subsets."""
    if scenario not in {"calibrated_dependence","synthetic_common_shock_stress"}:
        raise ValueError("Unknown dependence scenario.")
    if not np.isfinite(stress_mix) or not 0<=stress_mix<=1:
        raise ValueError("stress_mix must be between zero and one.")
    corr=calibration.correlation.loc[list(calibration.names),list(calibration.names)].to_numpy().copy()
    if scenario=="synthetic_common_shock_stress":
        corr=(1-stress_mix)*corr+stress_mix*np.ones_like(corr)
    correlation=pd.DataFrame(corr,index=calibration.names,columns=calibration.names)
    book=fixed_notional_book(calibration.names,calibration,steps=steps,rate=rate)
    paths=simulate_paths(book,calibration.annual_volatilities.to_numpy(),corr,n_paths=n_paths,seed=seed)
    digest=sha256()
    digest.update(json.dumps({"names":calibration.names,"shape":paths.shape},separators=(",",":")).encode())
    digest.update(np.ascontiguousarray(paths,dtype="<f8").tobytes())
    return MasterPaths(calibration.names,paths,correlation,seed,scenario,digest.hexdigest())


def block_tail_interval(pnl, *, block_length=4, n_bootstrap=500, seed=730721, confidence=.95):
    """Circular block-bootstrap ES for chronological nonoverlapping period P&Ls."""
    values=np.asarray(pnl,dtype=float)
    if values.ndim!=1 or len(values)<2 or not np.isfinite(values).all():
        raise ValueError("Need at least two finite chronological P&Ls.")
    if isinstance(block_length,bool) or not isinstance(block_length,int) or not 1<=block_length<=len(values):
        raise ValueError("Invalid block length.")
    if isinstance(n_bootstrap,bool) or not isinstance(n_bootstrap,int) or n_bootstrap<2 or not 0<confidence<1:
        raise ValueError("Invalid bootstrap settings.")
    rng=np.random.default_rng(seed)
    blocks=int(np.ceil(len(values)/block_length))
    draws=np.empty(n_bootstrap)
    tail=max(1,int(np.ceil(.05*len(values))))
    for index in range(n_bootstrap):
        starts=rng.integers(0,len(values),size=blocks)
        indices=((starts[:,None]+np.arange(block_length))%len(values)).reshape(-1)[:len(values)]
        sample=values[indices].copy()
        sample.partition(tail-1)
        draws[index]=-sample[:tail].mean()
    low,high=np.quantile(draws,[(1-confidence)/2,(1+confidence)/2])
    return dict(estimate=expected_shortfall(values),lower=float(low),upper=float(high),
                bootstrap_se=float(draws.std(ddof=1)),block_length=block_length,
                n_periods=len(values),tail_observations=tail,n_bootstrap=n_bootstrap,
                method="circular_block_bootstrap_ES_nonoverlap_20_session_periods")


def historical_equity_diagnostic(prices,compositions,*,test_start="2021-01-01",test_end="2026-11-04",
                                  total_notional=300000.,horizon=20,industries=None,
                                  n_bootstrap=500,seed=730721):
    """Actual static-equity diagnostic, not an option-overlay or forecast backtest.

    Each nonoverlapping return interval starts at its preceding close, holds equal
    initial dollar amounts for horizon sessions, and reports the price-only change.
    Costs, dividends, financing and derivative positions are not part of this
    separate diagnostic. Contemporary industry labels are descriptive only.
    """
    if not isinstance(prices,pd.DataFrame) or not isinstance(prices.index,pd.DatetimeIndex):
        raise ValueError("Need a dated complete-history master panel.")
    if not prices.index.is_unique or not prices.index.is_monotonic_increasing or not np.isfinite(prices.to_numpy()).all() or (prices.to_numpy()<=0).any():
        raise ValueError("Diagnostic prices must be complete, positive and uniquely ordered.")
    if isinstance(horizon,bool) or not isinstance(horizon,int) or horizon<1 or total_notional<=0:
        raise ValueError("Invalid horizon or capital.")
    future_indices=np.flatnonzero((prices.index>=pd.Timestamp(test_start)) & (prices.index<=pd.Timestamp(test_end)))
    if len(future_indices)<2*horizon or future_indices[0]==0:
        raise ValueError("Need a preceding close and at least two full nonoverlapping periods.")
    origin=int(future_indices[0]-1)
    last=int(future_indices[-1])
    window_rows=[]
    for start in range(origin,last-horizon+1,horizon):
        window_rows.append((start,start+horizon))
    if len(window_rows)<2:
        raise ValueError("Too few complete historical periods.")
    rows,summary_rows,contribution_rows=[],[],[]
    industries={} if industries is None else dict(industries)
    for composition,chain in compositions.items():
        for breadth,names in chain.items():
            names=tuple(names)
            if len(names)!=breadth or not set(names).issubset(prices.columns):
                raise ValueError("Composition labels do not match complete price columns.")
            weights=np.full(breadth,total_notional/breadth)
            name_pnls=[]
            for first,last_date in window_rows:
                start_prices=prices.iloc[first].loc[list(names)].to_numpy()
                end_prices=prices.iloc[last_date].loc[list(names)].to_numpy()
                contributions=weights*(end_prices/start_prices-1)
                name_pnls.append(contributions)
                rows.append(dict(composition=composition,breadth=breadth,
                                 origin=prices.index[first],target_start=prices.index[first+1],
                                 target_end=prices.index[last_date],total_notional=total_notional,
                                 price_only_pnl=float(contributions.sum())))
            matrix=np.asarray(name_pnls)
            pnl=matrix.sum(axis=1)
            tail_count=max(1,int(np.ceil(.05*len(pnl))))
            tail_indices=np.argsort(pnl)[:tail_count]
            tail=block_tail_interval(pnl,block_length=min(4,len(pnl)),n_bootstrap=n_bootstrap,seed=seed)
            mean=moving_block_mean_interval(pnl,block_length=min(4,len(pnl)),n_bootstrap=n_bootstrap,seed=seed)
            group_contributions={}
            for name,value in zip(names,-matrix[tail_indices].mean(axis=0)):
                group=industries.get(name,"unclassified_current_snapshot")
                group_contributions[group]=group_contributions.get(group,0.)+float(value)
            np.testing.assert_allclose(sum(group_contributions.values()),tail["estimate"],atol=1e-8)
            group_counts=pd.Series([industries.get(name,"unclassified_current_snapshot") for name in names]).value_counts()
            summary_rows.append(dict(
                composition=composition,breadth=breadth,periods=len(pnl),tail_observations=tail_count,
                mean_20_session_pnl=float(pnl.mean()),mean_block_lower=mean["lower"],mean_block_upper=mean["upper"],
                pnl_std=float(pnl.std(ddof=1)),loss_es95=tail["estimate"],es95_block_lower=tail["lower"],es95_block_upper=tail["upper"],
                industry_weight_hhi=float(np.sum((group_counts.to_numpy()/breadth)**2)),
                largest_current_industry_tail_contributor=max(group_contributions,key=group_contributions.get),
            ))
            for group,value in group_contributions.items():
                contribution_rows.append(dict(composition=composition,breadth=breadth,current_industry=group,
                                              portfolio_tail_loss_contribution=value))
    return {"periods":pd.DataFrame(rows),"summary":pd.DataFrame(summary_rows),
            "tail_group_contributions":pd.DataFrame(contribution_rows),
            "convention":"price-only static equal-initial-dollar equity; no derivatives, trading costs, financing or dividends",
            "universe_gate":"conditional current-survivor complete-history subset; not point-in-time membership"}

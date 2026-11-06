"""Past-only physical return-risk forecasts; separate from Q option valuation."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class RiskProtocol:
    train_start: str = "2010-01-04"
    train_end: str = "2017-12-31"
    validation_start: str = "2018-01-01"
    validation_end: str = "2020-12-31"
    test_start: str = "2021-01-01"
    test_end: str = "2026-11-04"
    horizons: tuple[int, ...] = (5, 20)
    lookback: int = 252
    recent_window: int = 20
    ewma_lambda: float = 0.94
    shrinkage: float = 0.20
    bootstrap_repetitions: int = 1000
    bootstrap_seed: int = 730501

    def __post_init__(self):
        dates = [pd.Timestamp(getattr(self, name)) for name in (
            "train_start", "train_end", "validation_start", "validation_end", "test_start", "test_end"
        )]
        if not all(a < b for a, b in zip(dates, dates[1:])):
            raise ValueError("Chronological split boundaries must be strictly increasing.")
        if self.lookback < 2 or not 2 <= self.recent_window <= self.lookback:
            raise ValueError("Require 2 <= recent_window <= lookback.")
        if not self.horizons or any(isinstance(h, bool) or not isinstance(h, int) or h < 1 for h in self.horizons):
            raise ValueError("Forecast horizons must be positive integers.")
        if len(set(self.horizons)) != len(self.horizons):
            raise ValueError("Forecast horizons must be unique.")
        if not 0 < self.ewma_lambda < 1 or not 0 <= self.shrinkage <= 1:
            raise ValueError("Invalid EWMA or shrinkage parameter.")
        if self.bootstrap_repetitions < 2:
            raise ValueError("At least two bootstrap repetitions are required.")


def validate_prices(prices):
    if not isinstance(prices, pd.DataFrame) or prices.shape[1] < 1 or prices.shape[0] < 3:
        raise ValueError("Prices must be a nonempty dated DataFrame with at least three rows.")
    frame = prices.copy()
    frame.index = pd.DatetimeIndex(frame.index)
    if frame.index.hasnans or frame.index.has_duplicates or not frame.index.is_monotonic_increasing:
        raise ValueError("Price dates must be unique, finite and increasing.")
    if not frame.columns.is_unique:
        raise ValueError("Underlying names must be unique.")
    values = frame.to_numpy(dtype=float)
    if not np.isfinite(values).all() or (values <= 0).any():
        raise ValueError("Use positive finite prices on an explicitly aligned sample; do not forward-fill.")
    return frame.astype(float)


def log_returns(prices):
    return np.log(validate_prices(prices)).diff().iloc[1:]


def variance_forecasts(prices, protocol=RiskProtocol()):
    """Forecast next-horizon cumulative squared log returns after each close.

    All feature values include information only through the origin close. The
    realized target uses returns on the following h observations, not r_t.
    """
    returns = log_returns(prices)
    squared = returns ** 2
    predictors = {
        "rv_long": squared.rolling(protocol.lookback, min_periods=protocol.lookback).mean(),
        "rv_recent": squared.rolling(protocol.recent_window, min_periods=protocol.recent_window).mean(),
        "ewma": squared.ewm(alpha=1 - protocol.ewma_lambda, adjust=False,
                                  min_periods=protocol.lookback).mean(),
    }
    # Identical history eligibility for every model; window sizes live in the protocol.
    for frame in predictors.values():
        frame.iloc[:protocol.lookback - 1] = np.nan
    dates = pd.Series(returns.index, index=returns.index)
    pieces = []
    for horizon in protocol.horizons:
        target = squared.rolling(horizon, min_periods=horizon).sum().shift(-horizon)
        for model, predictor in predictors.items():
            for name in returns.columns:
                pieces.append(pd.DataFrame({
                    "origin": returns.index, "target_start": dates.shift(-1).to_numpy(),
                    "target_end": dates.shift(-horizon).to_numpy(), "asset": name,
                    "panel": "single_names", "horizon": horizon, "model": model,
                    "variance_forecast": (horizon * predictor[name]).to_numpy(),
                    "realized_variance": target[name].to_numpy(),
                    "feature_last_date": returns.index,
                }))
    return pd.concat(pieces, ignore_index=True).dropna().reset_index(drop=True)


def covariance_estimates(history, shrinkage=0.20, variance_floor=1e-12, factor_history=None):
    """Daily sample covariance, fixed diagonal shrinkage and internal one factor.

    The factor is the equal-weight cross-sectional return, estimated entirely
    inside the supplied past window. It is not an observed market/ETF factor.
    """
    sample = np.asarray(history, dtype=float)
    if sample.ndim != 2 or sample.shape[0] < 2 or sample.shape[1] < 1 or not np.isfinite(sample).all():
        raise ValueError("History must be a finite observation-by-asset array.")
    if not np.isfinite(shrinkage) or not 0 <= shrinkage <= 1:
        raise ValueError("shrinkage must be between zero and one.")
    if not np.isfinite(variance_floor) or variance_floor <= 0:
        raise ValueError("variance_floor must be positive.")
    centered = sample - sample.mean(axis=0)
    covariance = centered.T @ centered / (len(sample) - 1)
    diagonal = np.diag(np.maximum(np.diag(covariance), variance_floor))
    shrink = (1 - shrinkage) * covariance + shrinkage * diagonal
    factor = centered.mean(axis=1)
    factor_variance = factor @ factor / (len(sample) - 1)
    if factor_variance > variance_floor:
        beta = centered.T @ factor / ((len(sample) - 1) * factor_variance)
        residual = centered - np.outer(factor, beta)
        residual_variance = np.sum(residual ** 2, axis=0) / (len(sample) - 1)
        factor_cov = np.outer(beta, beta) * factor_variance + np.diag(np.maximum(residual_variance, variance_floor))
    else:
        factor_cov = diagonal
    estimates = {
        "sample_covariance": covariance,
        "diagonal_shrinkage": shrink,
        "internal_factor": factor_cov,
    }
    if factor_history is not None:
        factors = np.asarray(factor_history, dtype=float)
        if factors.ndim != 2 or factors.shape[0] != sample.shape[0] or factors.shape[1] < 1 or not np.isfinite(factors).all():
            raise ValueError("Factor history must be a finite aligned observation-by-factor array.")
        factors = factors - factors.mean(axis=0)
        loadings = np.linalg.lstsq(factors, centered, rcond=None)[0]
        factor_matrix_cov = factors.T @ factors / (len(sample) - 1)
        residual = centered - factors @ loadings
        residual_variance = np.sum(residual ** 2, axis=0) / (len(sample) - 1)
        estimates["external_factor"] = (
            loadings.T @ factor_matrix_cov @ loadings
            + np.diag(np.maximum(residual_variance, variance_floor))
        )
    return estimates


def covariance_forecasts(prices, protocol=RiskProtocol(), factor_prices=None):
    """Physical cumulative-risk forecasts for a fixed equal-weight return basket."""
    returns = log_returns(prices)
    factors = None
    if factor_prices is not None:
        factors = log_returns(factor_prices)
        if not factors.index.equals(returns.index):
            raise ValueError("Factor returns must have exactly the same observation dates.")
    weights = np.full(returns.shape[1], 1 / returns.shape[1])
    portfolio_returns = returns.to_numpy() @ weights
    pieces = []
    for position in range(protocol.lookback - 1, len(returns) - min(protocol.horizons)):
        history = returns.iloc[position - protocol.lookback + 1:position + 1].to_numpy()
        factor_history = None if factors is None else factors.iloc[position - protocol.lookback + 1:position + 1].to_numpy()
        covariances = covariance_estimates(history, protocol.shrinkage, factor_history=factor_history)
        for horizon in protocol.horizons:
            if position + horizon >= len(returns):
                continue
            realized = np.sum(portfolio_returns[position + 1:position + horizon + 1] ** 2)
            for model, covariance in covariances.items():
                pieces.append({
                    "origin": returns.index[position], "target_start": returns.index[position + 1],
                    "target_end": returns.index[position + horizon], "asset": "equal_weight_basket",
                    "panel": "portfolio", "horizon": horizon, "model": model,
                    "variance_forecast": float(horizon * weights @ covariance @ weights),
                    "realized_variance": float(realized), "feature_last_date": returns.index[position],
                    "minimum_covariance_eigenvalue": float(np.linalg.eigvalsh(covariance).min()),
                })
    return pd.DataFrame(pieces)


def chronological_nonoverlap(panel, protocol=RiskProtocol()):
    """Retain disjoint target intervals within each chronological split/horizon."""
    frame = panel.copy()
    for column in ("origin", "target_start", "target_end", "feature_last_date"):
        frame[column] = pd.to_datetime(frame[column])
    if not (frame["feature_last_date"] <= frame["origin"]).all():
        raise ValueError("A feature is available after its forecast origin.")
    if not (frame["target_start"] > frame["origin"]).all():
        raise ValueError("Targets must start strictly after the forecast origin.")
    if not (frame["target_end"] >= frame["target_start"]).all():
        raise ValueError("Target dates are invalid.")
    splits = {
        "train": (protocol.train_start, protocol.train_end),
        "validation": (protocol.validation_start, protocol.validation_end),
        "test": (protocol.test_start, protocol.test_end),
    }
    retained = []
    for label, (start, end) in splits.items():
        eligible = frame.loc[(frame["origin"] >= pd.Timestamp(start)) & (frame["target_end"] <= pd.Timestamp(end))]
        for horizon in protocol.horizons:
            subset = eligible.loc[eligible["horizon"].eq(horizon)]
            dates = subset[["origin", "target_start", "target_end"]].drop_duplicates().sort_values("origin")
            if dates["origin"].duplicated().any():
                raise ValueError("Target dates disagree across assets/models for an origin.")
            previous_end = pd.Timestamp.min
            origins = []
            for row in dates.itertuples(index=False):
                if row.target_start > previous_end:
                    origins.append(row.origin)
                    previous_end = row.target_end
            retained.append(subset.loc[subset["origin"].isin(origins)].assign(split=label))
    return pd.concat(retained, ignore_index=True)


def add_losses(panel, forecast_floor=1e-12):
    """QLIKE = log(forecast) + realized/forecast; lower is better.

    This excludes the target-only constant, permitting zero realized variance.
    Raw QLIKE may be negative; differences across forecasts remain meaningful.
    """
    frame = panel.copy()
    forecast = frame["variance_forecast"].to_numpy(dtype=float)
    target = frame["realized_variance"].to_numpy(dtype=float)
    if not np.isfinite(forecast).all() or not np.isfinite(target).all() or (forecast < 0).any() or (target < 0).any():
        raise ValueError("Variance forecasts/targets must be finite and nonnegative.")
    if not np.isfinite(forecast_floor) or forecast_floor <= 0:
        raise ValueError("forecast_floor must be positive.")
    safe = np.maximum(forecast, forecast_floor)
    frame["mse"] = (forecast - target) ** 2
    frame["qlike"] = np.log(safe) + target / safe
    return frame


def moving_block_mean_interval(values, *, block_length, n_bootstrap=1000, seed=730501, confidence=.95):
    """Circular moving-block bootstrap for chronological date-level differences."""
    values = np.asarray(values, dtype=float)
    if values.ndim != 1 or len(values) < 2 or not np.isfinite(values).all():
        raise ValueError("Need at least two finite chronological differences.")
    if isinstance(block_length, bool) or not isinstance(block_length, int) or not 1 <= block_length <= len(values):
        raise ValueError("block_length must be between one and the observation count.")
    if not isinstance(n_bootstrap, int) or n_bootstrap < 2 or not 0 < confidence < 1:
        raise ValueError("Invalid bootstrap count or confidence.")
    rng = np.random.default_rng(seed)
    n_blocks = int(np.ceil(len(values) / block_length))
    draws = np.empty(n_bootstrap)
    for start in range(0, n_bootstrap, 64):
        count = min(64, n_bootstrap - start)
        starts = rng.integers(0, len(values), size=(count, n_blocks))
        indices = ((starts[:, :, None] + np.arange(block_length)) % len(values)).reshape(count, -1)[:, :len(values)]
        draws[start:start + count] = values[indices].mean(axis=1)
    alpha = (1 - confidence) / 2
    low, high = np.quantile(draws, [alpha, 1 - alpha])
    return {"estimate": float(values.mean()), "lower": float(low), "upper": float(high),
            "bootstrap_se": float(draws.std(ddof=1)), "block_length": block_length,
            "n_dates": len(values), "n_bootstrap": n_bootstrap, "confidence": confidence,
            "method": "circular_moving_block_bootstrap_date_mean"}

"""Release-aware feature joins and train-only interpretable variance models."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .risk_models import log_returns

PRICE_FEATURES = (
    "log_rv_recent", "log_rv_long", "log_ewma", "return_5", "return_20", "negative_return_20",
)
MARKET_FEATURES = (
    "SPY_log_rv_20", "SPY_log_rv_252", "SPY_return_5", "SPY_return_20",
    "XLF_log_rv_20", "XLF_log_rv_252", "XLF_return_5", "XLF_return_20",
    "beta_SPY", "beta_XLF", "beta_SPY_return_5", "beta_XLF_return_5",
)


def close_cutoffs(dates):
    """Conservative filing cutoff at the origin's 16:00 New York close.

    Forecasts use final-close price features and are issued after close. A filing
    accepted after this cutoff cannot enter that origin's feature set. This does
    not assert that a real feed or trading fill was available at the same close.
    """
    dates = pd.DatetimeIndex(dates)
    if dates.tz is not None:
        raise ValueError("Provide session dates, not timezone-aware intraday timestamps.")
    return (dates.normalize().tz_localize("America/New_York") + pd.Timedelta(hours=16)).tz_convert("UTC")


def _aware_utc(values, name):
    timestamps = [pd.Timestamp(value) for value in values]
    if any(value is pd.NaT or pd.isna(value) or value.tzinfo is None for value in timestamps):
        raise ValueError(f"{name} must contain verified timezone-aware timestamps.")
    return pd.DatetimeIndex([value.tz_convert("UTC") for value in timestamps])


def release_aware_asof(origins, observations, *, feature_columns, symbol_column="symbol",
                       origin_column="origin_at", available_column="available_at", max_age_days=None,
                       period_column="period_end", max_period_age_days=None):
    """Join the latest actually available release; never infer from fiscal dates.

    Missing pre-release values remain NaN. When fiscal periods are supplied,
    choose the newest available period before its latest available revision.
    Publication timestamps/timezones and
    original-vintage eligibility must be verified by the data audit before use.
    ``max_age_days`` can invalidate stale releases without zero imputation.
    """
    if not feature_columns or not set(feature_columns).issubset(observations.columns):
        raise ValueError("Explicit existing feature columns are required.")
    if not {symbol_column, origin_column}.issubset(origins.columns):
        raise ValueError("Origins need symbol and origin timestamp columns.")
    if not {symbol_column, available_column}.issubset(observations.columns):
        raise ValueError("Observations need symbol and verified availability timestamps.")
    if set(feature_columns) & set(origins.columns) or available_column in origins.columns:
        raise ValueError("Release columns would overwrite origin information.")
    left, right = origins.copy(), observations.copy()
    left[origin_column] = _aware_utc(left[origin_column], origin_column)
    right[available_column] = _aware_utc(right[available_column], available_column)
    has_period = period_column in right.columns
    if has_period:
        right["matched_period_end"] = pd.to_datetime(right[period_column])
        if right["matched_period_end"].isna().any():
            raise ValueError("Fiscal period ends must be valid when supplied.")
        if not (right["matched_period_end"] <= right[available_column].dt.tz_localize(None)).all():
            raise ValueError("A fiscal period cannot end after its release.")
    if has_period:
        newest_at_release = right.groupby([symbol_column, available_column])["matched_period_end"].transform("max")
        right = right.loc[right["matched_period_end"].eq(newest_at_release)].copy()
    if right.duplicated([symbol_column, available_column]).any():
        if has_period and {"filed", "accn"}.issubset(right.columns):
            if right.duplicated([symbol_column, available_column, "matched_period_end", "filed", "accn"]).any():
                raise ValueError("Duplicate filing identities are ambiguous.")
            right = right.sort_values([symbol_column, available_column, "filed", "accn"]).drop_duplicates([symbol_column, available_column], keep="last")
        else:
            raise ValueError("Duplicate symbol/availability releases are ambiguous.")
    if max_age_days is not None and (not np.isfinite(max_age_days) or max_age_days < 0):
        raise ValueError("max_age_days must be nonnegative.")
    if max_period_age_days is not None and (not has_period or not np.isfinite(max_period_age_days) or max_period_age_days < 0):
        raise ValueError("A nonnegative period-age limit requires fiscal periods.")
    left["_original_order"] = np.arange(len(left))
    pieces = []
    for symbol, group in left.groupby(symbol_column, sort=False):
        columns = [available_column, *feature_columns] + (["matched_period_end"] if has_period else [])
        candidate = right.loc[right[symbol_column].eq(symbol), columns].sort_values(available_column)
        if has_period:
            # Later amendments/comparatives of older periods cannot roll back a
            # newer quarter already known at that origin. Same-period revisions
            # remain eligible only from their actual availability timestamps.
            candidate = candidate.loc[candidate["matched_period_end"] >= candidate["matched_period_end"].cummax()]
        merged = pd.merge_asof(group.sort_values(origin_column), candidate,
                               left_on=origin_column, right_on=available_column, direction="backward")
        if max_age_days is not None:
            age = (merged[origin_column] - merged[available_column]).dt.total_seconds() / 86400
            merged.loc[age > max_age_days, list(feature_columns)] = np.nan
        if max_period_age_days is not None:
            period_age = (merged[origin_column].dt.tz_localize(None) - merged["matched_period_end"]).dt.total_seconds() / 86400
            merged.loc[period_age > max_period_age_days, list(feature_columns)] = np.nan
        pieces.append(merged)
    if not pieces:
        raise ValueError("At least one forecast origin is required.")
    joined = pd.concat(pieces, ignore_index=True).sort_values("_original_order").drop(columns="_original_order")
    seen = joined[available_column].notna()
    if not (joined.loc[seen, available_column] <= joined.loc[seen, origin_column]).all():
        raise AssertionError("Future release entered the join.")
    return joined.reset_index(drop=True)


def price_market_features(prices, factors, *, lookback=252, recent_window=20, ewma_lambda=.94):
    """Past-only company and observed SPY/XLF price features at origin close."""
    returns = log_returns(prices)
    factor_returns = log_returns(factors)
    if not returns.index.equals(factor_returns.index) or not {"SPY", "XLF"}.issubset(factor_returns.columns):
        raise ValueError("Exactly aligned SPY/XLF factor observations are required.")
    if not 2 <= recent_window <= lookback or not 0 < ewma_lambda < 1:
        raise ValueError("Invalid feature parameters.")
    common = pd.DataFrame(index=returns.index)
    for name in ("SPY", "XLF"):
        source = factor_returns[name]
        common[f"{name}_log_rv_20"] = np.log(source.pow(2).rolling(recent_window).mean().clip(lower=1e-12))
        common[f"{name}_log_rv_252"] = np.log(source.pow(2).rolling(lookback).mean().clip(lower=1e-12))
        common[f"{name}_return_5"] = source.rolling(5).sum()
        common[f"{name}_return_20"] = source.rolling(20).sum()
    pieces = []
    for symbol in returns.columns:
        source = returns[symbol]
        features = common.copy()
        features["log_rv_recent"] = np.log(source.pow(2).rolling(recent_window).mean().clip(lower=1e-12))
        features["log_rv_long"] = np.log(source.pow(2).rolling(lookback).mean().clip(lower=1e-12))
        features["log_ewma"] = np.log(source.pow(2).ewm(alpha=1-ewma_lambda, adjust=False, min_periods=lookback).mean().clip(lower=1e-12))
        features["return_5"] = source.rolling(5).sum()
        features["return_20"] = source.rolling(20).sum()
        features["negative_return_20"] = features["return_20"].clip(upper=0)
        for factor in ("SPY", "XLF"):
            denominator = factor_returns[factor].rolling(lookback).var(ddof=1)
            features[f"beta_{factor}"] = source.rolling(lookback).cov(factor_returns[factor]) / denominator.replace(0, np.nan)
            features[f"beta_{factor}_return_5"] = features[f"beta_{factor}"] * features[f"{factor}_return_5"]
        features["asset"] = symbol
        features["origin"] = returns.index
        features["feature_last_date"] = returns.index
        features["origin_at"] = close_cutoffs(returns.index)
        pieces.append(features.reset_index(drop=True))
    return pd.concat(pieces, ignore_index=True)


@dataclass(frozen=True)
class LogVarianceRidge:
    feature_names: tuple[str, ...]
    means: np.ndarray
    scales: np.ndarray
    coefficients: np.ndarray
    intercept: float
    smear: float
    alpha: float
    log_bounds: tuple[float, float]
    training_rows: int

    def predict(self, features):
        if list(features.columns) != list(self.feature_names):
            raise ValueError("Prediction columns must match fitted feature names/order.")
        x = features.to_numpy(dtype=float)
        if not np.isfinite(x).all():
            raise ValueError("Unknown feature values cannot be imputed to zero.")
        log_prediction = ((x - self.means) / self.scales) @ self.coefficients + self.intercept
        return np.exp(np.clip(log_prediction, *self.log_bounds)) * self.smear


def fit_log_variance_ridge(features, daily_realized_variance, *, alpha=1.0):
    """Fit scaling, coefficients and retransformation correction on train only.

    The caller must pass only training rows with targets ending before its cutoff.
    Target is the total underlying variance, not a factor-residual variance.
    """
    if not isinstance(features, pd.DataFrame) or not features.columns.is_unique:
        raise ValueError("Features must have unique named columns.")
    x = features.to_numpy(dtype=float)
    target = np.asarray(daily_realized_variance, dtype=float)
    if x.ndim != 2 or len(x) < 2 or target.shape != (len(x),) or not np.isfinite(x).all() or not np.isfinite(target).all() or (target < 0).any():
        raise ValueError("Finite complete training features and nonnegative variance targets are required.")
    if not np.isfinite(alpha) or alpha <= 0:
        raise ValueError("Positive finite ridge penalty required.")
    means, scales = x.mean(axis=0), x.std(axis=0, ddof=0)
    scales = np.where(scales > 1e-12, scales, 1.0)
    standardized = (x - means) / scales
    y = np.log(np.maximum(target, 1e-12))
    intercept = float(y.mean())
    coefficients = np.linalg.solve(standardized.T @ standardized + alpha * np.eye(x.shape[1]),
                                   standardized.T @ (y - intercept))
    fitted = standardized @ coefficients + intercept
    smear = float(np.exp(y - fitted).mean())
    return LogVarianceRidge(tuple(features.columns), means, scales, coefficients, intercept,
                            smear, float(alpha), (float(y.min()-5), float(y.max()+5)), len(x))


def design_matrix(panel, feature_names, assets):
    """Named numerical features plus a fixed, declared issuer intercept encoding."""
    if not panel["asset"].isin(assets).all():
        raise ValueError("An issuer was not in the predeclared sample.")
    x = panel.loc[:, list(feature_names)].copy()
    for asset in list(assets)[1:]:
        x[f"issuer_{asset}"] = panel["asset"].eq(asset).astype(float)
    return x


def filing_balance_sheet_ratios(snapshots):
    """Dimensionless same-filing/period USD proxies from approved SEC snapshots.

    These are accounting exposure proxies, not regulatory capital/liquidity or
    insured-deposit measures. Broker/dealer issuers are excluded from the bank
    deposit hypothesis by the source's explicit issuer approval flag.
    """
    required = {
        "symbol", "period_end", "available_at", "unit", "same_filing_and_period",
        "original_vintage_verified", "assets", "liabilities", "cash_and_due_from_banks",
        "deposits", "deposit_feature_approved_for_issuer",
    }
    if not required.issubset(snapshots.columns):
        raise ValueError("Missing audited same-period SEC snapshot fields.")
    data = snapshots.copy()
    true = lambda column: data[column].astype(str).str.lower().eq("true")
    if not data["unit"].eq("USD").all() or not true("same_filing_and_period").all() or not true("original_vintage_verified").all():
        raise ValueError("Only approved same-period USD filing-vintage snapshots may enter features.")
    data["available_at"] = _aware_utc(data["available_at"], "available_at")
    assets = pd.to_numeric(data["assets"], errors="raise")
    liabilities = pd.to_numeric(data["liabilities"], errors="raise")
    cash = pd.to_numeric(data["cash_and_due_from_banks"], errors="raise")
    deposits = pd.to_numeric(data["deposits"], errors="raise")
    for values in (assets, liabilities, cash, deposits):
        if not np.isfinite(values.dropna().to_numpy()).all():
            raise ValueError("Observed financial values must be finite.")
    if (assets.dropna() <= 0).any():
        raise ValueError("Observed asset denominators must be positive.")
    identity = [column for column in ("filed", "accn") if column in data.columns]
    result = data[["symbol", "period_end", "available_at", *identity]].copy()
    result["liabilities_assets"] = liabilities / assets
    approved_bank = true("deposit_feature_approved_for_issuer")
    result["bank_deposits_liabilities"] = (deposits / liabilities.where(liabilities > 0)).where(approved_bank)
    result["bank_cash_assets"] = (cash / assets).where(approved_bank)
    return result

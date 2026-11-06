"""Monte Carlo uncertainty for independent outcomes and paired hedge policies.

Each vector element must be one economic outcome, not an antithetic-pair average
or an observation from overlapping historical forecast windows. Paired inputs
must represent the same outcomes in the same order; verify scenario identifiers
before calling. Equal lengths alone cannot establish pairing.
"""
from __future__ import annotations

from numbers import Integral

import numpy as np
from scipy.stats import norm


def _sample(values, name="values"):
    try:
        sample = np.asarray(values, dtype=float)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a finite one-dimensional numeric vector.") from exc
    if sample.ndim != 1 or sample.size < 2 or not np.isfinite(sample).all():
        raise ValueError(f"{name} must be a finite one-dimensional vector with at least two observations.")
    return sample


def _probability(value, name, *, include_one=False):
    if isinstance(value, (bool, np.bool_)):
        raise ValueError(f"{name} must be a probability.")
    try:
        value = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a probability.") from exc
    valid = 0 < value <= 1 if include_one else 0 < value < 1
    if not np.isfinite(value) or not valid:
        endpoint = "(0, 1]" if include_one else "(0, 1)"
        raise ValueError(f"{name} must be finite and in {endpoint}.")
    return value


def _integer(value, name, minimum):
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, Integral) or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}.")
    return int(value)


def _bootstrap_settings(confidence, tail_probability, n_bootstrap, seed, chunk_size):
    return (
        _probability(confidence, "confidence"),
        _probability(tail_probability, "tail_probability", include_one=True),
        _integer(n_bootstrap, "n_bootstrap", 2),
        _integer(seed, "seed", 0),
        _integer(chunk_size, "chunk_size", 1),
    )


def _risk(sample, metric, tail_count):
    """Reduce a fresh 2D resample matrix; ES partitions that matrix in place."""
    if metric == "es":
        sample.partition(tail_count - 1, axis=1)
        return -sample[:, :tail_count].mean(axis=1)
    if metric == "std":
        return sample.std(axis=1, ddof=1)
    if metric == "rmse":
        return np.sqrt(np.mean(sample ** 2, axis=1))
    raise ValueError("metric must be 'es', 'std', or 'rmse'.")


def _bootstrap_summary(draws, estimate, confidence):
    alpha = (1 - confidence) / 2
    lower, upper = np.quantile(draws, [alpha, 1 - alpha])
    return {
        "estimate": float(estimate),
        "lower": float(lower),
        "upper": float(upper),
        "bootstrap_se": float(draws.std(ddof=1)),
        "confidence": confidence,
    }


def mean_interval(values, confidence=0.95):
    """Two-sided normal Monte Carlo interval for an independent-outcome mean.

    For an expected-cost budget, ``upper`` is a conservative two-sided upper
    endpoint, not a hard limit on each path's realized cost. It is a one-sided
    (1 + confidence)/2 upper bound under the normal approximation. Selection
    over many candidates needs untouched evaluation and/or simultaneous bounds.
    """
    sample = _sample(values)
    confidence = _probability(confidence, "confidence")
    mean = float(sample.mean())
    se = float(sample.std(ddof=1) / np.sqrt(sample.size))
    radius = float(norm.ppf((1 + confidence) / 2)) * se
    return {
        "mean": mean,
        "se": se,
        "lower": mean - radius,
        "upper": mean + radius,
        "n_paths": int(sample.size),
        "confidence": confidence,
        "method": "normal_independent_outcome_mean",
    }


def expected_shortfall(pnl, tail_probability=0.05):
    """Loss ES = minus the mean of the worst ceil(tail_probability*N) P&Ls.

    This matches ``hedging_harness.core.summarize`` at tail_probability=.05.
    The result may be negative when even the selected worst outcomes profit.
    """
    sample = _sample(pnl, "pnl")
    probability = _probability(tail_probability, "tail_probability", include_one=True)
    tail_count = max(1, int(np.ceil(probability * sample.size)))
    return float(_risk(sample[None, :].copy(), "es", tail_count)[0])


def paired_tail_difference(
    left_pnl,
    right_pnl,
    *,
    confidence=0.95,
    tail_probability=0.05,
    n_bootstrap=1000,
    seed=20261105,
    chunk_size=32,
):
    """Paired percentile-bootstrap interval for ES(left) minus ES(right).

    Negative estimates favor the left policy under loss ES. Each bootstrap draw
    uses identical outcome indices for both policies, while each policy's ES is
    evaluated on its own worst resampled outcomes. This is a difference of ESs,
    not ES of the paired P&L difference. Input order is never changed in place.

    Percentile intervals quantify simulation sampling uncertainty conditional
    on the fixed policies/model. They do not include calibration uncertainty or
    justify policy selection using the evaluation outcomes. chunk_size affects
    memory consumption without changing the seeded sequence of resamples.
    """
    left = _sample(left_pnl, "left_pnl")
    right = _sample(right_pnl, "right_pnl")
    if left.shape != right.shape:
        raise ValueError("Paired inputs must have the same number of outcomes.")
    confidence, probability, n_bootstrap, seed, chunk_size = _bootstrap_settings(
        confidence, tail_probability, n_bootstrap, seed, chunk_size
    )
    n_paths = int(left.size)
    tail_count = max(1, int(np.ceil(probability * n_paths)))
    estimate = expected_shortfall(left, probability) - expected_shortfall(right, probability)
    rng = np.random.default_rng(seed)
    draws = np.empty(n_bootstrap)
    for start in range(0, n_bootstrap, chunk_size):
        count = min(chunk_size, n_bootstrap - start)
        indices = rng.integers(0, n_paths, size=(count, n_paths))
        left_es = _risk(left[indices], "es", tail_count)
        right_es = _risk(right[indices], "es", tail_count)
        draws[start:start + count] = left_es - right_es
    return {
        **_bootstrap_summary(draws, estimate, confidence),
        "n_paths": n_paths,
        "tail_probability": probability,
        "tail_count": tail_count,
        "effective_tail_probability": tail_count / n_paths,
        "n_bootstrap": n_bootstrap,
        "seed": seed,
        "method": "paired_percentile_bootstrap_ES_difference",
        "difference_convention": "ES(left) - ES(right); negative favors left",
        "assumption": "independent outcomes; policies paired in identical outcome order",
    }


def risk_interval(
    pnl,
    *,
    metric="es",
    confidence=0.95,
    tail_probability=0.05,
    n_bootstrap=1000,
    seed=20261105,
    chunk_size=32,
):
    """Percentile-bootstrap uncertainty for loss ES, sample std, or RMSE.

    The tail fraction is used only for metric='es'. Other metrics report their
    respective economic-outcome statistic, not uncertainty in the sample mean.
    """
    sample = _sample(pnl, "pnl")
    if metric not in ("es", "std", "rmse"):
        raise ValueError("metric must be 'es', 'std', or 'rmse'.")
    confidence, probability, n_bootstrap, seed, chunk_size = _bootstrap_settings(
        confidence, tail_probability, n_bootstrap, seed, chunk_size
    )
    n_paths = int(sample.size)
    tail_count = max(1, int(np.ceil(probability * n_paths)))
    estimate = _risk(sample[None, :].copy(), metric, tail_count)[0]
    rng = np.random.default_rng(seed)
    draws = np.empty(n_bootstrap)
    for start in range(0, n_bootstrap, chunk_size):
        count = min(chunk_size, n_bootstrap - start)
        indices = rng.integers(0, n_paths, size=(count, n_paths))
        draws[start:start + count] = _risk(sample[indices], metric, tail_count)
    result = {
        **_bootstrap_summary(draws, estimate, confidence),
        "metric": metric,
        "n_paths": n_paths,
        "n_bootstrap": n_bootstrap,
        "seed": seed,
        "method": "percentile_bootstrap_risk_statistic",
        "assumption": "independent economic outcomes under a fixed model and policy",
    }
    if metric == "es":
        result.update(tail_probability=probability, tail_count=tail_count,
                      effective_tail_probability=tail_count / n_paths)
    return result

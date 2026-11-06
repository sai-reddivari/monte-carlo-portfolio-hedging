"""Run a frozen price-history risk forecast study without fitting on test outcomes."""
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))
import numpy as np
import pandas as pd

from hedging_harness.risk_models import (
    RiskProtocol, add_losses, chronological_nonoverlap, covariance_forecasts,
    moving_block_mean_interval, validate_prices, variance_forecasts,
)


def _hash(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def _json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def _table(frame):
    def fmt(value):
        if isinstance(value, (float, np.floating)):
            return f"{value:.6g}"
        return str(value).replace("|", "/")
    columns = list(frame.columns)
    return "\n".join([
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
        *["| " + " | ".join(fmt(value) for value in row) + " |" for row in frame.itertuples(index=False, name=None)],
    ])


def run(prices_path, factors_path, output_dir):
    protocol = RiskProtocol()
    prices_path, factors_path = Path(prices_path).resolve(), Path(factors_path).resolve()
    prices = validate_prices(pd.read_csv(prices_path, index_col="date", parse_dates=True))
    factors = validate_prices(pd.read_csv(factors_path, index_col="date", parse_dates=True))
    if not prices.index.equals(factors.index):
        raise ValueError("Stock and factor histories must have exactly the same aligned dates.")
    out = Path(output_dir).resolve()
    out.mkdir(parents=True, exist_ok=False)
    metadata_files = [prices_path.parent / name for name in (
        "prices_metadata.json", "core_10_metadata.json", "issuer_symbol_mappings.json"
    ) if (prices_path.parent / name).is_file()]
    frozen = {
        "protocol": asdict(protocol),
        "data_metadata_sha256": {str(p): _hash(p) for p in metadata_files}, "underlyings": list(prices.columns),
        "factor_symbols": list(factors.columns),
        "prices_file": str(prices_path), "prices_sha256": _hash(prices_path),
        "factor_file": str(factors_path), "factors_sha256": _hash(factors_path),
        "frozen_before_evaluation_utc": datetime.now(timezone.utc).isoformat(),
        "parameter_selection": "Fixed defaults; no training/validation/test outcome tuning.",
        "universe_caveat": "Conditional current-name sample; historical eligibility and survivorship-free membership are unverified.",
    }
    # Persist boundaries, parameters and data identities before computing losses.
    _json(out / "protocol.json", frozen)
    frozen_hash = _hash(out / "protocol.json")
    single = variance_forecasts(prices, protocol)
    portfolio = covariance_forecasts(prices, protocol, factors)
    full = pd.concat([single, portfolio], ignore_index=True)
    selected = chronological_nonoverlap(full, protocol)
    losses = add_losses(selected)
    losses.to_csv(out / "forecast_observations.csv", index=False)
    scores = losses.groupby(["panel", "split", "horizon", "asset", "model"], sort=True).agg(
        n_forecasts=("qlike", "size"), mean_qlike=("qlike", "mean"), mean_mse=("mse", "mean"),
        mean_forecast_variance=("variance_forecast", "mean"), mean_realized_variance=("realized_variance", "mean"),
    ).reset_index()
    scores.to_csv(out / "scores_by_asset.csv", index=False)
    pooled = losses.groupby(["panel", "split", "horizon", "model"], sort=True).agg(
        n_dates=("origin", "nunique"), n_asset_forecasts=("qlike", "size"),
        mean_qlike=("qlike", "mean"), mean_mse=("mse", "mean"),
    ).reset_index()
    baseline_names = {"single_names": "rv_long", "portfolio": "sample_covariance"}
    pooled["mse_skill_vs_baseline"] = np.nan
    pooled["qlike_difference_vs_baseline"] = np.nan
    for (panel, split, horizon), group in pooled.groupby(["panel", "split", "horizon"]):
        reference = group.loc[group["model"].eq(baseline_names[panel])].iloc[0]
        pooled.loc[group.index, "mse_skill_vs_baseline"] = 1 - group["mean_mse"] / reference["mean_mse"]
        pooled.loc[group.index, "qlike_difference_vs_baseline"] = group["mean_qlike"] - reference["mean_qlike"]
    pooled.to_csv(out / "pooled_scores.csv", index=False)

    comparisons = []
    for (panel, split, horizon), group in losses.loc[losses["split"].isin(["validation", "test"])].groupby(["panel", "split", "horizon"], sort=True):
        baseline = baseline_names[panel]
        for metric in ("qlike", "mse"):
            pivot = group.pivot(index=["origin", "asset"], columns="model", values=metric).dropna()
            for model in pivot.columns:
                if model == baseline:
                    continue
                # One average difference per origin keeps contemporaneous names together.
                differences = (pivot[model] - pivot[baseline]).groupby(level="origin").mean().sort_index()
                block_length = min(len(differences), max(2, math.ceil(63 / horizon)))
                interval = moving_block_mean_interval(
                    differences.to_numpy(), block_length=block_length,
                    n_bootstrap=protocol.bootstrap_repetitions,
                    seed=protocol.bootstrap_seed + int(horizon) + (0 if metric == "qlike" else 100),
                )
                comparisons.append({
                    "panel": panel, "split": split, "horizon": int(horizon), "metric": metric,
                    "model": model, "baseline": baseline, **interval,
                    "interpretation": "negative difference favors model; pointwise interval",
                })
    comparisons = pd.DataFrame(comparisons)
    comparisons.to_csv(out / "paired_loss_differences.csv", index=False)
    minimum_eigenvalue = float(portfolio["minimum_covariance_eigenvalue"].min())
    assert minimum_eigenvalue >= -1e-10
    assert (losses["feature_last_date"] <= losses["origin"]).all()
    assert (losses["target_start"] > losses["origin"]).all()
    assert _hash(out / "protocol.json") == frozen_hash
    checks = {
        "price_only_past_feature_checks_passed": True,
        "target_windows_nonoverlapping_within_split_horizon": True,
        "covariance_positive_semidefinite_checks_passed": True,
        "minimum_covariance_eigenvalue": minimum_eigenvalue,
        "train_validation_test_predeclared": True,
        "test_parameters_tuned": False,
        "macro_funding_features_evaluated": False,
        "historical_membership_verified": False,
        "listed_option_hedge_value_evaluated": False,
        "full_stage5_gate_passed": False,
    }
    _json(out / "checks.json", checks)

    os.environ.setdefault("MPLCONFIGDIR", tempfile.mkdtemp(prefix="risk-mpl-", dir="/tmp"))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    test = pooled.loc[pooled["split"].eq("test")]
    fig, axes = plt.subplots(2, 2, figsize=(13, 8))
    for row_index, panel in enumerate(("single_names", "portfolio")):
        for column_index, horizon in enumerate(protocol.horizons):
            ax = axes[row_index, column_index]
            group = test.loc[test["panel"].eq(panel) & test["horizon"].eq(horizon)]
            ax.bar(group["model"], group["mse_skill_vs_baseline"], color="tab:blue")
            ax.axhline(0, color="black", linewidth=.8)
            ax.tick_params(axis="x", labelrotation=20)
            ax.set(title=f"{panel.replace('_', ' ')}: {horizon} sessions", ylabel="MSE skill versus reference")
            ax.grid(axis="y", alpha=.2)
    fig.suptitle("Untouched 2021–2026 test sample: fixed price-risk models")
    fig.tight_layout()
    fig.savefig(out / "test_mse_skill.png", dpi=150)
    plt.close(fig)
    intervals = comparisons.loc[comparisons["split"].eq("test") & comparisons["metric"].eq("qlike")].reset_index(drop=True)
    fig, ax = plt.subplots(figsize=(11, 7))
    for position, interval in intervals.iterrows():
        ax.plot([interval["lower"], interval["upper"]], [position, position], color="tab:blue")
        ax.plot(interval["estimate"], position, "o", color="tab:blue")
    ax.set_yticks(range(len(intervals)), [f"{r.panel}, {r.horizon} sessions: {r.model}" for r in intervals.itertuples()])
    ax.axvline(0, color="black", linewidth=.8)
    ax.set(xlabel="Mean QLIKE(model) minus QLIKE(reference)", title="Pointwise 95% moving-block intervals; negative favors model")
    ax.grid(axis="x", alpha=.2)
    fig.tight_layout()
    fig.savefig(out / "test_qlike_intervals.png", dpi=150)
    plt.close(fig)

    text = [
        "# Price-history risk research — chronological physical-risk forecasts", "",
        f"Universe: {', '.join(prices.columns)}. External factors: {', '.join(factors.columns)}. Input sessions: {len(prices):,}, {prices.index.min().date()} through {prices.index.max().date()}.",
        "This is a conditional current-name price-risk study, not a survivorship-free universe backtest or a listed-option trading strategy.",
        "Where BK appears, it is a stable study identifier for the issuer whose exchange ticker changed to BNY in 2026. The data audit records the explicit source-symbol mapping and overlap checks; the risk model does not silently fill missing prices.",
        "## Frozen protocol",
        "Training: 2010–2017. Validation: 2018–2020. Untouched test: 2021–2026-11-04. Parameters are fixed before scores are computed; neither validation nor test outcomes tune the windows, EWMA decay, shrinkage or factors. The protocol file is persisted and hashed before evaluation.",
        "Targets are cumulative next-5/20-session squared log returns. All features use information through the origin close only. Evaluation target intervals are disjoint within each split/horizon; cross-asset dependence is preserved by averaging loss differences at each origin before resampling chronological blocks. Circular moving-block lengths approximate one quarter: 13 forecast origins for 5-session targets and 4 for 20-session targets. Intervals are pointwise and do not establish simultaneous superiority.",
        "Price-return histories are split-adjusted and exclude dividend cash flows. They are vendor histories available now, not an archive of every historical data revision. Market and sector factors are observed SPY/XLF price returns from the same past window.",
        "## Models",
        "Company forecasts: rv_long = mean squared returns over 252 sessions; rv_recent =20 sessions; ewma uses lambda 0.94 with 252-session warmup. Each daily variance is multiplied by the horizon, a fixed persistence approximation rather than a fitted term structure.",
        "Portfolio baseline: sample covariance of the past 252 sessions. Alternatives: fixed 20% diagonal shrinkage; an internal equal-weight financial-return factor; and past-only SPY/XLF factor loadings with diagonal residual covariance. Factor loadings and covariance estimates are refreshed using only the window available at each origin. They do not fit on future factor returns.",
        "The portfolio target is squared return risk for a fixed equal-weight linear return basket, not a traded self-financing NAV. Q option valuation and protective-overlay outcomes are separate later tests. Sample covariance is positive semidefinite; diagonal floors stabilize shrinkage and factor estimates.",
        "QLIKE is log(forecast) + realized/forecast, omitting a target-only constant. Lower is better; raw scores may be negative. MSE is squared variance-prediction error. MSE skill above zero improves over the reference; QLIKE differences below zero improve over the reference.",
        "## Untouched test results",
        _table(test[["panel", "horizon", "model", "n_dates", "mean_qlike", "mean_mse", "mse_skill_vs_baseline", "qlike_difference_vs_baseline"]]),
        "![Test MSE skill](test_mse_skill.png)",
        "## Dependence-aware uncertainty",
        _table(intervals[["panel", "horizon", "model", "baseline", "estimate", "lower", "upper", "n_dates", "block_length"]]),
        "![Test QLIKE intervals](test_qlike_intervals.png)",
        "The complete CSVs include per-company, pooled and portfolio scores for train, validation and test. Findings are reported as observed, including deterioration or inconclusive intervals; no model is selected post hoc from test outcomes.",
        "## Stage and research gates",
        f"Past-only forecasting/covariance implementation and evaluation are complete for the available {len(prices.columns)}-name sample. This supports the price-history baseline component of stages 4–5. Historical universe membership, liquidity eligibility and survivorship coverage remain unverified, so a wider current-name sample does not by itself complete the generalization gate.",
        "Stage 5 incremental macro, option-implied and company-funding features have not been tested. Release/acceptance timestamps, vintage-aware macro observations and issuer/subsidiary mappings remain outstanding. Forecast improvement has not yet been translated into option-hedging value. Stage 6 equity overlays and the stage 7 untouched-period/composition/realistic-execution gate are not passed by this artifact.",
        "## Checks and provenance",
        f"Feature-origin availability and target alignment passed. Minimum observed covariance eigenvalue: {minimum_eigenvalue:.8g}. The accompanying tests include future-price perturbation invariance, external-factor availability, PSD, strict next-horizon targets, split boundaries and non-overlap.",
        "protocol.json records input hashes and parameters. manifest.json records source/data/output identities. No credentials are read or stored by this runner.",
    ]
    (out / "report.md").write_text("\n\n".join(text) + "\n")
    manifest = {
        **frozen, "protocol_sha256": frozen_hash, "checks": checks,
        "source_sha256": {
            str(p.relative_to(ROOT)): _hash(p)
            for p in [ROOT / "src/hedging_harness/risk_models.py", Path(__file__).resolve()]
        },
        "artifacts_sha256": {p.name: _hash(p) for p in sorted(out.iterdir()) if p.is_file()},
    }
    _json(out / "manifest.json", manifest)
    print(json.dumps({"output_dir": str(out), "names": len(prices.columns), "checks": checks}, indent=2))
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prices", type=Path, default=ROOT / "data/market/prices_split_adjusted.csv")
    parser.add_argument("--factors", type=Path, default=ROOT / "data/market/prices_benchmarks.csv")
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    run(args.prices, args.factors, args.output_dir or ROOT / "results" / f"risk-research-{stamp}")


if __name__ == "__main__":
    main()

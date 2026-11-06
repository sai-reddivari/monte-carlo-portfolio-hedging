"""Run dated European model-contract replays using audited underlying prices.

These are model options on historical split-adjusted stock observations, not
historical listed-option quotes or executable-option backtests. Default volatility
uses 252 returns strictly before each replay window. No credentials are read.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

from hedging_harness.configuration import defaults
_DEFAULTS = defaults()['replay']

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from hedging_harness.replay import OptionPosition, replay

WINDOWS = {name: tuple(dates) for name, dates in defaults()['replay_windows'].items()}


def plot_study(study):
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(len(study["windows"]), 2, figsize=(13, 8), squeeze=False)
    for row, window in enumerate(study["windows"]):
        for strategy, label in (("unhedged_equity", "Long equity"), ("protective_puts", "Long equity + model puts")):
            ledger = study["results"][window, strategy].ledger
            axes[row, 0].plot(ledger.index, ledger.cumulative_pnl, label=label)
        short_ledger = study["results"][window, "short_calls_stock_hedged"].ledger
        axes[row, 1].plot(short_ledger.index, short_ledger.cumulative_pnl, color="tab:purple",
                          label="Short model calls + stock hedge")
        for ax in axes[row]:
            ax.axhline(0, color="black", linewidth=.8)
            ax.grid(alpha=.2)
            ax.set_ylabel("Cumulative model P&L ($)")
            ax.tick_params(axis="x", rotation=25)
            ax.legend(fontsize=8)
        axes[row, 0].set_title(window.replace("_", " ") + ": fixed long-equity book")
        axes[row, 1].set_title(window.replace("_", " ") + ": short-call liability study")
    fig.suptitle("Model European contracts on historical stock prices — no historical option quotes")
    fig.tight_layout()
    return fig


def _markdown_table(frame):
    columns = list(frame.columns)
    output = ["| " + " | ".join(columns) + " |", "| " + " | ".join("---" for _ in columns) + " |"]
    for _, row in frame.iterrows():
        formatted = [f"{value:,.4f}" if isinstance(value, (float, np.floating)) else str(value) for value in row]
        output.append("| " + " | ".join(formatted) + " |")
    return "\n".join(output)


def run_study(prices_path=None, *, output_dir=None, calibration_returns=_DEFAULTS['calibration_returns'],
              notional_per_name=_DEFAULTS['notional_per_name'], rate=_DEFAULTS['rate'], cost_bps=_DEFAULTS['cost_bps'], hedge_every=_DEFAULTS['hedge_every'],
              write_outputs=_DEFAULTS['write_outputs'], make_plot=_DEFAULTS['make_plot']):
    prices_path = Path(prices_path or ROOT / "data/market/prices_split_adjusted.csv").resolve()
    history = pd.read_csv(prices_path, index_col="date", parse_dates=["date"])
    prices_sha256 = sha256(prices_path.read_bytes()).hexdigest()
    metadata_path = prices_path.parent / "prices_metadata.json"
    source_metadata = json.loads(metadata_path.read_text()) if metadata_path.is_file() else {}
    source_verified = (
        source_metadata.get("provider") == "FMP"
        and source_metadata.get("adjustment") == "split_adjusted"
        and any(item.get("sha256") == prices_sha256 for item in source_metadata.get("data_files", {}).values())
    )
    data_label = (
        "FMP split-adjusted historical stock closes; synthetic model option contracts"
        if source_verified else "Caller-supplied dated underlying observations; price basis not verified; model contracts"
    )
    if list(history.columns) != ["JPM", "PNC", "GS"]:
        raise ValueError("This small replay study requires canonical JPM,PNC,GS columns in that order.")
    if not history.index.is_unique or not history.index.is_monotonic_increasing or history.isna().any().any():
        raise ValueError("Canonical underlying history must be aligned, complete and increasing.")
    if calibration_returns < 30 or notional_per_name <= 0:
        raise ValueError("Use at least 30 prior calibration returns and positive notional.")
    if output_dir is not None and not write_outputs:
        raise ValueError("output_dir is only used when write_outputs=True.")
    results, calibration_rows, summary_rows, manual_rows, event_frames = {}, [], [], [], []
    checks = []
    for label, (start, end) in WINDOWS.items():
        window = history.loc[start:end].copy()
        if window.empty or window.index[0] != pd.Timestamp(start) or window.index[-1] != pd.Timestamp(end):
            raise ValueError(f"Missing endpoints in declared replay window {label}.")
        earlier = history.loc[history.index < window.index[0]].tail(calibration_returns + 1)
        if len(earlier) != calibration_returns + 1:
            raise ValueError(f"Insufficient strictly earlier calibration history for {label}.")
        log_returns = np.diff(np.log(earlier.to_numpy()), axis=0)
        vols = log_returns.std(axis=0, ddof=1) * np.sqrt(252)
        if not np.isfinite(vols).all() or (vols <= 0).any():
            raise ValueError("Invalid historical-volatility calibration.")
        for name, vol in zip(window.columns, vols):
            calibration_rows.append(dict(
                window=label, name=name, cutoff=earlier.index[-1].date().isoformat(),
                first_observation=earlier.index[0].date().isoformat(),
                replay_start=window.index[0].date().isoformat(),
                price_observations=len(earlier), return_observations=len(log_returns),
                annual_volatility=float(vol),
            ))
        core = {name: notional_per_name / window.iloc[0][name] for name in window.columns}
        common_capital = notional_per_name * len(core)
        calls, puts = [], []
        for name, vol in zip(window.columns, vols):
            shared = dict(underlying=name, strike=float(window.iloc[0][name]), expiry=window.index[-1],
                          volatility=float(vol), multiplier=1.)
            calls.append(OptionPosition(instrument_id=f"{name}_model_call", kind="call", quantity=-core[name], **shared))
            puts.append(OptionPosition(instrument_id=f"{name}_model_put", kind="put", quantity=core[name], **shared))
        cases = {
            "short_calls_stock_hedged": dict(positions=calls, equity_holdings={}, hedge_options=True, initial_capital=0.),
            "unhedged_equity": dict(positions=[], equity_holdings=core, hedge_options=False, initial_capital=common_capital),
            "protective_puts": dict(positions=puts, equity_holdings=core, hedge_options=False, initial_capital=common_capital),
        }
        for strategy, settings in cases.items():
            result = replay(window, hedge_every=hedge_every, cost_bps=cost_bps, rate=rate,
                            as_of=window.index[0], session_calendar=window.index,
                            data_label=data_label,
                            **settings)
            result.provenance["volatility_calibration"] = {
                "method": "sample standard deviation of prior daily log returns times sqrt(252)",
                "cutoff": earlier.index[-1].date().isoformat(),
                "return_observations": calibration_returns,
                "interpretation": "realized-volatility proxy supplied as fixed model sigma; not historical implied volatility",
            }
            results[label, strategy] = result
            ledger = result.ledger
            running_peak = np.maximum.accumulate(np.r_[result.initial_capital, ledger.nav.to_numpy()])[1:]
            summary_rows.append(dict(
                window=label, strategy=strategy, observations=len(window),
                initial_capital=result.initial_capital, terminal_nav=result.terminal_nav,
                terminal_model_pnl=result.terminal_pnl,
                max_drawdown_dollars=float((running_peak - ledger.nav.to_numpy()).max()),
                opening_option_cashflow=float(ledger.opening_option_cashflow.sum()),
                option_settlement_cashflow=float(ledger.option_settlement_cashflow.sum()),
                stock_cost=result.total_stock_cost, stock_turnover=float(ledger.stock_turnover.sum()),
                total_interest=float(ledger.interest.sum()), peak_borrowing=result.peak_borrowing,
            ))
            # Independent cash aggregation from executed stock records and instrument events.
            trade_flows = result.trades.groupby(level="date")[["stock_cashflow", "transaction_cost"]].sum().reindex(window.index, fill_value=0.).astype(float)
            option_flows = result.option_ledger.groupby(level="date")[["opening_cashflow", "settlement_cashflow"]].sum().reindex(window.index, fill_value=0.).astype(float)
            expected_cash = result.initial_capital + (
                ledger.interest + trade_flows.stock_cashflow - trade_flows.transaction_cost
                + option_flows.opening_cashflow + option_flows.settlement_cashflow
            ).cumsum()
            np.testing.assert_allclose(expected_cash, ledger.cash, atol=1e-7, rtol=1e-12)
            terminal_holdings = result.holdings.xs(window.index[-1], level="date")
            assert terminal_holdings.net_shares.eq(0).all()
            assert ledger.iloc[-1].option_value == 0
            # Modify only later prices: earlier decisions and account records must be unchanged.
            pivot = len(window) // 2
            modified_window = window.copy()
            modified_window.iloc[pivot:] *= 1.01
            modified = replay(modified_window, hedge_every=hedge_every, cost_bps=cost_bps,
                              rate=rate, as_of=window.index[0], **settings)
            pd.testing.assert_frame_equal(ledger.iloc[:pivot], modified.ledger.iloc[:pivot])
            # Recompute expiry settlement from observed terminal spot and signed units.
            expiry_cash = sum(position.units * max(
                (window.loc[position.expiry, position.underlying] - position.strike)
                * (1 if position.kind == "call" else -1), 0.) for position in settings["positions"])
            np.testing.assert_allclose(expiry_cash, ledger.option_settlement_cashflow.sum(), atol=1e-7, rtol=1e-12)
            check = dict(window=label, strategy=strategy,
                         cash_from_trade_and_option_records=True, expiry_payoff_recomputed=True,
                         terminal_shares_and_liabilities_zero=True, no_future_info_decisions=True,
                         calibration_strictly_before_replay=earlier.index[-1] < window.index[0])
            checks.append(check)
            selected_dates = sorted({window.index[0], window.index[min(hedge_every,len(window)-1)], window.index[-1]})
            for date in selected_dates:
                row = ledger.loc[date]
                previous_cash = result.initial_capital if date == window.index[0] else ledger.cash.shift(1).loc[date]
                reconstructed = (previous_cash + row.interest + row.opening_option_cashflow
                                 + row.option_settlement_cashflow + row.stock_cashflow - row.transaction_cost)
                manual_rows.append(dict(window=label, strategy=strategy, date=date.date().isoformat(),
                                        previous_cash=previous_cash, interest=row.interest,
                                        option_entry_cashflow=row.opening_option_cashflow,
                                        option_settlement_cashflow=row.option_settlement_cashflow,
                                        core_stock_cashflow=row.core_stock_cashflow,
                                        hedge_stock_cashflow=row.hedge_stock_cashflow,
                                        stock_cost=row.transaction_cost,
                                        reconstructed_cash=reconstructed, recorded_cash=row.cash,
                                        residual=reconstructed-row.cash,
                                        core_equity_value=row.core_equity_value,
                                        hedge_stock_value=row.hedge_stock_value,
                                        option_value=row.option_value, nav=row.nav))
            if not result.option_ledger.empty:
                event_frames.append(result.option_ledger.loc[result.option_ledger.event.isin(["open","settle"])].reset_index().assign(window=label,strategy=strategy))
    summary = pd.DataFrame(summary_rows).set_index(["window","strategy"])
    calibration = pd.DataFrame(calibration_rows).set_index(["window","name"])
    manual = pd.DataFrame(manual_rows)
    checks_frame = pd.DataFrame(checks)
    events = pd.concat(event_frames,ignore_index=True)
    manifest = dict(
        study="European model-contract accounting replay on historical stock prices",
        generated_utc=datetime.now(timezone.utc).isoformat(),
        model_options_are_historical_quoted_options=False,
        historical_option_backtest_gate_passed=False,
        model_contract_accounting_gate_passed=bool(checks_frame.drop(columns=["window","strategy"]).all().all()),
        prices_file=str(prices_path), prices_file_sha256=prices_sha256,
        market_data_source_verified=bool(source_verified),
        source_metadata_file=str(metadata_path) if metadata_path.is_file() else None,
        price_basis=("FMP split-adjusted close; dividends excluded; not a total-return index" if source_verified else "Caller-supplied price basis not verified"),
        historical_sigma_is_implied_volatility=False,
        calibration_returns=calibration_returns, windows=WINDOWS,
        rate=rate, rate_interpretation="constant illustrative model financing rate, not a historical rate observation",
        cost_bps=cost_bps, stock_execution="observe close and transact at same model close plus assumed proportional cost",
        sessions_per_year=252, hedge_every=hedge_every, notional_per_name=notional_per_name,
        core_equity_comparisons_use_same_initial_capital=True,
        protective_puts_automatically_delta_neutralized=False,
        limitations=["No historical option quotes or historical implied volatilities",
                     "No listed-option executable backtest or American exercise claim",
                     "No dividends, split event processing, margin, borrow fees or option spreads",
                     "Source observation index used as session calendar; exchange calendar not independently verified",
                     "Three current survivors and two illustrative historical windows are not an unbiased sector study"],
        runs={f"{window}/{strategy}": result.provenance for (window,strategy),result in results.items()},
        source_sha256={str(Path(__file__).relative_to(ROOT)):sha256(Path(__file__).read_bytes()).hexdigest()},
    )
    study = dict(results=results,summary=summary,calibration=calibration,manual_reconciliation=manual,
                 option_events=events,checks=checks_frame,manifest=manifest,windows=WINDOWS)
    if write_outputs:
        stamp=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        destination=Path(output_dir or ROOT/"results"/f"model-contract-replay-{stamp}").resolve()
        destination.mkdir(parents=True,exist_ok=False)
        for (window,strategy),result in results.items():
            folder=destination/window/strategy
            folder.mkdir(parents=True)
            for name in ("ledger","trades","holdings","option_ledger"):
                getattr(result,name).to_csv(folder/f"{name}.csv")
        summary.to_csv(destination/"summary.csv")
        calibration.to_csv(destination/"calibration.csv")
        manual.to_csv(destination/"manual_reconciliation.csv",index=False)
        events.to_csv(destination/"representative_option_events.csv",index=False)
        checks_frame.to_csv(destination/"checks.csv",index=False)
        if make_plot:
            fig=plot_study(study)
            fig.savefig(destination/"historical_model_contract_replay.png",dpi=150,bbox_inches="tight")
            import matplotlib.pyplot as plt
            plt.close(fig)
        report=("# Model-contract replay: normal and stress windows\n\n"
                "These are synthetic European contracts priced with a fixed prior-realized-volatility proxy "
                f"on {data_label}. They are not historical option quotes or executable "
                "listed-option backtests. Historical stock observations are not risk-neutral simulations.\n\n"
                "## Calibration\n\n"+_markdown_table(calibration.reset_index())+"\n\n"
                "## Account outcomes\n\n"+_markdown_table(summary.reset_index())+"\n\n"
                f"Core-equity comparisons share ${notional_per_name * len(history.columns):,.2f} initial capital. The short-call liability "
                "account starts at zero capital and is a different mandate; its P&L must not be interpreted "
                "as an equity investment return. Protective puts retain their negative delta; they are not "
                "automatically delta-hedged.\n\n"
                "## Independent accounting checks\n\n"+_markdown_table(checks_frame)+"\n\n"
                "Inception, first scheduled rebalance and expiry cash rows are in `manual_reconciliation.csv`. "
                "Each reconstructs previous cash + interest + signed option flows + core/hedge stock cash flows "
                "minus stock cost. Full instrument opening/settlement records are in "
                "`representative_option_events.csv`; all daily account, holding and trade records are retained.\n\n"
                "## Gate boundary\n\n"
                "The small model-contract accounting replay passes its automated reconciliation and causality checks. "
                "A historical listed-option replay remains pending actual timestamped option quotes, implied volatilities "
                "and lifecycle/execution data. Two windows and three surviving names do not establish sector-wide "
                "out-of-sample effectiveness.\n")
        (destination/"report.md").write_text(report)
        manifest["artifacts_sha256"]={str(file.relative_to(destination)):sha256(file.read_bytes()).hexdigest()
                                     for file in sorted(destination.rglob("*")) if file.is_file()}
        (destination/"run_record.json").write_text(json.dumps(manifest,indent=2)+"\n")
        study["output_dir"]=destination
    return study


def main():
    import matplotlib
    matplotlib.use("Agg")
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prices",type=Path)
    parser.add_argument("--output-dir",type=Path)
    parser.add_argument("--calibration-returns",type=int,default=252)
    parser.add_argument("--notional-per-name",type=float,default=100000.)
    parser.add_argument("--rate",type=float,default=.04)
    parser.add_argument("--cost-bps",type=float,default=5.)
    parser.add_argument("--hedge-every",type=int,default=5)
    args=parser.parse_args()
    study=run_study(args.prices,output_dir=args.output_dir,calibration_returns=args.calibration_returns,
                    notional_per_name=args.notional_per_name,rate=args.rate,cost_bps=args.cost_bps,
                    hedge_every=args.hedge_every)
    print(study["summary"].round(4).to_string())
    print(f"Replay accounting checks passed: {study['manifest']['model_contract_accounting_gate_passed']}")
    print(f"Historical listed-option replay gate passed: {study['manifest']['historical_option_backtest_gate_passed']}")
    print(f"Artifacts: {study['output_dir']}")


if __name__=="__main__":
    main()

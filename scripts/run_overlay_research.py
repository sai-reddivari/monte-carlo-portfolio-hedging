"""Stage-6 equity overlay study in two separated phases.

    freeze    Sees prices through the validation end only. Evaluates the training
              and validation windows, selects one policy per family, and writes
              a hashed protocol.
    evaluate  Verifies the protocol, inputs and sources, logs the attempt, then
              evaluates the test windows once. A repeat run, or any changed
              source, needs --revision-note and is reported as test-informed.

Results are European model options on historical underlying prices, not listed
option fills. No credentials are read and nothing is downloaded.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import numpy as np
import pandas as pd

from hedging_harness import overlays as ov

SOURCE_FILES = (
    "hedging_harness/overlays.py", "hedging_harness/replay.py", "hedging_harness/risk_models.py",
    "hedging_harness/uncertainty.py", "BlackScholes_Functions/BlackScholes_D1D2_Price_Payoff_Greeks.py",
    "scripts/run_overlay_research.py",
)
PRE_FREEZE_DISCLOSURES = [
    "The first and last rows of the price panels were displayed before the book was fixed, so 2010 and 2026 price levels were visible. The book therefore holds all ten panel names and assigns side by a business-line rule.",
    "The author has general knowledge of market history after 2020, so the test period is untouched by this protocol but is not unknown history.",
    "The data integrity audit reported only aggregate pass or fail counts for sessions after 2020.",
    "Training and validation outputs could be inspected before freezing. The test split was not evaluated before the protocol hash was recorded.",
    "Freezes equity-overlays-20261106T020955456052Z and equity-overlays-20261106T021350045727Z were superseded before any test evaluation. Inspecting validation output prompted three reporting additions: realized spend against budget, side-specific protection, and results excluding the best window. A hard-coded gate was also replaced by a computed one. No decision rule, candidate or selection changed.",
    "Validation holds 11 windows because a twelfth misses the split end by one session. The frozen rule drops it, and it was left dropped after validation output was seen.",
]
LIMITATIONS = [
    "No historical option quotes or observed implied volatilities. Option prices are Black-Scholes values at an assumed volatility with no skew or term structure.",
    "No option bid/ask charge, because replay has no option execution cost. Purchased protection is therefore flattered.",
    "European cash settlement only. Listed single-name options are American and physically settled.",
    "Split-adjusted closes are not total returns. Dividends received on longs, owed on shorts and owed on a short ETF are excluded, and the option model has no dividend yield.",
    "No stock borrow fee, short rebate spread or margin requirement. Short proceeds earn the full constant rate.",
    "The rate is a constant illustrative 4%, including years when short rates were near zero.",
    "Issuers are current survivors. Historical membership is unavailable, so failed and acquired banks are absent.",
    "Each window is a separate account that buys and liquidates the whole book, which overstates stock turnover against a rolled book.",
    "Holdings are not rebalanced inside a window, so exposure drifts from target.",
    "Window results are not a continuously funded portfolio. No NAV path, CAGR or full-period drawdown is reported.",
]

REQUIRED_FAMILIES = {"unhedged", "reduced_equity", "etf_hedge", "long_puts", "short_calls", "sector_puts",
                     "structures", "risk_informed"}
INK, MUTED, GRID, SURFACE = "#0b0b0b", "#52514e", "#e6e5e0", "#fcfcfb"
SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300"]


def _utc():
    return datetime.now(timezone.utc)


def _json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False, default=float) + "\n")


def _table(frame, digits=3):
    def cell(value):
        if isinstance(value, (bool, np.bool_)):
            return "yes" if value else "no"
        if isinstance(value, (float, np.floating)):
            return "n/a" if not np.isfinite(value) else f"{value:,.{digits}f}"
        return str(value).replace("|", "/")
    columns = [str(column) for column in frame.columns]
    rows = ["| " + " | ".join(cell(value) for value in row) + " |" for row in frame.itertuples(index=False, name=None)]
    return "\n".join(["| " + " | ".join(columns) + " |", "|" + " --- |" * len(columns), *rows])


def _hashes(config, config_path, root):
    data = config["data"]
    inputs = [data["core_prices"], data["benchmark_prices"], *data["metadata_files"]]
    return dict(config_sha256=ov.file_hash(config_path),
                input_sha256={name: ov.file_hash(root / name) for name in inputs},
                source_sha256={name: ov.file_hash(root / name) for name in SOURCE_FILES if (root / name).is_file()})


def _windows_for(config, calendar, sessions=None):
    sessions = sessions or config["windows"]["sessions"]
    lookback, lag = config["estimation"]["lookback"], config["windows"]["decision_lag_sessions"]
    return {split: ov.build_windows(calendar, split, *config["splits"][split], sessions, lookback, lag)
            for split in ("train", "validation", "test")}


def _window_counts(config, windows, calendar):
    rows = []
    for split, items in windows.items():
        rows.append(dict(split=split, windows=len(items), first_start=items[0].start.date().isoformat() if items else "",
                         last_end=items[-1].end.date().isoformat() if items else "",
                         unused_sessions=ov.unused_sessions(items, calendar, *config["splits"][split])))
    return pd.DataFrame(rows)


def _assert_checks(checks, context):
    failed = checks.drop(columns=["key", "label"]).all()
    if not failed.all():
        raise AssertionError(f"Accounting checks failed in {context}: {list(failed[~failed].index)}")


def selected_candidates(protocol):
    """The headline set: both fixed comparators and each selected family winner."""
    by_label = {row["label"]: row for row in protocol["candidates"]}
    primary = next(row["label"] for row in protocol["candidates"] if row.get("primary"))
    labels = [ov.BASELINE, primary, *[item["label"] for item in protocol["selection"].values()]]
    return [by_label[label] for label in labels]


# --------------------------------------------------------------------------- hand reconciliation

def hand_reconciliation(prices, window, candidate, weights, settings, case, windows=()):
    """Rebuild inception, the worst mark and expiry from raw closes, then compare."""
    state = ov.estimate_state(prices, window.decision_date, weights, settings)
    instruction = ov.build_instruction(candidate, state, window, weights, settings)
    result = ov.run_window(prices, window, instruction, settings)
    ledger = result.ledger
    start, end = prices.loc[window.start], prices.loc[window.end]
    shares, capital, rate = instruction.equity_holdings, settings.capital, settings.rate
    bps, year = settings.cost_bps / 10000, settings.sessions_per_year
    stock_paid = sum(units * start[name] for name, units in shares.items())
    entry_cost = sum(abs(units) * start[name] for name, units in shares.items()) * bps
    value = lambda spot_row, position, left: position.units * ov.closed_form_price(
        spot_row[position.underlying], position.strike, left / year, rate, position.volatility, position.kind)
    premium = sum(value(start, position, window.sessions) for position in instruction.positions)
    opening_cash = capital - stock_paid - premium - entry_cost
    rows = []

    def add(stage, item, hand, recorded):
        rows.append(dict(case=case, window=window.key, policy=candidate["label"], stage=stage, item=item,
                         hand=float(hand), ledger=float(recorded), residual=float(hand) - float(recorded)))

    first = ledger.iloc[0]
    add("inception", "stock cash flow", -stock_paid, first["stock_cashflow"])
    add("inception", "option premium cash flow", -premium, first["opening_option_cashflow"])
    add("inception", "stock cost", entry_cost, first["transaction_cost"])
    add("inception", "cash", opening_cash, first["cash"])
    add("inception", "nav", capital - entry_cost, first["nav"])
    inside = ledger.iloc[1:-1]
    step = ledger.index.get_loc(inside["nav"].idxmin())
    adverse_date = ledger.index[step]
    row = prices.loc[adverse_date]
    cash = opening_cash * math.exp(rate * step / year)
    stock_mark = sum(units * row[name] for name, units in shares.items())
    option_mark = sum(value(row, position, window.sessions - step) for position in instruction.positions)
    mark = ledger.loc[adverse_date]
    add(f"adverse {adverse_date.date()}", "cash", cash, mark["cash"])
    add(f"adverse {adverse_date.date()}", "stock value", stock_mark, mark["core_equity_value"])
    add(f"adverse {adverse_date.date()}", "option value", option_mark, mark["option_value"])
    add(f"adverse {adverse_date.date()}", "nav", cash + stock_mark + option_mark, mark["nav"])
    settle = sum(position.units * max((end[position.underlying] - position.strike)
                                      * (1 if position.kind == "call" else -1), 0.0)
                 for position in instruction.positions)
    proceeds = sum(units * end[name] for name, units in shares.items())
    exit_cost = sum(abs(units) * end[name] for name, units in shares.items()) * bps
    before = opening_cash * math.exp(rate * window.sessions / year)
    last = ledger.iloc[-1]
    add("expiry", "option settlement", settle, last["option_settlement_cashflow"])
    add("expiry", "stock proceeds", proceeds, last["stock_cashflow"])
    add("expiry", "stock cost", exit_cost, last["transaction_cost"])
    add("expiry", "terminal nav", before + settle + proceeds - exit_cost, last["nav"])
    add("expiry", "total interest", before - opening_cash, ledger["interest"].sum())
    following = next((item for item in windows if item.start == window.end), None)
    if following is not None:
        again = ov.estimate_state(prices, following.decision_date, weights, settings)
        renewed = ov.build_instruction(candidate, again, following, weights, settings)
        restart = ov.run_window(prices, following, renewed, settings)
        add("roll", "next window opens with common capital, not prior NAV", capital, restart.initial_capital)
    legs = []
    for position in instruction.positions:
        side_shares = shares[position.underlying]
        payoff = position.units * max((end[position.underlying] - position.strike)
                                      * (1 if position.kind == "call" else -1), 0.0)
        legs.append(dict(case=case, window=window.key, policy=candidate["label"], underlying=position.underlying,
                         kind=position.kind, book_shares=side_shares, contracts=position.quantity,
                         multiplier=position.multiplier, option_units=position.units,
                         covered_fraction=abs(position.units / side_shares), strike=position.strike,
                         decision_close=state.spots[position.underlying], execution_close=start[position.underlying],
                         expiry_close=end[position.underlying], pricing_volatility=position.volatility,
                         premium=value(start, position, window.sessions), settlement=payoff,
                         stock_pnl_on_book_shares=side_shares * (end[position.underlying] - start[position.underlying])))
    return pd.DataFrame(rows), pd.DataFrame(legs)


def reconcile_cases(prices, records, windows, protocol, weights, settings, split):
    """Choose adverse windows by a fixed rule, one for each protected side."""
    frame = records.loc[records["split"].eq(split) & records["label"].eq(ov.BASELINE)]
    by_key = {window.key: window for window in windows}
    by_label = {row["label"]: row for row in protocol["candidates"]}
    cases = (("long_downside", "long_equity_pnl", "long_puts"), ("short_upside", "short_equity_pnl", "short_calls"))
    tables, legs = [], []
    for case, column, family in cases:
        key = frame.loc[frame[column].idxmin(), "key"]
        table, leg = hand_reconciliation(prices, by_key[key], by_label[protocol["selection"][family]["label"]],
                                         weights, settings, f"{split}_{case}", windows)
        tables.append(table)
        legs.append(leg)
    return pd.concat(tables, ignore_index=True), pd.concat(legs, ignore_index=True)


# --------------------------------------------------------------------------- plots

def _style(ax):
    ax.set_facecolor(SURFACE)
    ax.grid(color=GRID, linewidth=.7)
    ax.set_axisbelow(True)
    ax.tick_params(colors=MUTED, labelsize=8, length=0)
    for side in ("top", "right", "left", "bottom"):
        ax.spines[side].set_visible(False)
    ax.title.set_color(INK)
    ax.xaxis.label.set_color(MUTED)
    ax.yaxis.label.set_color(MUTED)


def plot_frontier(summary, split, protocol, path):
    """Protection bought per unit of premium, one small multiple per family."""
    import matplotlib.pyplot as plt

    frame = summary.loc[summary["split"].eq(split)].set_index("label")
    base = frame.loc[ov.BASELINE, "es_loss_pct"]
    selected = {item["label"] for item in protocol["selection"].values()}
    mandate = 100 * protocol["config"]["policies"]["mandate_annual_budget"]
    titles = dict(long_puts="Long-name puts", short_calls="Short-name calls", sector_puts="XLF puts",
                  structures="Put spreads and collars", risk_informed="Risk-informed puts")
    fig, axes = plt.subplots(1, len(titles), figsize=(14, 3.7), sharex=True, sharey=True, facecolor=SURFACE)
    for ax, (family, title) in zip(axes, titles.items()):
        _style(ax)
        ax.axhline(0, color=MUTED, linewidth=.9)
        ax.axvline(mandate, color=MUTED, linewidth=.8, linestyle=(0, (3, 3)))
        group = frame.loc[frame["family"].eq(family)]
        for label, row in group.iterrows():
            chosen = label in selected
            marker = "s" if label.startswith("collar") else "o"
            ax.scatter(row["annual_net_premium_pct"], base - row["es_loss_pct"], s=70 if chosen else 34, marker=marker,
                       color=SERIES[0], edgecolor=INK if chosen else SURFACE, linewidth=1.3 if chosen else .8, zorder=3)
            if chosen:
                ax.annotate("selected", (row["annual_net_premium_pct"], base - row["es_loss_pct"]),
                            textcoords="offset points", xytext=(6, 6), fontsize=8, color=INK)
        ax.set_title(title, fontsize=10, loc="left")
        ax.set_xlabel("Net premium, % of capital per year", fontsize=8)
    axes[0].set_ylabel("ES loss reduction vs unhedged, pts", fontsize=8)
    fig.suptitle(f"{split.title()}: protection against premium (dashed line = 2% mandate; squares = collars). {ov.LABEL}.",
                 fontsize=10, color=INK, x=.01, ha="left")
    fig.tight_layout(rect=(0, 0, 1, .95))
    fig.savefig(path, dpi=150, facecolor=SURFACE)
    plt.close(fig)


def plot_window_scatter(records, labels, split, path):
    """Each dot is one window, so shape shows protection and upside give-up."""
    import matplotlib.pyplot as plt

    frame = records.loc[records["split"].eq(split)]
    pivot = frame.pivot(index="key", columns="label", values="pnl_pct")
    shown = [label for label in labels if label != ov.BASELINE]
    columns = 4
    rows = math.ceil(len(shown) / columns)
    fig, axes = plt.subplots(rows, columns, figsize=(13, 3.2 * rows), sharex=True, sharey=True, facecolor=SURFACE,
                             squeeze=False)
    limits = (float(pivot.min().min()) - 1, float(pivot.max().max()) + 1)
    for ax in axes.flat[len(shown):]:
        ax.set_visible(False)
    for ax, label in zip(axes.flat, shown):
        _style(ax)
        ax.plot(limits, limits, color=MUTED, linewidth=.9)
        ax.axhline(0, color=GRID, linewidth=.9)
        ax.axvline(0, color=GRID, linewidth=.9)
        ax.scatter(pivot[ov.BASELINE], pivot[label], s=30, color=SERIES[0], edgecolor=SURFACE, linewidth=.8, zorder=3)
        ax.set_title(label, fontsize=10, loc="left")
        ax.set_xlim(limits)
        ax.set_ylim(limits)
    for ax in axes[-1]:
        ax.set_xlabel("Unhedged window P&L, % of capital", fontsize=8)
    for ax in axes[:, 0]:
        ax.set_ylabel("Policy window P&L, %", fontsize=8)
    fig.suptitle(f"{split.title()}: policy against unhedged by window (diagonal = no change). {ov.LABEL}.",
                 fontsize=10, color=INK, x=.01, ha="left")
    fig.tight_layout(rect=(0, 0, 1, .95))
    fig.savefig(path, dpi=150, facecolor=SURFACE)
    plt.close(fig)


def attribution_table(records, labels, split):
    frame = records.loc[records["split"].eq(split) & records["label"].isin(labels)].copy()
    scale = 100 / frame["initial_capital"]
    parts = dict(long_equity="long_equity_pnl", short_equity="short_equity_pnl", etf_sleeve="etf_pnl",
                 options="option_pnl", interest="interest")
    for name, column in parts.items():
        frame[name] = frame[column] * scale
    frame["stock_costs"] = -frame["stock_cost"] * scale
    frame["total"] = frame["pnl_pct"]
    columns = [*parts, "stock_costs", "total"]
    table = frame.groupby("label", sort=False)[columns].mean()
    return table.reindex(labels).reset_index()


def plot_attribution(table, split, path):
    import matplotlib.pyplot as plt

    parts = ["long_equity", "short_equity", "etf_sleeve", "options", "interest", "stock_costs"]
    frame = table.set_index("label").iloc[::-1]
    fig, ax = plt.subplots(figsize=(11, 4.6), facecolor=SURFACE)
    _style(ax)
    ax.grid(axis="y", visible=False)
    positive = np.zeros(len(frame))
    negative = np.zeros(len(frame))
    for color, part in zip(SERIES, parts):
        values = frame[part].to_numpy()
        left = np.where(values >= 0, positive, negative)
        ax.barh(frame.index, values, left=left, height=.56, color=color, edgecolor=SURFACE, linewidth=2,
                label=part.replace("_", " "))
        positive += np.where(values >= 0, values, 0)
        negative += np.where(values < 0, values, 0)
    ax.scatter(frame["total"], frame.index, color=INK, s=26, zorder=4, label="total")
    ax.axvline(0, color=MUTED, linewidth=.9)
    ax.set_xlabel("Mean per window, % of capital", fontsize=9)
    ax.legend(ncol=7, fontsize=8, frameon=False, loc="upper left", bbox_to_anchor=(0, 1.1), labelcolor=MUTED)
    fig.suptitle(f"{split.title()}: where window P&L came from. {ov.LABEL}.", fontsize=10, color=INK, x=.01, ha="left")
    fig.tight_layout(rect=(0, 0, 1, .96))
    fig.savefig(path, dpi=150, facecolor=SURFACE)
    plt.close(fig)


def plot_pricing(sensitivity, names, path):
    """How much the conclusion moves with the assumed option volatility."""
    import matplotlib.pyplot as plt

    splits = ["validation", "test"]
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.2), sharex=True, sharey=True, facecolor=SURFACE)
    markers = ["o", "s", "^", "D"]
    for ax, split in zip(axes, splits):
        _style(ax)
        ax.grid(axis="y", visible=False)
        frame = sensitivity.loc[sensitivity["split"].eq(split) & sensitivity["scenario"].isin(names)]
        labels = [label for label in frame["label"].unique() if frame.loc[frame["label"].eq(label), "option_policy"].any()]
        rows = {label: index for index, label in enumerate(labels[::-1])}
        for color, marker, name in zip(SERIES, markers, names):
            group = frame.loc[frame["scenario"].eq(name) & frame["label"].isin(labels)]
            ax.scatter(group["es_reduction_pct"], group["label"].map(rows), color=color, marker=marker, s=44,
                       edgecolor=SURFACE, linewidth=.8, label=name, zorder=3)
        ax.set_yticks(list(rows.values()), list(rows.keys()))
        ax.axvline(0, color=MUTED, linewidth=.9)
        ax.set_title(split.title(), fontsize=10, loc="left")
        ax.set_xlabel("ES loss reduction vs unhedged, pts", fontsize=8)
    handles, names_shown = axes[0].get_legend_handles_labels()
    fig.legend(handles, names_shown, ncol=len(names), fontsize=8, frameon=False, labelcolor=MUTED, loc="upper right")
    fig.suptitle(f"Pricing-volatility sensitivity with fixed budgets. {ov.LABEL}.", fontsize=10, color=INK, x=.01, ha="left")
    fig.tight_layout(rect=(0, 0, 1, .93))
    fig.savefig(path, dpi=150, facecolor=SURFACE)
    plt.close(fig)


# --------------------------------------------------------------------------- freeze

def freeze(config_path, output_dir=None, root=ROOT):
    root, config_path = Path(root).resolve(), Path(config_path).resolve()
    config = ov.load_config(config_path)
    panel = ov.load_panel(config, root)
    calendar = panel.index
    validation_end = pd.Timestamp(config["splits"]["validation"][1])
    visible = panel.loc[:validation_end]  # Test closes cannot reach anything below.
    windows = _windows_for(config, calendar)
    weights, settings = ov.signed_weights(config), ov.Settings.from_config(config)
    candidates = ov.expand_candidates(config)
    destination = Path(output_dir or root / "results" / f"equity-overlays-{_utc():%Y%m%dT%H%M%S%fZ}").resolve()
    destination.mkdir(parents=True, exist_ok=False)
    development = windows["train"] + windows["validation"]
    records, checks, _ = ov.evaluate_windows(visible, development, candidates, weights, settings)
    _assert_checks(checks, "freeze")
    tail = config["selection"]["tail_probability"]
    summary = ov.summarize(records, tail)
    selection = ov.select_policies(summary, candidates, config)
    protocol = dict(
        study=config["study"], label=ov.LABEL, frozen_utc=_utc().isoformat(), config=config, candidates=candidates,
        selection=selection, test_windows=[dict(key=item.key, decision_date=item.decision_date.date().isoformat(),
                                                start=item.start.date().isoformat(), end=item.end.date().isoformat())
                                           for item in windows["test"]],
        last_price_visible_to_selection=visible.index[-1].date().isoformat(),
        exchange_calendar_matches=ov.exchange_calendar_matches(calendar, config["data"]["calendar"]),
        panel=dict(first=calendar[0].date().isoformat(), last=calendar[-1].date().isoformat(), sessions=len(calendar),
                   columns=list(panel.columns)),
        pre_freeze_disclosures=PRE_FREEZE_DISCLOSURES, **_hashes(config, config_path, root),
    )
    protocol["config_path"] = str(config_path.relative_to(root)) if config_path.is_relative_to(root) else str(config_path)
    # The validation reconciliation needs the selection, so it runs before the hash is taken.
    reconciliation, legs = reconcile_cases(visible, records, windows["validation"], protocol, weights, settings, "validation")
    records.to_csv(destination / "development_windows.csv", index=False)
    summary.to_csv(destination / "development_summary.csv", index=False)
    checks.to_csv(destination / "development_checks.csv", index=False)
    reconciliation.to_csv(destination / "hand_reconciliation_validation.csv", index=False)
    legs.to_csv(destination / "hand_legs_validation.csv", index=False)
    _window_counts(config, windows, calendar).to_csv(destination / "window_counts.csv", index=False)
    ov.paired_uncertainty(records, [row["label"] for row in selected_candidates(protocol)], config).to_csv(
        destination / "development_uncertainty.csv", index=False)
    ov.tail_episodes(records, tail).to_csv(destination / "development_tail_episodes.csv", index=False)
    _json(destination / "protocol.json", protocol)
    digest = ov.file_hash(destination / "protocol.json")
    (destination / "protocol.sha256").write_text(digest + "\n")
    return destination, digest


# --------------------------------------------------------------------------- evaluate

def verify_protocol(run_dir, root=ROOT):
    """Compare the frozen protocol with the files on disk. Returns any differences."""
    run_dir, root = Path(run_dir).resolve(), Path(root).resolve()
    recorded = (run_dir / "protocol.sha256").read_text().strip()
    digest = ov.file_hash(run_dir / "protocol.json")
    if digest != recorded:
        raise ValueError("protocol.json does not match its recorded hash.")
    protocol = json.loads((run_dir / "protocol.json").read_text())
    config_path = root / protocol["config_path"]
    current = _hashes(protocol["config"], config_path, root)
    changed = [name for key in ("input_sha256", "source_sha256") for name, value in protocol[key].items()
               if current[key].get(name) != value]
    if current["config_sha256"] != protocol["config_sha256"]:
        changed.append(protocol["config_path"])
    return protocol, digest, changed


def _log_attempt(run_dir, digest, changed, revision_note):
    path = Path(run_dir) / "test_evaluation_log.json"
    log = json.loads(path.read_text()) if path.is_file() else []
    if (log or changed) and not revision_note:
        reason = "the test split was already evaluated" if log else f"frozen files changed: {changed}"
        raise PermissionError(f"Refusing test evaluation because {reason}. Pass a revision note to disclose it.")
    log.append(dict(attempt=len(log) + 1, started_utc=_utc().isoformat(), protocol_sha256=digest,
                    changed_files=changed, revision_note=revision_note, test_informed=bool(log)))
    _json(path, log)
    return log


def run_sensitivity(panel, protocol, weights, base):
    """Re-evaluate selected policies under predeclared assumptions, without reselection."""
    config = protocol["config"]
    candidates = selected_candidates(protocol)
    tail = config["selection"]["tail_probability"]
    sensitivity = config["sensitivity"]
    scenarios = [(item["name"], base.with_(pricing=item), None) for item in sensitivity["pricing"]]
    scenarios += [(f"rate_{rate:.2f}", base.with_(rate=rate), None) for rate in sensitivity["rates"]]
    scenarios += [(f"window_{count}", base, count) for count in sensitivity["window_sessions"]]
    frames, all_checks = [], []
    for name, active, sessions in scenarios:
        windows = _windows_for(config, panel.index, sessions)
        chosen = windows["validation"] + windows["test"]
        records, checks, _ = ov.evaluate_windows(panel, chosen, candidates, weights, active)
        all_checks.append(checks.assign(scenario=name))
        summary = ov.summarize(records, tail)
        reference = summary.loc[summary["label"].eq(ov.BASELINE)].set_index("split")["es_loss_pct"]
        summary["es_reduction_pct"] = summary["split"].map(reference) - summary["es_loss_pct"]
        frames.append(summary.assign(scenario=name))
    table = pd.concat(frames, ignore_index=True)
    table["option_policy"] = table["annual_premium_paid_pct"].gt(0)
    return table, pd.concat(all_checks, ignore_index=True)


def gate_table(protocol, checks, sensitivity_checks, reconciliation, log, summary):
    accounting = bool(checks.drop(columns=["key", "label"]).all().all()
                      and sensitivity_checks.drop(columns=["key", "label", "scenario"]).all().all())
    residual = float(reconciliation["residual"].abs().max())
    untouched = len(log) == 1 and not log[-1]["changed_files"]
    test = summary.loc[summary["split"].eq("test")]
    windows = int(test["n_windows"].iloc[0])
    calendar = protocol["exchange_calendar_matches"]
    families = set(test["family"])
    missing = sorted(REQUIRED_FAMILIES - families)
    return [
        dict(gate="Fixed 6-10-name long/short book", status="passed",
             evidence=f"{len(ov.signed_weights(protocol['config']))} names, gross and net validated against issuer weights"),
        dict(gate="Calendar and coverage alignment", status="passed" if calendar else "failed",
             evidence=f"{protocol['panel']['sessions']} sessions, exchange calendar match: {calendar}"),
        dict(gate="Protocol frozen and hashed before test", status="passed",
             evidence=f"Selection saw prices through {protocol['last_price_visible_to_selection']}"),
        dict(gate="Test evaluated once with no later changes", status="passed" if untouched else "failed",
             evidence=f"{len(log)} logged attempt(s), changed files: {log[-1]['changed_files']}"),
        dict(gate="Model-contract accounting", status="passed" if accounting else "failed",
             evidence=f"All window checks true: {accounting}; largest hand residual ${residual:.2e}"),
        dict(gate="All eight comparisons evaluated", status="passed" if not missing else "failed",
             evidence=f"Test families evaluated: {len(families)}; missing: {missing}"),
        dict(gate="Statistical evidence of protection", status="exploratory",
             evidence=f"{windows} test windows and {int(test['tail_windows'].iloc[0])} tail windows"),
        dict(gate="Continuous rolled portfolio NAV", status="not_available",
             evidence="replay opens all options at inception; separate windows only"),
        dict(gate="Listed-option execution backtest", status="blocked",
             evidence="No verified historical option quotes; results are model contracts only"),
        dict(gate="Dividends, borrow, margin, option spreads, American exercise", status="not_modeled",
             evidence="Not supported by replay or the price inputs"),
        dict(gate="Survivorship-safe generalization", status="blocked",
             evidence="Historical membership access denied; current survivors only"),
    ]


def render_report(run_dir, protocol, digest, log, data):
    summary, labels = data["summary"], data["labels"]
    display = ["label", "n_windows", "mean_pnl_pct", "worst_pnl_pct", "es_loss_pct", "worst_max_drawdown_pct",
               "downside_capture", "upside_retained"]
    costs = ["label", "annual_premium_paid_pct", "annual_premium_received_pct", "annual_settlement_net_pct",
             "annual_stock_cost_pct", "annual_interest_pct", "peak_borrowing_pct", "peak_funding_ex_short_proceeds_pct"]
    budgets = ["label", "annual_budget_pct", "annual_net_premium_pct", "worst_window_budget_multiple"]
    exposure = ["label", "mean_gross_exposure_pct", "mean_net_exposure_pct", "mean_etf_exposure_pct",
                "mean_delta_adjusted_net_pct", "mean_beta_net_pct", "mean_target_coverage"]
    pick = lambda split, columns: summary.loc[summary["split"].eq(split) & summary["label"].isin(labels), columns] \
        .set_index("label").reindex(labels).reset_index()
    test_informed = len(log) > 1 or bool(log[-1]["changed_files"])
    status = ("**These test results were revised after an earlier test evaluation or changed frozen files. They are not "
              "untouched out-of-sample evidence.**" if test_informed else
              "The test split was evaluated once, after the protocol hash below was recorded.")
    selection = pd.DataFrame([dict(family=family, selected=item["label"], validation_es_loss_pct=item["validation_es_loss_pct"],
                                   candidates=len(item["candidates_considered"]))
                              for family, item in protocol["selection"].items()])
    sensitivity = data["sensitivity"]
    pricing = sensitivity.loc[sensitivity["option_policy"]].pivot_table(
        index=["split", "label"], columns="scenario", values="es_reduction_pct").reset_index()
    uncertainty = data["uncertainty"]
    parts = [
        f"# Stage 6 equity overlays\n\n**{ov.LABEL}.** Not listed-option fills and not observed implied volatilities.\n",
        f"{status}\n\nProtocol SHA-256: `{digest}`\n",
        "## Window counts\n\n" + _table(data["counts"]) + "\n\nEvery window is a separate account opened with the same capital. "
        "Nothing here is a chained NAV, CAGR or full-period drawdown.\n",
        "## Validation selection\n\n" + _table(selection) + "\n",
        "## Test results by window\n\nValues are % of capital per window. Downside capture is policy loss over unhedged "
        "loss in windows where the unhedged book lost money, so lower is better. Upside retained is the same ratio in "
        "windows where it gained.\n\n" + _table(pick("test", display)) + "\n",
        "## Validation results by window\n\n" + _table(pick("validation", display)) + "\n",
        "## Test costs and financing\n\nAnnual columns are spending rates in % of capital, not compounded returns.\n\n"
        + _table(pick("test", costs)) + "\n",
        "## Realized spend against budget\n\nBudgets are sized at the decision close. Execution is one session later with "
        "the strike already fixed, so realized net premium can differ, most of all for a collar, whose cost is a small "
        "difference between two premiums. Test first, then validation.\n\n" + _table(pick("test", budgets)) + "\n\n"
        + _table(pick("validation", budgets)) + "\n",
        "## Side-specific protection\n\nWhole-book tails fall in sector selloffs, when shorts gain, so they cannot show what "
        "a short-side call does. This table uses windows where the protected side lost money. Capture is side loss with "
        "the option over side loss without it, so lower is better. Values are % of capital.\n\n"
        + _table(data["sides"]) + "\n",
        "## Test exposure\n\n" + _table(pick("test", exposure)) + "\n",
        "## Test P&L attribution\n\nMean per window, % of capital.\n\n" + _table(data["attribution"]) + "\n\n"
        "![Attribution](attribution_test.png)\n",
        "## Frontiers\n\n![Validation frontier](frontier_validation.png)\n\n![Test frontier](frontier_test.png)\n\n"
        "Unselected test grid points are descriptive. None was chosen using test outcomes.\n\n"
        "![Window scatter](window_scatter_test.png)\n",
        "## Dependence-aware uncertainty\n\nDifferences against unhedged use a circular block bootstrap over chronological "
        "windows, with issuers aggregated inside each window. Negative ES differences favor the policy. Intervals are "
        "pointwise. The ex-best column repeats the mean difference without the single most favorable window, which shows "
        "how far a result rests on one episode.\n\n" + _table(uncertainty) + "\n",
        "## Tail episodes\n\nAdjacent tail windows are merged, because one crisis can span windows.\n\n"
        + _table(data["episodes"]) + "\n",
        "## Pricing and design sensitivity\n\nES loss reduction against unhedged, in points. Budgets stay fixed, so dearer "
        "options buy less coverage.\n\n" + _table(pricing) + "\n\n![Pricing](pricing_sensitivity.png)\n",
        "## Sector basis\n\nAn XLF put pays on sector moves. It does not pay for an issuer-specific loss, and it does not "
        "protect short positions against a rally. The ten worst test windows for the book are below, in % of capital.\n\n"
        + _table(data["basis"].loc[data["basis"]["split"].eq("test")].nsmallest(10, "book_pnl_pct")) + "\n",
        "## Hand reconciliation\n\nHand values are rebuilt from raw closes with an erf-based option formula, then compared "
        "with the replay ledger.\n\n" + _table(data["reconciliation"][["case", "stage", "item", "hand", "ledger", "residual"]], 2) + "\n",
        "## Gates\n\n" + _table(pd.DataFrame(data["gates"])) + "\n",
        "## Disclosures\n\n" + "\n".join(f"- {item}" for item in protocol["pre_freeze_disclosures"]) + "\n",
        "## Limitations\n\n" + "\n".join(f"- {item}" for item in LIMITATIONS) + "\n",
    ]
    (Path(run_dir) / "report.md").write_text("\n".join(parts))


def evaluate(run_dir, revision_note=None, root=ROOT):
    import matplotlib
    matplotlib.use("Agg")
    run_dir, root = Path(run_dir).resolve(), Path(root).resolve()
    protocol, digest, changed = verify_protocol(run_dir, root)
    log = _log_attempt(run_dir, digest, changed, revision_note)
    config = protocol["config"]
    panel = ov.load_panel(config, root)
    weights, settings = ov.signed_weights(config), ov.Settings.from_config(config)
    windows = _windows_for(config, panel.index)
    frozen = [dict(key=item.key, decision_date=item.decision_date.date().isoformat(),
                   start=item.start.date().isoformat(), end=item.end.date().isoformat()) for item in windows["test"]]
    if frozen != protocol["test_windows"]:
        raise ValueError("Test windows differ from the frozen protocol.")
    out = run_dir if len(log) == 1 else run_dir / f"revision-{len(log) - 1}"
    out.mkdir(exist_ok=True)
    candidates, tail = protocol["candidates"], config["selection"]["tail_probability"]
    test_records, checks, _ = ov.evaluate_windows(panel, windows["test"], candidates, weights, settings)
    _assert_checks(checks, "test evaluation")
    development = pd.read_csv(run_dir / "development_windows.csv")
    records = pd.concat([development, test_records], ignore_index=True)
    summary = ov.summarize(records, tail)
    labels = [row["label"] for row in selected_candidates(protocol)]
    uncertainty = ov.paired_uncertainty(records.loc[records["split"].isin(["validation", "test"])], labels, config)
    episodes = ov.tail_episodes(records, tail)
    sides = ov.side_protection(records.loc[records["split"].isin(["validation", "test"])], labels)
    sensitivity, sensitivity_checks = run_sensitivity(panel, protocol, weights, settings)
    _assert_checks(sensitivity_checks.drop(columns=["scenario"]), "sensitivity")
    selection = protocol["selection"]
    basis = ov.sector_basis(records, selection["sector_puts"]["label"], selection["long_puts"]["label"])
    reconciliation, legs = reconcile_cases(panel, records, windows["test"], protocol, weights, settings, "test")
    earlier = pd.read_csv(run_dir / "hand_reconciliation_validation.csv")
    reconciliation = pd.concat([earlier, reconciliation], ignore_index=True)
    legs = pd.concat([pd.read_csv(run_dir / "hand_legs_validation.csv"), legs], ignore_index=True)
    attribution = attribution_table(records, labels, "test")
    gates = gate_table(protocol, checks, sensitivity_checks, reconciliation, log, summary)
    counts = _window_counts(config, windows, panel.index)
    for name, frame in dict(windows=records, summary=summary, uncertainty=uncertainty, tail_episodes=episodes,
                            side_protection=sides,
                            sensitivity=sensitivity, sector_basis=basis, hand_reconciliation=reconciliation,
                            hand_legs=legs, attribution_test=attribution, test_checks=checks).items():
        frame.to_csv(out / f"{name}.csv", index=False)
    for split in ("validation", "test"):
        plot_frontier(summary, split, protocol, out / f"frontier_{split}.png")
    plot_window_scatter(records, labels, "test", out / "window_scatter_test.png")
    plot_attribution(attribution, "test", out / "attribution_test.png")
    plot_pricing(sensitivity, [item["name"] for item in config["sensitivity"]["pricing"]], out / "pricing_sensitivity.png")
    render_report(out, protocol, digest, log, dict(
        summary=summary, labels=labels, counts=counts, attribution=attribution, uncertainty=uncertainty,
        episodes=episodes, sides=sides, sensitivity=sensitivity, basis=basis, reconciliation=reconciliation,
        gates=gates))
    artifacts = {str(path.relative_to(out)): ov.file_hash(path) for path in sorted(out.rglob("*"))
                 if path.is_file() and path.name not in {"manifest.json", "gate_status.json", "test_evaluation_log.json"}}
    _json(out / "manifest.json", dict(
        study=protocol["study"], label=ov.LABEL, completed_utc=_utc().isoformat(), protocol_sha256=digest,
        attempt=len(log), test_informed=len(log) > 1 or bool(changed), python=sys.version.split()[0],
        pandas=pd.__version__, numpy=np.__version__, limitations=LIMITATIONS, artifacts_sha256=artifacts))
    # Written last, so a failed plot or report cannot leave a false completion marker.
    _json(out / "gate_status.json", dict(protocol_sha256=digest, gates=gates))
    return dict(output_dir=out, gates=gates, summary=summary, labels=labels)


def main():
    os.environ.setdefault("MPLCONFIGDIR", tempfile.mkdtemp(prefix="mc-mpl-"))
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    frozen = commands.add_parser("freeze", help="Select on validation and record the protocol.")
    frozen.add_argument("--config", type=Path, default=ROOT / "config" / "equity_overlay_study.json")
    frozen.add_argument("--output-dir", type=Path)
    final = commands.add_parser("evaluate", help="Evaluate the frozen protocol on the test split.")
    final.add_argument("--run-dir", type=Path, required=True)
    final.add_argument("--revision-note", help="Required to re-run. The output is disclosed as test-informed.")
    args = parser.parse_args()
    if args.command == "freeze":
        destination, digest = freeze(args.config, args.output_dir)
        print(f"Frozen protocol: {destination}\nSHA-256: {digest}")
        return
    result = evaluate(args.run_dir, args.revision_note)
    for gate in result["gates"]:
        print(f"{gate['status']:<14} {gate['gate']}")
    print(f"Artifacts: {result['output_dir']}")


if __name__ == "__main__":
    main()

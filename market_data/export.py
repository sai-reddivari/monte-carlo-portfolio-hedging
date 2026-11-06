"""Canonical daily price panels for downstream calibration and model replay."""
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path

import pandas as pd

from .fmp import FMPClient
from .coverage import DEFAULT_SYMBOLS, DEFAULT_WINDOWS, check_exchange_calendar


def export_price_panels(client: FMPClient, *, output_dir: str | Path = "data/market",
                        start: str = "2010-01-04", end: str = "2026-11-04",
                        symbols=DEFAULT_SYMBOLS, refresh: bool = False) -> dict:
    """Fetch at most one split-adjusted history per symbol, preserving raw units.

    Dates are explicit study cutoffs. Returns and simulated prices must not be
    substituted for these positive, as-observed split-adjusted stock levels.
    The exported series does not include dividend cash flows.
    """
    if len(pd.bdate_range(start, end)) > 5000:
        raise ValueError("Requested history may exceed FMP's 5,000-record endpoint limit; split the date range explicitly")
    if any(start > window_start or end < window_end for window_start, window_end in DEFAULT_WINDOWS.values()):
        raise ValueError("History must contain both predetermined normal and stress windows")
    output_dir = Path(output_dir)
    datasets = {}
    columns = []
    for symbol in symbols:
        dataset = client.get_prices(symbol, start, end, adjustment="split_adjusted", refresh=refresh)
        if not dataset["records"]:
            raise ValueError("Cannot export an empty symbol history")
        datasets[symbol] = dataset
        frame = pd.DataFrame(dataset["records"])
        series = frame.set_index(pd.to_datetime(frame["date"]))["close"].rename(symbol)
        columns.append(series)
    panel = pd.concat(columns, axis=1).sort_index()
    panel.index.name = "date"
    if panel.index.has_duplicates or not panel.index.is_monotonic_increasing:
        raise ValueError("Export dates must be unique and increasing")
    if panel.isna().any().any():
        raise ValueError("Symbol histories have unaligned dates; refusing to fill or drop missing names")
    calendar_check = check_exchange_calendar(panel.index, start, end)
    if calendar_check.get("exchange_calendar_checked") and not calendar_check["exchange_calendar_validated"]:
        raise ValueError("Price history does not match the expected exchange sessions; see coverage checks")
    output_dir.mkdir(parents=True, exist_ok=True)
    full_path = output_dir / "prices_split_adjusted.csv"
    panel.to_csv(full_path, date_format="%Y-%m-%d")
    artifacts = {"full_history": {"path": str(full_path), "observations": len(panel), "first_date": panel.index[0].strftime("%Y-%m-%d"), "last_date": panel.index[-1].strftime("%Y-%m-%d"), "sha256": sha256(full_path.read_bytes()).hexdigest()}}
    for label, (window_start, window_end) in DEFAULT_WINDOWS.items():
        subset = panel.loc[window_start:window_end]
        if subset.empty:
            raise ValueError("History does not contain an intended replay interval")
        path = output_dir / f"prices_split_adjusted_{label}.csv"
        subset.to_csv(path, date_format="%Y-%m-%d")
        artifacts[label] = {"path": str(path), "observations": len(subset), "first_date": subset.index[0].strftime("%Y-%m-%d"), "last_date": subset.index[-1].strftime("%Y-%m-%d"), "sha256": sha256(path.read_bytes()).hexdigest()}
    metadata = {
        "exported_utc": datetime.now(timezone.utc).isoformat(), "provider": "FMP",
        "adjustment": "split_adjusted", "source_price_field": "close",
        "currency": "USD", "date_index": "unique ascending timezone-naive daily dates",
        "symbols": list(symbols), "requested_start": start, "requested_end": end,
        "dividend_cashflows_included": False, "executable_option_quotes_included": False,
        **calendar_check, "data_files": artifacts,
        "source_metadata": {symbol: dataset["metadata"] for symbol, dataset in datasets.items()},
        "limitations": ["Historical split-adjusted prices are model-replay inputs, not historical option quotes.", "A dividend-adjusted total-return series must not be substituted for stock prices in an option settlement ledger.", "This three-survivor sample is not a survivorship-safe financial-sector universe."],
    }
    metadata_path = output_dir / "prices_metadata.json"
    metadata_path.write_text(json.dumps(metadata, indent=2) + "\n")
    return metadata

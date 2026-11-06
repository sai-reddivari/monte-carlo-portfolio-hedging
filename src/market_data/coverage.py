"""Small-window data coverage checks; no empirical coverage is inferred from docs."""
from __future__ import annotations
from datetime import datetime, timezone
from functools import lru_cache
import math
from typing import Sequence
import numpy as np
import pandas as pd

from .fmp import FMPClient, FMPError

DEFAULT_SYMBOLS = ("JPM", "PNC", "GS")
DEFAULT_WINDOWS = {
    "normal_2019": ("2019-01-02", "2019-03-29"),
    "stress_covid_2020": ("2020-02-03", "2020-04-30"),
}


@lru_cache(maxsize=16)
def _exchange_sessions(start: str, end: str):
    import exchange_calendars as xcals
    calendar = xcals.get_calendar("XNYS", start=start, end=end)
    sessions = calendar.sessions_in_range(start, end)
    if sessions.tz is not None:
        sessions = sessions.tz_localize(None)
    return tuple(sessions.strftime("%Y-%m-%d")), xcals.__version__


def check_exchange_calendar(dates, start: str, end: str) -> dict:
    """Compare the exact observations with a versioned NYSE session calendar."""
    try:
        expected, version = _exchange_sessions(start, end)
    except ImportError:
        return {"exchange_calendar_checked": False, "exchange_calendar_validated": False,
                "exchange_calendar_status": "dependency_required"}
    observed = set(pd.to_datetime(list(dates)).strftime("%Y-%m-%d"))
    missing, unexpected = sorted(set(expected) - observed), sorted(observed - set(expected))
    return {
        "exchange_calendar_checked": True, "exchange_calendar_validated": not missing and not unexpected,
        "calendar": "XNYS", "calendar_package": "exchange_calendars", "calendar_version": version,
        "expected_sessions": len(expected), "missing_expected_sessions": missing, "unexpected_dates": unexpected,
    }


def summarize_prices(records: list[dict], start: str, end: str) -> dict:
    if not records:
        return {"observations": 0, "status": "empty", "first_date": None, "last_date": None}
    frame = pd.DataFrame(records).set_index("date").sort_index()
    if frame.index.has_duplicates:
        raise ValueError("duplicate observation dates")
    prices = frame["close"].to_numpy(dtype=float)
    if not np.isfinite(prices).all() or (prices <= 0).any():
        raise ValueError("prices must be finite and positive")
    log_returns = np.diff(np.log(prices))
    weekdays = pd.bdate_range(start, end).strftime("%Y-%m-%d")
    result = {
        "status": "observed", "observations": len(frame),
        "first_date": str(frame.index[0]), "last_date": str(frame.index[-1]),
        "missing_weekdays_including_possible_exchange_holidays": len(set(weekdays) - set(frame.index)),
        "annualized_log_return_volatility": float(log_returns.std(ddof=1) * math.sqrt(252)) if len(log_returns) > 1 else None,
        "max_abs_one_session_log_return": float(np.abs(log_returns).max()) if len(log_returns) else None,
        "exchange_calendar_validated": False,
    }
    result.update(check_exchange_calendar(frame.index, start, end))
    return result


def audit_market_data(client: FMPClient, *, symbols: Sequence[str] = DEFAULT_SYMBOLS,
                      windows: dict[str, tuple[str, str]] | None = None, refresh: bool = False) -> dict:
    windows = DEFAULT_WINDOWS if windows is None else windows
    rows = []
    datasets = {}
    for label, (start, end) in windows.items():
        for adjustment in ("split_adjusted", "dividend_adjusted"):
            for symbol in symbols:
                row = {"symbol": symbol, "window": label, "start": start, "end": end, "adjustment": adjustment}
                try:
                    dataset = client.get_prices(symbol, start, end, adjustment=adjustment, refresh=refresh)
                    datasets[label, adjustment, symbol] = dataset
                    row.update(summarize_prices(dataset["records"], start, end))
                    row["source_metadata"] = dataset["metadata"]
                except FMPError as error:
                    row.update(status=error.code, http_status=error.http_status, observations=0)
                rows.append(row)
    alignment = []
    for label in windows:
        for adjustment in ("split_adjusted", "dividend_adjusted"):
            date_sets = [set(row["date"] for row in datasets[label, adjustment, symbol]["records"])
                         for symbol in symbols if (label, adjustment, symbol) in datasets]
            complete = len(date_sets) == len(symbols) and all(date_sets)
            alignment.append({
                "window": label, "adjustment": adjustment,
                "all_symbols_available": bool(complete),
                "common_observations": len(set.intersection(*date_sets)) if complete else 0,
                "union_observations": len(set.union(*date_sets)) if date_sets else 0,
                "all_dates_aligned": bool(complete and all(dates == date_sets[0] for dates in date_sets)),
            })
    price_observed = all(row["status"] == "observed" and row["observations"] >= 40 for row in rows)
    aligned = all(row["all_dates_aligned"] for row in alignment)
    calendar_complete = all(row.get("exchange_calendar_validated", False) for row in rows)
    status = "price_sample_observed" if price_observed and aligned and calendar_complete else "credential_required" if all(row["status"] == "credential_required" for row in rows) else "coverage_incomplete"
    return {
        "audited_utc": datetime.now(timezone.utc).isoformat(),
        "status": status, "requests_sent": client.request_count,
        "symbols": list(symbols), "windows": windows, "price_coverage": rows,
        "alignment": alignment,
        "research_gate_2_passed": False,
        "historical_listed_options_gate": {
            "status": "vendor_documented_unavailable",
            "expired_contracts": "not_supported_by_documented_FMP_API",
            "timestamped_historical_bid_ask": "not_supported_by_documented_FMP_API",
            "entitlement": "not_applicable_to_unsupported_product",
            "source": "https://site.financialmodelingprep.com/faqs",
            "source_question": "Does FMP provide options data or Level-2 (Depth of Market) data through the API?",
        },
        "financial_statement_gate": {"status": "not_audited", "point_in_time_release_dates": "unverified"},
        "limitations": [
            "Successful small-window price requests do not establish long-history, delisted-name or historical-option coverage.",
            "Business-day gaps include exchange holidays; use the explicit versioned exchange-calendar fields to distinguish missing sessions.",
            "Dividend-adjusted observations are recorded separately from split-adjusted prices; neither is silently substituted.",
            "The price audit alone cannot pass Research Gate 2, which additionally requires a reconciled replay and validated historical research evidence.",
        ],
    }

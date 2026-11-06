"""One validated model-input source for the notebook sequence."""
from hashlib import sha256
from pathlib import Path

from .core import load_study


def load_named_inputs(path):
    """Return named inputs, named scenario and config without recreating defaults.

    Book remains the validated numerical input container. Dictionaries are a
    readable notebook view of the same validated file, not independent snapshots.
    """
    path = Path(path).resolve()
    book, config = load_study(path)
    portfolio = {
        name: dict(spot=book.spots[i], strike=book.strikes[i],
                   notional=book.notionals[i], pricing_vol=book.pricing_vols[i],
                   days_to_expiration=book.steps,
                   days_in_trading_year=book.sessions_per_year,
                   risk_free_rate=book.rate)
        for i, name in enumerate(book.names)
    }
    corr = config["scenario"]["correlation"]
    scenario = {
        "path_vols": dict(zip(book.names, config["scenario"]["path_vols"])),
        "correlations": {(left, right): corr[i][j]
                         for i, left in enumerate(book.names)
                         for j, right in enumerate(book.names) if j > i},
    }
    config["shared_input_source"] = {
        "path": str(path), "sha256": sha256(path.read_bytes()).hexdigest(),
        "status": config.get("input_status", "unspecified"),
    }
    return portfolio, scenario, config


def input_tables(path):
    """Derived, named research tables from the single authoritative study file.

    The controlled study uses relative session expiries and illustrative market
    observations. Exporting these tables does not turn them into dated quotes.
    """
    import pandas as pd
    portfolio, scenario, config = load_named_inputs(path)
    source = config["shared_input_source"]["sha256"]
    underlyings, instruments, positions, observations = [], [], [], []
    for name, item in portfolio.items():
        instrument_id = f"MODEL::{name}::CALL::{item['days_to_expiration']}S"
        underlyings.append(dict(underlying_id=name, symbol=name, currency="USD",
            calendar="synthetic_252_session_year", classification="illustrative_label"))
        instruments.append(dict(instrument_id=instrument_id, underlying_id=name,
            kind="call", strike=item["strike"], expiry_sessions=item["days_to_expiration"],
            sessions_per_year=item["days_in_trading_year"], exercise="European",
            settlement="cash", multiplier=1., expiry_convention="relative_to_experiment_start"))
        positions.append(dict(portfolio_id="controlled_base", instrument_id=instrument_id,
            signed_quantity=-item["notional"] / item["spot"], multiplier=1.))
        observations.append(dict(snapshot_id="illustrative_start", underlying_id=name,
            spot=item["spot"], pricing_vol=item["pricing_vol"], path_vol=scenario["path_vols"][name],
            financing_rate=item["risk_free_rate"], source_sha256=source, market_observed=False))
    return {"underlyings": pd.DataFrame(underlyings), "instruments": pd.DataFrame(instruments),
            "positions": pd.DataFrame(positions), "model_observations": pd.DataFrame(observations)}


def export_input_tables(path, output_dir):
    """Write inspectable derived views; the shared JSON stays authoritative."""
    import json
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    tables = input_tables(path)
    hashes = {}
    for name, table in tables.items():
        target = output_dir / f"{name}.csv"
        table.to_csv(target, index=False)
        hashes[target.name] = sha256(target.read_bytes()).hexdigest()
    _, _, config = load_named_inputs(path)
    record = {"source": config["shared_input_source"], "derived_views_only": True,
              "files_sha256": hashes}
    (output_dir / "manifest.json").write_text(json.dumps(record, indent=2) + "\n")
    return record

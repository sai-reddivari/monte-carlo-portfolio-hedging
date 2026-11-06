"""05_model_contract_replay: original study operations moved from notebook cells."""
from IPython.display import display
from hedging_harness.configuration import defaults, notebook_controls
from hedging_harness.notebook_views import verify_frozen_overlay, historical_root, historical_path


def run():
    _controls = notebook_controls('05_model_contract_replay')
    from pathlib import Path
    from hashlib import sha256
    import sys
    import json
    import pandas as pd
    import matplotlib
    matplotlib.use("module://matplotlib_inline.backend_inline")
    import matplotlib.pyplot as plt
    from IPython.display import display

    ROOT = Path.cwd()
    if not (ROOT / "hedging_harness" / "replay.py").is_file():
        ROOT = ROOT.parent
    assert (ROOT / "hedging_harness" / "replay.py").is_file(), f"Wrong project root: {ROOT}"
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from scripts.run_model_contract_replay import run_study, plot_study

    PRICES_PATH = ROOT / "data/market/prices_split_adjusted.csv"
    CALIBRATION_RETURNS = _controls['CALIBRATION_RETURNS']
    NOTIONAL_PER_NAME = _controls['NOTIONAL_PER_NAME']
    RATE = _controls['RATE']
    COST_BPS = _controls['COST_BPS']
    HEDGE_EVERY = _controls['HEDGE_EVERY']

    history = pd.read_csv(PRICES_PATH, index_col="date", parse_dates=["date"])
    source_metadata = json.loads((PRICES_PATH.parent / "prices_metadata.json").read_text())
    print(f"Underlying history: {len(history):,} sessions; {history.index[0].date()} to {history.index[-1].date()}")
    print(f"Price basis: {source_metadata['adjustment']}; dividend cashflows included: {source_metadata['dividend_cashflows_included']}")
    display(history.head())

    study = run_study(
        PRICES_PATH, calibration_returns=CALIBRATION_RETURNS,
        notional_per_name=NOTIONAL_PER_NAME, rate=RATE, cost_bps=COST_BPS,
        hedge_every=HEDGE_EVERY, write_outputs=False, make_plot=False,
    )
    assert study["manifest"]["market_data_source_verified"]
    calibration = study["calibration"]
    assert (pd.to_datetime(calibration["cutoff"]) < pd.to_datetime(calibration["replay_start"])).all()
    assert calibration["return_observations"].eq(CALIBRATION_RETURNS).all()
    display(calibration)

    summary = study["summary"]
    display(summary[[
        "observations", "initial_capital", "terminal_nav", "terminal_model_pnl",
        "max_drawdown_dollars", "stock_cost", "peak_borrowing"
    ]].round(4))

    fig = plot_study(study)
    plt.show()

    manual = study["manual_reconciliation"]
    examples = manual.loc[
        (manual["window"].eq("normal_2019") & manual["strategy"].eq("short_calls_stock_hedged"))
        | (manual["window"].eq("stress_covid_2020") & manual["strategy"].eq("protective_puts"))
    ]
    display(examples[[
        "window", "strategy", "date", "previous_cash", "interest", "option_entry_cashflow",
        "option_settlement_cashflow", "core_stock_cashflow", "hedge_stock_cashflow",
        "stock_cost", "recorded_cash", "residual"
    ]].round(6))
    print("Stress-window put opening and settlement events:")
    events = study["option_events"]
    display(events.loc[
        events["window"].eq("stress_covid_2020") & events["strategy"].eq("protective_puts"),
        ["date", "instrument_id", "event", "spot", "signed_units", "opening_cashflow", "settlement_cashflow", "model_value"],
    ].round(6))

    checks = study["checks"]
    assert checks.drop(columns=["window", "strategy"]).all().all()
    display(checks)
    print("Model-contract accounting gate passed:", study["manifest"]["model_contract_accounting_gate_passed"])
    print("Historical listed-option replay gate passed:", study["manifest"]["historical_option_backtest_gate_passed"])

    record = {key: value for key, value in study["manifest"].items() if key != "runs"}
    notebook_path = ROOT / "Hedging_Study_Notebooks/05_model_contract_replay.ipynb"
    notebook_source = json.loads(notebook_path.read_text())
    code_text = "\n\n".join(
        "".join(cell["source"]) for cell in notebook_source["cells"] if cell["cell_type"] == "code"
    )
    record["notebook_code_sha256"] = sha256(code_text.encode()).hexdigest()
    print(json.dumps(record, indent=2))
    return locals()

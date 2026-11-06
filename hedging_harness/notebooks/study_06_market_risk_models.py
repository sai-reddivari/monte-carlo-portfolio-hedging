"""06_market_risk_models: original study operations moved from notebook cells."""
from IPython.display import display
from hedging_harness.configuration import defaults, notebook_controls
from hedging_harness.notebook_views import verify_frozen_overlay, historical_root, historical_path


def run():
    _controls = notebook_controls('06_market_risk_models')
    from pathlib import Path
    from datetime import datetime, timezone
    import sys
    import pandas as pd
    from IPython.display import display, Image

    ROOT = Path.cwd()
    if not (ROOT / "hedging_harness").is_dir():
        ROOT = ROOT.parent
    assert (ROOT / "hedging_harness").is_dir(), f"Wrong project root: {ROOT}"
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from scripts.run_risk_research import run

    PRICES_FILE = ROOT / "data/market/prices_core_10.csv"
    FACTOR_FILE = ROOT / "data/market/prices_benchmarks.csv"
    assert PRICES_FILE.is_file() and FACTOR_FILE.is_file(), "Run the market-data audit/pull first."
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    OUTPUT_DIR = ROOT / "results" / f"risk-research-notebook-{stamp}"

    output = run(PRICES_FILE, FACTOR_FILE, OUTPUT_DIR)
    print(f"Saved empirical research artifacts: {output}")

    scores = pd.read_csv(output / "pooled_scores.csv")
    test_scores = scores.loc[scores["split"].eq("test")]
    display(test_scores[[
        "panel", "horizon", "model", "n_dates", "mean_qlike", "mean_mse",
        "mse_skill_vs_baseline", "qlike_difference_vs_baseline"
    ]])
    display(Image(filename=str(output / "test_mse_skill.png")))

    intervals = pd.read_csv(output / "paired_loss_differences.csv")
    test_intervals = intervals.loc[intervals["split"].eq("test") & intervals["metric"].eq("qlike")]
    display(test_intervals[["panel", "horizon", "model", "baseline", "estimate", "lower", "upper", "n_dates", "block_length"]])
    display(Image(filename=str(output / "test_qlike_intervals.png")))
    return locals()

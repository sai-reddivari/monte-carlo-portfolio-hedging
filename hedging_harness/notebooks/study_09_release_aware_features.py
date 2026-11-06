"""09_release_aware_features: original study operations moved from notebook cells."""
from IPython.display import display
from hedging_harness.configuration import defaults, notebook_controls
from hedging_harness.notebook_views import verify_frozen_overlay, historical_root, historical_path


def run():
    _controls = notebook_controls('09_release_aware_features')
    from pathlib import Path
    from datetime import datetime, timezone
    import json
    import sys
    import pandas as pd
    from IPython.display import display, Image

    ROOT = Path.cwd()
    if not (ROOT / "hedging_harness").is_dir():
        ROOT = ROOT.parent
    assert (ROOT / "hedging_harness").is_dir(), f"Wrong project root: {ROOT}"
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from scripts.run_feature_research import run

    PRICES_FILE = ROOT / "data/market/prices_core_10.csv"
    FACTOR_FILE = ROOT / "data/market/prices_benchmarks.csv"
    SEC_FILE = ROOT / "data/market/features/sec_facts_core10/sec_filing_snapshots.csv"
    assert PRICES_FILE.is_file() and FACTOR_FILE.is_file() and SEC_FILE.is_file()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    OUTPUT_DIR = ROOT / "results" / f"feature-research-notebook-{stamp}"

    output = run(PRICES_FILE, FACTOR_FILE, OUTPUT_DIR, include_sec_core10=True)
    print(f"Saved feature research: {output}")

    coverage = pd.read_csv(output / "cohort_coverage.csv")
    display(coverage)
    locked = json.loads((output / "selected_models.json").read_text())
    selected = pd.DataFrame(locked["models"])
    display(selected[["cohort", "horizon", "model", "alpha", "validation_mean_qlike", "training_latest_target", "validation_latest_target"]])

    scores = pd.read_csv(output / "scores.csv")
    test_scores = scores.loc[scores["split"].eq("test")]
    display(test_scores)
    intervals = pd.read_csv(output / "paired_loss_differences.csv")
    incremental = intervals.loc[
        intervals["split"].eq("test") & intervals["metric"].eq("qlike")
        & intervals["left_model"].isin(["ridge_balance_sheet", "ridge_interactions"])
        & intervals["reference"].isin(["ridge_market_sector", "ridge_balance_sheet"])
    ]
    display(incremental[["cohort", "horizon", "left_model", "reference", "estimate", "lower", "upper", "n_dates", "block_length"]])
    display(Image(filename=str(output / "test_qlike_intervals.png")))

    trace = pd.read_csv(output / "financial_availability_trace.csv")
    display(trace.head(12))
    checks = json.loads((output / "checks.json").read_text())
    display(pd.Series(checks).to_frame("value"))
    return locals()

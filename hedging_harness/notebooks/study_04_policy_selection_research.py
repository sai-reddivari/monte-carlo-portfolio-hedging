"""04_policy_selection_research: original study operations moved from notebook cells."""
from IPython.display import display
from hedging_harness.configuration import defaults, notebook_controls
from hedging_harness.notebook_views import verify_frozen_overlay, historical_root, historical_path


def run():
    _controls = notebook_controls('04_policy_selection_research')
    from pathlib import Path
    from hashlib import sha256
    from datetime import datetime, timezone
    import sys
    import json

    import pandas as pd
    from IPython.display import Image, display

    ROOT = Path.cwd()
    if not (ROOT / "hedging_harness" / "research.py").is_file():
        ROOT = ROOT.parent
    assert (ROOT / "hedging_harness" / "research.py").is_file()
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from hedging_harness.research import load_protocol, run_release

    PROTOCOL = ROOT / "config" / "research_release_1.json"
    RELEASE_DIR = ROOT / "results" / "research-release-1" / "release-1"
    RUN_NEW_EXPERIMENT = _controls['RUN_NEW_EXPERIMENT']

    spec, book, scenario, policies, study_path = load_protocol(PROTOCOL)
    print(spec["research_question"])
    print(f"Expected financed cost budget: ${spec['cost_budget_dollars']:,.0f}; one-way stock charge: {spec['cost_bps']:g} bp")
    print(f"Selection: {spec['selection']}; evaluation: {spec['evaluation']}")
    display(pd.DataFrame(spec["candidates"]).fillna("not used"))

    from hedging_harness.notebook_views import load_cached_release
    RELEASE_DIR, selected, selection, evaluation, gate = load_cached_release(PROTOCOL, study_path, RELEASE_DIR, ROOT, RUN_NEW_EXPERIMENT=RUN_NEW_EXPERIMENT, run_release=run_release)

    columns = ["policy", "loss_es95", "pnl_std", "mean_pnl", "mean_financed_cost", "cost_mean_upper", "budget_feasible"]
    print("Selection sample:")
    display(selection[columns].round(4))
    print("Held-out evaluation sample:")
    display(evaluation[columns].round(4))
    print("Locked-policy evaluation:")
    display(evaluation.loc[evaluation["policy"].eq(selected), columns].round(4))

    tail_differences = pd.read_csv(RELEASE_DIR / "paired_tail_differences.csv")
    mean_differences = pd.read_csv(RELEASE_DIR / "paired_mean_differences.csv")
    print("Paired ES95 differences:")
    display(tail_differences[["benchmark", "estimate", "lower", "upper", "bootstrap_se"]].round(4))
    print("Paired mean-P&L differences:")
    display(mean_differences.round(4))
    print("Selected-policy economic-risk intervals:")
    display(pd.DataFrame(json.loads((RELEASE_DIR / "selected_risk_intervals.json").read_text())).round(4))

    display(Image(filename=str(RELEASE_DIR / "cost_risk.png")))
    display(Image(filename=str(RELEASE_DIR / "peak_funding.png")))
    display(evaluation[["policy", "mean_turnover", "mean_trades", "mean_peak_borrowing", "peak_borrowing_p95", "max_peak_borrowing"]].round(3))

    display(pd.read_csv(RELEASE_DIR / "accounting_checks.csv").round(10))
    print(json.dumps(gate, indent=2))
    chosen = evaluation.loc[evaluation["policy"].eq(selected)].iloc[0]
    print(f"Locked policy {selected}: ES95 ${chosen['loss_es95']:,.2f}; expected financed cost ${chosen['mean_financed_cost']:,.2f}")
    print("Standalone report:", RELEASE_DIR / "report.md")
    print("Independent validation:", ROOT / "docs" / "independent_validation.md")
    return locals()

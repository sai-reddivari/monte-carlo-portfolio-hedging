"""08_breadth_and_composition: original study operations moved from notebook cells."""
from IPython.display import display
from hedging_harness.configuration import defaults, notebook_controls
from hedging_harness.notebook_views import verify_frozen_overlay, historical_root, historical_path


def run():
    _controls = notebook_controls('08_breadth_and_composition')
    from pathlib import Path
    from hashlib import sha256
    import sys
    import json

    import numpy as np
    import pandas as pd
    import matplotlib
    matplotlib.use("module://matplotlib_inline.backend_inline")
    import matplotlib.pyplot as plt
    from IPython.display import display

    ROOT = Path.cwd()
    if not (ROOT / "hedging_harness" / "breadth.py").is_file():
        ROOT = ROOT.parent
    assert (ROOT / "hedging_harness" / "breadth.py").is_file(), f"Wrong project root: {ROOT}"
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from scripts.run_breadth_research import plot_study

    STUDY_DIR = ROOT / "results/breadth-20261106T020730752645Z"
    manifest = json.loads((STUDY_DIR / "manifest.json").read_text())
    protocol_bytes = (STUDY_DIR / "protocol.json").read_bytes()
    protocol = json.loads(protocol_bytes)
    assert sha256(protocol_bytes).hexdigest() == manifest["protocol_sha256"]
    for name, digest in manifest["artifacts_sha256"].items():
        assert sha256((STUDY_DIR / name).read_bytes()).hexdigest() == digest, name
    for name, digest in protocol["source_sha256"].items():
        assert sha256((historical_root() / name).read_bytes()).hexdigest() == digest, name

    for name, digest in protocol["data_sha256"].items():
        assert sha256((historical_root() / name).read_bytes()).hexdigest() == digest, name
    assert sha256(historical_path(protocol["locked_selection_path"]).read_bytes()).hexdigest() == protocol["locked_selection_sha256"]

    summary = pd.read_csv(STUDY_DIR / "policy_summary.csv")
    paired = pd.read_csv(STUDY_DIR / "paired_ES_differences.csv")
    availability = pd.read_csv(STUDY_DIR / "availability_audit_all_50.csv")
    master_scenarios = pd.read_csv(STUDY_DIR / "master_scenarios.csv")
    historical_summary = pd.read_csv(STUDY_DIR / "historical_equity_summary.csv")
    print("Frozen source and artifact hashes verified.")
    print(f"Policy cases: {manifest['policy_cases']}; master simulations: {manifest['master_simulations']}")

    assert len(availability) == 50
    assert availability["included_in_complete_master"].sum() == 42
    print("Excluded partial histories, with missing observations retained:")
    display(availability.loc[~availability["included_in_complete_master"]])
    print("Canonical master begins:", protocol["master_names"][:10])
    print("Composition seeds:", protocol["composition_seeds"])

    vols = pd.read_csv(STUDY_DIR / "calibrated_annual_volatilities.csv", index_col=0)
    print("Calibration cutoff:", protocol["calibration_cutoff"])
    print("Last calibration observation:", protocol["calibration_last_observation"])
    print("Covariance model:", protocol["covariance_model"])
    display(vols.head(10))
    display(master_scenarios)
    assert master_scenarios["names"].eq(42).all()
    assert master_scenarios["n_paths"].eq(protocol["n_paths"]).all()
    np.testing.assert_allclose(summary["total_notional"], protocol["total_notional"])
    print(f"All books retain ${protocol['total_notional']:,.0f} total initial underlying notional.")

    assert not protocol["policy_reselected"]
    canonical = summary.loc[summary["composition"].eq("canonical")]
    display(canonical[[
        "scenario", "breadth", "policy", "mean_pnl", "pnl_std", "loss_es95",
        "mean_financed_cost", "cost_mean_upper", "cost_budget_upper_bound_passes"
    ]].round(4))
    fig = plot_study({"summary": summary, "protocol": protocol})
    plt.show()

    display(paired.loc[
        paired["composition"].eq("canonical") & paired["breadth"].eq(40),
        ["scenario", "left_policy", "right_policy", "estimate", "lower", "upper", "bootstrap_se"],
    ].round(4))
    print("Negative estimates favor the locked policy under this conditional loss statistic.")

    display(historical_summary.loc[historical_summary["composition"].eq("canonical"), [
        "breadth", "periods", "tail_observations", "mean_20_session_pnl", "pnl_std",
        "loss_es95", "es95_block_lower", "es95_block_upper", "industry_weight_hhi",
        "largest_current_industry_tail_contributor"
    ]].round(4))
    periods = pd.read_csv(STUDY_DIR / "historical_equity_periods.csv", parse_dates=["origin", "target_start", "target_end"])
    for _, group in periods.groupby(["composition", "breadth"]):
        group = group.sort_values("origin")
        assert (group["target_start"] > group["origin"]).all()
        assert (group["target_start"].iloc[1:].to_numpy() > group["target_end"].iloc[:-1].to_numpy()).all()
    print("Historical return intervals are non-overlapping within each composition/breadth.")

    assert manifest["conditional_breadth_computation_passed"]
    assert not manifest["full_stage7_gate_passed"]
    assert not manifest["point_in_time_membership_verified"]
    assert not manifest["overlay_generalization_evidence_included"]
    record = {key: value for key, value in manifest.items() if key != "artifacts_sha256"}
    notebook_path = ROOT / "Hedging_Study_Notebooks/08_breadth_and_composition.ipynb"
    notebook_source = json.loads(notebook_path.read_text())
    code_text = "\n\n".join(
        "".join(cell["source"]) for cell in notebook_source["cells"] if cell["cell_type"] == "code"
    )
    record["notebook_code_sha256"] = sha256(code_text.encode()).hexdigest()
    print(json.dumps(record, indent=2))
    return locals()

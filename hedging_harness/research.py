"""Frozen, budget-aware policy selection and independent simulation evaluation."""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .core import load_study, simulate_paths, hedge, summarize, provenance, paired_difference
from .policies import HedgePolicy
from .uncertainty import mean_interval, paired_tail_difference, risk_interval


def _json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def _digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def load_protocol(path):
    """Read and validate all decisions before either sample is generated."""
    path = Path(path).resolve()
    spec = json.loads(path.read_text())
    if spec.get("schema_version") != 1:
        raise ValueError("Unsupported research-protocol schema.")
    if spec.get("objective") != "minimize_selection_ES95_subject_to_cost_upper_bound":
        raise ValueError("Unknown pre-specified objective.")
    if spec.get("tail_probability") != .05:
        raise ValueError("This release uses summarize's ES95, so tail_probability must equal .05.")
    for key in ("cost_budget_dollars", "cost_bps"):
        if isinstance(spec[key], bool) or not np.isfinite(spec[key]) or spec[key] < 0:
            raise ValueError(f"{key} must be finite and nonnegative.")
    if spec["confidence"] != .95:
        raise ValueError("Release 1 uses fixed 95% intervals; confidence must equal .95.")
    for sample in ("selection", "evaluation"):
        for key, minimum in (("seed", 0), ("n_paths", 2)):
            value = spec[sample][key]
            if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
                raise ValueError(f"Invalid {sample} {key}.")
    if spec["selection"]["seed"] == spec["evaluation"]["seed"]:
        raise ValueError("Selection and evaluation require distinct seeds.")
    b = spec["bootstrap"]
    if not isinstance(b["n_resamples"], int) or isinstance(b["n_resamples"], bool) or b["n_resamples"] < 2:
        raise ValueError("At least two bootstrap resamples are required.")
    if not isinstance(b["seed"], int) or isinstance(b["seed"], bool) or b["seed"] < 0:
        raise ValueError("Invalid bootstrap seed.")
    policies = [HedgePolicy(**item) for item in spec["candidates"]]
    labels = [p.label for p in policies]
    if not policies or None in labels or len(set(labels)) != len(labels):
        raise ValueError("Candidate labels must be nonempty and unique.")
    if not set(spec["benchmark_labels"]).issubset(labels):
        raise ValueError("Benchmarks must be pre-specified candidates.")
    if not isinstance(spec["audit_path"], int) or isinstance(spec["audit_path"], bool) or not 0 <= spec["audit_path"] < min(spec["selection"]["n_paths"], spec["evaluation"]["n_paths"]):
        raise ValueError("Audit path is outside a sample.")
    study_path = (path.parent / spec["study_file"]).resolve()
    book, config = load_study(study_path)
    return spec, book, config["scenario"], policies, study_path


def select_policy(table, budget):
    """Select ONLY from selection metrics, with a deterministic tie break."""
    required = {"policy", "loss_es95", "mean_financed_cost", "cost_mean_upper"}
    if not required.issubset(table.columns):
        raise ValueError("Missing policy-selection columns.")
    eligible = table.loc[table["cost_mean_upper"] <= budget]
    if eligible.empty:
        raise ValueError("No candidate satisfies the pre-specified cost constraint; do not relax it after evaluation.")
    return str(eligible.sort_values(
        ["loss_es95", "mean_financed_cost", "policy"], kind="stable"
    ).iloc[0]["policy"])


def _check_account(book, result, zero):
    """Reconcile audit cash and all-outcome financed costs, including bands."""
    paired_difference(result, zero)  # Reject different actual paths/order.
    cost_residual = zero.terminal_pnl - result.terminal_pnl - result.financed_costs
    np.testing.assert_allclose(cost_residual, 0, atol=1e-8, rtol=0)
    cash_error = 0.
    value_error = 0.
    for _, frame in result.ledger.groupby("name", sort=False):
        flows = frame.premium_received + frame.interest + frame.stock_cashflow - frame.transaction_cost - frame.payoff_paid
        cash_error = max(cash_error, float(np.abs(frame.cash.to_numpy() - flows.cumsum().to_numpy()).max()))
        value_error = max(value_error, float(np.abs(frame.net_value - frame.cash - frame.stock_value + frame.option_liability).max()))
        if frame.iloc[-1].shares_after != 0 or frame.iloc[-1].option_liability != 0:
            raise AssertionError("Unsettled terminal account.")
    np.testing.assert_allclose([cash_error, value_error], 0, atol=1e-8, rtol=0)
    final_cash = result.ledger.loc[result.ledger.step.eq(book.steps), "cash"].sum()
    # The caller verifies its configured audit index separately.
    return {"max_cash_residual": cash_error, "max_marked_value_residual": value_error,
            "max_financed_cost_residual": float(np.abs(cost_residual).max()),
            "audit_final_cash": float(final_cash)}


def _run_sample(book, scenario, policies, sample, spec, label):
    paths = simulate_paths(book, **scenario, **sample)
    results, rows, checks = {}, [], []
    for policy in policies:
        result = hedge(book, paths, policy=policy, cost_bps=spec["cost_bps"],
                       audit_path=spec["audit_path"], scenario_label=label)
        zero = hedge(book, paths, policy=policy, cost_bps=0.)
        check = _check_account(book, result, zero)
        np.testing.assert_allclose(check["audit_final_cash"], result.terminal_pnl[spec["audit_path"]].sum(), atol=1e-8, rtol=0)
        metrics = summarize(result).loc["Portfolio"].to_dict()
        cost = mean_interval(result.financed_costs.sum(axis=1), spec["confidence"])
        rows.append({"policy": policy.label, "kind": policy.kind, **metrics,
                     "cost_mean_se": cost["se"], "cost_mean_lower": cost["lower"],
                     "cost_mean_upper": cost["upper"],
                     "budget_feasible": cost["upper"] <= spec["cost_budget_dollars"],
                     "scenario_id": result.scenario_id})
        checks.append({"sample": label, "policy": policy.label, **check})
        results[policy.label] = result
    ids = {r.scenario_id for r in results.values()}
    if len(ids) != 1:
        raise AssertionError("Policy cases must share identical realized paths.")
    return pd.DataFrame(rows), results, pd.DataFrame(checks)


def _table(frame, columns):
    frame = frame.loc[:, columns]
    def fmt(value):
        if isinstance(value, (float, np.floating)):
            return f"{value:,.3f}"
        return str(value).replace("|", "/")
    lines = ["| " + " | ".join(columns) + " |", "| " + " | ".join("---" for _ in columns) + " |"]
    lines += ["| " + " | ".join(fmt(value) for value in row) + " |" for row in frame.itertuples(index=False, name=None)]
    return "\n".join(lines)


def _plots(out, evaluation, selected, budget):
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(10, 5.5))
    colors = {"periodic": "tab:blue", "delta_band": "tab:orange", "maturity_band": "tab:green"}
    for kind, group in evaluation.groupby("kind", sort=False):
        ax.scatter(group.mean_financed_cost, group.loss_es95, label=kind.replace("_", " "),
                   color=colors[kind], s=55)
        for row in group.itertuples():
            if kind == "periodic":
                ax.annotate(row.policy, (row.mean_financed_cost, row.loss_es95),
                            xytext=(5, 5), textcoords="offset points", fontsize=8)
    chosen = evaluation.loc[evaluation.policy.eq(selected)].iloc[0]
    ax.scatter([chosen.mean_financed_cost], [chosen.loss_es95], marker="*", s=240,
               color="red", edgecolor="black", label=f"Locked: {selected}", zorder=5)
    ax.axvline(budget, color="black", linestyle="--", linewidth=1, label="Expected-cost budget")
    ax.set(xlabel="Evaluation mean financed stock cost ($)", ylabel="Evaluation portfolio ES95 loss ($)",
           title="Pre-specified hedge policies on untouched evaluation paths")
    ax.legend(fontsize=8)
    ax.grid(alpha=.2)
    fig.tight_layout()
    fig.savefig(out / "cost_risk.png", dpi=160)
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(10, 4.8))
    order = evaluation.sort_values("mean_peak_borrowing")
    ax.barh(order.policy, order.mean_peak_borrowing, color=["tab:red" if p == selected else "tab:blue" for p in order.policy])
    ax.set(xlabel="Mean concurrent portfolio peak borrowing ($)", title="Observed-event funding requirements")
    ax.grid(axis="x", alpha=.2)
    fig.tight_layout()
    fig.savefig(out / "peak_funding.png", dpi=160)
    plt.close(fig)


def _report(out, spec, book, selection, evaluation, selected, tails, means, risk, gate):
    chosen = evaluation.loc[evaluation.policy.eq(selected)].iloc[0]
    columns = ["policy", "loss_es95", "pnl_std", "mean_pnl", "mean_financed_cost", "cost_mean_upper", "budget_feasible"]
    lines = [
        "# Research Release 1 — budget-aware hedge selection",
        "",
        f"Gate status: **{gate['status']}** for the controlled synthetic study. Human review is a separate next step.",
        "",
        f"Locked choice: **{selected}**. Objective: minimize selection-sample ES95 subject to a ${spec['cost_budget_dollars']:,.0f} expected financed stock-cost budget.",
        f"The book has {len(book.names)} short synthetic European calls, ${sum(book.notionals):,.0f} initial underlying notional, {book.steps} trading sessions and a {spec['cost_bps']:g}bp one-way stock charge.",
        "",
        "## Protocol and separation",
        f"The fixed {len(selection)}-policy candidate set was evaluated on {spec['selection']['n_paths']:,} selection outcomes (seed {spec['selection']['seed']}). selection.json was written and hashed before generating the {spec['evaluation']['n_paths']:,} held-out evaluation outcomes (seed {spec['evaluation']['seed']}). No evaluation-based reselection occurs.",
        "The cost screen uses the upper endpoint of a two-sided 95% normal Monte Carlo interval (a 97.5% one-sided endpoint), not a hard per-path cap or simultaneous guarantee across candidates. Evaluation feasibility is assessed again without changing the locked choice.",
        "The fixed delta band is absolute hedge-share discrepancy divided by option units. The maturity-sensitive band multiplies that threshold by sqrt(remaining maturity / initial maturity). Both open and settle unconditionally.",
        "",
        "## Selection results",
        _table(selection, columns),
        "",
        "## Untouched evaluation results",
        _table(evaluation, columns),
        "",
        f"The locked policy's evaluation budget status is **{bool(chosen.budget_feasible)}**. A false status would be reported as a budget miss, not corrected by switching policies on evaluation data.",
        "",
        "![Evaluation cost-risk comparison](cost_risk.png)",
        "",
        "## Incremental protection and uncertainty",
        "Each row is ES95(selected) minus ES95(benchmark). Negative values favor the selected rule. Paired bootstrap resamples use common economic-outcome indices and recompute each policy's own worst tail. These are pointwise percentile intervals conditional on the fixed model/policies, not a simultaneous dominance claim or an ES of the P&L difference.",
        _table(tails, ["benchmark", "estimate", "lower", "upper", "bootstrap_se"]),
        "",
        "Mean net-P&L differences use separate paired mean intervals; negative values mean lower selected-policy average net P&L:",
        _table(means, ["benchmark", "mean_difference", "paired_se", "mc_95_low", "mc_95_high"]),
        "",
        "Selected-policy economic risk intervals:",
        _table(pd.DataFrame(risk), ["metric", "estimate", "lower", "upper", "bootstrap_se"]),
        "",
        "## Trading and financing",
        _table(evaluation, ["policy", "mean_turnover", "mean_trades", "mean_peak_borrowing", "peak_borrowing_p95", "max_peak_borrowing"]),
        "Shared peak funding is the maximum negative aggregate contemporaneous cash, not the sum of separate per-name maxima. The engine observes after interest and after combined trades/costs/settlement; intraday execution order and margin are outside scope.",
        "",
        "![Peak financing comparison](peak_funding.png)",
        "",
        "## Accounting and reproducibility",
        "All candidate ledgers reconcile cash flows, marked value, expiry settlement and the all-outcome financed-cost identity. Pairing verifies fingerprints of the actual stock paths and asset order. protocol.json, selection.json, provenance.json, gate_status.json, CSV tables and selected audit ledgers accompany this report.",
        "",
        "## Interpretation and limits",
        "Adaptive rules purchase different residual-risk/cost combinations. Any improvement or inconclusive interval is a valid controlled-study result; the code does not label the largest sample mean an optimal trading strategy. All outputs are conditional on illustrative constant-volatility Q-GBM, zero dividends, common European expiry and simplified stock execution/funding. Sampling intervals omit calibration and model uncertainty. This gate does not establish historical profitability, a market-data gate, a listed-option backtest or stages 3–7.",
        "Historical data, release-aware forecast testing, explicit equity overlays and survivorship-aware breadth are separate evidence requirements. The initial cost budget is an experiment assumption, not an authorization to spend money or trade.",
    ]
    (out / "report.md").write_text("\n\n".join(lines) + "\n")


def run_release(protocol_path, output_dir):
    """Run selection, persist its lock, then evaluate without reselecting."""
    protocol_path = Path(protocol_path).resolve()
    spec, book, scenario, policies, study_path = load_protocol(protocol_path)
    out = Path(output_dir).resolve()
    out.mkdir(parents=True, exist_ok=False)
    _json(out / "protocol.json", spec)
    source_record = provenance(book, scenario, spec["selection"]["seed"], spec["selection"]["n_paths"])
    protocol_record = {"protocol_sha256": _digest(protocol_path), "study_sha256": _digest(study_path),
                       "protocol_file": str(protocol_path), "study_file": str(study_path),
                       "frozen_before_selection_utc": datetime.now(timezone.utc).isoformat(),
                       "source": source_record}
    _json(out / "protocol_commitment.json", protocol_record)
    selection, selection_results, checks1 = _run_sample(book, scenario, policies, spec["selection"], spec, "selection")
    selection.to_csv(out / "selection_metrics.csv", index=False)
    selected = select_policy(selection, spec["cost_budget_dollars"])
    locked = {"selected_policy": selected, "policy": asdict(next(p for p in policies if p.label == selected)),
              "selection_scenario_id": selection_results[selected].scenario_id,
              "selection_seed": spec["selection"]["seed"], "evaluation_seed": spec["evaluation"]["seed"],
              "budget_dollars": spec["cost_budget_dollars"], "budget_screen": "upper endpoint of two-sided normal mean CI",
              "objective": spec["objective"], "protocol_sha256": protocol_record["protocol_sha256"],
              "locked_before_evaluation_utc": datetime.now(timezone.utc).isoformat()}
    _json(out / "selection.json", locked)
    lock_hash = _digest(out / "selection.json")
    evaluation, evaluation_results, checks2 = _run_sample(book, scenario, policies, spec["evaluation"], spec, "evaluation")
    if _digest(out / "selection.json") != lock_hash:
        raise AssertionError("The selected rule changed during evaluation.")
    if selection_results[selected].scenario_id == evaluation_results[selected].scenario_id:
        raise AssertionError("Evaluation reused selection outcomes.")
    evaluation.to_csv(out / "evaluation_metrics.csv", index=False)
    pd.concat([checks1, checks2], ignore_index=True).to_csv(out / "accounting_checks.csv", index=False)
    chosen = evaluation_results[selected]
    tails, means = [], []
    for index, label in enumerate(spec["benchmark_labels"]):
        benchmark = evaluation_results[label]
        mean = paired_difference(chosen, benchmark)
        tail = paired_tail_difference(chosen.terminal_pnl.sum(axis=1), benchmark.terminal_pnl.sum(axis=1),
            confidence=spec["confidence"], tail_probability=spec["tail_probability"],
            n_bootstrap=spec["bootstrap"]["n_resamples"], seed=spec["bootstrap"]["seed"] + index)
        tails.append({"benchmark": label, **tail})
        means.append({"benchmark": label, **mean})
    tails, means = pd.DataFrame(tails), pd.DataFrame(means)
    tails.to_csv(out / "paired_tail_differences.csv", index=False)
    means.to_csv(out / "paired_mean_differences.csv", index=False)
    pnl = chosen.terminal_pnl.sum(axis=1)
    risk = [risk_interval(pnl, metric=metric, confidence=spec["confidence"],
             n_bootstrap=spec["bootstrap"]["n_resamples"], seed=spec["bootstrap"]["seed"] + 100 + index)
            for index, metric in enumerate(("es", "std"))]
    _json(out / "selected_risk_intervals.json", risk)
    for label in dict.fromkeys([selected, *spec["benchmark_labels"]]):
        evaluation_results[label].ledger.to_csv(out / f"audit_{label}.csv", index=False)
    gate = {"gate": "research_gate_1", "status": "complete", "human_review": "pending_separate_review",
            "scope": "controlled synthetic policy-selection study only",
            "selected_policy": selected, "selected_evaluation_budget_feasible": bool(evaluation.loc[evaluation.policy.eq(selected), "budget_feasible"].iloc[0]),
            "selection_locked_before_evaluation": True, "selection_lock_sha256": lock_hash,
            "accounting_checks_passed": True, "tail_uncertainty_reported": True,
            "peak_financing_reported": True, "market_or_stage7_gate_passed": False}
    record = {**protocol_record, "selected_policy": locked, "selection_lock_sha256": lock_hash,
              "evaluation": provenance(book, scenario, spec["evaluation"]["seed"], spec["evaluation"]["n_paths"]),
              "evaluation_scenario_id": chosen.scenario_id,
              "intervals": {"confidence": spec["confidence"], "scope": "pointwise", "bootstrap": spec["bootstrap"]}}
    _json(out / "provenance.json", record)
    _plots(out, evaluation, selected, spec["cost_budget_dollars"])
    _report(out, spec, book, selection, evaluation, selected, tails, means, risk, gate)
    # Completion is committed only after report and figures exist successfully.
    _json(out / "gate_status.json", gate)
    manifest = {p.name: _digest(p) for p in sorted(out.iterdir()) if p.is_file()}
    _json(out / "artifact_manifest.json", manifest)
    return {"output_dir": str(out), "selected_policy": selected, "gate": gate,
            "selection": selection, "evaluation": evaluation, "tail_differences": tails,
            "mean_differences": means, "risk_intervals": risk}

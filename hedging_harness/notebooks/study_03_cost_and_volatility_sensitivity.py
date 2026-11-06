"""03_cost_and_volatility_sensitivity: original study operations moved from notebook cells."""
from IPython.display import display
from hedging_harness.configuration import defaults, notebook_controls
from hedging_harness.notebook_views import verify_frozen_overlay, historical_root, historical_path


def run():
    _controls = notebook_controls('03_cost_and_volatility_sensitivity')
    from pathlib import Path
    from hashlib import sha256
    import sys
    import json

    import numpy as np
    import pandas as pd
    import matplotlib.pyplot as plt
    from IPython.display import display

    ROOT = Path.cwd()
    if not (ROOT / "hedging_harness" / "core.py").is_file():
        ROOT = ROOT.parent
    assert (ROOT / "hedging_harness" / "core.py").is_file(), f"Wrong project root: {ROOT}"
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))

    from hedging_harness import Book, simulate_paths, hedge, summarize, initial_exposures, provenance, paired_difference

    plt.rcParams.update({
        "axes.spines.top": False, "axes.spines.right": False,
        "axes.grid": True, "grid.alpha": 0.2,
    })
    print(f"Project root: {ROOT}")

    from hedging_harness.study import load_named_inputs
    option_portfolio, scenario, shared_config = load_named_inputs(
        ROOT / "config" / "illustrative_study.json"
    )


    POLICIES = _controls['POLICIES']
    COST_GRID_BPS = _controls['COST_GRID_BPS']
    REFERENCE_COST_BPS = _controls['REFERENCE_COST_BPS']
    HEDGE_VOL_MULTIPLIERS = _controls['HEDGE_VOL_MULTIPLIERS']
    SENSITIVITY_POLICIES = _controls['SENSITIVITY_POLICIES']
    N_PATHS = shared_config["n_paths"]
    SEED = shared_config["seed"]
    AUDIT_PATH = _controls['AUDIT_PATH']
    VALIDATION_N = _controls['VALIDATION_N']
    VALIDATION_SEED = SEED + 1
    VALIDATION_POLICIES = {name: POLICIES[name] for name in ("daily", "weekly")}

    option_underlyings = list(option_portfolio)
    assert set(scenario["path_vols"]) == set(option_underlyings)
    assert isinstance(N_PATHS, int) and N_PATHS >= 2
    assert 0 <= AUDIT_PATH < min(N_PATHS, VALIDATION_N)
    assert VALIDATION_N >= 2 and VALIDATION_SEED != SEED
    assert len(set(COST_GRID_BPS)) == len(COST_GRID_BPS)
    assert 0.0 in COST_GRID_BPS and REFERENCE_COST_BPS in COST_GRID_BPS
    assert all(np.isfinite(cost) and cost >= 0 for cost in COST_GRID_BPS)
    assert len(set(HEDGE_VOL_MULTIPLIERS)) == len(HEDGE_VOL_MULTIPLIERS)
    assert 1.0 in HEDGE_VOL_MULTIPLIERS
    assert all(np.isfinite(multiplier) and multiplier > 0 for multiplier in HEDGE_VOL_MULTIPLIERS)
    assert set(SENSITIVITY_POLICIES).issubset(POLICIES)

    assumptions = pd.DataFrame.from_dict(option_portfolio, orient="index")
    assumptions.index.name = "name"
    for field in ("days_to_expiration", "days_in_trading_year", "risk_free_rate"):
        assert assumptions[field].nunique() == 1, f"The simulator requires one common {field}."
    assumptions["call_units"] = assumptions["notional"] / assumptions["spot"]
    assumptions["maturity_years"] = assumptions["days_to_expiration"] / assumptions["days_in_trading_year"]
    assumptions["path_vol"] = pd.Series(scenario["path_vols"])
    assert not assumptions.isna().any().any()
    np.testing.assert_allclose(
        assumptions["pricing_vol"], assumptions["path_vol"],
        err_msg="Use matching pricing/path vols to isolate the hedge-volatility error in this experiment."
    )

    correlation_matrix = pd.DataFrame(
        np.eye(len(option_underlyings)), index=option_underlyings, columns=option_underlyings
    )
    seen_pairs = set()
    for (name_a, name_b), value in scenario["correlations"].items():
        assert name_a in option_portfolio and name_b in option_portfolio and name_a != name_b
        assert np.isfinite(value) and -1 <= value <= 1
        pair = frozenset((name_a, name_b))
        assert pair not in seen_pairs
        seen_pairs.add(pair)
        correlation_matrix.loc[name_a, name_b] = value
        correlation_matrix.loc[name_b, name_a] = value
    assert len(seen_pairs) == len(option_underlyings) * (len(option_underlyings) - 1) // 2
    assert np.linalg.eigvalsh(correlation_matrix.to_numpy()).min() >= -1e-10

    first_option = option_portfolio[option_underlyings[0]]
    book = Book(
        names=tuple(option_underlyings),
        spots=tuple(option_portfolio[name]["spot"] for name in option_underlyings),
        strikes=tuple(option_portfolio[name]["strike"] for name in option_underlyings),
        notionals=tuple(option_portfolio[name]["notional"] for name in option_underlyings),
        pricing_vols=tuple(option_portfolio[name]["pricing_vol"] for name in option_underlyings),
        steps=first_option["days_to_expiration"],
        sessions_per_year=first_option["days_in_trading_year"],
        rate=first_option["risk_free_rate"],
    )
    simulation_scenario = {
        "path_vols": [scenario["path_vols"][name] for name in option_underlyings],
        "correlation": correlation_matrix.loc[option_underlyings, option_underlyings].to_numpy().tolist(),
    }
    opening_exposures = initial_exposures(book)
    display(assumptions)
    print("Fixed opening premium and base exposures:")
    display(opening_exposures.round(4))

    paths = simulate_paths(book, **simulation_scenario, n_paths=N_PATHS, seed=SEED)
    assert paths.shape == (N_PATHS, book.steps + 1, len(book.names))
    assert np.isfinite(paths).all() and (paths > 0).all()
    np.testing.assert_allclose(paths[:, 0, :], np.broadcast_to(book.spots, (N_PATHS, len(book.names))))
    base_paths_sha256 = sha256(paths.tobytes()).hexdigest()
    premium_reference = opening_exposures["initial_premium"].to_numpy()
    print(f"Baseline paths: {paths.shape}; seed: {SEED}")
    print(f"Total fixed model premium: ${premium_reference.sum():,.4f}")
    print(f"Path-array SHA256: {base_paths_sha256}")

    cost_results = {}
    cost_rows = []
    for cost in COST_GRID_BPS:
        for policy, interval in POLICIES.items():
            result = hedge(book, paths, hedge_every=interval, cost_bps=cost, audit_path=AUDIT_PATH)
            cost_results[cost, policy] = result
            cost_rows.append({"cost_bps": cost, "policy": policy, **summarize(result).loc["Portfolio"].to_dict()})
    cost_table = pd.DataFrame(cost_rows)
    cost_summary = cost_table.set_index(["cost_bps", "policy"])
    display(cost_summary[[
        "mean_pnl", "mean_se", "pnl_std", "loss_es95",
        "mean_cost", "mean_financed_cost", "mean_turnover"
    ]].round(4))

    cost_check_rows = []
    for (cost, policy), result in cost_results.items():
        reference = cost_results[0.0, policy]
        residual = reference.terminal_pnl - result.terminal_pnl - result.financed_costs
        np.testing.assert_allclose(residual, 0.0, atol=1e-8, rtol=0)
        np.testing.assert_allclose(reference.turnover, result.turnover, atol=1e-9, rtol=0)
        np.testing.assert_array_equal(reference.trade_counts, result.trade_counts)
        np.testing.assert_allclose(reference.ledger["shares_after"], result.ledger["shares_after"])
        opening = result.ledger.loc[result.ledger["step"].eq(0)].set_index("name").reindex(book.names)
        np.testing.assert_allclose(opening["premium_received"], premium_reference)
        cost_check_rows.append({
            "cost_bps": cost, "policy": policy,
            "max_financed_cost_identity_residual": np.abs(residual).max(),
            "mean_financed_portfolio_cost": result.financed_costs.sum(axis=1).mean(),
        })
    cost_checks = pd.DataFrame(cost_check_rows).set_index(["cost_bps", "policy"])
    display(cost_checks.round(8))
    print("Financed-cost identities, fixed premiums and unchanged-trade checks passed for every cost case.")

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8))
    for policy in SENSITIVITY_POLICIES:
        sub = cost_table.loc[cost_table["policy"].eq(policy)].sort_values("cost_bps")
        for ax, metric in zip(axes, ["pnl_std", "loss_es95"]):
            ax.plot(sub["mean_financed_cost"], sub[metric], marker="o", label=policy)
            for _, row in sub.iterrows():
                ax.annotate(f"{row['cost_bps']:g} bp", (row["mean_financed_cost"], row[metric]),
                            xytext=(4, 5), textcoords="offset points", fontsize=8)
            ax.set_xlabel("Mean financed stock trading cost ($)")
    axes[0].set_ylabel("Portfolio P&L standard deviation ($)")
    axes[1].set_ylabel("Portfolio ES95 loss ($)")
    axes[0].legend()
    fig.suptitle("Stock trading cost versus residual hedge risk")
    fig.tight_layout()
    plt.show()

    paired_rows = []
    for cost in COST_GRID_BPS:
        daily_row = cost_summary.loc[(cost, "daily")]
        weekly_row = cost_summary.loc[(cost, "weekly")]
        comparison = paired_difference(cost_results[cost, "daily"], cost_results[cost, "weekly"])
        paired_rows.append({
            "cost_bps": cost,
            **comparison,
            "daily_std_reduction_vs_weekly_pct": 100 * (1 - daily_row["pnl_std"] / weekly_row["pnl_std"]),
            "daily_ES95_reduction_vs_weekly": weekly_row["loss_es95"] - daily_row["loss_es95"],
            "daily_extra_financed_cost": daily_row["mean_financed_cost"] - weekly_row["mean_financed_cost"],
            "mean_interval_excludes_zero": comparison["mc_95_low"] > 0 or comparison["mc_95_high"] < 0,
        })
    paired_policy_comparisons = pd.DataFrame(paired_rows).set_index("cost_bps")
    display(paired_policy_comparisons.round(4))

    hedge_vol_inputs = pd.DataFrame(
        [np.asarray(book.pricing_vols) * multiplier for multiplier in HEDGE_VOL_MULTIPLIERS],
        index=pd.Index(HEDGE_VOL_MULTIPLIERS, name="hedge_vol_multiplier"), columns=book.names,
    )
    print("Actual annual hedge volatilities (decimal units):")
    display(hedge_vol_inputs)

    vol_results = {}
    vol_rows = []
    for multiplier in HEDGE_VOL_MULTIPLIERS:
        for policy in SENSITIVITY_POLICIES:
            if multiplier == 1.0:
                result = cost_results[REFERENCE_COST_BPS, policy]
            else:
                result = hedge(
                    book, paths, hedge_every=POLICIES[policy], cost_bps=REFERENCE_COST_BPS,
                    hedge_vols=np.asarray(book.pricing_vols) * multiplier, audit_path=AUDIT_PATH,
                )
            vol_results[multiplier, policy] = result
            vol_rows.append({
                "hedge_vol_multiplier": multiplier, "policy": policy,
                **summarize(result).loc["Portfolio"].to_dict(),
            })
    vol_table = pd.DataFrame(vol_rows)
    vol_summary = vol_table.set_index(["hedge_vol_multiplier", "policy"])
    display(vol_summary[[
        "mean_pnl", "mean_se", "pnl_std", "loss_es95", "mean_cost", "mean_financed_cost", "mean_turnover"
    ]].round(4))

    vol_comparison_rows = []
    vol_opening_rows = []
    for (multiplier, policy), result in vol_results.items():
        reference = vol_results[1.0, policy]
        opening = result.ledger.loc[result.ledger["step"].eq(0)].set_index("name").reindex(book.names)
        np.testing.assert_allclose(opening["premium_received"], premium_reference)
        for column in ("spot", "option_liability", "payoff_paid"):
            np.testing.assert_allclose(result.ledger[column], reference.ledger[column])
        for name in book.names:
            if policy == "daily":
                vol_opening_rows.append({
                    "hedge_vol_multiplier": multiplier, "name": name,
                    "premium_received": opening.loc[name, "premium_received"],
                    "initial_hedge_shares": opening.loc[name, "shares_after"],
                })
        if multiplier != 1.0:
            comparison = paired_difference(result, reference)
            vol_comparison_rows.append({
                "hedge_vol_multiplier": multiplier, "policy": policy,
                **comparison,
                "ES95_difference_vs_correct_vol": (
                    vol_summary.loc[(multiplier, policy), "loss_es95"] - vol_summary.loc[(1.0, policy), "loss_es95"]
                ),
                "mean_interval_excludes_zero": comparison["mc_95_low"] > 0 or comparison["mc_95_high"] < 0,
            })
    vol_opening_comparison = pd.DataFrame(vol_opening_rows).set_index(["hedge_vol_multiplier", "name"])
    vol_comparisons = pd.DataFrame(vol_comparison_rows).set_index(["hedge_vol_multiplier", "policy"])
    print("Opening premiums remain fixed while hedge shares change:")
    display(vol_opening_comparison.round(6))
    print("Changed hedge volatility minus correct-volatility reference:")
    display(vol_comparisons.round(4))
    assert sha256(paths.tobytes()).hexdigest() == base_paths_sha256
    print("Fixed-premium, fixed-mark, fixed-settlement and unchanged-path checks passed.")

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.5))
    for policy in SENSITIVITY_POLICIES:
        sub = vol_table.loc[vol_table["policy"].eq(policy)].sort_values("hedge_vol_multiplier")
        for ax, metric in zip(axes, ["pnl_std", "loss_es95"]):
            ax.plot(sub["hedge_vol_multiplier"], sub[metric], marker="o", label=policy)
            ax.set_xlabel("Hedge volatility / base pricing volatility")
    for ax in axes:
        ax.axvline(1.0, color="black", linestyle="--", linewidth=0.8, alpha=0.6)
        ax.set_xticks(HEDGE_VOL_MULTIPLIERS)
    axes[0].set_ylabel("Portfolio P&L standard deviation ($)")
    axes[1].set_ylabel("Portfolio ES95 loss ($)")
    axes[0].legend()
    fig.suptitle(f"Same paths and premiums; different hedge deltas; {REFERENCE_COST_BPS:g} bp stock cost")
    fig.tight_layout()
    plt.show()

    fresh = simulate_paths(book, **simulation_scenario, n_paths=VALIDATION_N, seed=VALIDATION_SEED)
    assert fresh.shape == (VALIDATION_N, book.steps + 1, len(book.names))
    validation_paths_sha256 = sha256(fresh.tobytes()).hexdigest()
    validation_results = {
        policy: hedge(book, fresh, hedge_every=interval, cost_bps=REFERENCE_COST_BPS, audit_path=AUDIT_PATH)
        for policy, interval in VALIDATION_POLICIES.items()
    }
    validation_table = pd.DataFrame({
        policy: summarize(result).loc["Portfolio"] for policy, result in validation_results.items()
    }).T
    validation_table.index.name = "policy"
    validation_paired = paired_difference(validation_results["daily"], validation_results["weekly"])

    baseline_comparison = cost_summary.xs(REFERENCE_COST_BPS, level="cost_bps").loc[list(VALIDATION_POLICIES)]
    validation_comparison = pd.concat({
        "baseline": baseline_comparison,
        "fresh_seed": validation_table,
    }, names=["run", "policy"])
    display(validation_comparison[[
        "paths", "mean_pnl", "mean_se", "pnl_std", "loss_es95", "mean_financed_cost"
    ]].round(4))
    paired_run_comparison = pd.DataFrame({
        "baseline": paired_difference(cost_results[REFERENCE_COST_BPS, "daily"], cost_results[REFERENCE_COST_BPS, "weekly"]),
        "fresh_seed": validation_paired,
    }).T
    paired_run_comparison.index.name = "run"
    print("Daily minus five-session mean net P&L; paired within each run:")
    display(paired_run_comparison.round(4))
    print(f"Fresh seed: {VALIDATION_SEED}; outcomes: {VALIDATION_N:,}; fixed stock cost: {REFERENCE_COST_BPS:g} bp")

    centers = paired_run_comparison["mean_difference"].to_numpy()
    left_errors = centers - paired_run_comparison["mc_95_low"].to_numpy()
    right_errors = paired_run_comparison["mc_95_high"].to_numpy() - centers
    fig, ax = plt.subplots(figsize=(9, 3.5))
    ax.errorbar(centers, np.arange(len(centers)), xerr=np.vstack([left_errors, right_errors]),
                fmt="o", capsize=5, color="tab:blue")
    ax.set_yticks(np.arange(len(centers)), [f"Baseline ({N_PATHS:,} paths)", f"Fresh seed ({VALIDATION_N:,} paths)"])
    ax.axvline(0, color="black", linewidth=0.8)
    ax.set(xlabel="Mean daily minus five-session net P&L ($)", title="Paired mean differences with approximate 95% Monte Carlo intervals")
    ax.margins(y=0.4)
    fig.tight_layout()
    plt.show()

    conclusion_rows = []
    for run, table in [("baseline", baseline_comparison), ("fresh_seed", validation_table)]:
        daily = table.loc["daily"]
        weekly = table.loc["weekly"]
        paired = paired_run_comparison.loc[run]
        conclusion_rows.append({
            "run": run,
            "daily_std_reduction_vs_weekly_pct": 100 * (1 - daily["pnl_std"] / weekly["pnl_std"]),
            "daily_ES95_reduction_vs_weekly": weekly["loss_es95"] - daily["loss_es95"],
            "daily_minus_weekly_mean_PnL": paired["mean_difference"],
            "paired_mean_SE": paired["paired_se"],
            "mean_interval_excludes_zero": paired["mc_95_low"] > 0 or paired["mc_95_high"] < 0,
        })
    conclusions = pd.DataFrame(conclusion_rows).set_index("run")
    display(conclusions.round(4))
    print("Portfolio ES95 by hedge-volatility multiplier:")
    display(vol_table.pivot(index="hedge_vol_multiplier", columns="policy", values="loss_es95").round(4))
    print("No policy was optimized or selected from these sample outcomes.")

    assert sha256(paths.tobytes()).hexdigest() == base_paths_sha256
    assert sha256(fresh.tobytes()).hexdigest() == validation_paths_sha256

    validation_record = provenance(book, simulation_scenario, VALIDATION_SEED, VALIDATION_N)
    validation_record["policies"] = VALIDATION_POLICIES
    validation_record["cost_bps"] = REFERENCE_COST_BPS
    validation_record["hedge_vols"] = list(book.pricing_vols)
    validation_record["paths_sha256"] = validation_paths_sha256

    run_record = provenance(book, simulation_scenario, SEED, N_PATHS)
    run_record["option_kind"] = "European call"
    run_record["position_side"] = "short"
    run_record["option_portfolio"] = option_portfolio
    run_record["named_scenario"] = {
        "path_vols": scenario["path_vols"],
        "correlations": [
            {"name_a": name_a, "name_b": name_b, "correlation": value}
            for (name_a, name_b), value in scenario["correlations"].items()
        ],
    }
    run_record["policies"] = POLICIES
    run_record["cost_grid_bps"] = COST_GRID_BPS
    run_record["reference_cost_bps"] = REFERENCE_COST_BPS
    run_record["hedge_volatility_cases"] = [
        {"multiplier": multiplier, "hedge_vols": (np.asarray(book.pricing_vols) * multiplier).tolist()}
        for multiplier in HEDGE_VOL_MULTIPLIERS
    ]
    run_record["sensitivity_policies"] = SENSITIVITY_POLICIES
    run_record["audit_path"] = AUDIT_PATH
    run_record["paths_sha256"] = base_paths_sha256
    run_record["opening_premium_by_name"] = dict(zip(book.names, premium_reference.tolist()))
    run_record["validation_run"] = validation_record
    run_record["input_source"] = "Shared validated config/illustrative_study.json; notebook controls remain explicit."
    run_record["python_executable"] = sys.executable
    notebook_path = ROOT / "Hedging_Study_Notebooks" / "03_cost_and_volatility_sensitivity.ipynb"
    notebook_source = json.loads(notebook_path.read_text())
    code_text = "\n\n".join(
        "".join(cell["source"]) for cell in notebook_source["cells"] if cell["cell_type"] == "code"
    )
    run_record["notebook_code_sha256"] = sha256(code_text.encode()).hexdigest()
    run_record["shared_input_source"] = shared_config["shared_input_source"]
    print(json.dumps(run_record, indent=2))
    return locals()

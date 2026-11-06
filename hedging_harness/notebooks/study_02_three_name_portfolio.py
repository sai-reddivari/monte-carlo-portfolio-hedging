"""02_three_name_portfolio: original study operations moved from notebook cells."""
from IPython.display import display
from hedging_harness.configuration import defaults, notebook_controls
from hedging_harness.notebook_views import verify_frozen_overlay, historical_root, historical_path


def run():
    _controls = notebook_controls('02_three_name_portfolio')
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

    from hedging_harness import Book, simulate_paths, hedge, summarize, initial_exposures, provenance

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
    COST_BPS = _controls['COST_BPS']
    AUDIT_PATH = _controls['AUDIT_PATH']
    N_PATHS = shared_config["n_paths"]
    SEED = shared_config["seed"]


    option_underlyings = list(option_portfolio)
    assert set(scenario["path_vols"]) == set(option_underlyings)
    assert isinstance(N_PATHS, int) and N_PATHS >= 2
    assert isinstance(AUDIT_PATH, int) and 0 <= AUDIT_PATH < N_PATHS
    assert np.isfinite(COST_BPS) and COST_BPS >= 0

    assumptions = pd.DataFrame.from_dict(option_portfolio, orient="index")
    assumptions.index.name = "name"
    for field in ("days_to_expiration", "days_in_trading_year", "risk_free_rate"):
        assert assumptions[field].nunique() == 1, f"The simulator requires one common {field}."
    assumptions["call_units"] = assumptions["notional"] / assumptions["spot"]
    assumptions["maturity_years"] = assumptions["days_to_expiration"] / assumptions["days_in_trading_year"]
    assumptions["path_vol"] = pd.Series(scenario["path_vols"])
    assert not assumptions.isna().any().any()

    correlation_matrix = pd.DataFrame(
        np.eye(len(option_underlyings)), index=option_underlyings, columns=option_underlyings
    )
    seen_pairs = set()
    for (name_a, name_b), value in scenario["correlations"].items():
        assert name_a in option_portfolio and name_b in option_portfolio and name_a != name_b
        assert np.isfinite(value) and -1 <= value <= 1
        pair = frozenset((name_a, name_b))
        assert pair not in seen_pairs, "Specify each unordered correlation pair once."
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
    path_vols = [scenario["path_vols"][name] for name in option_underlyings]
    opening_exposures = initial_exposures(book)
    print("Named study assumptions:")
    display(assumptions)
    print("Opening short-call exposures and delta-offsetting stock quantities:")
    display(opening_exposures.round(4))
    print(f"Total initial underlying notional: ${sum(book.notionals):,.0f}")
    print("Equal notional does not imply equal option premium, gamma or vega.")

    dependence = {
        "independent": np.eye(len(book.names)),
        "illustrative_correlated": correlation_matrix.loc[option_underlyings, option_underlyings].to_numpy(),
    }
    path_sets = {}
    return_correlations = {}
    for label, correlation in dependence.items():
        paths = simulate_paths(book, path_vols, correlation, n_paths=N_PATHS, seed=SEED)
        assert paths.shape == (N_PATHS, book.steps + 1, len(book.names))
        assert np.isfinite(paths).all() and (paths > 0).all()
        np.testing.assert_allclose(paths[:, 0, :], np.broadcast_to(book.spots, (N_PATHS, len(book.names))))
        path_sets[label] = paths
        returns = np.diff(np.log(paths), axis=1).reshape(-1, len(book.names))
        return_correlations[label] = pd.DataFrame(
            np.corrcoef(returns, rowvar=False), index=book.names, columns=book.names
        )
        print(f"{label}: {paths.shape}; empirical return correlations:")
        display(return_correlations[label].round(4))

    results = {}
    tables = []
    for label, paths in path_sets.items():
        for policy, interval in POLICIES.items():
            result = hedge(
                book, paths, hedge_every=interval, cost_bps=COST_BPS, audit_path=AUDIT_PATH
            )
            results[label, policy] = result
            table = summarize(result).reset_index().assign(dependence=label, policy=policy)
            tables.append(table)
            total_pnl = result.terminal_pnl.sum(axis=1)
            portfolio_row = table.loc[table["name"].eq("Portfolio")].iloc[0]
            np.testing.assert_allclose(portfolio_row["mean_pnl"], total_pnl.mean(), atol=1e-9)
            np.testing.assert_allclose(portfolio_row["pnl_std"], total_pnl.std(ddof=1), rtol=1e-12)

    summary = pd.concat(tables, ignore_index=True)
    portfolio = summary.loc[summary["name"].eq("Portfolio")].copy()
    portfolio_table = portfolio.set_index(["dependence", "policy"])
    display(portfolio_table[[
        "paths", "mean_pnl", "mean_se", "pnl_std", "pnl_p05", "loss_es95", "mean_turnover"
    ]].round(4))
    print(f"Completed {len(results)} scenario/policy cases on {N_PATHS:,} outcomes each.")

    account_columns = [
        "premium_received", "interest", "stock_cashflow", "transaction_cost", "payoff_paid",
        "cash", "stock_value", "option_liability", "net_value",
    ]
    aggregate_ledgers = {}
    accounting_rows = []
    for (label, policy), result in results.items():
        ledger = result.ledger
        assert len(ledger) == (book.steps + 1) * len(book.names)
        aggregate = ledger.groupby("step")[account_columns].sum()
        aggregate_ledgers[label, policy] = aggregate
        cash_flows = (
            aggregate["premium_received"] + aggregate["interest"] + aggregate["stock_cashflow"]
            - aggregate["transaction_cost"] - aggregate["payoff_paid"]
        )
        cash_residual = aggregate["cash"] - cash_flows.cumsum()
        value_residual = aggregate["net_value"] - (
            aggregate["cash"] + aggregate["stock_value"] - aggregate["option_liability"]
        )
        np.testing.assert_allclose(cash_residual, 0.0, atol=1e-8, rtol=0)
        np.testing.assert_allclose(value_residual, 0.0, atol=1e-8, rtol=0)
        last_rows = ledger.loc[ledger["step"].eq(book.steps)]
        assert last_rows["shares_after"].eq(0).all()
        assert last_rows["option_liability"].eq(0).all()
        np.testing.assert_allclose(
            aggregate.iloc[-1]["cash"], result.terminal_pnl[AUDIT_PATH].sum(), atol=1e-8, rtol=0
        )
        accounting_rows.append({
            "dependence": label, "policy": policy,
            "max_cash_residual": cash_residual.abs().max(),
            "max_value_residual": value_residual.abs().max(),
            "terminal_shared_cash": aggregate.iloc[-1]["cash"],
        })
    accounting_checks = pd.DataFrame(accounting_rows).set_index(["dependence", "policy"])
    display(accounting_checks.round(8))
    example_ledger = aggregate_ledgers["illustrative_correlated", "weekly"]
    selected_steps = sorted({0, 1, 4, 5, 6, max(0, book.steps - 1), book.steps})
    print("Correlated five-session hedge: shared-account cash flows and cash:")
    display(example_ledger.loc[example_ledger.index.isin(selected_steps), [
        "premium_received", "interest", "stock_cashflow", "transaction_cost", "payoff_paid", "cash"
    ]].round(4))
    print("All shared-account cash, marked-value and terminal-settlement checks passed.")

    risk_rows = []
    for label in dependence:
        daily_std = portfolio_table.loc[(label, "daily"), "pnl_std"]
        initial_std = portfolio_table.loc[(label, "initial_only"), "pnl_std"]
        for policy in POLICIES:
            row = portfolio_table.loc[(label, policy)]
            risk_rows.append({
                "dependence": label, "policy": policy,
                "pnl_std": row["pnl_std"],
                "std_relative_to_daily": row["pnl_std"] / daily_std if daily_std else np.nan,
                "std_reduction_vs_initial_pct": 100 * (1 - row["pnl_std"] / initial_std) if initial_std else np.nan,
                "loss_es95": row["loss_es95"],
                "mean_turnover": row["mean_turnover"],
            })
    risk_comparison = pd.DataFrame(risk_rows).set_index(["dependence", "policy"])
    display(risk_comparison.round(4))

    policy_names = list(POLICIES)
    positions = np.arange(len(policy_names))
    width = 0.36
    fig, axes = plt.subplots(1, 3, figsize=(15, 4.5))
    metrics = [("pnl_std", "P&L standard deviation ($)"), ("loss_es95", "Portfolio ES95 loss ($)"), ("mean_turnover", "Mean total stock turnover ($)")]
    for ax, (metric, ylabel) in zip(axes, metrics):
        for scenario_index, label in enumerate(dependence):
            heights = portfolio_table.loc[label].reindex(policy_names)[metric].to_numpy()
            offset = (scenario_index - 0.5) * width
            ax.bar(positions + offset, heights, width=width, label=label.replace("illustrative_", ""))
        ax.set_xticks(positions, [p.replace("_", " ") for p in policy_names], rotation=20)
        ax.set_ylabel(ylabel)
        ax.ticklabel_format(axis="y", style="plain")
    axes[0].legend()
    fig.suptitle(f"Three-name portfolio: hedge-frequency comparison, {COST_BPS:g} bp stock cost")
    fig.tight_layout()
    plt.show()

    plotted_policies = ["daily", "weekly"]
    plotted_pnls = [
        results[label, policy].terminal_pnl.sum(axis=1)
        for label in dependence for policy in plotted_policies
    ]
    bins = np.histogram_bin_edges(np.concatenate(plotted_pnls), bins=70)
    fig, axes = plt.subplots(1, len(dependence), figsize=(12, 4.5), sharex=True, sharey=True)
    for ax, label in zip(axes, dependence):
        for policy in plotted_policies:
            pnl = results[label, policy].terminal_pnl.sum(axis=1)
            ax.hist(pnl, bins=bins, alpha=0.5, density=True, label=policy)
        ax.axvline(0, color="black", linewidth=0.8)
        ax.set(title=label.replace("_", " "), xlabel="Portfolio terminal net P&L ($)")
        ax.legend()
    axes[0].set_ylabel("Probability density")
    fig.tight_layout()
    plt.show()
    print("Correlated scenario, daily hedge: names and joint portfolio:")
    display(summary.loc[
        summary["dependence"].eq("illustrative_correlated") & summary["policy"].eq("daily"),
        ["name", "mean_pnl", "mean_se", "pnl_std", "loss_es95"],
    ].set_index("name").round(4))

    variance_rows = []
    covariances = {}
    pnl_correlations = {}
    for (label, policy), result in results.items():
        pnl = result.terminal_pnl
        covariance = np.cov(pnl, rowvar=False, ddof=1)
        covariances[label, policy] = pd.DataFrame(covariance, index=book.names, columns=book.names)
        pnl_correlations[label, policy] = pd.DataFrame(
            np.corrcoef(pnl, rowvar=False), index=book.names, columns=book.names
        )
        own = np.trace(covariance)
        cross = covariance.sum() - own
        observed = pnl.sum(axis=1).var(ddof=1)
        np.testing.assert_allclose(own + cross, observed, rtol=1e-12, atol=1e-8)
        sum_standalone_stds = np.sqrt(np.diag(covariance)).sum()
        variance_rows.append({
            "dependence": label, "policy": policy,
            "own_variances": own, "cross_covariances": cross,
            "portfolio_variance": observed,
            "std_diversification_ratio": np.sqrt(observed) / sum_standalone_stds if sum_standalone_stds else np.nan,
        })
    variance_decomposition = pd.DataFrame(variance_rows).set_index(["dependence", "policy"])
    display(variance_decomposition.round(4))
    for label in dependence:
        print(f"{label}: daily-hedge P&L correlations:")
        display(pnl_correlations[label, "daily"].round(4))
    print("Variance identities passed for every scenario/policy case.")

    tail_count = max(1, int(np.ceil(0.05 * N_PATHS)))
    tail_rows = []
    tail_comparison_rows = []
    for (label, policy), result in results.items():
        pnl = result.terminal_pnl
        portfolio_pnl = pnl.sum(axis=1)
        tail_indices = np.argsort(portfolio_pnl)[:tail_count]
        contributions = -pnl[tail_indices].mean(axis=0)
        portfolio_es95 = -portfolio_pnl[tail_indices].mean()
        case_summary = summary.loc[
            summary["dependence"].eq(label) & summary["policy"].eq(policy)
        ].set_index("name")
        np.testing.assert_allclose(contributions.sum(), portfolio_es95, atol=1e-8, rtol=1e-12)
        np.testing.assert_allclose(portfolio_es95, case_summary.loc["Portfolio", "loss_es95"], atol=1e-8)
        for name, contribution in zip(book.names, contributions):
            tail_rows.append({
                "dependence": label, "policy": policy, "name": name,
                "standalone_name_ES95": case_summary.loc[name, "loss_es95"],
                "portfolio_tail_loss_contribution": contribution,
                "portfolio_tail_contribution_pct": 100 * contribution / portfolio_es95 if portfolio_es95 else np.nan,
            })
        standalone_sum = case_summary.loc[list(book.names), "loss_es95"].sum()
        tail_comparison_rows.append({
            "dependence": label, "policy": policy,
            "sum_standalone_ES95": standalone_sum,
            "actual_portfolio_ES95": portfolio_es95,
            "standalone_sum_minus_portfolio": standalone_sum - portfolio_es95,
        })
    tail_contributions = pd.DataFrame(tail_rows).set_index(["dependence", "policy", "name"])
    tail_comparison = pd.DataFrame(tail_comparison_rows).set_index(["dependence", "policy"])
    print(f"Portfolio tail contains {tail_count} of {N_PATHS} outcomes per case.")
    display(tail_comparison.round(4))
    print("Name contributions in the daily and five-session portfolio tails:")
    display(tail_contributions.loc[
        tail_contributions.index.get_level_values("policy").isin(["daily", "weekly"])
    ].round(4))
    print("Tail-contribution sums agree with portfolio ES95 in all cases.")

    interpretation_rows = []
    for label in dependence:
        daily = portfolio_table.loc[(label, "daily")]
        weekly = portfolio_table.loc[(label, "weekly")]
        daily_variance = variance_decomposition.loc[(label, "daily")]
        weekly_tail = tail_contributions.xs((label, "weekly"), level=("dependence", "policy"))
        interpretation_rows.append({
            "dependence": label,
            "weekly_to_daily_std_ratio": weekly["pnl_std"] / daily["pnl_std"] if daily["pnl_std"] else np.nan,
            "daily_std_diversification_ratio": daily_variance["std_diversification_ratio"],
            "largest_weekly_portfolio_tail_contributor": weekly_tail["portfolio_tail_loss_contribution"].idxmax(),
        })
    interpretation = pd.DataFrame(interpretation_rows).set_index("dependence")
    display(interpretation)
    independent_daily_std = portfolio_table.loc[("independent", "daily"), "pnl_std"]
    correlated_daily_std = portfolio_table.loc[("illustrative_correlated", "daily"), "pnl_std"]
    if independent_daily_std:
        print(f"Correlated / independent daily portfolio P&L standard deviation: {correlated_daily_std / independent_daily_std:.4f}")
    print("All portfolio statistics use pathwise sums; no individual tail statistics were added to estimate portfolio risk.")

    configured_scenario = {
        "path_vols": path_vols,
        "correlation": dependence["illustrative_correlated"].tolist(),
    }
    run_record = provenance(book, configured_scenario, SEED, N_PATHS)
    run_record["option_kind"] = "European call"
    run_record["position_side"] = "short"
    run_record["policies"] = POLICIES
    run_record["cost_bps"] = COST_BPS
    run_record["audit_path"] = AUDIT_PATH
    run_record["tail_observation_count"] = tail_count
    run_record["dependence_scenarios"] = {label: correlation.tolist() for label, correlation in dependence.items()}
    run_record["option_portfolio"] = option_portfolio
    run_record["named_scenario"] = {
        "path_vols": scenario["path_vols"],
        "correlations": [
            {"name_a": name_a, "name_b": name_b, "correlation": value}
            for (name_a, name_b), value in scenario["correlations"].items()
        ],
    }
    run_record["input_source"] = "Shared validated config/illustrative_study.json; notebook controls remain explicit."
    run_record["python_executable"] = sys.executable
    notebook_path = ROOT / "Hedging_Study_Notebooks" / "02_three_name_portfolio.ipynb"
    notebook_source = json.loads(notebook_path.read_text())
    code_text = "\n\n".join(
        "".join(cell["source"]) for cell in notebook_source["cells"] if cell["cell_type"] == "code"
    )
    run_record["notebook_code_sha256"] = sha256(code_text.encode()).hexdigest()
    run_record["shared_input_source"] = shared_config["shared_input_source"]
    print(json.dumps(run_record, indent=2))
    return locals()

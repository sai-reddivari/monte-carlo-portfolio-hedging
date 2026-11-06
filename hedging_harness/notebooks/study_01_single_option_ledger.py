"""01_single_option_ledger: original study operations moved from notebook cells."""
from IPython.display import display
from hedging_harness.configuration import defaults, notebook_controls
from hedging_harness.notebook_views import verify_frozen_overlay, historical_root, historical_path


def run():
    _controls = notebook_controls('01_single_option_ledger')
    from pathlib import Path
    from dataclasses import asdict, replace
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
        "figure.figsize": (10, 4), "axes.spines.top": False,
        "axes.spines.right": False, "axes.grid": True, "grid.alpha": 0.2,
    })
    print(f"Project root: {ROOT}")

    from hedging_harness.study import load_named_inputs
    option_portfolio, scenario, shared_config = load_named_inputs(
        ROOT / "config" / "illustrative_study.json"
    )


    OPTION_NAME = _controls['OPTION_NAME']
    HEDGE_EVERY = _controls['HEDGE_EVERY']
    COST_BPS = _controls['COST_BPS']
    AUDIT_PATH = _controls['AUDIT_PATH']
    N_PATHS = shared_config["n_paths"]
    SEED = shared_config["seed"]


    option_underlyings = list(option_portfolio)
    assert OPTION_NAME in option_portfolio, "Choose an existing option name."
    assert set(scenario["path_vols"]) == set(option_underlyings)
    assert isinstance(N_PATHS, int) and N_PATHS >= 2
    assert isinstance(AUDIT_PATH, int) and 0 <= AUDIT_PATH < N_PATHS
    assert COST_BPS >= 0 and np.isfinite(COST_BPS)

    assumptions = pd.DataFrame.from_dict(option_portfolio, orient="index")
    for field in ("days_to_expiration", "days_in_trading_year", "risk_free_rate"):
        assert assumptions[field].nunique() == 1, f"The joint simulator requires one common {field}."

    correlation_matrix = pd.DataFrame(
        np.eye(len(option_underlyings)), index=option_underlyings, columns=option_underlyings
    )
    seen_pairs = set()
    for (name_a, name_b), value in scenario["correlations"].items():
        assert name_a in option_portfolio and name_b in option_portfolio and name_a != name_b
        pair = frozenset((name_a, name_b))
        assert pair not in seen_pairs, "Specify each correlation pair once."
        seen_pairs.add(pair)
        correlation_matrix.loc[name_a, name_b] = value
        correlation_matrix.loc[name_b, name_a] = value
    assert len(seen_pairs) == len(option_underlyings) * (len(option_underlyings) - 1) // 2

    first_option = option_portfolio[option_underlyings[0]]
    study_book = Book(
        names=tuple(option_underlyings),
        spots=tuple(option_portfolio[name]["spot"] for name in option_underlyings),
        strikes=tuple(option_portfolio[name]["strike"] for name in option_underlyings),
        notionals=tuple(option_portfolio[name]["notional"] for name in option_underlyings),
        pricing_vols=tuple(option_portfolio[name]["pricing_vol"] for name in option_underlyings),
        steps=first_option["days_to_expiration"],
        sessions_per_year=first_option["days_in_trading_year"],
        rate=first_option["risk_free_rate"],
    )
    study_scenario = {
        "path_vols": [scenario["path_vols"][name] for name in option_underlyings],
        "correlation": correlation_matrix.loc[option_underlyings, option_underlyings].to_numpy().tolist(),
    }
    study_paths = simulate_paths(study_book, **study_scenario, n_paths=N_PATHS, seed=SEED)
    asset_index = option_underlyings.index(OPTION_NAME)
    option = option_portfolio[OPTION_NAME]
    single = replace(
        study_book, names=(OPTION_NAME,), spots=(option["spot"],), strikes=(option["strike"],),
        notionals=(option["notional"],), pricing_vols=(option["pricing_vol"],),
    )
    single_paths = study_paths[:, :, asset_index:asset_index + 1]
    assert single_paths.shape == (N_PATHS, single.steps + 1, 1)
    np.testing.assert_allclose(single_paths[:, 0, 0], option["spot"])
    print(f"Selected option: {OPTION_NAME}; quantity: {single.units[0]:,.0f} short call units")
    print(f"Selected paths: {single_paths.shape}; seed: {SEED}; audit path: {AUDIT_PATH}")
    print(f"Expiry: {single.steps} sessions = {single.maturity:.2f} years")
    print(f"Pricing vol: {single.pricing_vols[0]:.1%}; path vol: {study_scenario['path_vols'][asset_index]:.1%}")

    opening_exposures = initial_exposures(single)
    display(opening_exposures.round(4))

    result = hedge(
        single, single_paths, hedge_every=HEDGE_EVERY,
        cost_bps=COST_BPS, audit_path=AUDIT_PATH,
    )
    ledger = result.ledger.copy()
    assert len(ledger) == single.steps + 1
    assert ledger["name"].eq(OPTION_NAME).all()
    assert result.terminal_pnl.shape == (N_PATHS, 1)
    policy_label = "Initial hedge only" if HEDGE_EVERY is None else f"Rebalance every {HEDGE_EVERY} sessions"
    print(f"{policy_label}; one-way stock cost: {COST_BPS:g} bp")

    opening = ledger.iloc[0]
    opening_account = pd.Series({
        "premium_received": opening["premium_received"],
        "shares_bought": opening["shares_after"],
        "stock_purchase_cashflow": opening["stock_cashflow"],
        "entry_transaction_cost": opening["transaction_cost"],
        "cash_after_opening": opening["cash"],
        "stock_value": opening["stock_value"],
        "option_liability": opening["option_liability"],
        "net_marked_value": opening["net_value"],
    }, name=OPTION_NAME)
    display(opening_account.to_frame().round(4))
    np.testing.assert_allclose(opening["premium_received"], opening_exposures.loc[OPTION_NAME, "initial_premium"])
    np.testing.assert_allclose(opening["shares_after"], opening_exposures.loc[OPTION_NAME, "hedge_shares"])
    display(np.testing.assert_allclose(opening["net_value"], -opening["transaction_cost"], atol=1e-9, rtol=0))


    selected_steps = {0, 1, max(0, single.steps - 1), single.steps}
    if HEDGE_EVERY is not None:
        selected_steps.update([max(0, HEDGE_EVERY - 1), HEDGE_EVERY, HEDGE_EVERY + 1])
        selected_steps.add((single.steps // HEDGE_EVERY) * HEDGE_EVERY)
    selected_rows = ledger.loc[ledger["step"].isin(sorted(selected_steps))]

    print("Stock holdings and trades:")
    display(selected_rows[["step", "event", "spot", "shares_before", "trade_units", "shares_after"]].round(4))
    print("Cash flows and resulting cash:")
    display(selected_rows[[
        "step", "premium_received", "interest", "stock_cashflow",
        "transaction_cost", "payoff_paid", "cash"
    ]].round(4))
    print("Marked account values:")
    display(selected_rows[["step", "stock_value", "option_liability", "net_value"]].round(4))

    cash_changes = (
        ledger["premium_received"] + ledger["interest"] + ledger["stock_cashflow"]
        - ledger["transaction_cost"] - ledger["payoff_paid"]
    )
    expected_interest = ledger["cash"].shift(1, fill_value=0.0) * np.expm1(single.rate / single.sessions_per_year)
    residuals = pd.DataFrame({
        "cash_accumulation": ledger["cash"] - cash_changes.cumsum(),
        "marked_net_value": ledger["net_value"] - (
            ledger["cash"] + ledger["stock_value"] - ledger["option_liability"]
        ),
        "share_trade_identity": ledger["shares_after"] - ledger["shares_before"] - ledger["trade_units"],
        "stock_cashflow": ledger["stock_cashflow"] + ledger["trade_units"] * ledger["spot"],
        "stock_cost": ledger["transaction_cost"] - (
            ledger["trade_units"].abs() * ledger["spot"] * COST_BPS / 10000
        ),
        "cash_interest": ledger["interest"] - expected_interest,
    })
    np.testing.assert_allclose(residuals.to_numpy(), 0.0, atol=1e-8, rtol=0)
    assert ledger.iloc[-1]["shares_after"] == 0
    assert ledger.iloc[-1]["option_liability"] == 0
    np.testing.assert_allclose(ledger.iloc[-1]["cash"], result.terminal_pnl[AUDIT_PATH, 0], atol=1e-9, rtol=0)
    display(residuals.abs().max().rename("maximum_absolute_residual").to_frame())
    print("Cash, marked value, trade, cost, interest and terminal P&L identities passed.")

    fig, axes = plt.subplots(4, 1, figsize=(10, 10), sharex=True)
    axes[0].plot(ledger["step"], ledger["spot"], color="tab:blue")
    axes[0].set_ylabel("Stock price")
    axes[1].step(ledger["step"], ledger["shares_after"], where="post", color="tab:orange")
    axes[1].set_ylabel("Shares after trade")
    axes[2].plot(ledger["step"], ledger["cash"], color="tab:purple")
    axes[2].set_ylabel("Cash ($)")
    axes[3].plot(ledger["step"], ledger["net_value"], color="tab:green")
    axes[3].axhline(0, color="black", linewidth=0.8)
    axes[3].set(ylabel="Net marked value ($)", xlabel="Trading session")
    fig.suptitle(f"{OPTION_NAME}, audit path {AUDIT_PATH}: {policy_label.lower()}, {COST_BPS:g} bp")
    fig.tight_layout()
    plt.show()

    last = ledger.iloc[-1]
    settlement_cashflows = pd.Series({
        "cash_before_final_session": ledger.iloc[-2]["cash"],
        "final_session_interest": last["interest"],
        "stock_liquidation_proceeds": last["stock_cashflow"],
        "liquidation_cost": -last["transaction_cost"],
        "call_payoff_paid": -last["payoff_paid"],
    }, name="cash_contribution")
    settlement_table = settlement_cashflows.to_frame()
    settlement_table["running_cash"] = settlement_cashflows.cumsum()
    display(settlement_table.round(4))
    np.testing.assert_allclose(
        last["payoff_paid"], single.units[0] * max(last["spot"] - single.strikes[0], 0), atol=1e-9, rtol=0
    )
    np.testing.assert_allclose(settlement_cashflows.sum(), last["cash"], atol=1e-8, rtol=0)
    print(f"Terminal stock price: {last['spot']:.4f}")
    print(f"Final net P&L for audit path {AUDIT_PATH}: ${last['cash']:,.4f}")

    gross = hedge(single, single_paths, hedge_every=HEDGE_EVERY, cost_bps=0.0)
    cost_identity_residual = gross.terminal_pnl - result.terminal_pnl - result.financed_costs
    np.testing.assert_allclose(cost_identity_residual, 0.0, atol=1e-8, rtol=0)
    np.testing.assert_allclose(gross.turnover, result.turnover, atol=1e-9, rtol=0)
    np.testing.assert_array_equal(gross.trade_counts, result.trade_counts)

    cost_check = pd.DataFrame({
        "mean_nominal_cost": [result.nominal_costs[:, 0].mean()],
        "mean_financed_cost": [result.financed_costs[:, 0].mean()],
        "mean_PnL_reduction": [(gross.terminal_pnl[:, 0] - result.terminal_pnl[:, 0]).mean()],
        "max_cost_identity_residual": [np.abs(cost_identity_residual).max()],
    }, index=pd.Index([OPTION_NAME], name="name"))
    display(cost_check.round(6))
    print("Path-by-path financed-cost identity and identical-trade checks passed.")

    summary = summarize(result)
    zero_cost_summary = summarize(gross)
    comparison = pd.concat({
        "zero_cost": zero_cost_summary.loc[[OPTION_NAME]],
        "with_cost": summary.loc[[OPTION_NAME]],
    }, names=["case", "name"])
    display(comparison[[
        "paths", "mean_pnl", "mean_se", "pnl_std", "rmse", "pnl_p05", "loss_es95"
    ]].round(4))
    display(comparison[["mean_cost", "mean_financed_cost", "mean_turnover", "mean_trades"]].round(4))

    zero_cost_pnl = gross.terminal_pnl[:, 0]
    net_pnl = result.terminal_pnl[:, 0]
    bins = np.histogram_bin_edges(np.concatenate([zero_cost_pnl, net_pnl]), bins=65)
    fig, ax = plt.subplots(figsize=(10, 4.5))
    ax.hist(zero_cost_pnl, bins=bins, alpha=0.5, label="Zero stock trading cost")
    ax.hist(net_pnl, bins=bins, alpha=0.5, label=f"{COST_BPS:g} bp stock trading cost")
    ax.axvline(0, color="black", linewidth=1)
    ax.set(xlabel="Terminal net P&L ($)", ylabel="Simulated outcomes", title=f"{OPTION_NAME}: {policy_label.lower()}")
    ax.legend()
    fig.tight_layout()
    plt.show()

    run_record = provenance(study_book, study_scenario, SEED, N_PATHS)
    run_record["option_kind"] = "European call"
    run_record["position_side"] = "short"
    run_record["traded_book"] = asdict(single)
    run_record["policy"] = {
        "selected_name": OPTION_NAME,
        "hedge_every": HEDGE_EVERY,
        "cost_bps": COST_BPS,
        "audit_path": AUDIT_PATH,
        "hedge_vols": list(single.pricing_vols),
    }
    run_record["path_generation"] = "Generate joint study paths, then select the named stock; same dimensions and seed as setup."
    run_record["input_source"] = "Shared validated config/illustrative_study.json; notebook controls remain explicit."
    run_record["python_executable"] = sys.executable
    notebook_path = ROOT / "Hedging_Study_Notebooks" / "01_single_option_ledger.ipynb"
    notebook_source = json.loads(notebook_path.read_text())
    code_text = "\n\n".join(
        "".join(cell["source"]) for cell in notebook_source["cells"] if cell["cell_type"] == "code"
    )
    run_record["notebook_code_sha256"] = sha256(code_text.encode()).hexdigest()
    run_record["shared_input_source"] = shared_config["shared_input_source"]
    print(json.dumps(run_record, indent=2))
    return locals()

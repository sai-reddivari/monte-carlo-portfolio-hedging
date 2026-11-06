"""00_study_setup: original study operations moved from notebook cells."""
from IPython.display import display
from hedging_harness.configuration import defaults, notebook_controls
from hedging_harness.notebook_views import verify_frozen_overlay, historical_root, historical_path


def run():
    _controls = notebook_controls('00_study_setup')
    from pathlib import Path
    import sys
    import json
    from hashlib import sha256

    import numpy as np
    import pandas as pandas
    import matplotlib.pyplot as plt
    from IPython.display import display

    ROOT = Path.cwd()
    if not (ROOT / "BlackScholes_Functions").is_dir():
        ROOT = ROOT.parent
    assert (ROOT / "BlackScholes_Functions").is_dir(), f"Wrong project root: {ROOT}"

    display(ROOT)

    from hedging_harness.study import load_named_inputs
    option_portfolio, scenario, shared_config = load_named_inputs(ROOT / 'config/illustrative_study.json')

    # scenario loaded from the same versioned study inputs


    display(option_portfolio['GS']['pricing_vol'])
    display(scenario['correlations'][("JPM","GS")])
    display(list(option_portfolio)) #calling list on a dictionary gives you the first level keys in a list
    display(list(option_portfolio['GS'])) #you can then drill down into the next level keys in a list


    option_underlyings = list(option_portfolio)
    assert set(scenario["path_vols"]) == set(option_underlyings), "Path-volatility names must match the option portfolio names."

    # Keep labels attached while constructing the numerical correlation matrix.
    correlation_matrix = pandas.DataFrame(
        np.eye(len(option_underlyings)),
        index=option_underlyings,
        columns=option_underlyings,
    )
    seen_pairs = set() #create an empty set of pairs of names --> sets store values without any duplicates. allows us to loop through scenario[correlations] however many names there are, and ensure we dont get the same pairs correlation twice
    for (name_a, name_b), value in scenario["correlations"].items(): #name a and name b are the 'tickers' in the tuple, the value is the correlation
        assert name_a in option_portfolio and name_b in option_portfolio, "Unknown correlation name." #making sure that the 'tickers' are in the 3 name portfolio
        assert name_a != name_b, "Self-correlations are already set to 1." #ensures that we are not comparing the same name to the same name
        assert np.isfinite(value) and -1 <= value <= 1, "Invalid correlation value." #if the correlation between a two security pair is <|1| then thats incorrect 
        pair = frozenset((name_a, name_b)) #loops through the 3 tuples/name-pairs in scenario[correlations], ensures that they are stable and fixed moving fwd.  
        assert pair not in seen_pairs, "Specify each unordered correlation pair once." #if a pair is not in seen_pairs, then add that pair to the seen_pairs
        seen_pairs.add(pair) 
        correlation_matrix.loc[name_a, name_b] = value #name_a Row, name_B column, value = X
        correlation_matrix.loc[name_b, name_a] = value #name_B Row, name_A column, value = X >equivalency in pair correlation on both 'sides' of matrix

    assert len(seen_pairs) == len(option_underlyings) * (len(option_underlyings) - 1) // 2, "Missing correlation pair." #quadratic rule for n-security portfolios. nxn corr matrix --> [n(n-1)]/2 off-diag corrs 
    assert np.linalg.eigvalsh(correlation_matrix.to_numpy()).min() >= -1e-10, "Correlation must be positive semidefinite."
    display(correlation_matrix)

    assumptions = pandas.DataFrame.from_dict(option_portfolio, orient="index")
    assumptions.index.name = "name"
    assumptions["call units"] = assumptions["notional"] / assumptions["spot"]
    assumptions["time_to_expiration_years"] = (
        assumptions["days_to_expiration"] / assumptions["days_in_trading_year"]
    )
    assumptions["path_vol"] = pandas.Series(scenario["path_vols"])
    assert assumptions.index.tolist() == option_underlyings
    assert not assumptions.isna().any().any(), "Missing or misaligned inputs."
    display(assumptions)

    import importlib
    import BlackScholes_Functions.BlackScholes_D1D2_Price_Payoff_Greeks as bs

    # Reload saved module edits when this cell is rerun in an existing kernel.
    importlib.reload(bs)
    from BlackScholes_Functions.BlackScholes_D1D2_Price_Payoff_Greeks import (
        bs_d1_d2, bs_price, bs_payoff, bs_greeks
    )
    from hedging_harness import Book, simulate_paths, provenance

    OPTION_KIND = _controls['OPTION_KIND']
    POSITION_SIGN = _controls['POSITION_SIGN']  # Pricing functions return long-call values; our positions are short.

    valuation_rows = []

    for name, option in option_portfolio.items():
        S = option["spot"]
        K = option["strike"]
        T = option["days_to_expiration"] / option["days_in_trading_year"]
        r = option["risk_free_rate"]
        sigma = option["pricing_vol"]

        d1, d2 = bs_d1_d2(S=S, K=K, T=T, r=r, sigma=sigma)
        price = bs_price(S=S, K=K, T=T, r=r, sigma=sigma, kind=OPTION_KIND)

        valuation_rows.append({
            "name": name,
            "maturity_years": T,
            "d1": d1,
            "d2": d2,
            "call_price": price,
            "short_value_per_unit": POSITION_SIGN * price,
        })

    option_values = pandas.DataFrame(valuation_rows).set_index("name")
    display(option_values.round(6))

    greek_rows = [] #empty set 

    for name, option in option_portfolio.items(): #call the bs_greeks function from BlackScholes_functions, define the input variables as constants across all names and derive values for each greek
        greeks = bs_greeks(
            S=option["spot"],
            K=option["strike"],
            T=option["days_to_expiration"] / option["days_in_trading_year"],
            r=option["risk_free_rate"],
            sigma=option["pricing_vol"],
            kind=OPTION_KIND,
        )
        greek_rows.append({"name": name, **greeks}) #for each name in the option portfolio, create a row indexed by name
                                                    #unfurl the greeks associated with that name into a dictionary containing the name, insert every key/va;lue pair from greeks for that name  

    display(greek_rows) #this is now a set of 3 dictionaries - one for each name and its greeks. 
    per_unit_greeks = pandas.DataFrame(greek_rows).set_index("name") #turn it into a dataframe
    short_call_greeks = POSITION_SIGN * per_unit_greeks

    print("One long call unit — raw Greek units:")
    display(per_unit_greeks.round(6))
    print("One short call unit — raw Greek units:")
    display(short_call_greeks.round(6))

    terminal_spot_grid = np.array([70.0, 80.0, 90.0, 100.0, 110.0, 120.0, 130.0])
    payoff_tables = {}

    for name, option in option_portfolio.items():
        payoff_per_unit = bs_payoff(
            ST=terminal_spot_grid, K=option["strike"], kind=OPTION_KIND
        )
        payoff_tables[name] = pandas.DataFrame({
            "terminal_spot": terminal_spot_grid,
            "call_payoff_per_unit": payoff_per_unit,
            "short_payoff_per_unit": POSITION_SIGN * payoff_per_unit,
        }).set_index("terminal_spot")

    payoff_scenarios = pandas.concat(payoff_tables, names=["name", "terminal_spot"])
    display(payoff_scenarios.round(4))


    #we have already sold the calls (short call) with  strikes at 100, we have received a premium for that
    #we do a basic grid of terminal stock prices +/- 30% of current spot/strike (equivalent) so from $70 to $130
    #payoff if terminal price is below $100 for us is zero, we have received our 'payoff' from the premium selling the options
    #as terminal price increases above strike price, payoff is linearly worse 
    #netPNL = premium received + payoff paid. so if its OOM, just premium received. if its IIM, can still be positive PNL if premium > payoff paid. 

    combined_options_table = pandas.concat(
        [
            assumptions,
            option_values[["d1", "d2", "call_price", "short_value_per_unit"]],
            per_unit_greeks,
        ],
        axis=1,
        verify_integrity=True,
    )
    assert combined_options_table.index.tolist() == option_underlyings
    assert not combined_options_table.isna().any().any()

    units = combined_options_table["call units"]
    spot = combined_options_table["spot"]
    combined_options_table["signed_call_units"] = POSITION_SIGN * units

    #we calculate the "initial premium" - value of the option position if we sold it at market price/BS price, because it 
    #tells us how much cash we can get from the options, and the cash is then used to fund the stock hedge against the short call position 
    combined_options_table["initial_premium"] = units * combined_options_table["call_price"] #premium you can get for selling the options
    combined_options_table["option_value"] = -combined_options_table["initial_premium"] #but we are short the options, so the option value is -1 * the option premium

    combined_options_table["option_delta_shares"] = POSITION_SIGN * units * combined_options_table["delta"] # option position total $ movement for $1 stock price
    combined_options_table["equity_hedge_shares"] = -combined_options_table["option_delta_shares"]

    #^option_delta_shares .... option units * delta = $ delta shares. for 1000 units, and .56 delta, $1 movement in price reults in -$560 loss in option position
    #equity_hedge_shares .... to hedge against that option delta, you would need 560 shares of stock (each moves $1 up cancelling the option position move)

    display(combined_options_table)
    #book_monetized_delta = call units * option delta * underlying stock price  
    combined_options_table["option_dollar_delta"] = combined_options_table["option_delta_shares"] * spot

    #book_mon_gamma1% = 0.5 * call units * gamma * .01(spot price)^2 (the gamma pnl contribution when underlying moves)
    combined_options_table["option_gamma_pnl_for_1pct_move"] = (
        POSITION_SIGN * 0.5 * units * combined_options_table["gamma"] * (0.01 * spot) ** 2
    )

    #daily_book_mon_vega1% = call units * vega * .01 (daily vega pnl contribution from .01 shift in vol)
    combined_options_table["option_vega_per_vol_point"] = (
        POSITION_SIGN * units * combined_options_table["vega"] * 0.01
    )

    #daily_book_mon_theta = call units * theta / 252 (daily theta pnl contribution from 1 day elapsed )
    combined_options_table["option_theta_per_session"] = (
        POSITION_SIGN * units * combined_options_table["theta"]
        / combined_options_table["days_in_trading_year"]
    )

    #daily_book_mon_rho (daily rho contribution to daily pnl )
    combined_options_table["option_rho_per_rate_point"] = (
        POSITION_SIGN * units * combined_options_table["rho"] * 0.01
    )

    ##delta-neutral (in theory) --> because you are long the exact amount of equity shares to offset short delta from options
    ## however - option has Gamma - the change in the Delta of the option based on the change in stock price / time movement . so option delta continues to move, and not 
    #linerly with equity hedge amount, and therefore you are not perfectly delta hedged until/unless you rebalance your optionshare holding
    combined_options_table["net_delta_after_hedge"] = (
        combined_options_table["option_delta_shares"] + combined_options_table["equity_hedge_shares"]
    )

    exposure_columns = [
        "call units", "initial_premium", "equity_hedge_shares", "option_dollar_delta",
        "option_gamma_pnl_for_1pct_move", "option_vega_per_vol_point",
        "option_theta_per_session", "option_rho_per_rate_point", "net_delta_after_hedge",
    ]
    exposures = combined_options_table[exposure_columns].copy()
    position_greeks = per_unit_greeks.mul(combined_options_table["signed_call_units"], axis="index")

    np.testing.assert_allclose(combined_options_table["net_delta_after_hedge"], 0.0, atol=1e-12)
    np.testing.assert_allclose(
        combined_options_table["option_value"] + combined_options_table["initial_premium"], 0.0
    )
    assert (position_greeks[["delta", "gamma", "vega"]] < 0).all().all() #delta/gamma/vega should be negative because we are short the call
    assert (exposures["equity_hedge_shares"] > 0).all()
    display(exposures.round(4))
    print("Short-call signs, premium/liability and initial delta-offset checks passed.")

    # Reproducible experiment controls. Edit these for a different run.
    N_PATHS = _controls['N_PATHS']
    SEED = _controls['SEED']

    for field in ("days_to_expiration", "days_in_trading_year", "risk_free_rate"):
        assert assumptions[field].nunique() == 1, f"The current simulator requires one common {field}."

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
    paths = simulate_paths(book, **simulation_scenario, n_paths=N_PATHS, seed=SEED)

    assert paths.shape == (N_PATHS, book.steps + 1, len(book.names))
    assert np.isfinite(paths).all() and (paths > 0).all()
    np.testing.assert_allclose(paths[:, 0, :], np.broadcast_to(book.spots, (N_PATHS, len(book.names))))
    print(f"Asset order: {book.names}")
    print(f"Paths shape: {paths.shape} — (path, date including inception, asset)")
    print(f"Seed: {SEED}; maturity: {book.maturity:.2f} years; rate: {book.rate:.1%}")

    sample_count = min(12, N_PATHS)
    sessions = np.arange(book.steps + 1)
    fig, axes = plt.subplots(1, len(book.names), figsize=(12, 3.8), sharey=True, squeeze=False)
    for asset_index, name in enumerate(book.names):
        ax = axes[0, asset_index]
        ax.plot(sessions, paths[:sample_count, :, asset_index].T, alpha=0.65, linewidth=0.8)
        ax.set(title=name, xlabel="Trading session")
        ax.grid(alpha=0.2)
    axes[0, 0].set_ylabel("Illustrative stock price")
    fig.suptitle("Correlated Q-GBM paths — illustrative inputs")
    fig.tight_layout()
    plt.show()

    terminal_spots = paths[:, -1, :]
    discount_factor = np.exp(-book.rate * book.maturity)
    discounted = terminal_spots * discount_factor
    mean_discounted = discounted.mean(axis=0)
    mean_se = discounted.std(axis=0, ddof=1) / np.sqrt(N_PATHS)
    mean_difference = mean_discounted - np.asarray(book.spots)
    z_scores = np.divide(
        mean_difference, mean_se, out=np.full(len(book.names), np.nan), where=mean_se > 0
    )
    martingale_check = pandas.DataFrame({
        "initial_spot": book.spots,
        "discounted_terminal_mean": mean_discounted,
        "mean_SE": mean_se,
        "mean_minus_spot": mean_difference,
        "difference_in_SEs": z_scores,
    }, index=pandas.Index(book.names, name="name"))
    display(martingale_check.round(6))

    # Evaluate actual simulated terminal call payoffs, in addition to the earlier example grid.
    terminal_call_payoffs = bs_payoff(
        ST=terminal_spots, K=np.asarray(book.strikes), kind=OPTION_KIND
    )
    short_terminal_payoffs = POSITION_SIGN * terminal_call_payoffs * book.units
    terminal_payoff_summary = pandas.DataFrame({
        "mean_call_payoff_per_unit": terminal_call_payoffs.mean(axis=0),
        "mean_short_position_payoff": short_terminal_payoffs.mean(axis=0),
        "discounted_mean_call_payoff_per_unit": (discount_factor * terminal_call_payoffs).mean(axis=0),
        "discounted_payoff_mean_SE": (
            (discount_factor * terminal_call_payoffs).std(axis=0, ddof=1) / np.sqrt(N_PATHS)
        ),
        "pricing_model_call_price": option_values.loc[list(book.names), "call_price"].to_numpy(),
    }, index=pandas.Index(book.names, name="name"))
    print("Simulated expiry payoffs; short-position payoff excludes premium and any hedge P&L:")
    display(terminal_payoff_summary.round(6))

    log_returns = np.diff(np.log(paths), axis=1)
    assert log_returns.shape == (N_PATHS, book.steps, len(book.names))
    pooled_returns = log_returns.reshape(-1, len(book.names))
    empirical_correlation = pandas.DataFrame(
        np.corrcoef(pooled_returns, rowvar=False), index=book.names, columns=book.names
    )
    correlation_difference = empirical_correlation - correlation_matrix
    volatility_check = pandas.DataFrame({
        "configured_path_vol": simulation_scenario["path_vols"],
        "empirical_annualized_vol": pooled_returns.std(axis=0, ddof=1) * np.sqrt(book.sessions_per_year),
    }, index=pandas.Index(book.names, name="name"))

    print("Configured return correlations:")
    display(correlation_matrix.round(4))
    print("Empirical return correlations:")
    display(empirical_correlation.round(4))
    print("Empirical minus configured correlations:")
    display(correlation_difference.round(4))
    print("Marginal annualized volatility check:")
    display(volatility_check.round(6))

    run_record = provenance(book, simulation_scenario, SEED, N_PATHS)
    run_record["option_kind"] = "European call"
    run_record["position_side"] = "short"
    run_record["position_sign"] = POSITION_SIGN
    run_record["quantity_convention"] = "notional / initial spot; share-equivalent call units; no exchange multiplier"
    run_record["option_portfolio"] = option_portfolio
    run_record["named_scenario"] = {
        "path_vols": scenario["path_vols"],
        "correlations": [
            {"name_a": name_a, "name_b": name_b, "correlation": value}
            for (name_a, name_b), value in scenario["correlations"].items()
        ],
    }
    notebook_path = ROOT / "Hedging_Study_Notebooks" / "00_study_setup.ipynb"
    notebook_source = json.loads(notebook_path.read_text())
    code_text = "\n\n".join(
        "".join(cell["source"]) for cell in notebook_source["cells"] if cell["cell_type"] == "code"
    )
    run_record["notebook_code_sha256"] = sha256(code_text.encode()).hexdigest()
    run_record["python_executable"] = sys.executable
    print(json.dumps(run_record, indent=2))
    return locals()

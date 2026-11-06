"""Conditional breadth research on a disclosed current-survivor master cohort.

Generates one master Q cube per dependence scenario, then takes named subsets.
This does not certify stage-7 point-in-time or derivative-overlay generalization.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

from hedging_harness.configuration import defaults
_DEFAULTS = defaults()['breadth']

ROOT=Path(__file__).resolve().parents[3]
if str(ROOT / "src") not in sys.path:sys.path.insert(0,str(ROOT / "src"))

from hedging_harness import HedgePolicy, hedge, initial_exposures, summarize
from hedging_harness.breadth import (
    COMPOSITION_SEEDS, DEFAULT_SIZES, complete_history_master, fit_calibration,
    fixed_notional_book, historical_equity_diagnostic, nested_compositions, simulate_master,
)
from hedging_harness.uncertainty import mean_interval, paired_tail_difference


def _table(frame):
    columns=list(frame.columns)
    lines=["| "+" | ".join(columns)+" |","| "+" | ".join("---" for _ in columns)+" |"]
    for _,row in frame.iterrows():
        lines.append("| "+" | ".join(f"{x:,.4f}" if isinstance(x,(float,np.floating)) else str(x) for x in row)+" |")
    return "\n".join(lines)


def plot_study(study):
    import matplotlib.pyplot as plt
    summary=study["summary"]
    fig,axes=plt.subplots(1,2,figsize=(13,4.8),sharey=True)
    for ax,scenario in zip(axes,study["protocol"]["scenarios"]):
        subset=summary.loc[summary.scenario.eq(scenario)]
        for policy in study["protocol"]["policies"]:
            cases=subset.loc[subset.policy.eq(policy)]
            canonical=cases.loc[cases.composition.eq("canonical")].sort_values("breadth")
            line, = ax.plot(canonical.breadth,canonical.loss_es95,marker="o",label=policy)
            for composition in sorted(set(cases.composition)-{"canonical"}):
                other=cases.loc[cases.composition.eq(composition)].sort_values("breadth")
                ax.scatter(other.breadth,other.loss_es95,alpha=.35,s=20,color=line.get_color())
        ax.set(title=scenario.replace("_"," "),xlabel="Number of underlying names")
        ax.set_xticks(study["protocol"]["sizes"])
        ax.grid(alpha=.2)
    axes[0].set_ylabel("Simulated portfolio ES95 loss ($)")
    axes[0].legend(fontsize=8)
    fig.suptitle(f"Conditional current-survivor breadth: ${study['protocol']['total_notional']:,.0f} total notional; canonical lines, other compositions as dots")
    fig.tight_layout()
    return fig


def run_study(*,prices_path=None,selection_path=None,output_dir=None,n_paths=_DEFAULTS['n_paths'],
              n_bootstrap=_DEFAULTS['n_bootstrap'],seed=_DEFAULTS['seed'],cutoff=_DEFAULTS['cutoff'],lookback=_DEFAULTS['lookback'],
              composition_seeds=tuple(_DEFAULTS['composition_seeds']),sizes=tuple(_DEFAULTS['sizes']),
              total_notional=_DEFAULTS['total_notional'],cost_bps=_DEFAULTS['cost_bps'],steps=_DEFAULTS['steps'],rate=_DEFAULTS['rate'],stress_mix=_DEFAULTS['stress_mix'],
              make_plot=_DEFAULTS['make_plot']):
    prices_path=Path(prices_path or ROOT/"data/market/prices_financial_50_unbalanced.csv").resolve()
    selection_path=Path(selection_path or ROOT/"results/research-release-1/release-1/selection.json").resolve()
    metadata_path=prices_path.parent/"financial_50_metadata.json"
    coverage_path=prices_path.parent/"financial_50_coverage.csv"
    universe_path=prices_path.parent/"financial_50_universe.csv"
    selection=json.loads(selection_path.read_text())
    selected_policy=HedgePolicy(**selection["policy"])
    locked_name=selection["selected_policy"]
    if selected_policy.label!=locked_name or selected_policy.kind!="maturity_band" or selected_policy.band!=.05:
        raise ValueError("This extension must use the locked gate-1 maturity_band_050 policy without reselection.")
    budget=float(selection["budget_dollars"])
    policy_map={locked_name:selected_policy,"daily":HedgePolicy(hedge_every=1,label="daily"),
                "weekly":HedgePolicy(hedge_every=5,label="weekly")}
    prices=pd.read_csv(prices_path,index_col="date",parse_dates=["date"])
    source_metadata=json.loads(metadata_path.read_text())
    price_hash=sha256(prices_path.read_bytes()).hexdigest()
    if source_metadata.get("files",{}).get("prices",{}).get("sha256")!=price_hash:
        raise ValueError("Price data no longer match the market-data audit hash.")
    master=complete_history_master(prices)
    source_coverage=pd.read_csv(coverage_path).set_index("stable_id")
    if set(source_coverage.index)!=set(prices.columns):
        raise ValueError("The source coverage catalog does not match all supplied names.")
    np.testing.assert_array_equal(source_coverage.loc[master.availability_audit.index,"observations"],
                                  master.availability_audit.observations)
    complete_from_source=set(source_coverage.index[source_coverage.status.eq("observed_full")])
    if complete_from_source!=set(master.names):
        raise ValueError("Actual complete-history availability disagrees with the source audit.")
    universe=pd.read_csv(universe_path).set_index("stable_id")
    industries=universe["industry"].fillna("unclassified_current_snapshot").to_dict()
    compositions=nested_compositions(master.names,sizes=tuple(sizes),seeds=tuple(composition_seeds))
    calibration=fit_calibration(master.prices,cutoff=cutoff,lookback=lookback,shrinkage=_DEFAULTS["shrinkage"])
    stamp=datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    destination=Path(output_dir or ROOT/"results"/f"breadth-{stamp}").resolve()
    destination.mkdir(parents=True,exist_ok=False)
    scenarios=["calibrated_dependence","synthetic_common_shock_stress"]
    protocol=dict(
        created_utc=datetime.now(timezone.utc).isoformat(),
        purpose="conditional numerical breadth and composition diagnostic; no policy reselection",
        calibration_cutoff=str(pd.Timestamp(cutoff).date()),calibration_returns=lookback,
        calibration_last_observation=str(calibration.last_observation.date()),
        covariance_model="fixed 20 percent diagonal shrinkage of past sample daily covariance",
        pricing_sigma="past realized-volatility proxy, not market implied volatility",
        calibration_data_sha256=calibration.calibration_data_sha256,
        master_names=list(master.names),excluded_partial_names=list(master.excluded_names),
        master_screen="complete full 2010–2026 history of CURRENT survivor snapshot; retrospective availability conditioning",
        master_selection_available_at_2020_cutoff=False,
        current_classification_is_historical_gics=False,
        sizes=list(sizes),composition_seeds=list(composition_seeds),
        compositions={label:{str(size):list(names) for size,names in chain.items()} for label,chain in compositions.items()},
        total_notional=float(total_notional),notional_allocation="equal initial underlying dollar notional within each subset",
        normalized_spot=100.,normalized_strike=100.,steps=steps,sessions_per_year=252,rate=rate,
        n_paths=n_paths,seed=seed,scenarios=scenarios,stress_mix=stress_mix,
        stress_convention="(1-stress_mix)*calibrated correlation + stress_mix*all-ones correlation; synthetic dependence stress only",
        measure="Q; drift=constant financing rate; historical dependence proxy does not identify market risk-neutral dependence",
        policies={label:asdict(policy) for label,policy in policy_map.items()},
        locked_selection_path=str(selection_path),locked_selection_sha256=sha256(selection_path.read_bytes()).hexdigest(),
        policy_reselected=False,cost_bps=cost_bps,budget_dollars=budget,
        n_bootstrap=n_bootstrap,bootstrap_seed=_DEFAULTS["paired_bootstrap_seed"],
        bootstrap_convention="paired independent-Monte-Carlo-outcome percentile ES differences within each book; pointwise intervals",
        historical_diagnostic="2021–2026 nonoverlapping20-session static equity price-only periods, conditional2026complete-survivor cohort",
        historical_block_length_periods=4,
        source_sha256={str(path.relative_to(ROOT)):sha256(path.read_bytes()).hexdigest() for path in
                       (Path(__file__),ROOT/"src/hedging_harness/breadth.py",ROOT/"src/hedging_harness/core.py",
                        ROOT/"src/hedging_harness/policies.py",ROOT/"src/hedging_harness/risk_models.py",ROOT/"src/hedging_harness/uncertainty.py",
                        ROOT/"src/hedging_harness/legacy.py",
                        ROOT/"src/BlackScholes_Functions/BlackScholes_D1D2_Price_Payoff_Greeks.py",
                        ROOT/"src/MonteCarlo_Functions/MonteCarlo_ExactPathwayGeneration.py")},
        data_sha256={str(path.relative_to(ROOT)):sha256(path.read_bytes()).hexdigest() for path in
                     (prices_path,metadata_path,coverage_path,universe_path)},
    )
    protocol_text=json.dumps(protocol,indent=2)
    (destination/"protocol.json").write_text(protocol_text+"\n")
    protocol_hash=sha256((destination/"protocol.json").read_bytes()).hexdigest()
    master.availability_audit.to_csv(destination/"availability_audit_all_50.csv")
    calibration.annual_volatilities.to_csv(destination/"calibrated_annual_volatilities.csv")
    calibration.daily_covariance.to_csv(destination/"calibrated_daily_covariance.csv")
    calibration.correlation.to_csv(destination/"calibrated_correlation.csv")
    summary_rows,paired_rows,group_rows,master_rows,book_rows=[],[],[],[],[]
    outcome_dir=destination/"portfolio_outcomes"
    outcome_dir.mkdir()
    for scenario in scenarios:
        master_paths=simulate_master(calibration,n_paths=n_paths,seed=seed,scenario=scenario,
                                     stress_mix=stress_mix,steps=steps,rate=rate)
        master_rows.append(dict(scenario=scenario,master_scenario_id=master_paths.scenario_id,
                                names=len(master_paths.names),n_paths=n_paths,observations=steps+1,
                                path_storage_MB=master_paths.paths.nbytes/1e6))
        master_paths.correlation.to_csv(destination/f"correlation_{scenario}.csv")
        for composition,chain in compositions.items():
            for breadth,names in chain.items():
                book=fixed_notional_book(names,calibration,total_notional=total_notional,steps=steps,rate=rate)
                np.testing.assert_allclose(sum(book.notionals),total_notional,atol=1e-8)
                subset_paths=master_paths.subset(names)
                exposures=initial_exposures(book)
                book_rows.append(dict(scenario=scenario,composition=composition,breadth=breadth,
                                      names=json.dumps(names),total_notional=sum(book.notionals),
                                      initial_premium=exposures.initial_premium.sum(),
                                      vega_per_vol_point=exposures.option_vega_per_vol_point.sum()))
                case_results={}
                archive={}
                for label,policy in policy_map.items():
                    result=hedge(book,subset_paths,policy=policy,cost_bps=cost_bps,
                                 scenario_label=f"{scenario}/{composition}/{breadth}")
                    case_results[label]=result
                    portfolio_pnl=result.terminal_pnl.sum(axis=1)
                    portfolio_cost=result.financed_costs.sum(axis=1)
                    interval=mean_interval(portfolio_cost)
                    metrics=summarize(result).loc["Portfolio"].to_dict()
                    summary_rows.append(dict(scenario=scenario,composition=composition,breadth=breadth,policy=label,
                                             total_notional=sum(book.notionals),master_scenario_id=master_paths.scenario_id,
                                             subset_scenario_id=result.scenario_id,
                                             cost_mean_lower=interval["lower"],cost_mean_upper=interval["upper"],
                                             cost_budget_upper_bound_passes=interval["upper"]<=budget,**metrics))
                    archive[f"{label}_portfolio_pnl"]=portfolio_pnl
                    archive[f"{label}_financed_cost"]=portfolio_cost
                    archive[f"{label}_peak_borrowing"]=result.peak_portfolio_borrowing
                    tail=np.argsort(portfolio_pnl)[:max(1,int(np.ceil(.05*n_paths)))]
                    grouped={}
                    for name,value in zip(names,-result.terminal_pnl[tail].mean(axis=0)):
                        group=industries.get(name,"unclassified_current_snapshot")
                        grouped[group]=grouped.get(group,0.)+float(value)
                    np.testing.assert_allclose(sum(grouped.values()),metrics["loss_es95"],atol=1e-7)
                    for group,value in grouped.items():
                        group_rows.append(dict(scenario=scenario,composition=composition,breadth=breadth,
                                               policy=label,current_industry=group,
                                               portfolio_tail_loss_contribution=value))
                for reference in ("daily","weekly"):
                    left,right=case_results[locked_name],case_results[reference]
                    if left.scenario_id!=right.scenario_id:raise AssertionError("Policy comparison paths differ.")
                    interval=paired_tail_difference(left.terminal_pnl.sum(axis=1),right.terminal_pnl.sum(axis=1),
                                                    n_bootstrap=n_bootstrap,seed=_DEFAULTS["paired_bootstrap_seed"])
                    paired_rows.append(dict(scenario=scenario,composition=composition,breadth=breadth,
                                            left_policy=locked_name,right_policy=reference,
                                            subset_scenario_id=left.scenario_id,**interval))
                np.savez_compressed(outcome_dir/f"{scenario}__{composition}__{breadth}.npz",**archive)
                print(f"Completed {scenario}/{composition}/{breadth}",flush=True)
                del subset_paths,case_results
        del master_paths
    summary=pd.DataFrame(summary_rows)
    paired=pd.DataFrame(paired_rows)
    group_contributions=pd.DataFrame(group_rows)
    master_scenarios=pd.DataFrame(master_rows)
    books=pd.DataFrame(book_rows)
    historical=historical_equity_diagnostic(master.prices,compositions,total_notional=total_notional,
                                            industries=industries,n_bootstrap=n_bootstrap)
    for name,frame in [("policy_summary",summary),("paired_ES_differences",paired),
                       ("model_tail_group_contributions",group_contributions),
                       ("master_scenarios",master_scenarios),("book_details",books),
                       ("historical_equity_periods",historical["periods"]),
                       ("historical_equity_summary",historical["summary"]),
                       ("historical_tail_group_contributions",historical["tail_group_contributions"])]:
        frame.to_csv(destination/f"{name}.csv",index=False)
    manifest=dict(
        generated_utc=datetime.now(timezone.utc).isoformat(),protocol_sha256=protocol_hash,
        protocol_hash_convention="SHA256 of exact protocol.json file bytes including terminal newline",
        source_sha256=protocol["source_sha256"],data_sha256=protocol["data_sha256"],
        declared_names=len(prices.columns),complete_master_names=len(master.names),
        partial_names_retained_in_audit=len(master.excluded_names),
        master_simulations=len(scenarios),policy_cases=len(summary),
        total_notional_constant=bool(np.allclose(summary.total_notional,total_notional)),
        master_paths_reused=True,policy_reselected=False,
        conditional_breadth_computation_passed=True,full_stage7_gate_passed=False,
        point_in_time_membership_verified=False,overlay_generalization_evidence_included=False,
        historical_option_quotes_available=False,
        limitations=[
            "Complete-history filtering through 2026 uses future availability relative to 2020 calibration cutoff",
            "Current-survivor2026 universe and classifications are not historical membership or historical GICS",
            "2021–2026 static-equity results are conditional diagnostics, not untouched-universe historical OOS",
            "Historical option quotes unavailable; Q options use realized-volatility proxy, not marketIV",
            "Dependence stress is synthetic; no jump/stochastic-volatility or crisis probability claim",
            "Different breadths/compositions share master innovations and historical episodes; they are not independent replications",
            "Monte Carlo ES intervals exclude calibration/model uncertainty and are pointwise",
            "Historical diagnostic excludes derivative overlays, costs, dividends and financing",
            "Only a few historical 20-session tail periods support ES95; block intervals remain approximate",
        ],
    )
    study=dict(protocol=protocol,summary=summary,paired=paired,historical=historical,
               master_scenarios=master_scenarios,availability=master.availability_audit,
               manifest=manifest,output_dir=destination)
    if make_plot:
        fig=plot_study(study)
        fig.savefig(destination/"breadth_policy_ES95.png",dpi=150,bbox_inches="tight")
        import matplotlib.pyplot as plt
        plt.close(fig)
    canonical=summary.loc[summary.composition.eq("canonical"),[
        "scenario","breadth","policy","mean_pnl","pnl_std","loss_es95","mean_financed_cost","cost_budget_upper_bound_passes"
    ]]
    report=("# Conditional breadth and composition research\n\n"
            f"All {len(prices.columns)} requested current issuer IDs remain in the coverage audit. "
            f"The master universe contains {len(master.names)} complete histories; the {len(master.excluded_names)} partial names "
            f"are explicitly excluded without filling: {', '.join(master.excluded_names)}. "
            "This retrospective full-history condition uses availability through 2026 and is not an eligibility rule known in 2020.\n\n"
            "## Frozen experiment\n\n"
            f"Past-only calibration through {calibration.last_observation.date()} uses {lookback} log returns and fixed 20% "
            f"diagonal covariance shrinkage. {n_paths:,} Q paths are generated once for each full {len(master.names)}-name master "
            "scenario, and every nested 3/10/25/40 book takes its named columns from that cube. "
            f"Total underlying notional stays ${total_notional:,.0f}. The canonical chain preserves the core three and core ten; "
            "two predeclared seeded chains vary composition. A common-shock correlation mixture is a synthetic stress, not an observed "
            "stress distribution. Historical realized volatilities are model-pricing proxies, not market implied volatilities.\n\n"
            f"The locked gate-1 rule is **{locked_name}**. It is compared with daily and five-session rebalancing "
            f"at {cost_bps:g} bp without reselection. Budget feasibility under the original ${budget:,.0f} expected financed-cost "
            "cap is reported rather than assumed to generalize.\n\n"
            "## Canonical policy outcomes\n\n"+_table(canonical)+"\n\n"
            "The full policy table also includes both seeded composition chains. `paired_ES_differences.csv` contains "
            "same-outcome bootstrap intervals for ES(locked) minus ES(reference), not ES of the P&L difference. "
            "A negative estimate favors the locked policy under this loss statistic. Pointwise intervals do not establish "
            "simultaneous dominance across all books or model validity.\n\n"
            "## Actual static-equity diagnostic\n\n"+_table(historical["summary"])+"\n\n"
            "Each 20-session interval holds equal initial dollar equity amounts and re-establishes the same notional at the "
            "next nonoverlapping interval. These are price-only diagnostics without derivatives, costs, funding or dividends. "
            "They condition on a 2026 survivor/availability-selected cohort; they are not untouched-universe historical OOS. "
            "Current-industry tail contributions use the same worst portfolio intervals and sum to portfolio ES. "
            "Circular four-period block intervals address some serial dependence; the small number of tail periods "
            "does not become more independent evidence merely because more companies were observed.\n\n"
            "## Stage-7 boundary\n\n"
            "Computational breadth, label alignment, fixed-notional comparisons and explicit exclusion accounting pass. "
            "**The full stage-7 gate remains false.** Point-in-time membership, historically valid classifications, "
            "plausible derivative execution and untouched overlay-policy generalization are not supplied by this diagnostic. "
            "FMP's documented absence of options data also prevents a historical market-option backtest claim.\n")
    (destination/"report.md").write_text(report)
    manifest["artifacts_sha256"]={str(file.relative_to(destination)):sha256(file.read_bytes()).hexdigest()
                                 for file in sorted(destination.rglob("*")) if file.is_file()}
    (destination/"manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
    return study


def main():
    import matplotlib
    matplotlib.use("Agg")
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prices",type=Path)
    parser.add_argument("--selection",type=Path)
    parser.add_argument("--output-dir",type=Path)
    parser.add_argument("--n-paths",type=int,default=_DEFAULTS["n_paths"])
    parser.add_argument("--bootstrap",type=int,default=_DEFAULTS["n_bootstrap"])
    args=parser.parse_args()
    study=run_study(prices_path=args.prices,selection_path=args.selection,output_dir=args.output_dir,
                    n_paths=args.n_paths,n_bootstrap=args.bootstrap)
    print(study["summary"].loc[study["summary"].composition.eq("canonical"),[
        "scenario","breadth","policy","pnl_std","loss_es95","mean_financed_cost"
    ]].round(4).to_string(index=False))
    print(f"Conditional breadth passed: {study['manifest']['conditional_breadth_computation_passed']}")
    print(f"Full stage-7 gate passed: {study['manifest']['full_stage7_gate_passed']}")
    print(f"Artifacts: {study['output_dir']}")


if __name__=="__main__":main()

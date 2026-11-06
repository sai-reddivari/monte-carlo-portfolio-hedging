"""Post-hoc review of immutable Stage 6 outcomes; no policy reselection.

Run from the repository with its Python environment. Writes only --output-dir.
Statistical estimates reproduce the frozen bootstrap independently in this file.
Collar sizing/initial delta reconstruction is independent of the replay engine.
"""
import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd


def digest(path):
    return sha256(Path(path).read_bytes()).hexdigest()


def es(x):
    return -np.sort(x, axis=-1)[..., :math.ceil(x.shape[-1] * .25)].mean(axis=-1)


def interval(left, right, block, draws=5000, seed=730601):
    n = len(left)
    rng = np.random.default_rng(seed)
    starts = rng.integers(0, n, size=(draws, math.ceil(n/block)))
    idx = ((starts[:, :, None] + np.arange(block)) % n).reshape(draws, -1)[:, :n]
    differences = es(left[idx]) - es(right[idx])
    lo, hi = np.quantile(differences, [.025, .975])
    return float(es(left)-es(right)), float(lo), float(hi)


def normal_cdf(x):
    return .5 * (1 + math.erf(x/math.sqrt(2)))


def price_delta(spot, strike, sigma, tau, rate, kind):
    d1 = (math.log(spot/strike)+(rate+.5*sigma*sigma)*tau)/(sigma*math.sqrt(tau))
    d2 = d1-sigma*math.sqrt(tau)
    if kind == 'call':
        return spot*normal_cdf(d1)-strike*math.exp(-rate*tau)*normal_cdf(d2), normal_cdf(d1)
    return strike*math.exp(-rate*tau)*normal_cdf(-d2)-spot*normal_cdf(-d1), normal_cdf(d1)-1


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--repo',type=Path,default=Path.cwd())
    parser.add_argument('--output-dir',type=Path,default=Path('/tmp/astra_statistical_review'))
    args=parser.parse_args()
    root=args.repo.resolve()
    source=root/'results/equity-overlays-20261106T023430248130Z'
    out=args.output_dir.resolve(); out.mkdir(parents=True,exist_ok=True)
    protocol=json.loads((source/'protocol.json').read_text())
    config=protocol['config']
    records=pd.read_csv(source/'windows.csv')
    summary=pd.read_csv(source/'summary.csv')
    pivot=records.loc[records.split.eq('test')].pivot(index='key',columns='label',values='pnl_pct').sort_index()
    selected=['reduced_75']+[v['label'] for v in protocol['selection'].values()]
    rows=[]
    for reference in ['unhedged','reduced_75']:
        for policy in selected:
            if policy==reference: continue
            for block in [2,4,6]:
                estimate,lower,upper=interval(pivot[policy].to_numpy(),pivot[reference].to_numpy(),block)
                rows.append(dict(analysis_status='post_hoc_exploratory_no_reselection',split='test',
                    policy=policy,reference=reference,metric='difference_in_mean_worst_6_of_23_losses_pct_capital',
                    estimate=estimate,lower=lower,upper=upper,confidence=.95,block_windows=block,
                    n_windows=len(pivot),tail_windows=math.ceil(.25*len(pivot)),bootstrap_draws=5000,seed=730601))
    comparisons=pd.DataFrame(rows); comparisons.to_csv(out/'paired_es_diagnostics.csv',index=False)
    original=pd.read_csv(source/'uncertainty.csv')
    check=comparisons.loc[comparisons.reference.eq('unhedged')&comparisons.block_windows.eq(4)].merge(
        original.loc[original.split.eq('test')],left_on='policy',right_on='label')
    es_residual=max(float(np.abs(check[a]-check[b]).max()) for a,b in
                    [('estimate','es_difference_pct'),('lower','es_lower_pct'),('upper','es_upper_pct')])

    prices=pd.read_csv(root/config['data']['core_prices'],index_col='date',parse_dates=['date'])
    weights={**config['book']['longs'],**{k:-v for k,v in config['book']['shorts'].items()}}
    cap=config['capital']; rate=config['execution']['rate']; mult=config['execution']['contract_multiplier']
    annual=config['execution']['sessions_per_year']; sessions=config['windows']['sessions']; tau=sessions/annual
    candidate=next(c for c in protocol['candidates'] if c['label']==protocol['selection']['structures']['label'])
    assert candidate['structure']=='collar'
    collar_rows=[]; exposures=[]
    for raw in protocol['test_windows']:
        decision=pd.Timestamp(raw['decision_date']); start=pd.Timestamp(raw['start'])
        hist=prices.loc[:decision]; decision_spot=hist.iloc[-1]; execution_spot=prices.loc[start]
        returns=np.log(hist/hist.shift(1)).dropna().iloc[-config['estimation']['lookback']:]
        vols=returns.std(ddof=1)*math.sqrt(annual)
        shares={name:math.trunc(w*cap/decision_spot[name]) for name,w in weights.items()}
        plans=[]; full=0.
        for name,sh in shares.items():
            if sh<=0:continue
            for kind,moneyness,sign in [('put',candidate['long_put'],1),('call',candidate['short_call'],-1)]:
                strike=moneyness*decision_spot[name]
                quote,_=price_delta(decision_spot[name],strike,vols[name],tau,rate,kind)
                full+=sign*sh*quote
                plans.append((name,sh,kind,strike,sign))
        budget=candidate['annual_budget']*cap*tau
        coverage=1 if full<=budget else budget/full
        stock_delta=sum(shares[name]*execution_spot[name] for name in shares)
        option_delta=0.; net_premium=0.
        for name,sh,kind,strike,sign in plans:
            contracts=math.floor(coverage*sh/mult+1e-9)
            units=sign*contracts*mult
            execution_value,delta=price_delta(execution_spot[name],strike,vols[name],tau,rate,kind)
            option_delta+=units*delta*execution_spot[name]
            net_premium+=units*execution_value
            collar_rows.append(dict(window=raw['key'],underlying=name,kind=kind,core_shares=sh,
                 contracts=sign*contracts,multiplier=mult,signed_units=units,
                 strike=strike,execution_spot=float(execution_spot[name]),sigma=float(vols[name]),
                 long_instrument_delta=delta,signed_delta_dollars=units*delta*execution_spot[name],
                 coverage=coverage,within_covered_shares=abs(units)<=sh,
                 positive_put_negative_call=(units>=0 if kind=='put' else units<=0)))
        saved=records.loc[records.key.eq(raw['key'])&records.label.eq(candidate['label'])].iloc[0]
        exposures.append(dict(window=raw['key'],stock_dollar_delta_pct=100*stock_delta/cap,
            option_dollar_delta_pct=100*option_delta/cap,total_dollar_delta_pct=100*(stock_delta+option_delta)/cap,
            saved_dollar_delta_pct=saved.delta_adjusted_net_pct,net_premium=net_premium,
            saved_net_premium=saved.premium_paid-saved.premium_received))
    collar=pd.DataFrame(collar_rows); exposure=pd.DataFrame(exposures)
    collar.to_csv(out/'collar_signed_legs_reconstruction.csv',index=False)
    exposure.to_csv(out/'collar_initial_exposure_reconstruction.csv',index=False)
    summary.loc[summary.split.eq('test')&summary.label.isin(['unhedged']+selected)].to_csv(out/'selected_test_summary.csv',index=False)
    artifacts=['paired_es_diagnostics.csv','collar_signed_legs_reconstruction.csv','collar_initial_exposure_reconstruction.csv','selected_test_summary.csv']
    metadata=dict(created_utc=datetime.now(timezone.utc).isoformat(),
        analysis_status='post_hoc_exploratory_review_of_already_exposed_test_results',
        no_policy_reselection=True,no_new_market_data=True,source_run=str(source.relative_to(root)),
        protocol_sha256=digest(source/'protocol.json'),source_windows_sha256=digest(source/'windows.csv'),
        source_summary_sha256=digest(source/'summary.csv'),frozen_protocol_source_hashes=protocol['source_sha256'],
        input_hashes={p:digest(root/p) for p in protocol['input_sha256']},
        inputs_match_frozen=all(digest(root/p)==h for p,h in protocol['input_sha256'].items()),
        script_sha256=digest(__file__),numpy_version=np.__version__,pandas_version=pd.__version__,
        statistic='mean worst ceil(0.25*n) terminal window losses; 6 of 23 test windows',
        bootstrap='paired circular moving blocks; recompute own tail per policy in each draw; 5000 draws seed730601; lengths2/4/6; pointwise95%',
        multiplicity_adjusted=False,uncertainty_excludes='sampling regimes absent from data, model-price uncertainty and policy-selection uncertainty',
        baseline_interval_max_abs_reproduction_residual=es_residual,
        collar_checks=dict(all_signs_correct=bool(collar.positive_put_negative_call.all()),
             all_calls_covered=bool(collar.within_covered_shares.all()),windows=len(exposure),legs=len(collar),
             maximum_delta_reconstruction_abs_error=float(abs(exposure.total_dollar_delta_pct-exposure.saved_dollar_delta_pct).max()),
             maximum_premium_reconstruction_abs_error=float(abs(exposure.net_premium-exposure.saved_net_premium).max()),
             mean_stock_delta_pct=float(exposure.stock_dollar_delta_pct.mean()),
             mean_option_delta_pct=float(exposure.option_dollar_delta_pct.mean()),
             mean_total_delta_pct=float(exposure.total_dollar_delta_pct.mean())),
        exposure_assumptions='Initial local Black-Scholes delta at execution close, fixed decision-estimated volatility, 63/252 maturity, zero dividends, rate4%; delta is not beta and is not static over the window. Saved beta_net_pct contains equity and ETF exposures only, omitting option beta.',
        artifacts_sha256={p:digest(out/p) for p in artifacts})
    (out/'metadata.json').write_text(json.dumps(metadata,indent=2)+'\n')
    print(json.dumps(metadata,indent=2))


if __name__=='__main__':
    main()

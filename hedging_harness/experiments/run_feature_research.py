"""Frozen chronological tests of price, market and filing-vintage information."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from dataclasses import asdict
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import sys
import tempfile

ROOT=Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
import numpy as np
import pandas as pd
from hedging_harness.feature_models import (
    PRICE_FEATURES,MARKET_FEATURES,design_matrix,filing_balance_sheet_ratios,
    fit_log_variance_ridge,price_market_features,release_aware_asof,
)
from hedging_harness.risk_models import (
    RiskProtocol,add_losses,chronological_nonoverlap,moving_block_mean_interval,
    validate_prices,variance_forecasts,
)

from hedging_harness.configuration import defaults
RIDGE_ALPHAS=tuple(defaults()['ridge_alphas'])


def _hash(path):return sha256(Path(path).read_bytes()).hexdigest()
def _json(path,value):Path(path).write_text(json.dumps(value,indent=2,allow_nan=False)+'\n')
def _table(frame):
    def fmt(v):return f'{v:.6g}' if isinstance(v,(float,np.floating)) else str(v).replace('|','/')
    return '\n'.join(['| '+' | '.join(frame.columns)+' |','| '+' | '.join('---' for _ in frame.columns)+' |',*['| '+' | '.join(fmt(v) for v in row)+' |' for row in frame.itertuples(index=False,name=None)]])


def _audit_admission(include_sec_core10=False):
    paths=[ROOT/'results/feature-audit/coverage.json',ROOT/'data/market/features/company_feature_fields_long.csv',ROOT/'data/market/features/treasury_rates_lagged_samples.csv']
    status={'FMP_macro_layer_admitted':False,'FMP_company_snapshot_layer_admitted':False}
    for label,path in [('FMP_company_fields',paths[1]),('FMP_treasury_samples',paths[2])]:
        if path.is_file():
            frame=pd.read_csv(path)
            eligible=frame['strict_historical_feature_usable'].astype(str).str.lower().eq('true').sum()
            status[label]={'observed_rows':len(frame),'strictly_admissible_rows':int(eligible)}
            if eligible:raise ValueError('New eligible FMP data require an explicit reviewed feature-schema extension.')
    sec=ROOT/'data/market/features/sec_facts/sec_filing_snapshots.csv'
    status['official_SEC_filing_layer_admitted']=sec.is_file()
    if sec.is_file():paths.extend([sec,sec.parent/'sec_filing_facts_long.csv',sec.parent/'sec_field_year_coverage.csv'])
    sec_core10=ROOT/'data/market/features/sec_facts_core10/sec_filing_snapshots.csv'
    if include_sec_core10:
        if not sec_core10.is_file():raise ValueError('The predeclared core10 SEC extension is unavailable.')
        paths.extend([sec_core10,sec_core10.parent/'sec_filing_facts_long.csv',sec_core10.parent/'sec_field_year_coverage.csv',sec_core10.parent/'sec_fact_coverage.json'])
    status['SEC_core10_extension_admitted']=bool(include_sec_core10)
    return status,{str(path):_hash(path) for path in paths if path.is_file()},sec,sec_core10


def _base_panel(prices,factors,protocol):
    simple=variance_forecasts(prices,protocol)
    keys=['origin','asset','horizon']
    base=simple.loc[simple['model'].eq('rv_long'),[
        'origin','target_start','target_end','asset','horizon','realized_variance','feature_last_date','panel'
    ]].copy()
    wide=simple.pivot(index=keys,columns='model',values='variance_forecast').reset_index()
    features=price_market_features(prices,factors,lookback=protocol.lookback,recent_window=protocol.recent_window,ewma_lambda=protocol.ewma_lambda)
    return base.merge(wide,on=keys,validate='one_to_one').merge(features.drop(columns='feature_last_date'),on=['origin','asset'],validate='many_to_one')


def _cohorts(base,assets,sec_path,protocol,sec_core10_path=None):
    scopes={'core_ten_market':{'assets':tuple(assets),'balance_features':(), 'interactions':()}}
    ratios=None
    if sec_path.is_file():
        snapshots=pd.read_csv(sec_path)
        ratios=filing_balance_sheet_ratios(snapshots)
        required={'JPM','PNC','GS'}
        if not required.issubset(assets):raise ValueError('The SEC study requires its predeclared JPM/PNC/GS cohort.')
        scopes['sec_three_generic']={'assets':('JPM','PNC','GS'),'balance_features':('liabilities_assets',),'interactions':('liabilities_assets_XLF_return_5',)}
        scopes['bank_two_funding']={'assets':('JPM','PNC'),'balance_features':('bank_deposits_liabilities','bank_cash_assets'),'interactions':('bank_deposits_liabilities_XLF_return_5','bank_cash_assets_XLF_return_5')}
    if sec_core10_path is not None:
        broad_ratios=filing_balance_sheet_ratios(pd.read_csv(sec_core10_path))
        scopes['sec_ten_generic']={'assets':tuple(assets),'balance_features':('liabilities_assets',),'interactions':('liabilities_assets_XLF_return_5',),'ratio_source':broad_ratios}
        scopes['bank_six_deposits']={'assets':('JPM','PNC','BAC','WFC','C','USB'),'balance_features':('bank_deposits_liabilities',),'interactions':('bank_deposits_liabilities_XLF_return_5',),'ratio_source':broad_ratios}
    output={};coverage=[]
    for name,scope in scopes.items():
        frame=base.loc[base['asset'].isin(scope['assets'])].copy()
        before=len(frame)
        common=list(PRICE_FEATURES)+list(MARKET_FEATURES)
        if scope['balance_features']:
            origins=frame.rename(columns={'asset':'symbol'})
            joined=release_aware_asof(origins,scope.get('ratio_source',ratios),feature_columns=list(scope['balance_features']),max_age_days=180,max_period_age_days=180)
            frame=joined.rename(columns={'symbol':'asset'})
            for feature in scope['balance_features']:
                frame[f'{feature}_XLF_return_5']=frame[feature]*frame['XLF_return_5']
            common+=list(scope['balance_features'])+list(scope['interactions'])
        frame=frame.dropna(subset=common+['rv_long','rv_recent','ewma'])
        complete=frame.groupby(['origin','horizon'])['asset'].transform('nunique').eq(len(scope['assets']))
        frame=frame.loc[complete]
        frame=chronological_nonoverlap(frame,protocol)
        frame['cohort']=name
        scope['panel']=frame
        scope['layers']={'ridge_price':tuple(PRICE_FEATURES),'ridge_market_sector':tuple(PRICE_FEATURES)+tuple(MARKET_FEATURES)}
        if scope['balance_features']:
            scope['layers']['ridge_balance_sheet']=tuple(PRICE_FEATURES)+tuple(MARKET_FEATURES)+scope['balance_features']
            scope['layers']['ridge_interactions']=scope['layers']['ridge_balance_sheet']+scope['interactions']
        output[name]=scope
        coverage.append({'cohort':name,'assets':','.join(scope['assets']),'input_asset_origin_rows':before,'eligible_nonoverlap_rows':len(frame),
                         'test_5_session_origins':frame.loc[frame['split'].eq('test')&frame['horizon'].eq(5),'origin'].nunique(),
                         'test_20_session_origins':frame.loc[frame['split'].eq('test')&frame['horizon'].eq(20),'origin'].nunique(),
                         'latest_test_origin':str(frame.loc[frame['split'].eq('test'),'origin'].max()),
                         'latest_test_target':str(frame.loc[frame['split'].eq('test'),'target_end'].max())})
    return output,pd.DataFrame(coverage)


def run(prices_path,factors_path,output_dir,*,include_sec_core10=False):
    protocol=RiskProtocol()
    prices_path,factors_path=Path(prices_path).resolve(),Path(factors_path).resolve()
    prices=validate_prices(pd.read_csv(prices_path,index_col='date',parse_dates=True))
    factors=validate_prices(pd.read_csv(factors_path,index_col='date',parse_dates=True))
    if not prices.index.equals(factors.index):raise ValueError('Stock/factor histories must align exactly.')
    admission,audit_hashes,sec_path,sec_core10_path=_audit_admission(include_sec_core10)
    out=Path(output_dir).resolve();out.mkdir(parents=True,exist_ok=False)
    frozen={
        'risk_protocol':asdict(protocol),'ridge_alphas':list(RIDGE_ALPHAS),
        'selection_objective':'minimum_validation_mean_QLIKE_per_layer_and_horizon',
        'fit_rule':'Scaler, coefficients and smearing fit train only; alpha from validation; no train+validation refit.',
        'price_features':list(PRICE_FEATURES),'market_sector_increment_features':list(MARKET_FEATURES),
        'SEC_core10_extension':bool(include_sec_core10),
        'cohort_hypotheses':{
            'core_ten_market':'Own price -> observed SPY/XLF market/sector information.',
            'sec_three_generic':'JPM/PNC/GS: market -> liabilities/assets -> liability ratio times XLF5-session return.',
            'bank_two_funding':'JPM/PNC: market -> deposits/liabilities and cash-due-banks/assets -> each ratio times XLF5-session return; GS excluded from bank deposit hypothesis.',
            'sec_ten_generic':'Optional predeclared extension: all10generic liabilities/assets and XLF interaction, same splits/grid.',
            'bank_six_deposits':'Optional predeclared extension: JPM/PNC/BAC/WFC/C/USB deposits/liabilities and XLF interaction only; no sparse cash substitution.',
        },
        'target':'TOTAL underlying next5/20session squared log returns, modeled as log daily variance with training-only smearing.',
        'forecast_timing':'After origin close; filings cutoff at16:00NewYork, conservative next-XNYS-close bound after actual SEC filed DATE. Not actual acceptance timestamp; no same-close execution claim.',
        'financial_sample':'Exactly matched fully observed names/dates within each cohort; no unknown values imputed0; release age AND fiscal-period age each bounded at180days.',
        'universe':list(prices.columns),'factor_symbols':['SPY','XLF'],
        'prices_path':str(prices_path),'prices_sha256':_hash(prices_path),'factors_path':str(factors_path),'factors_sha256':_hash(factors_path),
        'feature_audit_sha256':audit_hashes,'admission':admission,
        'frozen_before_model_selection_utc':datetime.now(timezone.utc).isoformat(),
        'scope':'Current-available cohort, not verified historical universe membership.',
    }
    _json(out/'protocol.json',frozen);protocol_hash=_hash(out/'protocol.json')
    scopes,coverage=_cohorts(_base_panel(prices,factors,protocol),prices.columns,sec_path,protocol,sec_core10_path if include_sec_core10 else None)
    coverage.to_csv(out/'cohort_coverage.csv',index=False)
    trace_parts=[]
    for cohort,scope in scopes.items():
        if scope['balance_features']:
            columns=['cohort','asset','origin','origin_at','horizon','split','available_at','matched_period_end',*scope['balance_features']]
            trace_parts.append(scope['panel'][columns].copy())
    financial_trace=pd.concat(trace_parts,ignore_index=True) if trace_parts else pd.DataFrame()
    maximum_release_age=None;maximum_period_age=None
    if not financial_trace.empty:
        origin_at=pd.to_datetime(financial_trace['origin_at'],utc=True)
        available_at=pd.to_datetime(financial_trace['available_at'],utc=True)
        release_age=(origin_at-available_at).dt.total_seconds()/86400
        period_age=(origin_at.dt.tz_localize(None)-pd.to_datetime(financial_trace['matched_period_end'])).dt.total_seconds()/86400
        assert release_age.ge(0).all() and release_age.le(180).all()
        assert period_age.ge(0).all() and period_age.le(180).all()
        maximum_release_age=float(release_age.max());maximum_period_age=float(period_age.max())
        financial_trace.to_csv(out/'financial_availability_trace.csv',index=False)
    models={};selection_rows=[];locked=[]
    for cohort,scope in scopes.items():
        for horizon in protocol.horizons:
            data=scope['panel'].loc[scope['panel']['horizon'].eq(horizon)]
            train=data.loc[data['split'].eq('train')];validation=data.loc[data['split'].eq('validation')]
            if train.empty or validation.empty:raise ValueError(f'Insufficient train/validation coverage for {cohort}.')
            assert train['target_end'].max()<=pd.Timestamp(protocol.train_end)
            assert validation['target_end'].max()<=pd.Timestamp(protocol.validation_end)
            for layer,features in scope['layers'].items():
                x_train=design_matrix(train,features,scope['assets']);x_validation=design_matrix(validation,features,scope['assets'])
                candidates=[]
                for alpha in RIDGE_ALPHAS:
                    fitted=fit_log_variance_ridge(x_train,train['realized_variance'].to_numpy()/horizon,alpha=alpha)
                    forecast=horizon*fitted.predict(x_validation)
                    score=float(add_losses(pd.DataFrame({'variance_forecast':forecast,'realized_variance':validation['realized_variance'].to_numpy()}))['qlike'].mean())
                    candidates.append((score,alpha,fitted))
                    selection_rows.append({'cohort':cohort,'horizon':horizon,'model':layer,'alpha':alpha,'validation_mean_qlike':score,'n_train_dates':train['origin'].nunique(),'n_validation_dates':validation['origin'].nunique(),'train_rows':len(train),'validation_rows':len(validation)})
                score,alpha,fitted=min(candidates,key=lambda x:(x[0],x[1]));models[cohort,horizon,layer]=fitted
                locked.append({
                    'cohort':cohort,'horizon':horizon,'model':layer,'alpha':alpha,'validation_mean_qlike':score,
                    'feature_names':list(fitted.feature_names),'means':fitted.means.tolist(),'scales':fitted.scales.tolist(),
                    'coefficients':fitted.coefficients.tolist(),'intercept':fitted.intercept,'smearing_factor':fitted.smear,
                    'log_prediction_guard_bounds':list(fitted.log_bounds),'train_rows':fitted.training_rows,
                    'training_latest_target':str(train['target_end'].max()),'validation_latest_target':str(validation['target_end'].max()),
                })
    pd.DataFrame(selection_rows).to_csv(out/'validation_selection.csv',index=False)
    _json(out/'selected_models.json',{'models':locked,'locked_before_test_predictions_utc':datetime.now(timezone.utc).isoformat(),'protocol_sha256':protocol_hash})
    lock_hash=_hash(out/'selected_models.json');predictions=[]
    columns=['cohort','origin','target_start','target_end','asset','horizon','split','realized_variance','feature_last_date','origin_at']
    for cohort,scope in scopes.items():
        for horizon in protocol.horizons:
            data=scope['panel'].loc[scope['panel']['horizon'].eq(horizon)]
            for model in ['rv_long','rv_recent','ewma']:
                part=data[columns].copy();part['model']=model;part['variance_forecast']=data[model].to_numpy();predictions.append(part)
            for layer,features in scope['layers'].items():
                part=data[columns].copy();part['model']=layer
                part['variance_forecast']=horizon*models[cohort,horizon,layer].predict(design_matrix(data,features,scope['assets']))
                predictions.append(part)
    losses=add_losses(pd.concat(predictions,ignore_index=True));assert _hash(out/'selected_models.json')==lock_hash
    losses.to_csv(out/'predictions.csv',index=False)
    by_asset=losses.groupby(['cohort','split','horizon','asset','model']).agg(n_dates=('origin','nunique'),mean_qlike=('qlike','mean'),mean_mse=('mse','mean')).reset_index()
    by_asset.to_csv(out/'scores_by_asset.csv',index=False)
    scores=losses.groupby(['cohort','split','horizon','model']).agg(n_dates=('origin','nunique'),n_asset_forecasts=('qlike','size'),mean_qlike=('qlike','mean'),mean_mse=('mse','mean')).reset_index()
    scores['mse_skill_vs_ewma']=np.nan;scores['qlike_difference_vs_ewma']=np.nan
    for (_,_,_),group in scores.groupby(['cohort','split','horizon']):
        reference=group.loc[group['model'].eq('ewma')].iloc[0]
        scores.loc[group.index,'mse_skill_vs_ewma']=1-group['mean_mse']/reference['mean_mse']
        scores.loc[group.index,'qlike_difference_vs_ewma']=group['mean_qlike']-reference['mean_qlike']
    scores.to_csv(out/'scores.csv',index=False)
    intervals=[]
    for (cohort,split,horizon),group in losses.loc[losses['split'].isin(['validation','test'])].groupby(['cohort','split','horizon']):
        pairs=[('ridge_price','ewma'),('ridge_market_sector','ridge_price'),('ridge_market_sector','ewma'),('ridge_market_sector','rv_recent')]
        if scopes[cohort]['balance_features']:
            pairs += [('ridge_balance_sheet','ridge_market_sector'),('ridge_interactions','ridge_balance_sheet'),('ridge_interactions','ewma')]
        for metric in ['qlike','mse']:
            wide=group.pivot(index=['origin','asset'],columns='model',values=metric)
            for left,right in pairs:
                differences=(wide[left]-wide[right]).groupby(level='origin').mean().sort_index()
                block_length=min(len(differences),max(2,math.ceil(63/horizon)))
                interval=moving_block_mean_interval(differences.to_numpy(),block_length=block_length,n_bootstrap=protocol.bootstrap_repetitions,seed=protocol.bootstrap_seed+int(horizon)+(0 if metric=='qlike' else 100))
                intervals.append({'cohort':cohort,'split':split,'horizon':int(horizon),'metric':metric,'left_model':left,'reference':right,**interval})
    intervals=pd.DataFrame(intervals);intervals.to_csv(out/'paired_loss_differences.csv',index=False)
    test=scores.loc[scores['split'].eq('test')]
    test_intervals=intervals.loc[intervals['split'].eq('test')&intervals['metric'].eq('qlike')]
    focused=test_intervals.loc[
        ((test_intervals['cohort']=='core_ten_market')&test_intervals['left_model'].isin(['ridge_price','ridge_market_sector'])&test_intervals['reference'].isin(['ewma','ridge_price']))
        |(test_intervals['left_model'].isin(['ridge_balance_sheet','ridge_interactions'])&test_intervals['reference'].isin(['ridge_market_sector','ridge_balance_sheet']))
    ]
    checks={
        'models_locked_before_test_predictions':True,'fit_scaler_training_only':True,
        'training_targets_purged_before_validation':True,'validation_targets_purged_before_test':True,
        'nonoverlap_targets_with_date_clustered_uncertainty':True,'test_hyperparameters_tuned':False,
        'total_underlying_variance_target':True,'official_SEC_balance_sheet_layer_tested':sec_path.is_file(),
        'original_vintage_publication_bound_used':sec_path.is_file(),'actual_acceptance_timestamps_claimed':False,
        'macro_layer_admitted':False,'full_stage5_macro_funding_gate_passed':False,'forecast_to_hedge_value_tested':False,
        'maximum_admitted_release_age_days':maximum_release_age,'maximum_admitted_fiscal_period_age_days':maximum_period_age,
    }
    _json(out/'checks.json',checks)
    os.environ.setdefault('MPLCONFIGDIR',tempfile.mkdtemp(prefix='feature-mpl-',dir='/tmp'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig,axes=plt.subplots(len(scopes),2,figsize=(14,4*len(scopes)),squeeze=False)
    for row,(cohort,scope) in enumerate(scopes.items()):
        for ax,horizon in zip(axes[row],protocol.horizons):
            group=test.loc[test['cohort'].eq(cohort)&test['horizon'].eq(horizon)]
            ax.bar(group['model'],group['mse_skill_vs_ewma'],color='tab:blue');ax.axhline(0,color='black',linewidth=.8)
            ax.tick_params(axis='x',labelrotation=30,labelsize=8)
            ax.set(title=f'{cohort}: {horizon} sessions',ylabel='MSE skill versus EWMA');ax.grid(axis='y',alpha=.2)
    fig.suptitle('Untouched test: incremental price, market and filing-vintage features')
    fig.tight_layout(rect=(0,0,1,.96));fig.savefig(out/'test_mse_skill.png',dpi=150);plt.close(fig)
    fig,ax=plt.subplots(figsize=(12,max(6,.45*len(focused))))
    for position,row in enumerate(focused.itertuples()):
        ax.plot([row.lower,row.upper],[position,position],color='tab:blue');ax.plot(row.estimate,position,'o',color='tab:blue')
    ax.set_yticks(range(len(focused)),[f'{r.cohort}, {r.horizon}: {r.left_model} vs {r.reference}' for r in focused.itertuples()])
    ax.axvline(0,color='black',linewidth=.8);ax.grid(axis='x',alpha=.2)
    ax.set(xlabel='Mean QLIKE(model) minus QLIKE(reference)',title='Pointwise 95% chronological block intervals; negative favors model')
    fig.tight_layout();fig.savefig(out/'test_qlike_intervals.png',dpi=150);plt.close(fig)
    report=[
        '# Release-aware incremental feature research',
        f"Actual core sample: {', '.join(prices.columns)}, observed SPY/XLF features and audited official SEC filing facts for JPM/PNC/GS. {len(prices):,} aligned stock sessions through {prices.index.max().date()}.",
        '## Frozen design and timing',
        'Training 2010–2017; validation 2018–2020; test 2021–2026-11-04. Targets are TOTAL underlying cumulative next-5/20-session squared log returns, not residual variance. Windows are disjoint within each split/horizon. Features use information through the origin close; forecasts are issued after close, so derivative execution cannot assume final-close features were known before a same-close fill.',
        'Direct benchmarks are rolling 20/252-session variance and EWMA(lambda 0.94). Ridge forecasts log daily variance; training-only residual smearing back-transforms to positive expected variance, multiplied by the horizon. All scalers, coefficients, smearing factors and numerical prediction bounds are fit on training rows only. A fixed alpha grid 0.1/1/10/100/1000 is selected on validation QLIKE. Selected models are persisted and hashed before test predictions; there is no train+validation refit or test-based model selection.',
        '## Matched cohorts and economic hypotheses',_table(coverage),
        'Core-ten tests own-price information against added observed SPY/XLF risk, return and past-only beta features. SEC-three compares this market baseline with generic published liabilities/assets, then its interaction with the five-session XLF return. Bank-two compares market information with deposits/liabilities and cash-due-from-banks/assets, then their XLF-return interactions. The optional separate core-ten generic and six-bank deposit extension retains the same splits/grid; it excludes missing/stale financial rows on a matched-sample basis. GS is excluded from the bank-deposit hypothesis. These are accounting exposure proxies, not regulatory capital, LCR or insured-deposit measures.',
        'Every comparison inside a cohort uses the same fully observed names/dates. Missing fundamentals are never zero-filled. PNC has no CashEq history, so the bank liquidity proxy consistently uses the distinct CashAndDueFromBanks concept for both banks; cash-equivalent fields are not silently substituted.',
        '## Release and vintage admission',
        f"Unverified FMP company-field snapshots observed: {admission.get('FMP_company_fields',{}).get('observed_rows',0)}; Treasury observations: {admission.get('FMP_treasury_samples',{}).get('observed_rows',0)}. Neither current-restated FMP values nor the limited date-only Treasury samples enters the model.",
        'Official SEC companyfacts bind instant USD facts to accession and filed date. Recent submission metadata independently crosschecks a subset; older facts retain native SEC binding rather than an independent archive download. Ratios require the same filing and fiscal period. Availability is a conservative next-XNYS-session-close bound after the actual filed DATE, not a measured acceptance timestamp. Releases accepted after the origin cutoff cannot enter that origin. As-of logic selects the newest available fiscal period and then its latest available revision; a later comparative/amendment of an older period cannot roll back a newer known quarter. Both release age and fiscal-period age are bounded at180calendar days. A recent comparative republication cannot refresh an old fiscal period; Citi2025Q4 and latermissingcoverage are explicitly excluded when stale rather than treated as current.',
        '## Validation-selected model settings',_table(pd.DataFrame(locked)[['cohort','horizon','model','alpha','validation_mean_qlike','train_rows','training_latest_target','validation_latest_target']]),
        '## Untouched test scores',_table(test),
        'QLIKE is log(forecast)+realized/forecast, omitting a target-only constant; lower is better. MSE skill above zero improves on EWMA. Physical variance forecasts are not automatically option-implied volatilities or Q prices.',
        '![Test MSE skill](test_mse_skill.png)',
        '## Incremental information and uncertainty',_table(focused[['cohort','horizon','left_model','reference','estimate','lower','upper','n_dates','block_length']]),
        'Loss differences average across names at each origin before circular moving-block resampling, keeping common market episodes together. Quarter-length chronological blocks address residual temporal dependence. These are pointwise 95% intervals, not simultaneous model dominance. Validation scores choose alpha; validation intervals are not final performance evidence. All other test comparisons and MSE intervals remain in paired_loss_differences.csv.',
        '![Test QLIKE intervals](test_qlike_intervals.png)',
        '## Gates and remaining limits',
        'This artifact tests price/market information and approved filing-vintage balance-sheet proxies/interactions on matched cohorts. Negative or inconclusive findings are retained. The full macro/company-funding research gate remains open: full vintage-aware macro history is unavailable, bank proxies do not establish all funding vulnerabilities, and forecast improvement has not yet been shown to improve a properly timed derivative overlay.',
        'The universe is conditioned on current/available names, not verified historical membership. Split-adjusted returns exclude dividend cash flows; latest price histories do not certify every historical revision. Accounting definitions can differ across issuers, and the bank-only experiment has only two issuers. These limitations prevent a full stage-7 or listed-option-profitability claim.',
        '## Provenance',
        'protocol.json freezes hypotheses, cohorts, source hashes, rejected/approved data and ridge grid. selected_models.json records training-only scaling/coefficients and validation selection before test predictions. CSVs contain all predictions, per-company scores, dated financial-availability traces and date-clustered comparisons. manifest.json hashes inputs/source/output artifacts. No credentials are read or recorded.',
    ]
    (out/'report.md').write_text('\n\n'.join(report)+'\n')
    assert _hash(out/'protocol.json')==protocol_hash and _hash(out/'selected_models.json')==lock_hash
    manifest={**frozen,'protocol_sha256':protocol_hash,'selected_models_sha256':lock_hash,'checks':checks,
        'source_sha256':{str(p.relative_to(ROOT)):_hash(p) for p in [ROOT/'hedging_harness/feature_models.py',ROOT/'hedging_harness/risk_models.py',Path(__file__).resolve()]},
        'artifacts_sha256':{p.name:_hash(p) for p in sorted(out.iterdir()) if p.is_file()},
    }
    _json(out/'manifest.json',manifest)
    print(json.dumps({'output_dir':str(out),'models':len(locked),'checks':checks},indent=2));return out


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prices',type=Path,default=ROOT/'data/market/prices_core_10.csv')
    parser.add_argument('--factors',type=Path,default=ROOT/'data/market/prices_benchmarks.csv')
    parser.add_argument('--output-dir',type=Path)
    parser.add_argument('--sec-core10',action='store_true',help='Run the separately predeclared matched core10/six-bank filing extension.')
    args=parser.parse_args();stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    run(args.prices,args.factors,args.output_dir or ROOT/'results'/f'feature-research-{stamp}',include_sec_core10=args.sec_core10)


if __name__=='__main__':main()

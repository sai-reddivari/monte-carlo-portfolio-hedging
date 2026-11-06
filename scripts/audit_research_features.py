"""Bounded capability audit: at most8 financial/filing and2 Treasury calls.

No period-end-only feature is released historically. Current statement values
with old accepted dates are never automatically labelled original PIT vintages.
"""
from datetime import datetime,timezone
from hashlib import sha256
import argparse
import json
from pathlib import Path
import sys

import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from market_data import FMPClient,FMPError,load_fmp_api_key
from market_data.features import BALANCE_ENDPOINTS,fetch_feature_endpoint,normalize_statement_records,normalize_treasury_records


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--financial-request-budget',type=int,default=8)
    parser.add_argument('--prior-financial-attempts',type=int,default=0)
    parser.add_argument('--refresh',action='store_true')
    args=parser.parse_args()
    if args.prior_financial_attempts<0 or args.prior_financial_attempts+args.financial_request_budget>8:
        parser.error('Initial financial audit may use at most8 requests including prior attempts')
    out=ROOT/'data/market/features';out.mkdir(parents=True,exist_ok=True)
    reports=ROOT/'results/feature-audit';reports.mkdir(parents=True,exist_ok=True)
    previous_report=json.loads((reports/'coverage.json').read_text()) if (reports/'coverage.json').is_file() else {}
    key=load_fmp_api_key(ROOT/'.env')
    financial=FMPClient(key,timeout=20,max_requests=args.financial_request_budget)
    treasury=FMPClient(key,timeout=20,max_requests=2)
    statement_rows=[];concept_rows=[];coverage=[]
    for symbol in ['JPM','PNC','GS']:
        for endpoint in BALANCE_ENDPOINTS:
            try:
                filename=f'{symbol}_{endpoint}.json'
                if (out/filename).is_file() and not args.refresh:
                    stored=json.loads((out/filename).read_text())
                    metadata=stored.pop('metadata');normalized=stored
                else:
                    payload=fetch_feature_endpoint(financial,endpoint,{'symbol':symbol,'period':'quarter','limit':3})
                    normalized=normalize_statement_records(payload,symbol,endpoint)
                    metadata={'provider':'FMP','endpoint':endpoint,'parameters':{'symbol':symbol,'period':'quarter','limit':3},'retrieved_utc':datetime.now(timezone.utc).isoformat()}
                    (out/filename).write_text(json.dumps({'metadata':metadata,**normalized},indent=2)+'\n')
                statement_rows.extend(normalized['long_fields']);concept_rows.extend(normalized['concept_coverage'])
                coverage.append({'symbol':symbol,'endpoint':endpoint,'status':'observed','records':len(normalized['records']),'publication_records':normalized['publication_records'],'timing_eligible_records':normalized['timing_eligible_records'],'strict_pit_usable_records':0,'path':str(out/filename)})
            except FMPError as error:
                coverage.append({'symbol':symbol,'endpoint':endpoint,'status':error.code,'http_status':error.http_status,'strict_pit_usable_records':0})
    try:
        if (out/'JPM_sec_filings_sample.json').is_file() and not args.refresh:
            rows=json.loads((out/'JPM_sec_filings_sample.json').read_text())['records']
        else:
            payload=fetch_feature_endpoint(financial,'sec-filings-search/symbol',{'symbol':'JPM','from':'2026-10-01','to':'2026-11-04','page':0,'limit':20})
            allowed={'symbol','cik','filingDate','acceptedDate','formType','link','finalLink'}
            rows=[{key:value for key,value in record.items() if key in allowed} for record in payload if isinstance(record,dict)]
            (out/'JPM_sec_filings_sample.json').write_text(json.dumps({'endpoint':'sec-filings-search/symbol','records':rows,'financial_values_joined_or_original_vintages_verified':False},indent=2)+'\n')
        coverage.append({'symbol':'JPM','endpoint':'sec-filings-search/symbol','status':'observed','records':len(rows),'strict_pit_usable_records':0})
    except FMPError as error:
        coverage.append({'symbol':'JPM','endpoint':'sec-filings-search/symbol','status':error.code,'http_status':error.http_status})
    if statement_rows:pd.DataFrame(statement_rows).to_csv(out/'company_feature_fields_long.csv',index=False)
    if concept_rows:pd.DataFrame(concept_rows).to_csv(out/'company_feature_concept_coverage.csv',index=False)
    treasury_rows=[];rate_coverage=[]
    for label,start,end in [('normal_2019','2019-01-02','2019-03-29'),('stress_2020','2020-02-03','2020-04-30')]:
        try:
            if (out/f'treasury_{label}.json').is_file() and not args.refresh:
                normalized=json.loads((out/f'treasury_{label}.json').read_text())
            else:
                payload=fetch_feature_endpoint(treasury,'treasury-rates',{'from':start,'to':end})
                normalized=normalize_treasury_records(payload,start=start,end=end)
                (out/f'treasury_{label}.json').write_text(json.dumps({'endpoint':'treasury-rates','requested_start':start,'requested_end':end,**normalized},indent=2)+'\n')
            treasury_rows.extend(normalized['records'])
            rate_coverage.append({'window':label,'status':'observed','observations':normalized['observations'],'actual_publication_timestamp_verified':False,'original_vintage_verified':False})
        except FMPError as error:
            rate_coverage.append({'window':label,'status':error.code,'http_status':error.http_status})
    if treasury_rows:pd.DataFrame(treasury_rows).to_csv(out/'treasury_rates_lagged_samples.csv',index=False)
    artifacts={path.name:{'path':str(path),'sha256':sha256(path.read_bytes()).hexdigest()} for path in out.glob('*') if path.is_file()}
    report={'audited_utc':datetime.now(timezone.utc).isoformat(),'financial_request_attempts':args.prior_financial_attempts+financial.request_count,'financial_request_attempts_this_run':financial.request_count,'prior_financial_attempts':args.prior_financial_attempts,'treasury_request_attempts':treasury.request_count,'statement_coverage':coverage,'treasury_coverage':rate_coverage,'artifacts':artifacts,'stage5_incremental_macro_funding_gate_passed':False,'original_statement_vintages_verified':False,'fiscal_period_end_used_as_publication_date':False,'fundamentals_usable_without_further_review':False,'treasury_usable_without_explicit_lag_and_snapshot_caveat':False,'limits':['As-reported values lacking filing/acceptance fields cannot be as-of joined using period-end.','Standardized current values with historical accepted dates are timing candidates only; original-vintage restatement risk remains unverified.','Two90-day Treasury samples do not provide a full historical forecast layer.','Access and timing metadata do not prove an incremental forecasting or hedging improvement.']}
    # Preserve audited initial-probe counts when regenerating from cache. The
    # current-run counts remain separate rather than pretending cached reads
    # were new HTTP attempts.
    for field in ['initial_live_financial_attempts_total','initial_live_treasury_attempts_total','initial_attempt_accounting_note']:
        if field in previous_report:report[field]=previous_report[field]
    (reports/'coverage.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({key:report[key] for key in ['financial_request_attempts','treasury_request_attempts','statement_coverage','treasury_coverage','stage5_incremental_macro_funding_gate_passed']},indent=2))


if __name__=='__main__':
    try:main()
    except Exception as error:
        print(json.dumps({'status':'feature_audit_failed','safe_code':getattr(error,'code',None),'error_type':type(error).__name__}))
        raise SystemExit(1) from None

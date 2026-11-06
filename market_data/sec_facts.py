"""Accession-bound SEC XBRL balance facts with conservative release availability.

Only entity-wide, noncustom US-GAAP instant USD facts from 10-K/10-Q filings and
amendments are used. Every distinct filing vintage is retained. A later filing's
comparative old period cannot replace a newer period in an as-of snapshot.
"""
from datetime import datetime,timezone
from hashlib import sha256
import json
from pathlib import Path
import re

import numpy as np
import pandas as pd

from .features import conservative_availability

FIELDS={
    'assets':'Assets',
    'liabilities':'Liabilities',
    'cash_and_cash_equivalents':'CashAndCashEquivalentsAtCarryingValue',
    'cash_and_due_from_banks':'CashAndDueFromBanks',
    'deposits':'Deposits',
    'stockholders_equity':'StockholdersEquity',
    'short_term_borrowings':'ShortTermBorrowings',
}
CORE10_BUSINESS_GROUPS={
    'JPM':'diversified_bank','PNC':'regional_bank','GS':'capital_markets',
    'BAC':'diversified_bank','WFC':'diversified_bank','C':'diversified_bank',
    'USB':'regional_bank','MS':'wealth_management_and_capital_markets',
    'SCHW':'brokerage_and_bank_group','BK':'custody_and_asset_servicing',
}
BANK_DEPOSIT_COMPARISON_GROUPS={'diversified_bank','regional_bank'}
FORMS={'10-K','10-Q','10-K/A','10-Q/A'}
_ACCESSION=re.compile(r'^\d{10}-\d{2}-\d{6}$')


def _iso_date(value):
    try:
        if not isinstance(value,str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}',value):return None
        return pd.Timestamp(value).strftime('%Y-%m-%d')
    except (ValueError,TypeError):return None


def submission_index(payload:dict, *, expected_cik:str) -> dict:
    if int(payload.get('cik',-1))!=int(expected_cik):
        raise ValueError('SEC submissions issuer does not match the FMP-derived CIK')
    recent=payload.get('filings',{}).get('recent',{})
    columns=['accessionNumber','filingDate','reportDate','form']
    if any(column not in recent for column in columns):
        raise ValueError('SEC submissions metadata columns missing')
    if len({len(recent[column]) for column in columns})!=1:
        raise ValueError('SEC submissions metadata is unaligned')
    result={}
    for i,accession in enumerate(recent['accessionNumber']):
        if not _ACCESSION.fullmatch(str(accession)):
            raise ValueError('SEC submissions accession is invalid')
        record={column:recent[column][i] for column in columns}
        if accession in result and result[accession]!=record:
            raise ValueError('Conflicting SEC submissions accession metadata')
        result[accession]=record
    return result


def normalize_sec_facts(facts:dict,submissions:dict, *, symbol:str,cik:str) -> tuple[pd.DataFrame,dict]:
    if int(facts.get('cik',-1))!=int(cik):
        raise ValueError('SEC companyfacts issuer does not match the FMP-derived CIK')
    independent=submission_index(submissions,expected_cik=cik)
    taxonomy=facts.get('facts',{}).get('us-gaap',{})
    rows=[];coverage=[];rejected=[];availability={}
    for field,tag in FIELDS.items():
        concept=taxonomy.get(tag,{})
        units=concept.get('units',{})
        candidates=units.get('USD',[])
        accepted_count=0
        for fact in candidates:
            if fact.get('form') not in FORMS:continue
            if 'start' in fact:
                rejected.append({'field':field,'reason':'duration_fact_not_instant'});continue
            end,filed=_iso_date(fact.get('end')),_iso_date(fact.get('filed'))
            accession=str(fact.get('accn',''))
            value=fact.get('val')
            if end is None or filed is None or filed<end or not _ACCESSION.fullmatch(accession):
                rejected.append({'field':field,'reason':'invalid_native_filing_binding'});continue
            if isinstance(value,bool) or not isinstance(value,(int,float)) or not np.isfinite(value):
                rejected.append({'field':field,'reason':'invalid_numeric_fact'});continue
            crosscheck=independent.get(accession)
            metadata_consistent=True
            if crosscheck is not None:
                metadata_consistent=(crosscheck['filingDate']==filed and crosscheck['form']==fact['form'])
                report_end=_iso_date(crosscheck.get('reportDate'))
                if report_end is not None and end>report_end:
                    metadata_consistent=False
            if filed not in availability:
                availability[filed]=conservative_availability(filed)
            row={
                'symbol':symbol,'cik':str(cik).zfill(10),'field':field,'taxonomy_tag':tag,'taxonomy':'us-gaap','unit':'USD',
                'period_end':end,'accn':accession,'filed':filed,'form':fact['form'],'value':float(value),
                **availability[filed],
                'actual_acceptance_timestamp_used':False,
                'source_binding':'official_SEC_companyfacts_accession_and_filed_date',
                'accession_crosscheck_status':'matched_SEC_submissions' if crosscheck is not None and metadata_consistent else 'SEC_submissions_mismatch' if crosscheck is not None else 'native_SEC_fact_binding_outside_recent_submissions_window',
                'independent_recent_accession_crosscheck':crosscheck is not None,
                'original_vintage_verified':metadata_consistent,
                'ambiguous_within_filing':False,
                'deposit_feature_approved_for_issuer':symbol in {'JPM','PNC'},
            }
            rows.append(row);accepted_count+=1
        coverage.append({'symbol':symbol,'field':field,'taxonomy_tag':tag,'USD_native_records':len(candidates),
                         'other_units':list(unit for unit in units if unit!='USD'),'normalized_records':accepted_count,
                         'status':'native_USD_filing_facts_observed' if accepted_count else 'unavailable_or_no_unambiguous_instant_USD_facts',
                         'deposit_feature_approved_for_issuer':symbol in {'JPM','PNC'} if field=='deposits' else None})
    if not rows:
        raise ValueError('No accession-bound instant USD facts available')
    frame=pd.DataFrame(rows)
    keys=['symbol','field','unit','period_end','accn','filed']
    frame=frame.drop_duplicates(subset=keys+['value']).copy()
    conflicts=frame.groupby(['symbol','field','unit','period_end','accn'])['value'].transform('nunique').gt(1)
    frame.loc[conflicts,'ambiguous_within_filing']=True
    frame.loc[conflicts,'original_vintage_verified']=False
    frame=frame.sort_values(['symbol','filed','accn','period_end','field']).reset_index(drop=True)
    report={
        'symbol':symbol,'cik':str(cik).zfill(10),'SEC_entity_name':facts.get('entityName'),
        'facts':len(frame),'verified_native_filing_facts':int(frame['original_vintage_verified'].sum()),
        'independent_recent_crosschecks':int(frame['independent_recent_accession_crosscheck'].sum()),
        'recent_crosscheck_mismatches':int(frame['accession_crosscheck_status'].eq('SEC_submissions_mismatch').sum()),
        'within_filing_ambiguous_facts':int(frame['ambiguous_within_filing'].sum()),
        'coverage':coverage,'rejected_counts':pd.DataFrame(rejected).value_counts().reset_index(name='count').to_dict(orient='records') if rejected else [],
        'historical_recent_metadata_limit':'Older native facts remain accession/filed-bound official SEC records; they are explicitly distinguished from independently crosschecked recent submissions.',
        'custom_taxonomy_or_dimensional_funding_features_supported':False,
    }
    return frame,report


def build_filing_snapshots(facts:pd.DataFrame) -> pd.DataFrame:
    required={'symbol','cik','field','unit','period_end','accn','filed','value','available_at','original_vintage_verified'}
    if not required.issubset(facts):raise ValueError('Missing normalized SEC fact columns')
    verified=facts.loc[facts['original_vintage_verified'].eq(True)&facts['unit'].eq('USD')].copy()
    rows=[]
    for (symbol,cik,accn,filed),group in verified.groupby(['symbol','cik','accn','filed']):
        anchors=group.loc[group['field'].eq('assets')]
        if anchors.empty:continue
        newest_period=anchors['period_end'].max()
        current=group.loc[group['period_end'].eq(newest_period)]
        row={'symbol':symbol,'cik':str(cik).zfill(10),'period_end':newest_period,'accn':accn,'filed':filed,
             'available_at':current['available_at'].iloc[0],'available_from_session':current['available_from_session'].iloc[0],
             'unit':'USD','same_filing_and_period':True,'original_vintage_verified':True,
             'actual_acceptance_timestamp_used':False,'availability_type':'derived_conservative_next_session_close',
             'deposit_feature_approved_for_issuer':symbol in {'JPM','PNC'}}
        for field in FIELDS:
            values=current.loc[current['field'].eq(field),'value']
            if values.nunique()>1:raise ValueError('Conflicting facts reached snapshot construction')
            row[field]=float(values.iloc[0]) if len(values) else np.nan
        row['independent_recent_crosscheck']=bool(current['independent_recent_accession_crosscheck'].all())
        row['source_binding']='official_SEC_companyfacts_accession_and_filed_date'
        rows.append(row)
    if not rows:raise ValueError('No coherent same-filing assets snapshots')
    return pd.DataFrame(rows).sort_values(['symbol','period_end','filed','accn']).reset_index(drop=True)


def select_snapshot_asof(snapshots:pd.DataFrame,symbol:str,decision_timestamp) -> pd.Series | None:
    decision=pd.Timestamp(decision_timestamp)
    if decision.tzinfo is None:raise ValueError('Decision timestamp must be timezone-aware')
    candidates=snapshots.loc[snapshots['symbol'].eq(symbol)&snapshots['original_vintage_verified'].eq(True)].copy()
    if candidates.empty:return None
    candidates['_available']=pd.to_datetime(candidates['available_at'],utc=True)
    candidates=candidates.loc[candidates['_available']<=decision.tz_convert('UTC')]
    candidates=candidates.loc[pd.to_datetime(candidates['period_end']).dt.date<=decision.date()]
    if candidates.empty:return None
    # Newest economic period first; only then allow a later, already-available
    # amendment of that period. A late comparative does not roll the book back.
    newest=candidates['period_end'].max()
    chosen=candidates.loc[candidates['period_end'].eq(newest)].sort_values(['_available','filed','accn']).iloc[-1]
    return chosen.drop(labels=['_available'])


def export_cached_sec_facts(root:str|Path) -> dict:
    root=Path(root);cache=root/'data/cache/sec';out=root/'data/market/features/sec_facts';out.mkdir(parents=True,exist_ok=True)
    manifest=json.loads((root/'data/market/features/sec_probe_manifest.json').read_text())
    frames=[];reports=[];source_files={}
    for symbol,identity in manifest['identifiers'].items():
        fact_path=cache/f'{symbol}_companyfacts.json';sub_path=cache/f'{symbol}_submissions.json'
        facts=json.loads(fact_path.read_text());submissions=json.loads(sub_path.read_text())
        frame,report=normalize_sec_facts(facts,submissions,symbol=symbol,cik=identity['cik'])
        frames.append(frame);reports.append(report)
        for path in [fact_path,sub_path,Path(identity['source_metadata_path'])]:
            source_files[str(path.relative_to(root))]=sha256(path.read_bytes()).hexdigest()
    all_facts=pd.concat(frames,ignore_index=True)
    snapshots=build_filing_snapshots(all_facts)
    year_coverage=[]
    for (symbol,year),group in snapshots.assign(year=snapshots['period_end'].str[:4]).groupby(['symbol','year']):
        for field in FIELDS:
            year_coverage.append({'symbol':symbol,'period_year':int(year),'field':field,
                'same_filing_snapshots':len(group),'nonmissing_snapshots':int(group[field].notna().sum()),
                'distinct_periods':int(group['period_end'].nunique()),
                'distinct_periods_with_value':int(group.loc[group[field].notna(),'period_end'].nunique()),
                'bank_deposit_comparison_approved':symbol in {'JPM','PNC'} if field=='deposits' else None})
    fact_path=out/'sec_filing_facts_long.csv';snapshot_path=out/'sec_filing_snapshots.csv'
    all_facts.to_csv(fact_path,index=False);snapshots.to_csv(snapshot_path,index=False)
    year_path=out/'sec_field_year_coverage.csv'
    pd.DataFrame(year_coverage).to_csv(year_path,index=False)
    result={
        'prepared_utc':datetime.now(timezone.utc).isoformat(),'source':'US_SEC_official_companyfacts_and_submissions',
        'source_documentation':'https://www.sec.gov/search-filings/edgar-application-programming-interfaces',
        'CIK_source':'Actual FMP SEC-filing metadata, retained and hashed; not guessed identifiers.',
        'sec_requests_in_initial_probe':manifest['sec_requests_including_initial_JPM_probe'],
        'fmp_identifier_requests':manifest['fmp_identifier_requests'],
        'user_agent':manifest['user_agent'],'automated_native_vintage_binding_checks_passed':all(report['recent_crosscheck_mismatches']==0 for report in reports),
        'company_reports':reports,'source_file_sha256':source_files,
        'files':{str(path.name):{'path':str(path),'sha256':sha256(path.read_bytes()).hexdigest()} for path in [fact_path,snapshot_path,year_path]},
        'snapshot_rows':len(snapshots),'retained_filing_fact_rows':len(all_facts),
        'availability':'Verified SEC filed DATE plus the close of the next XNYS session; actual intraday acceptance time not asserted.',
        'asof_rule':'Only available_at<=decision; maximize period_end first, then latest available filed/accession within that period.',
        'missing_facts_filled_with_zero':False,'all_returned_selected_filing_vintages_retained':True,
        'human_review_status':'pending_definition_and_representative_filing_review',
        'incremental_forecasting_improvement_established':False,
        'limitations':['SEC companyfacts covers noncustom, entity-wide facts; missing custom funding tags are not synthesized.','Independent submissions crosschecks cover recent metadata; older facts are explicitly native SEC accession/filed bindings, not independently downloaded archived filings.','CashAndDueFromBanks is a separate bank liquidity concept from CashAndCashEquivalents, not a silent alias.','Deposit funding is approved for JPM/PNC bank comparison; GS brokerage funding requires separate economic interpretation.','The existence of auditable data does not establish forecast or hedge improvement.'],
    }
    (out/'sec_fact_coverage.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


def export_cached_sec_core10(root:str|Path) -> dict:
    """Separate predeclared extension; never rewrite the frozen three-name set."""
    root=Path(root);out=root/'data/market/features/sec_facts_core10'
    manifest=json.loads((out/'sec_core10_probe_manifest.json').read_text())
    frames=[];reports=[];hashes={}
    for symbol,group in CORE10_BUSINESS_GROUPS.items():
        identity=manifest['identifiers'][symbol]
        paths=[root/'data/cache/sec'/f'{symbol}_{kind}.json' for kind in ['companyfacts','submissions']]
        fact_payload,submissions=(json.loads(path.read_text()) for path in paths)
        frame,report=normalize_sec_facts(fact_payload,submissions,symbol=symbol,cik=identity['cik'])
        approved=group in BANK_DEPOSIT_COMPARISON_GROUPS
        frame['business_group']=group;frame['deposit_feature_approved_for_issuer']=approved
        report['business_group']=group;report['deposit_feature_approved_for_issuer']=approved
        for coverage in report['coverage']:
            if coverage['field']=='deposits':coverage['deposit_feature_approved_for_issuer']=approved
        frames.append(frame);reports.append(report)
        for path in paths+[Path(identity['source_metadata_path'])]:
            hashes[str(path.relative_to(root))]=sha256(path.read_bytes()).hexdigest()
    facts=pd.concat(frames,ignore_index=True)
    snapshots=build_filing_snapshots(facts)
    snapshots['business_group']=snapshots['symbol'].map(CORE10_BUSINESS_GROUPS)
    snapshots['deposit_feature_approved_for_issuer']=snapshots['business_group'].isin(BANK_DEPOSIT_COMPARISON_GROUPS)
    coverage=[]
    for (symbol,year),frame in snapshots.assign(period_year=snapshots['period_end'].str[:4]).groupby(['symbol','period_year']):
        for field in FIELDS:
            coverage.append({'symbol':symbol,'period_year':int(year),'field':field,
                'same_filing_snapshots':len(frame),'nonmissing_snapshots':int(frame[field].notna().sum()),
                'distinct_periods':frame['period_end'].nunique(),
                'distinct_periods_with_value':frame.loc[frame[field].notna(),'period_end'].nunique()})
    paths=[out/'sec_filing_facts_long.csv',out/'sec_filing_snapshots.csv',out/'sec_field_year_coverage.csv']
    for frame,path in zip([facts,snapshots,pd.DataFrame(coverage)],paths):frame.to_csv(path,index=False)
    result={
        'prepared_utc':datetime.now(timezone.utc).isoformat(),
        'cohort':list(CORE10_BUSINESS_GROUPS),'predeclared_extension':True,
        'frozen_three_name_artifacts_rewritten':False,
        'source':'official_SEC_accession_bound_instant_USD_companyfacts',
        'fmp_identifier_requests':manifest['fmp_identifier_requests'],
        'new_official_SEC_requests':manifest['sec_requests'],
        'base_three_companyfacts_and_submissions_reused_from_cache':True,
        'company_reports':reports,'snapshot_rows':len(snapshots),'retained_filing_fact_rows':len(facts),
        'source_file_sha256':hashes,
        'files':{path.name:{'path':str(path),'sha256':sha256(path.read_bytes()).hexdigest()} for path in paths},
        'business_groups':CORE10_BUSINESS_GROUPS,
        'bank_deposit_comparison_eligible':sorted(symbol for symbol,group in CORE10_BUSINESS_GROUPS.items() if group in BANK_DEPOSIT_COMPARISON_GROUPS),
        'BK_identifier_note':'Stable study identifier BK uses actual FMP filing symbol BNY following the documented ticker change; SEC CIK verified from those filing records.',
        'availability':'Verified SEC filed DATE plus next XNYS session close, derived conservative availability rather than actual acceptance timestamp.',
        'asof_rule':'Filter available_at<=decision; newest economic period first; latest available filing only within that period.',
        'cash_equivalents_imputed':False,'missing_values_filled_with_zero':False,
        'automated_native_vintage_binding_checks_passed':all(r['recent_crosscheck_mismatches']==0 for r in reports),
        'human_review_status':'pending_economic_definition_and_representative_filing_review',
        'forecast_model_splits_or_hyperparameters_changed':False,
        'incremental_forecasting_improvement_established':False,
        'limitations':['Current core10 cohort is not a historical point-in-time membership universe.',
            'Older native filing facts are accession-bound but not independently checked against downloaded archival documents.',
            'Cash equivalents and cash due from banks remain separate concepts.',
            'GS/MS/SCHW/BK deposits are retained but not approved as comparable bank deposit-funding features.',
            'Access and coverage are not an incremental forecast-benefit result.'],
    }
    (out/'sec_fact_coverage.json').write_text(json.dumps(result,indent=2)+'\n')
    return result

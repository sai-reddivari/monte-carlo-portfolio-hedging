"""Publication-aware feature capability audit; access is not PIT validation.

This module never uses a fiscal period-end as a release date and never labels a
current vendor snapshot as an original historical filing vintage merely because
it contains an old filing/acceptance timestamp.
"""
from datetime import date,datetime,timedelta,timezone
from functools import lru_cache
import math
from pathlib import Path
import re
from urllib.parse import urlparse

import exchange_calendars as xcals
import pandas as pd

from .fmp import FMPClient,FMPError

BALANCE_ENDPOINTS=('balance-sheet-statement-as-reported','balance-sheet-statement')
RATE_FIELDS=('month1','month2','month3','month6','year1','year2','year3','year5','year7','year10','year20','year30')
CONCEPT_ALIASES={
    'total_assets':{'assets','totalassets'},
    'cash_liquidity':{'cashandcashequivalents','cashandcashequivalentsatcarryingvalue'},
    'total_deposits':{'deposits','depositliabilities'},
    'uninsured_deposits':{'depositsuninsured','uninsureddeposits'},
    'short_term_debt_or_borrowings':{'shorttermdebt','shorttermborrowings'},
    'long_term_debt':{'longtermdebt','longtermdebtnoncurrent'},
    'total_equity':{'stockholdersequity','totalstockholdersequity','totalequity'},
}


@lru_cache(maxsize=64)
def _availability_calendar(start_year:int,end_year:int):
    return xcals.get_calendar('XNYS',start=f'{start_year}-01-01',end=f'{end_year}-12-31')


def finite_number(value):
    """Keep a genuinely reported zero; unknown/non-numeric stays None."""
    if value is None or isinstance(value,bool):return None
    try:number=float(value)
    except (TypeError,ValueError):return None
    return number if math.isfinite(number) else None


def _date_only(value):
    if not isinstance(value,str) or not re.match(r'^\d{4}-\d{2}-\d{2}',value):return None
    try:return date.fromisoformat(value[:10])
    except ValueError:return None


def conservative_availability(publication_date: str, *, lag_sessions:int=1) -> dict:
    """Use the close of the Nth NYSE session strictly after publication date.

    This conservative convention avoids guessing a missing intraday/time-zone
    publication field. It does not establish the vendor value's original vintage.
    """
    if not isinstance(lag_sessions,int) or isinstance(lag_sessions,bool) or lag_sessions<1:
        raise ValueError('lag_sessions must be a positive integer')
    observed=_date_only(publication_date)
    if observed is None:raise ValueError('An explicit valid publication date is required')
    start=observed+timedelta(days=1)
    end=start+timedelta(days=max(30,lag_sessions*4))
    calendar=_availability_calendar(observed.year-1,end.year+1)
    sessions=calendar.sessions_in_range(start.isoformat(),end.isoformat())
    session=sessions[lag_sessions-1]
    close=calendar.session_close(session)
    return {'available_from_session':session.strftime('%Y-%m-%d'),'available_at':close.isoformat(),
            'availability_policy':f'close_of_{lag_sessions}_NYSE_session_after_publication_calendar_date',
            'calendar':'XNYS','calendar_package_version':xcals.__version__}


def publication_status(row:dict, *, as_of:str='2026-11-04') -> dict:
    period_end=_date_only(row.get('date'))
    filing=_date_only(row.get('filingDate') or row.get('fillingDate'))
    accepted=_date_only(row.get('acceptedDate'))
    result={'period_end':period_end.isoformat() if period_end else None,
            'filing_date':filing.isoformat() if filing else None,
            'accepted_at_source':row.get('acceptedDate') if accepted else None,
            'publication_date':None,'available_from_session':None,'available_at':None,
            'period_end_used_as_publication_date':False,'original_filing_value_vintage_verified':False,
            'strict_historical_feature_usable':False,'timing_usable_with_conservative_lag':False}
    if not period_end:
        result['publication_status']='blocked_invalid_period_end';return result
    actual=[item for item in (filing,accepted) if item]
    if not actual:
        result['publication_status']='blocked_no_filing_or_accepted_date';return result
    publication=max(actual)
    if publication<=period_end:
        result['publication_status']='blocked_publication_not_after_period_end';return result
    result['publication_date']=publication.isoformat()
    result.update(conservative_availability(publication.isoformat()))
    result['timing_usable_with_conservative_lag']=result['available_from_session']<=as_of
    result['publication_status']='publication_fields_present_original_vintage_unverified'
    result['accepted_timestamp_timezone_verified']=False
    result['filing_link_present']=any(isinstance(row.get(key),str) and urlparse(row[key]).hostname in {'www.sec.gov','sec.gov'} for key in ('link','finalLink'))
    return result


def _tag_name(tag):
    return re.sub('[^a-z]','',str(tag).lower().replace('us-gaap:',''))


def funding_category(tag):
    name=_tag_name(tag)
    if 'deposit' in name:return 'deposit_funding'
    if 'cash' in name or 'liquid' in name:return 'cash_liquidity'
    if any(word in name for word in ['debt','borrow','repurchase','commercialpaper']):return 'debt_wholesale_funding'
    if 'securit' in name:return 'securities_and_financing_assets'
    if 'asset' in name:return 'assets'
    if 'equity' in name or 'stockholder' in name:return 'equity'
    return 'other'


def normalize_statement_records(payload:list, symbol:str, endpoint:str, *, as_of:str='2026-11-04') -> dict:
    if endpoint not in BALANCE_ENDPOINTS or not isinstance(payload,list):
        raise ValueError('Unsupported statement endpoint/schema')
    records=[];fields=[]
    for row in payload:
        if not isinstance(row,dict) or row.get('symbol',symbol)!=symbol:
            raise FMPError('unexpected_statement_schema')
        values=row.get('data',{}) if endpoint.endswith('as-reported') else {key:value for key,value in row.items() if key not in {'symbol','date','reportedCurrency','cik','fiscalYear','period','filingDate','fillingDate','acceptedDate','link','finalLink'}}
        if not isinstance(values,dict):raise FMPError('unexpected_statement_schema')
        publication=publication_status(row,as_of=as_of)
        currency=row.get('reportedCurrency')
        currency=currency if isinstance(currency,str) and re.fullmatch('[A-Z]{3}',currency) else None
        normalized={
            'symbol':symbol,'endpoint':endpoint,'reported_currency':currency,
            'fiscal_year':str(row.get('fiscalYear')) if str(row.get('fiscalYear','')).isdigit() else None,
            'period':row.get('period') if row.get('period') in {'Q1','Q2','Q3','Q4','FY'} else None,
            **publication,'numeric_fields':{},
        }
        for tag,value in values.items():
            # Never copy unknown string metadata or credentials into artifacts.
            if any(word in str(tag).lower() for word in ['apikey','api_key','token','password']):continue
            number=finite_number(value)
            if number is not None or value is None:
                normalized['numeric_fields'][str(tag)]=number
                fields.append({
                    'symbol':symbol,'endpoint':endpoint,'period_end':publication['period_end'],
                    'available_at':publication['available_at'],'available_from_session':publication['available_from_session'],
                    'field':str(tag),'value':number,'reported_currency':currency,
                    'field_status':'missing' if number is None else 'reported_zero' if number==0 else 'reported_numeric',
                    'funding_category':funding_category(tag),
                    'timing_usable_with_conservative_lag':publication['timing_usable_with_conservative_lag'],
                    'original_filing_value_vintage_verified':False,'strict_historical_feature_usable':False,
                })
        records.append(normalized)
    conceptual=[]
    for concept,aliases in CONCEPT_ALIASES.items():
        matching=[field for field in fields if _tag_name(field['field']) in aliases]
        nonmissing=[field for field in matching if field['value'] is not None]
        conceptual.append({'symbol':symbol,'endpoint':endpoint,'concept':concept,
            'candidate_source_fields':sorted({field['field'] for field in matching}),
            'numeric_observations':len(nonmissing),'status':'candidate_present_requires_definition_units_vintage_review' if nonmissing else 'unavailable_or_missing',
            'strict_historical_feature_usable':False})
    return {'records':records,'long_fields':fields,'concept_coverage':conceptual,
            'publication_records':sum(record['publication_date'] is not None for record in records),
            'timing_eligible_records':sum(record['timing_usable_with_conservative_lag'] for record in records),
            'strict_pit_usable_records':0,
            'issuer_group':'capital_markets_comparison' if symbol=='GS' else 'bank_comparison' if symbol in {'JPM','PNC'} else 'classification_review_required'}


def normalize_treasury_records(payload:list, *, start:str,end:str) -> dict:
    if not isinstance(payload,list):raise FMPError('unexpected_treasury_schema')
    if (date.fromisoformat(end)-date.fromisoformat(start)).days>90:
        raise ValueError('FMP documents at most90days per Treasury request')
    rows=[];seen=set()
    for row in payload:
        observed=_date_only(row.get('date')) if isinstance(row,dict) else None
        if observed is None or not start<=observed.isoformat()<=end:
            raise FMPError('invalid_treasury_observation_date')
        if observed in seen:raise FMPError('duplicate_treasury_date')
        seen.add(observed)
        normalized={'observation_date':observed.isoformat(),**conservative_availability(observed.isoformat()),
            'publication_timestamp_supplied':False,'provider_ingestion_timestamp_verified':False,
            'original_vintage_verified':False,'strict_historical_feature_usable':False,
            'usable_only_under_explicit_lagged_current_snapshot_assumption':True}
        for maturity in RATE_FIELDS:
            rate=finite_number(row.get(maturity))
            normalized[maturity+'_pct']=rate
            normalized[maturity+'_decimal']=rate/100 if rate is not None else None
        if normalized['year10_decimal'] is not None and normalized['month3_decimal'] is not None:
            normalized['slope_10y_3m_decimal']=normalized['year10_decimal']-normalized['month3_decimal']
        else:normalized['slope_10y_3m_decimal']=None
        rows.append(normalized)
    rows.sort(key=lambda row:row['observation_date'])
    return {'records':rows,'observations':len(rows),'units':'vendor yields in percentage points; explicit decimal conversion divides by100',
        'actual_publication_timestamp_verified':False,'original_vintage_verified':False,
        'availability_convention':'one complete XNYS session after observation calendar date, at that session close; conservative assumption, not a measured vendor publication timestamp',
        'full_historical_forecast_layer_supported_by_these_samples':False}


def fetch_feature_endpoint(client:FMPClient,endpoint:str,parameters:dict) -> list:
    if endpoint not in {*BALANCE_ENDPOINTS,'sec-filings-search/symbol','treasury-rates'}:
        raise ValueError('Feature audit endpoint not allowlisted')
    if any(key.lower() in {'apikey','api_key','token','key'} for key in parameters):
        raise ValueError('Credentials cannot be metadata parameters')
    payload=client._request_json(endpoint,dict(parameters))
    if not isinstance(payload,list):raise FMPError('unexpected_feature_schema')
    return payload

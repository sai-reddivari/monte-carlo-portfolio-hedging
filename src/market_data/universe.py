"""Conditional current-universe breadth data; never labelled PIT membership."""
from __future__ import annotations
from datetime import datetime, timezone
from hashlib import sha256
import json
import re
from pathlib import Path
import time

import numpy as np
import pandas as pd

from .fmp import FMPClient, FMPError
from .coverage import _exchange_sessions

CORE_IDS = ('JPM','PNC','GS','BAC','WFC','C','USB','MS','SCHW','BK')
CURRENT_SYMBOL_BY_ID = {'BK':'BNY'}


def select_current_universe(snapshot: pd.DataFrame, *, size: int = 50, min_market_cap: float = 2e9,
                            min_volume: float = 250000) -> tuple[pd.DataFrame,pd.DataFrame]:
    """Freeze eligibility using a dated current snapshot, not historical results.

    Required core issuer IDs appear first; remaining eligible names are ordered
    by current market cap (descending), then volume and symbol. Names are not
    removed because their historical price data are absent or short.
    """
    if not 10 <= size <= 50:
        raise ValueError('size must be between10 and50')
    required={'symbol','companyName','marketCap','sector','industry','country','volume','isEtf','isFund','isActivelyTrading'}
    if not required.issubset(snapshot):
        raise ValueError('Missing current-universe fields')
    audit=snapshot.copy()
    audit['stable_id']=audit['symbol'].replace({'BNY':'BK'})
    audit['eligible_sector']=audit['sector'].eq('Financial Services')
    audit['eligible_country']=audit['country'].eq('US')
    audit['eligible_instrument']=~audit['isEtf'].eq(True)&~audit['isFund'].eq(True)&audit['isActivelyTrading'].eq(True)
    audit['eligible_common_symbol']=audit['symbol'].map(lambda s:bool(re.fullmatch(r'[A-Z]{1,5}(?:-[AB])?',str(s))))
    audit['eligible_size_liquidity']=(audit['marketCap']>=min_market_cap)&(audit['volume']>=min_volume)
    flags=['eligible_sector','eligible_country','eligible_instrument','eligible_common_symbol','eligible_size_liquidity']
    audit['eligible_before_issuer_deduplication']=audit[flags].all(axis=1)
    eligible=audit.loc[audit['eligible_before_issuer_deduplication']].copy()
    eligible['issuer_dedup_key']=eligible['companyName'].str.lower().str.replace(r'[^a-z0-9]','',regex=True)
    eligible=eligible.sort_values(['marketCap','volume','symbol'],ascending=[False,False,True])
    eligible=eligible.loc[~eligible['issuer_dedup_key'].duplicated()].copy()
    eligible=eligible.loc[~eligible['stable_id'].duplicated()].copy()
    missing=[name for name in CORE_IDS if name not in set(eligible['stable_id'])]
    if missing:
        raise ValueError('Required core issuer is absent from the eligible snapshot')
    priority={name:i for i,name in enumerate(CORE_IDS)}
    eligible['core_priority']=eligible['stable_id'].map(priority).fillna(len(CORE_IDS))
    eligible=eligible.sort_values(['core_priority','marketCap','volume','symbol'],ascending=[True,False,False,True])
    selected=eligible.head(size).copy()
    selected['universe_order']=np.arange(len(selected))
    audit['selected']=audit.index.isin(selected.index)
    audit['eligibility_reason']=np.where(audit['selected'],'selected_current_snapshot',np.where(audit['eligible_before_issuer_deduplication'],'eligible_but_not_selected_or_duplicate_issuer','failed_explicit_current_screen'))
    return selected.drop(columns=['issuer_dedup_key','core_priority']),audit


def fetch_unbalanced_panel(client: FMPClient, universe: pd.DataFrame, *, output_dir: str|Path='data/market',
                           start: str='2010-01-04', end: str='2026-11-04', pause_seconds: float=.3,
                           max_retries: int=1, snapshot_metadata: dict|None=None) -> dict:
    """Fetch/cache bounded histories and retain all selected columns and NaNs."""
    if len(universe)>50 or pause_seconds<0 or max_retries not in (0,1):
        raise ValueError('At most50 names and one bounded retry are supported')
    expected_dates,calendar_version=_exchange_sessions(start,end)
    expected=pd.DatetimeIndex(pd.to_datetime(expected_dates),name='date')
    columns={}
    coverage=[]
    sources={}
    for _,security in universe.sort_values('universe_order').iterrows():
        stable_id,symbol=str(security['stable_id']),str(security['symbol'])
        dataset=None
        error_code=None
        attempts=0
        for attempt in range(max_retries+1):
            before=client.request_count
            try:
                dataset=client.get_prices(symbol,start,end,adjustment='split_adjusted')
                attempts+=client.request_count-before
                if client.request_count>before:
                    time.sleep(pause_seconds)
                break
            except FMPError as error:
                attempts+=client.request_count-before
                error_code=error.code
                if client.request_count>before:
                    time.sleep(pause_seconds)
                if attempt>=max_retries or error.code not in {'rate_limited','transport_error','http_error'}:
                    break
                time.sleep(min(2.0,1.0+attempt))
        row={'stable_id':stable_id,'source_symbol':symbol,'request_attempts':attempts,'historical_membership_verified':False}
        if dataset is None or not dataset['records']:
            columns[stable_id]=pd.Series(index=expected,dtype=float,name=stable_id)
            row.update(status=error_code or 'empty',observations=0,first_observed_date=None,last_observed_date=None,missing_expected_sessions=len(expected),leading_missing_sessions=len(expected),internal_missing_sessions=None,trailing_missing_sessions=None)
        else:
            frame=pd.DataFrame(dataset['records'])
            column=frame.set_index(pd.to_datetime(frame['date']))['close'].rename(stable_id)
            column.index.name='date'
            if column.index.has_duplicates or not column.index.is_monotonic_increasing or not np.isfinite(column).all() or (column<=0).any():
                raise ValueError('Adapter returned invalid historical observations')
            columns[stable_id]=column
            sources[stable_id]=dataset['metadata']
            first,last=column.index.min(),column.index.max()
            inside=expected[(expected>=first)&(expected<=last)]
            missing=expected.difference(column.index)
            unexpected=column.index.difference(expected)
            row.update(status='observed_full' if len(missing)==0 and len(unexpected)==0 else 'observed_partial',observations=len(column),first_observed_date=first.strftime('%Y-%m-%d'),last_observed_date=last.strftime('%Y-%m-%d'),missing_expected_sessions=len(missing),leading_missing_sessions=int((expected<first).sum()),internal_missing_sessions=len(inside.difference(column.index)),trailing_missing_sessions=int((expected>last).sum()),unexpected_dates=len(unexpected))
        coverage.append(row)
    panel=pd.concat(columns.values(),axis=1).sort_index()
    panel=panel.reindex(index=expected.union(panel.index),columns=universe.sort_values('universe_order')['stable_id'].tolist())
    panel.index.name='date'
    availability=panel.notna()
    output_dir=Path(output_dir);output_dir.mkdir(parents=True,exist_ok=True)
    paths={'prices':output_dir/'prices_financial_50_unbalanced.csv','availability':output_dir/'prices_financial_50_availability.csv','coverage':output_dir/'financial_50_coverage.csv','universe':output_dir/'financial_50_universe.csv'}
    panel.to_csv(paths['prices'],date_format='%Y-%m-%d')
    availability.to_csv(paths['availability'],date_format='%Y-%m-%d')
    pd.DataFrame(coverage).to_csv(paths['coverage'],index=False)
    universe.to_csv(paths['universe'],index=False)
    metadata={
        'created_utc':datetime.now(timezone.utc).isoformat(),'source':'FMP','adjustment':'split_adjusted','source_price_field':'close','requested_start':start,'requested_end':end,
        'calendar':'XNYS','calendar_package':'exchange_calendars','calendar_version':calendar_version,'expected_sessions':len(expected),'selected_names':len(universe),
        'universe_asof_snapshot':snapshot_metadata or {},'universe_type':'fixed CURRENT survivor snapshot; NOT historical point-in-time membership',
        'selection_rule':'Preserve required core10 issuer IDs, then descending current marketCap, volume and symbol; US active Financial Services, nonETF/nonfund common-symbol pattern, marketCap>=2bn, current daily volume>=250000; deduplicate current issuer names.',
        'data_availability_does_not_define_historical_membership':True,'missing_values_filled':False,'failed_symbols_dropped':False,'incomplete_names_dropped':False,
        'historical_membership_status':'FMP historical-sp500-constituent HTTP402 entitlement_denied','survivorship_safe_generalization_gate_passed':False,
        'historical_option_quotes_verified':False,'dividend_cashflows_included':False,'request_attempts_in_this_client':client.request_count,'coverage':coverage,'source_metadata':sources,
        'files':{label:{'path':str(path),'sha256':sha256(path.read_bytes()).hexdigest()} for label,path in paths.items()},
        'limitations':['Current-sector classification, market cap and volume are not point-in-time historical eligibility.','The bounded100-name source snapshot is not a complete historical financial-sector universe.','First observed price is data availability, not a verified IPO date or historical membership start.','Current issuer-name deduplication does not validate every historical merger/spinoff/symbol reassignment.','All selected columns and unavailable dates are retained; downstream balanced subsets must disclose exclusions explicitly.'],
    }
    (output_dir/'financial_50_metadata.json').write_text(json.dumps(metadata,indent=2)+'\n')
    return metadata

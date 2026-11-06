"""Export fixed core10/ETF histories with explicit BK-to-BNY issuer continuity.

First seed JPM/PNC/GS via audit_market_data.py --export-prices. This command then
allows at most9 new core/ETF requests plus one identifier-resolution request.
All requests reuse normalized caches. The source mapping is documented below.
"""
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[2]
if str(ROOT / "src") not in sys.path:sys.path.insert(0,str(ROOT / "src"))
from market_data import FMPClient, load_fmp_api_key
from market_data.coverage import check_exchange_calendar

CORE=['JPM','PNC','GS','BAC','WFC','C','USB','MS','SCHW','BK']
BENCHMARKS=['SPY','XLF']
START='2010-01-04'
END='2026-11-04'
EFFECTIVE='2026-05-21'
ISSUER_SOURCE='https://www.bny.com/corporate/global/en/about-us/newsroom/press-release/bny-announces-planned-change-of-stock-ticker-symbol-to-bny-130465.html'


def _write_csv(frame,path):
    content=frame.to_csv(date_format='%Y-%m-%d').encode()
    if not path.exists() or path.read_bytes()!=content:
        temporary=path.with_suffix('.tmp')
        temporary.write_bytes(content)
        temporary.replace(path)
    return {'path':str(path),'sha256':sha256(content).hexdigest(),'observations':len(frame)}


def main():
    out=ROOT/'data/market';out.mkdir(parents=True,exist_ok=True)
    key=load_fmp_api_key(ROOT/'.env')
    client=FMPClient(key,cache_dir=ROOT/'data/cache/fmp',max_requests=9)
    identifiers=FMPClient(key,cache_dir=ROOT/'data/cache/fmp',max_requests=1)
    columns={};sources={};raw_coverage=[]
    for symbol in CORE+BENCHMARKS:
        dataset=client.get_prices(symbol,START,END,adjustment='split_adjusted')
        frame=pd.DataFrame(dataset['records'])
        if frame.empty:raise ValueError('A required core/benchmark history is empty')
        series=frame.set_index(pd.to_datetime(frame['date']))['close'].rename(symbol)
        series.index.name='date'
        columns[symbol]=series;sources[symbol]=dataset['metadata']
        raw_coverage.append({'symbol':symbol,'observations':len(series),'first_date':series.index[0].strftime('%Y-%m-%d'),'last_date':series.index[-1].strftime('%Y-%m-%d'),**check_exchange_calendar(series.index,START,END)})
    current=identifiers.get_prices('BNY',START,END,adjustment='split_adjusted')
    frame=pd.DataFrame(current['records'])
    bny=frame.set_index(pd.to_datetime(frame['date']))['close'].rename('BNY')
    bny.index.name='date'
    old=columns['BK']
    overlap=old.index.intersection(bny.index)
    if len(overlap)==0:raise ValueError('BK/BNY issuer-price overlap cannot be verified')
    np.testing.assert_allclose(old.loc[overlap],bny.loc[overlap],rtol=1e-6,atol=1e-6)
    mapped=pd.concat([old.loc[old.index<EFFECTIVE],bny.loc[bny.index>=EFFECTIVE]]).sort_index().rename('BK')
    assert not mapped.index.has_duplicates
    assert check_exchange_calendar(mapped.index,START,END)['exchange_calendar_validated']
    columns['BK']=mapped
    mapping={
        'stable_study_id':'BK','issuer':'The Bank of New York Mellon Corporation','old_ticker':'BK','current_ticker':'BNY','effective_date':EFFECTIVE,
        'mapping_rule':'BK observations before effective date; actual BNY observations on/after effective date; no forward fill.',
        'issuer_source':ISSUER_SOURCE,'issuer_capital_structure_or_CUSIP_changed':False,
        'vendor_overlap_observations':len(overlap),'max_overlap_abs_difference':float((old.loc[overlap]-bny.loc[overlap]).abs().max()),
        'source_metadata_BNY':current['metadata'],
    }
    coverage=[];files={}
    for label,names,filename in [('core_10',CORE,'prices_core_10.csv'),('benchmarks',BENCHMARKS,'prices_benchmarks.csv')]:
        panel=pd.concat([columns[name] for name in names],axis=1).sort_index()
        assert not panel.isna().any().any()
        assert np.isfinite(panel.to_numpy()).all() and (panel.to_numpy()>0).all()
        calendar=check_exchange_calendar(panel.index,START,END)
        assert calendar['exchange_calendar_validated']
        files[label]=_write_csv(panel,out/filename)
        for name in names:
            coverage.append({'symbol':name,'observations':len(panel),'first_date':panel.index[0].strftime('%Y-%m-%d'),'last_date':panel.index[-1].strftime('%Y-%m-%d'),'canonical_series':'issuer_resolved' if name=='BK' else 'direct_symbol',**calendar})
    _write_csv(pd.concat([old.rename('BK_original_symbol'),bny.rename('BNY_current_symbol')],axis=1),out/'bny_symbol_history_raw.csv')
    (out/'issuer_symbol_mappings.json').write_text(json.dumps({'mappings':[mapping]},indent=2)+'\n')
    metadata={
        'retrieved_utc':datetime.now(timezone.utc).isoformat(),'source':'FMP','adjustment':'split_adjusted','source_price_field':'close','currency':'USD',
        'requested_start':START,'requested_end':END,'core_symbols':CORE,'benchmark_symbols':BENCHMARKS,
        'core_requests_this_run':client.request_count,'identifier_requests_this_run':identifiers.request_count,
        'coverage':coverage,'raw_symbol_coverage':raw_coverage,'source_metadata':sources,'issuer_symbol_mappings':[mapping],
        'data_files':files,'core_panel_status':'aligned_with_explicit_issuer_mapping','core_panel_observations':files['core_10']['observations'],
        'dividend_cashflows_included':False,'historical_option_quotes_included':False,
        'universe_selection':'fixed current named example; not point-in-time membership',
        'historical_membership_status':'entitlement_denied_HTTP_402','survivorship_safe_generalization_gate_passed':False,
    }
    (out/'core_10_metadata.json').write_text(json.dumps(metadata,indent=2)+'\n')
    pd.DataFrame([{k:v for k,v in row.items() if not isinstance(v,list)} for row in coverage]).to_csv(out/'core_10_coverage.csv',index=False)
    print(json.dumps({'status':'exported','files':files,'core_requests':client.request_count,'identifier_requests':identifiers.request_count,'mapping_overlap':len(overlap)},indent=2))


if __name__=='__main__':
    try:main()
    except Exception as error:
        # Avoid raw errors from any request transport or provider payload.
        print(json.dumps({'status':'core_export_failed','safe_code':getattr(error,'code',None),'error_type':type(error).__name__}))
        raise SystemExit(1) from None

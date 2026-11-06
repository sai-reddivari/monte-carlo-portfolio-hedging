"""Bounded SEC core10 extension; separate artifacts, no retries on failure."""
from datetime import datetime,timezone
from hashlib import sha256
import json
from pathlib import Path
import ssl
import sys
import time
from urllib.error import HTTPError,URLError
from urllib.request import Request,urlopen

import certifi

ROOT=Path(__file__).resolve().parents[2]
if str(ROOT / "src") not in sys.path:sys.path.insert(0,str(ROOT / "src"))
from market_data import FMPClient,FMPError,load_fmp_api_key
from market_data.features import fetch_feature_endpoint
from market_data.sec_facts import CORE10_BUSINESS_GROUPS,export_cached_sec_core10


def main():
    out=ROOT/'data/market/features/sec_facts_core10';out.mkdir(parents=True,exist_ok=True)
    cache=ROOT/'data/cache/sec';cache.mkdir(parents=True,exist_ok=True)
    manifest_path=out/'sec_core10_probe_manifest.json'
    frozen=ROOT/'data/market/features/sec_facts'
    frozen_hashes={str(path):sha256(path.read_bytes()).hexdigest() for path in frozen.glob('*') if path.is_file()}
    if manifest_path.exists():
        manifest=json.loads(manifest_path.read_text())
        if manifest.get('stopped_on_error'):raise ValueError('Previous source access failed; no automatic retry authorized')
    else:
        original=json.loads((ROOT/'data/market/features/sec_probe_manifest.json').read_text())
        manifest={'started_utc':datetime.now(timezone.utc).isoformat(),
            'user_agent':'MonteCarloEvaluations/0.1 (noncommercial portfolio hedging research)',
            'fmp_identifier_requests':0,'sec_requests':0,'identifiers':dict(original['identifiers']),
            'requests':[],'stopped_on_error':False,'frozen_base_sha256':frozen_hashes}
    def save():manifest_path.write_text(json.dumps(manifest,indent=2)+'\n')
    fmp=FMPClient(load_fmp_api_key(ROOT/'.env'),max_requests=max(1,7-manifest['fmp_identifier_requests']),timeout=20)
    try:
        for symbol in CORE10_BUSINESS_GROUPS:
            if symbol in manifest['identifiers']:continue
            if manifest['fmp_identifier_requests']>=7:raise ValueError('FMP identifier request budget exhausted')
            lookup='BNY' if symbol=='BK' else symbol
            manifest['fmp_identifier_requests']+=1;save()
            payload=fetch_feature_endpoint(fmp,'sec-filings-search/symbol',{'symbol':lookup,'from':'2026-01-01','to':'2026-11-04','page':0,'limit':1})
            allowed={'symbol','cik','filingDate','acceptedDate','formType','link','finalLink'}
            records=[{key:value for key,value in row.items() if key in allowed} for row in payload if isinstance(row,dict)]
            ciks={str(row.get('cik','')).zfill(10) for row in records if str(row.get('cik','')).isdigit() and row.get('symbol')==lookup}
            if len(ciks)!=1:raise ValueError('Identifier metadata missing or ambiguous')
            path=out/f'{symbol}_identifier_fmp_filings.json'
            path.write_text(json.dumps({'source':'FMP actual SEC filing metadata','study_symbol':symbol,'lookup_symbol':lookup,'records':records},indent=2)+'\n')
            manifest['identifiers'][symbol]={'cik':next(iter(ciks)),'source_metadata_path':str(path),'lookup_symbol':lookup};save()
            print(json.dumps({'symbol':symbol,'identifier_status':'verified_actual_filing_metadata'}),flush=True)
            time.sleep(.25)
        for symbol in CORE10_BUSINESS_GROUPS:
            for kind in ['companyfacts','submissions']:
                path=cache/f'{symbol}_{kind}.json'
                if path.exists():continue
                if manifest['sec_requests']>=14:raise ValueError('SEC request budget exhausted')
                cik=manifest['identifiers'][symbol]['cik']
                url=f'https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json' if kind=='companyfacts' else f'https://data.sec.gov/submissions/CIK{cik}.json'
                request=Request(url,headers={'User-Agent':manifest['user_agent'],'Accept':'application/json'})
                manifest['sec_requests']+=1;save()
                with urlopen(request,timeout=30,context=ssl.create_default_context(cafile=certifi.where())) as response:
                    raw=response.read(40_000_001)
                if len(raw)>40_000_000:raise ValueError('SEC response exceeds size bound')
                payload=json.loads(raw)
                if int(payload['cik'])!=int(cik):raise ValueError('SEC issuer mismatch')
                path.write_text(json.dumps(payload))
                manifest['requests'].append({'symbol':symbol,'kind':kind,'status':'observed','bytes':len(raw),'path':str(path),'source_url':url});save()
                print(json.dumps({'symbol':symbol,'kind':kind,'status':'observed','bytes':len(raw)}),flush=True)
                time.sleep(.25)
    except (HTTPError,URLError,FMPError,ValueError,KeyError) as error:
        manifest['stopped_on_error']=True
        manifest['safe_failure']={'error_type':type(error).__name__,'http_status':getattr(error,'code',None) if isinstance(error,HTTPError) else getattr(error,'http_status',None)}
        save();print(json.dumps({'status':'stopped_without_retry',**manifest['safe_failure']}));return
    report=export_cached_sec_core10(ROOT)
    if any(sha256(Path(path).read_bytes()).hexdigest()!=digest for path,digest in frozen_hashes.items()):
        raise ValueError('Frozen three-name artifacts changed')
    manifest['finished_utc']=datetime.now(timezone.utc).isoformat();manifest['frozen_base_unchanged']=True;save()
    print(json.dumps({'status':'completed','snapshots':report['snapshot_rows'],'facts':report['retained_filing_fact_rows'],'fmp_requests':manifest['fmp_identifier_requests'],'sec_requests':manifest['sec_requests'],'frozen_base_unchanged':True}))


if __name__=='__main__':
    try:main()
    except Exception as error:
        print(json.dumps({'status':'extension_failed','error_type':type(error).__name__}));raise SystemExit(1) from None

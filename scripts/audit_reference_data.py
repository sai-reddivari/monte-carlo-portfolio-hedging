"""Bounded current-universe/membership entitlement audit: at most3 requests.

This explicitly refreshes a current metadata snapshot; it cannot reconstruct
past eligibility. Preserve its saved timestamp and hashes with any research run.
"""
from pathlib import Path
import json
import sys
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:sys.path.insert(0,str(ROOT))
from market_data import FMPClient,FMPError,load_fmp_api_key


def main():
    out=ROOT/'data/market';out.mkdir(parents=True,exist_ok=True)
    client=FMPClient(load_fmp_api_key(ROOT/'.env'),cache_dir=ROOT/'data/cache/fmp',max_requests=3)
    queries=[
        ('company-screener',{'sector':'Financial Services','country':'US','exchange':'NYSE,NASDAQ','isEtf':'false','isFund':'false','isActivelyTrading':'true','limit':100},'financial_universe_current'),
        ('historical-sp500-constituent',{},'sp500_membership_changes'),
        ('delisted-companies',{'page':0,'limit':10},'delisted_sample'),
    ]
    report=[]
    for endpoint,parameters,label in queries:
        try:
            result=client.get_reference(endpoint,parameters)
            (out/f'{label}.json').write_text(json.dumps(result,indent=2)+'\n')
            pd.DataFrame(result['records']).to_csv(out/f'{label}.csv',index=False)
            report.append({'endpoint':endpoint,'status':'observed','records':len(result['records']),'path':str(out/f'{label}.csv'),'historical_completeness_validated':False})
        except FMPError as error:
            report.append({'endpoint':endpoint,'status':error.code,'http_status':error.http_status})
    result={'requests_sent':client.request_count,'datasets':report}
    (out/'reference_audit.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()

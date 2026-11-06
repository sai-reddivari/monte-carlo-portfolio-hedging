"""Fetch an explicitly conditional current50-name research panel (no PIT claim)."""
from pathlib import Path
import json
import sys
import pandas as pd

ROOT=Path(__file__).resolve().parents[2]
if str(ROOT / "src") not in sys.path:sys.path.insert(0,str(ROOT / "src"))
from market_data import FMPClient,load_fmp_api_key
from market_data.universe import select_current_universe,fetch_unbalanced_panel


def main():
    source=json.loads((ROOT/'data/market/financial_universe_current.json').read_text())
    universe,audit=select_current_universe(pd.DataFrame(source['records']))
    audit.to_csv(ROOT/'data/market/financial_50_eligibility_audit.csv',index=False)
    # One previous BNY issuer-continuity request consumed the first breadth
    # request. Remaining ceiling49 includes any bounded retries and failures.
    client=FMPClient(load_fmp_api_key(ROOT/'.env'),cache_dir=ROOT/'data/cache/fmp',timeout=15,max_requests=49)
    metadata=fetch_unbalanced_panel(client,universe,output_dir=ROOT/'data/market',snapshot_metadata=source['metadata'])
    print(json.dumps({'selected_names':metadata['selected_names'],'request_attempts':client.request_count,'full_histories':sum(row['status']=='observed_full' for row in metadata['coverage']),'partial_histories':sum(row['status']=='observed_partial' for row in metadata['coverage']),'failed_histories':sum(row['status'] not in ['observed_full','observed_partial'] for row in metadata['coverage']),'historical_membership_verified':False,'survivorship_safe_generalization_gate_passed':False,'prices':metadata['files']['prices']['path']},indent=2))


if __name__=='__main__':main()

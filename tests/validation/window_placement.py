from pathlib import Path
import sys,json,hashlib,time
from datetime import datetime,timezone
import numpy as np
import pandas as pd
import argparse
parser = argparse.ArgumentParser(description='Reproduce fixed window-placement diagnostics.')
parser.add_argument('--repo', type=Path, required=True)
parser.add_argument('--output-dir', type=Path, required=True)
args = parser.parse_args()
ROOT = args.repo.resolve()
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from hedging_harness import overlays as ov
OUT = args.output_dir.resolve()
OUT.mkdir(parents=True, exist_ok=False)
FROZEN=ROOT/'results/equity-overlays-20261106T023430248130Z'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
source=json.loads((FROZEN/'protocol.json').read_text())
config=source['config']
labels=['unhedged','reduced_75']+[v['label'] for v in source['selection'].values()]
candidates=[next(c for c in source['candidates'] if c['label']==label) for label in labels]
assert len(candidates)==8
for p,h in {**source['source_sha256'],**source['input_sha256']}.items():
    assert sha(ROOT/p)==h,(p,'changed since frozen run')
protocol={'purpose':'Post-hoc descriptive window-phase sensitivity on already exposed outcomes; not a new confirmatory test.',
    'created_utc':datetime.now(timezone.utc).isoformat(),'offset_sessions':[0,5,21,42],
    'anchoring':'Each split starts at its original first eligible execution session plus offset; subsequent windows advance63 sessions and end within split.',
    'sessions':63,'labels':labels,'fixed_candidates':candidates,
    'source_frozen_protocol':str(FROZEN/'protocol.json'),'source_frozen_protocol_sha256':sha(FROZEN/'protocol.json'),
    'config':config,'source_sha256':source['source_sha256'],'input_sha256':source['input_sha256'],
    'script_sha256':sha(__file__),
    'analysis':'All offsets reported separately. Same8 selected policies, past-only estimates recomputed at each shifted decision date. No reselection, no pooling of overlapping offset samples, no new confidence intervals, no continuous NAV.',
    'metrics':['n_windows','tail_windows','es_loss_pct','mean_pnl_pct','upside_retained','downside_capture'],
    'baseline_check':'Offset0 summaries must match frozen development_summary.csv and summary.csv to1e-9.'}
pp=OUT/'diagnostic_protocol.json'
assert not pp.exists(),'Do not overwrite diagnostic freeze'
pp.write_text(json.dumps(protocol,indent=2)+'\n')
(OUT/'diagnostic_protocol.sha256').write_text(sha(pp)+'\n')
(OUT/'pre_run_commitment.json').write_text(json.dumps({'frozen_utc':datetime.now(timezone.utc).isoformat(),'protocol_sha256':sha(pp),'evaluation_started':False},indent=2)+'\n')
print('FROZEN',sha(pp),flush=True)
start_time=time.monotonic()
prices=ov.load_panel(config,ROOT)
settings=ov.Settings.from_config(config)
weights=ov.signed_weights(config)
calendar=prices.index
summaries=[];records=[];allchecks=[];windows_meta=[]
for offset in protocol['offset_sessions']:
    for split,(begin,end) in config['splits'].items():
        original=ov.build_windows(calendar,split,begin,end,63,settings.lookback,config['windows']['decision_lag_sessions'])
        first=calendar.get_loc(original[0].start)+offset
        windows=ov.build_windows(calendar,split,calendar[first],end,63,settings.lookback,config['windows']['decision_lag_sessions'])
        assert all(w.end<=pd.Timestamp(end) and w.sessions==63 for w in windows)
        rec,checks,_=ov.evaluate_windows(prices,windows,candidates,weights,settings)
        assert checks.drop(columns=['key','label']).all().all()
        summary=ov.summarize(rec,.25)
        summary.insert(0,'offset_sessions',offset);rec.insert(0,'offset_sessions',offset);checks.insert(0,'offset_sessions',offset);checks.insert(1,'split',split)
        summaries.append(summary);records.append(rec);allchecks.append(checks)
        windows_meta.append({'offset_sessions':offset,'split':split,'n_windows':len(windows),'first_start':str(windows[0].start.date()),'last_end':str(windows[-1].end.date())})
        pd.concat(summaries,ignore_index=True).to_csv(OUT/'summary.csv',index=False)
        pd.concat(records,ignore_index=True).to_csv(OUT/'window_records.csv',index=False)
        pd.concat(allchecks,ignore_index=True).to_csv(OUT/'checks.csv',index=False)
        print('DONE',offset,split,len(windows),round(time.monotonic()-start_time,1),flush=True)
        if time.monotonic()-start_time>540:raise TimeoutError('Bounded diagnostic exceeded9min')
summary=pd.concat(summaries,ignore_index=True)
reference=pd.concat([pd.read_csv(FROZEN/'development_summary.csv'),pd.read_csv(FROZEN/'summary.csv')]).drop_duplicates(['split','label'],keep='last')
base=summary.loc[summary.offset_sessions.eq(0)]
merged=base.merge(reference,on=['split','label'],suffixes=('_new','_frozen'),validate='one_to_one')
metrics=['n_windows','tail_windows','es_loss_pct','mean_pnl_pct','upside_retained','downside_capture']
errors={m:float(np.nanmax(np.abs(merged[m+'_new']-merged[m+'_frozen']))) for m in metrics}
assert all(e<1e-9 for e in errors.values()),errors
comparisons=[]
for (offset,split),group in summary.groupby(['offset_sessions','split']):
    ref=group.set_index('label')
    for _,row in group.iterrows():
        comparisons.append(dict(offset_sessions=int(offset),split=split,label=row.label,n_windows=int(row.n_windows),tail_windows=int(row.tail_windows),
            es_loss_pct=row.es_loss_pct,mean_pnl_pct=row.mean_pnl_pct,upside_retained=row.upside_retained,
            es_reduction_vs_unhedged=float(ref.loc['unhedged','es_loss_pct']-row.es_loss_pct),
            es_reduction_vs_reduced75=float(ref.loc['reduced_75','es_loss_pct']-row.es_loss_pct)))
pd.DataFrame(comparisons).to_csv(OUT/'comparisons.csv',index=False)
pd.DataFrame(windows_meta).to_csv(OUT/'window_counts.csv',index=False)
assert sha(pp)==(OUT/'diagnostic_protocol.sha256').read_text().strip()
for p,h in {**source['source_sha256'],**source['input_sha256']}.items():assert sha(ROOT/p)==h,(p,'changed during diagnostic')
result={'completed_utc':datetime.now(timezone.utc).isoformat(),'elapsed_seconds':time.monotonic()-start_time,'baseline_max_abs_error':errors,
    'policy_window_replays':sum(len(x) for x in records),'all_accounting_checks':True,'protocol_sha256':sha(pp),'status':'complete_posthoc_diagnostic',
    'outputs_sha256':{p.name:sha(p) for p in OUT.glob('*.csv')}}
(OUT/'completion.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2),flush=True)

import sys,json,math
sys.path.insert(0,'.')
import numpy as np,pandas as pd
from hedging_harness import overlays as ov
from scripts import run_overlay_research as r
pd.set_option('display.width',230,'display.max_columns',30,'display.max_rows',60)
R='results/equity-overlays-20261106T023430248130Z'
p=json.load(open(R+'/protocol.json')); cfg=p['config']
print('hash/changed',r.verify_protocol(R)[1][:12],r.verify_protocol(R)[2])
panel=ov.load_panel(cfg,'.'); W=ov.signed_weights(cfg); S=ov.Settings.from_config(cfg)
wins=r._windows_for(cfg,panel.index); by={c['label']:c for c in p['candidates']}
sel={k:v['label'] for k,v in p['selection'].items()}
w=pd.read_csv(R+'/windows.csv')
# 1 budget: reprice ACTUAL contracts at decision close vs execution close
rows=[]
for sp in ('validation','test'):
  for win in wins[sp]:
    st=ov.estimate_state(panel,win.decision_date,W,S)
    for fam in ('long_puts','short_calls','sector_puts','structures','risk_informed'):
      ins=ov.build_instruction(by[sel[fam]],st,win,W,S)
      yrs=win.sessions/252
      dec=sum(q.units*ov.closed_form_price(st.spots[q.underlying],q.strike,yrs,S.rate,q.volatility,q.kind) for q in ins.positions)
      exe=sum(q.units*ov.closed_form_price(panel.loc[win.start,q.underlying],q.strike,yrs,S.rate,q.volatility,q.kind) for q in ins.positions)
      gap=np.mean([panel.loc[win.start,q.underlying]/st.spots[q.underlying]-1 for q in ins.positions]) if ins.positions else 0
      rows.append(dict(split=sp,key=win.key,start=win.start.date(),fam=fam,budget=ins.window_budget,dec=dec,exe=exe,gap=gap))
b=pd.DataFrame(rows); b['mult_dec']=b.dec/b.budget; b['mult_exe']=b.exe/b.budget
print(b.groupby(['split','fam']).agg(n=('key','size'),max_dec=('mult_dec','max'),max_exe=('mult_exe','max'),over=('mult_exe',lambda x:int((x>1).sum())),sum_exe=('exe','sum'),sum_bud=('budget','sum')).assign(total_ratio=lambda d:d.sum_exe/d.sum_bud).round(3))
print(b.loc[b.groupby(['split','fam']).mult_exe.idxmax(),['split','fam','key','start','mult_dec','mult_exe','gap']].round(3).to_string(index=False))
print('corr premium slippage vs gap',b.assign(sl=(b.exe-b.dec)/b.budget).groupby('fam').apply(lambda d:round(d.sl.corr(d.gap),2)).to_dict())
# 2 exposure drift
u=w[(w.label=='unhedged')]
for sp in ('validation','test'):
  d=u[u.split==sp]; print(sp,'gross',round(d.gross_exposure_pct.min(),3),round(d.gross_exposure_pct.max(),3),'net',round(d.net_exposure_pct.min(),3),round(d.net_exposure_pct.max(),3),'argmax',d.loc[d.gross_exposure_pct.idxmax(),'start'],'argmin',d.loc[d.gross_exposure_pct.idxmin(),'start'])
# 3 collar delta split by leg at execution
rows=[]
for win in wins['test']:
  st=ov.estimate_state(panel,win.decision_date,W,S); ins=ov.build_instruction(by[sel['structures']],st,win,W,S); yrs=win.sessions/252
  def delta(q):
    s=panel.loc[win.start,q.underlying]; root=q.volatility*math.sqrt(yrs); d1=(math.log(s/q.strike)+(S.rate+q.volatility**2/2)*yrs)/root
    n=.5*(1+math.erf(d1/math.sqrt(2))); return q.units*s*(n if q.kind=='call' else n-1)/1e6
  rows.append(dict(key=win.key,put=sum(delta(q) for q in ins.positions if q.kind=='put'),call=sum(delta(q) for q in ins.positions if q.kind=='call')))
c=pd.DataFrame(rows); print('collar mean delta put,call pct',c.put.mean().round(3),c.call.mean().round(3))
col=w[(w.label=='collar_95_110_b2')&(w.split=='test')]; print('collar delta_adj mean',col.delta_adjusted_net_pct.mean().round(3),'range',col.delta_adjusted_net_pct.min().round(1),col.delta_adjusted_net_pct.max().round(1),'settle paid windows',(col.settlement_paid>0).sum(),'paid$m',round(col.settlement_paid.sum()/1e6,1),'recv$m',round(col.settlement_received.sum()/1e6,1))
# collar pnl change vs unhedged in up/down windows
un=u[u.split=='test'].set_index('key'); cc=col.set_index('key'); dif=(cc.pnl_pct-un.pnl_pct)
print('collar diff: down-window sum',dif[un.pnl<0].sum().round(2),'up-window sum',dif[un.pnl>0].sum().round(2),'n',(un.pnl<0).sum(),(un.pnl>0).sum())
# 4 short sleeve capture
sc=w[(w.label=='short_call_k110_b1')&(w.split=='test')].set_index('key')
L=un[un.short_equity_pnl<0].index
base=un.loc[L,'short_equity_pnl'].sum(); opt=sc.loc[L,'option_pnl'].sum(); fin=(sc.loc[L,'interest']-un.loc[L,'interest']).sum()
print('capture ex fin',round((base+opt)/base,6),'incl fin',round((base+opt+fin)/base,6),'fin$',round(fin),'whole-book window net',round((sc.pnl-un.pnl).sum()/1e6,2),'tail diff')
t6=un.nsmallest(6,'pnl').index; print('call option pnl in book tail $m',round(sc.loc[t6,'option_pnl'].sum()/1e6,2),'paid',round(sc.loc[t6,'settlement_received'].sum()/1e6,2))
# 5 drawdown
for lab in ('unhedged','long_put_k90_b2'):
  d=w[(w.label==lab)&(w.split=='validation')].sort_values('max_drawdown_pct').iloc[-1]; print(lab,d.key,d.max_drawdown_pct.round(3),d.pnl_pct.round(3))

"""Build publication figures from saved aggregate results; no fitting or simulation."""
from pathlib import Path
import argparse
import json
import hashlib
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
import pandas as pd

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'results/figures'
INK='#183B48';TEAL='#247B82';ORANGE='#C8713A';GRAY='#7B878C';PALE='#EFF5F5'
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.labelcolor':INK,
    'text.color':INK,'axes.edgecolor':'#B6C2C6','axes.spines.top':False,'axes.spines.right':False,
    'axes.titleweight':'bold','axes.titlepad':14,'figure.facecolor':'white','savefig.facecolor':'white'})
SOURCES=[
 'results/research-release-1/release-1/evaluation_metrics.csv',
 'results/research-release-1/release-1/paired_tail_differences.csv',
 'results/equity-overlays-20261106T023430248130Z/summary.csv',
 'results/breadth-20261106T020730752645Z/policy_summary.csv',
 'tests/artifacts/independent_validation/window_placement/comparisons.csv',
 'data/market/financial_50_coverage.csv']
CONTROL_SOURCES=[
 'config/research_release_1.json',
 'config/equity_overlay_study.json',
 'src/hedging_harness/breadth.py',
 'src/hedging_harness/feature_models.py',
 'src/hedging_harness/experiments/run_feature_research.py',
 'tests/validation/accounting.py',
 'tests/validation/statistics.py',
 'tests/validation/window_placement.py']

def save(fig,name):
    for ext in ['png','pdf']:fig.savefig(OUT/f'{name}.{ext}',dpi=190,bbox_inches='tight',pad_inches=.16)
    plt.close(fig)

def build_controls_figure():
    """Explain design choices and their limits; this is not an additional result."""
    OUT.mkdir(parents=True,exist_ok=True)
    fig=plt.figure(figsize=(11.6,7.4))
    ax=fig.add_axes([.02,.05,.96,.90])
    ax.axis('off');ax.set_xlim(0,12);ax.set_ylim(0,7.2)
    ax.text(.12,7.02,'What the design protects against — and what remains open',
            fontsize=15,fontweight='bold',va='top')
    columns=[.18,2.72,7.65]
    for x,label,color in zip(columns,
            ['WHAT COULD MISLEAD US?','WHAT WE CONTROLLED OR CHECKED','WHAT REMAINS UNRESOLVED'],
            [INK,TEAL,ORANGE]):
        ax.text(x,6.38,label,fontsize=9.5,fontweight='bold')
    rows=[
      ('Unequal\ncomparisons',
       'Shared simulated paths; fixed notional\nin breadth tests; common base holdings\nfor historical overlays.',
       'Reducing exposure changes upside;\nadding names also changes\nportfolio composition.'),
      ('Selection\noptimism',
       'Fresh simulated evaluation paths;\nchronological historical splits;\ntrain-only fitting, validation selection.',
       'Historical periods are not unknown;\nadditional checks on observed\noutcomes remain post-hoc.'),
      ('Unavailable\ninformation',
       'Filing-linked facts; next-session-close\nadmission and staleness limits;\npast-only estimates and execution lag.',
       'Availability conventions are not\na verified record of when every\nvendor observation arrived.'),
      ('Arithmetic or\nsampling error',
       'Cash/stock/option reconciliation;\nindependent terminal reconstruction;\npaired, dependence-aware intervals.',
       'Few historical tail windows;\npointwise intervals; arithmetic\nchecks do not validate market prices.'),
      ('Dependence on\none specification',
       'Cost and pricing-volatility grids;\ncomposition and dependence scenarios;\nshifted historical windows.',
       'Overlapping windows add no new\nindependent crises. Executable prices\nand usable liquidity remain untested.')]
    for i,(risk,control,limit) in enumerate(rows):
        top=6.10-i*1.13
        ax.add_patch(FancyBboxPatch((.05,top-1.03),11.9,1.02,
            boxstyle='round,pad=.01,rounding_size=.045',
            facecolor=PALE if i%2==0 else '#F8FAFA',edgecolor='none'))
        ax.text(columns[0],top-.17,risk,fontsize=12,fontweight='bold',va='top',linespacing=1.45)
        ax.text(columns[1],top-.16,control,fontsize=11.5,va='top',linespacing=1.5,color=TEAL)
        ax.text(columns[2],top-.16,limit,fontsize=11.5,va='top',linespacing=1.5,color=INK)
    ax.text(.12,.13,'Each control applies to its relevant experiment; sensitivity checks do not certify real-market performance.',
            fontsize=10,color=GRAY)
    for ext in ['png','svg']:
        fig.savefig(OUT/f'research_controls.{ext}',dpi=190,bbox_inches='tight',pad_inches=.16)
    svg=OUT/'research_controls.svg'
    svg.write_text('\n'.join(line.rstrip() for line in svg.read_text().splitlines())+'\n')
    plt.close(fig)

def write_manifest():
    manifest={'purpose':'Publication exhibits and design explanation; no new empirical experiment.',
      'inputs':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in SOURCES if (ROOT/p).is_file()},
      'design_sources':{p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in CONTROL_SOURCES},
      'builder_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (OUT/'sources.json').write_text(json.dumps(manifest,indent=2)+'\n')

def build():
    OUT.mkdir(parents=True,exist_ok=True)
    # Explicitly separate experiment types: one is not empirical confirmation of the other.
    fig,ax=plt.subplots(figsize=(11.5,4.1));ax.axis('off');ax.set_xlim(0,12);ax.set_ylim(0,4.2)
    cards=[(.1,'01  CONTROLLED EXPERIMENT','Choose when to\nrebalance','3-name short-call book\n14 hedge rules\n5,000 selection paths\n10,000 held-out paths','Question: cost versus residual tail loss'),
           (4.1,'02  HISTORICAL APPLICATION','Compare ways to\nprotect equity','10-name long/short portfolio\n8 protection policies\n11 validation + 23 test windows\nModel-priced European options','Question: protection versus retained upside'),
           (8.1,'03  BREADTH EXTENSION','Vary portfolio\ncomposition','50 companies audited\n42 complete histories\n3 / 10 / 25 / 40-name books\nFixed total notional; common paths','Question: what changes with more names?')]
    for x,k,title,body,foot in cards:
        ax.add_patch(FancyBboxPatch((x,.35),3.7,3.65,boxstyle='round,pad=.02,rounding_size=.10',facecolor=PALE,edgecolor='#D9E5E5'))
        ax.text(x+.18,3.65,k,color=TEAL,fontsize=10,fontweight='bold')
        ax.text(x+.18,3.19,title,fontsize=11.4,fontweight='bold')
        ax.text(x+.18,2.45,body,va='top',fontsize=11,linespacing=1.65)
        ax.text(x+.18,.73,foot,fontsize=8.5,color=GRAY)
    save(fig,'study_design')
    e=pd.read_csv(ROOT/SOURCES[0],float_precision='round_trip').set_index('policy')
    names=['weekly','maturity_band_050','daily'];labels=['Weekly','Selected band','Daily'];colors=[GRAY,TEAL,INK]
    fig,axes=plt.subplots(1,2,figsize=(10.7,4.5))
    for ax,col,title in zip(axes,['loss_es95','mean_financed_cost'],['Tail loss on held-out paths','Financed trading cost']):
        vals=e.loc[names,col];ax.bar(labels,vals,color=colors,width=.57)
        ax.set_title(title,loc='left',fontsize=13);ax.set_ylabel('US dollars');ax.set_ylim(0,max(vals)*1.24)
        ax.spines['left'].set_visible(False);ax.grid(axis='y',alpha=.18);ax.set_axisbelow(True)
        for i,v in enumerate(vals):ax.text(i,v+max(vals)*.025,f'${v:,.2f}',ha='center',fontsize=10,fontweight='bold')
    axes[0].text(.02,.96,'ES95: mean loss in the worst 5% of paths',transform=axes[0].transAxes,va='top',fontsize=9,color=GRAY)
    axes[1].axhline(500,color=ORANGE,lw=1.3,ls='--');axes[1].text(.02,.96,'$500 expected-cost screen',transform=axes[1].transAxes,va='top',fontsize=9,color=ORANGE)
    fig.subplots_adjust(wspace=.28,bottom=.20)
    fig.text(.08,.035,'10,000 held-out paths. Selected minus daily ES95: +$1.90; paired 95% interval [-$31.61, +$33.56].',fontsize=9,color=GRAY)
    save(fig,'controlled_tradeoff')
    s=pd.read_csv(ROOT/SOURCES[2],float_precision='round_trip');s=s.loc[s.split.eq('test')].set_index('label')
    selected={'unhedged':('Unhedged',(8,-6)), 'reduced_75':('75% equity',(-80,-19)),
      'long_put_k90_b2':('Single-name puts',(-123,-7)), 'collar_95_110_b2':('Collar',(10,6)),
      'etf_h100':('XLF hedge',(10,4)), 'short_call_k110_b1':('Calls on short equities',(-160,10)),
      'sector_put_k95_b2':('Sector puts',(-94,-3)), 'risk_k90_t125':('Risk-informed puts',(14,-16))}
    fig,ax=plt.subplots(figsize=(10.7,5.4))
    for k,(label,offset) in selected.items():
        row=s.loc[k];x=row.upside_retained*100;y=row.es_loss_pct
        color=TEAL if k in ['long_put_k90_b2','collar_95_110_b2'] else INK if k in ['unhedged','reduced_75'] else GRAY
        ax.scatter(x,y,s=80,color=color,zorder=3,edgecolor='white',linewidth=.8)
        ax.annotate(label,(x,y),xytext=offset,textcoords='offset points',fontsize=9.5,color=color)
    ax.set_xlim(0,118);ax.set_ylim(2.4,7.05);ax.set_xlabel('Upside retained in baseline-up windows (%) →');ax.set_ylabel('Mean loss in the worst 6 of 23 test windows (%)')
    ax.set_title('Protection must be judged alongside retained upside',loc='left',fontsize=14)
    ax.grid(alpha=.16);ax.spines['left'].set_visible(False)
    ax.text(.02,.97,'Lower loss and greater upside are preferable; the figure shows point estimates.',transform=ax.transAxes,va='top',fontsize=9,color=GRAY)
    fig.subplots_adjust(bottom=.21)
    fig.text(.085,.035,'Separate 63-session accounts; percentages of initial capital. This is not simulated ES95 or a continuous return series.',fontsize=8.8,color=GRAY)
    save(fig,'historical_tradeoff')
    b=pd.read_csv(ROOT/SOURCES[3],float_precision='round_trip')
    fig,ax=plt.subplots(figsize=(9.8,4.2))
    for scenario,label,color in [('calibrated_dependence','Calibrated dependence',TEAL),('synthetic_common_shock_stress','Synthetic common shock',ORANGE)]:
        v=b.loc[b.scenario.eq(scenario)&b.composition.eq('canonical')&b.policy.eq('maturity_band_050')].sort_values('breadth')
        ax.plot(v.breadth,v.loss_es95,'o-',color=color,label=label,lw=2)
    ax.set_xticks([3,10,25,40]);ax.set_xlabel('Number of companies');ax.set_ylabel('Simulated ES95 (US dollars)');ax.set_title('More names do not guarantee a lower tail loss',loc='left',fontsize=14)
    ax.legend(frameon=False);ax.grid(alpha=.16)
    fig.subplots_adjust(bottom=.23)
    fig.text(.09,.03,'Canonical compositions; $300,000 total notional. Subsets share master paths within each scenario.',fontsize=9,color=GRAY)
    save(fig,'breadth')
    w=pd.read_csv(ROOT/SOURCES[4]);v=w.loc[w.label.eq('long_put_k90_b2')]
    fig,ax=plt.subplots(figsize=(9.8,4.2))
    for split,color in [('validation',TEAL),('test',ORANGE)]:
        z=v.loc[v.split.eq(split)].sort_values('offset_sessions')
        ax.plot(z.offset_sessions,z.es_reduction_vs_reduced75,'o-',label=split.title(),color=color,lw=2)
    ax.axhline(0,color=GRAY,ls='--',lw=1);ax.set_xticks([0,5,21,42]);ax.set_xlabel('Start-date offset (trading sessions)')
    ax.set_ylabel('Tail-loss reduction versus 75% equity (pp)');ax.set_title('The measured benefit depends on window placement',loc='left',fontsize=13)
    ax.legend(frameon=False);ax.grid(alpha=.16);fig.subplots_adjust(bottom=.23)
    fig.text(.09,.03,'Long puts; positive values favor puts. Post-hoc, overlapping samples; offsets are not independent crises.',fontsize=9,color=GRAY)
    save(fig,'window_placement')
    build_controls_figure()
    write_manifest()

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--only-controls',action='store_true',help='Build only the README design figure and refresh source identities.')
    args=parser.parse_args()
    if args.only_controls:
        build_controls_figure()
        write_manifest()
    else:
        build()

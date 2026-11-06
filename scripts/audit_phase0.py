"""Finish the Phase 0 manifest with read-only evidence/CSV comparisons.

No historical output or source is changed. Run only after freeze_phase0 batches
have completed. Rerunning recomputes audit fields; it never reruns experiments.
"""
from __future__ import annotations

from collections import Counter
import json
import os
from pathlib import Path
import re
import subprocess
import sys

from freeze_phase0 import BASE, MANIFEST, ROOT, THREADS, digest, dump, tracked

os.environ.update(THREADS)
import numpy as np
import pandas as pd


def evidence_checks():
    checks = []

    def check(base, name, expected, manifest):
        path = Path(name)
        if not path.is_absolute():
            path = base/path
        actual = digest(path) if path.is_file() else None
        checks.append(dict(manifest=str(manifest.relative_to(ROOT)),
            path=str(path.relative_to(ROOT)) if path.is_relative_to(ROOT) else str(path),
            expected=expected, actual=actual, passed=actual == expected))

    findings = ROOT/'docs/Final Findings and Takeaways'
    manifest = findings/'bundle_manifest.json'
    for name, expected in json.loads(manifest.read_text())['files_sha256'].items():
        check(findings, name, expected, manifest)
    for top in [findings/'frozen_package_and_review_evidence', ROOT/'results/research-release-2']:
        for manifest in sorted(top.glob('*/archive_manifest.json')):
            for name, spec in json.loads(manifest.read_text())['files'].items():
                check(manifest.parent, name, spec['sha256'], manifest)
        manifest = top/'release-2/manifest.json'
        value = json.loads(manifest.read_text())
        for name, spec in value['snapshots'].items():
            check(manifest.parent, name, spec['sha256'], manifest)
        for spec in value['frozen_experiments'].values():
            for name, expected in spec['files_sha256'].items():
                check(ROOT, name, expected, manifest)
        for name, expected in value['review_archive_manifests_sha256'].items():
            check(ROOT, name+'/archive_manifest.json', expected, manifest)
        manifest = top/'astra-review-20261106/accounting/verified_outputs/audit_summary.json'
        value = json.loads(manifest.read_text())
        for name, expected in value['artifacts_sha256'].items():
            check(manifest.parent, name, expected, manifest)
        check(manifest.parent.parent, value['script']['name'], value['script']['sha256'], manifest)
        for suffix, filename, field in [('statistical_review','metadata.json','artifacts_sha256'),
                                         ('window_placement','completion.json','outputs_sha256')]:
            manifest = top/'astra-review-20261106'/suffix/filename
            for name, expected in json.loads(manifest.read_text())[field].items():
                check(manifest.parent, name, expected, manifest)
    return checks


def csv_comparison(original, reproduced):
    result = dict(table=str(original.relative_to(ROOT)),
        reproduction=str(reproduced.relative_to(ROOT)), saved_sha256=digest(original),
        reproduced_sha256=digest(reproduced) if reproduced.is_file() else None,
        passed=False, numeric_cells=0, numeric_mismatches=0, text_mismatches=0,
        max_absolute_difference=0., max_finite_relative_difference=0., examples=[])
    result['byte_equal'] = result['saved_sha256'] == result['reproduced_sha256']
    if not reproduced.is_file():
        result['reason'] = 'Reproduction output missing'
        return result
    a = pd.read_csv(original, float_precision='round_trip')
    b = pd.read_csv(reproduced, float_precision='round_trip')
    if list(a.columns) != list(b.columns) or a.shape != b.shape:
        result['reason'] = f'Schema/shape differs: saved {a.shape}, new {b.shape}; saved columns {list(a.columns)}, new {list(b.columns)}'
        return result
    result['rows'], result['columns'] = a.shape
    for column in a.columns:
        left, right = a[column], b[column]
        numeric = pd.api.types.is_numeric_dtype(left) and pd.api.types.is_numeric_dtype(right)
        if numeric:
            x, y = left.to_numpy(dtype=float), right.to_numpy(dtype=float)
            valid = np.isclose(x, y, rtol=1e-9, atol=0, equal_nan=True)
            result['numeric_cells'] += int((~np.isnan(x)).sum())
            result['numeric_mismatches'] += int((~valid).sum())
            finite = np.isfinite(x) & np.isfinite(y)
            absolute = np.abs(y[finite]-x[finite])
            if len(absolute):
                result['max_absolute_difference'] = max(result['max_absolute_difference'],float(absolute.max()))
            nonzero = finite & (x != 0)
            if nonzero.any():
                result['max_finite_relative_difference'] = max(result['max_finite_relative_difference'],float(np.max(np.abs((y[nonzero]-x[nonzero])/x[nonzero]))))
        else:
            valid = ((left == right) | (left.isna() & right.isna())).to_numpy()
            result['text_mismatches'] += int((~valid).sum())
        for row in np.flatnonzero(~valid)[:5]:
            if len(result['examples']) < 12:
                def value(v):
                    if pd.isna(v):
                        return None
                    return v.item() if isinstance(v,np.generic) else v
                result['examples'].append(dict(row=int(row),column=column,before=value(left.iloc[row]),after=value(right.iloc[row])))
    result['passed'] = result['numeric_mismatches'] == 0 and result['text_mismatches'] == 0
    return result


def contracts(folder):
    # Small result tables contain published summaries, interval endpoints,
    # diagnostics and window accounting. Large prediction/trace tables retain
    # exact byte hashes and are compared in full, rather than duplicated here.
    values = {}
    for path in sorted(folder.rglob('*.csv')):
        if path.stat().st_size > 1024*1024:
            continue
        frame = pd.read_csv(path, float_precision='round_trip')
        numeric = frame.select_dtypes(include='number')
        if numeric.empty:
            continue
        text = frame.select_dtypes(exclude='number').fillna('').astype(str)
        values[str(path.relative_to(folder))] = dict(
            saved_table_sha256=digest(path),
            row_identifiers=text.to_dict(orient='list'),
            numbers={name:[float(v) if np.isfinite(v) else None for v in numeric[name]] for name in numeric.columns},
            nonfinite_convention='null represents a saved nonfinite/missing numeric cell; original bytes are hashed')
    return values


def json_comparison(original, reproduced):
    import math
    result=dict(file=str(original.relative_to(ROOT)),reproduction=str(reproduced.relative_to(ROOT)),
        byte_equal=reproduced.is_file() and digest(original)==digest(reproduced),numeric_cells=0,
        numeric_mismatches=[],observed_timing_differences=[],string_differences=[],structure_differences=[],boolean_differences=[])
    if not reproduced.is_file():
        result['structure_differences'].append('Reproduction output missing')
        result['passed']=False
        return result
    def compare(a,b,pointer=''):
        if isinstance(a,bool) or isinstance(b,bool):
            if a!=b:
                result['boolean_differences'].append(dict(pointer=pointer,before=a,after=b))
        elif isinstance(a,(int,float)) and isinstance(b,(int,float)):
            if pointer=='/elapsed_seconds':
                if a!=b:
                    result['observed_timing_differences'].append(dict(pointer=pointer,before=a,after=b,
                        reason='Measured runtime is observational, not an economic/numerical result. Both measurements are retained; no equality tolerance is asserted.'))
                return
            result['numeric_cells']+=1
            if not math.isclose(a,b,rel_tol=1e-9,abs_tol=0) and not (math.isnan(a) and math.isnan(b)):
                result['numeric_mismatches'].append(dict(pointer=pointer,before=a,after=b))
        elif isinstance(a,dict) and isinstance(b,dict):
            if a.keys()!=b.keys():
                result['structure_differences'].append(dict(pointer=pointer,missing=sorted(a.keys()-b.keys()),added=sorted(b.keys()-a.keys())))
            for key in a.keys() & b.keys():
                compare(a[key],b[key],pointer+'/'+str(key))
        elif isinstance(a,list) and isinstance(b,list):
            if len(a)!=len(b):
                result['structure_differences'].append(dict(pointer=pointer,before_length=len(a),after_length=len(b)))
            for index,(left,right) in enumerate(zip(a,b)):
                compare(left,right,pointer+'/'+str(index))
        elif a!=b:
            result['string_differences'].append(dict(pointer=pointer,before=a,after=b))
    compare(json.loads(original.read_text()),json.loads(reproduced.read_text()))
    result['passed']=not(result['numeric_mismatches'] or result['structure_differences'] or result['boolean_differences'])
    return result


def word_numbers():
    output = []
    pattern = r'\b(?:zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|fourteen|twenty|twenty-five|forty|fifty|hundred|million|first|second)\b'
    for path in sorted((ROOT/'docs/Final Findings and Takeaways').glob('research_release_2_*.md')):
        for line_number,line in enumerate(path.read_text().splitlines(),1):
            for found in re.finditer(pattern,line,flags=re.I):
                output.append(dict(document=str(path.relative_to(ROOT)),line=line_number,
                    column=found.start()+1,literal=found.group(),context=line))
    return output


def publication_checks():
    from decimal import Decimal
    refs = json.loads((ROOT/'config/research_release_2_package.json').read_text())['canonical_runs']
    checks = []

    def add(label, printed, actual, source, selector):
        # Display precision is separate from the 1e-9 deterministic replay
        # tolerance. Half a last printed unit is explicitly stored per number.
        printed = str(printed)
        expected = float(printed)
        tolerance = float(Decimal(10) ** Decimal(printed).as_tuple().exponent / 2)
        checks.append(dict(label=label,printed=printed,actual=float(actual),
            source=source,selector=selector,display_rounding_tolerance=tolerance,
            display_tolerance_reason='Half one unit of the last printed decimal place; this tests publication rounding, not experiment reproducibility.',
            passed=abs(float(actual)-expected) <= tolerance))

    release = refs['controlled_release']+'/evaluation_metrics.csv'
    e = pd.read_csv(ROOT/release).set_index('policy')
    for metric, values in [('loss_es95',['3327.95','3326.05','6242.90']),
                            ('mean_financed_cost',['487.97','545.69','336.13'])]:
        for policy, printed in zip(['maturity_band_050','daily','weekly'],values):
            add(f'{policy} {metric}',printed,e.loc[policy,metric],release,f'policy={policy}; column={metric}')
    add('Selected cost upper endpoint','490.18',e.loc['maturity_band_050','cost_mean_upper'],release,'policy=maturity_band_050; column=cost_mean_upper')
    add('Selected weekly ES improvement','2914.96',e.loc['weekly','loss_es95']-e.loc['maturity_band_050','loss_es95'],release,'weekly ES minus selected ES')
    add('Weekly ES improvement percent','46.7',100*(1-e.loc['maturity_band_050','loss_es95']/e.loc['weekly','loss_es95']),release,'100*(1-selected_ES/weekly_ES)')
    add('Daily financed-cost reduction percent','10.6',100*(1-e.loc['maturity_band_050','mean_financed_cost']/e.loc['daily','mean_financed_cost']),release,'100*(1-selected_cost/daily_cost)')
    path = refs['controlled_release']+'/paired_tail_differences.csv'
    paired = pd.read_csv(ROOT/path).set_index('benchmark')
    for benchmark,values in [('daily',['1.90','-31.61','33.56']),('weekly',['-2914.96','-3100.69','-2710.43'])]:
        for metric,printed in zip(['estimate','lower','upper'],values):
            add(f'Selected minus {benchmark} {metric}',printed,paired.loc[benchmark,metric],path,f'benchmark={benchmark}; column={metric}')
    path = refs['incremental_features']+'/paired_loss_differences.csv'
    f = pd.read_csv(ROOT/path)
    for cohort,horizon,values in [('sec_ten_generic',5,['-0.00660','-0.01095','-0.00279']),
        ('sec_ten_generic',20,['0.00648','0.00167','0.01101']),
        ('bank_six_deposits',5,['0.01501','0.00056','0.03266']),
        ('bank_six_deposits',20,['0.06993','0.02808','0.12480'])]:
        row=f.loc[(f.cohort==cohort)&(f.horizon==horizon)&(f.split=='test')&(f.metric=='qlike')&(f.left_model=='ridge_balance_sheet')&(f.reference=='ridge_market_sector')].iloc[0]
        for metric,printed in zip(['estimate','lower','upper'],values):
            add(f'{cohort}, {horizon}-session QLIKE {metric}',printed,row[metric],path,f'test, QLIKE, balance_sheet minus market_sector; {cohort}; horizon={horizon}; {metric}')
    path = refs['equity_overlays']+'/summary.csv'
    s = pd.read_csv(ROOT/path)
    test = s.loc[s.split=='test'].set_index('label')
    rows = [('unhedged',['6.280','1.644','100.0']),('reduced_75',['4.458','1.484','78.7']),
        ('etf_h100',['5.232','-0.086','25.1']),('long_put_k90_b2',['5.700','1.451','93.4']),
        ('short_call_k110_b1',['6.516','1.738','105.0']),('sector_put_k95_b2',['6.058','1.399','93.5']),
        ('collar_95_110_b2',['2.906','-0.033','13.2']),('risk_k90_t125',['5.990','1.532','96.3'])]
    for label,values in rows:
        for metric,printed in zip(['es_loss_pct','mean_pnl_pct','upside_retained'],values):
            add(f'{label} {metric}',printed,test.loc[label,metric]*(100 if metric=='upside_retained' else 1),path,f'split=test; label={label}; column={metric}'+('; multiply by 100' if metric=='upside_retained' else ''))
    for label,printed in [('long_put_k90_b2','1.304'),('short_call_k110_b1','2.599'),('sector_put_k95_b2','1.269'),('collar_95_110_b2','4.125'),('risk_k90_t125','1.303')]:
        add(f'{label} worst premium/allowance',printed,test.loc[label,'worst_window_budget_multiple'],path,f'test, {label}, worst_window_budget_multiple')
    for label,printed in [('unhedged','50.401'),('collar_95_110_b2','-5.385')]:
        add(f'{label} local dollar delta percent',printed,test.loc[label,'mean_delta_adjusted_net_pct'],path,f'test, {label}, mean_delta_adjusted_net_pct')
    collar=s.loc[(s.split=='validation')&(s.label=='collar_95_110_b2')].iloc[0]
    add('Validation collar worst premium/allowance','6.517',collar.worst_window_budget_multiple,path,'validation, collar_95_110_b2, worst_window_budget_multiple')
    for metric,printed in [('annual_premium_paid_pct','11.532'),('annual_premium_received_pct','11.387'),('annual_net_premium_pct','0.145')]:
        add('Test collar '+metric,printed,test.loc['collar_95_110_b2',metric],path,'test, collar_95_110_b2, '+metric)
    path = refs['equity_overlays']+'/windows.csv'
    w=pd.read_csv(ROOT/path)
    u=w.loc[(w.split=='test')&(w.label=='unhedged')].set_index('key')
    add('Minimum test inception gross percent','126.644',u.gross_exposure_pct.min(),path,'test unhedged minimum gross_exposure_pct')
    add('Maximum test inception gross percent','140.634',u.gross_exposure_pct.max(),path,'test unhedged maximum gross_exposure_pct')
    short=w.loc[(w.split=='test')&(w.label=='short_call_k110_b1')].set_index('key')
    losing=u.loc[u.short_equity_pnl<0].index
    base=u.loc[losing,'short_equity_pnl'].sum()
    option=short.loc[losing,'option_pnl'].sum()
    financing=(short.loc[losing,'interest']-u.loc[losing,'interest']).sum()
    add('Original short-sleeve capture','0.946109',(base+option)/base,path,'short-equity-loss windows; (base short PNL + call PNL)/base short PNL')
    add('Financing-inclusive short-sleeve capture','0.946695',(base+option+financing)/base,path,'same windows; include marginal call-premium financing')
    for split,label,printed in [('test','long_put_k90_b2','0.927'),('test','risk_k90_t125','0.911'),('test','sector_put_k95_b2','0.932'),('test','short_call_k110_b1','1.131'),('test','collar_95_110_b2','0.072'),('validation','collar_95_110_b2','1.166')]:
        group=w.loc[(w.split==split)&(w.label==label)]
        add(f'{split} {label} whole-split spend/allowance',printed,(group.premium_paid.sum()-group.premium_received.sum())/group.window_budget.sum(),path,f'{split}, {label}; sum(net premium)/sum(window_budget)')
    path=refs['conditional_breadth']+'/policy_summary.csv'
    b=pd.read_csv(ROOT/path)
    for breadth,printed in [(25,'4521.13'),(40,'4640.84')]:
        row=b.loc[(b.scenario=='calibrated_dependence')&(b.composition=='canonical')&(b.breadth==breadth)&(b.policy=='maturity_band_050')].iloc[0]
        add(f'Canonical {breadth}-name ES95',printed,row.loss_es95,path,f'calibrated_dependence, canonical, breadth={breadth}, maturity_band_050')
    path='results/research-release-2/astra-review-20261106/statistical_review/paired_es_diagnostics.csv'
    paired=pd.read_csv(ROOT/path)
    for label,printed in [('long_put_k90_b2','1.241'),('sector_put_k95_b2','1.599'),('risk_k90_t125','1.531'),('collar_95_110_b2','-1.552')]:
        row=paired.loc[(paired.policy==label)&(paired.reference=='reduced_75')&(paired.block_windows==4)].iloc[0]
        add(f'{label} post-hoc tail difference versus reduced equity',printed,row.estimate,path,f'{label}, reduced_75, block_windows=4')
        if label=='collar_95_110_b2':
            for metric,printed in [('lower','-3.034'),('upper','0.773')]:
                add('Collar versus reduced equity '+metric,printed,row[metric],path,'collar_95_110_b2, reduced_75, block_windows=4, '+metric)
    return checks


def acquisition_entries(manifest):
    mappings = {
        'audit_market_data': ['results/data-audit','data/market/prices_split_adjusted.csv','data/market/prices_metadata.json','data/market/data_gate_status.json'],
        'fetch_core_prices': ['data/market/prices_core_10.csv','data/market/prices_benchmarks.csv','data/market/core_10_metadata.json','data/market/core_10_coverage.csv','data/market/issuer_symbol_mappings.json'],
        'audit_reference_data': ['data/market/financial_universe_current.json','data/market/financial_universe_current.csv','data/market/reference_audit.json','data/market/delisted_sample.csv','data/market/delisted_sample.json'],
        'fetch_financial_universe': ['data/market/financial_50_universe.csv','data/market/financial_50_metadata.json','data/market/financial_50_coverage.csv','data/market/financial_50_eligibility_audit.csv','data/market/prices_financial_50_unbalanced.csv','data/market/prices_financial_50_availability.csv'],
        'audit_research_features': ['results/feature-audit','data/market/features'],
        'extend_sec_core10': ['data/market/features/sec_facts_core10'],
    }
    existing_names = {e['name'] for e in manifest['experiments']}
    for name, locations in mappings.items():
        if name in existing_names:
            continue
        hashes = {}
        missing = []
        for location in locations:
            path = ROOT/location
            if not path.exists():
                missing.append(location)
                continue
            for p in [path] if path.is_file() else sorted(path.rglob('*')):
                if p.is_file() and '__pycache__' not in p.parts:
                    hashes[str(p.relative_to(ROOT))] = digest(p)
        manifest['experiments'].append(dict(name=name, entry_kind='data_acquisition_not_economic_experiment',
            command=f'.venv/bin/python scripts/{name}.py'+(' --export-prices' if name=='audit_market_data' else ''),
            git_sha=manifest['frozen_git_sha'],environment_file_hash=manifest['environment_sha256'],
            seeds={}, publication_numbers_ref='#/publication_numbers', status='hash-only',
            reason='Frozen vendor/SEC historical snapshot cannot be regenerated from present live endpoints without possibly revised data, new retrieval metadata and credentials/entitlements. Existing saved inputs were used unchanged. No live refresh was attempted.',
            output_locations=locations,saved_outputs_sha256=hashes,missing_saved_locations=missing,
            approximate_runtime='network-dependent; not measured in Phase 0'))


def historical_inventory(manifest):
    before=json.loads((BASE/'tracked_files_before.json').read_text())
    folders=set('/'.join(name.split('/')[:2]) for name in before if name.startswith('results/'))
    folders.discard('results/research-release-1')
    folders.discard('results/research-release-2')
    for container in ['results/research-release-1','results/research-release-2']:
        folders.update('/'.join(name.split('/')[:3]) for name in before if name.startswith(container+'/'))
    covered={}
    for entry in manifest['experiments']:
        if entry.get('reference') and entry.get('table_comparison',{}).get('passed'):
            covered.setdefault(entry['reference'],[]).append(entry['name'])
    inventory=[]
    for folder in sorted(folders):
        hashes={name:sha for name,sha in before.items() if name.startswith(folder+'/')}
        sources={}
        for name in ['protocol.json','manifest.json','run_record.json']:
            path=ROOT/folder/name
            if path.is_file():
                sources.update(json.loads(path.read_text()).get('source_sha256',{}))
        checks=[]
        for name,expected in sources.items():
            path=Path(name)
            if not path.is_absolute():path=ROOT/path
            actual=digest(path) if path.is_file() else None
            checks.append(dict(path=name,recorded=expected,current=actual,passed=actual==expected))
        row=dict(directory=folder,files_sha256=hashes,recorded_source_checks=checks,
            tables=sum(name.endswith('.csv') for name in hashes),
            historical_command='Not recorded as a shell command; do not infer one from a directory timestamp.')
        candidate=None
        if folder.startswith('results/research-release-1/'):
            candidate='controlled_release'
        elif folder.startswith('results/breadth-'):
            candidate='conditional_breadth'
        elif folder.startswith('results/equity-overlays-') and 'review' not in folder:
            candidate='equity_overlays'
        elif folder.startswith('results/feature-research'):
            protocol_path=ROOT/folder/'protocol.json'
            if protocol_path.is_file():
                candidate='incremental_features' if json.loads(protocol_path.read_text()).get('SEC_core10_extension') else 'incremental_features_original'
        matching_alias=False
        if candidate:
            destination=ROOT/'results/pre_refactor/experiments_accelerate_pinned'/candidate
            tables=[name for name in hashes if name.endswith('.csv')]
            matching_alias=bool(tables) and all((destination/Path(name).relative_to(folder)).is_file() and digest(destination/Path(name).relative_to(folder))==hashes[name] for name in tables)
        if folder in covered:
            row.update(status='reproduced',covered_by=covered[folder],reason='All saved CSV output cells match the recorded fresh replay; any historical source-version difference is separately retained below.')
        elif matching_alias:
            row.update(status='covered_by_current_entrypoint',covered_by=[candidate+'_accelerate_pinned'],reason='Every saved CSV is byte-identical to the recorded fresh final-source replay; original metadata/source identities are preserved separately. No separate historical shell command is asserted.')
        elif 'risk-research-notebook' in folder:
            row.update(status='covered_by_current_entrypoint',covered_by=['price_risk_accelerate_pinned','notebook_06_market_risk_models'],reason='Historical notebook wrapper of the price-risk entry point; its original outputs are retained by exact hashes.')
        elif 'feature-research-notebook-20261106T024305' in folder:
            row.update(status='covered_by_current_entrypoint',covered_by=['incremental_features_accelerate_pinned','notebook_09_release_aware_features'],reason='Historical wrapper of the final SEC-core10 feature entry point; saved outputs are retained by exact hashes.')
        elif any(part in folder for part in ['astra-review','opus-review','equity-overlays-review','research-release-2/release-2']):
            row.update(status='archived_alias',reason='Reviewer or publication evidence already inventoried and hash-checked; not an additional economic experiment.')
        elif folder in ['results/data-audit','results/feature-audit']:
            row.update(status='hash-only',reason='Saved acquisition snapshot; live refresh explicitly not attempted (see acquisition command entries).')
        else:
            mismatch=any(not check['passed'] for check in checks)
            row.update(status='hash-only',reason='Earlier development run: recorded source SHA differs from the available frozen implementation; that historical source version is not separately supplied, so rerunning it exactly would require reconstructing/changing code. Saved products are hashed, never replaced.' if mismatch else 'Earlier/incomplete development snapshot without a complete matching source-and-completion record. No separate historical shell command or source version can be verified; saved products are hashed, never replaced.')
        inventory.append(row)
    return inventory


def report(manifest, comparisons):
    canonical=[c for c in comparisons if c['experiment'].endswith('_accelerate_pinned')]
    counts=manifest['execution_counts']
    json_results=json.loads((BASE/'json_comparisons.json').read_text())
    lines=['# Phase 0 freeze report', '',
        'Phase 0 is complete with the findings below. **Phase 1 has not started and requires owner confirmation.** No research implementation, assumptions, seed, window, split, policy or original finding document was changed.', '',
        'The research conclusion remains: **Incremental economic hedge value remains unestablished.**', '',
        '## Checkpoint and changes', '',
        '- Original research commit: `71c0be1`.',
        '- Notes-only commit: `cd1356e` — `docs: convert next-steps notes to markdown`. Both RTF files were extracted with macOS `textutil`; each Markdown file was compared byte-for-byte with a second extraction before the RTF was removed. No other file was in that commit.',
        '- Environment-only commit / immutable tag: `a96d99210ea16ac2dd33f46623aaf96cbc563196` — `chore: capture pre-refactor Python environment`.',
        '- `pre-refactor` was created once and pushed, along with main, to `https://github.com/sai-reddivari/financial-sector-hedging.git`. The audit checks the local and remote tag again.',
        f'- Frozen environment SHA-256: `{manifest["environment_sha256"]}`. Python 3.14.8, macOS 26.6 arm64, 57 pinned distributions; no installations/upgrades.',
        '- New audit products: `docs/EXPERIMENTS.md`, this report, `env/manifest_runtime_environment.json`, `scripts/freeze_phase0.py`, `scripts/audit_phase0.py`, `results/manifest_pre_refactor.json`, and preserved logs/outputs under `results/pre_refactor/`.',
        '- Two notebook-generated timestamped result directories remain at their original fresh destinations under `results/`; their complete products are hashed by the manifest. Original notebooks were also copied byte-for-byte into `results/pre_refactor/notebooks/as_committed/` before fresh-kernel attempts.', '',
        'The initially combined push command was rejected by automatic approval review on authorization grounds. The explicit attached instruction to “Push main and the tag to origin” was then verified, and the exact non-force push succeeded. No approval remains blocked.', '',
        'Actual successful push output:', '', '```text',
        'To https://github.com/sai-reddivari/financial-sector-hedging.git',
        '   71c0be1..a96d992  main -> main',
        ' * [new tag]         pre-refactor -> pre-refactor', '```', '',
        '## Executed commands and results', '',
        'All commands used the captured `.venv`. The first full canonical pass set OMP/MKL/OpenBLAS thread counts to one. Inspection identified Apple Accelerate; the second full canonical pass and all subsequent commands additionally set `VECLIB_MAXIMUM_THREADS=1`. Both passes are retained. `PYTHONHASHSEED=0` is fixed for all runs. No research seed changed.', '',
        'The commands actually executed are listed verbatim in each manifest entry; each log contains complete stdout/stderr, including failures. `scripts/freeze_phase0.py` was invoked in this order: `initialize`, `canonical`, `canonical-pinned`, `notebooks`, `reviewers`, `ancillary`. Publication utilities execute their original code in disposable `git archive pre-refactor` workspaces so their fixed report destinations cannot replace frozen evidence.', '',
        '| Entry | Status | Exit | Measured seconds | Log |','|---|---|---:|---:|---|']
    for e in manifest['experiments']:
        elapsed=f'{e["elapsed_seconds"]:.3f}' if 'elapsed_seconds' in e else 'not run'
        log=f'[`{Path(e["log"]).name}`](../{e["log"]})' if e.get('log') else 'saved products hashed'
        lines.append(f'| `{e["name"]}` | {e["status"]} | {e.get("exit_code", "—")} | {elapsed} | {log} |')
    lines += ['',f'Total measured child-command time: {manifest["elapsed_experiment_seconds"]:.3f} seconds (not total human/audit wall time). Status counts: `{json.dumps(counts,sort_keys=True)}`. Packaging exit 1 is the explicitly expected overwrite refusal, not a successful new packaging operation.', '',
        '## Frozen evidence and numerical comparisons', '',
        f'- Findings-bundle and nested evidence identity checks: **{manifest["evidence_cross_check"]["checks"]} checked; {len(manifest["evidence_cross_check"]["mismatches"])} mismatches**. Both the findings-folder copies and original result archives are checked.',
        f'- Fully Accelerate-pinned canonical pass: **{len(canonical)} CSV tables; {sum(c["numeric_cells"] for c in canonical):,} numeric cells; {sum(not c["passed"] for c in canonical)} differing tables; {sum(c["byte_equal"] for c in canonical)} byte-identical tables**.',
        f'- All comparisons, including the initial pass and reviewer outputs: **{len(comparisons)} tables; {sum(c["numeric_cells"] for c in comparisons):,} numeric cells; {sum(not c["passed"] for c in comparisons)} differing tables**.',
        f'- JSON comparisons: **{len(json_results)} files; {sum(c["numeric_cells"] for c in json_results):,} numeric values; {sum(len(c["numeric_mismatches"]) for c in json_results)} numerical mismatches**. Added provenance keys, timestamps/hash strings, one observational runtime and a supplemental notebook-execution record not produced by the economic CLI are listed explicitly in `json_comparisons.json`.',
        f'- Original tracked identities checked after execution: **{len(json.loads((BASE/"tracked_files_before.json").read_text()))}; {len(manifest["original_tracked_file_changes"])} changed**.',
        f'- Publication inventory: **{len(manifest["publication_numbers"])} numeric literal occurrences** plus **{len(manifest["publication_number_words"])} number-word occurrences**, retaining exact text and source locations. This includes dates and link identifiers. Numerical contracts retain full-precision saved summary/window-table values, not just rounded prose.',
        f'- Economic publication display checks: **{manifest["publication_numeric_checks"]["count"]}; {len(manifest["publication_numeric_checks"]["mismatches"])} discrepancies**. Their per-number display precision is recorded separately from deterministic replay tolerance.', '',
        'CSV comparisons check every cell and preserve row/column order, text and missingness. Deterministic relative tolerance is `1e-9`, absolute tolerance zero. No tolerance was relaxed to hide a mismatch. Full output-file hashes, including timestamp-sensitive protocol/report/JSON hashes, remain in the manifest. Timing and metadata differences do not imply an economic result changed.', '',
        'Full-precision reproduced controlled results:', '',
        '| Policy | ES95 dollars | Mean financed stock cost dollars |','|---|---:|---:|']
    e=pd.read_csv(ROOT/'results/pre_refactor/experiments_accelerate_pinned/controlled_release/evaluation_metrics.csv').set_index('policy')
    for name in ['maturity_band_050','daily','weekly']:
        lines.append(f'| {name} | {e.loc[name,"loss_es95"]:.12f} | {e.loc[name,"mean_financed_cost"]:.12f} |')
    lines += ['', 'The selected-minus-weekly ES95 estimate remains `-2914.958895237145`, paired interval `[-3100.6926138820118, -2710.425377174788]`; selected-minus-daily remains `1.898743772447233`, interval `[-31.61428212326467, 33.56382311508891]`. These do not establish incremental historical economic hedge value.', '',
        '## Findings and explicit limits', '']
    for finding in manifest['findings']:
        if finding['kind']=='publication_display_discrepancy':
            lines += [f'- **Existing publication rounding discrepancy:** `{finding["label"]}` prints `{finding["printed"]}`, while the unchanged frozen CSV and both replays give `{finding["actual"]}`. Direct rounding to cents is `3327.94`; the printed `3327.95` is outside its half-cent rounding interval. The original three-decimal report prints `3327.945`, so double rounding is a possible explanation, not an established correction. Both values are recorded; no document or result was edited.']
        elif finding['kind']=='command_failed':
            path=ROOT/finding['log']
            tail=re.sub(r'\x1b\[[0-9;]*m','','; '.join(path.read_text().splitlines()[-3:]))
            lines += [f'- **`{finding["name"]}` failed as saved:** {tail}. Full log: `{finding["log"]}`. No repair was attempted in Phase 0.']
        elif finding['kind']=='historical_source_version_unavailable':
            lines += [f'- **Historical source unavailable: `{finding["directory"]}`.** {finding["reason"]} The manifest lists {len(finding["mismatches"])} recorded source-hash differences; original artifacts were not modified.']
        elif finding['kind']=='json_reproduction_difference':
            lines += [f'- **JSON structure/provenance difference (`{finding["experiment"]}`, `{finding["file"]}`):** {len(finding["numeric_mismatches"])} numeric mismatches, {len(finding["boolean_differences"])} boolean differences, {len(finding["structure_differences"])} structural differences. '+('The supplemental `notebook_execution.json` was not generated by the economic CLI; notebook 07 was executed separately and its fresh copy/log are retained.' if finding['file'].endswith('notebook_execution.json') else 'The current frozen source records additional module/input provenance that was absent when the historical run was saved. Added keys and raw string changes are retained in the JSON comparison report. No saved metadata was altered.')]
        else:
            lines += ['- **Recorded discrepancy:** `'+json.dumps(finding,ensure_ascii=False)+'`.']
    lines += ['',
        'Six acquisition utilities are explicitly `hash-only`: frozen historical vendor/SEC snapshots cannot be recreated by a present live refresh without possible revisions, new retrieval metadata, credentials and entitlements. No refresh was attempted and no credentials were copied to evidence. The complete saved products are hashed, and the economic runs consume them unchanged. This does not verify raw-provider accuracy or recover unavailable historical option quotes or membership vintages.', '',
        'Earlier development result directories are inventoried individually in `historical_saved_runs`, including incomplete attempts and recorded source hashes that differ from the available final source. Those unavailable historical source versions were not reconstructed or rerun. Their saved products remain byte-identical. This limitation is separate from the seven canonical publication families, which were fully replayed. Original three-name price-risk outputs were also reproduced byte-for-byte despite their older runner hash.', '',
        'Original investigation wall-clock timings and plot/notebook metadata are not deterministic quantities. Their saved artifacts and fresh attempts are preserved. The manifest distinguishes successful fresh-kernel execution, partial failures, timeout/hash-only entries and read-only notebook views. No fresh environment/clean-clone reproduction, package restructuring, methodology improvement, new tests, license choice or Phase 1 implementation is claimed.', '',
        '## Existing test suite: actual output', '',
        'Command: `.venv/bin/python -m pytest -q --junitxml=results/pre_refactor/tests.xml` with the fully pinned runtime controls above.', '', '```text',
        (BASE/'logs/existing_test_suite.txt').read_text().rstrip(), '```', '',
        '## Audit command output', '', '```text',
        json.dumps(dict(status=manifest['status'],execution_counts=manifest['execution_counts'],
            evidence_checks=manifest['evidence_cross_check']['checks'],evidence_mismatches=len(manifest['evidence_cross_check']['mismatches']),
            tables_compared=len(comparisons),tables_with_differences=sum(not c['passed'] for c in comparisons),
            numeric_cells_compared=sum(c['numeric_cells'] for c in comparisons),original_tracked_file_changes=len(manifest['original_tracked_file_changes'])),indent=2),
        '```', '', 'The Phase 0 boundary is the stopping point. The owner must confirm before `refactor/publication` is created or Phase 1 begins.', '']
    (ROOT/'docs/PHASE0_REPORT.md').write_text('\n'.join(lines))
    path=ROOT/'docs/EXPERIMENTS.md'
    marker='\n## Historical saved-run coverage (completed audit)\n'
    text=path.read_text().split(marker)[0].rstrip()+marker+'\nEvery originally tracked result directory is accounted for below. `covered_by_current_entrypoint` means all saved CSVs are byte-identical to a fresh replay, or the explicitly identified notebook wrapper of that runner. Hash-only development snapshots have missing historical source/completion evidence; they are not silently counted as executed. Full file hashes, source mismatches and reasons are in `historical_saved_runs` in the manifest.\n\n| Saved directory | Coverage | Recorded source mismatches | Reason |\n|---|---|---:|---|\n'
    for row in manifest['historical_saved_runs']:
        text+=f'| `{row["directory"]}` | {row["status"]} | {sum(not c["passed"] for c in row["recorded_source_checks"])} | {row["reason"]} |\n'
    path.write_text(text)


def main():
    manifest = json.loads(MANIFEST.read_text())
    if any(e['status'] == 'running' for e in manifest['experiments']):
        raise RuntimeError('An experiment is still running; do not finalize concurrently')
    acquisition_entries(manifest)
    checks = evidence_checks()
    dump(BASE/'evidence_checks.json',checks)
    manifest['evidence_cross_check'] = dict(report='results/pre_refactor/evidence_checks.json',
        report_sha256=digest(BASE/'evidence_checks.json'),checks=len(checks),
        mismatches=[c for c in checks if not c['passed']])
    all_comparisons = []
    json_comparisons=[]
    for entry in manifest['experiments']:
        if entry['name'] in ['notebook_06_market_risk_models','notebook_09_release_aware_features']:
            key='price_risk' if entry['name'].startswith('notebook_06') else 'incremental_features'
            entry['reference']=manifest['canonical_runs'][key]
            entry['table_output']=next((p for p in entry['output_locations'] if (ROOT/p).is_dir()),None)
        reference = entry.get('reference')
        if entry['name'] in ['owner_checks','owner_window_check']:
            filename='owner_checks_output.txt' if entry['name']=='owner_checks' else 'window_placement_output.txt'
            saved=ROOT/'results/research-release-2/opus-review-20261106/owner_checks'/filename
            entry['stdout_comparison']=dict(saved=str(saved.relative_to(ROOT)),saved_sha256=digest(saved),
                fresh_sha256=digest(ROOT/entry['log']),byte_equal=digest(saved)==digest(ROOT/entry['log']))
        entry['input_sha256']={name:digest(ROOT/name) for name in entry.get('inputs',[]) if (ROOT/name).is_file()}
        entry.setdefault('expected_exit_code',0)
        if not reference:
            continue
        folder = ROOT/reference
        entry['numeric_contracts'] = contracts(folder)
        if entry['name'].startswith('equity_overlays_freeze') or entry['name'] in ['owner_checks','owner_window_check']:
            continue
        destination = ROOT/(entry.get('table_output') or entry['output_locations'][0])
        comparisons = [csv_comparison(p,destination/p.relative_to(folder)) for p in sorted(folder.rglob('*.csv'))]
        entry['table_comparison'] = dict(tables=len(comparisons),
            numeric_cells=sum(c['numeric_cells'] for c in comparisons),
            passed=all(c['passed'] for c in comparisons),
            byte_equal_tables=sum(c['byte_equal'] for c in comparisons),
            numeric_mismatches=sum(c['numeric_mismatches'] for c in comparisons),
            text_mismatches=sum(c['text_mismatches'] for c in comparisons))
        all_comparisons.extend(dict(experiment=entry['name'],**c) for c in comparisons)
        json_results=[json_comparison(p,destination/p.relative_to(folder)) for p in sorted(folder.rglob('*.json'))]
        entry['json_comparison']=dict(files=len(json_results),numeric_cells=sum(c['numeric_cells'] for c in json_results),
            numeric_mismatches=sum(len(c['numeric_mismatches']) for c in json_results),
            structure_differences=sum(len(c['structure_differences']) for c in json_results),
            boolean_differences=sum(len(c['boolean_differences']) for c in json_results),
            observed_timing_differences=sum(len(c['observed_timing_differences']) for c in json_results),
            string_differences=sum(len(c['string_differences']) for c in json_results))
        json_comparisons.extend(dict(experiment=entry['name'],**c) for c in json_results)
    dump(BASE/'table_comparisons.json',all_comparisons)
    manifest['table_comparison_report'] = 'results/pre_refactor/table_comparisons.json'
    dump(BASE/'json_comparisons.json',json_comparisons)
    manifest['json_comparison_report']='results/pre_refactor/json_comparisons.json'
    manifest['publication_number_words'] = word_numbers()
    manifest['historical_saved_runs']=historical_inventory(manifest)
    rounded_checks=publication_checks()
    dump(BASE/'publication_numeric_checks.json',rounded_checks)
    manifest['publication_numeric_checks'] = dict(report='results/pre_refactor/publication_numeric_checks.json',
        count=len(rounded_checks),mismatches=[c for c in rounded_checks if not c['passed']],
        scope='Selected published economic table values, intervals, exposure/budget diagnostics and derived comparisons. Full literal/number-word inventories are separate; this is not a claim to independently validate every prose statement.')
    manifest['seed_inventory'] = dict(path='results/pre_refactor/seed_inventory.json',sha256=digest(BASE/'seed_inventory.json'))
    before = json.loads((BASE/'tracked_files_before.json').read_text())
    changed = []
    for name, expected in before.items():
        actual = digest(ROOT/name) if (ROOT/name).is_file() else None
        if actual != expected:
            changed.append(dict(path=name,before=expected,after=actual))
    manifest['original_tracked_file_changes'] = changed
    manifest['tag_verification'] = dict(
        local=subprocess.check_output(['git','rev-parse','pre-refactor'],cwd=ROOT,text=True).strip(),
        origin=subprocess.check_output(['git','ls-remote','origin','refs/tags/pre-refactor'],cwd=ROOT,text=True).strip())
    tag=manifest['tag_verification']
    tag['passed']=tag['local']==manifest['frozen_git_sha'] and bool(tag['origin']) and tag['origin'].split()[0]==manifest['frozen_git_sha']
    freeze=subprocess.check_output([str(ROOT/'.venv/bin/python'),'-m','pip','freeze','--all'],cwd=ROOT,text=True)
    expected='\n'.join(line for line in (ROOT/'env/frozen_environment.txt').read_text().splitlines() if not line.startswith('#'))+'\n'
    manifest['frozen_packages_unchanged'] = freeze == expected
    manifest['findings'] = [dict(kind='evidence_hash_mismatch',**c) for c in checks if not c['passed']]
    manifest['findings'] += [dict(kind='table_reproduction_difference',**c) for c in all_comparisons if not c['passed']]
    manifest['findings'] += [dict(kind='json_reproduction_difference',**c) for c in json_comparisons if not c['passed']]
    manifest['findings'] += [dict(kind='command_failed',name=e['name'],reason=e.get('reason'),log=e.get('log')) for e in manifest['experiments'] if e['status']=='failed']
    manifest['findings'] += [dict(kind='publication_display_discrepancy',**c) for c in rounded_checks if not c['passed']]
    manifest['findings'] += [dict(kind='historical_source_version_unavailable',directory=r['directory'],reason=r['reason'],mismatches=[c for c in r['recorded_source_checks'] if not c['passed']]) for r in manifest['historical_saved_runs'] if r['status']=='hash-only' and any(not c['passed'] for c in r['recorded_source_checks'])]
    if changed:
        manifest['findings'].append(dict(kind='original_tracked_files_changed',files=changed))
    if not manifest['frozen_packages_unchanged']:
        manifest['findings'].append(dict(kind='environment_changed'))
    if not tag['passed']:
        manifest['findings'].append(dict(kind='tag_identity_mismatch',verification=tag))
    manifest['execution_counts'] = dict(Counter(e['status'] for e in manifest['experiments']))
    manifest['elapsed_experiment_seconds'] = sum(e.get('elapsed_seconds',0) for e in manifest['experiments'])
    manifest['status'] = 'phase0_complete_with_findings' if manifest['findings'] else 'phase0_complete'
    manifest['phase1_started'] = False
    dump(MANIFEST,manifest)
    report(manifest,all_comparisons)
    print(json.dumps(dict(status=manifest['status'], execution_counts=manifest['execution_counts'],
        evidence_checks=len(checks),evidence_mismatches=len(manifest['evidence_cross_check']['mismatches']),
        tables_compared=len(all_comparisons),tables_with_differences=sum(not c['passed'] for c in all_comparisons),
        numeric_cells_compared=sum(c['numeric_cells'] for c in all_comparisons),
        original_tracked_file_changes=len(changed),manifest_size_bytes=MANIFEST.stat().st_size),indent=2))


if __name__ == '__main__':
    main()

"""Offline publication reproduction from the immutable raw-input checkpoint."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tarfile
import time

ROOT = Path(__file__).resolve().parents[1]
CONTROLS = dict(OMP_NUM_THREADS='1', MKL_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1',
                VECLIB_MAXIMUM_THREADS='1', PYTHONHASHSEED='0', MPLBACKEND='Agg',
                MPLCONFIGDIR='/tmp/hedging-publication-mpl')


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False)+'\n')


def frozen_workspace(destination):
    """Materialize archived sources; never rewrite historical provenance."""
    before=json.loads((ROOT/'results/manifest_pre_refactor.json').read_text())
    expected=before['frozen_git_sha']
    actual=subprocess.check_output(['git','rev-parse','pre-refactor'],cwd=ROOT,text=True).strip()
    if actual!=expected:
        raise RuntimeError('Immutable pre-refactor tag identity changed')
    destination=Path(destination)
    destination.mkdir(parents=True,exist_ok=False)
    archive=subprocess.check_output(['git','archive','pre-refactor'],cwd=ROOT)
    with tarfile.open(fileobj=io.BytesIO(archive)) as stream:
        stream.extractall(destination,filter='data')
    return destination


def restore_inputs(frozen):
    """Restore missing input bytes from the tag; reject existing changed inputs."""
    import shutil
    for path in sorted((frozen/'data').rglob('*')):
        if not path.is_file():
            continue
        target=ROOT/path.relative_to(frozen)
        if target.exists():
            if sha(target)!=sha(path):
                raise RuntimeError(f'Input differs from frozen bytes: {target}')
        else:
            target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(path,target)


def run(command, log, timeout=1200):
    print('$ '+shlex.join(map(str,command)),flush=True)
    started=time.monotonic()
    with Path(log).open('w') as output:
        process=subprocess.run(list(map(str,command)),cwd=ROOT,env=dict(os.environ,**CONTROLS),
                               stdout=output,stderr=subprocess.STDOUT,timeout=timeout)
    if process.returncode:
        raise RuntimeError(f'Command exited {process.returncode}; see {log}')
    return time.monotonic()-started


def window_worker(frozen,destination):
    """Replay the archived diagnostic with current engine and disclosed path redirection."""
    # The archived checks validate the frozen source/input checkpoint. This
    # process imports the CURRENT engine; its actual hashes are recorded by
    # the enclosing post-refactor manifest, separately from historical hashes.
    from hedging_harness import overlays
    source=Path(frozen)/'results/research-release-2/astra-review-20261106/window_placement/run_diagnostic.py'
    destination=Path(destination).resolve();destination.mkdir(parents=True,exist_ok=False)
    text=source.read_text()
    original=Path(json.loads((ROOT/'results/manifest_pre_refactor.json').read_text())['python']).parents[2]
    text=text.replace(f"ROOT=Path({str(original)!r})",f"ROOT=Path({str(Path(frozen).resolve())!r})")
    text=text.replace("OUT=Path('/tmp/astra_window_phase_20261106')",f'OUT=Path({str(destination)!r})')
    exec(compile(text,str(source),'exec'),{'__file__':str(source),'__name__':'__main__'})


def reproduce(output, *, fast=False, notebooks=False, reviewers=False):
    os.environ.update(CONTROLS)
    output=Path(output).resolve()
    output.mkdir(parents=True,exist_ok=False)
    frozen=frozen_workspace(output/'frozen_source')
    restore_inputs(frozen)
    sys.path.insert(0,str(ROOT/'scripts'))
    from audit_phase0 import csv_comparison, contracts, json_comparison
    pre=json.loads((ROOT/'results/manifest_pre_refactor.json').read_text())
    refs=dict(pre['canonical_runs'])
    refs['price_risk_original_three']='results/risk-research-20261106T014645390937Z'
    tasks=[('controlled_release','run_research_release_1.py',[]),
           ('model_replay','run_model_contract_replay.py',[]),
           ('price_risk','run_risk_research.py',['--prices','data/market/prices_core_10.csv'])]
    if not fast:
        tasks += [('price_risk_original_three','run_risk_research.py',[]),
                  ('incremental_features_original','run_feature_research.py',[]),
                  ('incremental_features','run_feature_research.py',['--sec-core10']),
                  ('conditional_breadth','run_breadth_research.py',[])]
    manifest=dict(schema_version=2,phase=1,git_sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        frozen_git_sha=pre['frozen_git_sha'],environment_sha256=sha(ROOT/'env/frozen_environment.txt'),
        runtime_environment=CONTROLS,python=sys.version,experiments=[],status='running',
        publication_numbers=pre['publication_numbers'],publication_number_words=pre['publication_number_words'],
        full_precision_note='Numeric contracts use full-precision saved/generated values. Publication displays round; three display differences are recorded in docs/review/errata_post_freeze.md.',
        configuration_sha256={str(p.relative_to(ROOT)):sha(p) for p in sorted((ROOT/'config').rglob('*.json'))})
    manifest['source_sha256']={str(p.relative_to(ROOT)):sha(p) for folder in ['hedging_harness','market_data','scripts'] for p in sorted((ROOT/folder).rglob('*.py'))}
    from .study import export_input_tables
    export_input_tables(ROOT/'config/illustrative_study.json',output/'derived_study_inputs')
    tables=[]; json_checks=[]
    def execute(name,command,destination):
        log=output/(name+'.log')
        elapsed=run(command,log)
        ref=ROOT/refs[name]
        # Exact old result folders remain as historical targets; metadata is
        # compared separately from deterministic values, never rewritten.
        comparison=[csv_comparison(p,destination/p.relative_to(ref)) for p in sorted(ref.rglob('*.csv'))]
        extra=[json_comparison(p,destination/p.relative_to(ref)) for p in sorted(ref.rglob('*.json'))]
        record=dict(name=name,command=shlex.join(map(str,command)),seeds=next(e['seeds'] for e in pre['experiments'] if e['name']==name+'_accelerate_pinned'),
            elapsed_seconds=elapsed,reference=refs[name],output_directory=str(destination),
            numeric_contracts=contracts(destination),table_comparison=comparison,
            outputs_sha256={str(p.relative_to(destination)):sha(p) for p in sorted(destination.rglob('*')) if p.is_file()},
            log=str(log),log_sha256=sha(log))
        manifest['experiments'].append(record);tables.extend(comparison);json_checks.extend(extra)
        write(output/'manifest.json',manifest)
        failures=[c for c in comparison if not c['passed']]
        numeric_json=[c for c in extra if c['numeric_mismatches']]
        if failures or numeric_json:
            write(output/'numerical_failures.json',dict(tables=failures,json=numeric_json))
            raise RuntimeError('Numerical contract changed; stop. See numerical_failures.json')
        print(f'{name}: {len(comparison)} CSVs, {sum(c["numeric_cells"] for c in comparison)} numeric cells; differences=0; {elapsed:.3f}s',flush=True)
    for name,script,args in tasks:
        destination=output/name
        execute(name,[sys.executable,ROOT/'scripts'/script,*args,'--output-dir',destination],destination)
    if not fast:
        destination=output/'equity_overlays'
        run([sys.executable,ROOT/'scripts/run_overlay_research.py','freeze','--output-dir',destination],output/'equity_overlays_freeze.log')
        execute('equity_overlays',[sys.executable,ROOT/'scripts/run_overlay_research.py','evaluate','--run-dir',destination],destination)
    if notebooks:
        run([sys.executable,ROOT/'scripts/run_harness_notebooks.py','--output-dir',output/'notebooks'],output/'notebooks.log',timeout=1800)
        from .notebook_views import run_investigations
        run_investigations(output/'investigations')
    if reviewers:
        archive=frozen/'results/research-release-2/astra-review-20261106'
        run([sys.executable,archive/'accounting/astra_overlay_independent_portable.py','--repo',frozen,'--output-dir',output/'independent_accounting'],output/'independent_accounting.log')
        run([sys.executable,archive/'statistical_review/diagnostic.py','--repo',frozen,'--output-dir',output/'independent_statistics'],output/'independent_statistics.log')
        run([sys.executable,'-m','hedging_harness.reproduction','--window-worker',frozen,output/'window_placement'],output/'window_placement.log')
        references=[('accounting/verified_outputs','independent_accounting'),('statistical_review','independent_statistics'),('window_placement','window_placement')]
        review_checks=[]
        for relative,target in references:
            ref=ROOT/'results/research-release-2/astra-review-20261106'/relative
            review_checks.extend(csv_comparison(p,output/target/p.relative_to(ref)) for p in sorted(ref.glob('*.csv')))
        write(output/'review_comparisons.json',review_checks)
        if any(not c['passed'] for c in review_checks):
            raise RuntimeError('Reviewer numerical reproduction changed; stop')
        manifest['review_comparison']=dict(tables=len(review_checks),numeric_cells=sum(c['numeric_cells'] for c in review_checks),mismatches=0,
            historical_source_check='Independent scripts validate frozen source identities against the immutable checkpoint.',
            shifted_window_engine='CURRENT engine; archived diagnostic ROOT/OUT paths only redirected. Current source hashes recorded separately.')
    write(output/'json_comparisons.json',json_checks)
    manifest.update(status='passed',tables_compared=len(tables),numeric_cells_compared=sum(c['numeric_cells'] for c in tables),
        numeric_mismatches=0,byte_identical_tables=sum(c['byte_equal'] for c in tables),
        scope='fast_subset' if fast else 'all_eight_current_research_variants',
        metadata_differences='Raw timestamp, path, source and artifact hash changes are retained in json_comparisons.json; never treated as empirical values.')
    write(output/'manifest.json',manifest)
    if not fast:
        write(ROOT/'results/manifest_post_refactor.json',manifest)
    print(json.dumps({k:manifest[k] for k in ['status','scope','tables_compared','numeric_cells_compared','numeric_mismatches','byte_identical_tables']},indent=2),flush=True)
    return manifest


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path)
    parser.add_argument('--fast',action='store_true')
    parser.add_argument('--notebooks',action='store_true')
    parser.add_argument('--reviewers',action='store_true')
    parser.add_argument('--window-worker',nargs=2,metavar=('FROZEN','OUTPUT'))
    args=parser.parse_args()
    if args.window_worker:
        window_worker(*args.window_worker)
        return
    destination=args.output_dir or ROOT/'results/reproduction'/time.strftime('%Y%m%dT%H%M%S')
    reproduce(destination,fast=args.fast,notebooks=args.notebooks,reviewers=args.reviewers)


if __name__=='__main__':
    main()

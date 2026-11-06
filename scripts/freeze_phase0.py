"""Phase 0 evidence capture. Never edits research sources or frozen outputs.

Uses the existing .venv without installing packages. This is an audit runner,
not the Phase 1 reproduction interface. Commands, failures and hashes persist
after each child process. Run from the repository root.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'results/pre_refactor'
MANIFEST = ROOT / 'results/manifest_pre_refactor.json'
PYTHON = ROOT / '.venv/bin/python'
THREADS = dict(OMP_NUM_THREADS='1', MKL_NUM_THREADS='1', OPENBLAS_NUM_THREADS='1',
               VECLIB_MAXIMUM_THREADS='1', PYTHONHASHSEED='0', MPLBACKEND='Agg', MPLCONFIGDIR='/tmp/phase0-mpl')


def digest(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def dump(path, value):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def tracked():
    return subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT).decode().split('\0')[:-1]


def initialize():
    if MANIFEST.exists():
        raise FileExistsError('Refusing to overwrite an existing Phase 0 manifest')
    BASE.mkdir(parents=True, exist_ok=True)
    files = {name: digest(ROOT / name) for name in tracked()}
    dump(BASE / 'tracked_files_before.json', files)
    numeric_literals = []
    documents = ROOT / 'docs/Final Findings and Takeaways'
    for name in ('research_release_2_publication.md', 'research_release_2_claims_and_errata.md'):
        path = documents / name
        for line_no, line in enumerate(path.read_text().splitlines(), 1):
            # Intentionally inclusive: dates, identifiers, headings, URLs and
            # prose numbers are retained alongside economic measurements.
            for match in re.finditer(r'[+\-−]?\d[\d,]*(?:\.\d+)?(?:[eE][+\-]?\d+)?', line):
                literal = match.group()
                numeric_literals.append(dict(id=f'N{len(numeric_literals)+1:04d}',
                    document=str(path.relative_to(ROOT)), line=line_no,
                    column=match.start()+1, literal=literal,
                    decimal_text=literal.replace(',', '').replace('−', '-'), context=line))
    dump(BASE / 'publication_numbers.json', numeric_literals)
    config = json.loads((ROOT / 'config/research_release_2_package.json').read_text())
    existing = {}
    for name in tracked():
        if name.startswith(('results/', 'reports/', 'docs/Final Findings and Takeaways/')):
            existing[name] = files[name]
    manifest = dict(schema_version=1, phase=0, status='in_progress',
        frozen_git_sha=subprocess.check_output(['git', 'rev-parse', 'pre-refactor'], cwd=ROOT, text=True).strip(),
        environment_file='env/frozen_environment.txt',
        environment_sha256=digest(ROOT / 'env/frozen_environment.txt'),
        python=str(PYTHON), manifest_run_environment=THREADS,
        tolerance=dict(relative=1e-9, absolute=0, zero_rule='Exact equality; paired NaNs represent missingness, not measurements.'),
        canonical_runs=config['canonical_runs'],
        publication_numbers=numeric_literals,
        publication_numbers_note='Every numeric literal occurrence is retained with exact text and location; dates, link identifiers and historical audit residuals are not silently treated as independently re-estimated quantities. Number words are inventoried separately in the final evidence report.',
        saved_output_sha256=existing, experiments=[], findings=[],
        seed_changes=[], package_upgrades=[])
    dump(MANIFEST, manifest)
    print(f'Initialized {MANIFEST.relative_to(ROOT)}: {len(files)} tracked identities, {len(numeric_literals)} numeric literal occurrences', flush=True)


def record(name, command, outputs, *, seeds=None, inputs=None, reference=None, timeout=1200, expected_exit=0, note=None):
    manifest = json.loads(MANIFEST.read_text())
    if any(item['name'] == name for item in manifest['experiments']):
        raise ValueError(f'Already recorded: {name}')
    log = BASE / 'logs' / f'{name}.txt'
    log.parent.mkdir(parents=True, exist_ok=True)
    entry = dict(name=name, command=shlex.join(map(str, command)),
        git_sha=manifest['frozen_git_sha'], environment_file_hash=manifest['environment_sha256'],
        runtime_environment=dict(THREADS),
        seeds=seeds or {}, inputs=inputs or [], output_locations=outputs,
        reference=reference, publication_numbers_ref='#/publication_numbers',
        status='running', expected_exit_code=expected_exit, timeout_seconds=timeout, log=str(log.relative_to(ROOT)), note=note)
    manifest['experiments'].append(entry)
    dump(MANIFEST, manifest)
    env = dict(os.environ, **THREADS)
    before_result_dirs = set((ROOT/'results').iterdir())
    start = time.monotonic()
    print(f'START {name}: {entry["command"]}', flush=True)
    with log.open('w') as stream:
        process = subprocess.Popen(list(map(str, command)), cwd=ROOT, env=env,
                                   stdout=stream, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            code = process.wait(timeout=timeout)
            entry.update(exit_code=code, status='passed' if code == expected_exit else 'failed')
            if code != expected_exit:
                entry['reason'] = f'Command exited {code}; full exception/output retained in {entry["log"]}'
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGTERM)
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
            entry.update(status='hash-only', reason='Exceeded the 20-minute per-experiment Phase 0 limit; existing outputs retained and hashed.', exit_code=process.returncode)
    entry['elapsed_seconds'] = time.monotonic() - start
    entry['log_sha256'] = digest(log)
    # Two original notebooks create timestamped research directories themselves.
    # Keep those destinations verbatim and include every produced file.
    added_dirs = sorted(p for p in set((ROOT/'results').iterdir())-before_result_dirs if p.is_dir())
    for p in added_dirs:
        relative = str(p.relative_to(ROOT))
        if relative not in outputs:
            outputs.append(relative)
    entry['output_locations'] = outputs
    entry['outputs_sha256'] = {}
    for location in outputs:
        path = ROOT / location
        paths = [path] if path.is_file() else sorted(path.rglob('*')) if path.exists() else []
        for p in paths:
            if p.is_file() and '__pycache__' not in p.parts:
                entry['outputs_sha256'][str(p.relative_to(ROOT))] = digest(p)
    if reference:
        entry['saved_outputs_sha256'] = {str(p.relative_to(ROOT)): digest(p) for p in sorted((ROOT/reference).rglob('*')) if p.is_file() and '__pycache__' not in p.parts}
    dump(MANIFEST, manifest)
    print(f'END {name}: {entry["status"]}; exit={entry.get("exit_code")}; {entry["elapsed_seconds"]:.3f}s; {len(entry["outputs_sha256"])} output files', flush=True)


def canonical(repeat=False):
    config = json.loads((ROOT / 'config/research_release_2_package.json').read_text())
    refs = config['canonical_runs']
    tasks = [
        ('controlled_release', 'run_research_release_1.py', [], dict(selection=730201, evaluation=730202, bootstrap_base=730204), ['config/research_release_1.json', 'config/illustrative_study.json']),
        ('model_replay', 'run_model_contract_replay.py', [], {}, ['data/market/prices_split_adjusted.csv']),
        ('price_risk', 'run_risk_research.py', ['--prices', 'data/market/prices_core_10.csv'], dict(bootstrap_base=730501), ['data/market/prices_core_10.csv','data/market/prices_benchmarks.csv']),
        ('price_risk_original_three', 'run_risk_research.py', [], dict(bootstrap_base=730501), ['data/market/prices_split_adjusted.csv','data/market/prices_benchmarks.csv']),
        ('incremental_features_original', 'run_feature_research.py', [], dict(bootstrap_base=730501), ['data/market/prices_core_10.csv','data/market/features/sec_facts/sec_filing_snapshots.csv']),
        ('incremental_features', 'run_feature_research.py', ['--sec-core10'], dict(bootstrap_base=730501), ['data/market/prices_core_10.csv','data/market/features/sec_facts_core10/sec_filing_snapshots.csv']),
        ('conditional_breadth', 'run_breadth_research.py', [], dict(paths=730701, composition=[730711,730712], paired_bootstrap=730731, historical_bootstrap=730721), ['data/market/prices_financial_50_unbalanced.csv',refs['controlled_release']+'/selection.json']),
    ]
    for name, script, args, seeds, inputs in tasks:
        output = f'results/pre_refactor/{"experiments_accelerate_pinned" if repeat else "experiments"}/{name}'
        ref = refs.get(name, 'results/risk-research-20261106T014645390937Z')
        record(name+('_accelerate_pinned' if repeat else ''), [PYTHON, 'scripts/'+script, *args, '--output-dir', output], [output], seeds=seeds, inputs=inputs, reference=ref)
    output = f'results/pre_refactor/{"experiments_accelerate_pinned" if repeat else "experiments"}/equity_overlays'
    record('equity_overlays_freeze'+('_accelerate_pinned' if repeat else ''), [PYTHON,'scripts/run_overlay_research.py','freeze','--output-dir',output], [output], seeds=dict(bootstrap=730601), inputs=['config/equity_overlay_study.json'], reference=refs['equity_overlays'], note='Existing candidate grid and validation selection reproduced in a fresh directory; no tuning or new windows.')
    record('equity_overlays'+('_accelerate_pinned' if repeat else ''), [PYTHON,'scripts/run_overlay_research.py','evaluate','--run-dir',output], [output], seeds=dict(bootstrap=730601), inputs=[output+'/protocol.json'], reference=refs['equity_overlays'], note='First evaluation of the fresh replication; original frozen evaluation log is untouched.')


def notebook_worker(source, destination):
    import nbformat
    from nbclient import NotebookClient
    from jupyter_client import KernelManager
    import tempfile
    source, destination = ROOT/source, ROOT/destination
    destination.parent.mkdir(parents=True, exist_ok=True)
    nb = nbformat.read(source, as_version=4)
    # Same transport and interpreter as the repository's notebook runner.
    with tempfile.TemporaryDirectory(prefix='phase0-kernel-', dir='/tmp') as runtime:
        runtime = Path(runtime)
        env = dict(os.environ, IPYTHONDIR=str(runtime/'ipython'), JUPYTER_RUNTIME_DIR=str(runtime),
                   MPLBACKEND='module://matplotlib_inline.backend_inline')
        km = KernelManager(kernel_name='python3', transport='ipc', connection_file=str(runtime/'k.json'))
        km.kernel_spec.argv = [str(PYTHON), '-m', 'ipykernel_launcher', '-f', '{connection_file}']
        client = NotebookClient(nb, timeout=1200, kernel_name='python3', km=km,
                                resources={'metadata': {'path': str(ROOT)}})
        try:
            client.execute(env=env)
        finally:
            if km.has_kernel:
                km.shutdown_kernel(now=True)
            nbformat.write(nb, destination)


def notebooks():
    import shutil
    for source in sorted(ROOT.glob('*Notebooks/*.ipynb')):
        archived = BASE/'notebooks/as_committed'/source.parent.name/source.name
        archived.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, archived)
        assert digest(source) == digest(archived)
        output = 'results/pre_refactor/notebooks/'+source.name
        if source.parent.name.startswith('MonteCarlo'):
            seeds = dict(base=1995, note='Exact additional streams and offsets remain in the source notebook.') if 'ModelIntroduction' not in source.name else {}
        elif source.name.startswith(('00','01','02','03')):
            seeds = dict(simulation=20261105, **(dict(fresh_validation=20261106) if source.name.startswith('03') else {}))
        elif source.name.startswith('04'):
            seeds = dict(selection=730201,evaluation=730202,bootstrap_base=730204,mode='reads_existing')
        elif source.name.startswith(('06','09')):
            seeds = dict(bootstrap_base=730501,horizon_offset=[5,20],mse_additional_offset=100)
        elif source.name.startswith('07'):
            seeds = dict(bootstrap=730601,mode='reads_existing_and_two_window_checks')
        elif source.name.startswith('08'):
            seeds = dict(paths=730701,composition=[730711,730712],paired_bootstrap=730731,historical_bootstrap=730721,mode='reads_existing')
        else:
            seeds = {}
        record('notebook_'+source.stem, [PYTHON,'scripts/freeze_phase0.py','notebook-worker',str(source.relative_to(ROOT)),output], [output], seeds=seeds, inputs=[str(source.relative_to(ROOT))], note='Fresh kernel; source and existing stored outputs are unchanged. Timing measurements are observational, not deterministic numerical contracts.')


def reviewers():
    base = 'results/research-release-2'
    out = 'results/pre_refactor/reviewers'
    record('independent_accounting', [PYTHON,base+'/astra-review-20261106/accounting/astra_overlay_independent_portable.py','--output-dir',out+'/accounting'], [out+'/accounting'], reference=base+'/astra-review-20261106/accounting/verified_outputs')
    record('independent_statistics', [PYTHON,base+'/astra-review-20261106/statistical_review/diagnostic.py','--output-dir',out+'/statistics'], [out+'/statistics'], seeds=dict(bootstrap=730601), reference=base+'/astra-review-20261106/statistical_review')
    record('window_placement', [PYTHON,'scripts/freeze_phase0.py','window-worker'], [out+'/window_placement'], reference=base+'/astra-review-20261106/window_placement', note='The archived script has a hard-coded /tmp output directory. The worker substitutes that output-path literal only in memory; original source, __file__, protocol assumptions, offsets and policies are preserved.')
    record('owner_checks', [PYTHON,base+'/opus-review-20261106/owner_checks/owner_checks.py'], [], reference=base+'/opus-review-20261106/owner_checks')
    record('owner_window_check', [PYTHON,base+'/opus-review-20261106/owner_checks/window_placement_check.py',base+'/astra-review-20261106/window_placement/window_records.csv'], [], reference=base+'/opus-review-20261106/owner_checks')


def window_worker():
    source = ROOT/'results/research-release-2/astra-review-20261106/window_placement/run_diagnostic.py'
    output = BASE/'reviewers/window_placement'
    output.mkdir(parents=True, exist_ok=False)
    text = source.read_text()
    old = "OUT=Path('/tmp/astra_window_phase_20261106')"
    assert text.count(old) == 1
    text = text.replace(old, f'OUT=Path({str(output)!r})')
    exec(compile(text, str(source), 'exec'), {'__file__': str(source), '__name__': '__main__'})


def publication_worker(kind):
    import io
    import shutil
    import tarfile
    import tempfile
    # Execute the unmodified publication scripts in a disposable archive of
    # the tag so their fixed reports/ paths cannot replace historical evidence.
    with tempfile.TemporaryDirectory(prefix='phase0-publication-', dir='/tmp') as temp:
        archive = subprocess.check_output(['git','archive','pre-refactor'], cwd=ROOT)
        with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
            tar.extractall(temp, filter='data')
        script = {'verify':'verify_release_2.py','status':'research_status.py','package':'package_release_2.py'}[kind]
        code = subprocess.call([str(PYTHON), str(Path(temp)/'scripts'/script)], cwd=temp)
        destination = BASE/'publication'/kind
        destination.mkdir(parents=True, exist_ok=False)
        for p in (Path(temp)/'reports').glob('*'):
            if p.is_file():
                shutil.copy2(p, destination/p.name)
        raise SystemExit(code)


def ancillary():
    for kind in ('verify','status','package'):
        record('publication_'+kind, [PYTHON,'scripts/freeze_phase0.py','publication-worker',kind], ['results/pre_refactor/publication/'+kind], expected_exit=1 if kind=='package' else 0,
               note='Unmodified script executed in a disposable git archive of pre-refactor. Package is expected to refuse overwriting the existing frozen publication snapshot.' if kind=='package' else 'Unmodified script in a disposable git archive of pre-refactor; generated reports copied out, original reports untouched.')
    record('existing_test_suite', [PYTHON,'-m','pytest','-q','--junitxml=results/pre_refactor/tests.xml'], ['results/pre_refactor/tests.xml'], note='Existing tests only; no Phase 1 tests introduced.')
    record('study_notebook_launcher', [PYTHON,'scripts/run_harness_notebooks.py','--output-dir','results/pre_refactor/original_launcher'], ['results/pre_refactor/original_launcher'], seeds=dict(illustrative=20261105), note='Checks the original default CLI exactly as saved; individual notebooks are also attempted separately so an early failure cannot hide later experiments.')
    for source in sorted((ROOT/'MonteCarlo_Functions').glob('*.py')):
        record('fragment_'+source.stem,[PYTHON,str(source.relative_to(ROOT))],[],inputs=[str(source.relative_to(ROOT))], note='Legacy notebook fragment checked as saved. Standalone failure is recorded rather than adding caller globals or inventing an experiment.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['initialize','canonical','canonical-pinned','notebooks','reviewers','ancillary','notebook-worker','window-worker','publication-worker'])
    parser.add_argument('paths', nargs='*')
    args = parser.parse_args()
    os.environ.update(THREADS)
    if args.action == 'notebook-worker':
        notebook_worker(*args.paths)
    elif args.action == 'window-worker':
        window_worker()
    elif args.action == 'publication-worker':
        publication_worker(*args.paths)
    elif args.action == 'canonical-pinned':
        canonical(repeat=True)
    else:
        globals()[args.action]()


if __name__ == '__main__':
    main()

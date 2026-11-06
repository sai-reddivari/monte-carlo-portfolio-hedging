"""Execute selected hedging-study notebooks in fresh kernels.

Sources are preserved. Executed copies and an execution manifest are written to
one new results directory. Original investigation notebooks are never selected.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import json
import os
import sys
import tempfile

import nbformat
from nbclient import NotebookClient
from jupyter_client import KernelManager

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path)
    parser.add_argument('--notebooks', nargs='+', help='Explicit notebook basenames; default is all study notebooks.')
    args = parser.parse_args()
    source_dir = ROOT / 'notebooks'
    if args.notebooks:
        paths = []
        for name in args.notebooks:
            if Path(name).name != name or Path(name).suffix != '.ipynb' or not (source_dir / name).is_file():
                parser.error(f'Unknown study notebook basename: {name}')
            paths.append(source_dir / name)
    else:
        paths = sorted(source_dir.glob('[0-9][0-9]_*.ipynb'))
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    dest = (args.output_dir or ROOT/'results'/f'harness-{stamp}').resolve()
    dest.mkdir(parents=True, exist_ok=False)
    os.environ.setdefault('MPLCONFIGDIR', tempfile.mkdtemp(prefix='mc-mpl-', dir='/tmp'))
    report = {'python': sys.executable, 'started_utc': stamp, 'notebooks': []}
    manifest = dest / 'execution_manifest.json'
    for path in paths:
        print(f'Executing {path.name}', flush=True)
        nb = nbformat.read(path, as_version=4)
        nbformat.validate(nb)
        entry = {'name': path.name, 'source_sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
        with tempfile.TemporaryDirectory(prefix='mc-kernel-', dir='/tmp') as runtime:
            runtime = Path(runtime)
            env = dict(os.environ)
            env['IPYTHONDIR'] = str(runtime / 'ipython')
            env['JUPYTER_RUNTIME_DIR'] = str(runtime)
            env['MPLBACKEND'] = 'module://matplotlib_inline.backend_inline'
            km = KernelManager(kernel_name='python3', transport='ipc', connection_file=str(runtime/'k.json'))
            km.kernel_spec.argv = [sys.executable, '-m', 'ipykernel_launcher', '-f', '{connection_file}']
            client = NotebookClient(nb, timeout=240, kernel_name='python3', km=km,
                                    resources={'metadata': {'path': str(ROOT)}})
            try:
                client.execute(env=env)
                entry['status'] = 'passed'
            except Exception as exc:
                entry.update(status='failed', error=str(exc))
                raise
            finally:
                if km.has_kernel:
                    km.shutdown_kernel(now=True)
                nbformat.write(nb, dest / path.name)
                report['notebooks'].append(entry)
                manifest.write_text(json.dumps(report, indent=2) + '\n')
    print(f'Executed notebooks and manifest: {dest}')


if __name__ == '__main__':
    main()

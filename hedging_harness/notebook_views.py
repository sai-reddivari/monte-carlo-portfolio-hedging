"""Thin notebook entry points and explicit historical-provenance context."""
from __future__ import annotations
import importlib
import json
from pathlib import Path
import tempfile
from hashlib import sha256
from .configuration import ROOT

_HISTORICAL = None


def historical_root():
    global _HISTORICAL
    if _HISTORICAL is None:
        from .reproduction import frozen_workspace
        # Only historical identities are checked here. Current arithmetic is
        # exercised separately and compared to the full-precision manifest.
        parent=Path(tempfile.mkdtemp(prefix='hedging-frozen-notebook-',dir='/tmp'))
        _HISTORICAL=frozen_workspace(parent/'source')
    return _HISTORICAL


def historical_path(value):
    path=Path(value)
    if not path.is_absolute():
        return ROOT/path
    manifest=json.loads((ROOT/'results/manifest_pre_refactor.json').read_text())
    original=Path(manifest['python']).parents[2]
    if path.is_relative_to(original):
        return ROOT/path.relative_to(original)
    raise ValueError(f'Historical path is outside the recorded repository: {value}')


def verify_frozen_overlay(run_dir):
    run_dir=Path(run_dir)
    protocol=json.loads((run_dir/'protocol.json').read_text())
    digest=sha256((run_dir/'protocol.json').read_bytes()).hexdigest()
    assert digest==(run_dir/'protocol.sha256').read_text().strip()
    snapshot=historical_root()
    changed=[]
    for field in ['source_sha256','input_sha256']:
        for name,expected in protocol[field].items():
            path=snapshot/name
            if not path.is_file() or sha256(path.read_bytes()).hexdigest()!=expected:
                changed.append(name)
    assert not changed,changed
    return protocol,digest,changed


def run(name):
    index=json.loads((ROOT/'hedging_harness/notebooks/index.json').read_text())
    if name not in index:
        raise ValueError(f'Unknown notebook: {name}')
    return importlib.import_module('.notebooks.'+index[name],package='hedging_harness').run()


def load_cached_release(*args,**kwargs):
    from .notebooks.cached_release import load_cached_release as implementation
    return implementation(*args,**kwargs)


def run_investigations(destination):
    """Execute original-method views in fresh kernels and retain their outputs."""
    import subprocess,sys
    destination=Path(destination);destination.mkdir(parents=True,exist_ok=False)
    for source in sorted((ROOT/'MonteCarlo_InvestigationNotebooks').glob('*.ipynb')):
        subprocess.run([sys.executable,'-m','hedging_harness.notebook_execution',
                        str(source.relative_to(ROOT)),str(destination/source.name)],cwd=ROOT,check=True)

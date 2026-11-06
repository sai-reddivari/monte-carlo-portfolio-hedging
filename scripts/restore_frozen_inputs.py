"""Restore missing authorized historical input bytes from the immutable local tag."""
from pathlib import Path
import sys
import tempfile
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from hedging_harness.reproduction import frozen_workspace,restore_inputs
with tempfile.TemporaryDirectory(prefix='hedging-inputs-',dir='/tmp') as temp:
    frozen=frozen_workspace(Path(temp)/'source')
    restore_inputs(frozen)
print('Frozen inputs restored/verified; no changed input was overwritten.')

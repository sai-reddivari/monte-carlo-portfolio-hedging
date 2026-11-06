"""Compatibility CLI for hedging_harness.experiments.run_feature_research."""
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from hedging_harness.experiments import run_feature_research as _implementation
from hedging_harness.experiments.run_feature_research import *
def __getattr__(name):
    return getattr(_implementation, name)
if __name__ == '__main__':
    _implementation.main()

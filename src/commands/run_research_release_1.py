"""Compatibility CLI for hedging_harness.experiments.run_research_release_1."""
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))
from hedging_harness.experiments import run_research_release_1 as _implementation
from hedging_harness.experiments.run_research_release_1 import *
def __getattr__(name):
    return getattr(_implementation, name)
if __name__ == '__main__':
    _implementation.main()

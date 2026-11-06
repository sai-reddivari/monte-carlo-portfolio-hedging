"""Compatibility entry point; numerical inputs are explicit package arguments."""
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))
from hedging_harness.legacy_methods import one_step_prices
if __name__ == '__main__':
    from hedging_harness.configuration import defaults
    params = defaults()['legacy_reference'].copy()
    result = one_step_prices(**params)
    print(result)

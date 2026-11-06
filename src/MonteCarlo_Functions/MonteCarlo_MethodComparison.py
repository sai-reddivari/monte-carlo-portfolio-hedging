"""Compatibility entry point; numerical inputs are explicit package arguments."""
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))
from hedging_harness.legacy_methods import compare_methods
if __name__ == '__main__':
    import argparse
    import importlib
    from hedging_harness.configuration import defaults
    parser = argparse.ArgumentParser(description='Original method example. The missing CRR implementation must be supplied explicitly.')
    parser.add_argument('--crr-provider', required=True, help='Importable module:function implementing the original CRR callable signature')
    args = parser.parse_args()
    module, name = args.crr_provider.split(':', 1)
    provider = getattr(importlib.import_module(module), name)
    print(compare_methods(**defaults()['legacy_reference'], crr_price=provider))

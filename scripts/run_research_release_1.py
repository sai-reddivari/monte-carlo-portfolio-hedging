"""Execute the frozen controlled policy-selection research protocol."""
from datetime import datetime, timezone
from pathlib import Path
import argparse
import json
import os
import sys

os.environ.setdefault("MPLBACKEND", "Agg")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from hedging_harness.research import run_release


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--protocol', type=Path, default=ROOT/'config/research_release_1.json')
    parser.add_argument('--output-dir', type=Path)
    args = parser.parse_args()
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
    result = run_release(args.protocol, args.output_dir or ROOT/'results/research-release-1'/stamp)
    print(json.dumps({k: result[k] for k in ['output_dir','selected_policy','gate']}, indent=2))


if __name__ == '__main__':
    main()

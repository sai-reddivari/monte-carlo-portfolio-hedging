"""Audit JPM/PNC/GS prices in two short windows, with at most 12 live requests.

Run: .venv/bin/python scripts/audit_market_data.py
Credentials are loaded locally from FMP_API_KEY or .env, never command arguments.
"""
from pathlib import Path
import argparse
import json
import sys

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))
from market_data import FMPClient, audit_market_data, load_fmp_api_key
from market_data.export import export_price_panels


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--refresh", action="store_true", help="Verify live access instead of reusing cached normalized data")
    parser.add_argument("--output", type=Path, default=ROOT / "results/data-audit/coverage.json")
    parser.add_argument("--export-prices", action="store_true", help="Also export a three-symbol full-history panel (at most three additional live requests)")
    parser.add_argument("--history-start", default="2010-01-04")
    parser.add_argument("--history-end", default="2026-11-04")
    args = parser.parse_args()
    try:
        api_key = load_fmp_api_key(ROOT / ".env")
        client = FMPClient(api_key, cache_dir=ROOT / "data/cache/fmp", max_requests=15 if args.export_prices else 12)
        report = audit_market_data(client, refresh=args.refresh)
        if args.export_prices and report["status"] == "price_sample_observed":
            metadata = export_price_panels(client, output_dir=ROOT / "data/market",
                                           start=args.history_start, end=args.history_end,
                                           refresh=args.refresh)
            report["canonical_prices"] = metadata["data_files"]
        report["requests_sent"] = client.request_count
    except Exception:
        # No raw exception strings: an authentication library could include a URL.
        report = {"status": "audit_setup_failed", "research_gate_2_passed": False, "requests_sent": 0}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({"status": report["status"], "requests_sent": report["requests_sent"],
                      "research_gate_2_passed": report["research_gate_2_passed"], "report": str(args.output)}, indent=2))


if __name__ == "__main__":
    main()

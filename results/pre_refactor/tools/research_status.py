"""Build a pinned publication evidence index; never promote empirical Gate 2."""
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]


def read(path):
    path = Path(path)
    return json.loads(path.read_text()) if path.is_file() else {}


def integrity(folder, mapping):
    failures = []
    for name, expected in mapping.items():
        path = Path(name)
        if not path.is_absolute():
            path = folder / path
        if not path.is_file() or sha256(path.read_bytes()).hexdigest() != expected:
            failures.append(str(path))
    return {'checked_files': len(mapping), 'passed': (not failures) if mapping else None, 'failures': failures}


def build():
    package = read(ROOT / 'config/research_release_2_package.json')
    runs = package['canonical_runs']
    r1 = ROOT / runs['controlled_release']
    r1gate = read(r1 / 'gate_status.json')
    r1integrity = integrity(r1, read(r1 / 'artifact_manifest.json'))
    data = read(ROOT / 'data/market/data_gate_status.json')
    verification = read(ROOT / package['verification'])
    verification_current = verification.get('package_config_sha256') == sha256((ROOT / 'config/research_release_2_package.json').read_bytes()).hexdigest()
    if verification_current:
        verification_current = all((ROOT / name).is_file() and sha256((ROOT / name).read_bytes()).hexdigest() == expected for name, expected in verification.get('checked_file_sha256', {}).items())
    ready = verification.get('passed', False) and verification_current
    entries = {}
    for name, relative in runs.items():
        if name == 'controlled_release':
            continue
        folder = ROOT / relative
        record_name = 'run_record.json' if name == 'model_replay' else 'manifest.json'
        record = read(folder / record_name)
        entries[name] = {
            'report': str((folder / 'report.md').relative_to(ROOT)),
            'record': str((folder / record_name).relative_to(ROOT)),
            'artifact_integrity': integrity(folder, record.get('artifacts_sha256', {})),
            'evidence_flags': record.get('checks', {}),
        }
        if name == 'conditional_breadth':
            entries[name]['conditional_breadth_computation_passed'] = record.get('conditional_breadth_computation_passed', False)
            entries[name]['full_stage7_gate_passed'] = False
    archive = ROOT / package['review_archive']
    audit = read(archive / 'accounting/verified_outputs/audit_summary.json')
    owner = next((name for name in package['overlay_owner_addendum_candidates'] if (ROOT / name).is_file()), None)
    state = {
        'generated_utc': datetime.now(timezone.utc).isoformat(),
        'human_review': 'separate downstream step; not included in computational publication readiness',
        'book_container': 'Book retained; shared source config/illustrative_study.json',
        'research_gate_1': {**r1gate, 'artifact_integrity': r1integrity,
            'report': runs['controlled_release'] + '/report.md',
            'independent_validation': 'docs/independent_validation.md',
            'notebook': 'Hedging_Study_Notebooks/04_policy_selection_research.ipynb'},
        'conditional_release_2': {
            'publication_ready': ready,
            'status': 'ready_for_separate_human_review' if ready else 'package_checks_pending_or_stale',
            'empirical_certification': False,
            'publication_summary': package['publication_summary'],
            'claims_and_errata': package['claims_and_errata'],
            'verification': package['verification'],
            'verification_current': verification_current,
            'publication_snapshot': package['publication_snapshot'],
            'public_push_performed': False,
            'test_evidence': package['test_evidence'],
            'test_summary': verification.get('test_summary', {}),
        },
        'data_gate': {
            'core_ten_price_and_calendar_passed': data.get('core_ten_and_benchmarks', {}).get('passed', False),
            'current_universe_names': data.get('current_universe_breadth', {}).get('selected_names', 0),
            'complete_histories': data.get('current_universe_breadth', {}).get('full_histories', 0),
            'partial_histories_retained': data.get('current_universe_breadth', {}).get('partial_histories', 0),
            'historical_membership': data.get('historical_membership', {}),
            'option_quotes': data.get('listed_option_quote_gate', {}),
            'evidence': 'data/market/data_gate_status.json'},
        'workstreams': entries,
        'stage6': {
            'owner': 'external Opus; Astra independent review integrated',
            'status': 'base_case_terminal_accounting_independently_reconstructed',
            'review_archive': package['review_archive'],
            'independent_accounting': {
                'status': audit.get('status'), 'outcomes': audit.get('rows'),
                'maximum_terminal_pnl_residual_dollars': audit.get('max_absolute_pnl_residual_dollars'),
                'scope': audit.get('scope'), 'not_validated': audit.get('not_validated', [])},
            'owner_addendum': owner,
            'owner_corrections_integrated_in': package['claims_and_errata'],
            'tail_definition': 'Worst six of 23 separate 63-session test windows; 25% tail fraction with ceiling rounding',
            'option_market_prices_acquired': False,
            'continuous_rolled_nav_available': False,
        },
        'research_gate_2': {
            'passed': False, 'stage7_full_empirical_claim': False,
            'remaining_evidence': [
                'Timestamped option bid/ask and contract terms for market-price claims',
                'Point-in-time universe and failed-name coverage for survivorship-safe generalization',
                'Frozen horizon-aligned forecast-to-hedge economic evaluation',
                'Realistic dividends, financing/borrow, margin, option spreads and lifecycle treatment'],
            'completed_but_not_sufficient': [
                'Independent stage6 base-case terminal accounting review',
                'Release-aware SEC feature forecasts on ten-name/six-bank extension',
                'Conditional breadth computations through forty names']},
        'next_economic_protocol': {
            'status': 'requirements_recorded_not_yet_frozen_or_run',
            'requirements': 'docs/next_economic_protocol_requirements.md',
            'publication_dependency': False,
            'rule': 'Exact policy mapping and execution protocol must be written and hashed before any further economic evaluation'},
    }
    target = ROOT / 'reports'
    target.mkdir(exist_ok=True)
    (target / 'research_status.json').write_text(json.dumps(state, indent=2) + '\n')
    lines = [
        '# Financial sector hedging research evidence checkpoint', '',
        '**Conditional Research Release 2: ' + ('ready for separate human review.' if ready else 'package checks pending or stale.') + '** No public upload has occurred.', '',
        f"[Publication summary](../{quote(package['publication_summary'])}) · [Claims and errata](../{quote(package['claims_and_errata'])}) · [Opus owner addendum](../docs/equity_overlay_review_addendum.md)", '',
        '**Research Gate 1 is complete for the controlled synthetic study and independently reproduced. Full empirical Research Gate 2 remains open.** Publication readiness does not certify market execution or survivorship-safe generalization.', '',
        'The locked maturity-sensitive hedge has held-out ES95 $3,327.95 and mean financed stock cost $487.97, with a $490.18 upper endpoint under its $500 expected-cost screen. ES95 improves relative to weekly; the daily comparison is inconclusive at lower cost.', '',
        '| Workstream | Canonical evidence | Scope |', '|---|---|---|',
        '| Shared inputs | `config/illustrative_study.json`, `data/study_inputs/` | One validated source; Book retained |',
        '| Market panel | [Data gate](../data/market/data_gate_status.json) | Ten names plus SPY/XLF; 4,236 sessions; current-survivor universe |',
        '| Breadth coverage | [Data coverage](../docs/data_coverage.md) | Fifty current names: 42 complete, eight partial histories retained |',
    ]
    scopes = {
        'model_replay': 'Historical stocks; hypothetical European options; accounting and lifecycle checks',
        'price_risk': 'Past-only five-/twenty-session risk forecasts; chronological evaluation',
        'incremental_features_original': 'Original three-name/two-bank cohorts; retained for comparison',
        'incremental_features': 'Final ten-name liabilities/assets and six-bank deposit extension; mixed and adverse results retained',
        'conditional_breadth': '3/10/25/40-name common-path computations; current availability conditioned; not full stage7 certification',
        'equity_overlays': '23 separate quarterly test accounts; model prices; worst six-window mean loss; independent terminal reconstruction',
    }
    for name, entry in entries.items():
        lines.append(f"| {name.replace('_', ' ')} | [Report](../{entry['report']}) | {scopes[name]} |")
    lines += ['',
        'Astra independently reconstructed all 2,013 base-case stage6 terminal outcomes with maximum P&L discrepancy $1.1921e-7, all 276 test collar legs and original bootstrap intervals. This does not certify all intrawindow marks/drawdowns, sensitivity runs or vendor/execution assumptions.', '',
        'Reviewer evidence is preserved outside `/tmp` in the [Astra archive](../results/research-release-2/astra-review-20261106/archive_manifest.json); the [Opus archive](../results/research-release-2/opus-review-20261106/archive_manifest.json) preserves his addendum/checks. Original frozen reports are unchanged. Post-hoc comparator and window-placement diagnostics are labelled in the claims supplement.', '',
        'The combined suite passed **194 tests plus 22 subtests**, with 28 pandas timezone deprecation warnings and no failures. [Recorded test cases](release_2_tests.xml) · [Integrity/link verification](release_2_verification.json).', '',
        'The final feature extension covers ten names/six banks, not only the earlier three names/two banks. Liabilities/assets gives a small five-day QLIKE gain and worse twenty-day QLIKE; deposit-share features worsen incremental QLIKE. Forecast-to-hedge value remains unestablished.', '',
        'No historical option quotes or observed implied volatility were acquired. Remaining empirical requirements include market quotes/contract terms, historical membership and failed names, realistic execution/financing and a separately frozen forecast-to-hedge study. A negative or inconclusive result does not block this conditional publication.', '',
        '[Next-protocol requirements](../docs/next_economic_protocol_requirements.md) are recorded separately; the exact new economic protocol has not been frozen or run. Retrospective remeasurement does not restore untouched-test status.', '',
        'Machine-readable state: [research_status.json](research_status.json). Canonical releases are pinned in `config/research_release_2_package.json`; status no longer selects a result by filesystem modification time.',
    ]
    (target / 'research_status.md').write_text('\n'.join(lines) + '\n')
    print(json.dumps({'conditional_release_2_publication_ready': ready, 'gate1_artifact_integrity': r1integrity['passed'], 'research_gate_2_passed': False, 'owner_addendum': owner}, indent=2))
    return state


if __name__ == '__main__':
    build()

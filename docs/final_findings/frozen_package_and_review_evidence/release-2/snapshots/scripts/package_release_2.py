"""Freeze a new local publication snapshot; never overwrite a prior package."""
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import shutil
import tempfile

from research_status import build
from verify_release_2 import verify

ROOT = Path(__file__).resolve().parents[1]


def package_release():
    config = json.loads((ROOT / 'config/research_release_2_package.json').read_text())
    destination = ROOT / config['publication_snapshot']
    if destination.exists():
        raise FileExistsError(f'Frozen package already exists: {destination}')
    evidence = verify()
    if not evidence['passed']:
        raise RuntimeError('Publication verification failed; no package frozen')
    state = build()
    if not state['conditional_release_2']['publication_ready']:
        raise RuntimeError('Publication state is not ready')
    sources = [
        'README.md', 'config/research_release_2_package.json',
        config['publication_summary'], config['claims_and_errata'],
        evidence['overlay_owner_addendum'], 'docs/next_economic_protocol_requirements.md',
        'docs/astra_research_review.md', 'reports/research_status.md', 'reports/research_status.json',
        config['verification'], config['test_evidence'],
        'scripts/research_status.py', 'scripts/verify_release_2.py', 'scripts/package_release_2.py',
    ]
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix='.release-2-staging-', dir=destination.parent))
    try:
        snapshots = {}
        for name in sources:
            source = ROOT / name
            relative = Path('snapshots') / name
            target = staging / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            digest = sha256(source.read_bytes()).hexdigest()
            assert digest == sha256(target.read_bytes()).hexdigest()
            snapshots[str(relative)] = {'sha256': digest, 'original_repo_path': name}
        experiments = {}
        for name, relative in config['canonical_runs'].items():
            folder = ROOT / relative
            experiments[name] = {
                'directory': relative,
                'files_sha256': {
                    str(path.relative_to(ROOT)): sha256(path.read_bytes()).hexdigest()
                    for path in sorted(folder.rglob('*')) if path.is_file()
                },
            }
        archives = {}
        for relative in (config['review_archive'], 'results/research-release-2/opus-review-20261106'):
            manifest_path = ROOT / relative / 'archive_manifest.json'
            archives[relative] = sha256(manifest_path.read_bytes()).hexdigest()
        manifest = {
            'release': config['release'], 'title': config['title'],
            'frozen_utc': datetime.now(timezone.utc).isoformat(),
            'publication_ready': True, 'human_review_complete': False,
            'research_gate_2_passed': False, 'public_push_performed': False,
            'integrity_checks_passed': len(evidence['checks']),
            'snapshots': snapshots, 'frozen_experiments': experiments,
            'review_archive_manifests_sha256': archives,
            'economic_protocol_or_results_changed': False,
            'next_economic_protocol_status': 'requirements only; exact protocol not yet frozen or run',
        }
        (staging / 'manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
        (staging / 'README.md').write_text(
            '# Conditional Research Release 2 frozen publication package\n\n'
            'Ready for separate human review. Full empirical Gate 2 remains open; no public upload occurred.\n\n'
            '[Publication summary](../../../docs/research_release_2_publication.md) · '
            '[Claims and errata](../../../docs/research_release_2_claims_and_errata.md) · '
            '[Evidence checkpoint](../../../reports/research_status.md)\n\n'
            '`manifest.json` pins every snapshot, original frozen experiment and review-archive manifest. '
            'Files under `snapshots/` are byte-identical archival copies; their links retain the original '
            'repository-relative context. Use the canonical links above for reading. This is a local '
            'publication snapshot, not a standalone export of market-data licensing rights.\n'
        )
        staging.rename(destination)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    print(json.dumps({'frozen_package': str(destination.relative_to(ROOT)), 'snapshots': len(snapshots), 'publication_ready': True, 'research_gate_2_passed': False}, indent=2))
    return destination


if __name__ == '__main__':
    package_release()

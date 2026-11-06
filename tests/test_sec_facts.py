"""Publication and issuer binding tests, with synthetic SEC-shaped records."""

import pandas as pd
import unittest
import math
import json
from pathlib import Path
import tempfile

from market_data.sec_facts import (
    normalize_sec_facts, build_filing_snapshots, select_snapshot_asof,
    CORE10_BUSINESS_GROUPS, export_cached_sec_core10,
)

CIK = '0000019617'
A = '0000019617-20-000001'
B = '0000019617-20-000002'


def fact(value, *, accession=A, end='2020-03-31', filed='2020-05-01', **extra):
    return {'val': value, 'accn': accession, 'end': end, 'filed': filed, 'form': '10-Q', **extra}


def payload(tags):
    return {'cik': int(CIK), 'entityName': 'Test issuer', 'facts': {'us-gaap': {
        tag: {'units': {'USD': values}} for tag, values in tags.items()}}}


def submissions(*, filing='2020-05-01'):
    return {'cik': CIK, 'filings': {'recent': {
        'accessionNumber': [A], 'filingDate': [filing],
        'reportDate': ['2020-03-31'], 'form': ['10-Q']}}}


def normalize(tags, metadata=None):
    return normalize_sec_facts(payload(tags), metadata or submissions(), symbol='JPM', cik=CIK)


class PublicationBindingTests(unittest.TestCase):
    def test_core10_separate_export_preserves_frozen_set_and_business_rules(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);cache=root/'data/cache/sec';cache.mkdir(parents=True)
            out=root/'data/market/features/sec_facts_core10';out.mkdir(parents=True)
            frozen=root/'data/market/features/sec_facts';frozen.mkdir()
            sentinel=frozen/'sec_filing_snapshots.csv';sentinel.write_text('frozen original\n')
            identifiers={}
            for symbol in CORE10_BUSINESS_GROUPS:
                for kind,value in [('companyfacts',payload({'Assets':[fact(100)],'Deposits':[fact(50)]})),
                                   ('submissions',submissions())]:
                    (cache/f'{symbol}_{kind}.json').write_text(json.dumps(value))
                metadata=out/f'{symbol}_identity.json';metadata.write_text(json.dumps({'cik':CIK}))
                identifiers[symbol]={'cik':CIK,'source_metadata_path':str(metadata)}
            (out/'sec_core10_probe_manifest.json').write_text(json.dumps({
                'identifiers':identifiers,'fmp_identifier_requests':7,'sec_requests':14}))
            report=export_cached_sec_core10(root)
            panel=pd.read_csv(out/'sec_filing_snapshots.csv')
            approved=set(panel.loc[panel['deposit_feature_approved_for_issuer'],'symbol'])
            assert approved=={'JPM','PNC','BAC','WFC','C','USB'}
            assert len(panel)==10 and panel['deposits'].eq(50).all()
            assert panel['liabilities'].isna().all() and panel['cash_and_cash_equivalents'].isna().all()
            assert sentinel.read_text()=='frozen original\n'
            assert report['frozen_three_name_artifacts_rewritten'] is False

    def test_same_filing_same_period_and_missing_not_zero(self):
        frame, report = normalize({'Assets': [fact(100)], 'Liabilities': [fact(70)],
            'Deposits': [fact(60, end='2019-12-31')]})
        snapshot = build_filing_snapshots(frame).iloc[0]
        assert snapshot['assets'] == 100 and snapshot['liabilities'] == 70
        assert pd.isna(snapshot['deposits']) and pd.isna(snapshot['cash_and_cash_equivalents'])
        assert snapshot['available_at'] == '2020-05-04T20:00:00+00:00'
        assert report['recent_crosscheck_mismatches'] == 0


    def test_cik_mismatch_rejected(self):
        bad = payload({'Assets': [fact(1)]}); bad['cik'] = 3
        with self.assertRaisesRegex(ValueError, 'issuer'):
            normalize_sec_facts(bad, submissions(), symbol='JPM', cik=CIK)
        bad = submissions(); bad['cik'] = 3
        with self.assertRaisesRegex(ValueError, 'issuer'):
            normalize({'Assets': [fact(1)]}, bad)


    def test_mismatched_accession_metadata_is_not_usable(self):
        frame, report = normalize({'Assets': [fact(100)]}, submissions(filing='2020-05-04'))
        assert report['recent_crosscheck_mismatches'] == 1
        assert not frame['original_vintage_verified'].any()
        with self.assertRaisesRegex(ValueError, 'No coherent'):
            build_filing_snapshots(frame)


    def test_conflicting_same_filing_values_excluded_and_duration_ignored(self):
        frame, report = normalize({'Assets': [fact(100), fact(100)],
            'Liabilities': [fact(60), fact(70)],
            'Deposits': [fact(20, start='2020-01-01')]})
        snapshot = build_filing_snapshots(frame).iloc[0]
        assert len(frame) == 3 and pd.isna(snapshot['liabilities'])
        assert report['within_filing_ambiguous_facts'] == 2
        assert report['rejected_counts'][0]['reason'] == 'duration_fact_not_instant'


    def test_non_usd_is_not_silently_converted(self):
        data = payload({'Assets': [fact(100)]})
        data['facts']['us-gaap']['Assets']['units'] = {'EUR': [fact(100)]}
        with self.assertRaisesRegex(ValueError, 'No accession-bound'):
            normalize_sec_facts(data, submissions(), symbol='JPM', cik=CIK)


    def test_native_older_binding_distinguished_from_independent_crosscheck(self):
        frame, _ = normalize({'Assets': [fact(100, accession=B)]})
        assert frame['original_vintage_verified'].all()
        assert not frame['independent_recent_accession_crosscheck'].any()
        assert frame.iloc[0]['accession_crosscheck_status'].startswith('native_SEC_fact_binding')


    def test_asof_newest_period_then_available_revision_never_rolls_back(self):
        base = {'symbol': 'JPM', 'original_vintage_verified': True}
        rows = [
            dict(base, period_end='2020-03-31', filed='2020-05-01', accn=A,
                 available_at='2020-05-04T20:00:00Z', assets=100),
            dict(base, period_end='2020-06-30', filed='2020-08-01', accn=B,
                 available_at='2020-08-03T20:00:00Z', assets=120),
            dict(base, period_end='2020-03-31', filed='2020-08-10', accn='older-comparative',
                 available_at='2020-08-11T20:00:00Z', assets=101),
            dict(base, period_end='2020-06-30', filed='2020-08-20', accn='revision',
                 available_at='2020-08-21T20:00:00Z', assets=125),
        ]
        frame = pd.DataFrame(rows)
        assert select_snapshot_asof(frame, 'JPM', '2020-05-04T19:59:59Z') is None
        assert select_snapshot_asof(frame, 'JPM', '2020-08-12T20:00:00Z')['assets'] == 120
        assert select_snapshot_asof(frame, 'JPM', '2020-08-21T20:00:00Z')['assets'] == 125
        with self.assertRaisesRegex(ValueError, 'timezone'):
            select_snapshot_asof(frame, 'JPM', '2020-08-21')

if __name__ == "__main__":
    unittest.main()

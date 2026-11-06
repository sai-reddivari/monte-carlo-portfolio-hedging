"""Credential isolation and coverage checks; no live HTTP calls or real keys."""
from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlparse

import pandas as pd

from market_data import FMPClient, FMPError, audit_market_data, load_fmp_api_key, summarize_prices
from market_data.coverage import check_exchange_calendar
from market_data.export import export_price_panels


class CredentialTests(unittest.TestCase):
    def test_environment_precedes_dotenv_without_mutating_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / '.env'
            path.write_text('export FMP_API_KEY="file-token"\n')
            environment = {'FMP_API_KEY': 'environment-token'}
            self.assertEqual(load_fmp_api_key(path, environment), 'environment-token')
            self.assertEqual(environment, {'FMP_API_KEY': 'environment-token'})
            self.assertEqual(load_fmp_api_key(path, {}), 'file-token')

    def test_missing_and_placeholder_credentials_are_not_configured(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / '.env'
            self.assertIsNone(load_fmp_api_key(path, {}))
            path.write_text('# FMP configuration\nFMP_API_KEY=\n')
            self.assertIsNone(load_fmp_api_key(path, {}))
            path.write_text('FMP_API_KEY=YOUR_API_KEY\n')
            self.assertIsNone(load_fmp_api_key(path, {}))

    def test_dotenv_does_not_execute_or_expand_shell_content(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / '.env'
            path.write_text("FMP_KEY='$(echo must-not-execute)'\n")
            self.assertEqual(load_fmp_api_key(path, {}), '$(echo must-not-execute)')


class FMPAdapterTests(unittest.TestCase):
    def test_adjustment_explicit_sorting_and_cache_excludes_secret(self):
        secret = 'unit-test-secret-not-real'
        calls = []
        def transport(url, timeout):
            calls.append(url)
            return json.dumps([
                {'symbol': 'JPM', 'date': '2020-03-03', 'close': 103, 'apikey': secret},
                {'symbol': 'JPM', 'date': '2020-03-02', 'close': 101, 'apikey': secret},
            ]).encode()
        with tempfile.TemporaryDirectory() as directory:
            client = FMPClient(secret, cache_dir=directory, transport=transport)
            result = client.get_prices('JPM', '2020-03-02', '2020-03-03')
            self.assertEqual([row['close'] for row in result['records']], [101, 103])
            self.assertEqual(result['metadata']['source_price_field'], 'close')
            self.assertNotIn(secret, repr(client))
            self.assertNotIn(secret, json.dumps(result))
            self.assertTrue(all(secret not in p.read_text() for p in Path(directory).glob('*.json')))
            cached = client.get_prices('JPM', '2020-03-02', '2020-03-03')
            self.assertEqual(cached['metadata']['retrieval'], 'cache')
            self.assertEqual(len(calls), 1)

    def test_dividend_adjusted_requires_its_own_field(self):
        with tempfile.TemporaryDirectory() as directory:
            client = FMPClient('fake', cache_dir=directory, transport=lambda *_: json.dumps([
                {'date': '2020-03-02', 'close': 100}
            ]).encode())
            with self.assertRaisesRegex(FMPError, 'missing_price_fields'):
                client.get_prices('JPM', '2020-03-02', '2020-03-03', adjustment='dividend_adjusted')
            self.assertFalse(list(Path(directory).glob('*.json')))

    def test_no_credentials_means_no_transport_call(self):
        calls=[]
        with tempfile.TemporaryDirectory() as directory:
            client = FMPClient(None, cache_dir=directory, transport=lambda *args: calls.append(args))
            report = audit_market_data(client)
            self.assertEqual(report['status'], 'credential_required')
            self.assertEqual(report['requests_sent'], 0)
            self.assertEqual(calls, [])
            self.assertFalse(report['research_gate_2_passed'])
            self.assertEqual(len(report['price_coverage']),12)

    def test_transport_errors_never_expose_authenticated_url(self):
        secret = 'fake-test-key'
        def failing(url, timeout):
            raise URLError('request failed at ' + url)
        with tempfile.TemporaryDirectory() as directory:
            client = FMPClient(secret, cache_dir=directory, transport=failing)
            with self.assertRaises(FMPError) as error:
                client.get_prices('JPM', '2020-03-02', '2020-03-03')
            self.assertEqual(error.exception.code, 'transport_error')
            self.assertNotIn(secret, str(error.exception))
            self.assertNotIn('https', str(error.exception))

    def test_http_and_vendor_errors_are_classified_without_body(self):
        secret = 'fake-test-key'
        def denied(url, timeout):
            raise HTTPError(url,402,'sensitive URL '+url,None,None)
        with tempfile.TemporaryDirectory() as directory:
            client = FMPClient(secret, cache_dir=directory, transport=denied)
            with self.assertRaises(FMPError) as error:
                client.get_prices('JPM','2020-03-02','2020-03-03')
            self.assertEqual(error.exception.code,'entitlement_denied')
            self.assertNotIn(secret,str(error.exception))
            client = FMPClient(secret, cache_dir=directory, transport=lambda *_: json.dumps({'Error Message': 'Invalid API Key '+secret}).encode())
            with self.assertRaises(FMPError) as error:
                client.get_prices('JPM','2020-03-02','2020-03-03')
            self.assertEqual(error.exception.code,'authentication_failed')
            self.assertFalse(list(Path(directory).glob('*.json')))

    def test_duplicate_out_of_window_and_invalid_prices_rejected(self):
        fixtures = [
            ([{'date':'2020-03-02','close':100}]*2,'duplicate_observation_date'),
            ([{'date':'2020-03-01','close':100}],'out_of_window_observation'),
            ([{'date':'2020-03-02','close':0}],'nonpositive_or_nonfinite_price'),
        ]
        for rows, code in fixtures:
            with self.subTest(code=code), tempfile.TemporaryDirectory() as directory:
                client=FMPClient('fake',cache_dir=directory,transport=lambda *_, rows=rows:json.dumps(rows).encode())
                with self.assertRaises(FMPError) as error:
                    client.get_prices('JPM','2020-03-02','2020-03-03')
                self.assertEqual(error.exception.code,code)

    def test_request_budget_is_finite(self):
        with tempfile.TemporaryDirectory() as directory:
            client = FMPClient('fake',cache_dir=directory,max_requests=1,transport=lambda *_: b'[]')
            client.get_prices('JPM','2020-03-02','2020-03-03')
            with self.assertRaisesRegex(FMPError,'request_budget_exhausted'):
                client.get_prices('GS','2020-03-02','2020-03-03')
            self.assertEqual(client.request_count,1)


class CoverageTests(unittest.TestCase):
    def test_exchange_holiday_is_not_a_missing_session(self):
        check=check_exchange_calendar(['2020-04-09','2020-04-13'],'2020-04-09','2020-04-13')
        self.assertTrue(check['exchange_calendar_validated'])
        self.assertEqual(check['expected_sessions'],2)
        self.assertEqual(check['missing_expected_sessions'],[])

    def test_missing_actual_session_is_detected(self):
        check=check_exchange_calendar(['2020-04-09'],'2020-04-09','2020-04-13')
        self.assertFalse(check['exchange_calendar_validated'])
        self.assertEqual(check['missing_expected_sessions'],['2020-04-13'])

    def test_price_samples_do_not_pass_historical_option_or_research_gate(self):
        def transport(url, timeout):
            parsed=urlparse(url)
            query=parse_qs(parsed.query)
            dates=pd.bdate_range(query['from'][0],query['to'][0])
            dates=dates.difference(pd.to_datetime(['2019-01-21','2019-02-18','2020-02-17','2020-04-10']))
            field='adjClose' if 'dividend-adjusted' in parsed.path else 'close'
            return json.dumps([{'date': day.strftime('%Y-%m-%d'), 'symbol':query['symbol'][0],field:100+i*.1} for i,day in enumerate(dates)]).encode()
        with tempfile.TemporaryDirectory() as directory:
            client=FMPClient('fake',cache_dir=directory,transport=transport)
            report=audit_market_data(client)
            self.assertEqual(report['status'],'price_sample_observed')
            self.assertEqual(report['requests_sent'],12)
            self.assertTrue(all(row['all_dates_aligned'] for row in report['alignment']))
            self.assertEqual(report['historical_listed_options_gate']['status'],'vendor_documented_unavailable')
            self.assertFalse(report['research_gate_2_passed'])
            self.assertTrue(all(row['exchange_calendar_validated'] for row in report['price_coverage']))

    def test_unaligned_and_missing_records_are_not_silently_filled(self):
        def transport(url, timeout):
            query=parse_qs(urlparse(url).query)
            dates=['2020-03-02','2020-03-03'] if query['symbol'][0]=='JPM' else ['2020-03-03']
            field='adjClose' if 'dividend-adjusted' in url else 'close'
            return json.dumps([{'date':day,field:100} for day in dates]).encode()
        with tempfile.TemporaryDirectory() as directory:
            client=FMPClient('fake',cache_dir=directory,transport=transport,max_requests=4)
            report=audit_market_data(client,symbols=['JPM','GS'],windows={'sample':('2020-03-02','2020-03-03')})
            self.assertEqual(report['status'],'coverage_incomplete')
            self.assertFalse(report['alignment'][0]['all_dates_aligned'])
            self.assertEqual(report['alignment'][0]['common_observations'],1)
            self.assertEqual(report['alignment'][0]['union_observations'],2)

    def test_summary_rejects_duplicate_dates(self):
        with self.assertRaisesRegex(ValueError,'duplicate'):
            summarize_prices([{'date':'2020-03-02','close':100}]*2,'2020-03-02','2020-03-03')


class ReferenceAndExportTests(unittest.TestCase):
    def test_reference_allowlist_discards_unknown_and_secret_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            client=FMPClient('fake-secret',cache_dir=directory,transport=lambda *_:json.dumps([
                {'symbol':'JPM','sector':'Financial Services','apikey':'fake-secret','unknown':'not-retained'}
            ]).encode())
            result=client.get_reference('company-screener',{'limit':1})
            self.assertEqual(result['records'],[{'symbol':'JPM','sector':'Financial Services'}])
            self.assertNotIn('fake-secret',json.dumps(result))
            with self.assertRaises(ValueError):client.get_reference('unknown-endpoint')
            with self.assertRaises(ValueError):client.get_reference('company-screener',{'apikey':'bad'})

    def test_export_preserves_names_dates_and_documented_adjustment(self):
        def transport(url,timeout):
            query=parse_qs(urlparse(url).query)
            dates=pd.bdate_range(query['from'][0],query['to'][0])
            return json.dumps([{'date':day.strftime('%Y-%m-%d'),'close':100+i*.1} for i,day in enumerate(dates)]).encode()
        with tempfile.TemporaryDirectory() as directory:
            client=FMPClient('fake',cache_dir=Path(directory)/'cache',transport=transport,max_requests=3)
            with patch('market_data.export.check_exchange_calendar',return_value={'exchange_calendar_checked':True,'exchange_calendar_validated':True}):
                metadata=export_price_panels(client,output_dir=Path(directory)/'market',start='2018-01-02',end='2020-04-30')
            panel=pd.read_csv(metadata['data_files']['full_history']['path'],parse_dates=['date'],index_col='date')
            self.assertEqual(panel.columns.tolist(),['JPM','PNC','GS'])
            self.assertTrue(panel.index.is_monotonic_increasing)
            self.assertFalse(panel.index.has_duplicates)
            self.assertFalse(metadata['dividend_cashflows_included'])
            self.assertFalse(metadata['executable_option_quotes_included'])
            self.assertEqual(metadata['adjustment'],'split_adjusted')
            self.assertEqual(client.request_count,3)

    def test_unsupported_date_ranges_fail_before_requests(self):
        client=FMPClient('fake',transport=lambda *_:self.fail('no request expected'))
        with self.assertRaises(ValueError):export_price_panels(client,start='2000-01-01',end='2026-11-04')
        with self.assertRaises(ValueError):export_price_panels(client,start='2020-01-01',end='2020-04-30')
        self.assertEqual(client.request_count,0)


if __name__=='__main__':
    unittest.main()

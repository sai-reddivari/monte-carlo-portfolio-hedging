import unittest
import math

from market_data.features import (
    conservative_availability, finite_number, normalize_statement_records,
    normalize_treasury_records, publication_status,
)
from market_data.fmp import FMPError


class PublicationBindingTests(unittest.TestCase):
    def test_unknown_not_zero_and_actual_zero_preserved(self):
        assert finite_number(None) is None and finite_number('unavailable') is None
        assert finite_number(True) is None and finite_number(float('inf')) is None
        assert finite_number(0) == 0


    def test_period_end_is_never_used_as_publication_date(self):
        status = publication_status({'date': '2020-03-31'})
        assert status['available_at'] is None
        assert not status['period_end_used_as_publication_date']
        assert not status['strict_historical_feature_usable']


    def test_old_filing_date_does_not_validate_current_vendor_vintage(self):
        status = publication_status({'date': '2020-03-31', 'filingDate': '2020-05-01',
                                     'acceptedDate': '2020-05-01 16:00:00'})
        assert status['available_from_session'] == '2020-05-04'
        assert status['timing_usable_with_conservative_lag']
        assert not status['original_filing_value_vintage_verified']
        assert not status['strict_historical_feature_usable']
        future = publication_status({'date': '2026-09-30', 'filingDate': '2026-11-05'})
        assert not future['timing_usable_with_conservative_lag']


    def test_actual_exchange_holidays_and_early_close(self):
        # Thanksgiving publication: the following Friday closes13:00NewYork.
        assert conservative_availability('2020-11-26')['available_at'] == '2020-11-27T18:00:00+00:00'
        assert conservative_availability('2020-07-02')['available_from_session'] == '2020-07-06'
        with self.assertRaises(ValueError): conservative_availability('2020-01-01', lag_sessions=0)


    def test_statement_missing_and_currency_remain_explicit(self):
        normalized = normalize_statement_records([{'symbol': 'JPM', 'date': '2020-03-31',
            'data': {'Assets': 100, 'Deposits': 0, 'UninsuredDeposits': None, 'api_key': 'secret'}}],
            'JPM', 'balance-sheet-statement-as-reported')
        values = normalized['records'][0]['numeric_fields']
        assert values == {'Assets': 100, 'Deposits': 0, 'UninsuredDeposits': None}
        assert normalized['records'][0]['reported_currency'] is None
        assert normalized['strict_pit_usable_records'] == 0
        assert next(x for x in normalized['long_fields'] if x['field'] == 'Deposits')['field_status'] == 'reported_zero'


    def test_treasury_percent_units_and_no_publication_claim(self):
        result = normalize_treasury_records([{'date': '2020-03-02', 'year10': 1.1, 'month3': 0.7}],
                                             start='2020-03-01', end='2020-03-31')
        row = result['records'][0]
        assert math.isclose(row['year10_decimal'], .011)
        assert math.isclose(row['slope_10y_3m_decimal'], .004)
        assert row['year2_decimal'] is None
        assert not row['publication_timestamp_supplied'] and not row['strict_historical_feature_usable']
        assert row['available_from_session'] == '2020-03-03'


    def test_treasury_range_duplicates_and_invalid_dates_rejected(self):
        with self.assertRaises(ValueError):
            normalize_treasury_records([], start='2020-01-01', end='2020-06-01')
        with self.assertRaisesRegex(FMPError, 'duplicate'):
            normalize_treasury_records([{'date': '2020-03-02'}]*2, start='2020-03-01', end='2020-03-31')
        with self.assertRaisesRegex(FMPError, 'date'):
            normalize_treasury_records([{'date': '2021-03-02'}], start='2020-03-01', end='2020-03-31')

if __name__ == "__main__":
    unittest.main()

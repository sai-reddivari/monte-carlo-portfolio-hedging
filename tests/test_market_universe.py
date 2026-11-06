"""Current-universe selection and explicit unbalanced history preservation."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import pandas as pd

from market_data import FMPError
from market_data.universe import CORE_IDS, select_current_universe, fetch_unbalanced_panel


def snapshot():
    rows=[]
    for i, stable_id in enumerate(CORE_IDS):
        symbol='BNY' if stable_id=='BK' else stable_id
        rows.append({'symbol':symbol,'companyName':f'Issuer {stable_id}','marketCap':10e9+i,'sector':'Financial Services','industry':'Banks','country':'US','volume':1000000,'isEtf':False,'isFund':False,'isActivelyTrading':True})
    for symbol,name,cap,volume in [('BRK-B','Berkshire Hathaway',100e9,2000000),('BRK-A','Berkshire Hathaway',100e9,1000000),('AAA','Extra issuer',50e9,1000000),('MER-PK','Preferred issue',999e9,1000000),('BAD','Illiquid issuer',999e9,1)]:
        rows.append({'symbol':symbol,'companyName':name,'marketCap':cap,'sector':'Financial Services','industry':'Other','country':'US','volume':volume,'isEtf':False,'isFund':False,'isActivelyTrading':True})
    return pd.DataFrame(rows)


class UniverseTests(unittest.TestCase):
    def test_nested_core_order_survives_issuer_dedup_and_common_share_screen(self):
        selected,audit=select_current_universe(snapshot(),size=12)
        self.assertEqual(selected['stable_id'].tolist()[:10],list(CORE_IDS))
        self.assertIn('BRK-B',selected['symbol'].tolist())
        self.assertNotIn('BRK-A',selected['symbol'].tolist())
        self.assertNotIn('MER-PK',selected['symbol'].tolist())
        self.assertNotIn('BAD',selected['symbol'].tolist())
        self.assertEqual(len(audit),15)
        self.assertEqual(int(audit['selected'].sum()),12)

    def test_missing_required_core_is_not_silently_replaced(self):
        frame=snapshot().loc[lambda x:x['symbol'].ne('PNC')]
        with self.assertRaisesRegex(ValueError,'Required core'):
            select_current_universe(frame,size=12)

    def test_declared_limits_are_enforced(self):
        for size in [3,51]:
            with self.assertRaises(ValueError):select_current_universe(snapshot(),size=size)

    def test_partial_and_failed_columns_are_retained_without_filling(self):
        class Client:
            request_count=0
            def get_prices(self,symbol,*args,**kwargs):
                self.request_count+=1
                if symbol=='CCC':raise FMPError('entitlement_denied')
                dates=['2020-04-09','2020-04-13'] if symbol=='AAA' else ['2020-04-13']
                return {'records':[{'date':day,'close':100.0} for day in dates],'metadata':{'provider':'fixture'}}
        universe=pd.DataFrame({'stable_id':['AAA','BBB','CCC'],'symbol':['AAA','BBB','CCC'],'universe_order':[0,1,2]})
        with tempfile.TemporaryDirectory() as directory:
            metadata=fetch_unbalanced_panel(Client(),universe,output_dir=directory,start='2020-04-09',end='2020-04-13',pause_seconds=0,max_retries=0)
            prices=pd.read_csv(Path(directory)/'prices_financial_50_unbalanced.csv',parse_dates=['date'],index_col='date')
            self.assertEqual(prices.shape,(2,3))
            self.assertTrue(pd.isna(prices.loc['2020-04-09','BBB']))
            self.assertTrue(prices['CCC'].isna().all())
            self.assertFalse(metadata['failed_symbols_dropped'])
            self.assertFalse(metadata['missing_values_filled'])
            self.assertFalse(metadata['survivorship_safe_generalization_gate_passed'])
            self.assertEqual(metadata['coverage'][1]['leading_missing_sessions'],1)
            self.assertEqual(metadata['coverage'][2]['status'],'entitlement_denied')

    def test_transient_error_retry_is_bounded_and_failure_retained(self):
        class Client:
            request_count=0
            def get_prices(self,*args,**kwargs):
                self.request_count+=1
                raise FMPError('rate_limited')
        client=Client()
        universe=pd.DataFrame({'stable_id':['AAA'],'symbol':['AAA'],'universe_order':[0]})
        with tempfile.TemporaryDirectory() as directory,patch('market_data.universe.time.sleep'):
            metadata=fetch_unbalanced_panel(client,universe,output_dir=directory,start='2020-04-09',end='2020-04-13',pause_seconds=0,max_retries=1)
            self.assertEqual(client.request_count,2)
            self.assertEqual(metadata['coverage'][0]['status'],'rate_limited')
            self.assertEqual(metadata['coverage'][0]['request_attempts'],2)


if __name__=='__main__':unittest.main()

"""Availability, fit separation, temporal purging and clustered resampling."""
from dataclasses import replace
import unittest
import numpy as np
import pandas as pd
from hedging_harness.feature_models import (
    PRICE_FEATURES, MARKET_FEATURES, close_cutoffs, design_matrix,
    fit_log_variance_ridge, price_market_features, release_aware_asof, filing_balance_sheet_ratios,
)
from hedging_harness.risk_models import RiskProtocol, chronological_nonoverlap, moving_block_mean_interval, variance_forecasts


class FeatureModelTests(unittest.TestCase):
    def setUp(self):
        rng=np.random.default_rng(44)
        self.dates=pd.bdate_range('2016-01-01',periods=180)
        self.prices=pd.DataFrame(100*np.exp(np.cumsum(rng.normal(0,.01,(180,3)),axis=0)),index=self.dates,columns=['A','B','C'])
        self.factors=pd.DataFrame(100*np.exp(np.cumsum(rng.normal(0,.008,(180,2)),axis=0)),index=self.dates,columns=['SPY','XLF'])

    def test_release_join_never_uses_a_future_filing(self):
        origins=pd.DataFrame({'symbol':['A','A','A','B'],'origin_at':['2020-02-01T21:00:00Z','2020-02-03T21:00:00Z','2020-05-01T20:00:00Z','2020-02-03T21:00:00Z']})
        releases=pd.DataFrame({'symbol':['A','A'],'period_end':['2019-12-31','2020-03-31'],'available_at':['2020-02-03T22:00:00Z','2020-04-30T18:00:00Z'],'funding':[.7,.6]})
        joined=release_aware_asof(origins,releases,feature_columns=['funding'])
        self.assertTrue(joined['funding'].iloc[:2].isna().all())
        self.assertEqual(joined['funding'].iloc[2],.6)
        self.assertTrue(pd.isna(joined['funding'].iloc[3]))
        earlier=releases.copy();earlier.loc[1,'funding']=999
        other=release_aware_asof(origins,earlier,feature_columns=['funding'])
        pd.testing.assert_frame_equal(joined.iloc[:2],other.iloc[:2])

    def test_older_comparative_cannot_overwrite_newer_known_quarter(self):
        origins=pd.DataFrame({'symbol':['A','A','A'],'origin_at':['2020-05-01T20:00:00Z','2020-05-20T20:00:00Z','2020-06-20T20:00:00Z']})
        releases=pd.DataFrame({
            'symbol':['A','A','A'],
            'available_at':['2020-04-30T18:00:00Z','2020-05-10T18:00:00Z','2020-06-10T18:00:00Z'],
            'period_end':['2020-03-31','2019-12-31','2020-03-31'],
            'assets':[100.,999.,105.],
        })
        joined=release_aware_asof(origins,releases,feature_columns=['assets'])
        np.testing.assert_array_equal(joined['assets'],[100.,100.,105.])
        self.assertTrue(joined['matched_period_end'].eq(pd.Timestamp('2020-03-31')).all())

    def test_same_availability_prefers_newer_period_then_filing_identity(self):
        origins=pd.DataFrame({'symbol':['JPM'],'origin_at':['2012-08-10T20:00:00Z']})
        releases=pd.DataFrame({'symbol':['JPM','JPM'],'period_end':['2012-03-31','2012-06-30'],'available_at':['2012-08-10T20:00:00Z']*2,'filed':['2012-08-09']*2,'accn':['001','002'],'f':[1.,2.]})
        joined=release_aware_asof(origins,releases,feature_columns=['f'])
        self.assertEqual(joined.loc[0,'f'],2.)
        self.assertEqual(joined.loc[0,'matched_period_end'],pd.Timestamp('2012-06-30'))

    def test_unknown_timezone_or_duplicate_release_rejected(self):
        origins=pd.DataFrame({'symbol':['A'],'origin_at':['2020-02-03T21:00:00Z']})
        releases=pd.DataFrame({'symbol':['A'],'available_at':['2020-02-01'],'f':[1.]})
        with self.assertRaises(ValueError):release_aware_asof(origins,releases,feature_columns=['f'])
        releases['available_at']='2020-02-01T00:00:00Z'
        with self.assertRaises(ValueError):release_aware_asof(origins,pd.concat([releases,releases]),feature_columns=['f'])

    def test_stale_release_becomes_unknown_not_zero(self):
        origins=pd.DataFrame({'symbol':['A'],'origin_at':['2021-02-03T21:00:00Z']})
        releases=pd.DataFrame({'symbol':['A'],'available_at':['2020-02-01T00:00:00Z'],'f':[7.]})
        joined=release_aware_asof(origins,releases,feature_columns=['f'],max_age_days=180)
        self.assertTrue(pd.isna(joined.loc[0,'f']))

    def test_recent_republication_does_not_refresh_old_period_age(self):
        origins=pd.DataFrame({'symbol':['A'],'origin_at':['2020-10-01T20:00:00Z']})
        releases=pd.DataFrame({'symbol':['A'],'period_end':['2019-12-31'],'available_at':['2020-09-20T20:00:00Z'],'f':[7.]})
        joined=release_aware_asof(origins,releases,feature_columns=['f'],max_age_days=180,max_period_age_days=180)
        self.assertTrue(pd.isna(joined.loc[0,'f']))

    def test_future_prices_and_factors_do_not_change_earlier_features(self):
        origin=self.dates[80]
        base=price_market_features(self.prices,self.factors,lookback=20,recent_window=5)
        p=self.prices.copy();p.loc[p.index>origin]*=np.exp(np.arange(99)[:,None]*.03)
        f=self.factors.copy();f.loc[f.index>origin]*=1.8
        altered=price_market_features(p,f,lookback=20,recent_window=5)
        pd.testing.assert_frame_equal(base.loc[base.origin<=origin].reset_index(drop=True),altered.loc[altered.origin<=origin].reset_index(drop=True))

    def test_standardizer_is_fit_only_on_the_supplied_train_sample(self):
        train=pd.DataFrame({'x':[1.,2.,3.,4.],'z':[5.,4.,3.,2.]})
        model=fit_log_variance_ridge(train,[.01,.02,.03,.04],alpha=1)
        np.testing.assert_allclose(model.means,[2.5,3.5])
        np.testing.assert_allclose(model.scales,train.std(ddof=0))
        old=model.means.copy()
        model.predict(pd.DataFrame({'x':[10000.],'z':[-10000.]}))
        np.testing.assert_array_equal(model.means,old)
        self.assertEqual(model.training_rows,4)
        self.assertTrue(np.isfinite(model.predict(train)).all())
        with self.assertRaises(ValueError):model.predict(train.assign(x=np.nan))

    def test_split_targets_are_purged_and_nonoverlapping(self):
        protocol=RiskProtocol(train_start='2016-01-01',train_end='2016-03-31',validation_start='2016-04-01',validation_end='2016-05-31',test_start='2016-06-01',test_end='2016-12-31',lookback=20,recent_window=5,horizons=(5,10))
        panel=chronological_nonoverlap(variance_forecasts(self.prices,protocol),protocol)
        for split,horizon in panel[['split','horizon']].drop_duplicates().itertuples(index=False):
            subset=panel.loc[panel.split.eq(split)&panel.horizon.eq(horizon)]
            end=pd.Timestamp(getattr(protocol,split+'_end'))
            self.assertTrue(subset.target_end.le(end).all())
            windows=subset[['origin','target_start','target_end']].drop_duplicates().sort_values('origin')
            self.assertTrue((windows.target_start.iloc[1:].to_numpy()>windows.target_end.iloc[:-1].to_numpy()).all())

    def test_cross_name_average_is_one_date_observation(self):
        frame=pd.DataFrame({'origin':np.repeat(pd.date_range('2020-01-01',periods=20),2),'difference':np.tile([-1.,1.],20)})
        by_date=frame.groupby('origin')['difference'].mean()
        interval=moving_block_mean_interval(by_date.to_numpy(),block_length=4,n_bootstrap=100)
        self.assertEqual(interval['n_dates'],20)
        self.assertEqual(interval['estimate'],0.)
        self.assertEqual(interval['lower'],0.)
        self.assertEqual(interval['upper'],0.)

    def test_filing_ratios_require_vintage_and_preserve_bank_scope_and_unknowns(self):
        snapshots=pd.DataFrame({
            'symbol':['JPM','GS'], 'period_end':['2020-03-31']*2,
            'available_at':['2020-05-01T20:00:00Z']*2,'unit':['USD']*2,
            'same_filing_and_period':[True]*2,'original_vintage_verified':[True]*2,
            'assets':[100.,200.],'liabilities':[80.,180.],
            'cash_and_due_from_banks':[10.,np.nan],'deposits':[60.,30.],
            'deposit_feature_approved_for_issuer':[True,False],
        })
        ratios=filing_balance_sheet_ratios(snapshots)
        np.testing.assert_allclose(ratios['liabilities_assets'],[.8,.9])
        self.assertEqual(ratios.loc[0,'bank_deposits_liabilities'],.75)
        self.assertEqual(ratios.loc[0,'bank_cash_assets'],.1)
        self.assertTrue(pd.isna(ratios.loc[1,'bank_deposits_liabilities']))
        self.assertTrue(pd.isna(ratios.loc[1,'bank_cash_assets']))
        snapshots.loc[0,'original_vintage_verified']=False
        with self.assertRaises(ValueError):filing_balance_sheet_ratios(snapshots)

    def test_close_cutoff_uses_exchange_timezone_across_dst(self):
        cutoffs=close_cutoffs(pd.to_datetime(['2020-01-02','2020-07-02']))
        self.assertEqual(cutoffs[0].hour,21)
        self.assertEqual(cutoffs[1].hour,20)


if __name__=='__main__':unittest.main()

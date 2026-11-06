"""Label, availability, capital and past-only checks for conditional breadth."""
import unittest

import numpy as np
import pandas as pd

from hedging_harness.breadth import (
    block_tail_interval, complete_history_master, fit_calibration,
    fixed_notional_book, historical_equity_diagnostic, nested_compositions,
    simulate_master,
)


class BreadthTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.dates=pd.bdate_range("2019-01-02",periods=650)
        returns=np.random.default_rng(51).normal(.0001,.01,(650,4))
        cls.prices=pd.DataFrame(100*np.exp(np.cumsum(returns,axis=0)),index=cls.dates,columns=["A","B","C","D"])
        cls.cutoff=cls.dates[300]
        cls.calibration=fit_calibration(cls.prices,cutoff=cls.cutoff,lookback=60)

    def test_partial_availability_is_explicit_and_no_rows_are_removed(self):
        prices=self.prices.copy()
        prices.loc[prices.index[:10],"D"]=np.nan
        master=complete_history_master(prices,required_core=("A","B"))
        self.assertEqual(master.names,("A","B","C"))
        self.assertEqual(master.excluded_names,("D",))
        self.assertEqual(len(master.prices),len(prices))
        self.assertEqual(len(master.availability_audit),4)
        self.assertEqual(master.availability_audit.loc["D","missing_observations"],10)
        self.assertIn("no_fill",master.availability_audit.loc["D","reason"])
        self.assertEqual(prices["D"].isna().sum(),10)

    def test_incomplete_required_core_is_not_silently_dropped(self):
        prices=self.prices.copy()
        prices.loc[prices.index[100],"A"]=np.nan
        with self.assertRaisesRegex(ValueError,"required core"):
            complete_history_master(prices,required_core=("A","B"))

    def test_master_subset_preserves_actual_named_paths_in_requested_order(self):
        master=simulate_master(self.calibration,n_paths=20,seed=71,steps=5)
        subset=master.subset(("D","A"))
        self.assertEqual(subset.shape,(20,6,2))
        np.testing.assert_array_equal(subset[:,:,0],master.paths[:,:,3])
        np.testing.assert_array_equal(subset[:,:,1],master.paths[:,:,0])
        smaller=master.subset(("A",))
        larger=master.subset(("A","B","C"))
        np.testing.assert_array_equal(smaller[:,:,0],larger[:,:,0])
        with self.assertRaises(ValueError):master.subset(("MISSING",))
        with self.assertRaises(ValueError):master.subset(("A","A"))

    def test_total_notional_is_constant_across_breadths(self):
        for size in (2,3,4):
            book=fixed_notional_book(tuple(self.prices.columns[:size]),self.calibration,total_notional=300000.)
            self.assertAlmostEqual(sum(book.notionals),300000.)
            np.testing.assert_allclose(book.notionals,np.repeat(300000./size,size))

    def test_seeded_compositions_are_reproducible_nested_and_not_outcome_selected(self):
        first=nested_compositions(tuple(self.prices.columns),sizes=(2,3,4),seeds=(11,12))
        second=nested_compositions(tuple(self.prices.columns),sizes=(2,3,4),seeds=(11,12))
        self.assertEqual(first,second)
        self.assertEqual(first["canonical"][2],("A","B"))
        for chain in first.values():
            self.assertEqual(chain[3][:2],chain[2])
            self.assertEqual(chain[4][:3],chain[3])
        with self.assertRaises(ValueError):
            nested_compositions(tuple(self.prices.columns),sizes=(3,2))

    def test_calibration_never_reads_future_prices(self):
        changed=self.prices.copy()
        changed.loc[changed.index>self.cutoff]*=3.
        other=fit_calibration(changed,cutoff=self.cutoff,lookback=60)
        pd.testing.assert_series_equal(self.calibration.annual_volatilities,other.annual_volatilities)
        pd.testing.assert_frame_equal(self.calibration.correlation,other.correlation)
        self.assertEqual(self.calibration.calibration_data_sha256,other.calibration_data_sha256)
        self.assertLessEqual(self.calibration.last_observation,self.cutoff)
        self.assertEqual(self.calibration.return_observations,60)

    def test_shrinkage_and_prespecified_common_shock_stress_remain_psd(self):
        base=simulate_master(self.calibration,n_paths=20,seed=71,steps=5)
        stress=simulate_master(self.calibration,n_paths=20,seed=71,steps=5,
                               scenario="synthetic_common_shock_stress",stress_mix=.4)
        self.assertGreater(np.linalg.eigvalsh(base.correlation).min(),-1e-10)
        self.assertGreater(np.linalg.eigvalsh(stress.correlation).min(),-1e-10)
        np.testing.assert_allclose(np.diag(stress.correlation),1.)
        self.assertTrue((stress.correlation.to_numpy()>=base.correlation.to_numpy()-1e-12).all())
        self.assertNotEqual(base.scenario_id,stress.scenario_id)

    def test_historical_diagnostics_hold_capital_and_nonoverlapping_targets(self):
        compositions=nested_compositions(tuple(self.prices.columns),sizes=(2,4),seeds=(13,))
        study=historical_equity_diagnostic(
            self.prices,compositions,test_start=self.dates[400],test_end=self.dates[-1],
            n_bootstrap=20,industries={"A":"banks","B":"banks","C":"insurance","D":"payments"},
        )
        self.assertTrue(study["periods"].total_notional.eq(300000.).all())
        for _,group in study["periods"].groupby(["composition","breadth"]):
            group=group.sort_values("origin")
            self.assertTrue((group.target_start>group.origin).all())
            self.assertTrue((group.target_start.iloc[1:].to_numpy()>group.target_end.iloc[:-1].to_numpy()).all())
        sums=study["tail_group_contributions"].groupby(["composition","breadth"]).portfolio_tail_loss_contribution.sum()
        expected=study["summary"].set_index(["composition","breadth"]).loss_es95
        np.testing.assert_allclose(sums.sort_index(),expected.sort_index(),atol=1e-8)
        self.assertIn("no derivatives",study["convention"])

    def test_constant_historical_tail_has_exact_block_interval(self):
        result=block_tail_interval(np.repeat(-10.,20),n_bootstrap=30,seed=9)
        self.assertEqual(result["estimate"],10.)
        self.assertEqual(result["lower"],10.)
        self.assertEqual(result["upper"],10.)
        self.assertEqual(result["tail_observations"],1)
        self.assertEqual(result,block_tail_interval(np.repeat(-10.,20),n_bootstrap=30,seed=9))


if __name__=="__main__":unittest.main()

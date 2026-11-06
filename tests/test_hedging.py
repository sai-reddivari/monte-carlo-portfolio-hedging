"""Financial invariants and meaningful numerical checks (standard unittest)."""
from dataclasses import replace
from pathlib import Path
import unittest
import numpy as np

from hedging_harness import Book, load_study, simulate_paths, hedge, summarize
from hedging_harness.legacy import call_price, call_delta

ROOT = Path(__file__).resolve().parents[1]


class HedgeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.book, cls.cfg = load_study(ROOT / "config/illustrative_study.json")
        cls.paths = simulate_paths(cls.book, **cls.cfg["scenario"], n_paths=1000, seed=81)

    def test_known_black_scholes_benchmark(self):
        self.assertAlmostEqual(float(call_price(100,100,1,.05,.2)),10.450583572185565,places=10)
        self.assertEqual(float(call_price(110,100,0,.05,.2)),10)

    def test_one_step_hand_accounting(self):
        b = Book(("A",),(100.,),(100.,),(100.,),(.2,),steps=1,sessions_per_year=1,rate=.05)
        p = np.array([[[100.],[120.]],[[100.],[80.]]])
        d = float(call_delta(100,100,1,.05,.2))
        premium = float(call_price(100,100,1,.05,.2))
        cost=.001
        expected=(premium-100*d-100*d*cost)*np.exp(.05)+d*p[:,-1,0]*(1-cost)-np.maximum(p[:,-1,0]-100,0)
        r=hedge(b,p,cost_bps=10)
        np.testing.assert_allclose(r.terminal_pnl[:,0],expected,atol=1e-12)

    def test_cash_and_mark_reconciliation(self):
        r=hedge(self.book,self.paths,hedge_every=5,cost_bps=7,audit_path=0)
        for name, frame in r.ledger.groupby("name",sort=False):
            expected=(frame.premium_received+frame.interest+frame.stock_cashflow-frame.transaction_cost-frame.payoff_paid).cumsum()
            np.testing.assert_allclose(frame.cash,expected,atol=1e-9)
            np.testing.assert_allclose(frame.net_value,frame.cash+frame.stock_value-frame.option_liability,atol=1e-10)
            self.assertEqual(frame.iloc[-1].shares_after,0)
            self.assertEqual(frame.iloc[-1].option_liability,0)
            self.assertAlmostEqual(frame.iloc[0].net_value,-frame.iloc[0].transaction_cost,places=9)

    def test_transaction_costs_include_financing(self):
        gross=hedge(self.book,self.paths,cost_bps=0)
        net=hedge(self.book,self.paths,cost_bps=8)
        np.testing.assert_allclose(gross.terminal_pnl-net.terminal_pnl,net.financed_costs,atol=2e-9)
        self.assertTrue(np.all(net.financed_costs>=net.nominal_costs))

    def test_initial_only_closed_form(self):
        b=self.book
        r=hedge(b,self.paths,hedge_every=None)
        s=np.asarray(b.spots); k=np.asarray(b.strikes); v=np.asarray(b.pricing_vols)
        d=b.units*call_delta(s,k,b.maturity,b.rate,v)
        cash=b.units*call_price(s,k,b.maturity,b.rate,v)-d*s
        terminal=self.paths[:,-1,:]
        expected=cash*np.exp(b.rate*b.maturity)+d*terminal-b.units*np.maximum(terminal-k,0)
        np.testing.assert_allclose(r.terminal_pnl,expected,atol=2e-9)

    def test_cash_account_additivity(self):
        joint=hedge(self.book,self.paths,cost_bps=5)
        pieces=[]
        for i,name in enumerate(self.book.names):
            b=replace(self.book,names=(name,),spots=(self.book.spots[i],),strikes=(self.book.strikes[i],),
                notionals=(self.book.notionals[i],),pricing_vols=(self.book.pricing_vols[i],))
            pieces.append(hedge(b,self.paths[:,:,i:i+1],cost_bps=5).terminal_pnl[:,0])
        np.testing.assert_allclose(joint.terminal_pnl.sum(axis=1),np.sum(pieces,axis=0),atol=1e-10)

    def test_no_future_information_in_trades(self):
        changed=self.paths.copy()
        changed[:,11:,:]*=1.4
        a=hedge(self.book,self.paths,audit_path=0).ledger
        b=hedge(self.book,changed,audit_path=0).ledger
        np.testing.assert_array_equal(a.loc[a.step<=10,"shares_after"],b.loc[b.step<=10,"shares_after"])

    def test_hedge_vol_does_not_change_premium(self):
        a=hedge(self.book,self.paths,audit_path=0).ledger
        b=hedge(self.book,self.paths,hedge_vols=np.asarray(self.book.pricing_vols)*.8,audit_path=0).ledger
        np.testing.assert_array_equal(a.premium_received,b.premium_received)
        self.assertFalse(np.allclose(a.shares_after,b.shares_after))

    def test_zero_vol_forward_paths_have_no_discounted_hedge_gain(self):
        p=simulate_paths(self.book,[0,0,0],np.eye(3),n_paths=2)
        a=hedge(self.book,p,hedge_every=1)
        b=hedge(self.book,p,hedge_every=None)
        np.testing.assert_allclose(a.terminal_pnl,b.terminal_pnl,atol=2e-9)

    def test_seed_and_correlations(self):
        corr=np.asarray(self.cfg["scenario"]["correlation"])
        again=simulate_paths(self.book,**self.cfg["scenario"],n_paths=1000,seed=81)
        np.testing.assert_array_equal(again,self.paths)
        r=np.diff(np.log(self.paths),axis=1).reshape(-1,3)
        np.testing.assert_allclose(np.corrcoef(r.T),corr,atol=.015)

    def test_singular_correlation_accepted(self):
        p=simulate_paths(self.book,[.2,.2,.2],np.ones((3,3)),n_paths=20)
        np.testing.assert_allclose(p[:,:,0],p[:,:,1],atol=1e-5)

    def test_daily_reduces_correct_model_error(self):
        p=simulate_paths(self.book,**self.cfg["scenario"],n_paths=12000,seed=503)
        daily=hedge(self.book,p)
        weekly=hedge(self.book,p,hedge_every=5)
        d=summarize(daily).loc["Portfolio"]
        w=summarize(weekly).loc["Portfolio"]
        self.assertLess(d.pnl_std,w.pnl_std*.7)
        self.assertLess(abs(d.mean_pnl),5*d.mean_se)

    def test_bad_inputs_fail_explicitly(self):
        for corr in [np.zeros((3,3)),[[1,2,0],[2,1,0],[0,0,1]],np.eye(2)]:
            with self.assertRaises(ValueError):simulate_paths(self.book,[.2]*3,corr,n_paths=2)
        for interval in [0,-1,1.5,True]:
            with self.assertRaises(ValueError):hedge(self.book,self.paths,hedge_every=interval)
        with self.assertRaises(ValueError):hedge(self.book,self.paths,cost_bps=-1)
        with self.assertRaises(ValueError):hedge(self.book,self.paths,hedge_vols=[0,.2,.2])
        with self.assertRaises(ValueError):hedge(self.book,self.paths[:,1:,:])
        with self.assertRaises(ValueError):replace(self.book,notionals=(100,))


if __name__=="__main__":
    unittest.main()

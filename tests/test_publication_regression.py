"""Known-value pricing and actual frozen-output regressions, not implementation mirrors."""
import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile

import numpy as np
import pandas as pd

from hedging_harness.pricing import bs_price,bs_greeks
from hedging_harness.legacy_methods import one_step_prices,compare_methods,_reference

ROOT=Path(__file__).resolve().parents[1]


def test_known_call_and_put_greeks():
    call=bs_greeks(100.,100.,1.,.05,.2,'call')
    expected=dict(delta=.6368306511756191,gamma=.018762017345846895,
                  vega=37.52403469169379,theta=-6.414027546438197,rho=53.232481545376345)
    for key,value in expected.items():np.testing.assert_allclose(call[key],value,rtol=1e-12,atol=0)
    np.testing.assert_allclose(bs_price(100.,100.,1.,.05,.2,'put'),5.573526022256971,rtol=1e-12,atol=0)
    np.testing.assert_allclose(bs_greeks(100.,100.,1.,.05,.2,'put')['delta'],call['delta']-1,rtol=1e-12,atol=0)


def test_one_step_snippet_matches_original_source_with_explicit_context():
    source=subprocess.check_output(['git','show','pre-refactor:MonteCarlo_Functions/MonteCarlo_OneStepExactPrices.py'],cwd=ROOT,text=True)
    ns=_reference(100.,100.,1.,.05,.2,1995);seen={};original=ns['mc_price_from_ST']
    def capture(ST,K,T,r,kind):
        value=original(ST,K,T,r,kind);seen[kind]=value;return value
    ns['mc_price_from_ST']=capture
    with contextlib.redirect_stdout(io.StringIO()):
        exec(compile(source,'frozen-one-step','exec'),ns)
        result=one_step_prices(100.,100.,1.,.05,.2)
    for row in result.itertuples():np.testing.assert_array_equal([row.price,row.standard_error],seen[row.option])


def test_method_snippet_requires_and_uses_explicit_missing_crr_dependency():
    source=subprocess.check_output(['git','show','pre-refactor:MonteCarlo_Functions/MonteCarlo_MethodComparison.py'],cwd=ROOT,text=True)
    ns=_reference(100.,100.,1.,.05,.2,1995)
    # A dependency sentinel tests forwarding without inventing the missing CRR implementation.
    def provider(S,K,T,r,sigma,steps,kind):
        assert steps==1000
        return 123. if kind=='call' else 456.
    ns['crr_price']=provider
    with contextlib.redirect_stdout(io.StringIO()):
        exec(compile(source,'frozen-method-comparison','exec'),ns)
        current=compare_methods(100.,100.,1.,.05,.2,crr_price=provider)
    pd.testing.assert_frame_equal(ns['routes'],current['routes'],check_exact=True)
    pd.testing.assert_frame_equal(ns['S_T'],current['terminal_prices'],check_exact=True)


def test_fast_publication_subset_against_full_precision_manifest():
    from hedging_harness.reproduction import reproduce
    sys.path.insert(0,str(ROOT/'scripts'))
    from diff_manifests import compare
    before=json.loads((ROOT/'results/manifest_pre_refactor.json').read_text())
    with tempfile.TemporaryDirectory(prefix='hedging-regression-',dir='/tmp') as temp:
        after=reproduce(Path(temp)/'run',fast=True)
        summary,errors=compare(before,after,allow_subset=True)
        assert summary['experiments']==3
        assert summary['passed'],errors

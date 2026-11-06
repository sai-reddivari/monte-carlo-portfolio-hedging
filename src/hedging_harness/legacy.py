"""Reuse the consolidated Black-Scholes module and the exact-GBM fragment.

The historical MethodComparison driver is not run. The exact-path source still
expects its NumPy import to be supplied by the calling notebook or this adapter.
"""
from pathlib import Path
import runpy

import numpy as np
from scipy.stats import norm

from BlackScholes_Functions.BlackScholes_D1D2_Price_Payoff_Greeks import (
    bs_d1_d2 as _d1_d2,
    bs_price as _price,
    initial_exposures,
)

ROOT = Path(__file__).resolve().parents[2]
SOURCES = (
    ROOT / "src/BlackScholes_Functions/BlackScholes_D1D2_Price_Payoff_Greeks.py",
    ROOT / "src/MonteCarlo_Functions/MonteCarlo_ExactPathwayGeneration.py",
)
exact_paths = runpy.run_path(str(SOURCES[1]), init_globals={"np": np})["exact_paths"]


def call_price(spot, strike, tau, rate, volatility):
    """Existing Black–Scholes formula, with explicit expiry handling."""
    if tau <= 0:
        return np.maximum(np.asarray(spot) - strike, 0.0)
    return _price(spot, strike, tau, rate, volatility, "call")


def call_delta(spot, strike, tau, rate, volatility):
    """Analytic call delta. The ledger never rebalances at expiry."""
    if tau <= 0:
        return np.where(np.asarray(spot) > strike, 1.0,
                        np.where(np.asarray(spot) < strike, 0.0, 0.5))
    return norm.cdf(_d1_d2(spot, strike, tau, rate, volatility)[0])

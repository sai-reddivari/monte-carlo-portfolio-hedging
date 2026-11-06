import numpy as np
import pandas as pd
from scipy.stats import norm

def bs_d1_d2(S, K, T, r, sigma):
    sqrtT = np.sqrt(T)
    d1 = (np.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * sqrtT)
    return d1, d1 - sigma * sqrtT

def bs_price(S, K, T, r, sigma, kind='call'):
    '''
    S: spot price
    K: strike price
    T: time to expiry T - t (in years)
    r: risk-free interest rate (annualized)
    sigma: volatility (annualized)
    kind: 'call' or 'put'
    '''
    d1, d2 = bs_d1_d2(S, K, T, r, sigma)
    disc_K = K * np.exp(-r * T)                    # present value of the strike
    if kind == 'call':
        return S * norm.cdf(d1) - disc_K * norm.cdf(d2)
    if kind == 'put':
        return disc_K * norm.cdf(-d2) - S * norm.cdf(-d1)
    raise ValueError(f"kind must be 'call' or 'put', got {kind!r}")



def bs_payoff(ST, K, kind='call'):
    # Vanilla payoff at expiry: max(S_T - K, 0) for a call, max(K - S_T, 0) for a put.
    if kind == 'call':
        return np.maximum(ST - K, 0.0)
    if kind == 'put':
        return np.maximum(K - ST, 0.0)
    raise ValueError(f"kind must be 'call' or 'put', got {kind!r}")

def bs_greeks(S, K, T, r, sigma, kind='call'):
    '''
    Analytic Black-Scholes greeks, the benchmark for the Monte Carlo greeks.
    Returns dict(delta, gamma, vega, theta, rho), each per unit change: vega per 1.00 of sigma,
    rho per 1.00 of r, theta per year. Theta is dV/dt, so it is negative for a call.
    '''
    d1, d2 = bs_d1_d2(S, K, T, r, sigma)
    sqrtT, disc_K, pdf = np.sqrt(T), K * np.exp(-r * T), norm.pdf(d1)
    gamma = pdf / (S * sigma * sqrtT)              # same for call and put
    vega = S * sqrtT * pdf                         # same for call and put
    decay = -sigma * S * pdf / (2 * sqrtT)         # theta term shared by call and put
    if kind == 'call':
        return dict(delta=norm.cdf(d1), gamma=gamma, vega=vega,
                    theta=decay - r * disc_K * norm.cdf(d2),
                    rho=T * disc_K * norm.cdf(d2))
    if kind == 'put':
        return dict(delta=norm.cdf(d1) - 1, gamma=gamma, vega=vega,
                    theta=decay + r * disc_K * norm.cdf(-d2),
                    rho=-T * disc_K * norm.cdf(-d2))
    raise ValueError(f"kind must be 'call' or 'put', got {kind!r}")


def initial_exposures(book):
    """Opening short-call exposures, in share-equivalent option units."""
    s, k, vol, q = map(
        np.asarray, (book.spots, book.strikes, book.pricing_vols, book.units)
    )
    greeks = bs_greeks(s, k, book.maturity, book.rate, vol, kind="call")
    return pd.DataFrame(dict(
        name=book.names,
        short_call_units=q,
        initial_premium=q * bs_price(s, k, book.maturity, book.rate, vol, kind="call"),
        hedge_shares=q * greeks["delta"],
        option_dollar_delta=-q * greeks["delta"] * s,
        option_gamma_pnl_for_1pct_move=-0.5 * q * greeks["gamma"] * (0.01 * s) ** 2,
        option_vega_per_vol_point=-q * greeks["vega"] * 0.01,
    )).set_index("name")

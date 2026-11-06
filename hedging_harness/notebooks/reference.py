"""Shared original investigation mechanics; no import-time experiments."""
from IPython.display import display

def reference_inputs(S0, K, T, r, sigma, seed):
    import numpy as np
    import pandas as pd
    import matplotlib.pyplot as plt
    from scipy.stats import norm
    from scipy.integrate import quad
    from scipy.stats import binom


    def _d1_d2(S, K, T, r, sigma):
        # d1 and d2 as in §1.4 (Lecture 1, p.43). np.log / np.sqrt rather than math.*, so that
        # S, sigma, T and r may be arrays when the data are varied in the parameter studies.
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
        d1, d2 = _d1_d2(S, K, T, r, sigma)
        disc_K = K * np.exp(-r * T)                    # present value of the strike
        if kind == 'call':
            return S * norm.cdf(d1) - disc_K * norm.cdf(d2)
        if kind == 'put':
            return disc_K * norm.cdf(-d2) - S * norm.cdf(-d1)
        raise ValueError(f"kind must be 'call' or 'put', got {kind!r}")


    def bs_greeks(S, K, T, r, sigma, kind='call'):
        '''
        Analytic Black-Scholes greeks, the benchmark for the Monte Carlo greeks.
        Returns dict(delta, gamma, vega, theta, rho), each per unit change: vega per 1.00 of sigma,
        rho per 1.00 of r, theta per year. Theta is dV/dt, so it is negative for a call.
        '''
        d1, d2 = _d1_d2(S, K, T, r, sigma)
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


    def payoff(ST, K, kind='call'):
        # Vanilla payoff at expiry: max(S_T - K, 0) for a call, max(K - S_T, 0) for a put.
        if kind == 'call':
            return np.maximum(ST - K, 0.0)
        if kind == 'put':
            return np.maximum(K - ST, 0.0)
        raise ValueError(f"kind must be 'call' or 'put', got {kind!r}")


    # Sample data from the exam brief (K = strike, T = time to expiry T - t)


    d1, d2 = _d1_d2(S0, K, T, r, sigma)
    C, P = bs_price(S0, K, T, r, sigma, 'call'), bs_price(S0, K, T, r, sigma, 'put')


    def p_tilde(S_prime, S, T, r, sigma):
        # Risk-neutral lognormal transition density of S_T = S_prime, given S_t = S (§1.3)
        bracket = np.log(S / S_prime) + (r - 0.5 * sigma**2) * T
        return np.exp(-bracket**2 / (2 * sigma**2 * T)) / (sigma * S_prime * np.sqrt(2 * np.pi * T))


    # For each option: the payoff, and the range of S' where it is non-zero (§1.4)
    contracts = {'call': (lambda s: s - K, K, np.inf),
                 'put':  (lambda s: K - s, 0.0, K)}

    rows = {}
    for kind, (pay, lower, upper) in contracts.items():
        expected, _ = quad(lambda s: p_tilde(s, S0, T, r, sigma) * pay(s), lower, upper)
        rows[kind] = {
            'E^Q[payoff], integral': expected,
            'price, discounted integral': np.exp(-r * T) * expected,
            'price, closed form': bs_price(S0, K, T, r, sigma, kind),
        }

    benchmark = pd.DataFrame(rows).T
    benchmark['difference'] = benchmark['price, discounted integral'] - benchmark['price, closed form']

    print(f"Black-Scholes closed form:   call C = {C:.4f}   put P = {P:.4f}\n")
    print(f"d1 = {d1:.4f}   d2 = {d2:.4f}   N(d1) = {norm.cdf(d1):.5f}   N(d2) = {norm.cdf(d2):.5f}\n")
    print(benchmark.to_string(float_format=lambda x: f'{x:.6f}' if abs(x) > 1e-4 else f'{x:.1e}'))
    print(f"\nPut-call parity:  C - P = {C - P:.6f}   S - K e^(-rT) = {S0 - K * np.exp(-r * T):.6f}")


    SEED = seed                                        

    #K, S0, r, sigma, T defined already in sample data above 

    # payoff(ST, K, kind) is defined with the Black-Scholes functions in §1.4


    def simulate_terminal_exact(S0, r, sigma, T, n_paths, rng): #GBM assumptions one step simulation to maturity #S_T = S_0 · exp((r − σ²/2)T + σ√T · Z),Z ~ N(0,1)
        phi = rng.standard_normal(n_paths)
        return S0 * np.exp((r - 0.5 * sigma**2) * T + sigma * np.sqrt(T) * phi)


    def mc_price_from_ST(ST, K, T, r, kind='call'): #MC payoff determined from payoff across average of terminal stock prices, discounted to present value
                                                     #standard error equal to sample standard deviation from the mean / sqrt(N)
        Y = np.exp(-r * T) * payoff(ST, K, kind)
        return Y.mean(), Y.std(ddof=1) / np.sqrt(Y.size)


    def euler_paths(S0, r, sigma, T, Z):
        # Euler-Maruyama (§1.8): S_{n+1} = S_n + r S_n dt + sigma S_n dW_n.
        # Z holds the standard normal draws: one row per path, one column per time step.
        n_paths, n_steps = Z.shape
        dt = T / n_steps
        dW = np.sqrt(dt) * Z                                  # Brownian increments, variance dt
        S = np.empty((n_paths, n_steps + 1))
        S[:, 0] = S0
        for n in range(n_steps):                              # loop over time; every path moves at once
            S[:, n + 1] = S[:, n] + r * S[:, n] * dt + sigma * S[:, n] * dW[:, n]
        return S


    def milstein_paths(S0, r, sigma, T, Z):
        # Milstein (§1.8): the Euler step plus the Ito-Taylor term 1/2 b b' (dW^2 - dt),
        # which for geometric Brownian motion (b = sigma S, b' = sigma) is 1/2 sigma^2 S_n (dW_n^2 - dt).
        n_paths, n_steps = Z.shape
        dt = T / n_steps
        dW = np.sqrt(dt) * Z
        S = np.empty((n_paths, n_steps + 1))
        S[:, 0] = S0
        for n in range(n_steps):
            Sn, dWn = S[:, n], dW[:, n]
            S[:, n + 1] = Sn + r * Sn * dt + sigma * Sn * dWn + 0.5 * sigma**2 * Sn * (dWn**2 - dt)
        return S


    def exact_paths(S0, r, sigma, T, Z):
        # Exact solution of geometric Brownian motion (§1.8): ln S moves by (r - sigma^2/2) dt + sigma dW
        # on every step, whatever the step size, so add up the log-steps along each path and exponentiate.
        n_paths, n_steps = Z.shape
        dt = T / n_steps
        log_paths = np.cumsum((r - 0.5 * sigma**2) * dt + sigma * np.sqrt(dt) * Z, axis=1)
        return np.hstack([np.full((n_paths, 1), S0), S0 * np.exp(log_paths)])


    SCHEMES = {'euler': euler_paths, 'milstein': milstein_paths, 'exact': exact_paths}


    def simulate_paths(S0, r, sigma, T, n_steps, n_paths, rng, scheme='euler', Z=None):
        # Single entry point for the pricing code: draw the normals from the seeded generator
        # (unless Z is supplied, e.g. -Z for antithetic paths), then run the chosen scheme.
        # Returns an array of shape (n_paths, n_steps + 1); column 0 is S0.
        if scheme not in SCHEMES:
            raise ValueError(f"scheme must be one of {list(SCHEMES)}, got {scheme!r}")
        if Z is None:
            Z = rng.standard_normal((n_paths, n_steps))
        return SCHEMES[scheme](S0, r, sigma, T, Z)

    return locals()

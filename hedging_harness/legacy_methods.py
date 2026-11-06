"""Original notebook-global examples with explicit numerical arguments.

The original statements are retained inside functions; pricing inputs and RNG
controls are arguments. No globals supplied by a prior notebook are required. The repository never supplied crr_price; the caller must pass that dependency explicitly.
"""
import contextlib
import io
import numpy as np
import pandas as pd
from scipy.stats import binom
from .pricing import bs_payoff as payoff
from .notebooks.reference import reference_inputs


def _reference(S0, K, T, r, sigma, seed):
    with contextlib.redirect_stdout(io.StringIO()):
        return reference_inputs(S0, K, T, r, sigma, seed)




def one_step_prices(S0, K, T, r, sigma, *, n_paths=100_000, seed=1995):
    ns = _reference(S0, K, T, r, sigma, seed)
    np = ns['np']; simulate_terminal_exact = ns['simulate_terminal_exact']; mc_price_from_ST = ns['mc_price_from_ST']; bs_price = ns['bs_price']
    SEED = seed
    estimates = []
    # First Monte Carlo prices: exact one-step scheme, N = 100,000, seeded, against Black-Scholes
    random_number = np.random.default_rng(SEED)
    ST = simulate_terminal_exact(S0, r, sigma, T, n_paths, random_number    ) 
    for kind in ('call', 'put'):
        option_price, standard_error = mc_price_from_ST(ST, K, T, r, kind)
        bs = bs_price(S0, K, T, r, sigma, kind)
        print(f"{kind:4s}  MC {option_price:.4f} +- {standard_error:.4f}   95% CI [{option_price - 1.96*standard_error:.4f}, {option_price + 1.96*standard_error:.4f}]"
              f"   BS {bs:.4f}   |error|/SE {abs(option_price - bs)/standard_error:.2f}")

        estimates.append(dict(option=kind, price=option_price, standard_error=standard_error, closed_form=bs))

    return pd.DataFrame(estimates)


def compare_methods(S0, K, T, r, sigma, *, crr_price, n_paths=100_000, n_steps=252, seed=1995):
    ns = _reference(S0, K, T, r, sigma, seed)
    SEED = seed
    euler_paths = ns['euler_paths']
    milstein_paths = ns['milstein_paths']
    exact_paths = ns['exact_paths']
    bs_price = ns['bs_price']
    rows = ns['rows']
    mc_price_from_ST = ns['mc_price_from_ST']
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


    # The three schemes on the same random draws: 5 paths, 252 daily steps
    Z = np.random.default_rng(SEED).standard_normal((5, 252))
    S_T = pd.DataFrame({name: f(S0, r, sigma, T, Z)[:, -1] for name, f in SCHEMES.items()})
    S_T['Euler - exact'] = S_T['euler'] - S_T['exact']
    S_T['Milstein - exact'] = S_T['milstein'] - S_T['exact']
    print("Terminal stock price S_T on five paths, all three schemes driven by the same draws:\n")
    print(S_T.round(4).to_string())


    N = n_paths                          # paths; daily steps for the time-stepping schemes
    results = []
    for kind in ('call', 'put'):
        results.append((kind, 'price, closed form', bs_price(S0, K, T, r, sigma, kind), np.nan))
        results.append((kind, 'Numerical integration of the risk-neutral integral',
            rows[kind]['price, discounted integral'], np.nan))
        results.append((kind, 'Binomial tree (CRR), 1000 steps', crr_price(S0, K, T, r, sigma, 1000, kind), np.nan))

        for scheme, steps in (('exact', 1), ('exact', n_steps), ('euler', n_steps), ('milstein', n_steps)):
            paths = simulate_paths(S0, r, sigma, T, steps, N, np.random.default_rng(SEED), scheme)
            price, se = mc_price_from_ST(paths[:, -1], K, T, r, kind)
            results.append((kind, f'Monte Carlo, {scheme} scheme, {steps} step' + ('s' if steps > 1 else ''), price, se))



    routes = pd.DataFrame(results, columns=['option', 'method', 'price', 'standard error']).set_index(['option', 'method'])
    benchmark_method = 'price, closed form'
    benchmark_price = routes.xs(benchmark_method, level='method')['price']
    routes['error vs benchmark'] = routes['price'] - routes.index.get_level_values('option').map(benchmark_price)
    routes['|error|/SE'] = routes['error vs benchmark'].abs() / routes['standard error']
    routes.round(4).fillna('–')                       # display copy only; routes itself keeps its numbers

    return dict(terminal_prices=S_T, routes=routes)

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


N, n_steps = 100_000, 252                          # paths; daily steps for the time-stepping schemes
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

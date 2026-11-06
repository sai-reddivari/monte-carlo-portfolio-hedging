SEED = 1995                                        


def simulate_terminal_exact(S0, r, sigma, T, n_paths, rng): #GBM assumptions one step simulation to maturity #S_T = S_0 · exp((r − σ²/2)T + σ√T · Z),Z ~ N(0,1)
    phi = rng.standard_normal(n_paths)
    return S0 * np.exp((r - 0.5 * sigma**2) * T + sigma * np.sqrt(T) * phi)


def mc_price_from_ST(ST, K, T, r, kind='call'): #MC payoff determined from payoff across average of terminal stock prices, discounted to present value
                                                 #standard error equal to sample standard deviation from the mean / sqrt(N)
    Y = np.exp(-r * T) * payoff(ST, K, kind)
    return Y.mean(), Y.std(ddof=1) / np.sqrt(Y.size)

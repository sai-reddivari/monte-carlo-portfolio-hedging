def exact_paths(S0, r, sigma, T, Z):
    # Exact solution of geometric Brownian motion (§1.8): ln S moves by (r - sigma^2/2) dt + sigma dW
    # on every step, whatever the step size, so add up the log-steps along each path and exponentiate.
    n_paths, n_steps = Z.shape
    dt = T / n_steps
    log_paths = np.cumsum((r - 0.5 * sigma**2) * dt + sigma * np.sqrt(dt) * Z, axis=1)
    return np.hstack([np.full((n_paths, 1), S0), S0 * np.exp(log_paths)])

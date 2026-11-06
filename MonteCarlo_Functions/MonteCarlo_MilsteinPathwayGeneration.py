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

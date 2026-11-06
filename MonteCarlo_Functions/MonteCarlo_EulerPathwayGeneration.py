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

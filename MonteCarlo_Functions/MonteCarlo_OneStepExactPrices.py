# First Monte Carlo prices: exact one-step scheme, N = 100,000, seeded, against Black-Scholes
random_number = np.random.default_rng(SEED)
ST = simulate_terminal_exact(S0, r, sigma, T, 100_000, random_number    ) 
for kind in ('call', 'put'):
    option_price, standard_error = mc_price_from_ST(ST, K, T, r, kind)
    bs = bs_price(S0, K, T, r, sigma, kind)
    print(f"{kind:4s}  MC {option_price:.4f} +- {standard_error:.4f}   95% CI [{option_price - 1.96*standard_error:.4f}, {option_price + 1.96*standard_error:.4f}]"
          f"   BS {bs:.4f}   |error|/SE {abs(option_price - bs)/standard_error:.2f}")

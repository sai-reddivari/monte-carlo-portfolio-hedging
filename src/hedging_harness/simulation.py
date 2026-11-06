"""Simulation interfaces; arithmetic preserved from the frozen core."""
import numpy as np
from .domain import _vol_vector
from .legacy import exact_paths


def _correlation_root(correlation, n):
    corr = np.asarray(correlation, dtype=float)
    if (corr.shape != (n, n) or not np.isfinite(corr).all()
            or not np.allclose(corr, corr.T, atol=1e-12, rtol=0)
            or not np.allclose(np.diag(corr), 1, atol=1e-12, rtol=0)):
        raise ValueError("Correlation must be finite, symmetric, with unit diagonal and one row per name.")
    eig, vec = np.linalg.eigh(corr)
    if eig.min() < -1e-10:
        raise ValueError("Correlation must be positive semidefinite.")
    # Symmetric square root also accepts singular, perfectly correlated cases.
    return (vec * np.sqrt(np.maximum(eig, 0))) @ vec.T



def simulate_paths(book, path_vols, correlation, n_paths=5000, seed=20261105):
    """Return (path, date including inception, asset); risk-neutral drift r.

    Reusing seed pairs policies/scenarios through common normal innovations.
    No antithetic averaging: every row remains an individual trading outcome.
    """
    if not isinstance(n_paths, int) or isinstance(n_paths, bool) or n_paths < 2:
        raise ValueError("n_paths must be an integer >= 2.")
    vols = _vol_vector(path_vols, len(book.names), positive=False)
    root = _correlation_root(correlation, len(book.names))
    z = np.random.default_rng(seed).standard_normal((n_paths, book.steps, len(book.names)))
    z = z @ root.T
    return np.stack([
        exact_paths(s, book.rate, v, book.maturity, z[:, :, i])
        for i, (s, v) in enumerate(zip(book.spots, vols))
    ], axis=-1)


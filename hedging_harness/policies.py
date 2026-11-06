"""Pre-specified stock rebalancing rules for the controlled hedge study."""

from dataclasses import dataclass
import math

import numpy as np


@dataclass(frozen=True)
class HedgePolicy:
    """A rule for resetting the stock hedge to its current delta target.

    ``band`` measures hedge discrepancy as a fraction of positive option units,
    rather than dollars or a percentage of current stock holdings. The maturity
    rule narrows that band by ``sqrt(remaining time / initial maturity)``.
    Inception and terminal liquidation are handled by the accounting engine.
    """

    kind: str = "periodic"
    hedge_every: int | None = 1
    band: float = 0.0
    label: str | None = None

    def __post_init__(self):
        if self.kind not in {"periodic", "delta_band", "maturity_band"}:
            raise ValueError("Unknown hedge-policy kind.")
        if self.hedge_every is not None and (
            not isinstance(self.hedge_every, int)
            or isinstance(self.hedge_every, bool)
            or self.hedge_every < 1
        ):
            raise ValueError("hedge_every must be a positive integer or None.")
        if isinstance(self.band, bool) or not np.isfinite(self.band) or self.band < 0:
            raise ValueError("band must be finite and nonnegative.")
        if self.kind == "periodic" and self.band != 0:
            raise ValueError("A periodic policy does not use a delta band.")
        if self.label is not None and (
            not isinstance(self.label, str) or not self.label.strip()
        ):
            raise ValueError("label must be a nonempty string or None.")

    def threshold(self, remaining_maturity, initial_maturity):
        """Return the current band in per-option delta units."""
        if (
            not np.isfinite(initial_maturity)
            or initial_maturity <= 0
            or not np.isfinite(remaining_maturity)
            or not 0 <= remaining_maturity <= initial_maturity
        ):
            raise ValueError("Maturities must satisfy 0 <= remaining <= initial.")
        if self.kind == "maturity_band":
            return self.band * math.sqrt(remaining_maturity / initial_maturity)
        return self.band

    def rebalance_mask(self, step, remaining_maturity, initial_maturity,
                       delta_target, current_shares, option_units):
        """Select asset/path cells using only the current state."""
        if self.kind == "periodic":
            due = self.hedge_every is not None and step % self.hedge_every == 0
            return np.full(np.shape(delta_target), due, dtype=bool)
        threshold = self.threshold(remaining_maturity, initial_maturity)
        return np.abs(delta_target - current_shares) > threshold * option_units

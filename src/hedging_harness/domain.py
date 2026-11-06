"""Domain interfaces; arithmetic preserved from the frozen core."""
from dataclasses import dataclass
import numpy as np
from .policies import HedgePolicy


@dataclass(frozen=True)
class Book:
    names: tuple[str, ...]
    spots: tuple[float, ...]
    strikes: tuple[float, ...]
    notionals: tuple[float, ...]
    pricing_vols: tuple[float, ...]
    steps: int = 63
    sessions_per_year: int = 252
    rate: float = 0.04

    def __post_init__(self):
        n = len(self.names)
        if not n or len(set(self.names)) != n or "Portfolio" in self.names:
            raise ValueError("Names must be nonempty, unique and not 'Portfolio'.")
        for field in ("spots", "strikes", "notionals", "pricing_vols"):
            value = np.asarray(getattr(self, field), dtype=float)
            if value.shape != (n,) or not np.isfinite(value).all() or (value <= 0).any():
                raise ValueError(f"{field} must have one finite positive value per name.")
        for field in ("steps", "sessions_per_year"):
            value = getattr(self, field)
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                raise ValueError(f"{field} must be a positive integer.")
        if not np.isfinite(self.rate):
            raise ValueError("rate must be finite.")

    @property
    def maturity(self):
        return self.steps / self.sessions_per_year

    @property
    def units(self):
        """Positive short-call share-equivalent units; fractional units allowed.

        Not exchange contract counts: no 100-share multiplier or lot rounding.
        """
        return np.asarray(self.notionals) / np.asarray(self.spots)



def _vol_vector(values, n, positive=True):
    a = np.asarray(values, dtype=float)
    if a.shape != (n,) or not np.isfinite(a).all() or (a < 0).any() or (positive and (a == 0).any()):
        raise ValueError("Volatilities must match the names and be finite and positive (path vols may be zero).")
    return a



@dataclass
class HedgeResult:
    names: tuple[str, ...]
    terminal_pnl: np.ndarray
    nominal_costs: np.ndarray
    financed_costs: np.ndarray
    turnover: np.ndarray
    trade_counts: np.ndarray
    ledger: pd.DataFrame
    peak_borrowing: np.ndarray | None = None
    peak_portfolio_borrowing: np.ndarray | None = None
    scenario_id: str | None = None
    scenario_label: str | None = None
    policy: HedgePolicy | None = None


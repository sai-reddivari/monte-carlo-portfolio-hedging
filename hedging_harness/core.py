"""Compatibility imports for the pre-publication module layout."""
from .domain import Book, HedgeResult, _vol_vector
from .data_loading import load_study
from .simulation import simulate_paths, _correlation_root
from .hedging import hedge
from .evaluation import summarize, paired_difference
from .reporting import provenance
from .pricing import initial_exposures

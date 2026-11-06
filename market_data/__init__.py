"""Bounded, credential-safe market-data access and explicit coverage audits."""
from .fmp import FMPClient, FMPError, load_fmp_api_key
from .coverage import audit_market_data, summarize_prices

__all__ = ["FMPClient", "FMPError", "load_fmp_api_key", "audit_market_data", "summarize_prices"]

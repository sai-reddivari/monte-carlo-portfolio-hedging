"""Small FMP stable-API adapter; successful normalized data only are cached.

No credentials, authenticated URLs, response bodies from errors, or exception
strings from HTTP libraries are included in cache metadata or public errors.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import re
import ssl
import certifi
from typing import Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

KEY_NAMES = ("FMP_API_KEY", "FMP_APIKEY", "FMP_KEY", "FINANCIAL_MODELING_PREP_API_KEY")
PRICE_ENDPOINTS = {
    "split_adjusted": ("historical-price-eod/full", "close"),
    "dividend_adjusted": ("historical-price-eod/dividend-adjusted", "adjClose"),
}
REFERENCE_FIELDS = {
    "company-screener": {"symbol", "companyName", "marketCap", "sector", "industry", "country", "exchange", "exchangeShortName", "volume", "isActivelyTrading", "isEtf", "isFund"},
    "historical-sp500-constituent": {"dateAdded", "addedSecurity", "removedTicker", "removedSecurity", "date", "symbol", "reason"},
    "delisted-companies": {"symbol", "companyName", "exchange", "ipoDate", "delistedDate"},
}
_SYMBOL = re.compile(r"^[A-Z0-9][A-Z0-9.\-^]{0,19}$")


class FMPError(RuntimeError):
    """A sanitized public error with a machine-readable failure code."""

    def __init__(self, code: str, http_status: int | None = None):
        self.code = code
        self.http_status = http_status
        super().__init__(f"FMP request failed: {code}" + (f" (HTTP {http_status})" if http_status else ""))


def load_fmp_api_key(env_path: str | Path = ".env", environ: Mapping[str, str] | None = None) -> str | None:
    """Read a recognized key without executing dotenv contents or mutating env.

    Process environment takes precedence. Supports plain or single/double-quoted
    values and optional `export`; interpolation and shell execution are disabled.
    The returned secret must never be printed or stored in a run record.
    """
    environment = os.environ if environ is None else environ
    for name in KEY_NAMES:
        value = environment.get(name, "").strip()
        if value and value not in {"YOUR_API_KEY", "YOUR_FMP_API_KEY", "replace_me"}:
            return value
    path = Path(env_path)
    if not path.is_file():
        return None
    found = {}
    for line in path.read_text().splitlines():
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        if text.startswith("export "):
            text = text[7:].lstrip()
        key, separator, value = text.partition("=")
        key = key.strip()
        if not separator or key not in KEY_NAMES:
            continue
        value = value.strip()
        if value.startswith(("'", '"')):
            if len(value) < 2 or value[-1] != value[0]:
                raise FMPError("invalid_dotenv_format")
            value = value[1:-1]
        else:
            value = value.split(" #", 1)[0].strip()
        if value and value not in {"YOUR_API_KEY", "YOUR_FMP_API_KEY", "replace_me"}:
            found[key] = value
    return next((found[key] for key in KEY_NAMES if key in found), None)


def _default_transport(url: str, timeout: float) -> bytes:
    request = Request(url, headers={"User-Agent": "MonteCarloEvaluations-coverage-audit/1.0", "Accept": "application/json"})
    with urlopen(request, timeout=timeout, context=ssl.create_default_context(cafile=certifi.where())) as response:
        # The bounded audit endpoints should be small; cap unexpected responses.
        payload = response.read(8_000_001)
        if len(payload) > 8_000_000:
            raise FMPError("response_too_large")
        return payload


class FMPClient:
    """FMP stable API with explicit adjustment basis and a finite call budget."""

    def __init__(self, api_key: str | None, *, cache_dir: str | Path = "data/cache/fmp",
                 timeout: float = 20.0, max_requests: int = 12,
                 transport: Callable[[str, float], bytes] | None = None):
        if not math.isfinite(timeout) or timeout <= 0 or not isinstance(max_requests, int) or max_requests < 1:
            raise ValueError("timeout and max_requests must be positive")
        self._api_key = api_key
        self.cache_dir = Path(cache_dir)
        self.timeout = timeout
        self.max_requests = max_requests
        self.request_count = 0
        self._transport = transport or _default_transport

    def __repr__(self):
        return f"FMPClient(credentials={'configured' if self._api_key else 'missing'}, requests={self.request_count})"

    def _request_json(self, endpoint: str, parameters: dict):
        if not self._api_key:
            raise FMPError("credential_required")
        if self.request_count >= self.max_requests:
            raise FMPError("request_budget_exhausted")
        self.request_count += 1
        url = "https://financialmodelingprep.com/stable/" + endpoint + "?" + urlencode({**parameters, "apikey": self._api_key})
        try:
            raw = self._transport(url, self.timeout)
            payload = json.loads(raw)
        except HTTPError as error:
            code = {401: "authentication_failed", 402: "entitlement_denied", 403: "access_denied", 429: "rate_limited"}.get(error.code, "http_error")
            status = error.code
            error.close()
            raise FMPError(code, status) from None
        except FMPError:
            raise
        except (URLError, TimeoutError, OSError):
            raise FMPError("transport_error") from None
        except (ValueError, UnicodeError):
            raise FMPError("invalid_json") from None
        except Exception:
            # Custom transports must not leak an authenticated URL in a traceback.
            raise FMPError("transport_error") from None
        if isinstance(payload, dict):
            # Classify vendor errors without returning their contents.
            text = json.dumps(payload).lower()
            if any(key in payload for key in ("Error Message", "error", "Error", "message")):
                code = "entitlement_denied" if any(word in text for word in ("premium", "subscription", "upgrade")) else "vendor_error"
                if "invalid api" in text or "invalid key" in text:
                    code = "authentication_failed"
                raise FMPError(code)
        return payload

    def get_prices(self, symbol: str, start: str, end: str, *, adjustment: str = "split_adjusted", refresh: bool = False) -> dict:
        """Return sorted normalized prices plus credential-free source metadata.

        `close` is the selected price series. `source_price_field` identifies the
        vendor field; dividend-adjusted prices are never silently substituted
        for split-adjusted traded-price observations.
        """
        symbol = symbol.upper()
        if not _SYMBOL.fullmatch(symbol):
            raise ValueError("Invalid symbol")
        start_date, end_date = date.fromisoformat(start), date.fromisoformat(end)
        if start_date > end_date:
            raise ValueError("start must be on or before end")
        if adjustment not in PRICE_ENDPOINTS:
            raise ValueError("Choose split_adjusted or dividend_adjusted explicitly")
        endpoint, close_field = PRICE_ENDPOINTS[adjustment]
        parameters = {"symbol": symbol, "from": start, "to": end}
        cache_id = sha256(json.dumps({"version": 1, "endpoint": endpoint, **parameters}, sort_keys=True).encode()).hexdigest()
        cache_path = self.cache_dir / f"{cache_id}.json"
        if cache_path.is_file() and not refresh:
            try:
                cached = json.loads(cache_path.read_text())
                if cached["metadata"]["cache_id"] != cache_id:
                    raise ValueError
                cached["metadata"]["retrieval"] = "cache"
                return cached
            except (ValueError, KeyError, TypeError):
                raise FMPError("invalid_cache") from None
        payload = self._request_json(endpoint, parameters)
        if not isinstance(payload, list):
            raise FMPError("unexpected_response_schema")
        normalized = []
        seen = set()
        for row in payload:
            if not isinstance(row, dict) or "date" not in row or close_field not in row:
                raise FMPError("missing_price_fields")
            try:
                observation_date = date.fromisoformat(row["date"])
                close = float(row[close_field])
            except (TypeError, ValueError):
                raise FMPError("invalid_price_observation") from None
            if not start_date <= observation_date <= end_date:
                raise FMPError("out_of_window_observation")
            if row.get("symbol", symbol) != symbol:
                raise FMPError("symbol_mismatch")
            if row["date"] in seen:
                raise FMPError("duplicate_observation_date")
            if not math.isfinite(close) or close <= 0:
                raise FMPError("nonpositive_or_nonfinite_price")
            seen.add(row["date"])
            record = {"date": row["date"], "symbol": symbol, "close": close}
            if "volume" in row and row["volume"] is not None:
                try:
                    volume = float(row["volume"])
                except (TypeError, ValueError):
                    raise FMPError("invalid_volume") from None
                if not math.isfinite(volume) or volume < 0:
                    raise FMPError("invalid_volume")
                record["volume"] = volume
            normalized.append(record)
        normalized.sort(key=lambda row: row["date"])
        result = {"metadata": {
            "provider": "FMP", "endpoint": endpoint, "parameters": parameters,
            "adjustment": adjustment, "source_price_field": close_field,
            "retrieved_utc": datetime.now(timezone.utc).isoformat(), "retrieval": "live",
            "cache_id": cache_id,
            "price_interpretation": "split-adjusted price; not a dividend total-return series" if adjustment == "split_adjusted" else "dividend-adjusted series; not an unadjusted executable option underlying quote",
        }, "records": normalized}
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps(result, indent=2) + "\n")
        return result

    def get_reference(self, endpoint: str, parameters: dict | None = None) -> dict:
        """Fetch a small allowlisted metadata sample without claiming PIT completeness."""
        if endpoint not in REFERENCE_FIELDS:
            raise ValueError("Reference endpoint is not allowlisted")
        parameters = {} if parameters is None else dict(parameters)
        if any(key.lower() in {"apikey", "api_key", "token", "key"} for key in parameters):
            raise ValueError("Credentials must not be passed as metadata parameters")
        payload = self._request_json(endpoint, parameters)
        if not isinstance(payload, list) or any(not isinstance(row, dict) for row in payload):
            raise FMPError("unexpected_response_schema")
        records = [{key: value for key, value in row.items() if key in REFERENCE_FIELDS[endpoint]} for row in payload]
        return {"metadata": {
            "provider": "FMP", "endpoint": endpoint, "parameters": parameters,
            "retrieved_utc": datetime.now(timezone.utc).isoformat(),
            "historical_completeness_validated": False,
        }, "records": records}

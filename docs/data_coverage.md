# Three-name market-data audit

The live three-name price audit has passed its bounded sample checks. The user supplied a local FMP credential; **12 verified HTTPS requests** returned aligned JPM, PNC and GS observations in the normal and stress windows, for both requested adjustment bases. The full original Research Gate 2 data requirements remain **false**: FMP documents no option-quote product, historical-membership access is denied, and release-aware macro/company-funding features are not yet verified. No option quotes have been invented.

The status artifact is `results/data-audit/coverage.json`; `coverage_live.json` archives the successful 12-request live audit before the cached calendar recheck. Its report separately records each symbol, interval and price-adjustment basis, common-date alignment, HTTP/entitlement failure codes, and outstanding data gates. A successful price sample is not sufficient to pass the later research release.

## Credentials and execution

Place the credential in the repository-local `.env` as `FMP_API_KEY=...`, using `.env.example` as a template. Existing process environment values take precedence. The loader also recognizes `FMP_APIKEY`, `FMP_KEY` and `FINANCIAL_MODELING_PREP_API_KEY`; it does not execute shell expressions, expand variables or modify the process environment.

Run:

```sh
.venv/bin/python scripts/audit_market_data.py
```

After changing an entitlement or key, use `--refresh` to verify live access instead of reusing the normalized cache. The default script permits at most **12 live requests**: three symbols × two short intervals × two adjustment bases. `--export-prices` additionally permits at most three per-symbol history requests (15 total), using explicit `--history-start` and `--history-end` cutoffs. There is no broad-history or paid-product purchase. The client has finite timeouts and a response-size bound. Install `requirements-market-data.txt` for the trusted CA bundle and versioned exchange calendar; HTTPS verification is enabled. Successful normalized prices are cached under `data/cache/fmp`; error bodies and authenticated URLs are not cached or reported.

`.gitignore` now excludes `.env`, `.env.*` and the market-data cache, while allowing the placeholder-only `.env.example`. There is currently no `.git` repository in the workspace, so these are protective rules for future version control, not encryption or an access-control mechanism.

## Verified documentation and intended sample

Documentation checked on 2026-11-05:

| Dataset | Documented endpoint or evidence | Empirical status |
|---|---|---|
| Daily stock prices and volume | `/stable/historical-price-eod/full` | Live normal/stress samples observed for all three names |
| Dividend-adjusted stock series | `/stable/historical-price-eod/dividend-adjusted` | Live normal/stress samples observed for all three names |
| As-reported income statements | `/stable/income-statement-as-reported` | Not audited; release-time and entitlement verification still required |
| Current/historical listed-option quotes, including expired contracts | Official FMP FAQ says options data are not supported | Vendor-documented unavailable; separate provider required |
| Current financial-sector screener | `/stable/company-screener` | Live 100-record current snapshot observed; not historical eligibility |
| Delisted-company sample | `/stable/delisted-companies` | Live 10-record sample observed; completeness unverified |
| Historical S&P 500 membership | `/stable/historical-sp500-constituent` | HTTP 402: account entitlement denied |

FMP's current stock-price documentation uses the **slash-form route**, not the similarly spelled hyphenated documentation slug. It documents OHLCV observations and explicit date bounds. [FMP daily price endpoint](https://site.financialmodelingprep.com/developer/docs/stable/historical-price-eod-full), [FMP quickstart](https://site.financialmodelingprep.com/developer/docs/quickstart).

The separate dividend-adjusted endpoint describes dividend-adjusted prices, and FMP's historical-data examples use an `adjClose` field. The adapter requires that field for this basis instead of silently substituting `close`. [Dividend-adjusted endpoint](https://site.financialmodelingprep.com/developer/docs/stable/historical-price-eod-dividend-adjusted), [Historical market-data examples](https://site.financialmodelingprep.com/datasets/market-data-historic).

The vendor FAQ describes EOD `close` as split-adjusted and `adjClose` as split/dividend-adjusted. It also acknowledges that historical data for some delisted symbols may be unavailable. Those statements are documentation evidence, not proof of completeness for this account, symbol or interval. [FMP coverage and adjustment FAQ](https://site.financialmodelingprep.com/faqs).

As-reported financial statements are documented, but fiscal-period dates must not be used as publication dates in a forecasting feature. Actual filing/acceptance timestamps, revisions and point-in-time availability still need to be audited before financial statement features can enter historical tests. [As-reported income statements](https://site.financialmodelingprep.com/developer/docs/stable/as-reported-income-statements).

The small audit uses JPM, PNC and GS over:

- Normal comparison interval: **2019-01-02 through 2019-03-29**.
- Stress comparison interval: **2020-02-03 through 2020-04-30**.

The normal window contains **61 sessions per name** and the stress window **62 sessions per name**, with exact date alignment for both bases. These are predetermined samples, not comprehensive regime coverage. Counts, duplicate dates, positive/finite prices, symbol consistency, actual date bounds and outlier log returns are checked. Missing weekdays are distinguished from exchange holidays using the versioned **XNYS calendar from exchange_calendars 4.13.2**. No data are forward-filled to conceal missing observations. [Calendar implementation](https://github.com/gerrymanoim/exchange_calendars).

After the successful sample, three additional full-history requests produced `data/market/prices_split_adjusted.csv`: a timezone-naive ascending daily index named `date`, columns `JPM`, `PNC`, `GS`, and **4,236 aligned observations from 2010-01-04 through 2026-11-04**. Every expected XNYS session is present and there are no unexpected dates. Canonical normal/stress window CSVs and `prices_metadata.json` record the basis, source endpoints, explicit cutoffs and file hashes. These are stock-price observations for calibration/model-contract replay; dividend cash flows and historical option quotes are not included.

## Interpretation and unresolved gates

Split-adjusted close and a dividend-adjusted return series serve different purposes. In a traded-stock ledger, dividends and corporate actions need explicit accounting. A dividend-adjusted price history is not an executable historical stock quote, and neither adjusted basis alone establishes that a zero-dividend option replay is economically complete.

The current-universe screener snapshot, delisted sample and entitlement result are saved under `data/market/` with credential-free metadata. The current screener contains 100 names across multiple financial subsectors and is not a historical financial-sector membership list. Historical S&P membership access returned HTTP 402. This prevents a claim of point-in-time/survivorship-safe sector breadth from the available evidence; failed and acquired names must not be silently excluded. [Screener documentation](https://site.financialmodelingprep.com/developer/docs/stable/search-company-screener), [Historical membership documentation](https://site.financialmodelingprep.com/developer/docs/stable/historical-sp-500).

The official FMP FAQ explicitly states that the API does not support options data or Level-2 market depth. Consequently no guessed current/expired-option endpoint was called, and an authenticated stock-data request is not evidence of option-quote access. Research Gate 2 needs a separate source for expired contracts and timestamped historical bid/ask, plus contract terms, exercise/settlement and corporate-action treatment. [FMP options capability FAQ](https://site.financialmodelingprep.com/faqs). If these quotes remain unavailable, a model-contract replay on historical stock observations can be an explicitly labelled intermediate study; it cannot be described as a listed-option execution backtest.

Cboe's Option Quotes product documents historical quote intervals with NBBO, expiries, strikes and option type; its documented history starts in January 2012. This is a candidate fallback to investigate, not an existing subscription or a purchased dataset. [Cboe historical option quotes](https://datashop.cboe.com/option-quote-intervals).

For later macro features, the FRED observations API documents realtime/vintage parameters. For bank fundamentals, FDIC provides a financial-data API; a defensible issuer-to-bank-subsidiary mapping and publication-date treatment remain necessary. Neither source has been incorporated into this first audit. [FRED/ALFRED vintage parameters](https://fred.stlouisfed.org/docs/api/fred/series_observations.html), [FDIC data-products guide](https://www.fdic.gov/system/files/2024-06/guide.pdf).

## Validation

`tests/test_market_data.py` uses synthetic fixtures and mocked transports only. It covers dotenv precedence and non-execution, absent credentials, normalized adjustment fields, no credential leakage in errors/caches, finite request budgets, duplicate/invalid/out-of-window observations, alignment gaps, and the rule that price samples alone cannot pass the historical-option or research gate. The suite includes exchange-holiday versus missing-session checks, canonical export/schema checks and allowlisted reference-data handling. All **18 adapter/coverage tests** and **5 current-universe tests** pass (23 market-data tests total).

## Expanded core and conditional breadth data

The fixed core now contains JPM, PNC, GS, BAC, WFC, C, USB, MS, SCHW and the stable study issuer ID BK. `prices_core_10.csv` and `prices_benchmarks.csv` (SPY/XLF) each contain the same 4,236 XNYS sessions. Their metadata retain the split-adjusted price basis and the absence of dividend cash flows.

BK required an explicit identifier reconciliation. The issuer announced a ticker change to BNY effective 2026-05-21 without a capital-structure or CUSIP change. FMP's old BK history ends on that date; its current BNY history overlaps 4,121 old-symbol observations with exactly matching closes. The core series uses old-symbol observations before the effective date and actual BNY observations thereafter. `issuer_symbol_mappings.json` records the evidence, and `bny_symbol_history_raw.csv` retains both original histories. No forward fill was used. [Issuer ticker-change announcement](https://www.bny.com/corporate/global/en/about-us/newsroom/press-release/bny-announces-planned-change-of-stock-ticker-symbol-to-bny-130465.html).

The breadth sample freezes 50 names from the saved current 100-name screener snapshot. It preserves the required core ten first, then chooses eligible remaining names by current market cap, volume and symbol. The explicit screen is US active Financial Services, non-ETF/non-fund, a common-share symbol pattern, market cap at least $2 billion and current daily volume at least 250,000. Current duplicate issuer names/share classes and preferred-like symbol patterns are excluded. This is a transparent current-snapshot screen, not proof of persistent historical liquidity.

`financial_50_universe.csv` preserves classifications and exact nested order; `financial_50_eligibility_audit.csv` retains every screened record and exclusion reason. All 50 selected columns remain in `prices_financial_50_unbalanced.csv`; `prices_financial_50_availability.csv` explicitly marks observed cells. There are **42 complete histories, eight partial histories and zero failed symbols**. Seven partial names have unavailable early observations (BAM, APO, HOOD, PYPL, ARES, RKT and COIN); KKR has three internal gaps on 2010-06-16, 2010-06-18 and 2010-06-23. These values are not filled, and names/dates are not silently removed. Provider first-observed dates are not asserted to be verified IPO or historical-membership dates.

The core/ETF stage used nine new requests after the three cached names. BNY identifier resolution used one breadth request; the remaining breadth fetch used 40, for **41 of the authorized 50 breadth attempts**, including any retry allowance. Request spacing is bounded, only transient errors get at most one retry, and the overall client ceiling also includes retries.

This sample supports **conditional current-universe breadth research**. It does not pass the original stage-7 historical-generalization gate: the historical membership endpoint returned HTTP 402, current classifications and liquidity screens are not point-in-time, and historical mergers/spinoffs/symbol reassignment remain unresolved beyond the documented BNY mapping. Partial and failed observations must remain visible in every downstream report.

## Reproduce the data preparation

Run with the local secret in `.env` and dependencies from `requirements-harness.txt` plus `requirements-market-data.txt`:

```sh
.venv/bin/python scripts/audit_market_data.py --export-prices
.venv/bin/python scripts/fetch_core_prices.py
.venv/bin/python scripts/audit_reference_data.py
.venv/bin/python scripts/fetch_financial_universe.py
```

Existing normalized history caches prevent repeated calls. The reference audit explicitly refreshes a **current** snapshot and can change its as-of date; preserve the saved snapshot and hashes to reproduce the original current-universe selection. The fixed history cutoff is 2026-11-04. `data/market/data_gate_status.json` summarizes verified access, available artifacts, exact remaining gates and human-review requirements.

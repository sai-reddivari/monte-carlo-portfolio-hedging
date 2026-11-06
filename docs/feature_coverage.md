# Feature source audit

This audit establishes source access, definitions and availability constraints. It does not establish incremental forecast or hedge improvement. Human review of economic definitions and representative filings remains pending. Current-universe price selection still has the historical membership/survivorship limitation documented in `data_coverage.md`.

## FMP findings

The authenticated initial probe used eight financial/filing HTTP attempts (including one repeated request after a local normalization failure) and two Treasury requests. A subsequent SEC-identifier lookup used two further FMP filing requests; those are counted separately in the SEC manifest. Credentials were read from environment/`.env`, never written to artifacts. Successful samples are cached; rerunning without `--refresh` uses those files.

| Endpoint | Observed sample | Strict historical admission |
|---|---|---|
| `balance-sheet-statement-as-reported` | Three quarterly records each for JPM, PNC, GS | Blocked: sampled records had no filing or acceptance date. |
| `balance-sheet-statement` | Three quarterly records each; all had filing and acceptance dates | Blocked: current standardized values were not established as the values originally reported in those filings. |
| `sec-filings-search/symbol` | JPM sample of20 records; later PNC/GS identifier samples | Identifiers/publication metadata only; not a binding of FMP accounting values to original documents. |
| `treasury-rates` |61 normal-window and62 stress-window observations | Date-only current snapshot. No actual publication/ingestion time or original-vintage evidence. |

The sampled statement fields and endpoint conventions follow the [official FMP documentation](https://site.financialmodelingprep.com/developer/docs). Filing dates and acceptance timestamps describe publication metadata; their presence alone does not prove original-value vintage. No fiscal period-end is used as a publication date. The Treasury samples retain vendor percentage yields and explicitly convert them to decimal units by dividing by100. A next-session-close availability assumption is labelled as an assumption. Two sample windows cannot support a full historical macro forecasting layer.

Machine-readable outputs are `results/feature-audit/coverage.json`, `data/market/features/company_feature_fields_long.csv`, `company_feature_concept_coverage.csv`, and `treasury_rates_lagged_samples.csv`. Missing values remain missing, reported zero remains zero, and missing uninsured deposits are not synthesized. Bank cash, repos, wholesale borrowing and deposits are separate concepts; identical treatment across banks and broker-dealers requires economic review.

## SEC source alternative

The official SEC API publishes issuer submissions and XBRL company facts, separated by taxonomy, concept and unit. Its aggregated company facts cover standard, entity-wide disclosures rather than every custom or dimensional item. Recent submissions metadata has a finite history, with additional archive references available separately. [SEC API documentation](https://www.sec.gov/search-filings/edgar-application-programming-interfaces).

Exactly six official SEC JSON reads succeeded: companyfacts and submissions for each of JPM, PNC and GS. CIKs came from actual retained FMP filing metadata, not inferred ticker mappings. The identifying User-Agent was `MonteCarloEvaluations/0.1 (noncommercial portfolio hedging research)`; requests used verified TLS and spaced access. No authentication, subscription or purchase was needed. Native responses and source hashes are retained; six calls do not include independently downloading each historical filing document.

The extraction retains2,826 distinct selected instant USD facts from10-K/10-Q filings and amendments. Each has a native accession, filed date, period end, taxonomy tag and unit. All332 facts with matching recent submissions entries agreed on accession metadata; there were zero mismatches and zero conflicting values within a selected filing. Older records remain explicitly labelled native SEC accession/filed bindings, rather than independently crosschecked archival documents. This distinction is available row by row.

The coherent snapshot panel has212 filing snapshots (JPM71, PNC70, GS71), spanning periods in2009 through2026Q3. Each snapshot takes its newest `Assets` period and includes only values with the same issuer, accession, filed date, period and USD unit. Comparative older periods in later filings never replace a newer economic period in the as-of selector. Multiple returned filing vintages remain in the long table, so a revision is admitted only after its own availability time.

| Export | Purpose |
|---|---|
| `data/market/features/sec_facts/sec_filing_facts_long.csv` | Accession-bound raw concept observations, crosscheck and vintage flags. |
| `sec_filing_snapshots.csv` in the same directory | Coherent per-filing snapshots for as-of feature joins. |
| `sec_field_year_coverage.csv` | Nonmissing observation and distinct-period counts per issuer, field and year. |
| `sec_fact_coverage.json` | Source hashes, request counts, exact concepts, coverage and limitations. |

Snapshot schema: `symbol,cik,period_end,accn,filed,available_at,available_from_session,unit`, the seven concept columns below, and verification/availability flags. CIKs are identifiers and should be read as strings. `available_at` is a timezone-aware UTC **derived bound**: close of the first XNYS session strictly after the verified SEC filed calendar date. It is not an actual acceptance timestamp. The exchange calendar accounts for holidays, daylight saving time and early closes.

For a decision timestamp, `select_snapshot_asof` first filters `available_at <= decision`; it then maximizes `period_end` and finally chooses the latest available filing within that period. Future releases are excluded, and a late comparative cannot roll the financial state backward. No source missingness is replaced with zero.

| Model column | Exact US-GAAP tag | Definition constraint |
|---|---|---|
| `assets` | `Assets` | Snapshot anchor. |
| `liabilities` | `Liabilities` | Ratios require same-filing assets. |
| `stockholders_equity` | `StockholdersEquity` | Parent stockholders' equity; not silently substituted with other equity concepts. |
| `cash_and_cash_equivalents` | `CashAndCashEquivalentsAtCarryingValue` | Available extensively for GS, sparsely JPM, absent PNC in this tag. |
| `cash_and_due_from_banks` | `CashAndDueFromBanks` | Bank-specific cash concept, distinct from cash equivalents. |
| `deposits` | `Deposits` | Bank comparison approved for JPM/PNC only; actual GS facts retained with approval false. |
| `short_term_borrowings` | `ShortTermBorrowings` | Sparse JPM/GS, absent PNC in this exact tag; no forced wholesale-funding alias. |

Native filing binding passes automated structural checks for these selected concepts. Economic comparability, representative-file review and actual incremental test performance remain separate requirements. No result here establishes that funding signals improve forecasts, hedges or stress performance.

## Reproduction and checks

Run `.venv/bin/python scripts/audit_research_features.py` for the cached FMP capability audit. To regenerate SEC tables from the exact six cached responses without network access:

```python
from pathlib import Path
from market_data.sec_facts import export_cached_sec_facts
export_cached_sec_facts(Path.cwd())
```

The14 offline feature/SEC tests cover issuer and accession binding, units, conflicting values, missingness, conservative exchange-session availability, current-vintage rejection, comparative period selection, amendment timing and future-release exclusion. No tests require credentials or live HTTP.

## Predeclared core10 supplement

The larger cohort uses JPM, PNC, GS, BAC, WFC, C, USB, MS, SCHW and stable study identifier BK. This extension was declared to the feature-evaluation worker before evaluating its results, with the train/validation/test cutoffs and model grid fixed. Separate files in `data/market/features/sec_facts_core10/` preserve the three-name artifacts unchanged; the fetch manifest retains their hashes and confirms equality. Reproduction uses `.venv/bin/python scripts/extend_sec_core10.py`; completed caches require no new requests. Any source error stops the acquisition without an automatic retry.

Seven additional FMP filing-CIK lookups and14 additional official SEC reads succeeded. BK's actual current filing lookup used BNY, consistent with the separately documented issuer ticker change. No CIK was guessed. The three original companyfacts/submissions pairs were reused. All1,276 available recent accession metadata crosschecks matched; there were no within-filing selected-value conflicts. Older values retain the same explicit native-binding-only caveat.

The supplement contains9,525 selected filing facts and697 coherent snapshots. Assets and stockholders' equity are present in all697; liabilities in696 because one BAC snapshot is missing its same-filing liability tag. Cash equivalents remain sparse and are not imputed. Snapshot coverage by issuer is:

| Issuer | Snapshots | Latest selected asset period |
|---|---:|---|
| JPM |71|2026-09-30|
| PNC |70|2026-09-30|
| GS |71|2026-09-30|
| BAC |70|2026-09-30|
| WFC |70|2026-09-30|
| C |66|2025-12-31|
| USB |70|2026-09-30|
| MS |70|2026-09-30|
| SCHW |69|2026-06-30|
| BK |70|2026-09-30|

These are observed endpoint/tag limits, not statements that an issuer has no more recent financial report. As-of and staleness rules govern eligibility; any missing or stale input must reduce the matched sample rather than trigger filling. Generic same-period liabilities/assets can be assessed on matched observations. Comparable bank-deposit eligibility is restricted to JPM/PNC/BAC/WFC/C/USB. GS and MS remain capital-markets/wealth-management groups, SCHW a brokerage-and-bank group, and BK a custody/asset-servicing group. Their actual deposit facts are retained with comparison approval false. This business classification is explicit study judgment, not a point-in-time historical industry membership series.

The supplement increases cross-sectional coverage; it does not establish incremental forecast or hedge improvement. Native structural checks pass, while definition/filing human review and the historical membership limitation remain separate from automated success. The SEC suite adds a test that the separate core10 exporter preserves the frozen three-name set, enforces deposit eligibility, and retains missing liabilities/cash as missing.

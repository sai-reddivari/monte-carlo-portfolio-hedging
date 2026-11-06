# Incremental market and filing-vintage feature research

The final artifacts are:

- [Frozen three-name SEC / two-bank study](../results/feature-research-20261106T024225834886Z/report.md).
- [Separate core-ten SEC / six-bank extension](../results/feature-research-20261106T024244836968Z/report.md).
- [Extended cohort coverage](../results/feature-research-20261106T024244836968Z/cohort_coverage.csv).
- [Actual financial availability trace](../results/feature-research-20261106T024244836968Z/financial_availability_trace.csv).
- [Locked models and train-only scaler parameters](../results/feature-research-20261106T024244836968Z/selected_models.json).
- [Date-clustered loss-difference intervals](../results/feature-research-20261106T024244836968Z/paired_loss_differences.csv).

The original three-cohort scores are unchanged within 1e-12 in the core-ten extension. The original SEC source files and original result directory remain immutable. Model definitions, chronological boundaries and penalty grid were not changed after examining the new cohort's losses.

## Reproduce

```sh
.venv/bin/python scripts/run_feature_research.py
.venv/bin/python scripts/run_feature_research.py --sec-core10
.venv/bin/python -m unittest discover -s tests -p test_feature_models.py -v
```

Notebook `09_release_aware_features.ipynb` runs the extension and displays the actual results. Each execution writes a new `results/feature-research-*` directory. Imports and runners do not read credentials or perform network requests.

## Frozen forecasting protocol

The target is **total underlying** cumulative squared log returns over the next five or twenty sessions, not residual variance. Training uses 2010–2017, validation 2018–2020 and test 2021–2026-11-04. Training/validation target intervals end before the next split, and targets do not overlap within a split/horizon.

Simple references are rolling 20/252-session variance and EWMA(lambda 0.94). An interpretable ridge regression models log daily variance. Scaling, coefficients, issuer intercepts, a residual smearing correction and numerical prediction guards are fit using only training rows. The fixed penalty grid is 0.1/1/10/100/1000. Validation QLIKE chooses alpha independently for each cohort/layer/horizon. There is no train-plus-validation refit. The selected models are persisted and hashed before computing test predictions.

The predeclared layers are:

1. Own-price variance and return features.
2. Observed SPY/XLF risk/return features and past-only beta interactions.
3. Same-period official SEC balance-sheet proxies.
4. Those proxies interacted with the preceding five-session XLF return.

The ten-name market study compares layers 1–2. JPM/PNC/GS generic capital-markets/bank comparisons use liabilities/assets for layers 3–4. JPM/PNC bank-only comparisons use deposits/liabilities and cash-due-from-banks/assets; GS is excluded from that deposit hypothesis. The separate broader extension uses generic liabilities/assets for all ten and deposit share only for six qualified banks: JPM, PNC, BAC, WFC, C and USB. It does not silently substitute sparse cash tags across issuers.

## Release and vintage eligibility

FMP's currently returned balance snapshots and the two small Treasury samples did not pass strict historical-vintage/publication admission. Those values do not enter the models.

Official SEC companyfacts instead bind each instant USD value to an accession and actual filed date. Recent submissions metadata independently verifies a subset of those bindings; older records retain native official SEC accession/date evidence rather than an independently downloaded original archive. Financial ratios require the same filing and fiscal period.

Available time is a **derived conservative bound**: the close of the next XNYS session after the actual SEC filed date. It is not an asserted intraday acceptance timestamp. The model's conservative cutoff is 16:00 New York on the origin session. Forecasts also use the final stock close, so they are issued after close; a later trade cannot assume those final-close features were available before a same-close fill.

As-of selection first chooses the newest available fiscal period, then the latest available revision of that period. Later comparative old-period facts cannot replace a newer known quarter. Actual JPM 2012Q1/Q2 statements have the same availability timestamp; the newer fiscal period correctly wins. Missing values remain missing. Both release age and fiscal-period age are bounded at 180 days; a recent comparative republication cannot make an old fiscal period fresh.

Citi's most recent selected native Assets period in the available snapshot is 2025Q4. Applying the stale-data limit and exact matched-name/date comparisons therefore truncates the broader generic-ten and six-bank tests to 276 five-session origins and 69 twenty-session origins, with latest eligible target 2026-07-06. The earlier three-name/two-bank study retains 293/73 test origins through 2026-11-03. The coverage table reports these differences instead of claiming every cohort reaches November.

## Dependence-aware evaluation and actual findings

Within each cohort, every model uses the same fully observed names and dates. Loss differences are averaged across names at an origin before circular moving-block resampling. Quarter-scale date blocks preserve common company episodes and address residual time dependence. Intervals are pointwise, not simultaneous superiority statements across every comparison.

QLIKE is `log(forecast) + realized/forecast`, omitting a target-only constant. Negative model-minus-reference differences favor the alternative model. MSE and QLIKE can disagree; both are reported.

Observed test findings include:

- In the full ten-name price/market study, own-price ridge improves QLIKE versus EWMA at both horizons, while adding market/sector features has inconclusive incremental QLIKE effects. Five-session ridge MSE can worsen despite better QLIKE.
- On the matched broader SEC-ten sample, liabilities/assets improves five-session QLIKE by **−0.00660**, pointwise interval **[−0.01095, −0.00279]**, relative to the market-information model.
- The same generic balance-sheet layer worsens twenty-session QLIKE: **+0.00648**, interval **[+0.00167, +0.01101]**.
- In the six-bank deposit experiment, the added deposit-share layer worsens QLIKE at both horizons: **+0.01501** at five sessions and **+0.06994** at twenty, with both pointwise intervals above zero.
- The additional balance-sheet × sector-return interactions are inconclusive under the displayed QLIKE comparisons.

These mixed/negative results are retained. They do not establish universal funding-feature value, a causal funding-risk mechanism, or improved derivative hedging. The generic feature and bank-funding experiments have different matched cohorts and eligibility dates; compare each layer with its own matched reference, not an unrelated full-sample score.

## Validation and gates

Twelve feature tests pass: future-release exclusion, strict timezone handling, future price/factor perturbation invariance, newest-period preference, same-availability fiscal priority, old-period republication staleness, missing data preservation, bank-specific feature approval, train-only scaling, purged/non-overlapping targets, date clustering and DST-aware close cutoffs.

Final artifact QA independently matched all current source, input and output SHA256 hashes; verified that the protocol preceded the selected-model lock and predictions; and reconstructed all 36 extended-study training scalers, validation-selected penalties and test forecasts to 1e-12. Every admitted filing was available by its forecast cutoff, with both release and fiscal-period age at most 180 days. Notebook 09 was executed and saved with five code cells and no error outputs. Both output figures were visually inspected.

The experiment tests incremental observed-market and verified filing-vintage information under a frozen protocol. The broader macro layer remains unavailable, actual original archive crosschecks remain incomplete for older facts, and forecast-to-hedge value is not inferred from forecast scores. The universe remains current/availability conditioned rather than historically eligible. Full stage-5 macro/funding and stage-7 economic generalization gates therefore remain explicitly open; human review of economic definitions and representative filings is a separate step.

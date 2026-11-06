# Independent validation of the controlled hedging study

Validation date: 2026-11-05. This review covers the controlled simulation and its statistical evaluation. It does not certify a market-data feed, historical option replay, or equity-overlay strategy.

## Financial conventions reviewed

The experiment sells synthetic, zero-dividend European calls at inception at their model prices, buys positive stock delta, and finances the residual through cash. Quantities are share-equivalent units: there is no exchange contract multiplier. Cash may be negative and both borrowing and lending use the same constant rate.

At each observation, the engine accrues interest before observing the current stock prices and applying the policy. The remaining maturity and current prices determine the hedge; future observations must not affect the current trade. Stock costs apply to the absolute value traded, including entry and liquidation. At expiry the engine liquidates stock and pays the call payoff, leaving cash equal to terminal net P&L.

The following original checks are economically meaningful and are preserved: a one-step hand calculation, cash-flow accumulation, cash plus stock less option liability, terminal settlement, financed-cost identity, initial-only closed form, account additivity, absence of future information in earlier trades, and unchanged opening premium when hedge volatility changes. Risk-neutral expected discounted hedging gain is a simulation benchmark, not a claim of real-world returns.

The policy extension must preserve these conventions. A delta band is measured relative to option units, and the maturity-sensitive band narrows with remaining maturity. Continuous delta neutrality is not claimed between observations. Entry and terminal settlement remain unconditional; a hold decision should not create a stock trade or trading fee.

## Peak borrowing and scenario identity

A portfolio's shared peak borrowing is the maximum over time of the negative **sum of contemporaneous name-level cash balances**, floored at zero. It is not the sum of the individual positions' peak borrowings, which can occur at different dates. The engine extension tracks both quantities separately and records cash before trades after interest and after trades/costs/settlement at each observation. This is observed-event funding, not a model of intraday liquidity or margin.

Paired policy comparisons require identical realized scenarios, including asset ordering. Equal array shape or an equal integer random seed alone is insufficient. The extension's path fingerprint is derived from actual price bytes and names; a human-readable scenario label cannot override that fingerprint. For breadth comparisons use subsets of a master joint path set, rather than regenerate each universe independently with the same seed.

## Uncertainty module and tested identities

`hedging_harness/uncertainty.py` provides:

- `mean_interval`: a two-sided normal Monte Carlo interval for an independent-outcome mean. For an expected-cost budget, the upper endpoint is a conservative selection constraint. A 95% two-sided interval has a 97.5% one-sided upper endpoint under the normal approximation. A cost-budget interval is not a per-outcome hard spending limit.
- `expected_shortfall`: minus the mean of the worst `ceil(tail_probability * N)` P&Ls, matching the existing ES95 convention. Profitable worst tails give negative loss ES and are not clipped to zero.
- `paired_tail_difference`: a percentile-bootstrap interval for `ES(left) - ES(right)`. Negative values favor the left policy. The same resampled outcome indices are applied to both policies; each policy's tail is then selected separately. This is a difference of expected shortfalls, not expected shortfall of the P&L difference.
- `risk_interval`: percentile-bootstrap uncertainty for loss ES, sample standard deviation, or RMSE. It reports uncertainty in that statistic, rather than confusing it with standard error of the P&L mean.

The statistical tests establish known outcomes: identical policy vectors give exactly zero paired uncertainty; an additive improvement in every outcome reduces ES by the same constant; the rounded-up worst-tail convention is correct; constant samples have zero uncertainty; the normal interval agrees with a known sample mean/variance; seeds reproduce results independently of chunk size; malformed data and parameters fail explicitly. Inputs are not mutated, and outputs serialize as finite JSON for ordinary finite economic samples.

Resampling assumes independent simulated outcomes in their original pairing order. Do not apply this implementation directly to overlapping historical windows, a time series of daily P&L, antithetic averages, or clustered historical episodes without a dependence-aware resampling design. The caller must verify scenario identities before passing arrays to the statistical function.

## Research Release 1 completion criteria

1. Freeze the candidate policies, objective, expected-cost budget, seeds, model scenarios and evaluation protocol before evaluating the held-out sample.
2. Select using the selection sample only. A pre-specified conservative upper endpoint for expected financed trading cost is a defensible budget screen; report its confidence convention.
3. Lock the selected policy and evaluate it on a separate untouched seed/sample. Report evaluation cost-budget feasibility even if it differs from the selection result.
4. Report mean net P&L and its SE separately from outcome standard deviation, tail risk, trading costs, turnover and shared peak financing needs.
5. Give paired uncertainty for incremental tail protection against fixed benchmarks. A negative or inconclusive improvement is an admissible research finding; it should not be converted into a success claim by post-hoc tuning.
6. Show ledger and financed-cost reconciliation checks, actual scenario identifiers and source/configuration provenance.
7. State that the findings are conditional on the illustrative Q model. Fresh seeds test Monte Carlo stability, not historical out-of-sample predictive validity.

## Limits that remain after this gate

At 5,000 simulated outcomes, an ES95 estimate averages 250 tail observations; 10,000 gives 500. Increasing bootstrap repetitions refines the resampling approximation but does not add economic observations. Percentile intervals are conditional on the empirical sample and fixed model: they do not capture parameter uncertainty, omitted jumps/stochastic volatility, quote quality, survivorship, or execution realism.

The current call book still has one option per underlying, a common maturity/calendar/rate, constant volatility, no dividends, no listed-contract lifecycle, and simplified funding. The market-data coverage gate, a reconciled historical replay, forecasting validation, and equity/derivative-overlay comparisons are distinct later milestones. A larger ticker count by itself does not satisfy them.

## Validation execution evidence

The independent validation worker executed these commands with the local `.venv/bin/python` environment:

```text
python -m unittest discover -s tests -p test_hedging.py -v       13 passed
python -m unittest discover -s tests -p test_policies.py -v      10 passed
python -m unittest discover -s tests -p test_uncertainty.py -v   10 passed
```

The policy tests independently confirm zero-band/daily equivalence, wide-band/initial-only equivalence, correct per-name hold/rebalance audit events, a narrowing maturity band, financed costs, absence of future information, shared peak funding versus a sum of separate peaks, accrued funding before settlement, actual-path scenario identity, periodic backward compatibility and invalid-policy rejection.

A separate performance check applied the paired ES bootstrap to 10,000 paired outcomes with 1,000 resamples in approximately 0.17 seconds on this execution environment. This is a local statistical-module check, not a production benchmark or evidence about empirical hedge performance.

Passing component tests alone does not mark the research gate complete. The production audit below separately verifies the locked selection, held-out evaluation and actual report artifacts.

## Independent release-protocol source review

The reviewer inspected `hedging_harness/research.py` and the actual pre-specified `config/research_release_1.json`. The protocol contains fourteen candidates, separate selection/evaluation seeds and counts, a $500 expected financed-cost budget, ES95 as the objective, and a conservative two-sided-95% normal cost upper endpoint. The implementation enforces the ES95 tail definition and fixed confidence convention.

The source writes and hashes `selection.json` before generating evaluation paths, verifies that the lock is unchanged afterward, requires different selection/evaluation scenario fingerprints, and validates actual-path pairing before mean and tail comparisons. Selecting the candidate uses only selection metrics and a deterministic tie break; evaluation budget failure is reported without reselection. The selected-vs-benchmark bootstrap intervals are explicitly pointwise rather than simultaneous dominance claims.

The review identified a completion-marker ordering issue: writing `gate_status.json` before rendering the report could leave a false complete marker if rendering failed. The integration owner fixed it; source inspection now confirms the complete marker is written only after plots and report succeed. The reviewer also requested and verified exact-confidence validation and removal of an unused audit-index expression. The production artifacts have now been independently reproduced as documented below. The separate human review remains pending.

## Price-risk extension validation

The independent worker also implemented and tested dated physical-risk forecasts and covariance models in `hedging_harness/risk_models.py`. Nine additional tests pass, including invariance of earlier forecasts to future price/factor perturbations, positive-semidefinite covariance, exact next-horizon target alignment, disjoint chronological evaluation targets, scoring identities and reproducible chronological block resampling.

The actual ten-name evidence is recorded in `results/risk-research-20261106T014747676804Z/report.md`; its data/source/output hashes were verified. The frozen split uses 2010–2017 training, 2018–2020 validation and 2021–2026-11-04 test. The 293 five-session and 73 twenty-session test origins are evaluated with date-level dependence-aware uncertainty. Favorable MSE point estimates do not become an unconditional improvement claim: corresponding QLIKE intervals include zero. These results do not establish incremental macro/funding value, forecast-to-hedge value or survivorship-free generalization.

## Production Research Release 1 artifact audit — passed

Audited directory: `results/research-release-1/release-1`.

Every output listed in `artifact_manifest.json` exists and its SHA256 matches. The source and study configuration hashes match the actual files, and the saved protocol content agrees with its source configuration. All recorded source hashes match the current files, including `risk_models.py`; there is no selection/evaluation source drift. The selection-lock hash agrees across the actual lock, provenance and gate artifacts. No production rerun is needed on account of source drift in this audit.

The source places lock persistence before evaluation path generation. The saved evidence has the corresponding UTC order:

| Evidence | UTC timestamp |
|---|---|
| Protocol commitment persisted | 2026-11-06 01:46:14.512306 |
| Selection lock persisted | 2026-11-06 01:46:16.382140 |
| Evaluation metrics persisted | 2026-11-06 01:46:20.302247 |
| Standalone report persisted | 2026-11-06 01:46:21.671074 |
| Complete gate marker persisted | 2026-11-06 01:46:21.671198 |

Filesystem timestamps support this ordering; the source and integration checks establish that the lock exists before the evaluation generator is called. Selection and evaluation use distinct seeds and distinct actual-path fingerprints. Each sample has exactly one shared fingerprint across all fourteen policy cases.

The reviewer independently regenerated both samples, reran **all fourteen candidates on both samples**, and compared the reconstructed metrics with every published selection/evaluation row. For all twenty-eight cases, the independent calculation verifies cash-flow accumulation, marked value, stock-trade cash flows, proportional fees, terminal settlement, zero-cost versus financed-cost identity, portfolio mean/SE/std/ES95, expected financed cost and its upper interval, and concurrent peak borrowing. It also reconstructs the selected/four-benchmark saved audit CSVs and the audited shared peak funding from both pre-trade accrued cash and after-trade balances.

Largest absolute recomputed residuals were:

| Identity | Largest residual |
|---|---:|
| Cash accumulation | 1.6007106751e-10 |
| Marked account value | 7.2759576142e-12 |
| Stock trade cash flow | 0 |
| Stock fee | 7.1054273576e-15 |
| Financed trading-cost identity | 2.6724933377e-10 |

All four paired ES-difference bootstrap intervals and both selected-policy ES/std intervals reproduce from the pre-specified bootstrap seeds. The independently recomputed selection using only the selection CSV is **maturity_band_050**. Its held-out financed cost is approximately **$487.971**, with upper endpoint **$490.177**, below the **$500** budget. Its held-out ES95 is approximately **$3,327.945**.

The selected-minus-weekly ES95 difference is approximately **−$2,914.959**, with pointwise interval **[−$3,100.693, −$2,710.425]**. Selected-minus-daily is approximately **+$1.899**, interval **[−$31.614, +$33.564]**. The latter is inconclusive for superiority and is not proof of equivalence/noninferiority without a pre-specified margin. The selected rule's mean financed cost is lower than daily's approximately **$545.691**.

The standalone report and both plots were inspected. They distinguish financed trading cost from peak borrowing, record pointwise rather than simultaneous uncertainty, and explicitly keep market-data/stage-7 claims false. The completion marker follows successful report rendering. The actual controlled-study evidence therefore supports **Research Gate 1 complete**, with human review explicitly separate and pending. This finding does not pass the later empirical or portfolio-protection gates.

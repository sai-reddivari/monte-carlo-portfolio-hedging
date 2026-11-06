# Financial-sector hedging research: release gates

The user-provided staged design is the mandate. `Book` remains the validated input container. The target is to progress through stage 7, with the controlled Research Release 1 as the first required deliverable. Passing a code test is not sufficient to claim an empirical research gate.

## Gate 1: controlled policy-selection release

1. Preserve the short-call cash/stock/option ledger and existing accounting invariants.
2. Compare periodic, fixed delta-band and maturity-sensitive delta-band rules.
3. Freeze the candidate set, expected financed-cost budget and objective before evaluation.
4. Select on separate simulated paths, persist the selected rule, then generate untouched evaluation paths.
5. Report portfolio ES95, mean/P&L variability, turnover, mean/95th-percentile/max observed peak financing and cost-budget uncertainty.
6. Report paired bootstrap uncertainty for ES differences, recomputing each policy's tail within common-index resamples; retain mean-difference intervals separately.
7. Produce an executable notebook, standalone report, machine-readable results, source/config hashes and independent validation.

Default protocol: `config/research_release_1.json`. The provisional expected financed stock-cost budget is $500 for a $300,000 initial underlying-notional book, at a one-way 5bp charge. Feasibility uses the upper endpoint of a two-sided 95% normal Monte Carlo interval for mean financed cost. This is not a hard pathwise cost cap or a simultaneous guarantee over all selected candidates. Untouched evaluation reports whether the locked policy remains budget-feasible. Evaluation failure is a result; the rule is not reselected on holdout outcomes.

## Stage 2: shared inputs and empirical data gate

- One validated study source; preserve stable name ordering and actual-path scenario fingerprints.
- Audit JPM, PNC and GS in a normal period and a stress period.
- Record actual FMP entitlement/coverage, adjustment conventions and dated cutoffs.
- Establish historical expired-option bid/ask coverage separately from stock data.
- `.env` is local secret input only, not experiment metadata. Never save API keys in outputs or logs.

Gate status requires actual sample evidence, not API scaffolding. Missing credentials or unknown historical option coverage remain explicit restrictions.

## Stages 3–7: market-informed research and breadth gate

3. Reconcile a small historical replay with signed positions, puts/calls, multipliers, multiple expiries, equities and lifecycle events. Model contracts on historical stock prices are identified as such; they are not an executable listed-option backtest.
4. Generate dated, past-only volatility/covariance estimates and dependence stresses for 8–12 eligible names. Separate physical risk scenarios from Q valuation.
5. Test incremental 5-/20-session variance and portfolio-risk forecasts with chronological, release-aware evaluation and treatment of overlapping labels.
6. Hold a fixed 6–10-name equity portfolio across overlay comparisons, including less equity risk, ETF protection, single-name/sector puts, spreads/collars and adaptive coverage. Do not automatically delta-neutralize protective options.
7. Expand through 3/10/25/40–50 names using master-universe paths/subsets, constant total exposure, coverage and membership controls, untouched periods, plausible execution and uncertainty accounting for shared episodes.

The user refers to the stage-7 target as Research Gate 2. That target requires the above empirical and validation evidence. Stage-1 synthetic results cannot establish it. Missing historical market observations, historical membership, release-time features or option-quote coverage must be recorded, not substituted with fabricated data.

## Work ownership

Root integrates shared inputs, frozen experiment protocols, runners, notebooks, reports and gates. Separate workers own the policy/accounting extension, independent uncertainty/validation, and market-data audit. A follow-on engine worker builds the small model-contract replay independently. Shared files have one active owner.

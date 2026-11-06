# Requirements before the next economic protocol is frozen

This is a design boundary and work specification, not a frozen economic experiment or authorization to purchase data. Conditional Release 2 is independent of this future work. No new policy mapping or economic evaluation was run during publication integration.

The exact policy mapping, contracts, execution rules and statistical protocol must be written and hashed before any further economic run. The current exposed history cannot become an untouched test by acquiring better quotes. Retrospective remeasurement must be labelled retrospective; a renewed confirmatory claim requires genuinely prospective or independently sequestered observations.

## Required data and engine behavior

Prioritize a small verified panel of timestamped option bid/ask and full contract terms, including expired contracts. Add dated dividends, financing, borrow/rebate treatment and restrictions on short proceeds. Verify timestamps, expiry conventions, corporate actions and exercise/settlement terms before admission. No missing quote may silently fall back to a model value.

The engine needs dated entry/exit, quote-driven marks, separate spread/fee accounting and a pre-fill premium limit. Limits must be based on quotes visible before the assumed fill; whole-contract resizing and a recorded no-trade outcome are required. The fill convention must distinguish observed quotes from demonstrated fills. Gross premiums paid/received, net premium, stock/option costs and financing remain separate ledger fields.

If the study claims continuous performance, carry and reconcile holdings/cash across rolls. Report total dollar delta and appropriate factor exposure including options, inception gross/net drift, realized spend/allowance and both initial-capital and running-peak-normalized drawdowns. Do not infer total beta from the existing equity-only beta field.

## Freeze checklist

1. Use a twenty-session decision/evaluation horizon aligned to the forecast target. Specify the exact return interval, option maturity, exit date, forecast cutoff and execution lag; a next-close fill must not silently shift the target interval.
2. Freeze one modest adaptive put policy and one static put comparator. Forecasts may change coverage, never the valuation of an identical option. Freeze issuance behavior for a live origin without a known future target.
3. Preserve the core equity mandate and a predetermined equity-reduction comparator. Do not match exposures or upside to realized test outcomes.
4. Freeze a common valuation/execution convention, premium cap, contract-rounding rule, quote quality/age rules, no-trade fallback and treatment of unfilled orders.
5. Freeze retained-exposure/upside requirements, gross and net premium constraints, financing limits and short-proceeds restrictions.
6. Name one primary downside estimand and its horizon/tail convention; define secondary return, cost and upside measures. Set dependence treatment, block-length sensitivities, multiplicity rules and minimum sample requirements in advance.
7. Record data provenance, sample eligibility, prospective/sequestered cutoff, model fits, policy mapping, protocol hash and selection lock before evaluation. For retrospective measurements, retain that label regardless of lock timing.

Better funding variables are a later focused extension: uninsured/runnable funding, maturity, securities losses relative to capital and liquidity, with parent/subsidiary mapping and failed-name coverage. Deposits/liabilities must not be treated as a complete test of funding vulnerability.

The [owner addendum](equity_overlay_review_addendum.md) supplies detailed engine/data requests. The [release claims supplement](Final%20Findings%20and%20Takeaways/research_release_2_claims_and_errata.md) preserves the original results and post-hoc diagnostic boundaries.

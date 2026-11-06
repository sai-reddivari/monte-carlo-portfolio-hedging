# Financial Sector Hedging Under Trading Costs and Model Uncertainty

Conditional Research Release 2. Prepared November 5, 2026, America/Chicago. This is a local publication package; no public upload has occurred. Full empirical Research Gate 2 remains open. Human review is separate from the computational and independent reviews reported here.

## Abstract

We study portfolio hedging through controlled simulation and historical model-contract replay. A locked maturity-sensitive delta hedge met its expected-cost screen and reduced ES95 relative to weekly hedging; its ES95 difference from daily hedging was inconclusive at lower trading cost. Historical extensions evaluated five- and twenty-session variance forecasts, filing-aware financial features and eight protection policies for a ten-name financial-sector equity long/short mandate. Forecast improvements depended on metric and horizon, while tested deposit-share features worsened incremental QLIKE. Model-priced option protection showed substantial pricing and window-placement sensitivity. Exposure reduction was a strong benchmark; collar protection sacrificed substantial upside. The study identifies the market-data and execution evidence needed before claiming incremental economic hedge value.

## Scope and design

The framework links validated portfolio inputs, discrete option hedging, cash/stock/option ledgers, chronological forecasts and equity-overlay comparisons. Frozen protocols, selection locks, source/input hashes, executed notebooks and machine-readable results support reconstruction. Original frozen result directories are preserved; [claims and errata](research_release_2_claims_and_errata.md) supply the corrected interpretation.

The historical input panel contains ten financial-sector issuers and SPY/XLF over 4,236 exchange-aligned sessions from January 4, 2010 through November 4, 2026. Prices are split-adjusted closes without dividend cash flows. Fifty current names were audited for breadth: 42 have complete histories and eight partial histories are retained. Historical membership and failed-name coverage are not established.

**Historical options are hypothetical European contracts, valued with Black–Scholes. No historical option quotes or observed implied-volatility surface have been acquired.** Historical overlays use trailing-return volatility as an explicit pricing assumption. Financing is illustrative, with omitted dividends, short-dividend payments, borrow/rebate spreads, margin, option bid/ask and American exercise. Separate-window accounts are not a continuous portfolio return series. Historical inference is exploratory and based on few tail observations.

## Controlled hedging result

Fourteen periodic and delta-band candidates were frozen for a three-name short-call book with $300,000 initial underlying notional, 63 sessions and a 5 bp one-way stock charge. Selection used 5,000 simulated Q paths; the selected policy was locked before generating 10,000 held-out paths. The expected financed stock-cost allowance was $500, screened using the upper endpoint of a two-sided 95% Monte Carlo interval. This is an expected-cost screen, not a pathwise spending cap.

| Held-out result | Locked maturity-sensitive band | Daily hedge | Weekly hedge |
|---|---:|---:|---:|
| Loss ES95, dollars | 3,327.95 | 3,326.05 | 6,242.90 |
| Mean financed stock cost, dollars | 487.97 | 545.69 | 336.13 |

The selected rule's cost upper endpoint was $490.18. Its ES95 improvement relative to weekly was $2,914.96, or 46.7%, with pointwise paired 95% interval for selected-minus-weekly [−$3,100.69, −$2,710.43]. Relative to daily, the ES95 difference was +$1.90 [−$31.61, +$33.56], at about 10.6% lower financed stock cost. This supports a conditional cost–risk tradeoff. It does not establish equivalence with daily hedging, historical alpha or robustness to an unspecified physical return process.

All 28 selection/evaluation cases, the ledgers, lock order and uncertainty intervals were independently reconstructed. See [frozen controlled report](../results/research-release-1/release-1/report.md) and [independent validation](independent_validation.md).

## Forecast evidence

Models use 2010–2017 training, 2018–2020 validation and 2021 onward test data. Targets are five-/twenty-session cumulative squared log returns. Training-only transformations and validation-selected regularization are locked before test prediction. Date-level block bootstrap retains cross-name dependence; name forecasts within the same date are not independent observations.

Price-only ridge improves QLIKE relative to EWMA at both horizons, with favorable pointwise intervals. At five sessions its MSE is 29.3% worse as a point estimate, but the paired MSE interval includes zero. At twenty sessions, pointwise intervals favor ridge for both QLIKE and MSE. These metrics weight errors differently; neither result alone establishes improved hedging.

The **final financial-feature extension covers ten names for liabilities/assets and six eligible banks for deposits/liabilities**, alongside the original three-name/two-bank cohorts. It uses SEC filing-linked observations, conservative next-session-close availability and limits on both release and fiscal-period staleness. Matched financial samples have 276 five-session and 69 twenty-session origins, ending in July 2026 because of Citi staleness; price-only samples have 293 and 73 origins.

| Incremental QLIKE comparison | Five-session difference and pointwise 95% interval | Twenty-session difference and pointwise 95% interval |
|---|---|---|
| Liabilities/assets versus market-sector model, ten names | −0.00660 [−0.01095, −0.00279] | +0.00648 [+0.00167, +0.01101] |
| Deposits/liabilities versus market-sector model, six banks | +0.01501 [+0.00056, +0.03266] | +0.06993 [+0.02808, +0.12480] |

Lower is better. The liability ratio provides a small horizon-specific gain; the tested deposit proxy worsens incremental QLIKE at both horizons. This concerns the proxy, model and cohort, not the general relevance of funding vulnerability. Adding SPY/XLF information or ratio/sector-return interactions does not establish a broad incremental gain. Macro information and forecast-to-hedge economic value remain untested.

Evidence: [final ten-name/six-bank feature report](../results/feature-research-20261106T024244836968Z/report.md), [original-cohort report](../results/feature-research-20261106T024225834886Z/report.md), [feature methods and reconstruction](feature_research.md).

## Historical equity overlays

The core mandate targets 90% long and 40% short equity at the decision close: 130% gross and 50% net on $100 million capital. Lagged whole-share execution produced test inception gross exposure of 126.644%–140.634%. Comparisons share the same executed base holdings. Policies use independent 63-session accounts, a one-session execution lag, 11 validation windows and 23 test windows. Validation selects one policy per family; no policy is reselected using test results.

**The stage 6 tail statistic is the mean loss of the worst six of 23 test windows**, a 25% tail fraction with ceiling rounding. It is not Gate 1's ES95. Values below are percentages of initial capital per window; upside retained is the ratio of aggregate policy gains to baseline gains in baseline-up windows.

| Policy | Worst-six mean loss | Mean window P&L | Upside retained |
|---|---:|---:|---:|
| Unhedged | 6.280 | 1.644 | 100.0% |
| Equity reduced to 75% | 4.458 | 1.484 | 78.7% |
| XLF stock hedge | 5.232 | −0.086 | 25.1% |
| Purchased single-name puts | 5.700 | 1.451 | 93.4% |
| Purchased calls protecting short equities | 6.516 | 1.738 | 105.0% |
| Purchased sector puts | 6.058 | 1.399 | 93.5% |
| Collar | 2.906 | −0.033 | 13.2% |
| Price-history-informed puts | 5.990 | 1.532 | 96.3% |

Reduced equity is a strong benchmark. Purchased-put tail differences versus unhedged are inconclusive under the reported pointwise intervals. The collar reduces modeled tail loss, but substantially changes exposure and sacrifices upside: mean initial local dollar delta changes from +50.401% to −5.385% of capital. Delta is not market beta, and no attribution establishes that the entire protection benefit is explained by reduced exposure.

Purchased short-sleeve calls can reduce short-sleeve losses while worsening whole-book downside ES. Including marginal premium financing gives short-side loss capture of 0.946695, compared with 0.946109 in the original sleeve metric. This is a narrow side-specific result, not whole-portfolio dominance.

Nominal annual premium allowances are decision-time sizing rules, **not enforced execution-time caps**. Worst test-window premium/allowance ratios are 1.304 for long puts, 2.599 for purchased short-sleeve calls, 1.269 for sector puts, 4.125 for the collar and 1.303 for price-informed puts. No retrospective resizing replaces those outcomes.

The independent reviewer reconstructed all 2,013 base-case policy/window terminal outcomes from raw prices and the frozen protocol without calling production pricing, risk, replay or overlay functions. Maximum absolute terminal-P&L discrepancy was $1.1921e-7. All 276 test collar legs and original paired block-bootstrap intervals also reconstructed. This does not certify every intrawindow mark/drawdown, sensitivity run, vendor observation or market execution assumption.

Evidence: [frozen stage 6 report](../results/equity-overlays-20261106T023430248130Z/report.md), [permanent reviewer archive](../results/research-release-2/astra-review-20261106/archive_manifest.json), [corrections and diagnostic interpretation](research_release_2_claims_and_errata.md).

The [overlay owner addendum](equity_overlay_review_addendum.md) accepts Astra's corrections and supplies targeted owner checks. It preserves the original experiment and separates episode-specific observations and hypotheses from supported conclusions. Its aggregate-budget clarification does not remove individual-window overruns; its pre-fill quote requirement is carried into the next-study requirements.

## Post-hoc robustness and breadth

Reviewer comparisons against the existing 75%-equity benchmark are explicitly post-hoc. Single-name, sector and price-informed puts have greater worst-six losses by 1.241, 1.599 and 1.531 percentage points, with positive pointwise intervals. They also preserve more upside; these results do not establish overall dominance by reduced equity. The collar's incremental tail advantage is unresolved: −1.552 [−3.034, +0.773].

Window-placement diagnostics fix offsets of 0/5/21/42 sessions and report every offset without policy reselection. Long-put validation tail improvement over reduced equity changes from +7.005 to −0.230 points between the original and 42-session offset. Test puts have greater tail loss than reduced equity at all four offsets, while retaining more upside. Sector-put test benefit versus unhedged changes sign at offset 42. The offsets overlap and alter both timing and included end-period observations; they cannot be pooled as additional independent crises.

Breadth experiments preserve total notional and use exact subsets of common master-universe paths through forty names. In the canonical calibrated case, selected-policy ES95 is $4,521.13 at twenty-five names and $4,640.84 at forty names. More names do not guarantee lower risk when composition and factor exposures change. The universe is retrospectively conditioned on current survival and data availability; full empirical stage 7 generalization is not established. See [breadth report](../results/breadth-20261106T020730752645Z/report.md).

## Conclusion and next study

A controlled hedging experiment identifies a favorable cost–risk tradeoff. Historical extensions show that forecast improvements depend on metric and horizon, while model-priced option protection depends materially on pricing, exposure and evaluation-window assumptions. Incremental economic hedge value remains unestablished.

The next economic study should prioritize a small verified timestamped option quote panel, contract terms, dividends and realistic financing/borrow. A twenty-session horizon should align the forecast target and economic evaluation. Adaptive and static protection must share execution conventions, hard premium caps and a predetermined equity-reduction benchmark, with downside and retained-upside objectives frozen before evaluation. Retrospective quotes improve measurement of exposed history; they do not make that history an untouched test again.

The [evidence checkpoint](../reports/research_status.md) records publication-package readiness separately from empirical gate status. Original reports remain frozen, and the [claims supplement](research_release_2_claims_and_errata.md) controls their interpretation.

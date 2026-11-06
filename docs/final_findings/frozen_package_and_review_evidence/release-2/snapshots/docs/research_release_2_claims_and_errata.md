# Research Release 2 claims and errata

This supplement accompanies the [publication summary](research_release_2_publication.md). It corrects interpretation without rewriting the original hashed experiments. Astra's full shared review and unmodified diagnostic files are preserved in the [permanent review archive](../results/research-release-2/astra-review-20261106/archive_manifest.json). Reviewer diagnostics use already exposed outcomes and are explicitly post-hoc. No original policy, position size or test date was replaced.

Opus's [owner addendum](equity_overlay_review_addendum.md) accepts all of Astra's corrections and contests none of the reported numbers. His original write-up remains unchanged. The corrections here control the release interpretation; the addendum's supplementary calculations are owner checks, not additional confirmatory evidence.

## Claim boundaries and corrections

| Topic | Publication wording and boundary |
|---|---|
| Release status | Conditional Research Release 2 can be publication-ready while full empirical Gate 2 remains open. Code success, independent accounting, publication readiness and empirical certification are separate decisions. |
| Option prices | Hypothetical European Black–Scholes contracts on historical stock paths. No acquired historical option quotes, executable fills or observed implied volatility. |
| Premium budget | A nominal annual allowance for decision-time sizing, not an execution-enforced cap. “Within a 2% budget” is too strong. Original overruns remain results. |
| Equity exposure | 130% gross/50% net are decision-close targets. Test executed inception gross exposure ranges 126.644%–140.634%; policies share base holdings. |
| Collar | Mean initial local dollar delta shifts from +50.401% to −5.385% of capital and upside retained is approximately 13%. This is a material exposure/upside tradeoff. The entire benefit has not been attributed to exposure reduction. |
| Beta | The saved beta field includes equity/ETF sleeves and omits options. It cannot establish matched total-portfolio beta. Local Black–Scholes delta is not market beta. |
| XLF “cost” | Mean −1.73 percentage-point P&L difference per window is underperformance versus unhedged, including exposure and financing, not transaction cost or premium. Actual stock costs are reported separately. |
| Tail loss | Stage 6 averages the worst six of 23 separate 63-session test-window outcomes: 25% tail fraction with ceiling rounding. Gate 1 uses ES95 on 10,000 simulated outcomes. These are different estimands. |
| Episodes | Four contiguous clusters of baseline tail windows are not four demonstrated independent crises. Overlapping shifted windows do not add independent observations. |
| Drawdown | At each observation, running-peak NAV minus current NAV is divided by **initial capital**; the saved statistic is the maximum of those declines within a window. It is not divided by the running peak and is not a full-period chained-NAV drawdown. |
| Short-side calls | Purchased calls protect short equities; they are not written calls. Whole-book downside ES worsens while some short-sleeve losses are reduced. Neither finding contradicts the other. |
| Short-sleeve capture | Original 0.946109 capture excludes marginal premium financing. Including that financing gives 0.946695. The direction survives; a roughly 5.3%–5.4% reduction is a side-specific metric. |
| Forecast metrics | Five-session own-price ridge MSE is 29.3% worse as a point estimate, with paired MSE interval crossing zero. Twenty-session ridge has favorable pointwise intervals for QLIKE and MSE. No hedge-value inference follows automatically. |
| Feature scope | Final extension tests generic liabilities/assets on ten names and deposits/liabilities on six banks, retaining earlier three-name/two-bank cohorts. Do not describe the final extension as only three names/two banks. |
| Funding interpretation | Adverse deposit-share results concern that proxy/model/cohort. Deposits/liabilities is not a complete measure of runnable funding, liquidity or solvency vulnerability. |
| Inconclusive inference | An interval including zero does not prove no useful protection. Pointwise intervals excluding zero are not multiplicity-adjusted discovery guarantees. |

### Realized premium spend

Ratios compare realized net premium at execution with each policy's nominal window allowance. The purchased short-sleeve call selected a 1% annual allowance; most other option policies selected 2%, while the adaptive policy changes its sizing allowance by state.

| Selected policy | Worst test spend/allowance |
|---|---:|
| Purchased long-name puts | 1.304× |
| Purchased calls protecting shorts | 2.599× |
| Purchased sector puts | 1.269× |
| Collar | 4.125× |
| Price-history-informed puts | 1.303× |

The collar reaches 6.517× in validation. Overnight movement between decision and execution changes the premiums of already-fixed strikes and contract counts. Net collar spending is especially unstable because it is the difference between large gross premiums. The test collar's annualized gross outlay and receipts are 11.532% and 11.387% of capital; the 0.145% net does not represent the gross cash or spread exposure. Hard execution-time caps require a new protocol, not replacement of frozen outcomes.

Whole-split spending and worst-window spending answer different questions. Opus's owner check reports test total premium/total allowance ratios of 0.927 for long puts, 0.911 for adaptive puts, 0.932 for sector puts, 1.131 for purchased short-sleeve calls and 0.072 for the collar. The collar's validation ratio is 1.166. Most test policies underspent in aggregate, but this does not eliminate the individual-window overruns or make the sizing allowance a hard cap.

The next protocol must enforce a premium limit against a quote visible **before** the assumed fill, with whole-contract resizing and a no-trade fallback. Resizing from an execution close and assuming a fill at that same close would reintroduce the timing problem the lag was intended to avoid.

## Independent review scope

Astra's portable accounting reconstruction starts from raw prices and the frozen protocol. It does not call production replay, overlay, valuation or risk functions or reuse saved option legs. It reconstructs volatility, beta, EWMA state, stock holdings, contract rounding, premium, terminal payoff, stock costs and financed cash.

- All 2,013 base-case outcomes: 33 candidates × 61 training/validation/test windows.
- Maximum absolute terminal-P&L discrepancy: $1.1921e-7.
- Frozen source, input, config and artifact checks pass.
- All 276 test collar legs reconstruct, with correct signs and calls covered by owned shares.
- Independently implemented NumPy paired block-bootstrap intervals reproduce the originals to approximately 1.8e-15.

This scope does not certify every intrawindow mark/drawdown, every sensitivity run, the vendor's observations or executable option pricing. The archived review summary records these exclusions. The current combined suite is separately recorded in [release test evidence](../reports/release_2_tests.xml); Astra's prior run reported 194 tests plus 22 subtests, with 28 timezone deprecation warnings.

## Post-hoc comparisons against reduced equity

These comparisons use the pre-existing 75%-equity benchmark without reselection. The estimand is selected-policy minus benchmark worst-six-window mean loss, in percentage points of initial capital. Positive means greater tail loss under the option/ETF policy. Intervals are pointwise paired block-bootstrap 95% intervals.

| Selected policy | Difference versus reduced equity | Pointwise 95% interval |
|---|---:|---|
| Long-name puts | +1.241 | [+0.944, +1.395] |
| Sector puts | +1.599 | [+0.678, +2.446] |
| Price-history-informed puts | +1.531 | [+1.032, +1.739] |
| Collar | −1.552 | [−3.034, +0.773] |
| XLF stock hedge | +0.774 | [−1.358, +3.143] |

The collar's incremental tail advantage remains unresolved. Purchased puts retain substantially more upside than reduced equity, so the tail comparisons do not establish overall economic dominance. Bootstrap block lengths 2/4/6 preserve the qualitative original conclusions versus unhedged; they do not address sparse crises, multiplicity, selection uncertainty or model-price uncertainty.

Evidence: [paired review diagnostics](../results/research-release-2/astra-review-20261106/statistical_review/paired_es_diagnostics.csv), [review metadata](../results/research-release-2/astra-review-20261106/statistical_review/metadata.json).

## Post-hoc window placement

Before running the diagnostic, the reviewer fixed offsets 0/5/21/42 trading sessions, preserving all eight selected policies, 63-session holding periods, pricing, sizing, capital and split boundaries. Past-only estimates update at shifted decision dates. All offsets are reported; none is selected.

The diagnostic completed 1,936 policy/window replays and all existing accounting checks passed. Offset zero exactly reproduced the frozen selected summaries. Frozen source/input hashes remained unchanged. It uses the production engine and is not another independent ledger implementation.

Long-put tail-loss **reduction** in percentage points of initial capital:

| Comparison | Offset 0 | Offset 5 | Offset 21 | Offset 42 |
|---|---:|---:|---:|---:|
| Validation versus unhedged | 10.351 | 7.042 | 7.219 | 2.229 |
| Validation versus reduced equity | 7.005 | 4.098 | 4.096 | −0.230 |
| Test versus unhedged | 0.580 | 1.207 | 0.810 | 0.164 |
| Test versus reduced equity | −1.241 | −0.998 | −1.302 | −1.369 |

Validation's long-put advantage over reduced equity changes sign at the 42-session shift. Test puts have higher tail losses than reduced equity at each offset while preserving more upside. Sector-put test benefit versus unhedged also changes sign at offset 42. Shifts change timing **and included end-period observations**; shifted samples overlap and cannot be pooled. No new significance intervals were computed for the shifts.

These findings show sensitivity to the specified contracts and partition. They do not show that COVID protection was an accounting artifact, that validation should be disregarded or that protection is useless.

Evidence: [diagnostic protocol](../results/research-release-2/astra-review-20261106/window_placement/diagnostic_protocol.json), [completion](../results/research-release-2/astra-review-20261106/window_placement/completion.json), [written findings](../results/research-release-2/astra-review-20261106/window_placement/summary.txt). Original diagnostic protocol SHA256: `057b938dbd6c4e9fdfe1cfa13f4d583328bb282e4ed43b6693464dbf033b10b0`.

## Conclusions to avoid

Do not infer that options only pay in fast crashes, that validation is an irrelevant outlier, that training/test agreement proves typical outcomes, or that purchased calls are redundant because equity sleeves are negatively correlated. Not using training for selection is not inherently an error. “Expensive scaling” and “late signals” can motivate a next hypothesis, but the frozen experiment does not identify them as universal causes.

The supported wording is that protection benefits were concentrated in particular episodes under the specified contracts, windows and model-pricing assumptions. The absence of a decisive benefit does not demonstrate absence of useful protection.

The original overlay write-up's statements that protection was “mostly exposure sold,” that policies reduced risk “mainly by holding less market exposure,” and that higher trailing volatility explained weaker coverage are not established causal attributions. Exposure reduction is the mechanism of the reduced-equity benchmark; collar attribution requires more work. “The risk signal fired after the damage” is descriptive for these selected windows, not an established general property. Opus withdraws claims based on comparators matched to realized test upside; those comparisons are not release evidence. No observed skew surface supports a universal assertion about how real skew would change every collar result.

## Next evidence and publication status

Descriptive robustness of exposed outcomes is Track A. A new economic study is Track B: timestamped bid/ask and contract terms first, then dividends and realistic financing/borrow, aligned twenty-session forecasting and evaluation, hard execution-time caps, static/adaptive comparators, retained-exposure requirements and predetermined inference rules. Freeze the exact mapping and protocol before another economic run. Quotes on exposed dates improve retrospective measurement, not untouched-test status.

Opus identifies the next engine requirements: dated option entry/exit, quote-driven valuation with missing-quote failure, pre-fill premium limits and fill/rejection records, separate option costs, carried holdings/cash, financing/dividends/lifecycle treatment and total option-inclusive exposure. Forecast issuance must work without requiring the subsequent realized target. These are requests for a separate future protocol; none is represented as implemented by this publication release.

Original frozen stage 6 protocol SHA256: `18948e86cef72c6b2bc183cc6e7d5ebba49cb9788806463864d57efdaf6079b6`. The [evidence index](../reports/research_status.json) records package readiness, owner-addendum integration and open empirical gates separately. Public upload and data purchase have not occurred.

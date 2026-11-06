# Stage 6 overlay review addendum

Owner response to Astra's review of the Stage 6 equity overlay study. It supplements the [original write-up](equity_overlay_research.md) and the [frozen run](../results/equity-overlays-20261106T023430248130Z/report.md), and replaces neither. Results remain **European model options on historical underlying prices**: no separate options source has been acquired, and historical option quotes and implied volatility remain an open data requirement.

## Summary

I accept all of Astra's corrections and contest none of its numbers. I recomputed the Stage 6 figures from the frozen outputs, and they match. Two corrections get a clarification below, and one adds a usable design point for the next protocol.

Five things change how the study should be read:

- **The 2% budget was an allowance, not a cap.** Sizing met it at the decision close in every window, but realized spend reached 4.13× in one test window.
- **My collar wording went too far.** The collar materially changes exposure and gives up most of the upside. Whether exposure explains its whole benefit has not been shown.
- **My short-call wording used the wrong evidence.** Negative sleeve correlation proves nothing, because a short position's signed P&L is negative whenever stocks move together.
- **The COVID result depends on window placement.** Shifting windows moves the worst unhedged validation window from −27.84% to −10.63%, and the long-put advantage over reduced equity changes sign at one shift.
- **Several of my interpretations are hypotheses, not conclusions.** They are separated in [Hypotheses and conclusions](#hypotheses-and-conclusions).

No policy, parameter or frozen result changed. Frozen source and input hashes still match protocol `18948e86cef72c6b2bc183cc6e7d5ebba49cb9788806463864d57efdaf6079b6`. Everything here using 2021 onward is post-hoc.

## Disposition of each correction

| Correction | Decision | My check |
| --- | --- | --- |
| Budget is a nominal allowance | Accepted | All five worst-window multiples reproduce |
| Inception gross 126.644%–140.634% | Accepted | Reproduced, with net 48.065%–52.886% |
| Collar delta and upside | Accepted, wording retracted | +50.401% stock and −5.385% total reproduce |
| ETF 1.73% is underperformance, not a cost | Accepted | My brief's table wrongly said "cost" |
| Tail statistic is the worst six of 23 windows | Accepted | Matches `summarize`; it is not ES95 |
| "Four episodes" are contiguous clusters | Accepted | Matches `tail_episodes`, which only merges adjacent windows |
| Drawdown divides by initial capital | Accepted | Matches `window_record` |
| Short-side calls are purchased, and both statements hold | Accepted | See [Short sleeve and whole book](#short-sleeve-and-whole-book) |
| Sleeve capture with financing is 0.946695 | Accepted | 0.946109 before and 0.946695 after, using −$45,530 of marginal interest |
| Forecast and deposit-share wording | Accepted | Outside my ownership, not rechecked |
| Prohibited interpretations | Accepted, three are mine | See [Errata](#errata) |
| Reduced-equity comparison | Accepted | All five point differences reproduce |
| Window-placement table | Accepted | Reproduced from `window_records.csv`; protocol hash matches |

**Clarification on the budget.** The worst-window multiples are correct but overstate overspending across a whole split. Total realized premium over total allowance is shown below, and only the short calls exceeded it in test.

**Clarification on the execution-time cap.** Astra's cap should apply as a price limit against a quote visible before the fill. Using the execution close to resize a position would bring back the same-close dependence the one-session lag removed.

## Budget overruns

Each position was sized so its premium, priced at the decision close, fit the allowance. Strikes and contract counts then stayed fixed while the stock moved to the next close.

To isolate this effect, I repriced the actual contracts at both closes:

| Test policy | Worst, priced at decision close | Worst, priced at execution close | Windows over allowance | Total premium over total allowance |
| --- | ---: | ---: | ---: | ---: |
| Long puts | 1.000× | 1.304× | 9 of 23 | 0.927 |
| Risk-informed puts | 1.000× | 1.303× | 9 of 23 | 0.911 |
| Sector puts | 1.000× | 1.269× | 12 of 23 | 0.932 |
| Short calls | 0.999× | 2.599× | 13 of 23 | 1.131 |
| Collar | 0.955× | 4.125× | 9 of 23 | 0.072 |

In validation, the worst multiples at execution were 1.316×, 1.316×, 1.419×, 1.183× and 6.517× in the same order. The collar's total there was 1.166.

So the overrun comes from the decision-to-execution gap, not from a sizing error. Across validation and test windows, premium slippage had a correlation of −0.94 to −0.95 with the average price gap for puts, +0.98 for calls and −0.99 for the collar.

The two largest test cases show why:

- **Short calls, test-017:** names rose an average of 9.7% between the two closes during the April 2025 rally, and GS moved from 462.22 to 516.87. Its 508.44 strike was already in the money when it traded.
- **Collar, test-002:** names fell 2.7%, which made the purchased puts dearer and the written calls cheaper at once. The collar paid 11.53% and received 11.39% of capital per year, so a small move in either leg is large relative to its net cost.

The lag is the right choice for avoiding same-close signals, and this is its price. Results should not be resized, because a hard cap belongs in a new protocol.

## Execution exposure drift

The 130% gross and 50% net figures are targets at the decision close. Whole shares are fixed from that close and then move with the market until execution.

| Split | Gross range at inception | Net range at inception |
| --- | --- | --- |
| Validation | 125.795%–132.822% | 46.619%–50.668% |
| Test | 126.644%–140.634% | 48.065%–52.886% |

The test extremes are 2021-07-06 for the low and 2025-04-09 for the high, the same dates as the largest premium overruns. Test means were 131.0% gross and 50.4% net.

Every policy except reduced equity holds the same core shares in a window, so comparisons between them remain valid. The drift does mean a window's actual exposure can differ from the stated mandate.

## Collar exposure and upside

Mean initial dollar delta across the 23 test windows, as % of capital:

| Component | Mean delta |
| --- | ---: |
| Stock | +50.401 |
| Purchased puts | −26.19 |
| Written calls | −29.60 |
| **Total** | **−5.385** |

The total ranged from −22.5% to +3.2%. This is local Black-Scholes delta at flat volatility, not market beta, and the saved beta field leaves out options entirely.

Against unhedged, the collar added a summed 32.53 points across the 11 down windows and gave up 71.12 points across the 12 up windows. It paid $74.2M on written calls in 13 windows and received $36.4M on puts.

The supported statement is that the collar materially changes exposure and sacrifices upside. Its tail advantage over reduced equity stays unresolved: 1.552 points at the original windows, with an interval spanning zero. The point estimate favored the collar at all four window offsets, but those offsets overlap and are not independent evidence.

## Short sleeve and whole book

These purchased calls answer two different questions, and both answers hold:

- **Whole book:** they worsened tail loss by 0.24 points. Across the six worst book windows they paid only $0.14M, and option P&L there was −$1.40M after premium. The book's tail windows are mostly selloffs, when shorts tend to gain.
- **Short sleeve:** in the 16 windows where the sleeve lost money, loss capture was 0.946 (0.947 with financing), so losses fell by about 5%. The worst sleeve window improved from −11.46% to −9.37%. Coverage averaged 25%.

Across all 23 windows the calls added $2.14M net, and $7.89M of the $8.72M they paid in sleeve-loss windows came when the whole book made money. That is a description of this sample, in which these shorts rose. It doesn't show the calls are redundant, because a mandate may care about the short sleeve in its own right.

## Drawdown definition

The reported statistic is, for each window:

> max over sessions of (running peak NAV − NAV) ÷ initial capital

- The running peak starts at initial capital and is reset in each window.
- The denominator is initial capital, not the running peak, so it differs from a conventional percentage drawdown when NAV has risen.
- It can be large in a profitable window. `long_put_k90_b2` in validation-009 shows 18.01% with a +4.94% result.
- Option marks use the window's fixed pricing volatility, so mid-window marks don't reflect volatility spikes. Astra's reconstruction did not certify intrawindow marks. My hand checks cover one worst-mark date in each of four windows.

## Window placement (post-hoc)

Astra fixed offsets of 0, 5, 21 and 42 sessions before running this. Offset 0 reproduces the frozen summaries, and all offsets are reported. They overlap, so they must not be pooled as extra observations.

Reduction in tail loss against unhedged, in points:

| Measure | Offset 0 | 5 | 21 | 42 |
| --- | ---: | ---: | ---: | ---: |
| Worst unhedged validation window, % | −27.84 | −20.51 | −22.74 | −10.63 |
| Long puts, validation | 10.35 | 7.04 | 7.22 | 2.23 |
| Long puts vs reduced equity, validation | 7.01 | 4.10 | 4.10 | −0.23 |
| Long puts, test | 0.58 | 1.21 | 0.81 | 0.16 |
| Long puts vs reduced equity, test | −1.24 | −1.00 | −1.30 | −1.37 |
| Long puts vs reduced equity, training | −0.37 | −0.61 | −0.46 | −0.39 |
| Sector puts, test | 0.22 | 0.49 | 0.01 | −0.11 |
| Reduced equity, test | 1.82 | 2.21 | 2.11 | 1.53 |
| Short calls, test | −0.24 | −0.28 | −0.25 | −0.24 |

The offsets change the crash being measured as well as the protection. The original window ran from 2020-01-03 to 2020-04-03, close to the market low. At offset 42 the worst window starts 2020-03-05 and ends after the rebound. A European option paying only at expiry is sensitive to where that date falls.

Three readings are supported:

- The large validation advantage of puts over reduced equity depends on the window partition.
- Puts had higher tail loss than reduced equity at every offset in test and training, while retaining more upside. That is a tradeoff, not dominance.
- Reduced equity moved far less than the option policies across offsets.

None of this shows COVID protection was an accounting artifact or that protection is useless.

## Hypotheses and conclusions

**Supported by the frozen experiment, under its contracts, windows and pricing:**

- Test-period benefits of purchased puts, sector puts and risk-informed puts against unhedged were inconclusive.
- Benefits were concentrated in particular episodes.
- Results depended materially on pricing volatility.
- Reduced equity was a strong benchmark.
- The collar sacrificed substantial upside.
- Purchased calls worsened whole-book tail loss while reducing some short-sleeve loss.

**Hypotheses only, not to be stated as findings:**

| Hypothesis | Where it stands |
| --- | --- |
| Puts act like expensive scaling outside crashes | Suggestive. My supporting grid matched to realized upside, which Astra rules out for future comparators. Use the fixed 75% comparison instead. |
| The collar is beaten by holding almost no book | Withdrawn as evidence. It relies on the same matching and on interest on freed cash. |
| The risk signal arrives late | Described for these windows: the ratio reached 1.25 in none of the 16 tail windows. Calm readings are common and the sample is small, so lateness is not established. |
| Validation is atypical | Not to be stated this way. Validation contains the sample's largest loss and cannot be set aside. |
| Spread risk grew in test | XLF's R² on book P&L was 0.82, 0.88 and 0.65 by split. This was a quick calculation, unreviewed. |
| Fixed budgets act as volatility timing | Weak. Coverage rises when premiums fall by construction, but it accounts for only about $6.6M of the $28.9M COVID option gain. |

My 7-lens review was paused with no agent finished, so none of these hypotheses went through refutation. Following Astra's instruction, I am not restarting it. Any further check should target a specific claim.

## Errata

The original write-up is unchanged. Please apply these in the claims supplement:

| Location | Original | Correction |
| --- | --- | --- |
| Write-up, Findings | "within the 2% annual budget" | "sized to a nominal 2% annual allowance at the decision close" |
| Write-up, Findings | "The collar's protection is mostly exposure sold" | "The collar materially changes exposure and sacrifices upside; its benefit has not been attributed" |
| Write-up, Findings | "did so mainly by holding less market exposure" | Applies to reduced equity only; use the collar wording above |
| Write-up, Findings | Long-put coverage explained by "higher trailing volatility" | Mark as an untested explanation |
| Write-up, Findings | "ETF hedge was costly" | "Underperformed unhedged by 1.73% per window on average, including exposure and financing effects" |
| Write-up, Findings and Validation | "four distinct tail episodes" | "four contiguous clusters of tail windows" |
| Write-up, Findings | ES defined only as the worst 25% | State "mean of the worst 6 of 23 test windows, 63-session windows" |
| Write-up, Study design | "130% gross and 50% net" | Add "decision-close targets; test inception gross 126.6%–140.6%" |
| Write-up, Test results | "as a percentage of capital" | "divided by initial capital, measured from the running peak" |
| Write-up, Gates | "No verified historical option quotes" | "FMP documents options as unsupported, and no other source has been acquired" |
| Brief to Astra | "Short calls duplicate protection", based on sleeve correlation | Withdrawn; use [Short sleeve and whole book](#short-sleeve-and-whole-book) |
| Brief to Astra | "seems to pay only in a fast, large crash" | Withdrawn; benefits were concentrated in particular episodes under these assumptions |
| Brief to Astra | "2018–2020 looks like the outlier" | Withdrawn |
| Brief to Astra | Not using training was "probably a design weakness" | Withdrawn; it was a disclosed protocol choice |
| Brief to Astra | ETF "cost 1.73% per window" | Same correction as above |

## Engine and data requests for the next protocol

These are requests only. No shared module or frozen study was changed. The first four block the next study as Astra has outlined it.

**Replay owner**

1. **Dated entry and exit:** add `entry_date` and `exit_date` to `OptionPosition`. A 20-session evaluation of a longer-dated option needs an exit before expiry, and `replay` settles only at expiry today.
2. **Quote-driven valuation:** accept dated bid and ask per instrument, fill at the ask or bid, mark from a declared convention, and raise an error on a missing quote rather than fall back to a model price.
3. **Execution-time premium cap:** add a `max_premium` limit, whole-contract resizing and a no-trade outcome. Record requested contracts, filled contracts and the reason. The limit should be checked against a quote visible before the fill.
4. **Separate option costs:** report option spread and fees in their own ledger column, with gross premium paid and received kept separate.
5. **Carried holdings:** accept opening holdings and cash, so a continuous rolled book can be reconciled.
6. **Overlay sleeve:** add `overlay_holdings` beside `equity_holdings`, so ETF exposure isn't routed through the core book.
7. **Financing:** add short-rebate and borrow rates, plus a restriction on using short proceeds.
8. **Dividends and lifecycle:** add cash dividends, and early exercise and assignment for listed American options.
9. **Total exposure:** report dollar delta and beta including options, since the saved beta field cannot compare total portfolio exposure across policies.

**Risk owner**

10. **Dated estimates:** add `latest_risk_state(prices, as_of, protocol)`, including 20-session forecasts. `variance_forecasts` drops origins without a realized target, so it cannot serve a live decision date.
11. **Betas:** return loadings from `covariance_estimates`.
12. **Block bootstrap:** add a `statistic=` argument to `moving_block_mean_interval`.

**Market-data owner**

13. **Option quotes:** timestamped bid and ask with contract terms, including expired contracts. A small verified panel for the ten names and XLF would be enough to start.
14. **Dividends:** dated cash dividends for the same names.
15. **Rates and borrow:** a dated short-rate series and borrow costs.
16. **Point-in-time membership:** including failed and acquired names, for later generalization.

**Overlay owner, in the next protocol**

17. Report inception gross and net, realized spend against allowance, and both drawdown definitions as standard outputs.

Historical quotes on dates already seen improve measurement, but that work is retrospective. Confirmatory claims need prospective or sequestered observations.

## Provenance

- **My checks:** [`results/equity-overlays-review-20261106/`](../results/equity-overlays-review-20261106/) holds both scripts and their outputs. Run them from the repo root.
- **Astra's evidence:** `/tmp/astra_overlay_portable_audit/`, `/tmp/astra_statistical_review/` and `/tmp/astra_window_phase_20261106/`. These are temporary until Sol archives them, and `window_placement_check.py` needs that records file.
- **Window diagnostic protocol:** `057b938dbd6c4e9fdfe1cfa13f4d583328bb282e4ed43b6693464dbf033b10b0`, confirmed against its file.
- **Not independently certified:** intrawindow option marks, drawdowns, sensitivity runs and vendor observations. Multiplicity across policies remains unadjusted.

# Stage 6: equity portfolios with derivative overlays

**European model options on historical underlying prices.** These are not listed-option fills, and no observed implied volatility is used. Every conclusion below depends on the pricing assumptions and on 23 test windows.

## Findings

On the test period (2021-01-04 to 2026-10-12), no purchased option overlay within the 2% annual budget clearly reduced tail loss. The two policies that did reduce it clearly, a smaller book and a collar, did so mainly by holding less market exposure.

- **Validation overstated protection.** Long puts cut expected shortfall (ES, the mean loss of the worst 25% of windows) by 10.35 points in validation and 0.58 in test. Almost all of the validation benefit came from one window, Q1 2020. Without its best window, the put policy's mean gain over unhedged falls from 2.69% to 0.06% per window.
- **Purchased protection was weak in test.** Test losses were slower and shallower than 2020, and higher trailing volatility halved the coverage the budget bought (35% against 70%). At 1.5× pricing volatility the put benefit is gone (−0.04 points).
- **The collar's protection is mostly exposure sold.** It had the largest ES reduction (3.37 points), but kept 13% of the upside and had a delta-adjusted net exposure near −5%. It is also fragile: at a 0% rate its coverage falls from 100% to 49%, and on 21-session windows to 30%.
- **The reduced book was the simplest result.** Scaling to 75% cut ES by 1.82 points with an interval that excludes zero, and kept 79% of the upside.
- **The ETF hedge was costly.** XLF rose, so the short sleeve lost 2.34% per window. Its mean difference was −1.73% per window, and the ES interval spans zero. Its interest income also relies on a generous assumption that short proceeds earn the full 4%.
- **Short-side calls need a side-specific reading.** They worsened whole-book ES by 0.24 points, because book tails fall in selloffs when shorts gain. On the short side they trimmed the worst window from −11.46% to −9.37%. Coverage averaged 25%.
- **Sector puts had visible basis risk.** Their worst window (−10.58%) was worse than unhedged (−10.05%), because XLF did not fall through the strike in that window.
- **The risk signal fired after the damage.** It was elevated in 2 of 23 test windows, both following selloffs and both followed by gains. It was never elevated before one of the six tail windows. The same pattern appeared in validation: the ratio was 0.64 before COVID and 2.49 after.

## Test results

Values are % of capital per window, across 23 windows. Downside capture is the policy's loss over the unhedged loss in the 11 windows where the unhedged book lost money, so lower is better. Upside retained uses the 12 windows where the book gained, so higher is better.

| Policy | Mean P&L | Worst window | ES loss | Worst drawdown | Downside capture | Upside retained |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 1. Unhedged | 1.64 | −10.05 | 6.28 | 15.18 | 1.00 | 1.00 |
| 2. Reduced to 75% | 1.48 | −7.29 | 4.46 | 11.17 | 0.69 | 0.79 |
| 3. XLF stock hedge, 100% of beta | −0.09 | −7.55 | 5.23 | 9.59 | 0.51 | 0.25 |
| 4. Long-name puts, 90% strike | 1.45 | −8.52 | 5.70 | 11.84 | 0.98 | 0.93 |
| 5. Short-name calls, 110% strike | 1.74 | −10.26 | 6.52 | 15.50 | 1.05 | 1.05 |
| 6. XLF puts, 95% strike | 1.40 | −10.58 | 6.06 | 13.08 | 1.01 | 0.94 |
| 7. Collar, 95% put and 110% call | −0.03 | −5.10 | 2.91 | 6.11 | 0.26 | 0.13 |
| 8. Risk-informed puts, 90% strike | 1.53 | −9.28 | 5.99 | 13.15 | 0.99 | 0.96 |

Drawdown is peak-to-trough inside one window, as a percentage of capital.

### Difference from unhedged

Intervals are 95% circular block bootstrap intervals over chronological windows, using blocks of four. They are pointwise, with no adjustment for comparing seven policies. Negative ES differences favor the policy.

| Policy | Mean difference | Interval | Excluding best window | ES difference | Interval |
| --- | ---: | --- | ---: | ---: | --- |
| Reduced to 75% | −0.16 | −0.81 to 0.54 | −0.29 | −1.82 | −2.38 to −0.92 |
| XLF stock hedge | −1.73 | −3.71 to 0.31 | −2.27 | −1.05 | −3.52 to 2.16 |
| Long-name puts | −0.19 | −0.42 to 0.06 | −0.28 | −0.58 | −1.35 to 0.25 |
| Short-name calls | 0.09 | −0.09 to 0.31 | 0.00 | 0.24 | 0.15 to 0.29 |
| XLF puts | −0.25 | −0.47 to 0.09 | −0.41 | −0.22 | −1.42 to 0.52 |
| Collar | −1.68 | −4.27 to 1.11 | −2.19 | −3.37 | −5.25 to −0.16 |
| Risk-informed puts | −0.11 | −0.23 to 0.01 | −0.16 | −0.29 | −0.68 to 0.12 |

All rows are exploratory. The test has 23 windows, six tail windows and four distinct tail episodes, because three adjacent tail windows from October 2021 to July 2022 count as one. Validation has 11 windows, three tail windows and three episodes.

### Costs and financing

Annual columns are spending rates in % of capital, not compounded returns.

| Policy | Budget | Premium paid | Premium received | Net settlement | Stock costs | Interest | Worst window vs budget | Funding need without short proceeds |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Unhedged | 0.00 | 0.00 | 0.00 | 0.00 | 0.54 | 1.99 | n/a | 8.20 |
| Reduced to 75% | 0.00 | 0.00 | 0.00 | 0.00 | 0.40 | 2.50 | n/a | 0.00 |
| XLF stock hedge | 0.00 | 0.00 | 0.00 | 0.00 | 0.81 | 4.70 | n/a | 17.08 |
| Long-name puts | 2.00 | 1.86 | 0.00 | 1.10 | 0.54 | 1.97 | 1.30× | 8.41 |
| Short-name calls | 1.00 | 1.13 | 0.00 | 1.52 | 0.54 | 1.98 | 2.60× | 8.86 |
| XLF puts | 2.00 | 1.86 | 0.00 | 0.90 | 0.54 | 1.97 | 1.27× | 8.31 |
| Collar | 2.00 | 11.53 | 11.39 | −6.57 | 0.54 | 1.99 | 4.13× | 4.40 |
| Risk-informed puts | 1.09 | 0.99 | 0.00 | 0.55 | 0.54 | 1.98 | 1.30× | 8.41 |

Ledger borrowing peaked at zero for every policy, because short proceeds are treated as usable cash. The last column removes that assumption.

Budgets are met on average but not in every window. Sizing happens at the decision close and execution happens one session later, with the strike already fixed. In window test-017, GS closed at 462.22 at the decision and 516.87 at execution, so the 508.44 call was in the money before it traded. A collar's net premium is a small difference between two large premiums, so it moves the most: 4.13× budget in test and 6.52× in validation.

### Exposure changes

| Policy | Gross | Net | ETF | Delta-adjusted net | Beta-adjusted net |
| --- | ---: | ---: | ---: | ---: | ---: |
| Unhedged | 131.0 | 50.4 | 0.0 | 50.4 | 67.1 |
| Reduced to 75% | 98.3 | 37.8 | 0.0 | 37.8 | 50.4 |
| XLF stock hedge | 131.0 | 50.4 | −67.4 | −17.0 | 0.0 |
| Collar | 131.0 | 50.4 | 0.0 | −5.4 | 67.1 |

- **Reduced equity** scales every position to 75%. The unused capital stays in cash at the same rate, which is why its interest is higher.
- **The ETF hedge** keeps the core book and adds a short XLF sleeve sized to the past-only beta. It is therefore a different exposure, not a cheaper version of the same one.
- **Beta-adjusted net** differs from net because issuers' past betas to XLF are not one. It ignores option positions.
- All option policies hold the same core shares as the unhedged book.

### Pricing sensitivity

ES loss reduction against unhedged, in points. Budgets stay fixed, so dearer options buy less coverage. Selected policies were not reselected. The 21-session column uses shorter windows and a different ES scale, so compare it only within its own column.

| Test policy | Base | Vol ×1.25 | Vol ×1.50 | Reactive vol | 0% rate | 21-session windows |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Long-name puts | 0.58 | 0.16 | −0.04 | 0.44 | 0.46 | 0.69 |
| Short-name calls | −0.24 | −0.24 | −0.24 | −0.24 | −0.23 | −0.09 |
| XLF puts | 0.22 | −0.02 | −0.15 | 0.01 | 0.12 | 0.25 |
| Collar | 3.37 | 3.46 | 3.56 | 3.56 | 2.39 | 0.86 |
| Risk-informed puts | 0.29 | 0.08 | −0.02 | 0.22 | 0.23 | 0.35 |
| XLF stock hedge | 1.05 | 1.05 | 1.05 | 1.05 | 0.34 | 1.27 |

The collar improves as volatility rises only because the flat-volatility model values its written call more. Real skew works the other way, making puts dearer and calls cheaper, so this should not be read as robustness. The ETF hedge's drop at a 0% rate shows how much it relied on interest from short proceeds.

## Sector basis

An XLF put pays on sector moves. It does not pay for an issuer-specific loss, and it does not protect shorts against a rally. It was sized to the book's net beta dollars.

| Window | Book | Long side | Short side | XLF put P&L | Name put P&L |
| --- | ---: | ---: | ---: | ---: | ---: |
| 2025-01-07 to 2025-04-09 | −10.05 | −12.10 | 1.68 | −0.53 | 1.54 |
| 2022-04-04 to 2022-07-06 | −7.93 | −14.57 | 6.26 | 3.30 | 1.64 |
| 2023-01-04 to 2023-04-05 | −7.78 | −13.99 | 5.85 | 0.05 | 1.02 |
| 2022-01-03 to 2022-04-04 | −5.27 | −10.65 | 5.03 | −0.40 | 0.11 |

The XLF put barely paid in early 2023 although the long book lost 14%, because the sector index fell less than those issuers. It also lost money in the worst test window.

## Study design

**Book.** $100 million of capital, 130% gross and 50% net. All ten panel issuers are held, so no issuer was chosen or dropped. JPM, BAC, WFC, C, PNC and USB are long at 15% each, and GS, MS, SCHW and BK are short at 10% each. Side follows business line: deposit-funded banks are long, and capital-markets, brokerage and custody franchises are short. This is a mandate for studying overlays, not an alpha view.

**Windows.** 63 sessions, non-overlapping, each a separate account opened with the same capital. A window that would pass its split's end is dropped.

| Split | Windows | First start | Last end | Unused sessions |
| --- | ---: | --- | --- | ---: |
| Training | 27 | 2011-01-04 | 2017-10-06 | 311 |
| Validation | 11 | 2018-01-02 | 2020-10-02 | 62 |
| Test | 23 | 2021-01-04 | 2026-10-12 | 17 |

Training's unused sessions include the 2010 estimation warmup. Results are never chained, so there is no NAV path, CAGR or full-period drawdown.

**Timing.** Shares, strikes, contract counts, betas and risk states come from closes through the decision date, one session before execution. Trades happen at the next close.

**Pricing and risk are kept separate.** Option prices use the 252-return trailing volatility with no skew. Risk estimates choose protection size and never price an option: an EWMA (λ = 0.94) over 252-session book-volatility ratio, and 252-return betas to XLF.

**Execution.** Stock costs 5 bps per side, a constant 4% rate for cash, borrowing and pricing, 100-share contracts rounded down, and `hedge_options=False`. Each window buys and liquidates the whole book.

**Selection.** Validation picked the lowest ES per family within a 2% budget, breaking ties by lower premium. The 4% budget is a frontier point only. The grid has 33 candidates.

| Family | Selected | Validation ES |
| --- | --- | ---: |
| XLF stock hedge | `etf_h100` | 5.38 |
| Long-name puts | `long_put_k90_b2` | 2.03 |
| Short-name calls | `short_call_k110_b1` | 12.62 |
| XLF puts | `sector_put_k95_b2` | 5.66 |
| Spread or collar | `collar_95_110_b2` | 1.37 |
| Risk-informed | `risk_k90_t125` | 6.79 |

The reduced-equity scale of 75% was fixed in advance and not selected. The short-call winner was the least harmful option, since every short-call candidate raised whole-book ES in validation.

## Protocol integrity

- Final run: [results/equity-overlays-20261106T023430248130Z](../results/equity-overlays-20261106T023430248130Z/report.md)
- Protocol SHA-256: `18948e86cef72c6b2bc183cc6e7d5ebba49cb9788806463864d57efdaf6079b6`
- Selection saw prices through 2020-12-31. The test split was evaluated once, with no frozen file changed, as recorded in `test_evaluation_log.json`.

Disclosures:

- The first and last rows of the price panels were displayed before the book was fixed, so 2010 and 2026 price levels were visible. That is why the book holds every panel name and uses a business-line rule.
- The author has general knowledge of market history after 2020. The test period is untouched by this protocol, but it is not unknown history.
- Two earlier freezes (`…020955456052Z` and `…021350045727Z`) were superseded before any test evaluation. Inspecting validation output prompted three reporting additions, and a hard-coded gate was replaced with a computed one. Selection, grid, config, inputs and development windows stayed identical, and those directories are kept for audit.
- Validation has 11 windows because a twelfth misses the split end by one session. The rule was left as frozen after validation output was seen.
- This document and notebook 07 were written after the test run. Their interpretation is post-hoc, but no policy, parameter or result changed.

## Gates

| Gate | Status | Evidence |
| --- | --- | --- |
| Fixed 6–10-name long/short book | Passed | 10 names, gross and net validated against issuer weights |
| Calendar and coverage alignment | Passed | 4,236 sessions match XNYS exactly, with no gaps |
| Protocol frozen and hashed before test | Passed | Selection stopped at 2020-12-31 |
| Test evaluated once with no later changes | Passed | One logged attempt, no changed files |
| Model-contract accounting | Passed | All window checks true, largest hand residual $1.5e-08 |
| All eight comparisons evaluated | Passed | Computed from the evaluated families |
| Statistical evidence of protection | Exploratory | 23 windows, six tail windows, four episodes |
| Continuous rolled portfolio NAV | Not available | `replay` opens all options at inception |
| Listed-option execution backtest | Blocked | No verified historical option quotes |
| Dividends, borrow, margin, option spreads, American exercise | Not modeled | Not supported by `replay` or the price inputs |
| Survivorship-safe generalization | Blocked | Historical membership access denied |

## Validation

- 71 tests in `tests/test_overlays.py` use hand-derived dollar expectations and an independent erf-based option formula. They cover signs, multipliers, common capital, unchanged core holdings, floors and caps, cash and NAV identities, calendar alignment, leakage and the protocol guards.
- 22 deliberate code faults were injected into a scratch copy, including leakage, wrong signs, overlapping windows and selection reading the wrong split. The tests caught all 22. This run predates the final reporting additions, which have their own tests.
- Every replay is rebuilt from raw trade and option records. Inception, the worst mark, expiry and the next-window capital reset are hand-reconciled for long downside and short upside protection, in both validation and test, across 60 line items.

Hand example from window test-005, a BAC put during the 2022 selloff: 366,748 shares long, 1,446 contracts covering 39.4%, strike 36.81 from the 40.90 decision close. The premium was $84,485. At the 30.98 expiry close the settlement was 144,600 × (36.81 − 30.98) = $843,018, against a stock loss of $3,612,468.

Short-side example from window test-017, a GS call during the 2025 rally: 21,634 shares short, 52 contracts covering 24%, strike 508.44. The premium was $202,174. At the 704.95 expiry close the settlement was $1,021,842, against a stock loss of $4,068,923.

## Limitations

- Options are priced at an assumed volatility with no skew or term structure. Market-priced protection may differ materially, particularly for out-of-the-money puts and after volatility spikes.
- There is no option bid/ask charge, which flatters purchased protection and the collar's two legs.
- Exercise is European with cash settlement, while listed single-name options are American and physically settled.
- Split-adjusted closes are not total returns. Dividends received on longs, owed on shorts and owed on the short ETF are excluded, and the option model has no dividend yield.
- There are no borrow fees, rebate spreads or margin requirements, and short proceeds earn the full constant rate.
- The 4% rate is constant and illustrative, including years when short rates were near zero.
- The issuers are current survivors, which favors the long book and works against the shorts. Failed and acquired banks are absent.
- Liquidating the whole book in each window overstates stock turnover against a rolled book.
- Holdings are not rebalanced inside a window, so exposure drifts.
- XLF's history is adjusted for its 2016 real-estate spin-off, so historical strike levels are model values only.

## Requests to upstream owners

**Replay owner (`hedging_harness/replay.py`)**

1. **Continuous rolls:** let `OptionPosition` take an `entry_date`, or let `replay` accept opening holdings, cash and a list of dated option openings. This is what a funded portfolio NAV needs.
2. **Option execution cost:** add `option_cost_bps` or a per-position half-spread, reported in its own ledger column.
3. **Overlay stock sleeve:** add `overlay_holdings` beside `equity_holdings`. XLF currently passes through `equity_holdings`, and overlays separates it by name.
4. **Separate financing rates:** add a short-rebate or borrow-fee rate and a restriction on using short proceeds.
5. **Dividends:** add per-underlying cash dividends and a dividend yield in option pricing.

**Risk owner (`hedging_harness/risk_models.py`)**

6. **Dated point estimates:** add `latest_risk_state(prices, as_of, protocol)`. `variance_forecasts` drops origins with no realized target, so it cannot serve a live decision date, and `overlays.estimate_state` repeats the same EWMA recursion.
7. **Exposed loadings:** return betas from `covariance_estimates`.
8. **General block bootstrap:** add a `statistic=` argument to `moving_block_mean_interval`, so ES differences do not need a separate resampler.

**Market-data owner**

9. **Data for later stages:** verified historical option quotes, dividend cash flows and point-in-time membership. These unblock the listed-option and survivorship gates.

## Reproduce

```sh
.venv/bin/python -m unittest tests.test_overlays
.venv/bin/python scripts/run_overlay_research.py freeze
.venv/bin/python scripts/run_overlay_research.py evaluate --run-dir results/equity-overlays-<stamp>
```

`freeze` writes a new directory. `evaluate` refuses a second run on the same directory, or any run after a frozen file changes, unless `--revision-note` is supplied. Such a run goes to a `revision-N` folder and is marked as test-informed. Nothing here reads credentials or downloads data.

The executed notebook is [07_equity_overlay_study.ipynb](../Hedging_Study_Notebooks/07_equity_overlay_study.ipynb). It reads the frozen run, verifies its hashes and reproduces two windows. It does not evaluate the test split again.

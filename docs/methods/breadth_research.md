# Conditional breadth and composition research

The stage-7 prototype is complete as a **conditional computational and historical price-risk diagnostic**. It does **not** pass the full stage-7 generalization gate. The cohort is selected using a 2026 current-survivor snapshot and availability through 2026, not historical point-in-time membership.

The final reproducible run is [breadth-20261106T020730752645Z](../../results/breadth-20261106T020730752645Z/report.md). Its [protocol](../../results/breadth-20261106T020730752645Z/protocol.json), [manifest](../../results/breadth-20261106T020730752645Z/manifest.json), all-name availability audit, portfolio outcome archives, model risk comparisons, group-tail contributions and actual static-equity diagnostics are retained. [Notebook 08](../../notebooks/08_breadth_and_composition.ipynb) is an executed report on that frozen run.

## Universe and exclusions

The FMP panel retains all 50 requested issuer IDs and all unavailable observations. Forty-two names have complete 2010–2026 histories. The following eight partial histories are explicitly excluded from this particular balanced master: **KKR, BAM, APO, HOOD, PYPL, ARES, RKT and COIN**. There is no forward-fill, silent removal from the source panel, or replacement of missing distressed histories.

The canonical master order preserves the original JPM/PNC/GS trio and the ten-name core JPM, PNC, GS, BAC, WFC, C, USB, MS, SCHW, BK. BK uses the data audit's documented BK/BNY stable-issuer mapping. Current industry labels are descriptive FMP classifications, not verified historical GICS.

Filtering for complete history through 2026 uses future availability relative to the 2020 calibration cutoff. The 2021–2026 diagnostic therefore does not become an untouched-universe historical out-of-sample test. A current-survivor history cannot establish which failures, acquisitions, delistings and changing memberships should have been present at older dates.

## Frozen simulation design

The numerical calibration uses only 252 daily log returns ending at or before **2020-12-31**, requiring 253 prior observations. The covariance is the past sample covariance with a fixed **20% shrinkage toward its diagonal**. Annualized marginal volatilities are past realized-volatility proxies. They are not historical implied volatilities or market-calibrated option quotes.

The controlled option study uses normalized stock and strike values of 100, 63 sessions to expiry, a constant 4% financing rate, zero dividends and 5 bp one-way stock costs. Each book has **$300,000 total initial underlying notional**, divided equally across its names. Equal notional does not equal equal premium, gamma or vega; the `book_details.csv` file reports those differences.

A single **42-asset master price cube** is generated for each dependence scenario. Every smaller book takes named columns from that exact cube. It never regenerates a smaller-dimensional simulation with the same integer seed. At 5,000 paths and 64 observed dates, each master cube occupies 107.52 MB before other working arrays.

The scenarios are:

1. Past-calibrated shrinkage dependence.
2. A prespecified synthetic common-shock stress: `0.6 * base correlation + 0.4 * all-ones correlation`.

The mixture stays positive semidefinite and keeps each marginal volatility fixed. It is a stress assumption, not an estimated crisis probability or a jump/stochastic-volatility model. The Q drift equals the model financing rate. Historical covariance provides a dependence proxy without identifying the market's risk-neutral joint distribution.

Three composition chains are fixed before calculation: the canonical order and permutations seeded **730711** and **730712**. Each chain is nested **3 → 10 → 25 → 40**. The seeded chains deliberately change composition, while the canonical three/ten preserve continuity with earlier notebooks.

## Locked policy and uncertainty

The policy is imported unchanged from `results/research-release-1/release-1/selection.json`: **maturity_band_050**, a normalized delta discrepancy threshold of `0.05 * sqrt(remaining maturity / initial maturity)`. It is compared with daily and five-session rebalancing without reselection or tuning on the breadth outputs.

The run contains 72 policy cases: two scenarios × three composition chains × four breadths × three rules. The original $500 expected financed-cost budget is checked with the mean-cost interval's upper endpoint rather than assumed to transfer.

For each book, portfolio ES95 is computed from the worst 250 of 5,000 portfolio outcomes. Five hundred paired bootstrap resamples estimate **ES(locked) minus ES(reference)**, not ES of the P&L difference. The paired policies share exactly the same subset path fingerprint. Negative differences favor the locked rule under that statistic.

These are pointwise Monte Carlo intervals conditional on the fixed model and policy. They exclude calibration/model uncertainty and do not establish simultaneous dominance across 48 comparisons. Composition variants share the same master innovations and are not independent simulated market histories.

## Findings from the frozen conditional run

At canonical breadth 40 under calibrated dependence:

| Policy | Portfolio ES95 | Mean financed stock cost |
|---|---:|---:|
| Locked maturity band | $4,640.84 | $487.95 |
| Daily | $4,713.83 | $545.59 |
| Five-session | $9,913.98 | $337.56 |

The locked-minus-daily ES difference is −$72.99, with a pointwise paired interval of approximately **[−$118.52, −$23.25]**. This is a conditional synthetic result, not a market trading-performance claim.

Breadth is not monotonically protective: canonical 25-name locked-policy ES is **$4,521.13**, below the 40-name value. Company mix, volatility and dependence matter alongside ticker count.

## Actual static-equity diagnostic

The additional diagnostic uses **73 non-overlapping 20-session intervals** from 2021 through 2026-11-04. Each interval starts at its preceding close and holds equal initial dollar stock amounts. It uses the same $300,000 notional for every breadth and composition. It does not contain derivative overlays, execution costs, financing or dividend cash flows.

There are only **four empirical tail intervals** in each historical ES95 calculation, not 40 × 73 independent episodes. Four-period circular block resampling supplies approximate mean and ES intervals while keeping chronological dependence and contemporaneous names together. More stocks during the same crisis are not more independent crises.

Canonical ten-name price-only ES is about $43,545 versus $38,366 for three names, while the 25/40-name values are approximately $32,446/$32,525. These are diagnostics of a 2026 survivor/availability-selected cohort. They neither certify unbiased historical generalization nor imply an option-overlay result. Tail group contributions use the same worst portfolio intervals and add exactly to portfolio ES; classifications are contemporary labels.

## Reproduce and test

```sh
.venv/bin/python src/commands/run_breadth_research.py
.venv/bin/python -m unittest discover -s tests -p test_breadth.py -v
```

The runner writes a new `results/breadth-*` directory and records its complete protocol before evaluating the policies. It reads cached data, not credentials, and does not make downloads. Nine focused tests cover exact master-path label alignment, constant notional, explicit partial availability, nested seeded compositions, no-future calibration, positive-semidefinite dependence stresses, non-overlapping historical targets and block-tail calculations.

## Gate boundary

`conditional_breadth_computation_passed = true` establishes this bounded implementation and audit. **`full_stage7_gate_passed = false` remains deliberate.** Historical membership and classifications, inclusion of failed/acquired names, plausible derivative execution, market option evidence, and untouched overlay-policy generalization remain absent from this diagnostic. FMP documents that options data are unsupported, so current underlying-price coverage must not be presented as historical listed-option coverage.

# Market-informed price-risk research

The implemented runner evaluates price-history forecasts and covariance models on actual FMP split-adjusted stock observations. The principal artifact is the ten-name run:

- [Core-ten report](../../results/risk-research-20261106T014747676804Z/report.md)
- [Frozen protocol and data identities](../../results/risk-research-20261106T014747676804Z/protocol.json)
- [Per-company scores](../../results/risk-research-20261106T014747676804Z/scores_by_asset.csv)
- [Pooled and portfolio scores](../../results/risk-research-20261106T014747676804Z/pooled_scores.csv)
- [Dependence-aware loss-difference intervals](../../results/risk-research-20261106T014747676804Z/paired_loss_differences.csv)
- [Manifest and gate limitations](../../results/risk-research-20261106T014747676804Z/manifest.json)

A three-name continuity run is retained at `results/risk-research-20261106T014645390937Z`. It uses the same frozen numerical protocol and does not tune parameters for the ten-name expansion.

## Reproduce

```sh
.venv/bin/python src/commands/run_risk_research.py --prices data/market/prices_core_10.csv
.venv/bin/python -m unittest discover -s tests -p test_risk_models.py -v
```

The first command writes a new timestamped `results/risk-research-*` directory. `--factors` defaults to `data/market/prices_benchmarks.csv`; `--output-dir` can select a new destination. Neither runner nor import reads credentials or performs a download.

## Inputs and protocol

The core-ten sample contains JPM, PNC, GS, BAC, WFC, C, USB, MS, SCHW and BK, aligned to 4,236 observed XNYS sessions from 2010-01-04 through 2026-11-04. SPY and XLF provide observed market/financial-sector factor returns on the same dates. BK is the stable study identifier for the issuer whose exchange ticker changed to BNY in 2026; the data audit contains explicit source-symbol lineage and overlap checks.

These are current/available names selected before the forecast outcomes were inspected. This does not establish historical universe eligibility or eliminate survivor selection. Split-adjusted prices exclude dividend cash flows. The vendor's currently available history is not an archive of every historical data revision.

The frozen chronological split is training 2010–2017, validation 2018–2020, and untouched test 2021–2026-11-04. Parameters are fixed defaults, not chosen using validation or test scores. The runner persists and hashes the complete protocol and data identities before calculating forecast losses.

Targets are cumulative squared log returns over the next five or twenty sessions. An origin close's return is an available feature, but is excluded from its future target. Forecasts use only the history up to that origin.

Company forecasts are a 252-session mean squared return reference, a 20-session recent-variance forecast, and EWMA variance with lambda 0.94 and a 252-session warmup. The horizon forecast scales the conditional daily variance by five or twenty; no future return is inserted into the predictors.

Portfolio risk uses an equal-weight linear return basket, not traded NAV. The daily covariance models are past-252-session sample covariance, fixed 20% diagonal shrinkage, an internal equal-weight financial factor, and observed SPY/XLF factor loadings with diagonal residual covariance. Loadings, factor covariance and residual variances all use the past window only. Physical return-risk forecasts are separate from Q-measure option pricing and do not automatically constitute pricing volatilities.

## Uncertainty and actual findings

Evaluation targets do not overlap within a split/horizon. Forecast-loss differences are first averaged across names at each origin, keeping contemporaneous companies together. A circular moving-block bootstrap then resamples chronological origin blocks: thirteen five-session origins or four twenty-session origins, approximately a quarter of trading observations. This addresses remaining temporal dependence and avoids representing ten correlated companies during one episode as ten independent episodes.

QLIKE is `log(forecast) + realized/forecast`, omitting a target-only constant. Its raw level may be negative; lower differences are better. MSE is squared variance-forecast error. Intervals are pointwise and do not support a simultaneous-superiority claim across every model/horizon.

On the untouched ten-name test sample:

- There are 293 non-overlapping five-session origins and 73 twenty-session origins, not 2,930/730 independent market episodes.
- EWMA's pooled company-level MSE improves by 13.75% at five sessions and 14.52% at twenty versus the 252-session reference.
- The corresponding QLIKE differences are −0.0061 and +0.0235, and both block-bootstrap intervals include zero. The data do not establish consistent superiority under QLIKE.
- Portfolio diagonal shrinkage improves point MSE by 11.43%/20.84%; its QLIKE differences also have intervals including zero. The SPY/XLF factor model likewise has no clear QLIKE improvement in this test.

These are descriptive outcomes under a fixed protocol, including inconclusive or adverse comparisons. A larger ticker count or a favorable point estimate is not reported as proof of predictive or hedge value.

## Gates and remaining work

The dated price-history forecast and stable covariance implementation is complete and independently tested for the ten-name sample. Nine tests cover future-price/factor perturbation invariance, PSD, exact next-horizon target alignment, temporal split boundaries, disjoint targets, known scoring values, and bootstrap reproducibility.

Stage 5's incremental macro, option-implied, company-funding and interaction layers remain untested. Financial-statement publication/acceptance dates, macro vintages and parent/subsidiary mappings must be verified before those features can enter tests. Translating a forecast improvement into option-overlay value is another experiment, not an implication of the forecast score.

The delivered 50-name panel is unbalanced: 42 names have full histories and eight have shorter histories. This runner rejects missing prices rather than silently remove rows or names. Any 25/40/50-name extension must explicitly record its history-coverage screen, start date, current-universe conditioning and membership limitations. Historical membership access remains denied, so survivorship-safe stage-7 generalization is not established.

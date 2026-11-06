# Price-history risk research — chronological physical-risk forecasts



Universe: JPM, PNC, GS, BAC, WFC, C, USB, MS, SCHW, BK. External factors: SPY, XLF. Input sessions: 4,236, 2010-01-04 through 2026-11-04.

This is a conditional current-name price-risk study, not a survivorship-free universe backtest or a listed-option trading strategy.

Where BK appears, it is a stable study identifier for the issuer whose exchange ticker changed to BNY in 2026. The data audit records the explicit source-symbol mapping and overlap checks; the risk model does not silently fill missing prices.

## Frozen protocol

Training: 2010–2017. Validation: 2018–2020. Untouched test: 2021–2026-11-04. Parameters are fixed before scores are computed; neither validation nor test outcomes tune the windows, EWMA decay, shrinkage or factors. The protocol file is persisted and hashed before evaluation.

Targets are cumulative next-5/20-session squared log returns. All features use information through the origin close only. Evaluation target intervals are disjoint within each split/horizon; cross-asset dependence is preserved by averaging loss differences at each origin before resampling chronological blocks. Circular moving-block lengths approximate one quarter: 13 forecast origins for 5-session targets and 4 for 20-session targets. Intervals are pointwise and do not establish simultaneous superiority.

Price-return histories are split-adjusted and exclude dividend cash flows. They are vendor histories available now, not an archive of every historical data revision. Market and sector factors are observed SPY/XLF price returns from the same past window.

## Models

Company forecasts: rv_long = mean squared returns over 252 sessions; rv_recent =20 sessions; ewma uses lambda 0.94 with 252-session warmup. Each daily variance is multiplied by the horizon, a fixed persistence approximation rather than a fitted term structure.

Portfolio baseline: sample covariance of the past 252 sessions. Alternatives: fixed 20% diagonal shrinkage; an internal equal-weight financial-return factor; and past-only SPY/XLF factor loadings with diagonal residual covariance. Factor loadings and covariance estimates are refreshed using only the window available at each origin. They do not fit on future factor returns.

The portfolio target is squared return risk for a fixed equal-weight linear return basket, not a traded self-financing NAV. Q option valuation and protective-overlay outcomes are separate later tests. Sample covariance is positive semidefinite; diagonal floors stabilize shrinkage and factor estimates.

QLIKE is log(forecast) + realized/forecast, omitting a target-only constant. Lower is better; raw scores may be negative. MSE is squared variance-prediction error. MSE skill above zero improves over the reference; QLIKE differences below zero improve over the reference.

## Untouched test results

| panel | horizon | model | n_dates | mean_qlike | mean_mse | mse_skill_vs_baseline | qlike_difference_vs_baseline |
| --- | --- | --- | --- | --- | --- | --- | --- |
| portfolio | 5 | diagonal_shrinkage | 293 | -5.75077 | 2.36143e-06 | 0.114257 | 0.00761249 |
| portfolio | 5 | external_factor | 293 | -5.75391 | 2.64004e-06 | 0.00975284 | 0.00447495 |
| portfolio | 5 | internal_factor | 293 | -5.75829 | 2.70344e-06 | -0.0140258 | 9.5169e-05 |
| portfolio | 5 | sample_covariance | 293 | -5.75838 | 2.66604e-06 | 0 | 0 |
| portfolio | 20 | diagonal_shrinkage | 73 | -4.35017 | 2.19642e-05 | 0.208366 | 0.00824007 |
| portfolio | 20 | external_factor | 73 | -4.35439 | 2.72713e-05 | 0.0170868 | 0.00401567 |
| portfolio | 20 | internal_factor | 73 | -4.35856 | 2.84197e-05 | -0.0243024 | -0.000155891 |
| portfolio | 20 | sample_covariance | 73 | -4.35841 | 2.77454e-05 | 0 | 0 |
| single_names | 5 | ewma | 293 | -5.44718 | 4.6778e-06 | 0.137485 | -0.00605881 |
| single_names | 5 | rv_long | 293 | -5.44112 | 5.42344e-06 | 0 | 0 |
| single_names | 5 | rv_recent | 293 | -5.36265 | 5.30041e-06 | 0.0226851 | 0.0784748 |
| single_names | 20 | ewma | 73 | -4.01922 | 4.03386e-05 | 0.14515 | 0.0234514 |
| single_names | 20 | rv_long | 73 | -4.04267 | 4.71879e-05 | 0 | 0 |
| single_names | 20 | rv_recent | 73 | -3.89708 | 5.35074e-05 | -0.133923 | 0.145591 |

![Test MSE skill](test_mse_skill.png)

## Dependence-aware uncertainty

| panel | horizon | model | baseline | estimate | lower | upper | n_dates | block_length |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| portfolio | 5 | diagonal_shrinkage | sample_covariance | 0.00761249 | -0.0354521 | 0.0596136 | 293 | 13 |
| portfolio | 5 | external_factor | sample_covariance | 0.00447495 | -0.0137898 | 0.0265181 | 293 | 13 |
| portfolio | 5 | internal_factor | sample_covariance | 9.5169e-05 | -0.0102252 | 0.00822364 | 293 | 13 |
| portfolio | 20 | diagonal_shrinkage | sample_covariance | 0.00824007 | -0.0402648 | 0.067481 | 73 | 4 |
| portfolio | 20 | external_factor | sample_covariance | 0.00401567 | -0.0142059 | 0.0292499 | 73 | 4 |
| portfolio | 20 | internal_factor | sample_covariance | -0.000155891 | -0.0126256 | 0.00848934 | 73 | 4 |
| single_names | 5 | ewma | rv_long | -0.00605881 | -0.0674028 | 0.0501811 | 293 | 13 |
| single_names | 5 | rv_recent | rv_long | 0.0784748 | -0.0104806 | 0.178592 | 293 | 13 |
| single_names | 20 | ewma | rv_long | 0.0234514 | -0.0725279 | 0.145585 | 73 | 4 |
| single_names | 20 | rv_recent | rv_long | 0.145591 | -0.0219144 | 0.378847 | 73 | 4 |

![Test QLIKE intervals](test_qlike_intervals.png)

The complete CSVs include per-company, pooled and portfolio scores for train, validation and test. Findings are reported as observed, including deterioration or inconclusive intervals; no model is selected post hoc from test outcomes.

## Stage and research gates

Past-only forecasting/covariance implementation and evaluation are complete for the available 10-name sample. This supports the price-history baseline component of stages 4–5. Historical universe membership, liquidity eligibility and survivorship coverage remain unverified, so a wider current-name sample does not by itself complete the generalization gate.

Stage 5 incremental macro, option-implied and company-funding features have not been tested. Release/acceptance timestamps, vintage-aware macro observations and issuer/subsidiary mappings remain outstanding. Forecast improvement has not yet been translated into option-hedging value. Stage 6 equity overlays and the stage 7 untouched-period/composition/realistic-execution gate are not passed by this artifact.

## Checks and provenance

Feature-origin availability and target alignment passed. Minimum observed covariance eigenvalue: 1.0166835e-05. The accompanying tests include future-price perturbation invariance, external-factor availability, PSD, strict next-horizon targets, split boundaries and non-overlap.

protocol.json records input hashes and parameters. manifest.json records source/data/output identities. No credentials are read or stored by this runner.

# Model-contract replay: normal and stress windows

These are synthetic European contracts priced with a fixed prior-realized-volatility proxy on FMP split-adjusted historical stock closes; synthetic model option contracts. They are not historical option quotes or executable listed-option backtests. Historical stock observations are not risk-neutral simulations.

## Calibration

| window | name | cutoff | first_observation | replay_start | price_observations | return_observations | annual_volatility |
| --- | --- | --- | --- | --- | --- | --- | --- |
| normal_2019 | JPM | 2018-12-31 | 2017-12-28 | 2019-01-02 | 253 | 252 | 0.2206 |
| normal_2019 | PNC | 2018-12-31 | 2017-12-28 | 2019-01-02 | 253 | 252 | 0.2320 |
| normal_2019 | GS | 2018-12-31 | 2017-12-28 | 2019-01-02 | 253 | 252 | 0.2579 |
| stress_covid_2020 | JPM | 2020-01-31 | 2019-01-31 | 2020-02-03 | 253 | 252 | 0.1898 |
| stress_covid_2020 | PNC | 2020-01-31 | 2019-01-31 | 2020-02-03 | 253 | 252 | 0.1995 |
| stress_covid_2020 | GS | 2020-01-31 | 2019-01-31 | 2020-02-03 | 253 | 252 | 0.2162 |

## Account outcomes

| window | strategy | observations | initial_capital | terminal_nav | terminal_model_pnl | max_drawdown_dollars | opening_option_cashflow | option_settlement_cashflow | stock_cost | stock_turnover | total_interest | peak_borrowing |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| normal_2019 | short_calls_stock_hedged | 61 | 0.0000 | 380.1648 | 380.1648 | 1,903.2696 | 15,225.5568 | -16,776.4355 | 326.8263 | 653,652.6049 | -2,120.1208 | 289,835.2497 |
| normal_2019 | unhedged_equity | 61 | 300,000.0000 | 316,466.6119 | 16,466.6119 | 27,121.7097 | 0.0000 | 0.0000 | 308.3882 | 616,776.4355 | -1.4354 | 151.4354 |
| normal_2019 | protective_puts | 61 | 300,000.0000 | 303,966.1487 | 3,966.1487 | 24,931.3372 | -12,381.9763 | 0.0000 | 308.3882 | 616,776.4355 | -119.9223 | 12,651.8986 |
| stress_covid_2020 | short_calls_stock_hedged | 62 | 0.0000 | -6,429.1598 | -6,429.1598 | 7,548.9063 | 13,325.2967 | 0.0000 | 183.4166 | 366,833.1562 | -493.1459 | 177,076.6166 |
| stress_covid_2020 | unhedged_equity | 62 | 300,000.0000 | 219,612.5025 | -80,387.4975 | 138,568.2232 | 0.0000 | 0.0000 | 259.9369 | 519,873.8989 | -1.4594 | 151.4594 |
| stress_covid_2020 | protective_puts | 62 | 300,000.0000 | 289,202.5277 | -10,797.4723 | 17,145.8065 | -10,434.5522 | 80,126.1011 | 259.9369 | 519,873.8989 | -102.9831 | 10,687.5354 |

Core-equity comparisons share $300,000.00 initial capital. The short-call liability account starts at zero capital and is a different mandate; its P&L must not be interpreted as an equity investment return. Protective puts retain their negative delta; they are not automatically delta-hedged.

## Independent accounting checks

| window | strategy | cash_from_trade_and_option_records | expiry_payoff_recomputed | terminal_shares_and_liabilities_zero | no_future_info_decisions | calibration_strictly_before_replay |
| --- | --- | --- | --- | --- | --- | --- |
| normal_2019 | short_calls_stock_hedged | True | True | True | True | True |
| normal_2019 | unhedged_equity | True | True | True | True | True |
| normal_2019 | protective_puts | True | True | True | True | True |
| stress_covid_2020 | short_calls_stock_hedged | True | True | True | True | True |
| stress_covid_2020 | unhedged_equity | True | True | True | True | True |
| stress_covid_2020 | protective_puts | True | True | True | True | True |

Inception, first scheduled rebalance and expiry cash rows are in `manual_reconciliation.csv`. Each reconstructs previous cash + interest + signed option flows + core/hedge stock cash flows minus stock cost. Full instrument opening/settlement records are in `representative_option_events.csv`; all daily account, holding and trade records are retained.

## Gate boundary

The small model-contract accounting replay passes its automated reconciliation and causality checks. A historical listed-option replay remains pending actual timestamped option quotes, implied volatilities and lifecycle/execution data. Two windows and three surviving names do not establish sector-wide out-of-sample effectiveness.

# Dated European model-contract replay

`hedging_harness.replay` separates option positions, core equity and stock hedges while retaining an auditable daily cash account. It supports signed calls/puts, contract multipliers, several options on one underlying, and different explicit expiry sessions.

The market-data input is an underlying-price DataFrame. It does **not** supply historical option premiums or bid/ask quotes. The replay opens synthetic European cash-settled options at fixed-volatility Black–Scholes prices. It must be described as **model contracts on historical stock observations**, never as an executable historical listed-option backtest.

## Public API

```python
from hedging_harness.replay import OptionPosition, replay

position = OptionPosition(
    instrument_id="JPM_model_put", underlying="JPM", kind="put",
    strike=100.0, expiry="2024-03-28", quantity=1.0,
    multiplier=100.0, volatility=0.25,
)
result = replay(
    prices, [position], equity_holdings={"JPM": 100.0},
    hedge_options=False, hedge_every=5, cost_bps=5.0, rate=0.04,
    initial_capital=10000.0,
)
```

Dates and prices in this snippet illustrate the interface; this is not a claim that the example contract traded. The expiry must be an actual row of the supplied price table, strictly after the first row.

`OptionPosition.quantity` is signed: positive for purchased options, negative for written options. Its `units` property is `quantity * multiplier`. Values, premiums, payoffs and Greeks scale by that signed quantity. `multiplier=1` represents share-equivalent model units; exchange-style multipliers are explicit inputs.

`hedge_options=False` leaves the option overlay's delta in the portfolio. This preserves the purpose of purchased puts against long equities. `hedge_options=True` adds an option-delta-offsetting stock hedge separately from core equity. It does not automatically neutralize the core equity mandate.

## Sessions, cutoffs and missing data

- Prices must have a unique, increasing, timezone-naive daily `DatetimeIndex` and unique underlying identifiers as columns. Missing, nonfinite and nonpositive prices are rejected.
- Rows declare the session calendar. One row-to-row interval is `1 / sessions_per_year`; weekends and holidays are not treated as additional sessions.
- Every option expiry must be a supplied session strictly after inception. All modeled options therefore settle within the replay interval.
- `session_calendar=` can supply a full externally verified calendar, in which case the price index must match exactly. The function does not independently know which exchange sessions are missing when no verified calendar is supplied.
- `as_of=` must equal the first observation. Volatility inputs are fixed and must be estimated using data available at entry. The function cannot infer whether a caller's volatility was derived from future data; the study runner records and checks its calibration cutoff explicitly.
- Decisions use the current observation and remaining session count only. Future-price perturbation tests verify that earlier decisions/account rows do not change.

## Initial capital and P&L

Initial capital is external cash contributed once, before opening trades. If unspecified, it defaults to the inception value of **gross long core-equity holdings**. For strategy comparisons, supply the same explicit capital to every strategy, especially when comparing full equity exposure, reduced equity exposure and option overlays.

At inception:

1. Purchase or short the fixed core equity holdings.
2. Buy or write the model options at their model prices: the cash flow is minus the signed option value.
3. If enabled, establish the option-delta stock hedge.
4. Execute the net underlying trades and charge proportional stock costs.

A purchased option consumes cash but adds equal signed option value to NAV. A written option produces cash and a matching negative option value. Before entry costs, NAV therefore equals contributed capital. Negative cash is borrowing at the same rate paid on positive cash.

Daily NAV is:

\[
\mathrm{NAV}=\mathrm{cash}+\mathrm{core\ equity\ value}+\mathrm{hedge\ stock\ value}+\mathrm{signed\ option\ value}.
\]

Cumulative P&L is NAV minus initial capital. The first daily P&L includes entry costs; the daily P&Ls sum to final cumulative P&L. A zero-capital short-option liability account has meaningful dollar P&L but does not have an ordinary equity investment return denominator.

Core and hedge holdings are attributed separately but executed **net by underlying**. If one sleeve buys shares while another sells them at the same observation, stock costs apply to the net executed quantity, not two offsetting external trades. This reflects the current single-account, linear-funding convention.

## Daily event order

Accrue interest on the previous cash balance → observe current stock prices → cash-settle expiring contracts → choose permitted hedge adjustments → net/execute stock trades and charge costs → mark remaining positions → report NAV.

Expiry forces the affected underlying's option hedge to reset even between scheduled rebalances. Several options may expire on different dates; the hedge target then reflects only the remaining active options. The final observation liquidates core and hedge stock by default. `liquidate_at_end=False` retains core equity and reports its marked NAV instead.

The model processes European cash settlement only. It does not simulate physical assignment, American early exercise, margin, option bid/ask spreads, dividends, corporate-action event processing, stock borrow fees or asymmetric financing. Peak borrowing is checked after interest and after each observation's combined flows, not during an intraday execution sequence.

## Auditable outputs

`ReplayResult` provides:

- `ledger`: daily interest, option cash flows, core/hedge stock cash flows, stock costs, turnover, cash, signed option value, stock values, NAV, daily/cumulative P&L and borrowing.
- `holdings`: date/underlying rows with separate core shares, hedge shares, net shares and option/portfolio deltas.
- `trades`: date/underlying execution records with core/hedge attribution and net executed shares.
- `option_ledger`: date/instrument records with remaining sessions, event, signed value/delta, opening cash and expiry settlement.
- `provenance`: actual inputs, calendar/quantity/capital conventions, source hashes and a hash of the consumed observations.

The properties `terminal_nav`, `terminal_pnl`, `peak_borrowing` and `total_stock_cost` provide compact results.

## Actual three-name replay study

Run:

```sh
.venv/bin/python scripts/run_model_contract_replay.py
```

The runner consumes `data/market/prices_split_adjusted.csv`, the audited FMP split-adjusted closes for JPM, PNC and GS. It uses two predefined windows:

- Normal illustration: 2019-01-02 through 2019-03-29.
- COVID stress illustration: 2020-02-03 through 2020-04-30.

For each window, the fixed model volatility is the sample standard deviation of **252 prior log returns**, using 253 closing observations strictly before the replay's first date, annualized by `sqrt(252)`. It is a realized-volatility proxy for model sigma, not an observed historical implied volatility. The financing rate is an illustrative constant 4%, not a historical rate series.

The predefined cases are short model calls with a five-session stock hedge, an unhedged long-equity book, and the same long equities with purchased model puts and no option-delta neutralization. The two equity cases have identical shares and initial capital. Options strike at the inception stock price and cash-settle at the window's last session. No policy is optimized on these two outcomes.

Every run exports the full ledgers, holdings, trades, instrument events, prior-data calibration table, summary, a plot, representative inception/rebalance/expiry cash reconciliation rows, and a source/data-hashed run record. Independent aggregation from trade and instrument records verifies daily cash, expiry payoffs are recomputed from raw observed terminal prices, and future-price perturbations verify causality.

The resulting gate is a **model-contract accounting replay**. Historical option quote coverage, dividend and lifecycle modeling, executable execution assumptions, survivorship-safe universes and broader out-of-sample evidence remain separate research gates. Historical stock observations are not Q-simulated paths, and two windows do not establish sector-wide forecasting or protection effectiveness.

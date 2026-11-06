# Stage 6 equity overlays — payload for Astra / Opus coordinator

## Mandate

Implement and validate Stage 6 of the financial-sector portfolio hedging study. Human review occurs after the automated implementation/research pass. Produce a complete, auditable first-pass overlay study; do not stop at a plan. Do not claim listed-option execution or survivorship-safe historical generalization where evidence is missing.

Working directory: `/Users/saireddivari/MonteCarloEvaluations`.

## Ownership and boundaries

Codex/root and its current workers own:

- `hedging_harness/core.py`, `policies.py`, `uncertainty.py`, `research.py`: controlled Research Release 1, policy selection, separate simulation evaluation, cost/tail/funding uncertainty.
- `market_data/`, all `data/market/` fetching and normalization, `scripts/audit_market_data.py`: FMP entitlement, pricing/corporate-action conventions, calendar/coverage and financial-universe audit.
- `hedging_harness/replay.py`, `scripts/run_model_contract_replay.py`, `tests/test_replay.py`, notebook `05_model_contract_replay.ipynb`: generalized European model-option replay and accounting.
- `hedging_harness/risk_models.py`, `scripts/run_risk_research.py`, `tests/test_risk_models.py`: dated past-only risk models, price-history forecast baselines, chronological/non-overlapping evaluation and covariance research.
- Existing notebooks `00`–`04`, shared config/research-gate integration and final integration.

Opus owns ONLY these new files unless Astra coordinates an explicit handoff:

- `hedging_harness/overlays.py`
- `tests/test_overlays.py`
- `scripts/run_overlay_research.py`
- `config/equity_overlay_study.json`
- `Hedging_Study_Notebooks/07_equity_overlay_study.ipynb`
- `docs/equity_overlay_research.md`
- `results/equity-overlays-*/` artifacts

Do not modify shared modules while their owner is active. If an interface needs extending, report the exact request and isolate the change; do not copy a second ledger implementation. No other process should fetch FMP data concurrently: request additional symbols/data through the market-data owner.

## Available data and evidence

Verified: FMP split-adjusted historical stock prices, three names JPM/PNC/GS, 4,236 aligned XNYS sessions from 2010-01-04 through 2026-11-04, no missing/unexpected exchange sessions. Source and hashes are in `data/market/prices_metadata.json`; primary panel `data/market/prices_split_adjusted.csv` has `date,JPM,PNC,GS`.

The data owner is preparing:

- `data/market/prices_core_10.csv`: JPM,PNC,GS,BAC,WFC,C,USB,MS,SCHW,BK.
- `data/market/prices_benchmarks.csv`: SPY and XLF.
- Corresponding actual coverage, calendar and adjustment metadata.

Wait for or detect those files; do not fabricate missing symbols/history. Build/test your interfaces while data arrive. If only three names are available, provide a separately labelled smoke test, not a passed 6–10-name gate.

FMP historical option bid/ask / expired-contract coverage is unverified. Historical membership access returned HTTP402. Current-universe survivor panels are permissible conditional research, not a point-in-time/survivorship-safe historical universe. Never print `.env` contents, API keys, authenticated URLs or raw errors that could contain them.

Prices are split-adjusted close, not dividend total returns. Using these as model-underlying observations does not automatically account for dividends, corporate actions, borrow fees or option adjustments.

## Existing replay API (read source before use)

`hedging_harness.replay` provides frozen `OptionPosition(instrument_id, underlying, kind, strike, expiry, quantity, volatility, multiplier=1.0)` and:

```
replay(prices, positions, *, equity_holdings=None,
       hedge_options=False, hedge_every=1, cost_bps=0.0, rate=0.0,
       initial_capital=None, sessions_per_year=252,
       liquidate_at_end=True, as_of=None, session_calendar=None,
       data_label=...)
```

- `prices`: finite positive date-indexed DataFrame, complete explicit sessions.
- Positive option quantity is purchased; negative is written. Quantity × multiplier is signed share-equivalent units.
- European model options open at first observation and cash-settle on explicit expiry dates in the supplied session index.
- Fixed supplied model volatilities must be estimated using observations available at the trade date. Availability/cutoff is caller responsibility.
- Core equity and option delta hedges are separate sleeves; stock trades net by underlying.
- `hedge_options=False` is essential for protective overlays: do not neutralize away their purpose.
- Pass the SAME explicit `initial_capital` in every strategy comparison. The default equals gross long inception equity and is unsuitable for comparisons that reduce equity exposure.
- Funding permits symmetric-rate borrowing/lending. Margin, option spreads, short borrow fees, dividends and American exercise are not yet supported; do not claim they are.
- Return exposes `ledger`, `trades`, `holdings`, `option_ledger`, `initial_capital`, `terminal_nav`, `terminal_pnl`, `peak_borrowing`, `total_stock_cost`, `provenance`.

## Study design to freeze before evaluation

1. Transparent fixed 6–10-name equity long/short mandate; predefined gross/net/issuer weights and dates. Do not optimize equity alpha or stock selection on test outcomes.
2. Use the identical initial equity book, capital, dates and realized stock paths across overlays. Report separate reduced-exposure comparators with their remaining cash earning the same rate.
3. Define a small, explicit protection-budget grid, maturity/strike rules, roll schedule, cost assumptions and calibration cutoffs before test evaluation. Historical model-option prices are not observed implied volatilities or executable quotes.
4. Use chronological periods consistent with the risk worker: training2010–2017, validation2018–2020, untouched test2021–2026-11-04. All rolling estimates must be past-only; treat overlapping protection windows through non-overlapping windows or dependence-aware evaluation.
5. Keep premium financing and cash/NAV conventions consistent. Compare economic risk for constant initial capital and explain any changed gross/net exposure.

Required baseline policies, within actual engine/data capability:

- Unhedged fixed equity book.
- Predetermined reduced equity exposure (at least one simple reduction).
- Sector ETF stock hedge with a past-only beta estimate, using XLF observations.
- Purchased puts for selected LONG equities.
- Purchased calls or another explicit upside-loss protection for SHORT equities.
- Sector downside protection with explicit beta/basis-risk caveat; a sector put alone does not protect short-side upside losses.
- Put spread or collar comparison with bounded-loss/limited-upside mechanics explained and signed positions correct.
- One modest price-risk-informed overlay, using past-only risk estimates; label it price-history-informed, not a validated macro/funding forecast.

Do not force unsupported policies into an existing API silently. If ETF holdings or additional instruments require columns, align complete calendars and pass all required underlying columns. A fixed-vol proxy may support a model-contract study but does not resolve option-market data coverage. Preserve all restrictions in results.

## Required results and tests

- Budget/protection frontier: total option premium paid/received, stock costs, financing, net P&L, drawdown, downside/tail loss, upside retained and peak borrowing.
- Exposure/NAV attribution separates core equities, ETF sleeve, option positions, cash and costs.
- Appropriate risk and budget uncertainty across historical evaluation windows, keeping names from the same market episode together. Do not apply independent-path Monte Carlo bootstrap directly to overlapping historical dates.
- Hand reconciliation of inception, roll/expiry and one adverse window for long puts AND short-position upside protection.
- Tests for sign conventions, contract multipliers, put floors/spread caps/collar upside, common initial capital, unchanged base-equity holdings across protection policies, cash and NAV identities, no future-information leakage, missing data and calendar alignment.
- Standalone Markdown report, machine-readable CSV/JSON outputs, source/input/protocol hashes, saved plots and a runnable executed notebook.
- Honest gate table: what passed, what is model-contract-only, what data/market features remain absent. No post-hoc reoptimization on test outcomes.

## Integration and what comes next

Opus ends at a reproducible Stage-6 overlay experiment and documented evidence. Codex/root integrates its artifacts and interfaces, then coordinates Stage7 breadth/composition tests with the data/risk owners: 3→10→25→40–50, master-universe paths/subsets, constant total exposure and untouched evaluation. Stage7 historical survivorship requirements remain blocked unless point-in-time membership/failed-name coverage is actually established.

Return a concise handoff with exact files, commands run, tests/results, selected assumptions, limitations and requested upstream API changes. Human review is explicitly downstream of this automated pass.

## Integration update: forecast timing and verified data

The core-ten and SPY/XLF panels are now available and aligned. FMP has explicitly documented that options data are unsupported; the restriction is no longer merely an unverified entitlement. Continue with clearly labelled model contracts until a separate provider is audited.

The risk forecasts are issued **after the origin close**, because features include that close. A forecast-informed overlay must therefore enter at a later executable observation. A same-close hypothetical model valuation must be labelled as such and must not be presented as an executable fill using information observed only after that close.

The core risk-model implementation and reports use training2010–2017, validation2018–2020 and test2021–2026-11-04. Negative/inconclusive forecast comparisons are retained. The current-universe/missing-history audit remains a condition on any later generalization claim.

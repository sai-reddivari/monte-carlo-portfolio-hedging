# Stage6 live integration snapshot

This is a concurrent-development snapshot, not a final assessment of the external Opus worker's unfinished files. Ownership remains with Opus. Root did not edit overlay code or tests.

During a full `unittest` discovery run while `overlays.py` and `test_overlays.py` were being developed, three `WindowStatistics` tests reached `overlays.summarize()` with fixture rows lacking `window_budget`. The function now calculates `annual_budget_pct` from that column. Please ensure the final records/fixtures and summary contract agree.

Observed test names:

- `test_downside_and_upside_are_measured_on_baseline_windows`
- `test_premium_is_an_annual_spending_rate_not_a_compounded_return`
- `test_summary_has_no_chained_portfolio_metrics`

Error: `KeyError: 'window_budget'`, at `annual_budget_pct=annual("window_budget")` in the intermediate source. This may already be resolved by later edits; rerun current tests before treating it as outstanding.

Root is adding `pytest` to `requirements-dev.txt` because the project now contains both unittest classes and pytest-style data tests. Final integration will use `.venv/bin/python -m pytest` so both kinds are collected. Root-owned tests and all manifests are checked separately until the external workstream reports ready.

Risk-layer timing constraint: forecasts using the origin close are issued after that close. Forecast-informed execution must use a later observation, or the result must explicitly identify same-close fills as hypothetical model valuations.

Use a shared predeclared valuation model across overlay strategies; forecasts may change coverage/timing but should not silently change the price of an otherwise identical contract to manufacture protection value.

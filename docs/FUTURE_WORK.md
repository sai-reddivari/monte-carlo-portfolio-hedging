# Future work — proposals only

No item below is implemented, tuned or tested by the publication refactor. Any next economic study needs a separately frozen protocol and exposed historical periods remain retrospective.

## From Opus's preserved next-steps note

Source: `docs/research_log/next_steps_opus.md` (unchanged).

- Prioritize a small timestamped real-option-quote reality check; verify contract terms, spreads, skew and pricing assumptions before new economic claims.
- Consider laddered/staggered expiries, holding the original budget fixed under a new protocol.
- Measure intrawindow protection and predetermined cash-in/monetization rules rather than choosing the best exit afterward.
- Decompose bank-versus-capital-markets losses and investigate whether proposed hedges target the actual mandate exposure.
- Consider an explicitly synthetic crisis simulator with jumps/volatility spikes; it would not establish real-market generalization.

## From Sol's preserved next-steps note

Source: `docs/research_log/next_steps_sol.md` (unchanged).

- Define the event and risk component the mandate is intended to insure before selecting a hedge.
- Separate terminal wealth, marked protection and usable distress liquidity, with predetermined monetization and re-entry rules.
- Test whether forecast improvement translates into economic hedge value with observed quotes, static/adaptive comparators and predetermined exposure reduction.
- Specify a narrow funding-vulnerability mechanism and include failed/acquired institutions rather than treating deposits/liabilities as a complete vulnerability measure.
- Use window-level reconstruction as hypothesis generation; freeze confirmatory tests separately.

## New engineering proposals

- **New:** review data redistribution rights before any broader publication; preserve the immutable tag and seek explicit owner direction before any history rewrite.
- **New:** acquire the missing historical CRR callable only if the original source can be established. No replacement pricing implementation was invented during refactoring.
- **New:** address pandas timezone/float-parser deprecations and consider package upgrades only in a separately validated change. No upgrades were wanted or performed in the frozen refactor environment.
- **New:** future cross-platform CI may need its own audited wheel hashes; the current architecture-specific wheel lock records the actual frozen macOS ARM64 packages.

# MonteCarloEvaluations — financial-sector hedging research

Start with [Financial Sector Hedging Under Trading Costs and Model Uncertainty](docs/research_release_2_publication.md), the conditional Research Release 2 publication summary, and its [claims and errata](docs/research_release_2_claims_and_errata.md). The [evidence checkpoint](reports/research_status.md) records package readiness separately from empirical certification. **Research Gate 1 is complete and independently reproduced; full empirical Research Gate 2 remains open.** Human review is a separate downstream step. No public upload has occurred.

The central finding is a favorable cost–risk tradeoff in controlled hedging simulations, with metric-/horizon-dependent historical forecasts and pricing-/window-dependent model-option protection. Incremental economic hedge value remains unestablished. Mixed, adverse and inconclusive findings are retained.

The project retains `Book` as its validated model container. Baseline notebooks 00–03 load one source, [`config/illustrative_study.json`](config/illustrative_study.json), through `hedging_harness.study.load_named_inputs`. Named dictionaries and DataFrames remain readable notebook views. Derived underlying/instrument/position/observation tables are in `data/study_inputs/`; the JSON is authoritative.

## Research notebooks

| Notebook | Purpose |
|---|---|
| [00 — Setup](Hedging_Study_Notebooks/00_study_setup.ipynb) | Assumptions, Black–Scholes values/Greeks, initial exposures and Q paths |
| [01 — One-option ledger](Hedging_Study_Notebooks/01_single_option_ledger.ipynb) | Premium, stock trades, financing, costs and settlement |
| [02 — Portfolio](Hedging_Study_Notebooks/02_three_name_portfolio.ipynb) | Dependence, hedge frequencies, variance and joint-tail contributions |
| [03 — Sensitivities](Hedging_Study_Notebooks/03_cost_and_volatility_sensitivity.ipynb) | Costs, fixed-premium hedge-volatility errors and fresh-seed checks |
| [04 — Research Release 1](Hedging_Study_Notebooks/04_policy_selection_research.ipynb) | Budget-aware policy selection, locked evaluation, tail uncertainty and peak funding |
| [05 — Model-contract replay](Hedging_Study_Notebooks/05_model_contract_replay.ipynb) | Signed calls/puts, multipliers and lifecycle accounting on actual stock observations |
| [06 — Market risk](Hedging_Study_Notebooks/06_market_risk_models.ipynb) | Past-only variance/covariance forecasts and chronological evaluation |
| [07 — Equity overlays](Hedging_Study_Notebooks/07_equity_overlay_study.ipynb) | Fixed ten-name long/short mandate, model-option policies and exposure-reduction benchmarks |
| [08 — Breadth and composition](Hedging_Study_Notebooks/08_breadth_and_composition.ipynb) | Constant-notional, common-path comparisons through forty names |
| [09 — Filing-aware features](Hedging_Study_Notebooks/09_release_aware_features.ipynb) | Chronological price/sector/SEC variance forecasts, including final ten-name/six-bank extension |

Opus's stage 6 work is integrated with his [owner review addendum](docs/equity_overlay_review_addendum.md). Astra independently reconstructed all 2,013 base-case terminal outcomes, all 276 test collar legs and the original paired bootstrap intervals. The [permanent review archive](results/research-release-2/astra-review-20261106/archive_manifest.json) preserves evidence previously under `/tmp`. This review does not certify every intrawindow mark, drawdown, sensitivity or execution assumption. The [research plan](docs/research_plan.md) records evidence required for each empirical gate.

Canonical final artifacts are pinned in [the release index](config/research_release_2_package.json), including the [ten-name/six-bank feature report](results/feature-research-20261106T024244836968Z/report.md) and [frozen stage 6 report](results/equity-overlays-20261106T023430248130Z/report.md). Original hashed reports remain unchanged; the release claims supplement controls their corrected interpretation.

## Completed controlled release

- [Standalone report](results/research-release-1/release-1/report.md)
- [Frozen protocol](config/research_release_1.json)
- [Locked choice](results/research-release-1/release-1/selection.json)
- [Held-out outcomes](results/research-release-1/release-1/evaluation_metrics.csv)
- [Paired ES95 uncertainty](results/research-release-1/release-1/paired_tail_differences.csv)
- [Independent validation](docs/independent_validation.md)

Fourteen periodic, fixed-band and maturity-band candidates were compared under a $500 expected financed stock-cost budget on a $300,000 synthetic short-call book at 5 bp. The policy is selected on 5,000 outcomes and locked before generating 10,000 held-out outcomes. The selected maturity band has evaluation ES95 $3,327.95 and expected financed cost $487.97. The selected-versus-daily ES interval includes zero; no formal equivalence/noninferiority claim is made. Selected-versus-weekly incremental protection has an entirely negative paired interval.

## Data and interpretation

[Data coverage](docs/data_coverage.md) and [`data_gate_status.json`](data/market/data_gate_status.json) document actual FMP capabilities and entitlements. Ten issuers plus SPY/XLF have 4,236 aligned XNYS sessions, 2010-01-04..2026-11-04. The 50-name panel retains all names and missingness: 42 full histories and 8 partial. BK→BNY issuer continuity is explicit, not a silent ticker substitution.

FMP officially does **not** provide options data. Historical membership access returned HTTP 402. Current-survivor panels and European model contracts on historical stock paths are useful conditional research, not a survivorship-safe listed-option backtest. Split-adjusted closes do not include dividend cash flows. [Replay details](docs/model_contract_replay.md) and [risk research](docs/risk_research.md) state their limits and actual findings.

Stage 6 uses separate 63-session accounts and averages the worst six of 23 test windows (25% tail fraction), unlike Gate 1's ES95. Premium budgets were decision-time sizing allowances, not execution-enforced caps. The collar materially changes local delta and sacrifices upside; its entire benefit has not been attributed to exposure reduction. Post-hoc reduced-equity comparisons and window-placement diagnostics are labelled as such in the claims supplement.

Risk scenarios and forecasts are physical-return research; option valuation uses an explicitly declared Q-model. Under Q, zero-dividend drift is the financing rate, not an equity expected-return estimate. A realized-volatility forecast is not automatically market implied volatility. Forecasts issued after the origin close cannot support an executable same-close trade based on that close.

## Environment and credentials

```sh
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
```

For market-data calls, place `FMP_API_KEY=...` in a local `.env` in this project root. `.env` and caches are ignored; `.env.example` contains placeholders only. Never put secrets in notebooks, results, reports or authenticated URLs in logs. There is currently no `.git` directory, so ignore rules are prospective Git protection, not encryption or access control.

## Reproduce and verify

```sh
MPLBACKEND=Agg MPLCONFIGDIR=/tmp/hedging-study-mpl .venv/bin/python -m pytest -q
.venv/bin/python scripts/verify_release_2.py
.venv/bin/python scripts/research_status.py
```

The combined suite passed 194 tests plus 22 subtests, with 28 pandas timezone deprecation warnings and no failures. Publication verification checks archived hashes, frozen artifacts, source/input identities, documentation links and recorded test evidence; it does not run a new economic experiment. Human review remains separate.

Optional economic replications write fresh directories and do not replace the frozen release:

```sh
.venv/bin/python scripts/run_research_release_1.py
.venv/bin/python scripts/run_model_contract_replay.py
.venv/bin/python scripts/run_risk_research.py --prices data/market/prices_core_10.csv
```

Research runners write fresh result directories with protocol/data/source identities. Imports make no downloads or trading calls. Existing release directories are never overwritten by the controlled-study runner. Notebook 04 reads the committed release by default; its explicit flag starts a separate replication.

The original `MonteCarlo_Functions`/investigation notebooks remain numerical-method references. The adapter reuses the consolidated Black–Scholes module and exact-GBM source. Trading costs already reduce net P&L, including their financing impact; never subtract them twice. Shared peak funding uses aggregate concurrent cash, not a sum of separate maxima. Tail estimates and validation intervals retain their sample/model restrictions.

[Next economic protocol requirements](docs/next_economic_protocol_requirements.md) are tracked separately. Exact policy mapping and execution/inference rules must be written and hashed before another economic evaluation. No new economic protocol is represented as frozen or completed by this publication release, and no data purchase has been made.

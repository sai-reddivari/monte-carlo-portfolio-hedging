# Financial-sector hedging under trading costs and model uncertainty

Can financial-sector risk signals improve protection of a ten-stock long/short portfolio after costs, pricing assumptions and simpler exposure-reduction benchmarks are considered?

A controlled hedging experiment identifies a favorable cost–risk tradeoff. Historical extensions show that forecast improvements depend on metric and horizon, while model-priced option protection depends materially on pricing, exposure and evaluation-window assumptions. Incremental economic hedge value remains unestablished.

The paragraph above is verbatim from the [frozen publication summary](docs/final_findings/research_release_2_publication.md). Read its [claims and errata](docs/final_findings/research_release_2_claims_and_errata.md) and the separate [post-freeze display errata](docs/review/errata_post_freeze.md). Full empirical Research Gate 2 remains open.

## Reproduce

Use Python **3.14.8** and the unchanged 57-distribution lock. No package upgrades are part of this refactor.

```sh
python3.14 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
make reproduce
make test
make diff
```

Run from a clone that includes the immutable `pre-refactor` tag. The pipeline restores exact missing raw input files from that tag, checks their hashes, and executes pricing/Greeks and simulation/hedging studies, chronological forecasts/features, all eight overlay policies and original sensitivities, notebook views, and independent accounting/statistical checks. It writes fresh outputs under `results/reproduction/` and the full-precision `results/manifest_post_refactor.json`. No API keys, downloads or parameter reselection on test outcomes are required. Raw data provenance and redistribution limits are in [data/README.md](data/README.md).

For a fast review, `make test` includes a real frozen-seed regression of the controlled release, historical replay and ten-name risk model. Complete command output, elapsed time and the fresh-environment check are in [the Phase 1 report](docs/PHASE1_REPORT.md).

## Repository map

| Path | Purpose |
|---|---|
| `hedging_harness/pricing.py`, `domain.py`, `simulation.py` | Pricing/Greeks, validated books and correlated Q paths |
| `hedging_harness/hedging.py`, `policies.py`, `replay.py`, `overlays.py` | Cost-aware hedges and historical cash/stock/option accounting |
| `hedging_harness/risk_models.py`, `feature_models.py`, `breadth.py` | Chronological forecasting, filing-aware features and conditional breadth |
| `hedging_harness/evaluation.py`, `reporting.py`, `experiments/` | Metrics, provenance and experiment interfaces |
| `hedging_harness/notebooks/`, `Hedging_Study_Notebooks/` | Package-owned studies and call-only notebook views |
| `config/` | Exact published defaults, seeds, splits, costs and policy settings |
| `docs/final_findings/`, `docs/research_log/` | Unchanged frozen conclusions/evidence and research history |
| `docs/provenance/`, `docs/review/` | Per-number provenance and post-freeze errata |
| `results/pre_refactor/`, `results/manifest_pre_refactor.json` | Preserved baseline, executed notebook backups, logs and numerical contracts |

[EXPERIMENTS](docs/EXPERIMENTS.md) lists commands, inputs, outputs, runtimes and non-determinism controls. [CHANGELOG](CHANGELOG.md) maps every moved path; compatibility modules/links retain historical imports and document context. [FUTURE_WORK](docs/FUTURE_WORK.md) contains proposals only.

## Limitations

- Historical options are hypothetical European Black–Scholes contracts at assumed volatility; observed option quotes, bid/ask, dividends, borrow/rebate spreads, margin and American exercise are absent. Current-survivor samples are not survivorship-safe historical universes. Separate-window accounts are not continuous portfolio returns.
- In the historical equity-overlay accounting engine, short proceeds count as cash, so recorded ledger borrowing is zero for every policy; usable liquidity is not modelled. This is not a claim of zero real financing needs. The controlled short-call Monte Carlo book is a different account and does report borrowing.
- The two superseded directories `results/equity-overlays-20261106T020955456052Z` and `results/feature-research-20261106T020600619286Z`, and all six acquisition utilities, are **hash-only, not reproducible from current code**. Historical code is not reconstructed; see EXPERIMENTS for each entry.
- The frozen bundle manifest lists one macOS metadata file that Git ignores (`frozen_package_and_review_evidence/.DS_Store`), so **47 of 48 bundle entries verify from a clean checkout**. The manifest and frozen documents remain unchanged.
- Publication figures are rounded; manifests retain full precision. Three display-rounding differences are listed separately without changing any conclusion. Pointwise intervals, sparse tail windows, model-price assumptions and post-hoc date shifts limit economic inference.
- The software license excludes third-party market data and historical review material. Redistribution rights for vendor snapshots are not certified. The immutable historical tag retains original research artifacts; removing them from current-tree tracking does not erase Git history.

## Citation and license

Use [CITATION.cff](CITATION.cff) to cite the study. [LICENSE](LICENSE) covers the project software; it does not grant rights to vendor data or third-party material.

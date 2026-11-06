# Frozen experiment inventory (Phase 0)

The research conclusion is unchanged: **Incremental economic hedge value remains unestablished.** Phase 0 records the existing experiments and their reproducibility; it does not implement either next-steps note. Phase 1 requires the owner's confirmation.

The immutable `pre-refactor` tag is `a96d99210ea16ac2dd33f46623aaf96cbc563196` (original research HEAD: `71c0be1`). The tag includes only the separately committed RTF-to-text conversions and captured environment. Both `main` at that SHA and the tag were pushed to `origin` during Phase 0. Statements about no public upload in the original research documents describe their historical preparation state and have deliberately not been edited.

Use the existing `.venv/bin/python` (Python 3.14.8, macOS 26.6, arm64), exactly as pinned in `env/frozen_environment.txt`. No packages were installed or upgraded. Every audit child process receives:

```sh
export OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
export VECLIB_MAXIMUM_THREADS=1
export PYTHONHASHSEED=0 MPLBACKEND=Agg MPLCONFIGDIR=/tmp/phase0-mpl
```

All commands below run from the repository root. `P` means `.venv/bin/python`; `OUT` means a **new, nonexistent** destination. Existing results, inputs, reports and source notebooks are never replaced. Exact executed commands, wall times, seeds, exceptions, output hashes and the environment hash are in `results/manifest_pre_refactor.json`; raw stdout/stderr is in `results/pre_refactor/logs/`. The audit runner `scripts/freeze_phase0.py` is new Phase 0 tooling, outside the tagged numerical implementation.

The first canonical pass used the three requested thread variables. NumPy build inspection then identified Apple Accelerate, so a second complete canonical pass adds `VECLIB_MAXIMUM_THREADS=1`. Both passes and their individual runtime environments are retained; `experiments_accelerate_pinned/` is the authoritative fully pinned replay. All later commands use the additional control. `env/manifest_runtime_environment.json` records the discovery without altering the environment file frozen at the immutable tag. No packages changed between passes.

## Research script entry points

| Name / entry point | Command | Frozen inputs | Outputs | Approximate runtime |
|---|---|---|---|---|
| Controlled policy release | `P scripts/run_research_release_1.py --output-dir OUT` | `config/research_release_1.json`, `config/illustrative_study.json` | Selection lock; selection/evaluation metrics; costs, tails, funding and accounting audits; report/plots | 20 s |
| Historical model-contract replay | `P scripts/run_model_contract_replay.py --output-dir OUT` | `data/market/prices_split_adjusted.csv`; 252-return calibration; fixed normal-2019 and COVID-2020 windows in runner | Per-window/per-strategy cash, holding, option and trade ledgers; summary, checks and hand reconciliation | 2 s |
| Original three-name price risk | `P scripts/run_risk_research.py --output-dir OUT` | Three-name split-adjusted prices; `prices_benchmarks.csv`; `RiskProtocol` defaults | Forecast observations; pooled/per-name scores; paired loss intervals; checks, report, plots | 4 s |
| Final ten-name price risk | `P scripts/run_risk_research.py --prices data/market/prices_core_10.csv --output-dir OUT` | Core-ten prices; same benchmark and protocol | Same price-risk outputs | 3 s |
| Original feature cohorts | `P scripts/run_feature_research.py --output-dir OUT` | Core-ten prices; SPY/XLF; saved feature admission audit; original SEC filing facts/snapshots | Predictions, financial availability traces, cohort coverage, selected models, validation/test scores and paired intervals | 5 s |
| Final ten-name / six-bank feature cohorts | `P scripts/run_feature_research.py --sec-core10 --output-dir OUT` | Same inputs plus `data/market/features/sec_facts_core10/` | Original cohorts plus final extension, same tables/report/plots | 6 s |
| Conditional breadth | `P scripts/run_breadth_research.py --output-dir OUT` | Fifty-name unbalanced prices and coverage/universe metadata; original locked Gate-1 selection | Two 42-name master scenarios, 3/10/25/40-name subsets and composition chains; policy/tail tables, NPZ outcomes, historical equity diagnostic | 30 s |
| Equity overlays: development and freeze | `P scripts/run_overlay_research.py freeze --output-dir OUT` | `config/equity_overlay_study.json`, core-ten and benchmark prices | Training/validation records, validation selections, frozen protocol and commitment | Several minutes |
| Equity overlays: first held-out evaluation | `P scripts/run_overlay_research.py evaluate --run-dir OUT` | The newly reproduced frozen protocol, original dates/candidates/pricing/execution/sensitivity settings | All candidate/window outcomes; selected summaries; uncertainty, attribution, side protection, sensitivities; report/plots | Several minutes |

The overlay commands reproduce the original selection/evaluation sequence into a fresh directory. No `--revision-note` rerun is performed against the original run. Research windows remain independent accounts; shifted reviewer offsets remain post-hoc diagnostics, not new independent evidence.

## Notebooks

The study launcher is `P scripts/run_harness_notebooks.py --notebooks NAME.ipynb --output-dir OUT` (all ten by default). It executes fresh IPC kernels with this environment, a 240-second cell timeout, and saves copies plus an execution manifest. Phase 0 also attempts each notebook separately using `P scripts/freeze_phase0.py notebook-worker SOURCE DESTINATION`, which retains the same code, interpreter and IPC transport and allows up to 1,200 seconds per cell. Original notebooks and their stored outputs remain untouched; new executed or partially executed copies are in `results/pre_refactor/notebooks/`.

| Notebook | Inputs / numerical controls | Outputs / experiment behavior | Approximate runtime |
|---|---|---|---|
| `Hedging_Study_Notebooks/00_study_setup.ipynb` | Inline three-name assumptions, seed 20261105, 5,000 paths | Pricing/Greeks, exposures, Q-path diagnostics in notebook; the saved `Book`/simulation import is commented out, so clean-kernel execution is expected to reveal that defect | Under 1 min to failure |
| `01_single_option_ledger.ipynb` | Illustrative config; JPM; weekly hedge; 5 bp; audit path zero | Cash/trade/settlement accounting in notebook | Under 1 min |
| `02_three_name_portfolio.ipynb` | Illustrative config; common normals across dependence/policy cases | Portfolio risk, variance/correlation and tail contributions | Under 1 min |
| `03_cost_and_volatility_sensitivity.ipynb` | Illustrative config plus unmodified inline cost/volatility grids; fresh seed = base + 1 | Cost and fixed-premium hedge-volatility sensitivities; fresh-seed check | Under 1 min |
| `04_policy_selection_research.ipynb` | Controlled protocol and committed release; `RUN_NEW_EXPERIMENT=False` | Reads frozen tables and reports by default; does not silently rerun/reselect | Under 1 min |
| `05_model_contract_replay.ipynb` | Same frozen replay inputs/defaults | Replay ledgers, reconciliation and charts in notebook | Under 1 min |
| `06_market_risk_models.ipynb` | Ten-name prices, benchmark, original risk protocol | Reruns price-risk study into timestamped `results/risk-research-notebook-*`, then displays outputs | Under 1 min |
| `07_equity_overlay_study.ipynb` | Pinned overlay run | Verifies hashes and reads results; independently reruns two representative windows using original methods | Under 1 min |
| `08_breadth_and_composition.ipynb` | Pinned breadth run, source/input identities | Reads and verifies frozen common-path results, then plots them | Under 1 min |
| `09_release_aware_features.ipynb` | Ten-name/six-bank extension flag enabled | Reruns feature research into timestamped `results/feature-research-notebook-*` | Under 1 min |
| `MonteCarlo_InvestigationNotebooks/MonteCarlo_ModelIntroduction.ipynb` | No code cells | Expository notebook only | Under 1 s |
| `MonteCarlo_Accuracy_ComputingCost.ipynb` | Seed 1995 and explicit offsets 21–25; saved grids and allocations | Exact/Euler/Milstein bias, convergence, variance reduction and hardware timing tables in notebook | Unknown in advance; bounded at 20 min |
| `MonteCarlo_EstimatingGreeks.ipynb` | Seed 1995 and saved repeated-seed finite-difference/pathwise/LR grids | Greek estimates and standard errors in notebook | Unknown in advance; bounded at 20 min |
| `MonteCarlo_PathDependency_HedgeControls.ipynb` | Seed 1995 and offsets 1–20; saved barrier grids and path counts | Barrier/path-control estimates, quadrature/grid comparisons and timings in notebook | Unknown in advance; bounded at 20 min |
| `MonteCarlo_StochasticVolatility.ipynb` | Seed 1995; offsets 251/252; 200,000-path, 3,276-step reference as saved | Stochastic-volatility scheme errors and implied-volatility diagnostics in notebook | Unknown in advance; bounded at 20 min |

The four original computational investigation notebooks have substantial work and hardware-dependent timings; their aggregate runtime was not measured before this audit. The conservative execution plan allows 20 minutes per unknown entry point and a four-hour total budget, with timeout entries explicitly marked `hash-only`. An attempted execution that raises an exception is recorded as `failed`, with saved outputs still hashed. It is not relabelled a successful reproduction.

## Archived reviewer entry points

| Entry point | Command | Inputs | Outputs | Approximate runtime |
|---|---|---|---|---|
| Independent terminal accounting | `P results/research-release-2/astra-review-20261106/accounting/astra_overlay_independent_portable.py --output-dir OUT` | Raw prices and immutable overlay protocol; validates original input/source/output hashes | 2,013 terminal reconstructions, cash components, residual summary | Under 1 min |
| Independent statistics / collar reconstruction | `P results/research-release-2/astra-review-20261106/statistical_review/diagnostic.py --output-dir OUT` | Frozen overlay records and raw prices; bootstrap seed 730601 | Original paired ES intervals, block-length variants, 276 collar legs and local exposures | Under 1 min |
| Window placement | `P scripts/freeze_phase0.py window-worker` | Archived `window_placement/run_diagnostic.py`; original 0/5/21/42 offsets, fixed eight policies and all original splits | Summary/records/checks/counts/comparisons for 1,936 policy/windows | About 1 min historically; machine-dependent |
| Owner supplementary checks | `P results/research-release-2/opus-review-20261106/owner_checks/owner_checks.py` | Original overlay protocol, prices and saved records | Budget/exposure/delta/short-sleeve diagnostics on stdout | Under 1 min |
| Owner window table | `P results/research-release-2/opus-review-20261106/owner_checks/window_placement_check.py results/research-release-2/astra-review-20261106/window_placement/window_records.csv` | Saved shifted-window records | Original post-hoc comparison table on stdout | Under 1 s |

The window worker changes **only** the archived script's hard-coded `/tmp/astra_window_phase_20261106` output literal in memory, directing fresh files into `results/pre_refactor/reviewers/window_placement/`. The archived file itself, numerical logic, source `__file__`, offsets, dates, seeds and candidate list are unchanged. Byte-identical copies of these reviewer scripts under `docs/Final Findings and Takeaways/frozen_package_and_review_evidence/` are aliases, not additional experiments; their hashes are independently checked.

## Acquisition and publication utilities

Acquisition utilities are entry points, but refreshing a vendor query does not reproduce a historical data snapshot. They are inventoried with explicit `hash-only` reasons and hashes of their saved products. Phase 0 uses the exact saved inputs rather than replacing them with new API responses. FMP/SEC retrievals may require credentials, entitlements, network access and historical vintages which are not embedded in the saved normalized tables. The local `.env` is never read into audit evidence or copied to a publication mirror.

| Script / command | Inputs | Saved outputs / reason not refreshed | Approximate runtime |
|---|---|---|---|
| `P scripts/audit_market_data.py [--export-prices]` | FMP key; cache; fixed date windows; up to 12/15 live requests | `results/data-audit/coverage.json`, three-name price panels/metadata; new live audit would update the historical snapshot | Network-dependent |
| `P scripts/fetch_core_prices.py` | Saved three-name seed plus FMP histories for remaining issuers, SPY/XLF and explicit BK/BNY mapping | Core-ten/benchmark panels, coverage/metadata and symbol mapping | Network-dependent |
| `P scripts/audit_reference_data.py` | FMP key; current screener, historical membership and delisted endpoints | Current-universe snapshot, entitlement result and delisted sample; historical membership was unavailable (HTTP 402) | Network-dependent |
| `P scripts/fetch_financial_universe.py` | Saved current-universe snapshot, FMP price histories | Fifty-name universe, eligibility/coverage audits, unbalanced prices and metadata | Network-dependent |
| `P scripts/audit_research_features.py` | FMP key; cached statements/filing facts and two Treasury samples | `results/feature-audit/coverage.json`, statement fields, Treasury and original SEC audit products | Network-dependent |
| `P scripts/extend_sec_core10.py` | FMP filing metadata and SEC companyfacts retrieval | Core-ten SEC facts, snapshots, coverage and probe manifest | Network-dependent |
| `P scripts/verify_release_2.py` | Existing release config, hashes, docs/links, archived test XML | Publication integrity verification; executed in disposable tagged archive to protect the original report | Seconds |
| `P scripts/research_status.py` | Existing config, verification and frozen result products | Publication status JSON/Markdown; executed in disposable tagged archive | Seconds |
| `P scripts/package_release_2.py` | Existing publication snapshot | Expected refusal to overwrite `results/research-release-2/release-2`; no new publication package is invented | Under 1 s |
| `P -m pytest -q` | Existing fourteen test modules and fixtures | Existing suite results plus new `results/pre_refactor/tests.xml` | Under 1 min |

The publication utilities' historical source copies under `results/research-release-2/release-2/snapshots/scripts/` and the findings bundle are evidence snapshots, not competing launchers. Their original relative import/path context is retained.

## Library fragments and configuration entry points

`BlackScholes_Functions/BlackScholes_D1D2_Price_Payoff_Greeks.py` provides pricing, payoff, Greeks and exposure functions, with no standalone experiment. `MonteCarlo_Functions/MonteCarlo_EulerPathwayGeneration.py`, `MonteCarlo_MilsteinPathwayGeneration.py` and `MonteCarlo_ExactPathwayGeneration.py` are function fragments requiring the caller's NumPy context. `MonteCarloSeeded_OneStepExact.py`, `MonteCarlo_OneStepExactPrices.py` and `MonteCarlo_MethodComparison.py` additionally expect notebook globals such as model parameters, pricing helpers and prior integral results. Phase 0 checks all six Python fragments as saved; failures expose missing caller context and are not repaired. Their complete computational experiments are in the investigation notebooks. `hedging_harness/legacy.py` deliberately supplies NumPy when loading the exact-path fragment; it does not run MethodComparison.

`hedging_harness` modules (`core`, `policies`, `study`, `research`, `replay`, `risk_models`, `feature_models`, `breadth`, `overlays`, `uncertainty`, `legacy`) and `market_data` modules are libraries called by the inventoried runners and notebooks, not separate hidden CLIs. There are no packaging console-script declarations or Makefile at the tag.

| Config | Authoritative role |
|---|---|
| `config/illustrative_study.json` | Named three-option inputs, dependence, seed 20261105, 5,000 paths; derived CSVs under `data/study_inputs/` |
| `config/research_release_1.json` | Fourteen candidates; selection seed 730201 / 5,000 paths, evaluation 730202 / 10,000 paths; bootstrap base 730204; costs and $500 screen |
| `config/equity_overlay_study.json` | Dates, 63-session accounts, one-session lag, ten-name weights, eight policy families, pricing/financing/cost assumptions, sensitivities and bootstrap seed 730601 |
| `config/research_release_2_package.json` | Evidence index and canonical result paths; explicitly **not** an economic protocol |
| Saved `protocol.json` / lock / commitment files | Runtime-expanded parameters and hashes for their own original runs; every such existing product is hashed in the manifest |
| `RiskProtocol` and runner/notebook inline controls | Remaining forecasting defaults, original cohorts, ridge grid, breadth parameters and legacy grids are still code-level at Phase 0; extraction is reserved for Phase 1 |

## Non-determinism audit beyond seeds

This is a source inspection and same-environment replay, not a claim of cross-platform bitwise determinism. The preserved output hash inventory distinguishes byte equality from numerical tolerance.

| Source / location | Effect and Phase 0 handling |
|---|---|
| NumPy/SciPy BLAS/LAPACK reductions, matrix products, decompositions and ridge solves (`core`, `risk_models`, `feature_models`, `breadth`, reviewer covariance/beta calculations) | Parallel reduction order and platform libraries may affect low bits. All manifest child processes pin OMP, MKL and OpenBLAS to one thread before imports. Python, package versions, architecture, OS and NumPy build configuration are captured. No algorithm or numerical tolerance is silently changed. |
| Multiprocessing / worker reduction order | No multiprocessing, concurrent executor, joblib parallelism or worker reduction was found in the tagged research-producing Python modules. The notebook runner starts one fresh kernel at a time. Package-native threads remain subject to the controls above; no new process-level parallel reduction is introduced. |
| `datetime.now(timezone.utc)` in all six research runners, `research.run_release`, notebook launcher and notebooks 04/06/09 | Changes output-directory names, provenance, commitment/selection timestamps, protocol hashes and downstream hash references. It does not choose calibration dates or train/validation/test placement. Full JSON/report hashes may therefore differ despite identical numerical tables. Original files are preserved; these differences are recorded, not normalized away. |
| `datetime.now` and retrieval timestamps in acquisition modules/utilities; vendor/SEC revisions and current screens | Live responses, membership, entitlement and filings can change independently of seeds. No live refresh is represented as reproducing the saved snapshot. Exact committed raw/normalized input hashes and explicit `hash-only` statuses are retained. |
| Dictionary iteration (`study`, `core`, `overlays`, `risk_models`, `feature_models`, `breadth`, reviewer scripts) | Python 3.14 preserves insertion order. Config JSON order and saved DataFrame column order are part of the contract. Weight/share summation and matrix feature order must remain intact during Phase 1. No result-producing unordered dictionary iteration was found; dictionaries built in explicit input/literal order must not be reconstructed from sets. |
| Sets / frozensets in `core.Book`, policy/config validation, `breadth` cohort checks and `feature_models` column validation | Used for membership, duplicate detection, set equality/difference checks, or explicitly sorted lists. They do not define simulation asset order. `replay.required_names` is filtered through original price-column order; `expiring_names` is queried for membership in ordered asset iteration. Plot compositions are explicitly sorted. No direct result-producing iteration over an unsorted set was found in the tagged libraries. `PYTHONHASHSEED=0` is additionally fixed for every child. |
| Group/sort/tail/tie ordering | Pandas groupby/pivot/sort order, `np.argsort`, insertion order of candidate lists and floating-point tie handling affect selected policies and tail contributions. Saved row/column and candidate order are preserved; no sorting or stable-sort substitution is applied to research code. Comparisons check text/schema and missingness as well as every numeric CSV cell. |
| Legacy investigation `time.perf_counter`, repeated minimum timings, plot metadata, temporary paths / kernel IDs | Wall-clock performance and image/notebook metadata are intrinsically observational. Existing timings/images/notebooks are hashed; new timings are reported as measured, without a deterministic-equality claim or a fabricated seed fix. No seed change can make elapsed time deterministic. |
| Kernel state and interactive execution order | Some committed notebooks have nonsequential execution counts or unexecuted cells. Fresh-kernel attempts reveal missing globals rather than inheriting a prior session. Both original notebook hashes and partial failure outputs are retained. No notebook code is repaired in Phase 0. |
| Filesystem discovery and absolute paths | Launchers explicitly sort notebook glob results. Fixed canonical release paths replace modification-time selection in `research_status`. Archived reviewer and saved protocol paths can be machine-specific; only the disclosed window output redirection and disposable publication workspace alter destinations, not numerical inputs. |

All explicit RNG uses in result-producing research paths were already seeded (including legacy notebook streams). No experimental seed or parameter was changed. Hash-seed and thread environment controls are execution controls, and are recorded separately from research seeds.

## Evidence interpretation

`results/pre_refactor/publication_numbers.json` retains each numeric literal's exact spelling, document/line/column and complete source line. It intentionally includes historical dates and identifiers; the manifest does not misrepresent them as estimated quantities. The final Phase 0 evidence report additionally inventories number words. Deterministic numerical contracts come from saved result-table values and source configurations, with the publication's rounded values preserved separately. Reviewer reconstruction residuals are historical measurements of agreement, not economic model parameters.

Bundle verification checks the top-level findings bundle, nested archive/snapshot manifests, all frozen experiment identities and both copies of reviewer evidence. Any missing or mismatched identity is a finding, never repaired silently. Fresh CSV comparisons use relative tolerance `1e-9` and zero absolute tolerance; paired NaNs represent missingness. Both raw hash differences and any numerical/text/schema differences are reported. Protocol timestamps and output paths are not excluded from the raw hash record.

See `docs/PHASE0_REPORT.md` for the actual completed commands, results, limitations and checkpoint status. The machine-readable manifest is authoritative about which commands were executed, failed, timed out or were explicitly hash-only.
## Historical saved-run coverage (completed audit)

Every originally tracked result directory is accounted for below. `covered_by_current_entrypoint` means all saved CSVs are byte-identical to a fresh replay, or the explicitly identified notebook wrapper of that runner. Hash-only development snapshots have missing historical source/completion evidence; they are not silently counted as executed. Full file hashes, source mismatches and reasons are in `historical_saved_runs` in the manifest.

| Saved directory | Coverage | Recorded source mismatches | Reason |
|---|---|---:|---|
| `results/breadth-20261106T020056662020Z` | covered_by_current_entrypoint | 1 | Every saved CSV is byte-identical to the recorded fresh final-source replay; original metadata/source identities are preserved separately. No separate historical shell command is asserted. |
| `results/breadth-20261106T020251008334Z` | covered_by_current_entrypoint | 1 | Every saved CSV is byte-identical to the recorded fresh final-source replay; original metadata/source identities are preserved separately. No separate historical shell command is asserted. |
| `results/breadth-20261106T020606662492Z` | covered_by_current_entrypoint | 1 | Every saved CSV is byte-identical to the recorded fresh final-source replay; original metadata/source identities are preserved separately. No separate historical shell command is asserted. |
| `results/breadth-20261106T020730752645Z` | reproduced | 0 | All saved CSV output cells match the recorded fresh replay; any historical source-version difference is separately retained below. |
| `results/data-audit` | hash-only | 0 | Saved acquisition snapshot; live refresh explicitly not attempted (see acquisition command entries). |
| `results/equity-overlays-20261106T020955456052Z` | hash-only | 2 | Earlier development run: recorded source SHA differs from the available frozen implementation; that historical source version is not separately supplied, so rerunning it exactly would require reconstructing/changing code. Saved products are hashed, never replaced. |
| `results/equity-overlays-20261106T021350045727Z` | covered_by_current_entrypoint | 1 | Every saved CSV is byte-identical to the recorded fresh final-source replay; original metadata/source identities are preserved separately. No separate historical shell command is asserted. |
| `results/equity-overlays-20261106T023430248130Z` | reproduced | 0 | All saved CSV output cells match the recorded fresh replay; any historical source-version difference is separately retained below. |
| `results/equity-overlays-review-20261106` | archived_alias | 0 | Reviewer or publication evidence already inventoried and hash-checked; not an additional economic experiment. |
| `results/feature-audit` | hash-only | 0 | Saved acquisition snapshot; live refresh explicitly not attempted (see acquisition command entries). |
| `results/feature-research-20261106T020600619286Z` | hash-only | 2 | Earlier development run: recorded source SHA differs from the available frozen implementation; that historical source version is not separately supplied, so rerunning it exactly would require reconstructing/changing code. Saved products are hashed, never replaced. |
| `results/feature-research-20261106T023309546693Z` | hash-only | 0 | Earlier/incomplete development snapshot without a complete matching source-and-completion record. No separate historical shell command or source version can be verified; saved products are hashed, never replaced. |
| `results/feature-research-20261106T023554469322Z` | covered_by_current_entrypoint | 1 | Every saved CSV is byte-identical to the recorded fresh final-source replay; original metadata/source identities are preserved separately. No separate historical shell command is asserted. |
| `results/feature-research-20261106T023728680733Z` | covered_by_current_entrypoint | 1 | Every saved CSV is byte-identical to the recorded fresh final-source replay; original metadata/source identities are preserved separately. No separate historical shell command is asserted. |
| `results/feature-research-20261106T023758007835Z` | covered_by_current_entrypoint | 1 | Every saved CSV is byte-identical to the recorded fresh final-source replay; original metadata/source identities are preserved separately. No separate historical shell command is asserted. |
| `results/feature-research-20261106T024225834886Z` | reproduced | 0 | All saved CSV output cells match the recorded fresh replay; any historical source-version difference is separately retained below. |
| `results/feature-research-20261106T024244836968Z` | reproduced | 0 | All saved CSV output cells match the recorded fresh replay; any historical source-version difference is separately retained below. |
| `results/feature-research-notebook-20261106T024136578460Z` | covered_by_current_entrypoint | 1 | Every saved CSV is byte-identical to the recorded fresh final-source replay; original metadata/source identities are preserved separately. No separate historical shell command is asserted. |
| `results/feature-research-notebook-20261106T024305994053Z` | covered_by_current_entrypoint | 0 | Every saved CSV is byte-identical to the recorded fresh final-source replay; original metadata/source identities are preserved separately. No separate historical shell command is asserted. |
| `results/model-contract-replay-20261106T014523263280Z` | reproduced | 0 | All saved CSV output cells match the recorded fresh replay; any historical source-version difference is separately retained below. |
| `results/research-release-1/first-locked-release` | covered_by_current_entrypoint | 0 | Every saved CSV is byte-identical to the recorded fresh final-source replay; original metadata/source identities are preserved separately. No separate historical shell command is asserted. |
| `results/research-release-1/release-1` | reproduced | 0 | All saved CSV output cells match the recorded fresh replay; any historical source-version difference is separately retained below. |
| `results/research-release-1/validated-release` | covered_by_current_entrypoint | 0 | Every saved CSV is byte-identical to the recorded fresh final-source replay; original metadata/source identities are preserved separately. No separate historical shell command is asserted. |
| `results/research-release-2/astra-review-20261106` | archived_alias | 0 | Reviewer or publication evidence already inventoried and hash-checked; not an additional economic experiment. |
| `results/research-release-2/opus-review-20261106` | archived_alias | 0 | Reviewer or publication evidence already inventoried and hash-checked; not an additional economic experiment. |
| `results/research-release-2/release-2` | archived_alias | 0 | Reviewer or publication evidence already inventoried and hash-checked; not an additional economic experiment. |
| `results/risk-research-20261106T014645390937Z` | reproduced | 1 | All saved CSV output cells match the recorded fresh replay; any historical source-version difference is separately retained below. |
| `results/risk-research-20261106T014747676804Z` | reproduced | 0 | All saved CSV output cells match the recorded fresh replay; any historical source-version difference is separately retained below. |
| `results/risk-research-notebook-20261106T015049784721Z` | covered_by_current_entrypoint | 0 | Historical notebook wrapper of the price-risk entry point; its original outputs are retained by exact hashes. |

## Phase 1 reproduction interface and explicit exclusions

`make reproduce` runs the package from the exact saved raw inputs and regenerates `results/manifest_post_refactor.json`. `make test` runs unit/accounting tests and a real fast-subset replay. `make diff` checks full-precision manifest contracts at relative tolerance 1e-9, absolute tolerance zero. The manifests retain full precision; publication display differences are recorded in `docs/review/errata_post_freeze.md`.

| Entry | Status | Reason |
|---|---|---|
| `results/equity-overlays-20261106T020955456052Z` | **hash-only, not reproducible from current code** | Superseded development freeze; original source version unavailable. Historical code is not reconstructed. |
| `results/feature-research-20261106T020600619286Z` | **hash-only, not reproducible from current code** | Superseded feature run; original source version unavailable. Historical code is not reconstructed. |
| `scripts/audit_market_data.py` | **hash-only, not reproducible from current code** | A present live query cannot regenerate the frozen vendor/entitlement snapshot. |
| `scripts/fetch_core_prices.py` | **hash-only, not reproducible from current code** | Frozen historical provider snapshot may have revisions; use its exact input bytes. |
| `scripts/audit_reference_data.py` | **hash-only, not reproducible from current code** | Historical current-universe/entitlement snapshot cannot be recovered by a present query. |
| `scripts/fetch_financial_universe.py` | **hash-only, not reproducible from current code** | Frozen survivor snapshot and histories are not a new live universe request. |
| `scripts/audit_research_features.py` | **hash-only, not reproducible from current code** | Financial/filing/Treasury snapshot and entitlements cannot be regenerated exactly. |
| `scripts/extend_sec_core10.py` | **hash-only, not reproducible from current code** | SEC/vendor vintages and retrieval metadata may change. |

The six acquisition programs remain available as acquisition utilities; the label concerns exact reproduction of their historical products. No credentials or live refresh are used by `make reproduce`. Normalized raw inputs are restored byte-for-byte from the immutable tag. Original pre-refactor outputs, notebooks and logs remain in place. Reproduction writes a new ignored directory, never into a frozen result directory.

Notebook 00's required import is restored in its package study. Source notebooks now only call package functions; their original executed versions remain under `results/pre_refactor/notebooks/as_committed/`. The eight identical legacy setup cells are shared in `hedging_harness/notebooks/reference.py`. The two old notebook-global snippets expose `one_step_prices(...)` and `compare_methods(..., crr_price=...)` in `hedging_harness/legacy_methods.py`. No CRR implementation existed in the frozen repository, so its callable remains an explicit required dependency, not an invented pricing method. These reference snippets are not canonical publication experiments.

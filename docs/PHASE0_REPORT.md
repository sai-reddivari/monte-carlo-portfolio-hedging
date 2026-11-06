# Phase 0 freeze report

Phase 0 is complete with the findings below. **Phase 1 has not started and requires owner confirmation.** No research implementation, assumptions, seed, window, split, policy or original finding document was changed.

The research conclusion remains: **Incremental economic hedge value remains unestablished.**

## Checkpoint and changes

- Original research commit: `71c0be1`.
- Notes-only commit: `cd1356e` — `docs: convert next-steps notes to markdown`. Both RTF files were extracted with macOS `textutil`; each Markdown file was compared byte-for-byte with a second extraction before the RTF was removed. No other file was in that commit.
- Environment-only commit / immutable tag: `a96d99210ea16ac2dd33f46623aaf96cbc563196` — `chore: capture pre-refactor Python environment`.
- `pre-refactor` was created once and pushed, along with main, to `https://github.com/sai-reddivari/financial-sector-hedging.git`. The audit checks the local and remote tag again.
- Frozen environment SHA-256: `18f8a8d16710d647f243be2c597265647d0b74b46a13f37fe0512df9070e19d4`. Python 3.14.8, macOS 26.6 arm64, 57 pinned distributions; no installations/upgrades.
- New audit products: `docs/EXPERIMENTS.md`, this report, `env/manifest_runtime_environment.json`, `scripts/freeze_phase0.py`, `scripts/audit_phase0.py`, `results/manifest_pre_refactor.json`, and preserved logs/outputs under `results/pre_refactor/`.
- Two notebook-generated timestamped result directories remain at their original fresh destinations under `results/`; their complete products are hashed by the manifest. Original notebooks were also copied byte-for-byte into `results/pre_refactor/notebooks/as_committed/` before fresh-kernel attempts.

The initially combined push command was rejected by automatic approval review on authorization grounds. The explicit attached instruction to “Push main and the tag to origin” was then verified, and the exact non-force push succeeded. No approval remains blocked.

Actual successful push output:

```text
To https://github.com/sai-reddivari/financial-sector-hedging.git
   71c0be1..a96d992  main -> main
 * [new tag]         pre-refactor -> pre-refactor
```

## Executed commands and results

All commands used the captured `.venv`. The first full canonical pass set OMP/MKL/OpenBLAS thread counts to one. Inspection identified Apple Accelerate; the second full canonical pass and all subsequent commands additionally set `VECLIB_MAXIMUM_THREADS=1`. Both passes are retained. `PYTHONHASHSEED=0` is fixed for all runs. No research seed changed.

The commands actually executed are listed verbatim in each manifest entry; each log contains complete stdout/stderr, including failures. `scripts/freeze_phase0.py` was invoked in this order: `initialize`, `canonical`, `canonical-pinned`, `notebooks`, `reviewers`, `ancillary`. Publication utilities execute their original code in disposable `git archive pre-refactor` workspaces so their fixed report destinations cannot replace frozen evidence.

| Entry | Status | Exit | Measured seconds | Log |
|---|---|---:|---:|---|
| `controlled_release` | passed | 0 | 17.022 | [`controlled_release.txt`](../results/pre_refactor/logs/controlled_release.txt) |
| `model_replay` | passed | 0 | 1.785 | [`model_replay.txt`](../results/pre_refactor/logs/model_replay.txt) |
| `price_risk` | passed | 0 | 2.976 | [`price_risk.txt`](../results/pre_refactor/logs/price_risk.txt) |
| `price_risk_original_three` | passed | 0 | 3.884 | [`price_risk_original_three.txt`](../results/pre_refactor/logs/price_risk_original_three.txt) |
| `incremental_features_original` | passed | 0 | 4.524 | [`incremental_features_original.txt`](../results/pre_refactor/logs/incremental_features_original.txt) |
| `incremental_features` | passed | 0 | 5.480 | [`incremental_features.txt`](../results/pre_refactor/logs/incremental_features.txt) |
| `conditional_breadth` | passed | 0 | 27.872 | [`conditional_breadth.txt`](../results/pre_refactor/logs/conditional_breadth.txt) |
| `equity_overlays_freeze` | passed | 0 | 65.487 | [`equity_overlays_freeze.txt`](../results/pre_refactor/logs/equity_overlays_freeze.txt) |
| `equity_overlays` | passed | 0 | 97.927 | [`equity_overlays.txt`](../results/pre_refactor/logs/equity_overlays.txt) |
| `controlled_release_accelerate_pinned` | passed | 0 | 8.762 | [`controlled_release_accelerate_pinned.txt`](../results/pre_refactor/logs/controlled_release_accelerate_pinned.txt) |
| `model_replay_accelerate_pinned` | passed | 0 | 1.855 | [`model_replay_accelerate_pinned.txt`](../results/pre_refactor/logs/model_replay_accelerate_pinned.txt) |
| `price_risk_accelerate_pinned` | passed | 0 | 3.623 | [`price_risk_accelerate_pinned.txt`](../results/pre_refactor/logs/price_risk_accelerate_pinned.txt) |
| `price_risk_original_three_accelerate_pinned` | passed | 0 | 2.900 | [`price_risk_original_three_accelerate_pinned.txt`](../results/pre_refactor/logs/price_risk_original_three_accelerate_pinned.txt) |
| `incremental_features_original_accelerate_pinned` | passed | 0 | 2.607 | [`incremental_features_original_accelerate_pinned.txt`](../results/pre_refactor/logs/incremental_features_original_accelerate_pinned.txt) |
| `incremental_features_accelerate_pinned` | passed | 0 | 5.554 | [`incremental_features_accelerate_pinned.txt`](../results/pre_refactor/logs/incremental_features_accelerate_pinned.txt) |
| `conditional_breadth_accelerate_pinned` | passed | 0 | 27.112 | [`conditional_breadth_accelerate_pinned.txt`](../results/pre_refactor/logs/conditional_breadth_accelerate_pinned.txt) |
| `equity_overlays_freeze_accelerate_pinned` | passed | 0 | 62.347 | [`equity_overlays_freeze_accelerate_pinned.txt`](../results/pre_refactor/logs/equity_overlays_freeze_accelerate_pinned.txt) |
| `equity_overlays_accelerate_pinned` | passed | 0 | 106.841 | [`equity_overlays_accelerate_pinned.txt`](../results/pre_refactor/logs/equity_overlays_accelerate_pinned.txt) |
| `notebook_00_study_setup` | failed | 1 | 3.424 | [`notebook_00_study_setup.txt`](../results/pre_refactor/logs/notebook_00_study_setup.txt) |
| `notebook_01_single_option_ledger` | passed | 0 | 2.317 | [`notebook_01_single_option_ledger.txt`](../results/pre_refactor/logs/notebook_01_single_option_ledger.txt) |
| `notebook_02_three_name_portfolio` | passed | 0 | 2.670 | [`notebook_02_three_name_portfolio.txt`](../results/pre_refactor/logs/notebook_02_three_name_portfolio.txt) |
| `notebook_03_cost_and_volatility_sensitivity` | passed | 0 | 4.208 | [`notebook_03_cost_and_volatility_sensitivity.txt`](../results/pre_refactor/logs/notebook_03_cost_and_volatility_sensitivity.txt) |
| `notebook_04_policy_selection_research` | passed | 0 | 1.741 | [`notebook_04_policy_selection_research.txt`](../results/pre_refactor/logs/notebook_04_policy_selection_research.txt) |
| `notebook_05_model_contract_replay` | passed | 0 | 2.894 | [`notebook_05_model_contract_replay.txt`](../results/pre_refactor/logs/notebook_05_model_contract_replay.txt) |
| `notebook_06_market_risk_models` | passed | 0 | 4.001 | [`notebook_06_market_risk_models.txt`](../results/pre_refactor/logs/notebook_06_market_risk_models.txt) |
| `notebook_07_equity_overlay_study` | passed | 0 | 2.087 | [`notebook_07_equity_overlay_study.txt`](../results/pre_refactor/logs/notebook_07_equity_overlay_study.txt) |
| `notebook_08_breadth_and_composition` | passed | 0 | 2.149 | [`notebook_08_breadth_and_composition.txt`](../results/pre_refactor/logs/notebook_08_breadth_and_composition.txt) |
| `notebook_09_release_aware_features` | passed | 0 | 5.654 | [`notebook_09_release_aware_features.txt`](../results/pre_refactor/logs/notebook_09_release_aware_features.txt) |
| `notebook_MonteCarlo_Accuracy_ComputingCost` | passed | 0 | 29.648 | [`notebook_MonteCarlo_Accuracy_ComputingCost.txt`](../results/pre_refactor/logs/notebook_MonteCarlo_Accuracy_ComputingCost.txt) |
| `notebook_MonteCarlo_EstimatingGreeks` | passed | 0 | 17.638 | [`notebook_MonteCarlo_EstimatingGreeks.txt`](../results/pre_refactor/logs/notebook_MonteCarlo_EstimatingGreeks.txt) |
| `notebook_MonteCarlo_ModelIntroduction` | passed | 0 | 0.806 | [`notebook_MonteCarlo_ModelIntroduction.txt`](../results/pre_refactor/logs/notebook_MonteCarlo_ModelIntroduction.txt) |
| `notebook_MonteCarlo_PathDependency_HedgeControls` | passed | 0 | 33.715 | [`notebook_MonteCarlo_PathDependency_HedgeControls.txt`](../results/pre_refactor/logs/notebook_MonteCarlo_PathDependency_HedgeControls.txt) |
| `notebook_MonteCarlo_StochasticVolatility` | passed | 0 | 55.866 | [`notebook_MonteCarlo_StochasticVolatility.txt`](../results/pre_refactor/logs/notebook_MonteCarlo_StochasticVolatility.txt) |
| `independent_accounting` | passed | 0 | 1.145 | [`independent_accounting.txt`](../results/pre_refactor/logs/independent_accounting.txt) |
| `independent_statistics` | passed | 0 | 0.445 | [`independent_statistics.txt`](../results/pre_refactor/logs/independent_statistics.txt) |
| `window_placement` | passed | 0 | 73.583 | [`window_placement.txt`](../results/pre_refactor/logs/window_placement.txt) |
| `owner_checks` | passed | 0 | 1.364 | [`owner_checks.txt`](../results/pre_refactor/logs/owner_checks.txt) |
| `owner_window_check` | passed | 0 | 0.297 | [`owner_window_check.txt`](../results/pre_refactor/logs/owner_window_check.txt) |
| `publication_verify` | passed | 0 | 1.253 | [`publication_verify.txt`](../results/pre_refactor/logs/publication_verify.txt) |
| `publication_status` | passed | 0 | 1.085 | [`publication_status.txt`](../results/pre_refactor/logs/publication_status.txt) |
| `publication_package` | passed | 1 | 0.875 | [`publication_package.txt`](../results/pre_refactor/logs/publication_package.txt) |
| `existing_test_suite` | passed | 0 | 68.588 | [`existing_test_suite.txt`](../results/pre_refactor/logs/existing_test_suite.txt) |
| `study_notebook_launcher` | failed | 1 | 2.457 | [`study_notebook_launcher.txt`](../results/pre_refactor/logs/study_notebook_launcher.txt) |
| `fragment_MonteCarloSeeded_OneStepExact` | passed | 0 | 0.040 | [`fragment_MonteCarloSeeded_OneStepExact.txt`](../results/pre_refactor/logs/fragment_MonteCarloSeeded_OneStepExact.txt) |
| `fragment_MonteCarlo_EulerPathwayGeneration` | passed | 0 | 0.021 | [`fragment_MonteCarlo_EulerPathwayGeneration.txt`](../results/pre_refactor/logs/fragment_MonteCarlo_EulerPathwayGeneration.txt) |
| `fragment_MonteCarlo_ExactPathwayGeneration` | passed | 0 | 0.020 | [`fragment_MonteCarlo_ExactPathwayGeneration.txt`](../results/pre_refactor/logs/fragment_MonteCarlo_ExactPathwayGeneration.txt) |
| `fragment_MonteCarlo_MethodComparison` | failed | 1 | 0.039 | [`fragment_MonteCarlo_MethodComparison.txt`](../results/pre_refactor/logs/fragment_MonteCarlo_MethodComparison.txt) |
| `fragment_MonteCarlo_MilsteinPathwayGeneration` | passed | 0 | 0.021 | [`fragment_MonteCarlo_MilsteinPathwayGeneration.txt`](../results/pre_refactor/logs/fragment_MonteCarlo_MilsteinPathwayGeneration.txt) |
| `fragment_MonteCarlo_OneStepExactPrices` | failed | 1 | 0.036 | [`fragment_MonteCarlo_OneStepExactPrices.txt`](../results/pre_refactor/logs/fragment_MonteCarlo_OneStepExactPrices.txt) |
| `audit_market_data` | hash-only | — | not run | saved products hashed |
| `fetch_core_prices` | hash-only | — | not run | saved products hashed |
| `audit_reference_data` | hash-only | — | not run | saved products hashed |
| `fetch_financial_universe` | hash-only | — | not run | saved products hashed |
| `audit_research_features` | hash-only | — | not run | saved products hashed |
| `extend_sec_core10` | hash-only | — | not run | saved products hashed |

Total measured child-command time: 768.645 seconds (not total human/audit wall time). Status counts: `{"failed": 4, "hash-only": 6, "passed": 45}`. Packaging exit 1 is the explicitly expected overwrite refusal, not a successful new packaging operation.

## Frozen evidence and numerical comparisons

- Findings-bundle and nested evidence identity checks: **482 checked; 0 mismatches**. Both the findings-folder copies and original result archives are checked.
- Fully Accelerate-pinned canonical pass: **94 CSV tables; 1,870,832 numeric cells; 0 differing tables; 94 byte-identical tables**.
- All comparisons, including the initial pass and reviewer outputs: **210 tables; 5,030,792 numeric cells; 0 differing tables**.
- JSON comparisons: **70 files; 11,184 numeric values; 0 numerical mismatches**. Added provenance keys, timestamps/hash strings, one observational runtime and a supplemental notebook-execution record not produced by the economic CLI are listed explicitly in `json_comparisons.json`.
- Original tracked identities checked after execution: **705; 0 changed**.
- Publication inventory: **286 numeric literal occurrences** plus **59 number-word occurrences**, retaining exact text and source locations. This includes dates and link identifiers. Numerical contracts retain full-precision saved summary/window-table values, not just rounded prose.
- Economic publication display checks: **81; 1 discrepancies**. Their per-number display precision is recorded separately from deterministic replay tolerance.

CSV comparisons check every cell and preserve row/column order, text and missingness. Deterministic relative tolerance is `1e-9`, absolute tolerance zero. No tolerance was relaxed to hide a mismatch. Full output-file hashes, including timestamp-sensitive protocol/report/JSON hashes, remain in the manifest. Timing and metadata differences do not imply an economic result changed.

Full-precision reproduced controlled results:

| Policy | ES95 dollars | Mean financed stock cost dollars |
|---|---:|---:|
| maturity_band_050 | 3327.944637142751 | 487.971370748886 |
| daily | 3326.045893370304 | 545.691316293726 |
| weekly | 6242.903532379895 | 336.134181024787 |

The selected-minus-weekly ES95 estimate remains `-2914.958895237145`, paired interval `[-3100.6926138820118, -2710.425377174788]`; selected-minus-daily remains `1.898743772447233`, interval `[-31.61428212326467, 33.56382311508891]`. These do not establish incremental historical economic hedge value.

## Findings and explicit limits

- **JSON structure/provenance difference (`controlled_release`, `results/research-release-1/release-1/protocol_commitment.json`):** 0 numeric mismatches, 0 boolean differences, 1 structural differences. The current frozen source records additional module/input provenance that was absent when the historical run was saved. Added keys and raw string changes are retained in the JSON comparison report. No saved metadata was altered.
- **JSON structure/provenance difference (`controlled_release`, `results/research-release-1/release-1/provenance.json`):** 0 numeric mismatches, 0 boolean differences, 2 structural differences. The current frozen source records additional module/input provenance that was absent when the historical run was saved. Added keys and raw string changes are retained in the JSON comparison report. No saved metadata was altered.
- **JSON structure/provenance difference (`price_risk_original_three`, `results/risk-research-20261106T014645390937Z/manifest.json`):** 0 numeric mismatches, 0 boolean differences, 1 structural differences. The current frozen source records additional module/input provenance that was absent when the historical run was saved. Added keys and raw string changes are retained in the JSON comparison report. No saved metadata was altered.
- **JSON structure/provenance difference (`price_risk_original_three`, `results/risk-research-20261106T014645390937Z/protocol.json`):** 0 numeric mismatches, 0 boolean differences, 1 structural differences. The current frozen source records additional module/input provenance that was absent when the historical run was saved. Added keys and raw string changes are retained in the JSON comparison report. No saved metadata was altered.
- **JSON structure/provenance difference (`equity_overlays`, `results/equity-overlays-20261106T023430248130Z/notebook_execution.json`):** 0 numeric mismatches, 0 boolean differences, 1 structural differences. The supplemental `notebook_execution.json` was not generated by the economic CLI; notebook 07 was executed separately and its fresh copy/log are retained.
- **JSON structure/provenance difference (`controlled_release_accelerate_pinned`, `results/research-release-1/release-1/protocol_commitment.json`):** 0 numeric mismatches, 0 boolean differences, 1 structural differences. The current frozen source records additional module/input provenance that was absent when the historical run was saved. Added keys and raw string changes are retained in the JSON comparison report. No saved metadata was altered.
- **JSON structure/provenance difference (`controlled_release_accelerate_pinned`, `results/research-release-1/release-1/provenance.json`):** 0 numeric mismatches, 0 boolean differences, 2 structural differences. The current frozen source records additional module/input provenance that was absent when the historical run was saved. Added keys and raw string changes are retained in the JSON comparison report. No saved metadata was altered.
- **JSON structure/provenance difference (`price_risk_original_three_accelerate_pinned`, `results/risk-research-20261106T014645390937Z/manifest.json`):** 0 numeric mismatches, 0 boolean differences, 1 structural differences. The current frozen source records additional module/input provenance that was absent when the historical run was saved. Added keys and raw string changes are retained in the JSON comparison report. No saved metadata was altered.
- **JSON structure/provenance difference (`price_risk_original_three_accelerate_pinned`, `results/risk-research-20261106T014645390937Z/protocol.json`):** 0 numeric mismatches, 0 boolean differences, 1 structural differences. The current frozen source records additional module/input provenance that was absent when the historical run was saved. Added keys and raw string changes are retained in the JSON comparison report. No saved metadata was altered.
- **JSON structure/provenance difference (`equity_overlays_accelerate_pinned`, `results/equity-overlays-20261106T023430248130Z/notebook_execution.json`):** 0 numeric mismatches, 0 boolean differences, 1 structural differences. The supplemental `notebook_execution.json` was not generated by the economic CLI; notebook 07 was executed separately and its fresh copy/log are retained.
- **`notebook_00_study_setup` failed as saved:** ; NameError: name 'Book' is not defined; . Full log: `results/pre_refactor/logs/notebook_00_study_setup.txt`. No repair was attempted in Phase 0.
- **`study_notebook_launcher` failed as saved:** ; NameError: name 'Book' is not defined; . Full log: `results/pre_refactor/logs/study_notebook_launcher.txt`. No repair was attempted in Phase 0.
- **`fragment_MonteCarlo_MethodComparison` failed as saved:**     SCHEMES = {'euler': euler_paths, 'milstein': milstein_paths, 'exact': exact_paths};                         ^^^^^^^^^^^; NameError: name 'euler_paths' is not defined. Full log: `results/pre_refactor/logs/fragment_MonteCarlo_MethodComparison.txt`. No repair was attempted in Phase 0.
- **`fragment_MonteCarlo_OneStepExactPrices` failed as saved:**     random_number = np.random.default_rng(SEED);                     ^^; NameError: name 'np' is not defined. Full log: `results/pre_refactor/logs/fragment_MonteCarlo_OneStepExactPrices.txt`. No repair was attempted in Phase 0.
- **Existing publication rounding discrepancy:** `maturity_band_050 loss_es95` prints `3327.95`, while the unchanged frozen CSV and both replays give `3327.944637142751`. Direct rounding to cents is `3327.94`; the printed `3327.95` is outside its half-cent rounding interval. The original three-decimal report prints `3327.945`, so double rounding is a possible explanation, not an established correction. Both values are recorded; no document or result was edited.
- **Historical source unavailable: `results/equity-overlays-20261106T020955456052Z`.** Earlier development run: recorded source SHA differs from the available frozen implementation; that historical source version is not separately supplied, so rerunning it exactly would require reconstructing/changing code. Saved products are hashed, never replaced. The manifest lists 2 recorded source-hash differences; original artifacts were not modified.
- **Historical source unavailable: `results/feature-research-20261106T020600619286Z`.** Earlier development run: recorded source SHA differs from the available frozen implementation; that historical source version is not separately supplied, so rerunning it exactly would require reconstructing/changing code. Saved products are hashed, never replaced. The manifest lists 2 recorded source-hash differences; original artifacts were not modified.

Six acquisition utilities are explicitly `hash-only`: frozen historical vendor/SEC snapshots cannot be recreated by a present live refresh without possible revisions, new retrieval metadata, credentials and entitlements. No refresh was attempted and no credentials were copied to evidence. The complete saved products are hashed, and the economic runs consume them unchanged. This does not verify raw-provider accuracy or recover unavailable historical option quotes or membership vintages.

Earlier development result directories are inventoried individually in `historical_saved_runs`, including incomplete attempts and recorded source hashes that differ from the available final source. Those unavailable historical source versions were not reconstructed or rerun. Their saved products remain byte-identical. This limitation is separate from the seven canonical publication families, which were fully replayed. Original three-name price-risk outputs were also reproduced byte-for-byte despite their older runner hash.

Original investigation wall-clock timings and plot/notebook metadata are not deterministic quantities. Their saved artifacts and fresh attempts are preserved. The manifest distinguishes successful fresh-kernel execution, partial failures, timeout/hash-only entries and read-only notebook views. No fresh environment/clean-clone reproduction, package restructuring, methodology improvement, new tests, license choice or Phase 1 implementation is claimed.

## Existing test suite: actual output

Command: `.venv/bin/python -m pytest -q --junitxml=results/pre_refactor/tests.xml` with the fully pinned runtime controls above.

```text
................................................................... [ 34%]
........................................................................ [ 71%]
....................................................... [100%]
=============================== warnings summary ===============================
tests/test_market_data.py: 16 warnings
tests/test_overlays.py: 4 warnings
tests/test_research_features.py: 8 warnings
  /Users/saireddivari/MonteCarloEvaluations/.venv/lib/python3.14/site-packages/pandas/core/series.py:848: Pandas4Warning: Series.values returning an ndarray that drops timezone information for DatetimeTZDtype is deprecated. In a future version, this will return the underlying DatetimeArray instead. Use 'Series.dt.tz_convert(None).to_numpy()' to get a NumPy array of UTC values, or 'Series.array' to get the ExtensionArray.
  See https://pandas.pydata.org/docs/dev/whatsnew/v3.1.0.html#whatsnew-310-deprecations-values for more details.
    warnings.warn(

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
194 passed, 28 warnings, 22 subtests passed in 68.11s (0:01:08)
```

## Audit command output

```text
{
  "status": "phase0_complete_with_findings",
  "execution_counts": {
    "passed": 45,
    "failed": 4,
    "hash-only": 6
  },
  "evidence_checks": 482,
  "evidence_mismatches": 0,
  "tables_compared": 210,
  "tables_with_differences": 0,
  "numeric_cells_compared": 5030792,
  "original_tracked_file_changes": 0
}
```

The Phase 0 boundary is the stopping point. The owner must confirm before `refactor/publication` is created or Phase 1 begins.

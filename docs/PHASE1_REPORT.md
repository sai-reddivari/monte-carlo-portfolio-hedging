# Phase 1 publication refactor report

Phase 0's provenance differences were changes in metadata coverage, not changes in economic values: the controlled release's current provenance enumerated four later-added modules (`breadth`, `feature_models`, `overlays`, `study`) absent from its historical record; the original three-name risk runner additionally recorded input-metadata hashes; fresh timestamps, absolute paths and dependent hashes changed; and the economic overlay CLI did not emit the supplemental notebook-execution record. The historical records remain byte-identical. Historical source identity is verified against the immutable tag, while current executed source identities and numerical output comparisons are recorded separately. Phase 0 CSV comparisons and JSON numeric comparisons had zero numerical mismatches; expanded post-freeze display rounding errata are recorded separately.

Status: Phase 1 complete with the explicit historical/data limitations below. No new economic conclusion, strategy, tuning or empirical certification is claimed.

## Changes and reviewable commits

The two required main-branch additions were committed before the branch was created: `1acbe20` preserves both provenance ledgers byte-for-byte, and `e8c3e4d` records all three display errata without editing frozen documents. Work then proceeded on `refactor/publication`, without amendments or squashing.

- `e738c3f`: separate pricing/domain/loading/simulation/hedging/evaluation/reporting interfaces; extracted function/class ASTs unchanged; existing 194 tests plus 22 subtests passed; 94 CSVs byte-identical.
- `33f5961`: package research runners and versioned forecast/breadth/replay/ridge defaults; all 94 CSVs still byte-identical.
- `a450572`: notebook package calls, shared investigation setup, notebook00 import/input repair, explicit legacy arguments; original executed notebooks untouched. Original snippet statements match the package functions with identical explicit inputs. CRR implementation was absent and remains a required callable dependency.
- `c071e08`: exact runtime/wheel locks, real fast-subset regression, known-value Greeks, Makefile and CI, license/citation metadata.
- `0b2ecc6`: byte-preserved document moves and compatibility links, README, future work and explicit exclusions; index-only removal of raw vendor/SEC snapshots, without deleting local bytes or altering the immutable tag/history.

CHANGELOG maps all implementation/document paths. Only requested README/EXPERIMENTS content was rewritten; existing research/finding documents retain exact bytes. The frozen summary's conclusion is verbatim in README. All original results/reports and all fifteen source-notebook backups retain their hashes. 547 original output/document identities were checked unchanged.

During validation, temporary-output path handling, archived-test discovery, a worker import and JSON integer-map key types were corrected. These were execution/configuration plumbing failures; no discrepant numerical result was accepted or silently reconciled. The final stochastic controls preserve the original integer keys. No packages were upgraded.

## Full-precision manifest comparison: actual output

Command: `.venv/bin/python scripts/diff_manifests.py`

```text
{
  "experiments": 8,
  "full_precision_contract_values": 197077,
  "csv_tables": 94,
  "csv_numeric_cells": 1870832,
  "relative_tolerance": 1e-09,
  "absolute_tolerance": 0,
  "mismatches": 0,
  "passed": true
}
```

All 94 research CSVs are also byte-identical, and 24 breadth NPZ outcome archives are byte-identical. The 197,077 contract values exclude duplicated large prediction tables; those tables are nevertheless compared cell-by-cell as part of all 1,870,832 CSV numeric cells. The publication's rounded literals remain frozen, with the three differences recorded in `docs/review/errata_post_freeze.md`. The pre-refactor manifest was not rewritten.

Reviewer reproduction: 11 tables, 107,226 numeric cells, zero differences. Independent accounting reconstructs the original 2,013 outcomes without production valuation/accounting calls. Statistical/collar reconstructions reproduce the original diagnostics. The shifted-window diagnostic uses the current engine with ROOT/OUT redirection only; its historical source checks concern the frozen tag, while actual current source hashes are separately recorded in the post manifest.

## Clean clone and fresh environment: executed

- Clean local clone: `/tmp/hedging-publication-clean-clone`; tested source commit `0b2ecc66b725ea80c19faa994c658d0e8b6da139`. The clone initially had no `data/market` directory.
- Fresh environment: `/tmp/hedging-publication-clean-env`, Python 3.14.8 on macOS 26.6 ARM64. All 57 normalized distribution/version pins match `env/frozen_environment.txt`. `pip check` reports no broken requirements.
- Install: `python3 -m venv /tmp/hedging-publication-clean-env`, followed by `/tmp/hedging-publication-clean-env/bin/python -m pip install --no-index --find-links /tmp/hedging-frozen-wheels --require-hashes --no-deps -r env/requirements-macos-arm64.lock`. The wheel cache was downloaded at the exact frozen versions; no upgrade occurred.
- From the clean clone: `make reproduce PYTHON=/tmp/hedging-publication-clean-env/bin/python`.
- Actual elapsed wall time: **480.35 seconds**. All four native thread controls equal one, `PYTHONHASHSEED=0`, Matplotlib Agg.
- The command restored exact missing input bytes from the immutable tag, exported study-input views, ran all eight research variants, all ten study and five investigation notebook views, independent accounting/statistics and current-engine shifted windows, regenerated the post manifest, and passed the manifest diff.
- Full stdout/stderr and timing: `results/post_refactor/clean_clone_reproduction.txt`; stage logs and reviewer comparisons are retained alongside it. Post-execution evidence/report commits add records only; numerical source files are byte-identical to the tested clone.

## Existing and new tests: actual runner output

Command: `OMP_NUM_THREADS=1 MKL_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 VECLIB_MAXIMUM_THREADS=1 PYTHONHASHSEED=0 MPLBACKEND=Agg MPLCONFIGDIR=/tmp/phase1-mpl .venv/bin/python -m pytest -q --junitxml=results/post_refactor/tests.xml`

```text
................................................................... [ 33%]
........................................................................ [ 70%]
...........................................................                                                                     [100%]
=============================== warnings summary ===============================
tests/test_market_data.py: 16 warnings
tests/test_overlays.py: 4 warnings
tests/test_research_features.py: 8 warnings
  /Users/saireddivari/MonteCarloEvaluations/.venv/lib/python3.14/site-packages/pandas/core/series.py:848: Pandas4Warning: Series.values returning an ndarray that drops timezone information for DatetimeTZDtype is deprecated. In a future version, this will return the underlying DatetimeArray instead. Use 'Series.dt.tz_convert(None).to_numpy()' to get a NumPy array of UTC values, or 'Series.array' to get the ExtensionArray.
  See https://pandas.pydata.org/docs/dev/whatsnew/v3.1.0.html#whatsnew-310-deprecations-values for more details.
    warnings.warn(

tests/test_publication_regression.py::test_method_snippet_requires_and_uses_explicit_missing_crr_dependency
tests/test_publication_regression.py::test_method_snippet_requires_and_uses_explicit_missing_crr_dependency
  frozen-method-comparison:44: Pandas4Warning: 'str' is not supported as a fill value for float64 dtype. In a future version, calling fillna with an incompatible value will raise. Explicitly cast to a common dtype before filling.

tests/test_publication_regression.py::test_method_snippet_requires_and_uses_explicit_missing_crr_dependency
tests/test_publication_regression.py::test_method_snippet_requires_and_uses_explicit_missing_crr_dependency
  /Users/saireddivari/MonteCarloEvaluations/hedging_harness/legacy_methods.py:93: Pandas4Warning: 'str' is not supported as a fill value for float64 dtype. In a future version, calling fillna with an incompatible value will raise. Explicitly cast to a common dtype before filling.
    routes.round(4).fillna('–')                       # display copy only; routes itself keeps its numbers

tests/test_publication_regression.py: 43 warnings
  /Users/saireddivari/MonteCarloEvaluations/scripts/audit_phase0.py:75: Pandas4Warning: The 'float_precision' argument is deprecated. Use the default float precision instead.
    a = pd.read_csv(original, float_precision='round_trip')

tests/test_publication_regression.py: 43 warnings
  /Users/saireddivari/MonteCarloEvaluations/scripts/audit_phase0.py:76: Pandas4Warning: The 'float_precision' argument is deprecated. Use the default float precision instead.
    b = pd.read_csv(reproduced, float_precision='round_trip')

tests/test_publication_regression.py: 42 warnings
  /Users/saireddivari/MonteCarloEvaluations/scripts/audit_phase0.py:118: Pandas4Warning: The 'float_precision' argument is deprecated. Use the default float precision instead.
    frame = pd.read_csv(path, float_precision='round_trip')

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
198 passed, 160 warnings, 22 subtests passed in 112.95s (0:01:52)
```

The original cost and hand-accounting tests remain. New tests check known call/put/Greek values, raw legacy-statement equivalence with explicit dependencies, and an actual three-experiment frozen-seed regression (well under ten minutes). Test discovery is restricted to owned `tests/`, not archived copies. GitHub Actions is configured; hosted execution was not observed and is not claimed.

## Explicit limitations and preserved findings

- The two superseded directories and all six acquisition utilities have individual **hash-only, not reproducible from current code** entries in EXPERIMENTS and a README Limitations line. Historical code was not reconstructed; present live queries were not substituted for old snapshots.
- Clean-checkout bundle verification is **47 of 48**. The only absent entry is ignored `frozen_package_and_review_evidence/.DS_Store`; there are zero hash mismatches among the 47 available entries. Neither the bundle manifest nor frozen documents was changed to hide that gap.
- Every one of the 33 historical overlay policies has zero recorded ledger borrowing across 2,013 outcomes because short proceeds are included as cash; usable liquidity is not modelled. This does not describe the different controlled short-call account, which reports borrowing.
- Vendor snapshot redistribution rights remain unverified. They are excluded from current-tree tracking but remain in the immutable historical tag and local files. MIT applies to project software, not third-party data or material. No history rewrite, data purchase or public-data-rights certification occurred.
- `compare_methods` requires the missing original CRR callable explicitly. No replacement implementation or new pricing experiment was invented; the other method results are tested against original statements with the same supplied dependency.
- Original window/quote/survivorship/financing limitations and the conclusion that incremental economic hedge value remains unestablished are unchanged. Reproduction uses already exposed data and creates no new untouched test.
- Unrelated `scratch/Astra Design Rationale.md` was left untouched and untracked.

Phase 1 ends here. The refactor branch is not merged into main.

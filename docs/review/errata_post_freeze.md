# Post-freeze display errata

These are display-rounding differences. Frozen raw results and frozen publication documents are preserved. No conclusion changes: incremental economic hedge value remains unestablished.

| Printed value | Full-precision frozen/reproduced value | Direct rounding | Files containing the printed value |
|---|---:|---:|---|
| 3,327.95 | 3327.944637142751 | 3,327.94 | `README.md` at the Phase 0 checkpoint; `docs/Final Findings and Takeaways/research_release_2_publication.md` line 23; its archived publication snapshot under `docs/Final Findings and Takeaways/frozen_package_and_review_evidence/release-2/snapshots/docs/research_release_2_publication.md`; the duplicate under `results/research-release-2/release-2/snapshots/docs/research_release_2_publication.md` |
| 4.096 (validation, offset 21) | 4.095485201507027 | 4.095 | `docs/Final Findings and Takeaways/research_release_2_claims_and_errata.md` line 85 and its two archived snapshot copies; `results/research-release-2/astra-review-20261106/window_placement/summary.txt` and its findings-bundle copy |
| -0.230 (validation, offset 42) | -0.23052718796931604 | -0.231 | `docs/Final Findings and Takeaways/research_release_2_publication.md` line 80; `research_release_2_claims_and_errata.md` line 85 and their archived snapshot copies; `results/research-release-2/astra-review-20261106/window_placement/summary.txt` and its findings-bundle copy |

Selected ES95 comes from `results/research-release-1/release-1/evaluation_metrics.csv`, policy `maturity_band_050`, column `loss_es95`. Shifted-window values come from `results/research-release-2/astra-review-20261106/window_placement/comparisons.csv`, validation, `long_put_k90_b2`, column `es_reduction_vs_reduced75`, offsets 21 and 42. Phase 0 reproduced those full-precision values. The manifests retain full precision; publication displays use rounded values. These three displays do not equal direct rounding of the raw numbers. Possible intermediate rounding is not treated as an established correction.

Paths above identify files at the main-branch Phase 0 checkpoint. Phase 1 moves are mapped in CHANGELOG; this errata and the frozen documents are not rewritten during those moves.

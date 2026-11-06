# Changes

## Publication layout - November 2026

- Reframe the project as Monte Carlo option hedging applied to an equity portfolio.
- Consolidate the repository into `src`, `notebooks`, `tests`, `docs`, `config`, `data` and `results`.
- Remove internal handoffs, reviews, refactor reports, duplicate release bundles and documentation symlinks.
- Restore executable experiment steps to the notebooks; retain shared mathematics in the package.
- Retain canonical experiments and numerical baselines; remove superseded runs and duplicate working copies from the current tree.
- Add a research paper authored in LaTeX, figures built from saved results and a narrative README.
- Move independent numerical validation and its reference tables under `tests`.
- Remove GitHub Actions and personal editor configuration as requested.

Numerical experiment settings are unchanged. Historical paths, intermediate runs and earlier documentation remain available in Git history. The `pre-refactor` tag remains the exact input checkpoint used for reproduction.

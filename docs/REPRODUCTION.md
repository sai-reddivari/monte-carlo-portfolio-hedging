# Reproducing the study

The public figures read saved aggregate tables. Full experiment reproduction additionally needs the exact historical inputs retained in the `pre-refactor` Git tag. Both workflows are available; a fresh live download is not an equivalent input snapshot.

## Environment

The recorded environment is Python 3.14.8 on macOS ARM64. Install `requirements.lock` into a virtual environment. The Makefile sets `PYTHONPATH=src`, single-thread OMP/MKL/OpenBLAS/Accelerate controls, `PYTHONHASHSEED=0` and a noninteractive plotting backend. Other platforms can differ in low-order floating-point results; the dependency lock is not a claim of universal binary compatibility.

```sh
python3.14 -m venv .venv
.venv/bin/python -m pip install -r requirements.lock
make figures
make test
make reproduce
make diff
```

`make test` restores missing inputs, then runs the tests. Changed existing inputs are rejected rather than overwritten. Its numerical regression runs the controlled hedge selection, historical model-contract replay and ten-name risk forecasts into temporary directories.

`make reproduce` runs all eight research variants, the study and numerical-method notebooks, and independent accounting/statistical/window-placement validation. It writes fresh outputs beneath the ignored `results/reproduction/` directory and updates `results/manifest_post_refactor.json`. It compares CSV schema, row identities, numeric cells and missingness with the saved experiments. Deterministic numeric comparisons use relative tolerance `1e-9` and zero absolute tolerance. Runtime, timestamps and source hashes are reported separately.

The required tag is `pre-refactor` at `a96d99210ea16ac2dd33f46623aaf96cbc563196`. The pipeline verifies its identity before extracting a disposable historical workspace. It does not need API credentials or network acquisition. Data provenance and redistribution limits are in [the data guide](../data/README.md).

## Experiment commands

Run from the repository root with `PYTHONPATH=src`. In the table, `P` means `.venv/bin/python` and `OUT` is a new output directory. Research parameters are read from `config/`; no parameter reselection is performed on historical test outcomes.

| Experiment | Command |
|---|---|
| Controlled short-call hedging | `P src/commands/run_research_release_1.py --output-dir OUT` |
| Historical model-contract replay | `P src/commands/run_model_contract_replay.py --output-dir OUT` |
| Original three-name price forecasts | `P src/commands/run_risk_research.py --output-dir OUT` |
| Ten-name price forecasts | `P src/commands/run_risk_research.py --prices data/market/prices_core_10.csv --output-dir OUT` |
| Original financial-feature cohorts | `P src/commands/run_feature_research.py --output-dir OUT` |
| Ten-name/six-bank financial features | `P src/commands/run_feature_research.py --sec-core10 --output-dir OUT` |
| Breadth and composition | `P src/commands/run_breadth_research.py --output-dir OUT` |
| Equity overlay selection | `P src/commands/run_overlay_research.py freeze --output-dir OUT` |
| Equity overlay evaluation | `P src/commands/run_overlay_research.py evaluate --run-dir OUT` |

The last two commands are sequential phases of one experiment. The eight variants usually take several minutes in total; notebook timing depends on hardware, and some numerical investigations are more expensive. The complete run records its measured runtimes.

## Notebooks and numerical validation

The notebook files contain their explanations and executable experiment steps. Reusable pricing, accounting and simulation functions remain in `src/`. To execute just the numbered study notebooks in fresh kernels:

```sh
PYTHONPATH=src .venv/bin/python src/commands/run_harness_notebooks.py --output-dir results/reproduction/notebook-check
```

The full reproduction also runs the `MonteCarlo_*.ipynb` numerical-method investigations. Outputs are saved separately; execution does not replace source notebooks.

Independent validation code is in [tests/validation](../tests/validation/), with reference tables in [tests/artifacts](../tests/artifacts/). Accounting and statistical checks use the verified historical workspace; the window-placement diagnostic uses the current overlay engine against verified historical inputs. Missing reference tables fail explicitly. `make verify` checks the saved validation fixtures against their recorded hashes.

## Figures and paper

`make figures` runs `src/commands/build_exhibits.py`. It reads saved CSVs and writes PNG/PDF figures plus an input-hash record under `results/figures/`. It does not fit a model or rerun an experiment.

The paper is authored in LaTeX. With Tectonic installed:

```sh
make paper
# Or provide the compiler explicitly:
make paper TECTONIC=/path/to/tectonic
```

Tectonic may download TeX support files on first use. The checked-in PDF needs no compiler. The builder rejects overfull boxes and unresolved references; rendered pages also require visual inspection before publication. The optional `TECTONIC_CACHE_DIR` environment variable directs the compiler cache to a writable location.

## Boundaries

- Two superseded historical runs (`equity-overlays-20261106T020955456052Z` and `feature-research-20261106T020600619286Z`) lack their matching original source versions. They are not part of the current reproduction; their historical identities remain in Git and the original manifest.
- Live acquisition utilities cannot recreate historical vendor or filing vintages exactly. They are not called by reproduction.
- Saved historical provenance may name paths that existed before the repository cleanup. Those records describe the original run, while current commands and source paths are documented here.
- The original standalone CRR reference implementation was absent. Legacy method comparison requires an explicit provider; no substitute is presented as the historical implementation.
- Reproducing arithmetic does not validate executable option prices, usable liquidity or a trading advantage. The paper states the economic assumptions separately.

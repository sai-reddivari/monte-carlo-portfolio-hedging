PYTHON ?= .venv/bin/python
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export VECLIB_MAXIMUM_THREADS=1
export PYTHONHASHSEED=0
export MPLBACKEND=Agg
export MPLCONFIGDIR=/tmp/hedging-publication-mpl

.PHONY: reproduce test diff verify
reproduce:
	$(PYTHON) -m hedging_harness.reproduction --notebooks --reviewers
	$(PYTHON) scripts/diff_manifests.py
test:
	$(PYTHON) scripts/restore_frozen_inputs.py
	$(PYTHON) -m pytest -q
diff:
	$(PYTHON) scripts/diff_manifests.py
verify:
	$(PYTHON) scripts/verify_frozen_bundle.py

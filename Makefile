PYTHON ?= .venv/bin/python
export PYTHONPATH := $(CURDIR)/src
export OMP_NUM_THREADS=1
export MKL_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export VECLIB_MAXIMUM_THREADS=1
export PYTHONHASHSEED=0
export MPLBACKEND=Agg
export MPLCONFIGDIR=/tmp/hedging-publication-mpl

.PHONY: reproduce test diff verify figures paper
reproduce:
	$(PYTHON) -m hedging_harness.reproduction --notebooks --validation
	$(PYTHON) src/commands/diff_manifests.py
test:
	$(PYTHON) src/commands/restore_frozen_inputs.py
	$(PYTHON) -m pytest -q
diff:
	$(PYTHON) src/commands/diff_manifests.py
verify:
	$(PYTHON) src/commands/verify_validation_artifacts.py

figures:
	$(PYTHON) src/commands/build_exhibits.py

paper: figures
	$(PYTHON) src/commands/build_paper.py $(if $(TECTONIC),--tectonic "$(TECTONIC)",)

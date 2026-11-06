"""MonteCarlo_ModelIntroduction: original study operations moved from notebook cells."""
from IPython.display import display
from hedging_harness.configuration import defaults, notebook_controls
from hedging_harness.notebook_views import verify_frozen_overlay, historical_root, historical_path


def run():
    _controls = notebook_controls('MonteCarlo_ModelIntroduction')

    return locals()

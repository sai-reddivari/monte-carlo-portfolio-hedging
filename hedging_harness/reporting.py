"""Reporting interfaces; arithmetic preserved from the frozen core."""
import numpy as np
import pandas as pd
from dataclasses import asdict
from hashlib import sha256
from pathlib import Path
import platform
import scipy
from .legacy import SOURCES


def provenance(book, scenario, seed, n_paths):
    """Record assumptions, runtime versions and hashes; no market-data claims."""
    files = list(SOURCES) + sorted(Path(__file__).parent.glob("*.py"))
    return dict(book=asdict(book), scenario=scenario, seed=seed, n_paths=n_paths,
        measure="Q; drift equals constant financing rate; no dividends",
        versions=dict(python=platform.python_version(), numpy=np.__version__,
                      scipy=scipy.__version__, pandas=pd.__version__),
        source_sha256={str(p.relative_to(Path(__file__).resolve().parents[1])):sha256(p.read_bytes()).hexdigest() for p in files})


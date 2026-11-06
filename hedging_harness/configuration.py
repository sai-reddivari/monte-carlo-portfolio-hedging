"""Versioned publication defaults; no environment-variable overrides of research parameters."""
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
def defaults():
    return json.loads((ROOT / 'config/published_defaults.json').read_text())
def notebook_controls(name):
    return json.loads((ROOT / 'config/notebook_controls.json').read_text()).get(name, {})

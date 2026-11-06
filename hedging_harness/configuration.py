"""Versioned publication defaults; no environment-variable overrides of research parameters."""
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
def defaults():
    return json.loads((ROOT / 'config/published_defaults.json').read_text())
def notebook_controls(name):
    data = json.loads((ROOT / 'config/notebook_controls.json').read_text())
    values = data.get(name, {})
    for key in data.get('__integer_key_maps__', {}).get(name, []):
        values[key] = {int(k): v for k, v in values[key].items()}
    return values

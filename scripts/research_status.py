"""Read the frozen historical evidence status without overwriting its report."""
from pathlib import Path
import json
ROOT=Path(__file__).resolve().parents[1]
def build():
    return json.loads((ROOT/'reports/research_status.json').read_text())
if __name__ == '__main__':
    print(json.dumps(build(),indent=2))

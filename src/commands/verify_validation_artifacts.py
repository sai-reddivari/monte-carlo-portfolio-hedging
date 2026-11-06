"""Verify the numeric reference tables and historical test artifacts."""
import hashlib
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]

def verify():
    artifacts=ROOT/'tests/artifacts'
    entries=json.loads((artifacts/'manifest.json').read_text())['sha256']
    if not entries:raise RuntimeError('Validation artifact manifest is empty')
    failures=[]
    for name,expected in entries.items():
        p=artifacts/name
        if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=expected:failures.append(name)
    print(json.dumps({'checked':len(entries),'failures':failures,'passed':not failures},indent=2))
    return not failures

if __name__=='__main__':raise SystemExit(0 if verify() else 1)

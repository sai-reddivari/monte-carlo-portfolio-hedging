"""Check the untouched publication bundle; explicitly disclose ignored macOS metadata."""
from hashlib import sha256
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def verify():
    folder=ROOT/'docs/final_findings'
    values=json.loads((folder/'bundle_manifest.json').read_text())['files_sha256']
    matching=[];missing=[];mismatches=[]
    for name,expected in values.items():
        path=folder/name
        if not path.is_file():missing.append(name)
        elif sha256(path.read_bytes()).hexdigest()==expected:matching.append(name)
        else:mismatches.append(name)
    known='frozen_package_and_review_evidence/.DS_Store'
    passed=not mismatches and not(set(missing)-{known})
    result=dict(entries=len(values),matching=len(matching),missing=missing,mismatches=mismatches,
        clean_checkout_expectation='47 of 48; ignored macOS metadata is absent',passed=passed)
    print(json.dumps(result,indent=2))
    return result


if __name__=='__main__':raise SystemExit(0 if verify()['passed'] else 1)

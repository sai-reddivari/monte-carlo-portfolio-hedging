"""Validate cached selection identity without reselecting on test outcomes."""
import json
from hashlib import sha256
from datetime import datetime, timezone
import pandas as pd

def load_cached_release(PROTOCOL, study_path, RELEASE_DIR, ROOT, *, RUN_NEW_EXPERIMENT=False, run_release):
    if RUN_NEW_EXPERIMENT or not (RELEASE_DIR / "gate_status.json").is_file():
        if RELEASE_DIR.exists():
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            RELEASE_DIR = ROOT / "results" / "research-release-1" / stamp
        run_release(PROTOCOL, RELEASE_DIR)

    commitment = json.loads((RELEASE_DIR / "protocol_commitment.json").read_text())
    if commitment["protocol_sha256"] != sha256(PROTOCOL.read_bytes()).hexdigest():
        raise ValueError("Cached results use a different protocol. Set RUN_NEW_EXPERIMENT=True to run the changed protocol separately.")
    if commitment["study_sha256"] != sha256(study_path.read_bytes()).hexdigest():
        raise ValueError("Cached results use different study inputs. Set RUN_NEW_EXPERIMENT=True for a separate run.")
    manifest = json.loads((RELEASE_DIR / "artifact_manifest.json").read_text())
    for name, expected_hash in manifest.items():
        assert sha256((RELEASE_DIR / name).read_bytes()).hexdigest() == expected_hash, name
    selection_lock = json.loads((RELEASE_DIR / "selection.json").read_text())
    gate = json.loads((RELEASE_DIR / "gate_status.json").read_text())
    assert gate["status"] == "complete"
    assert sha256((RELEASE_DIR / "selection.json").read_bytes()).hexdigest() == gate["selection_lock_sha256"]
    selected = selection_lock["selected_policy"]
    selection = pd.read_csv(RELEASE_DIR / "selection_metrics.csv")
    evaluation = pd.read_csv(RELEASE_DIR / "evaluation_metrics.csv")
    print(f"Verified release: {RELEASE_DIR}")
    print(f"Locked policy: {selected}")
    return RELEASE_DIR, selected, selection, evaluation, gate

"""Verify publication evidence without rerunning or reselecting economic policies."""
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]


def digest(path):
    return sha256(path.read_bytes()).hexdigest()


def verify():
    config_path = ROOT / "config/research_release_2_package.json"
    config = json.loads(config_path.read_text())
    checks = []
    checked = {}

    def check(label, passed, detail=None):
        checks.append({"check": label, "passed": bool(passed), "detail": detail})

    def mapping(base, values, label):
        check(label + " manifest present", bool(values))
        for name, expected in values.items():
            path = Path(name)
            if not path.is_absolute():
                path = base / path
            exists = path.is_file()
            actual = digest(path) if exists else None
            check(label + ": " + name, actual == expected)
            if exists:
                try:
                    key = str(path.relative_to(ROOT))
                except ValueError:
                    key = str(path)
                checked[key] = actual

    for name, relative in config["canonical_runs"].items():
        folder = ROOT / relative
        check(name + " report", (folder / "report.md").is_file())
        if name == "controlled_release":
            mapping(folder, json.loads((folder / "artifact_manifest.json").read_text()), name)
            continue
        record_name = "run_record.json" if name == "model_replay" else "manifest.json"
        record = json.loads((folder / record_name).read_text())
        mapping(folder, record.get("artifacts_sha256", {}), name + " outputs")
        if record.get("source_sha256"):
            mapping(ROOT, record["source_sha256"], name + " sources")
        for field in ("feature_audit_sha256", "input_sha256"):
            if record.get(field):
                mapping(ROOT, record[field], name + " " + field)
        for key in ("prices", "factors"):
            if record.get(key + "_path") and record.get(key + "_sha256"):
                mapping(ROOT, {record[key + "_path"]: record[key + "_sha256"]}, name + " " + key)
        protocol_path = folder / "protocol.json"
        if record.get("protocol_sha256"):
            check(name + " protocol bytes", digest(protocol_path) == record["protocol_sha256"])
        if name == "equity_overlays":
            protocol = json.loads(protocol_path.read_text())
            mapping(ROOT, protocol["source_sha256"], name + " frozen sources")
            mapping(ROOT, protocol["input_sha256"], name + " frozen inputs")
            mapping(ROOT, {protocol["config_path"]: protocol["config_sha256"]}, name + " frozen config")

    for relative in (config["review_archive"], "results/research-release-2/opus-review-20261106"):
        folder = ROOT / relative
        manifest = json.loads((folder / "archive_manifest.json").read_text())
        mapping(folder, {k: v["sha256"] for k, v in manifest["files"].items()}, relative)

    review = ROOT / config["review_archive"]
    accounting = json.loads((review / "accounting/verified_outputs/audit_summary.json").read_text())
    check("independent terminal accounting", accounting["status"] == "passed" and accounting["rows"] == 2013)
    mapping(review / "accounting/verified_outputs", accounting["artifacts_sha256"], "independent accounting outputs")
    check("portable reviewer script", digest(review / "accounting/astra_overlay_independent_portable.py") == accounting["script"]["sha256"])
    for relative, record_name, field in (
        ("statistical_review", "metadata.json", "artifacts_sha256"),
        ("window_placement", "completion.json", "outputs_sha256"),
    ):
        folder = review / relative
        record = json.loads((folder / record_name).read_text())
        mapping(folder, record[field], relative + " original output hashes")
    phase = review / "window_placement"
    completion = json.loads((phase / "completion.json").read_text())
    check("diagnostic commitment bytes", digest(phase / "diagnostic_protocol.json") == completion["protocol_sha256"])
    check("window diagnostic accounting", completion["all_accounting_checks"] and completion["policy_window_replays"] == 1936)

    owner = next((p for p in config["overlay_owner_addendum_candidates"] if (ROOT / p).is_file()), None)
    check("overlay owner addendum received", owner is not None)
    documents = ["README.md", config["publication_summary"], config["claims_and_errata"], "docs/next_economic_protocol_requirements.md"]
    if owner:
        documents.append(owner)
    for relative in documents:
        path = ROOT / relative
        check(relative + " exists", path.is_file())
        if not path.is_file():
            continue
        checked[relative] = digest(path)
        missing = []
        for target in re.findall(r"\]\(([^)]+)\)", path.read_text()):
            if target.startswith(("https://", "http://", "#")):
                continue
            target = target.split("#", 1)[0]
            if not (path.parent / target).exists():
                missing.append(target)
        check(relative + " local links", not missing, missing)

    xml_path = ROOT / config["test_evidence"]
    suite = ET.parse(xml_path).getroot().find("testsuite")
    summary = {k: int(suite.attrib.get(k, 0)) for k in ("tests", "failures", "errors", "skipped")}
    check("combined test suite", summary["tests"] >= 216 and summary["failures"] == 0 and summary["errors"] == 0)
    checked[config["test_evidence"]] = digest(xml_path)
    check("empirical Gate 2 remains open", config["research_gate_2_passed"] is False)
    check("no public push claimed", config["public_push_performed"] is False)
    result = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "kind": "publication_integrity_and_link_verification_not_new_economic_evaluation",
        "package_config_sha256": digest(config_path),
        "passed": all(c["passed"] for c in checks),
        "checks": checks,
        "checked_file_sha256": checked,
        "test_summary": summary,
        "test_interpretation": "216 recorded cases = 194 tests plus 22 subtests; 28 pandas timezone deprecation warnings in the test run",
        "overlay_owner_addendum": owner,
        "independent_stage6_review": "2013 base-case terminal outcomes; does not certify all intrawindow marks, sensitivities or execution",
        "research_gate_2_passed": False,
    }
    output = ROOT / config["verification"]
    output.write_text(json.dumps(result, indent=2) + "\n")
    failures = [c for c in checks if not c["passed"]]
    print(json.dumps({"passed": result["passed"], "checks": len(checks), "failures": failures, "report": str(output.relative_to(ROOT))}, indent=2))
    return result


if __name__ == "__main__":
    raise SystemExit(0 if verify()["passed"] else 1)

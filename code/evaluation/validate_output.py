"""Structural validator for output.csv (format, ordering and evidence rules from problem_statement.md)."""
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OPS = {
    "FINDING": ["REPORT_REMAINING_RECORD", "REPORT_EXPOSED_PII", "REPORT_ACTIVE_DATA_FLOW", "REPORT_RESTORE_RISK"],
    "REMEDIATION": ["DISABLE_DATA_FLOW", "BLOCK_RESTORE", "DELETE_RECORD", "REDACT_RECORD", "ANONYMIZE_RECORD"],
    "VERIFICATION": ["VERIFY_RECORD_ABSENT", "VERIFY_RECORD_PRESENT", "VERIFY_RECORD_REDACTED",
                     "VERIFY_RECORD_ANONYMIZED", "VERIFY_DATA_FLOW_DISABLED", "VERIFY_RESTORE_BLOCKED"],
}
STATE = dict(zip(sum(OPS.values(), []), ["PRESENT", "PRESENT", "ACTIVE", "ACTIVE", "DISABLED", "BLOCKED", "ABSENT",
                                          "REDACTED", "ANONYMIZED", "ABSENT", "PRESENT", "REDACTED", "ANONYMIZED",
                                          "DISABLED", "BLOCKED"]))
FIELDS = {"step_no", "phase", "system_id", "resource_id", "operation", "state", "evidence_id"}


def validate(output, dataset):
    reqs = {r["case_id"]: r for r in csv.DictReader(open(dataset / "deletion_requests.csv", encoding="utf-8"))}
    manifest = {r["file_id"]: r for r in csv.DictReader(open(dataset / "evidence_files.csv", encoding="utf-8"))}
    rows = list(csv.DictReader(open(output, encoding="utf-8")))
    errors = []
    if [r["case_id"] for r in rows] != sorted(reqs):
        errors.append("case ids differ from deletion_requests.csv or are not sorted")
    for r in rows:
        cid, status = r["case_id"], r["deletion_status"]
        steps = json.loads(r["steps_json"])
        if status not in ("COMPLETE", "INCOMPLETE", "NOT_APPLICABLE"):
            errors.append(f"{cid}: bad status {status}")
        if status == "NOT_APPLICABLE" and steps:
            errors.append(f"{cid}: NOT_APPLICABLE must be []")
        last = None
        for i, s in enumerate(steps, 1):
            if set(s) != FIELDS or s["step_no"] != i:
                errors.append(f"{cid}: bad fields/step_no at {i}")
                continue
            if s["operation"] not in OPS[s["phase"]] or s["state"] != STATE[s["operation"]]:
                errors.append(f"{cid}: bad operation/state at {i}")
                continue
            k = (["FINDING", "REMEDIATION", "VERIFICATION"].index(s["phase"]), OPS[s["phase"]].index(s["operation"]),
                 s["system_id"], s["resource_id"])
            if last and k < last:
                errors.append(f"{cid}: ordering violated at step {i}")
            last = k
            ev = s["evidence_id"]
            needs = s["phase"] == "FINDING" or (status == "COMPLETE" and s["phase"] == "VERIFICATION")
            if needs and not ev:
                errors.append(f"{cid}: step {i} needs evidence")
            if not needs and ev:
                errors.append(f"{cid}: step {i} must have empty evidence")
            if ev and (ev not in manifest or manifest[ev]["captured_at"] > reqs[cid]["audit_at"]):
                errors.append(f"{cid}: step {i} cites evidence {ev} unavailable at audit_at")
        if status == "COMPLETE" and any(s["phase"] != "VERIFICATION" for s in steps):
            errors.append(f"{cid}: COMPLETE may only contain verification steps")
    return len(rows), errors


if __name__ == "__main__":
    n, errs = validate(ROOT / "output.csv", ROOT / "dataset")
    print(f"{n} rows, {len(errs)} problems")
    for e in errs[:40]:
        print(" -", e)
    sys.exit(1 if errs else 0)

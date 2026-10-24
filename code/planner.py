"""Turn reconstructed resource states into a status and ordered steps."""
from engine import (FINDING_ORDER, REMEDIATION_ORDER, VERIFY_ORDER, STATE, system_of)

RANK = {op: i for i, op in enumerate(FINDING_ORDER + REMEDIATION_ORDER + VERIFY_ORDER)}


def step(phase, op, rid, evidence=""):
    return {"phase": phase, "system_id": system_of(rid), "resource_id": rid, "operation": op,
            "state": STATE[op], "evidence_id": evidence}


def plan(states, audit_at, retention_ok):
    """states: rid -> {'kind','file'}.  Returns (status, steps)."""
    findings, remediation, verification = [], [], []
    complete_verif = []
    for rid, st in states.items():
        k, f, sysid = st["kind"], st["file"], system_of(rid)
        if sysid in ("account_service", "search_service", "export_service"):
            if k == "PRESENT":
                findings.append(step("FINDING", "REPORT_REMAINING_RECORD", rid, f))
                remediation.append(step("REMEDIATION", "DELETE_RECORD", rid))
                verification.append(step("VERIFICATION", "VERIFY_RECORD_ABSENT", rid))
            elif sysid == "account_service":
                complete_verif.append(step("VERIFICATION", "VERIFY_RECORD_ABSENT", rid, f))
                verification.append(step("VERIFICATION", "VERIFY_RECORD_ABSENT", rid))
            else:
                complete_verif.append(step("VERIFICATION", "VERIFY_RECORD_ABSENT", rid, f))
        elif sysid == "support_platform":
            if k == "ATTACH":
                findings.append(step("FINDING", "REPORT_REMAINING_RECORD", rid, f))
                remediation.append(step("REMEDIATION", "DELETE_RECORD", rid))
                verification.append(step("VERIFICATION", "VERIFY_RECORD_ABSENT", rid))
            elif k == "EXPOSED":
                findings.append(step("FINDING", "REPORT_EXPOSED_PII", rid, f))
                remediation.append(step("REMEDIATION", "REDACT_RECORD", rid))
                verification.append(step("VERIFICATION", "VERIFY_RECORD_REDACTED", rid))
            else:
                complete_verif.append(step("VERIFICATION", "VERIFY_RECORD_REDACTED", rid, f))
        elif sysid == "analytics_platform":
            if k == "EXPOSED":
                findings.append(step("FINDING", "REPORT_EXPOSED_PII", rid, f))
                remediation.append(step("REMEDIATION", "ANONYMIZE_RECORD", rid))
                verification.append(step("VERIFICATION", "VERIFY_RECORD_ANONYMIZED", rid))
            else:
                complete_verif.append(step("VERIFICATION", "VERIFY_RECORD_ANONYMIZED", rid, f))
        elif sysid == "integration_service":
            if k == "ACTIVE":
                findings.append(step("FINDING", "REPORT_ACTIVE_DATA_FLOW", rid, f))
                remediation.append(step("REMEDIATION", "DISABLE_DATA_FLOW", rid))
                verification.append(step("VERIFICATION", "VERIFY_DATA_FLOW_DISABLED", rid))
            else:
                complete_verif.append(step("VERIFICATION", "VERIFY_DATA_FLOW_DISABLED", rid, f))
        elif sysid == "backup_service":
            if k == "ALLOWED":
                findings.append(step("FINDING", "REPORT_RESTORE_RISK", rid, f))
                remediation.append(step("REMEDIATION", "BLOCK_RESTORE", rid))
                verification.append(step("VERIFICATION", "VERIFY_RESTORE_BLOCKED", rid))
            else:
                complete_verif.append(step("VERIFICATION", "VERIFY_RESTORE_BLOCKED", rid, f))
        elif sysid == "identity_service":
            if k == "EXPOSED":
                findings.append(step("FINDING", "REPORT_EXPOSED_PII", rid, f))
                remediation.append(step("REMEDIATION", "REDACT_RECORD", rid))
                verification.append(step("VERIFICATION", "VERIFY_RECORD_REDACTED", rid))
            else:
                complete_verif.append(step("VERIFICATION", "VERIFY_RECORD_REDACTED", rid, f))
        elif sysid in ("security_service", "legal_service"):
            if retention_ok(rid, st):
                complete_verif.append(step("VERIFICATION", "VERIFY_RECORD_PRESENT", rid, f))
                verification.append(step("VERIFICATION", "VERIFY_RECORD_PRESENT", rid))
    if findings:
        status, steps = "INCOMPLETE", findings + remediation + verification
    else:
        status, steps = "COMPLETE", complete_verif
    return status, finalize(steps)


def finalize(steps):
    key = lambda s: (RANK[s["operation"]], s["system_id"], s["resource_id"])
    seen, out = set(), []
    for s in sorted(steps, key=key):
        k = (s["operation"], s["resource_id"])
        if k in seen:
            continue
        seen.add(k)
        out.append(s)
    # stable phase order: findings, remediation, verification
    order = {"FINDING": 0, "REMEDIATION": 1, "VERIFICATION": 2}
    out.sort(key=lambda s: (order[s["phase"]], RANK[s["operation"]], s["system_id"], s["resource_id"]))
    for i, s in enumerate(out, 1):
        s["step_no"] = i
    return out

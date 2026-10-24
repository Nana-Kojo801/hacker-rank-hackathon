"""Turn reconstructed resource states into a status and ordered steps."""
from engine import FINDING_ORDER, REMEDIATION_ORDER, VERIFY_ORDER, STATE
from evidence import system_of

ORDER = FINDING_ORDER + REMEDIATION_ORDER + VERIFY_ORDER
RANK = {op: i for i, op in enumerate(ORDER)}
PHASE_RANK = {"FINDING": 0, "REMEDIATION": 1, "VERIFICATION": 2}

# action -> (finding op, remediation op, verification op)
TREATMENT = {
    "DELETE": ("REPORT_REMAINING_RECORD", "DELETE_RECORD", "VERIFY_RECORD_ABSENT"),
    "REDACT": ("REPORT_EXPOSED_PII", "REDACT_RECORD", "VERIFY_RECORD_REDACTED"),
    "ANONYMIZE": ("REPORT_EXPOSED_PII", "ANONYMIZE_RECORD", "VERIFY_RECORD_ANONYMIZED"),
    "FLOW": ("REPORT_ACTIVE_DATA_FLOW", "DISABLE_DATA_FLOW", "VERIFY_DATA_FLOW_DISABLED"),
    "RESTORE": ("REPORT_RESTORE_RISK", "BLOCK_RESTORE", "VERIFY_RESTORE_BLOCKED"),
}


def step(phase, op, rid, evidence=""):
    return {"phase": phase, "system_id": system_of(rid), "resource_id": rid, "operation": op,
            "state": STATE[op], "evidence_id": evidence}


def plan(states):
    """states: rid -> evaluation dict from World.evaluate.  Returns (status, steps)."""
    findings, remediation, verification, proof = [], [], [], []
    for rid, st in states.items():
        action = st["action"]
        if action == "RETAIN":
            if st["file"]:      # a proof step must cite evidence that existed at audit_at
                proof.append(step("VERIFICATION", "VERIFY_RECORD_PRESENT", rid, st["file"]))
            verification.append(step("VERIFICATION", "VERIFY_RECORD_PRESENT", rid))
            continue
        f_op, r_op, v_op = TREATMENT[action]
        if st["violated"]:
            findings.append(step("FINDING", f_op, rid, st["file"]))
            remediation.append(step("REMEDIATION", r_op, rid))
            verification.append(step("VERIFICATION", v_op, rid))
        else:
            proof.append(step("VERIFICATION", v_op, rid, st["file"]))
            if system_of(rid) == "account_service":
                verification.append(step("VERIFICATION", v_op, rid))
    if findings:
        return "INCOMPLETE", finalize(findings + remediation + verification)
    return "COMPLETE", finalize(proof)


def finalize(steps):
    seen, out = set(), []
    for s in steps:
        k = (s["phase"], s["operation"], s["resource_id"])
        if k not in seen:
            seen.add(k)
            out.append(s)
    out.sort(key=lambda s: (PHASE_RANK[s["phase"]], RANK[s["operation"]], s["system_id"], s["resource_id"]))
    for i, s in enumerate(out, 1):
        s["step_no"] = i
    return out

"""Builds a tiny synthetic dataset (same schema as dataset/) with hand-derived expected answers.

Four fictional subjects exercise behaviours the public samples barely cover:
  X1  old (historical) e-mail in the request + replication drift (account only left in a read replica)
  X2  non-deletion request written in Spanish -> NOT_APPLICABLE
  X3  evidence captured after audit_at must be ignored (account reappears only in a later snapshot)
  X4  active data flow + restorable backup + tombstone that still exposes the e-mail address
Run:  python3 code/evaluation/custom_cases/build_custom_cases.py
"""
import csv
import json
import shutil
from pathlib import Path

HERE = Path(__file__).parent
DS = HERE / "dataset"
EV = DS / "evidence"
RULES = Path(__file__).resolve().parents[3] / "dataset" / "deletion_rules.csv"


def w(path, rows, header):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        wr = csv.writer(f)
        wr.writerow(header)
        wr.writerows(rows)


def main():
    if DS.exists():
        shutil.rmtree(DS)
    EV.mkdir(parents=True)
    shutil.copy(RULES, DS / "deletion_rules.csv")
    w(DS / "user_identities.csv", [
        ["user_901", "Ada Quartz", "ada.quartz@example.test", "+1 555 0101", "h" * 64, "2026-05-01T00:00:00Z"],
        ["user_902", "Bruno Lime", "bruno.lime@example.test", "+1 555 0102", "i" * 64, "2026-05-01T00:00:00Z"],
        ["user_903", "Chika Moss", "chika.moss@example.test", "+1 555 0103", "j" * 64, "2026-05-01T00:00:00Z"],
        ["user_904", "Dara Pine", "dara.pine@example.test", "+1 555 0104", "k" * 64, "2026-05-01T00:00:00Z"],
    ], ["user_id", "name", "email", "phone", "email_hash", "updated_at"])
    w(DS / "user_audit_log.csv", [
        ["audit_x1", "user_901", "2026-03-01T00:00:00Z", "email", "ada.old@example.test", "ada.quartz@example.test"],
    ], ["audit_id", "user_id", "event_time", "field_name", "old_value", "new_value"])
    w(DS / "system_activity.csv", [
        ["activity_x1", "2026-06-01T10:00:00Z", "CHECK_DATA_FLOW", "deletion_worker", "integration_service", "data_flow_9040", "SUCCESS", "Connector status check."],
        ["activity_x2", "2026-06-01T10:05:00Z", "CHECK_RESTORE_ACCESS", "deletion_worker", "backup_service", "backup_9040", "SUCCESS", "Restore check."],
        ["activity_x3", "2026-06-01T10:10:00Z", "REDACT_RECORD", "deletion_worker", "identity_service", "tombstone_9040", "FAILED", "Redaction result."],
    ], ["activity_id", "event_time", "event_type", "source_system", "target_system", "resource_id", "reported_result", "details"])

    # X1: primary lacks the account, read replica still has it
    (EV / "customer_data_read_replica_20260610.sql").write_text("""-- Captured at: 2026-06-10T08:00:00Z
-- Database topology: read_replica
BEGIN TRANSACTION;
CREATE TABLE customer_data_primary (resource_id TEXT PRIMARY KEY, data_store TEXT, collection TEXT, payload TEXT);
CREATE TABLE customer_data_read_replica (resource_id TEXT PRIMARY KEY, data_store TEXT, collection TEXT, payload TEXT);
INSERT INTO "customer_data_primary" VALUES('audit_record_9101','security_service','security_audit_events','{"resource_id":"audit_record_9101","subject_reference":"user_901","event_name":"account_deletion_reviewed","retention_until":"2033-12-31T23:59:59Z"}');
INSERT INTO "customer_data_read_replica" VALUES('audit_record_9101','security_service','security_audit_events','{"resource_id":"audit_record_9101","subject_reference":"user_901","event_name":"account_deletion_reviewed","retention_until":"2033-12-31T23:59:59Z"}');
INSERT INTO "customer_data_read_replica" VALUES('account_9001','account_service','customer_profiles','{"resource_id":"account_9001","customer_reference":"user_901","full_name":"Ada Quartz","email":"ada.quartz@example.test","phone":"+1 555 0101","account_status":"ACTIVE"}');
INSERT INTO "customer_data_primary" VALUES('account_9999','account_service','customer_profiles','{"resource_id":"account_9999","customer_reference":"user_999","full_name":"Other Person","email":"other@example.test","phone":null,"account_status":"ACTIVE"}');
COMMIT;
""", encoding="utf-8")

    # X3: earlier snapshot proves absence; later file (after audit_at) shows the account again
    (EV / "customer_profiles_20260620.sql").write_text("""-- Captured at: 2026-06-20T08:00:00Z
-- Database topology: primary_only
BEGIN TRANSACTION;
CREATE TABLE customer_profiles_primary (resource_id TEXT PRIMARY KEY, user_id TEXT, full_name TEXT, email TEXT, phone TEXT, account_status TEXT, updated_at TEXT);
INSERT INTO "customer_profiles_primary" VALUES('account_9100','user_999','Other Person','other@example.test','+1','ACTIVE','2026-06-19T00:00:00Z');
COMMIT;
""", encoding="utf-8")
    (EV / "customer_profiles_20260702.sql").write_text("""-- Captured at: 2026-07-02T08:00:00Z
-- Database topology: primary_only
BEGIN TRANSACTION;
CREATE TABLE customer_profiles_primary (resource_id TEXT PRIMARY KEY, user_id TEXT, full_name TEXT, email TEXT, phone TEXT, account_status TEXT, updated_at TEXT);
INSERT INTO "customer_profiles_primary" VALUES('account_9003','user_903','Chika Moss','chika.moss@example.test','+1 555 0103','ACTIVE','2026-07-01T00:00:00Z');
COMMIT;
""", encoding="utf-8")
    (EV / "audit_ledger_20260620.json").write_text(json.dumps({
        "exported_at": "2026-06-20T09:00:00Z", "origin": "security_audit_service", "records": [
            {"recorded_at": "2026-06-20T09:00:00Z", "system": "account_service", "resource_id": "account_9003",
             "record_type": "USER_PROFILE", "result": "NOT_FOUND", "subject_reference": "chika.moss@example.test"},
            {"recorded_at": "2026-06-20T09:00:00Z", "system": "security_service", "resource_id": "audit_record_9103",
             "record_type": "SECURITY_AUDIT_LOG", "result": "FOUND", "subject_reference": "user_903",
             "retention_until": "2033-12-31T23:59:59Z"}]}), encoding="utf-8")

    # X4: bundle with active flow, restorable backup, tombstone exposing the e-mail
    (EV / "snapshot_bundle_20260625.json").write_text(json.dumps({
        "exported_at": "2026-06-25T12:00:00Z", "source": "records_assurance_service", "snapshots": [
            {"captured_at": "2026-06-25T12:00:00Z", "data_store": "integration_service", "collection": "connector_configurations",
             "records": [{"resource_id": "data_flow_9040", "subject_selector": "user_904", "enabled": True, "mode": "continuous_sync"}]},
            {"captured_at": "2026-06-25T12:00:00Z", "data_store": "backup_service", "collection": "backup_catalog",
             "records": [{"resource_id": "backup_9040", "subject_reference": "user_904", "restore_allowed": True}]},
            {"captured_at": "2026-06-25T12:00:00Z", "data_store": "identity_service", "collection": "deleted_customer_references",
             "records": [{"resource_id": "tombstone_9040", "subject_reference": "user_904", "name": None,
                          "email": "dara.pine@example.test", "phone": None, "email_hash": None, "account_status": "DELETED"}]},
            {"captured_at": "2026-06-25T12:00:00Z", "data_store": "security_service", "collection": "security_audit_events",
             "records": [{"resource_id": "audit_record_9104", "subject_reference": "user_904", "event_name": "account_deletion_reviewed",
                          "retention_until": "2033-12-31T23:59:59Z"}]}]}), encoding="utf-8")

    w(DS / "evidence_files.csv", [
        ["evidence_01", "evidence/databases/customer_data_read_replica_20260610.sql", "customer_data_read_replica_capture", "2026-06-10T08:00:00Z"],
        ["evidence_02", "evidence/databases/customer_profiles_20260620.sql", "customer_profiles_capture", "2026-06-20T08:00:00Z"],
        ["evidence_03", "evidence/records/audit_ledger_20260620.json", "security_audit_service", "2026-06-20T09:00:00Z"],
        ["evidence_04", "evidence/databases/customer_profiles_20260702.sql", "customer_profiles_capture", "2026-07-02T08:00:00Z"],
        ["evidence_05", "evidence/records/snapshot_bundle_20260625.json", "records_assurance_snapshot_bundle", "2026-06-25T12:00:00Z"],
    ], ["file_id", "file_path", "origin", "captured_at"])
    (EV / "databases").mkdir(exist_ok=True)
    (EV / "records").mkdir(exist_ok=True)
    for name, sub in [("customer_data_read_replica_20260610.sql", "databases"), ("customer_profiles_20260620.sql", "databases"),
                      ("customer_profiles_20260702.sql", "databases"), ("audit_ledger_20260620.json", "records"),
                      ("snapshot_bundle_20260625.json", "records")]:
        (EV / name).rename(EV / sub / name)

    reqs = [
        ["x1", "ada.old@example.test", "2026-06-01T09:00:00Z", "COMPLETE", "2026-06-02T09:00:00Z", "2026-06-10T09:00:00Z",
         "Please delete my account and everything linked to my old e-mail address too."],
        ["x2", "bruno.lime@example.test", "2026-06-01T09:00:00Z", "NOT_STARTED", "2026-06-02T09:00:00Z", "2026-06-10T09:00:00Z",
         "Solo quiero actualizar mi dirección de entrega. Por favor, no borren mi cuenta ni mis pedidos."],
        ["x3", "chika.moss@example.test", "2026-06-10T09:00:00Z", "COMPLETE", "2026-06-12T09:00:00Z", "2026-06-21T09:00:00Z",
         "Please erase the account associated with this address."],
        ["x4", "dara.pine@example.test", "2026-06-15T09:00:00Z", "PARTIALLY_COMPLETE", "2026-06-16T09:00:00Z", "2026-06-26T09:00:00Z",
         "I want my account and personal data permanently deleted. Keep only what the law requires."],
    ]
    w(DS / "deletion_requests.csv", reqs, ["case_id", "email", "requested_at", "reported_status", "reported_at", "audit_at", "request_text"])

    def st(n, phase, system, rid, op, state, ev=""):
        return {"step_no": n, "phase": phase, "system_id": system, "resource_id": rid, "operation": op, "state": state, "evidence_id": ev}

    expected = {
        "x1": ("INCOMPLETE", [
            st(1, "FINDING", "account_service", "account_9001", "REPORT_REMAINING_RECORD", "PRESENT", "evidence_01"),
            st(2, "REMEDIATION", "account_service", "account_9001", "DELETE_RECORD", "ABSENT"),
            st(3, "VERIFICATION", "account_service", "account_9001", "VERIFY_RECORD_ABSENT", "ABSENT"),
            st(4, "VERIFICATION", "security_service", "audit_record_9101", "VERIFY_RECORD_PRESENT", "PRESENT")]),
        "x2": ("NOT_APPLICABLE", []),
        "x3": ("COMPLETE", [
            st(1, "VERIFICATION", "account_service", "account_9003", "VERIFY_RECORD_ABSENT", "ABSENT", "evidence_03"),
            st(2, "VERIFICATION", "security_service", "audit_record_9103", "VERIFY_RECORD_PRESENT", "PRESENT", "evidence_03")]),
        "x4": ("INCOMPLETE", [
            st(1, "FINDING", "identity_service", "tombstone_9040", "REPORT_EXPOSED_PII", "PRESENT", "evidence_05"),
            st(2, "FINDING", "integration_service", "data_flow_9040", "REPORT_ACTIVE_DATA_FLOW", "ACTIVE", "evidence_05"),
            st(3, "FINDING", "backup_service", "backup_9040", "REPORT_RESTORE_RISK", "ACTIVE", "evidence_05"),
            st(4, "REMEDIATION", "integration_service", "data_flow_9040", "DISABLE_DATA_FLOW", "DISABLED"),
            st(5, "REMEDIATION", "backup_service", "backup_9040", "BLOCK_RESTORE", "BLOCKED"),
            st(6, "REMEDIATION", "identity_service", "tombstone_9040", "REDACT_RECORD", "REDACTED"),
            st(7, "VERIFICATION", "security_service", "audit_record_9104", "VERIFY_RECORD_PRESENT", "PRESENT"),
            st(8, "VERIFICATION", "identity_service", "tombstone_9040", "VERIFY_RECORD_REDACTED", "REDACTED"),
            st(9, "VERIFICATION", "integration_service", "data_flow_9040", "VERIFY_DATA_FLOW_DISABLED", "DISABLED"),
            st(10, "VERIFICATION", "backup_service", "backup_9040", "VERIFY_RESTORE_BLOCKED", "BLOCKED")]),
    }
    w(DS / "expected_output.csv", [[k, v[0], json.dumps(v[1], separators=(",", ":"))] for k, v in expected.items()],
      ["case_id", "deletion_status", "steps_json"])
    # blank placeholders other loaders may expect
    w(DS / "sample_deletion_requests.csv", [], ["case_id", "email", "requested_at", "reported_status", "reported_at", "audit_at", "request_text"])
    print("custom dataset written to", DS)


if __name__ == "__main__":
    main()

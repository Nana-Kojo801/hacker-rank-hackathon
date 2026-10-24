"""Case engine: link resources to a subject, reconstruct their state at audit_at, apply policy, emit steps."""
import csv
import re
from collections import defaultdict
from datetime import datetime, timedelta

from evidence import PREFIX_SYSTEM, RID_RE, system_of

TS = "%Y-%m-%dT%H:%M:%SZ"


def P(s):
    return datetime.strptime(s, TS)


FINDING_ORDER = ["REPORT_REMAINING_RECORD", "REPORT_EXPOSED_PII", "REPORT_ACTIVE_DATA_FLOW", "REPORT_RESTORE_RISK"]
REMEDIATION_ORDER = ["DISABLE_DATA_FLOW", "BLOCK_RESTORE", "DELETE_RECORD", "REDACT_RECORD", "ANONYMIZE_RECORD"]
VERIFY_ORDER = ["VERIFY_RECORD_ABSENT", "VERIFY_RECORD_PRESENT", "VERIFY_RECORD_REDACTED",
                "VERIFY_RECORD_ANONYMIZED", "VERIFY_DATA_FLOW_DISABLED", "VERIFY_RESTORE_BLOCKED"]
STATE = {
    "REPORT_REMAINING_RECORD": "PRESENT", "REPORT_EXPOSED_PII": "PRESENT",
    "REPORT_ACTIVE_DATA_FLOW": "ACTIVE", "REPORT_RESTORE_RISK": "ACTIVE",
    "DISABLE_DATA_FLOW": "DISABLED", "BLOCK_RESTORE": "BLOCKED", "DELETE_RECORD": "ABSENT",
    "REDACT_RECORD": "REDACTED", "ANONYMIZE_RECORD": "ANONYMIZED",
    "VERIFY_RECORD_ABSENT": "ABSENT", "VERIFY_RECORD_PRESENT": "PRESENT", "VERIFY_RECORD_REDACTED": "REDACTED",
    "VERIFY_RECORD_ANONYMIZED": "ANONYMIZED", "VERIFY_DATA_FLOW_DISABLED": "DISABLED",
    "VERIFY_RESTORE_BLOCKED": "BLOCKED",
}


def truthy(v):
    return str(v).strip().lower() in ("1", "true", "yes", "active", "enabled", "y")


def kind_of(o):
    """Semantic state of one observation: what the record looks like."""
    a = o.attrs
    s = o.system
    result = str(a.get("result", "")).lower()
    if s == "account_service":
        if a.get("profile_null") or str(a.get("status_code", a.get("http_status", ""))) == "404" \
                or result == "not_found" or str(a.get("rows", "1")) == "0":
            return "ABSENT"
        return "PRESENT"
    if s in ("search_service", "export_service"):
        if result in ("not_found", "miss") or str(a.get("rows", "1")) == "0":
            return "ABSENT"
        return "PRESENT"
    if s == "support_platform":
        text = str(a.get("message_text", a.get("message_excerpt", "")))
        if a.get("storage_class") == "ticket_attachment" or "attachment" in str(a.get("record_type", "")) \
                or "attachment" in str(a.get("event", "")):
            return "ATTACH"
        if result == "redacted" or "[redacted]" in text.lower():
            return "REDACTED"
        if result == "identifiable" or o.emails or o.phones or o.names:
            return "EXPOSED"
        return "REDACTED"
    if s == "analytics_platform":
        if result == "anonymized" or a.get("no_identifier"):
            return "ANONYMIZED"
        if result == "identifiable" or o.emails or o.users or o.hashes or o.phones:
            return "EXPOSED"
        return "ANONYMIZED"
    if s == "integration_service":
        if "enabled" in a:
            return "ACTIVE" if truthy(a["enabled"]) else "DISABLED"
        if result:
            return "ACTIVE" if result == "active" else "DISABLED"
        return "ACTIVE"
    if s == "backup_service":
        if "restore_allowed" in a:
            return "ALLOWED" if truthy(a["restore_allowed"]) else "BLOCKED"
        if result:
            return "ALLOWED" if result == "active" else "BLOCKED"
        return "ALLOWED"
    if s == "identity_service":
        return "EXPOSED" if (o.emails or o.phones or o.hashes or o.names) else "REDACTED"
    if s == "security_service":
        return "PRESENT"
    if s == "legal_service":
        return "PRESENT"
    return "PRESENT"


class World:
    def __init__(self, obs, manifest, coverage, activity_rows, identities):
        self.obs = obs
        self.manifest = manifest
        self.coverage = coverage          # file_id -> {system: time}
        self.book = identities
        self.by_rid = defaultdict(list)
        for o in obs:
            self.by_rid[o.rid].append(o)
        self.ident_index = defaultdict(set)   # identifier -> rids (any time)
        for o in obs:
            for i in o.idents():
                self.ident_index[i].add(o.rid)
        self.activity = activity_rows
        for a in activity_rows:
            a["_t"] = P(a["event_time"])

    # ---------------------------------------------------------------- linking
    def linked_rids(self, user, audit_at):
        ids = user.emails | user.hashes | {user.user_id} | user.phones
        rids = set()
        for i in ids:
            rids |= self.ident_index.get(i, set())
        return rids

    # ---------------------------------------------------------------- state
    def timeline(self, rid, audit_at):
        """List of (t, file_id, kind, obs) events for rid at or before audit_at, ascending."""
        system = system_of(rid)
        events = []
        files_with = set()
        for o in self.by_rid.get(rid, []):
            if self.manifest[o.file_id]["captured_at"] > audit_at or o.t > audit_at:
                continue
            events.append((o.t, o.file_id, kind_of(o), o))
            files_with.add(o.file_id)
        for fid, cov in self.coverage.items():
            t = cov.get(system)
            if not t or t > audit_at or fid in files_with or self.manifest[fid]["captured_at"] > audit_at:
                continue
            events.append((t, fid, "ABSENT", None))
        events.sort(key=lambda e: (e[0], 0 if e[3] is None else 1))
        return events

    def state(self, rid, audit_at):
        ev = self.timeline(rid, audit_at)
        if not ev:
            return None
        t, fid, kind, o = ev[-1]
        return {"t": t, "file": fid, "kind": kind, "obs": o}

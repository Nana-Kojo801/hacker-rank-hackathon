"""World model: observations + activity -> per-resource compliance state at audit_at."""
from collections import defaultdict
from datetime import datetime

from evidence import system_of

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

# required action implied by the operation the deletion worker attempted on a resource
WORKER_OP_ACTION = {
    "DELETE_RECORD": "DELETE", "REDACT_RECORD": "REDACT", "ANONYMIZE_RECORD": "ANONYMIZE",
    "CHECK_DATA_FLOW": "FLOW", "DISABLE_DATA_FLOW": "FLOW",
    "CHECK_RESTORE_ACCESS": "RESTORE", "BLOCK_RESTORE": "RESTORE", "RETAIN_RECORD": "RETAIN",
}
DEFAULT_ACTION = {
    "account_service": "DELETE", "search_service": "DELETE", "export_service": "DELETE",
    "support_platform": "REDACT", "analytics_platform": "ANONYMIZE", "integration_service": "FLOW",
    "backup_service": "RESTORE", "identity_service": "REDACT", "security_service": "RETAIN",
    "legal_service": "RETAIN", "marketing_platform": "DELETE", "object_storage": "DELETE",
    "cache_service": "DELETE", "email_delivery_service": "REDACT",
}


def truthy(v):
    return str(v).strip().lower() in ("1", "true", "yes", "active", "enabled", "y")


def facts(o):
    """Reduce an observation to exists / identifier / flow / restore facts."""
    a = o.attrs
    result = str(a.get("result", "")).lower()
    code = str(a.get("status_code", a.get("http_status", "")))
    exists = True
    if a.get("profile_null") or code == "404" or result in ("not_found", "miss") or str(a.get("rows", "1")) == "0":
        exists = False
    direct = bool(o.emails or o.phones or o.hashes or o.names)
    attrib = bool(direct or o.users)
    text = str(a.get("message_text", a.get("message_excerpt", ""))).lower()
    if result in ("anonymized", "redacted") or a.get("no_identifier"):
        direct = attrib = False
    elif result == "identifiable":
        direct = attrib = True
    if "[redacted]" in text:
        direct = False
    enabled = None
    if "enabled" in a:
        enabled = truthy(a["enabled"])
    elif o.system == "integration_service" and result:
        enabled = result == "active"
    allowed = None
    if "restore_allowed" in a:
        allowed = truthy(a["restore_allowed"])
    elif "eligible" in a:
        allowed = truthy(a["eligible"]) and not truthy(a.get("deletion_block", "false"))
    elif "decision" in a:
        allowed = str(a["decision"]).lower() != "deny"
    elif o.system == "backup_service" and result:
        allowed = result == "active"
    return {"exists": exists, "direct": direct, "attrib": attrib, "enabled": enabled, "allowed": allowed}


def violates(action, f):
    if action == "DELETE":
        return f["exists"]
    if action == "REDACT":
        return f["exists"] and f["direct"]
    if action == "ANONYMIZE":
        return f["exists"] and f["attrib"]
    if action == "FLOW":
        return bool(f["enabled"])
    if action == "RESTORE":
        return bool(f["allowed"])
    return False


class World:
    def __init__(self, obs, manifest, coverage, activity_rows, identities):
        self.obs = obs
        self.manifest = manifest
        self.coverage = coverage          # file_id -> {system: time}
        self.book = identities
        self.by_rid = defaultdict(list)
        for o in obs:
            self.by_rid[o.rid].append(o)
        self.ident_index = defaultdict(set)
        for o in obs:
            for i in o.idents():
                self.ident_index[i].add(o.rid)
        self.file_systems = defaultdict(set)
        for o in obs:
            self.file_systems[o.file_id].add(o.system)
        for fid, cov in coverage.items():
            self.file_systems[fid] |= set(cov)
        self.activity = activity_rows
        self.worker_ops = defaultdict(list)
        for a in activity_rows:
            a["_t"] = P(a["event_time"])
            if a["source_system"] == "deletion_worker":
                self.worker_ops[a["resource_id"]].append(a)

    def fallback_file(self, system, audit_at):
        """Latest evidence file at/before audit_at that speaks about this system at all."""
        best = ""
        best_t = ""
        for fid, row in self.manifest.items():
            t = row["captured_at"]
            if t > audit_at or t < best_t:
                continue
            if fid in self.file_systems and system in self.file_systems[fid]:
                best, best_t = fid, t
        return best

    def linked_rids(self, user):
        ids = user.emails | user.hashes | {user.user_id} | user.phones
        rids = set()
        for i in ids:
            rids |= self.ident_index.get(i, set())
        return rids

    def action_for(self, rid):
        if any(o.attrs.get("attachment") for o in self.by_rid.get(rid, [])):
            return "DELETE"          # support attachment belonging only to the subject (rule_06)
        ops = self.worker_ops.get(rid)
        if ops:
            return WORKER_OP_ACTION.get(ops[-1]["event_type"], DEFAULT_ACTION.get(system_of(rid), "DELETE"))
        return DEFAULT_ACTION.get(system_of(rid), "DELETE")

    def store_of(self, o):
        return (self.manifest[o.file_id]["origin"], o.attrs.get("table", o.system))

    def evaluate(self, rid, requested_at, audit_at, need_explicit=True):
        """-> dict(action, violated, file, retained_obs) or None when nothing is known."""
        system = system_of(rid)
        action = self.action_for(rid)
        floor = "" if action == "RETAIN" else requested_at
        events = defaultdict(list)    # store -> [(t, explicit, file, facts, obs)]
        seen_files = set()
        for o in self.by_rid.get(rid, []):
            fid = o.file_id
            if self.manifest[fid]["captured_at"] > audit_at or o.t > audit_at or o.t < floor:
                continue
            events[self.store_of(o)].append((o.t, 1, fid, facts(o), o))
            seen_files.add(fid)
        if action != "RETAIN":
            for fid, cov in self.coverage.items():
                t = cov.get(system)
                if not t or t > audit_at or t < floor or fid in seen_files or self.manifest[fid]["captured_at"] > audit_at:
                    continue
                f = {"exists": False, "direct": False, "attrib": False, "enabled": False, "allowed": False}
                events[(self.manifest[fid]["origin"], system)].append((t, 0, fid, f, None))
        if need_explicit and action != "RETAIN" and not any(e[1] for ev in events.values() for e in ev):
            return None
        if not events and action == "RETAIN":      # standing retention record: fall back to any sighting
            for o in self.by_rid.get(rid, []):
                events[self.store_of(o)].append((o.t, 1, o.file_id, facts(o), o))
        if not events:
            return None
        latest = {s: max(ev, key=lambda e: (e[0], e[1])) for s, ev in events.items()}
        bad = [e for e in latest.values() if violates(action, e[3])]
        conflict = bool(bad) and len(bad) < len(latest)
        if action == "RETAIN":
            best = max(latest.values(), key=lambda e: (e[0], e[1]))
            return {"action": action, "violated": False, "file": best[2], "obs": best[4], "t": best[0]}
        if bad:
            best = max(bad, key=lambda e: (e[0], e[1]))
            return {"action": action, "violated": True, "file": best[2], "obs": best[4], "t": best[0],
                    "conflict": conflict}
        pool = list(latest.values())
        best = max(pool, key=lambda e: (e[1], e[0]))      # prefer explicit proof over omission
        return {"action": action, "violated": False, "file": best[2], "obs": best[4], "t": best[0]}

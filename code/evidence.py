"""Evidence loading: turns every evidence file into flat `Obs` observations.

An observation says "resource R (in system S) was seen at time T with these
identifiers and this state".  Everything downstream (linking, state
reconstruction, policy evaluation) works on observations only, so format quirks
stay in this module.
"""
import csv
import json
import re
import sqlite3
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

PREFIX_SYSTEM = {
    "account": "account_service",
    "search": "search_service",
    "support": "support_platform",
    "analytics": "analytics_platform",
    "export": "export_service",
    "backup": "backup_service",
    "data_flow": "integration_service",
    "audit_record": "security_service",
    "tombstone": "identity_service",
    "marketing": "marketing_platform",
    "object": "object_storage",
    "cache": "cache_service",
    "email_delivery": "email_delivery_service",
    "legal_hold": "legal_service",
}
RID_RE = re.compile(r"\b(" + "|".join(PREFIX_SYSTEM) + r")_[A-Za-z0-9]+\b")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
HASH_RE = re.compile(r"\b[0-9a-f]{64}\b")
USER_RE = re.compile(r"\buser_\d+\b")
PHONE_RE = re.compile(r"\+\d[\d ()\-]{6,}\d")


def system_of(rid):
    m = RID_RE.fullmatch(rid or "")
    return PREFIX_SYSTEM[m.group(1)] if m else None


@dataclass
class Obs:
    file_id: str
    captured_at: str          # file level capture time
    when: str                 # observation time (falls back to captured_at)
    rid: str
    system: str
    source: str = ""          # file kind / table / event, for debugging
    emails: set = field(default_factory=set)
    hashes: set = field(default_factory=set)
    users: set = field(default_factory=set)
    phones: set = field(default_factory=set)
    names: set = field(default_factory=set)
    attrs: dict = field(default_factory=dict)   # normalised state attributes
    t: str = ""               # time this observation speaks for (snapshot time for snapshots)

    def __post_init__(self):
        self.t = self.t or self.when

    def idents(self):
        return self.emails | self.hashes | self.users | self.phones


def norm_email(e):
    return e.strip().lower() if isinstance(e, str) else e


def norm_phone(p):
    return re.sub(r"\D", "", p) if isinstance(p, str) else p


def collect(value, obs):
    """Pull identifiers out of an arbitrary scalar/str into obs."""
    if not isinstance(value, str):
        return
    for e in EMAIL_RE.findall(value):
        obs.emails.add(norm_email(e))
    for h in HASH_RE.findall(value):
        obs.hashes.add(h)
    for u in USER_RE.findall(value):
        obs.users.add(u)


def collect_key(key, value, obs):
    if value is None or value == "":
        return
    k = key.lower()
    if isinstance(value, str):
        if "phone" in k:
            obs.phones.add(norm_phone(value))
        elif "name" in k and "file" not in k and "connector" not in k and "index" not in k and "event" not in k:
            obs.names.add(value.strip().lower())
        collect(value, obs)


def flat_items(d, prefix=""):
    for k, v in d.items():
        if isinstance(v, dict):
            yield from flat_items(v, k + ".")
        elif isinstance(v, list):
            for i in v:
                if isinstance(i, dict):
                    yield from flat_items(i, k + ".")
                else:
                    yield prefix + k, i
        else:
            yield prefix + k, v


# attribute keys we keep verbatim (lower-cased value)
STATE_KEYS = {
    "result", "status_code", "http_status", "rows", "enabled", "restore_allowed", "download_available",
    "account_status", "status", "record_type", "event_code", "event_name", "retention_until",
    "last_delivery_status", "mode", "state", "reported_state", "legal_hold", "hold_status",
    "expires_at", "mode", "ticket_id", "message_text", "message_excerpt", "attachment",
    "uploaded_by", "storage_class", "audience_cohort", "connector_name", "destination",
    "eligible", "deletion_block", "decision", "marker_found", "email_opt_in", "last_run",
}


def make_obs(file_id, captured, rec, system=None, source="", rid=None):
    rid = rid or rec.get("resource_id") or rec.get("id")
    if not rid or not RID_RE.fullmatch(str(rid)):
        return None
    when = (rec.get("observed_at") or rec.get("recorded_at") or rec.get("updated_at")
            or rec.get("indexed_at") or captured)
    o = Obs(file_id, captured, when, rid, system or system_of(rid), source)
    for k, v in flat_items(rec):
        base = k.split(".")[-1]
        collect_key(base, v, o)
        if base.lower() in STATE_KEYS or base in ("enabled",):
            o.attrs[base.lower()] = v
        if base == "profile" and v is None:
            o.attrs["profile"] = None
    if "profile" in rec and rec["profile"] is None:
        o.attrs["profile_null"] = True
    if isinstance(rec.get("profile"), dict):
        o.attrs["profile_fields"] = {k: v for k, v in rec["profile"].items()}
    return o


def load_manifest(dataset):
    out = {}
    with open(dataset / "evidence_files.csv", newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            out[r["file_id"]] = r
    return out


# ------------------------------------------------------------------ formats
def parse_json(file_id, captured, path):
    """Returns (observations, coverage) where coverage maps system -> time the file speaks for."""
    data = json.loads(path.read_text(encoding="utf-8"))
    out = []
    cov = {}

    def walk(node, snap_time=None, source=""):
        if isinstance(node, dict):
            if "resource_id" in node:
                o = make_obs(file_id, captured, node, system=None, source=source)
                if o:
                    if snap_time:
                        o.t = snap_time
                    out.append(o)
                return
            if "data_store" in node and "records" in node:     # snapshot-bundle collection
                snap_time = node.get("captured_at") or captured
                cov[node["data_store"]] = snap_time
            for k, v in node.items():
                walk(v, snap_time, source + "/" + k)
        elif isinstance(node, list):
            for i in node:
                walk(i, snap_time, source)

    walk(data, source=path.name)
    return out, cov


TABLE_SYSTEM = {
    "customer_profiles": "account_service", "customer_profiles_primary": "account_service",
    "customer_profiles_failover_replica": "account_service",
    "search_documents_primary": "search_service", "customer_search_documents": "search_service",
}


def parse_sql(file_id, captured, path):
    text = path.read_text(encoding="utf-8")
    con = sqlite3.connect(":memory:")
    con.executescript(text)
    con.row_factory = sqlite3.Row
    out = []
    scope = {}
    tables = [r[0] for r in con.execute("select name from sqlite_master where type='table'")]
    if "snapshot_scope" in tables:
        scope = {r[0]: r[1] for r in con.execute("select origin_system, captured_at from snapshot_scope")}
    else:
        for t in tables:
            hint = TABLE_SYSTEM.get(t)
            if hint:
                scope[hint] = captured
    for t in tables:
        if t == "snapshot_scope":
            continue
        for row in con.execute(f"select * from {t}"):
            rec = dict(row)
            for k, v in list(rec.items()):          # wide tables carry the record as a JSON payload column
                if isinstance(v, str) and v.startswith("{"):
                    try:
                        payload = json.loads(v)
                    except ValueError:
                        continue
                    del rec[k]
                    for pk, pv in payload.items():
                        rec.setdefault(pk, pv)
            o = make_obs(file_id, captured, rec, source=f"sql:{t}")
            if o:
                o.attrs["table"] = t
                o.t = scope.get(o.system, captured)
                scope.setdefault(o.system, captured)
                out.append(o)
    m = re.search(r"Database topology: (\w+)", text)
    for o in out:
        o.attrs["topology"] = m.group(1) if m else ""
    return out, scope


PIPE_RE = re.compile(r"^-\s*(\S+)\s*\|\s*(\S+)\s*\|\s*(\S+)\s*\|\s*(\S+)\s*\|\s*(\S+)\s*\|\s*(.*)$")


def parse_text_handover(file_id, captured, path):
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        m = PIPE_RE.match(line)
        if not m:
            continue
        when, system, rid, rtype, result, subj = m.groups()
        o = Obs(file_id, captured, when, rid, system, "handover")
        o.attrs.update({"record_type": rtype.lower(), "result": result.lower()})
        collect(subj, o)
        if "no direct identifier" in subj.lower():
            o.attrs["no_identifier"] = True
        out.append(o)
    return out


KV_RE = re.compile(r'(\w+)=(?:"((?:[^"\\]|\\.)*)"|(\S+))')


def parse_kv(text):
    d = {}
    for m in KV_RE.finditer(text):
        d[m.group(1)] = m.group(2) if m.group(2) is not None else m.group(3)
    return d


def log_events(path):
    """Yield (timestamp, dict-of-fields) for each log line in any supported layout."""
    for raw in path.read_text(encoding="utf-8").splitlines():
        raw = raw.strip()
        if not raw:
            continue
        ts, _, rest = raw.partition(" ")
        d = {}
        if rest.startswith("{"):
            try:
                d = json.loads(rest)
            except Exception:
                d = parse_kv(rest)
        elif rest.split(" ", 1)[0] in ("DEBUG", "INFO", "WARN", "ERROR") and " | " in rest:
            parts = [p.strip() for p in rest.split(" | ")]
            d = {"level": parts[0], "service": parts[1], "trace_id": parts[2], "event": parts[3]}
            d.update(parse_kv(" | ".join(parts[4:])))
        else:
            d = parse_kv(rest)
            if "message" in d and "event=" in d["message"].replace('\\"', '"'):
                inner = parse_kv(d["message"].replace('\\"', '"'))
                d.update(inner)
                d["service"] = d.get("function", d.get("service"))
                d["trace_id"] = d.get("requestId", d.get("trace_id"))
        if rest.startswith("<"):   # syslog
            m = re.match(r"<\d+>1 (\S+) (\S+) (\S+) - - (.*)", rest)
            if m:
                d = parse_kv(m.group(4))
                d["service"] = m.group(2)
                d["trace_id"] = m.group(3)
        yield ts, d


def parse_log(file_id, captured, path):
    out = []
    pending = {}   # trace_id -> lookup identifier(s) seen in the *_started line
    for ts, d in log_events(path):
        ev = d.get("event", "")
        trace = d.get("trace_id") or d.get("requestId")
        if ev.endswith("_started") or ev in ("message_scan_started",):
            for k in ("lookup_key", "match_key", "subject_key", "scan_key", "subject_ref", "correlation_key"):
                if d.get(k) and d.get(k) != "null":
                    pending.setdefault(trace, []).append(d[k])
        rid = d.get("resource_id")
        if ev.endswith("_started"):       # a *_started line carries only the lookup key, not a state
            continue
        if rid and RID_RE.fullmatch(rid):
            o = Obs(file_id, captured, ts, rid, system_of(rid), f"log:{ev}")
            for k, v in d.items():
                if v in (None, "", "null"):
                    continue
                collect_key(k, str(v), o)
                if k.lower() in STATE_KEYS:
                    o.attrs[k.lower()] = v
            for k in ("lookup_key", "match_key", "subject_key", "scan_key", "subject_ref", "correlation_key"):
                if d.get(k) and d.get(k) != "null":
                    collect(d[k], o)
            for v in pending.get(trace, []):
                collect(v, o)
            o.attrs["event"] = ev
            out.append(o)
    return out


def pdf_text(path):
    return subprocess.run(["pdftotext", "-layout", str(path), "-"], capture_output=True, text=True).stdout


def load_all(dataset):
    """Returns (observations, manifest, file_kinds)."""
    manifest = load_manifest(dataset)
    obs = []
    extras = {}      # file_id -> {system: time} coverage of snapshot-style files
    for fid, row in manifest.items():
        path = dataset / row["file_path"]
        cap = row["captured_at"]
        suffix = path.suffix.lower()
        if suffix == ".json":
            o, cov = parse_json(fid, cap, path)
            obs += o
            if cov:
                extras[fid] = cov
        elif suffix == ".sql":
            o, scope = parse_sql(fid, cap, path)
            obs += o
            extras[fid] = scope
        elif suffix == ".log":
            obs += parse_log(fid, cap, path)
        elif suffix == ".txt":
            obs += parse_text_handover(fid, cap, path)
        # PDFs / PNGs are handled by the multimodal reader (see multimodal.py)
    import multimodal
    obs += multimodal.load_documents(dataset, manifest)
    return obs, manifest, extras

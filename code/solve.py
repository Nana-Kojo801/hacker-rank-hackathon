"""Case solving glue: identity -> linked resources -> states -> plan."""
import csv
import json
from datetime import timedelta
from pathlib import Path

import evidence
from engine import World, P, system_of
from identity import IdentityBook
import planner


def load_world(dataset):
    obs, manifest, cov = evidence.load_all(dataset)
    with open(dataset / "system_activity.csv", newline="", encoding="utf-8") as f:
        acts = list(csv.DictReader(f))
    return World(obs, manifest, cov, acts, IdentityBook(dataset))


def retention_ok(audit_at):
    def check(rid, st):
        o = st.get("obs")
        ru = o.attrs.get("retention_until") if o else None
        return (not ru) or ru >= audit_at
    return check


def solve_case(world, q, extra_rids=()):
    user = world.book.resolve(q["email"])
    audit_at = q["audit_at"]
    rids = set(world.linked_rids(user, audit_at)) | set(extra_rids)
    states = {}
    for rid in rids:
        st = world.state(rid, audit_at)
        if st:
            states[rid] = st
    status, steps = planner.plan(states, audit_at, retention_ok(audit_at))
    return status, steps

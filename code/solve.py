"""Case solving glue: identity -> linked resources -> states -> plan."""
import csv

import evidence
from engine import World
from identity import IdentityBook
from linking import Linker
import planner


def load_world(dataset):
    obs, manifest, cov = evidence.load_all(dataset)
    with open(dataset / "system_activity.csv", newline="", encoding="utf-8") as f:
        acts = list(csv.DictReader(f))
    return World(obs, manifest, cov, acts, IdentityBook(dataset))


def prune_accounts(world, q, rids):
    """A user can have several old account lookups; keep the one tied to this request's deletion run."""
    from datetime import timedelta
    from engine import P
    accs = [r for r in rids if r.startswith("account_") and r in world.worker_ops]
    if len(accs) < 2:
        return rids
    t0 = P(q["reported_at"])
    near = {r for r in accs if any(t0 - timedelta(hours=2) <= a["_t"] <= t0 + timedelta(hours=3) for a in world.worker_ops[r])}
    return {r for r in rids if r not in accs or r in near} if near else rids


def evaluate_all(world, q, rids, need_explicit=True):
    states = {}
    for rid in rids:
        st = world.evaluate(rid, q["requested_at"], q["audit_at"], need_explicit=need_explicit)
        if st:
            states[rid] = st
    return states


class Solver:
    """Solves cases against one world; `all_cases` is every request known (samples + evaluation)."""

    def __init__(self, world, all_cases):
        self.w = world
        prelim = {}
        for q in all_cases:
            u = world.book.resolve(q["email"])
            prelim[q["case_id"]] = planner.plan(evaluate_all(world, q, prune_accounts(world, q, set(world.linked_rids(u)))))[0]
        self.linker = Linker(world, all_cases, prelim)

    def solve(self, q):
        user = self.w.book.resolve(q["email"])
        rids = prune_accounts(self.w, q, set(self.w.linked_rids(user)))
        states = evaluate_all(self.w, q, rids)
        for rid in self.linker.extra_rids(q["case_id"]):
            st = self.w.evaluate(rid, q["requested_at"], q["audit_at"], need_explicit=False)
            if st:
                states[rid] = st
        return planner.plan(states)

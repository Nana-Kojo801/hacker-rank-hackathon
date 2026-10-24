"""Case solving glue: identity -> linked resources -> states -> plan."""
import csv

import evidence
from engine import World
from identity import IdentityBook
import planner


def load_world(dataset):
    obs, manifest, cov = evidence.load_all(dataset)
    with open(dataset / "system_activity.csv", newline="", encoding="utf-8") as f:
        acts = list(csv.DictReader(f))
    return World(obs, manifest, cov, acts, IdentityBook(dataset))


def resources_for(world, q, user):
    return set(world.linked_rids(user))


def solve_case(world, q):
    user = world.book.resolve(q["email"])
    states = {}
    for rid in resources_for(world, q, user):
        st = world.evaluate(rid, q["requested_at"], q["audit_at"])
        if st:
            states[rid] = st
    return planner.plan(states)

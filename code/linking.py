"""Attach identifier-less resources (accounts, anonymised analytics rows) to cases.

Some resources carry no identifier in any evidence file (a 404 account profile, an anonymised analytics
row).  The only link left is the deletion worker's activity stream.  Rows of one case share a sub-minute
phase relative to the case's account row, and the offset per row type is stable, so we

  1. take account rows near the case's `reported_at` whose result matches the reported status,
  2. resolve unique candidates by elimination,
  3. learn the seconds-offset histogram per row type from those resolved cases (self-calibration, no labels),
  4. resolve the remaining ambiguous groups with that likelihood, and
  5. attach leftover ANONYMIZE rows the same way.
"""
import itertools
import math
from collections import Counter, defaultdict
from datetime import timedelta

from engine import P

RESULT_FOR_STATUS = {"COMPLETE": "SUCCESS", "PARTIALLY_COMPLETE": "PARTIAL", "NOT_STARTED": "FAILED"}
ACCOUNT_WINDOW = (-1.4, -0.6)     # hours relative to reported_at
ANALYTICS_WINDOW = (-0.8, -0.2)


def phase(row):
    return row["_t"].second


class Linker:
    def __init__(self, world, cases, prelim):
        self.w = world
        self.cases = cases
        self.prelim = prelim       # case_id -> status from identifier-linked evidence alone
        self.linked = {}
        self.claimed = set()
        for q in cases:
            u = world.book.resolve(q["email"])
            rids = world.linked_rids(u) if u else set()
            self.linked[q["case_id"]] = rids
            self.claimed |= rids
        self.rows = [a for a in world.activity if a["source_system"] == "deletion_worker"]
        self.account_rows = [a for a in self.rows if a["target_system"] == "account_service" and a["event_type"] == "DELETE_RECORD"]
        self.anon_rows = [a for a in self.rows if a["event_type"] == "ANONYMIZE_RECORD" and a["target_system"] == "analytics_platform"]
        self.account = {}          # case_id -> account rid
        self.analytics = {}        # case_id -> anonymised analytics rid
        self.hist = defaultdict(Counter)
        self._assign_accounts()
        self._assign_analytics()

    # ------------------------------------------------------------ helpers
    def _window(self, q, lo, hi):
        t0 = P(q["reported_at"])
        return lo, hi, t0

    def _candidates(self, q, rows, win, taken, strict_result=True):
        t0 = P(q["reported_at"])
        lo, hi = win
        out = []
        want = RESULT_FOR_STATUS.get(q["reported_status"])
        for a in rows:
            if a["resource_id"] in self.claimed or a["resource_id"] in taken:
                continue
            if not (t0 + timedelta(hours=lo) <= a["_t"] <= t0 + timedelta(hours=hi)):
                continue
            if strict_result and a["reported_result"] != want:
                continue
            out.append(a)
        return out

    def _known_rows(self, cid):
        """Worker rows of this case's identifier-linked, non-account resources."""
        out = []
        for rid in self.linked[cid]:
            if rid.startswith("account_"):
                continue
            for a in self.w.worker_ops.get(rid, []):
                out.append(a)
        return out

    @staticmethod
    def _kind(a):
        return (a["target_system"], a["event_type"], a["reported_result"])

    def _loglik(self, base, known):
        s = 0.0
        for k in known:
            h = self.hist.get(self._kind(k))
            if not h:
                continue
            tot = sum(h.values())
            r = (phase(k) - phase(base)) % 60
            p = sum(h[(r + d) % 60] for d in (-1, 0, 1)) / tot
            s += math.log(p + 0.02)
        return s

    # ------------------------------------------------------------ accounts
    def _assign_accounts(self):
        taken = set()
        for q in self.cases:
            for rid in self.linked[q["case_id"]]:
                if rid.startswith("account_") and rid in self.w.worker_ops:
                    t0 = P(q["reported_at"])
                    if any(t0 - timedelta(hours=2) <= a["_t"] <= t0 + timedelta(hours=3) for a in self.w.worker_ops[rid]):
                        self.account[q["case_id"]] = rid
        cases = [q for q in self.cases if q["case_id"] not in self.account]
        # 1. unique elimination (iterate)
        changed = True
        pool = {q["case_id"]: q for q in cases}
        while changed:
            changed = False
            for cid, q in list(pool.items()):
                c = self._candidates(q, self.account_rows, ACCOUNT_WINDOW, taken)
                if len(c) == 1:
                    self.account[cid] = c[0]["resource_id"]
                    taken.add(c[0]["resource_id"])
                    del pool[cid]
                    changed = True
        self._calibrate()
        # 2. resolve ambiguous groups by likelihood
        groups = defaultdict(list)
        for cid, q in pool.items():
            groups[q["reported_at"]].append(q)
        for rep, qs in groups.items():
            cand = {}
            for q in qs:
                cand[q["case_id"]] = self._candidates(q, self.account_rows, ACCOUNT_WINDOW, taken)
            allrows = {a["resource_id"]: a for c in cand.values() for a in c}
            if not allrows:
                continue
            ids = [q["case_id"] for q in qs]
            rids = list(allrows)
            best, best_s = None, -1e9
            n = min(len(ids), len(rids))
            for chosen in itertools.permutations(rids, n):
                s = 0.0
                ok = True
                for cid, rid in zip(ids, chosen):
                    if allrows[rid] not in cand[cid]:
                        ok = False
                        break
                    s += self._loglik(allrows[rid], self._known_rows(cid))
                if ok and s > best_s:
                    best, best_s = chosen, s
            if best is None:        # relax result matching
                for cid, q in ((q["case_id"], q) for q in qs):
                    cand[cid] = self._candidates(q, self.account_rows, ACCOUNT_WINDOW, taken, strict_result=False)
                allrows = {a["resource_id"]: a for c in cand.values() for a in c}
                rids = list(allrows)
                n = min(len(ids), len(rids))
                for chosen in itertools.permutations(rids, n):
                    s = sum(self._loglik(allrows[r], self._known_rows(c)) for c, r in zip(ids, chosen))
                    if s > best_s:
                        best, best_s = chosen, s
            if best:
                for cid, rid in zip(ids, best):
                    self.account[cid] = rid
                    taken.add(rid)
        # 3. hand-built cases log their deletion call right at reported_at instead of an hour earlier
        for q in self.cases:
            if q["case_id"] in self.account:
                continue
            c = self._candidates(q, self.account_rows, (-0.3, 0.3), taken, strict_result=False)
            if len(c) == 1:
                self.account[q["case_id"]] = c[0]["resource_id"]
                taken.add(c[0]["resource_id"])
        self.taken_accounts = taken

    def _has_account_link(self, cid):
        return any(r.startswith("account_") and self._is_worker_target(r) for r in self.linked[cid])

    def _is_worker_target(self, rid):
        return rid in self.w.worker_ops

    def _calibrate(self):
        rowof = {a["resource_id"]: a for a in self.account_rows}
        for cid, rid in self.account.items():
            base = rowof[rid]
            for k in self._known_rows(cid):
                self.hist[self._kind(k)][(phase(k) - phase(base)) % 60] += 1

    # ------------------------------------------------------------ analytics
    def _assign_analytics(self):
        """Attach anonymised analytics rows to cases whose identifier-linked evidence looks complete."""
        rowof = {a["resource_id"]: a for a in self.account_rows}
        need = [q for q in self.cases
                if q["case_id"] in self.account and self.prelim.get(q["case_id"]) == "COMPLETE"
                and not any(r.startswith("analytics_") for r in self.linked[q["case_id"]])]
        taken = set()
        pending = {q["case_id"]: q for q in need}
        kind = ("analytics_platform", "ANONYMIZE_RECORD", "SUCCESS")
        # pass 1: unique candidate by elimination, used to learn the phase offset
        changed = True
        while changed:
            changed = False
            for cid, q in list(pending.items()):
                c = self._candidates(q, self.anon_rows, ANALYTICS_WINDOW, taken, strict_result=False)
                if len(c) == 1 and sum(1 for p in pending.values() if p["reported_at"] == q["reported_at"]) == 1:
                    self.analytics[cid] = c[0]["resource_id"]
                    taken.add(c[0]["resource_id"])
                    base = rowof[self.account[cid]]
                    self.hist[kind][(phase(c[0]) - phase(base)) % 60] += 1
                    del pending[cid]
                    changed = True
        # pass 2: likelihood within the remaining groups
        groups = defaultdict(list)
        for cid, q in pending.items():
            groups[q["reported_at"]].append(q)
        for rep, qs in groups.items():
            scored = []
            for q in qs:
                base = rowof[self.account[q["case_id"]]]
                for a in self._candidates(q, self.anon_rows, ANALYTICS_WINDOW, taken, strict_result=False):
                    r = (phase(a) - phase(base)) % 60
                    h = self.hist.get(kind)
                    tot = sum(h.values()) if h else 0
                    p = (sum(h[(r + d) % 60] for d in (-1, 0, 1)) / tot) if tot else 0.5
                    scored.append((p, q["case_id"], a["resource_id"]))
            scored.sort(reverse=True)
            used_c, used_r = set(), set()
            for p, cid, rid in scored:
                if p < 0.15 or cid in used_c or rid in used_r:
                    continue
                self.analytics[cid] = rid
                used_c.add(cid)
                used_r.add(rid)
            taken |= used_r

    # ------------------------------------------------------------ output
    def extra_rids(self, cid):
        out = set()
        if cid in self.account:
            out.add(self.account[cid])
        if cid in self.analytics:
            out.add(self.analytics[cid])
        return out

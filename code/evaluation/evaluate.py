"""Scoring helpers shared by the sample run, the custom cases and the report generator."""
import json
from difflib import SequenceMatcher

FIELDS = ("phase", "system_id", "resource_id", "operation", "state", "evidence_id")


def key(s):
    return tuple(s[f] for f in FIELDS)


def lcs_ratio(a, b):
    if not a and not b:
        return 1.0
    return SequenceMatcher(None, a, b, autojunk=False).ratio()


def score(pred_rows, gold_rows):
    n = len(gold_rows)
    status_ok = exact = 0
    tp = n_pred = n_gold = 0
    field_ok = field_tot = 0
    order_scores = []
    for cid, g in gold_rows.items():
        p = pred_rows.get(cid)
        gs = json.loads(g["steps_json"])
        ps = json.loads(p["steps_json"]) if p else []
        status_ok += bool(p) and p["deletion_status"] == g["deletion_status"]
        gk, pk = [key(s) for s in gs], [key(s) for s in ps]
        exact += gk == pk
        n_gold += len(gk)
        n_pred += len(pk)
        tp += len(set(gk) & set(pk))
        order_scores.append(lcs_ratio(gk, pk))
        for i, s in enumerate(gs):
            for f in FIELDS:
                field_tot += 1
                field_ok += i < len(ps) and ps[i][f] == s[f]
    prec = tp / n_pred if n_pred else 1.0
    rec = tp / n_gold if n_gold else 1.0
    return {
        "cases": n,
        "status_accuracy": status_ok / n,
        "step_precision": prec,
        "step_recall": rec,
        "step_f1": 2 * prec * rec / (prec + rec) if prec + rec else 0.0,
        "field_accuracy": field_ok / field_tot if field_tot else 1.0,
        "sequence_exact_match": exact / n,
        "sequence_similarity": sum(order_scores) / n,
        "steps_expected": n_gold,
        "steps_predicted": n_pred,
        "steps_matched": tp,
    }


def diff(pred_row, gold_row):
    """Human-readable missing/extra steps for one case."""
    gs = {key(s) for s in json.loads(gold_row["steps_json"])}
    ps = {key(s) for s in json.loads(pred_row["steps_json"])}
    fmt = lambda k: f"{k[3]} {k[2]} [{k[5] or '-'}]"
    return sorted(map(fmt, gs - ps)), sorted(map(fmt, ps - gs))

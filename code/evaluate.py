"""Score predictions against sample_output.csv."""
import csv
import json
import sys
from pathlib import Path


def key(s):
    return (s["phase"], s["system_id"], s["resource_id"], s["operation"], s["state"], s["evidence_id"])


def score(pred_rows, gold_rows):
    n = len(gold_rows)
    status_ok = exact = 0
    step_tp = step_pred = step_gold = 0
    field_ok = field_tot = 0
    for cid, g in gold_rows.items():
        p = pred_rows.get(cid)
        gs = json.loads(g["steps_json"])
        ps = json.loads(p["steps_json"]) if p else []
        status_ok += bool(p) and p["deletion_status"] == g["deletion_status"]
        gk, pk = [key(s) for s in gs], [key(s) for s in ps]
        exact += gk == pk
        step_gold += len(gk)
        step_pred += len(pk)
        step_tp += len(set(gk) & set(pk))
        for i, s in enumerate(gs):
            for f in ("phase", "system_id", "resource_id", "operation", "state", "evidence_id"):
                field_tot += 1
                field_ok += i < len(ps) and ps[i][f] == s[f]
    prec = step_tp / step_pred if step_pred else 1.0
    rec = step_tp / step_gold if step_gold else 1.0
    return {"cases": n, "status_acc": status_ok / n, "sequence_exact": exact / n,
            "step_precision": prec, "step_recall": rec,
            "step_f1": 2 * prec * rec / (prec + rec) if prec + rec else 0.0,
            "field_acc": field_ok / field_tot if field_tot else 1.0}

"""Runs the public samples and the custom cases, then writes evaluation/evaluation_report.md.

  python3 code/evaluation/run_evaluation.py [--no-llm]
"""
import argparse
import json
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
import evaluate  # noqa: E402
import main as agent  # noqa: E402

ROOT = HERE.parent.parent


def run_set(dataset, requests_name, gold_name, all_extra, use_llm):
    reqs = agent.read(dataset, requests_name)
    rows = agent.run(dataset, reqs, reqs + all_extra, use_llm)
    gold = {r["case_id"]: r for r in agent.read(dataset, gold_name)}
    pred = {r["case_id"]: r for r in rows}
    return evaluate.score(pred, gold), pred, gold


def fmt(m):
    return (f"| cases | {m['cases']} |\n| status accuracy | {m['status_accuracy']:.1%} |\n"
            f"| step precision | {m['step_precision']:.1%} |\n| step recall | {m['step_recall']:.1%} |\n"
            f"| step F1 | {m['step_f1']:.1%} |\n| field accuracy (positional) | {m['field_accuracy']:.1%} |\n"
            f"| sequence exact match | {m['sequence_exact_match']:.1%} |\n"
            f"| sequence similarity (order-aware) | {m['sequence_similarity']:.1%} |\n"
            f"| steps matched / expected / predicted | {m['steps_matched']} / {m['steps_expected']} / {m['steps_predicted']} |\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-llm", action="store_true")
    a = ap.parse_args()
    use_llm = not a.no_llm
    ds = ROOT / "dataset"
    full_reqs = agent.read(ds, "deletion_requests.csv")
    m1, pred1, gold1 = run_set(ds, "sample_deletion_requests.csv", "sample_output.csv", full_reqs, use_llm)
    cds = HERE / "custom_cases" / "dataset"
    m2, pred2, gold2 = run_set(cds, "deletion_requests.csv", "expected_output.csv", [], use_llm)

    lines = [f"# Evaluation report\n\nGenerated {date.today().isoformat()} by `code/evaluation/run_evaluation.py` "
             f"({'with model calls' if use_llm else 'deterministic mode, no model calls'}).\n"]
    lines.append("## 1. Public sample set (32 cases, `dataset/sample_output.csv`)\n\n| metric | value |\n| --- | --- |\n" + fmt(m1))
    lines.append("Definitions: *step precision/recall* compare the set of (phase, system, resource, operation, state, "
                 "evidence) tuples; *field accuracy* compares each field of the expected step at the same position; "
                 "*sequence exact match* requires the whole ordered array to be identical; *sequence similarity* is the "
                 "order-aware ratio of the longest matching subsequence.\n")
    lines.append("### Remaining differences on the samples\n")
    any_diff = False
    for cid in sorted(gold1):
        miss, extra = evaluate.diff(pred1[cid], gold1[cid])
        if miss or extra or pred1[cid]["deletion_status"] != gold1[cid]["deletion_status"]:
            any_diff = True
            lines.append(f"* `{cid}` expected {gold1[cid]['deletion_status']}, got {pred1[cid]['deletion_status']}; "
                         f"missing: {', '.join(miss) or 'none'}; extra: {', '.join(extra) or 'none'}")
    if not any_diff:
        lines.append("* none")
    lines.append("\n## 2. Additional cases created by the team (`code/evaluation/custom_cases`)\n")
    lines.append("A small synthetic dataset with the same schema, built by `build_custom_cases.py`, with answers derived "
                 "by hand from `deletion_rules.csv`.\n\n| case | behaviour exercised |\n| --- | --- |\n"
                 "| x1 | request e-mail is a *historical* address; the account survives only in a read replica (replication drift) |\n"
                 "| x2 | non-deletion request written in Spanish (must be `NOT_APPLICABLE`, `[]`) |\n"
                 "| x3 | a later snapshot (after `audit_at`) shows the account again and must be ignored |\n"
                 "| x4 | active data flow + restorable backup + tombstone still exposing the e-mail; checks ordering of findings, remediation and verification |\n")
    lines.append("| metric | value |\n| --- | --- |\n" + fmt(m2))
    for cid in sorted(gold2):
        miss, extra = evaluate.diff(pred2[cid], gold2[cid])
        ok = not miss and not extra and pred2[cid]["deletion_status"] == gold2[cid]["deletion_status"]
        lines.append(f"* `{cid}`: {'PASS' if ok else 'FAIL'} ({pred2[cid]['deletion_status']})"
                     + ("" if ok else f" missing: {', '.join(miss)}; extra: {', '.join(extra)}"))
    out = HERE / "evaluation_report.md"
    existing = out.read_text(encoding="utf-8") if out.exists() else ""
    tail = existing.split("<!-- manual -->", 1)[1] if "<!-- manual -->" in existing else ""
    out.write_text("\n".join(lines) + "\n\n<!-- manual -->" + tail, encoding="utf-8")
    print(json.dumps({"samples": m1, "custom": m2}, indent=2))


if __name__ == "__main__":
    main()

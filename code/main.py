"""Ghost Data audit agent.

Usage:
  python3 code/main.py                 # audit dataset/deletion_requests.csv -> output.csv (repo root)
  python3 code/main.py --no-llm        # deterministic only (no model calls)
  python3 code/main.py --samples       # score the 32 public samples against sample_output.csv
  python3 code/main.py --dataset DIR --output FILE
"""
import argparse
import csv
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import classify  # noqa: E402
import solve  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATASET = ROOT / "dataset"


def read(dataset, name):
    path = dataset / name
    if not path.exists():
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def run(dataset, requests, all_cases, use_llm=True):
    """Return output rows (sorted by case_id) for `requests`; `all_cases` is every known request."""
    world = solve.load_world(dataset)
    solver = solve.Solver(world, all_cases)
    out = []
    for q in sorted(requests, key=lambda r: r["case_id"]):
        ok, _method = classify.authorizes_deletion(q["request_text"], use_llm)
        status, steps = solver.solve(q) if ok else ("NOT_APPLICABLE", [])
        out.append({"case_id": q["case_id"], "deletion_status": status,
                    "steps_json": json.dumps(steps, separators=(",", ":"), ensure_ascii=False)})
    return out


def write(rows, path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["case_id", "deletion_status", "steps_json"])
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-llm", action="store_true", help="skip model calls (deterministic fallbacks only)")
    ap.add_argument("--samples", action="store_true", help="score the public samples")
    ap.add_argument("--dataset", type=Path, default=DATASET)
    ap.add_argument("--output", type=Path, default=ROOT / "output.csv")
    a = ap.parse_args()
    if a.no_llm:
        os.environ["AUDIT_NO_LLM"] = "1"       # also disables the vision fallback inside evidence loading
    reqs = read(a.dataset, "deletion_requests.csv")
    samples = read(a.dataset, "sample_deletion_requests.csv")
    if a.samples:
        sys.path.insert(0, str(Path(__file__).parent / "evaluation"))
        import evaluate
        rows = run(a.dataset, samples, samples + reqs, not a.no_llm)
        gold = {r["case_id"]: r for r in read(a.dataset, "sample_output.csv")}
        print(json.dumps(evaluate.score({r["case_id"]: r for r in rows}, gold), indent=2))
    else:
        rows = run(a.dataset, reqs, samples + reqs, not a.no_llm)
        write(rows, a.output)
        print(f"wrote {len(rows)} rows to {a.output}")

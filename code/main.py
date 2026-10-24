"""Ghost Data audit agent.  Usage: python code/main.py [--no-llm] [--samples]

Reads dataset/, writes output.csv at the repository root.
"""
import argparse
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import classify  # noqa: E402
import solve  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
DATASET = ROOT / "dataset"


def read(name):
    with open(DATASET / name, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def run(requests, all_cases, use_llm=True):
    world = solve.load_world(DATASET)
    solver = solve.Solver(world, all_cases)
    out = []
    for q in sorted(requests, key=lambda r: r["case_id"]):
        ok, method = classify.authorizes_deletion(q["request_text"], use_llm)
        if not ok:
            status, steps = "NOT_APPLICABLE", []
        else:
            status, steps = solver.solve(q)
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
    ap.add_argument("--no-llm", action="store_true")
    ap.add_argument("--samples", action="store_true", help="run the public samples and score them")
    a = ap.parse_args()
    reqs, samples = read("deletion_requests.csv"), read("sample_deletion_requests.csv")
    if a.samples:
        import evaluate
        rows = run(samples, samples + reqs, not a.no_llm)
        gold = {r["case_id"]: r for r in read("sample_output.csv")}
        print(json.dumps(evaluate.score({r["case_id"]: r for r in rows}, gold), indent=2))
    else:
        rows = run(reqs, samples + reqs, not a.no_llm)
        write(rows, ROOT / "output.csv")
        print(f"wrote {len(rows)} rows to output.csv")

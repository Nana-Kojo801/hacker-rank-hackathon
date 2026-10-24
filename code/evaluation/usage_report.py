"""Summarise model usage of the final run into evaluation/usage_report.md.

  python3 code/evaluation/usage_report.py [--cases 518]

Reads code/.cache/usage.jsonl (one JSON line per *uncached* model call, appended by llm.py).  Delete that file
(and code/.cache/llm/) before the final full run so the report describes exactly that run.
"""
import argparse
import json
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).parent
USAGE = HERE.parent / ".cache" / "usage.jsonl"
# USD per 1M tokens (input, output) - published list prices; edit if your provider's prices differ
PRICES = {"gpt-4o-mini": (0.15, 0.60), "gpt-4o": (2.50, 10.00), "gpt-4.1-mini": (0.40, 1.60), "gpt-4.1": (2.00, 8.00)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", type=int, default=518)
    a = ap.parse_args()
    calls = [json.loads(l) for l in USAGE.read_text().splitlines()] if USAGE.exists() else []
    per = defaultdict(lambda: defaultdict(int))
    for c in calls:
        m = per[(c["model"], c["purpose"])]
        m["calls"] += 1
        m["in"] += c["prompt_tokens"]
        m["out"] += c["completion_tokens"]
    lines = ["# Token usage and cost report\n",
             "Summary of the model calls made by the final full-dataset run that produced `output.csv` "
             f"({a.cases} requests). Everything except request classification and the optional vision fallback is deterministic code, "
             "so the agent makes at most one model call per distinct request text.\n"]
    if not calls:
        lines.append("**No model calls were recorded for this run** (deterministic mode, or every answer was served from the "
                     "on-disk cache). Provider: none. Total tokens: 0. Estimated cost: USD 0.00.\n")
    else:
        lines.append("| provider | model | purpose | calls | input tokens | output tokens | est. cost (USD) |\n| --- | --- | --- | ---: | ---: | ---: | ---: |")
        tot_in = tot_out = tot_calls = 0
        tot_cost = 0.0
        by_model = defaultdict(lambda: [0, 0, 0, 0.0])
        for (model, purpose), m in sorted(per.items()):
            pin, pout = PRICES.get(model, (0.0, 0.0))
            cost = m["in"] / 1e6 * pin + m["out"] / 1e6 * pout
            lines.append(f"| OpenAI | {model} | {purpose} | {m['calls']} | {m['in']} | {m['out']} | {cost:.4f} |")
            tot_in += m["in"]; tot_out += m["out"]; tot_calls += m["calls"]; tot_cost += cost
            b = by_model[model]; b[0] += m["calls"]; b[1] += m["in"]; b[2] += m["out"]; b[3] += cost
        lines.append("\n## Per-model totals\n\n| model | calls | input tokens | output tokens | est. cost (USD) |\n| --- | ---: | ---: | ---: | ---: |")
        for model, b in sorted(by_model.items()):
            lines.append(f"| {model} | {b[0]} | {b[1]} | {b[2]} | {b[3]:.4f} |")
        lines.append("\n## Overall\n")
        lines.append(f"* model calls: {tot_calls}\n* input tokens: {tot_in}\n* output tokens: {tot_out}\n"
                     f"* total tokens: {tot_in + tot_out}\n* average tokens per request: {(tot_in + tot_out) / a.cases:.1f}\n"
                     f"* estimated total cost: USD {tot_cost:.4f}\n* estimated cost per request: USD {tot_cost / a.cases:.6f}\n")
        lines.append("Prices are list prices per million tokens (input/output): " +
                     ", ".join(f"{k} {v[0]}/{v[1]}" for k, v in PRICES.items() if any(k == mm for mm, _ in per)) + ".")
    (HERE / "usage_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()

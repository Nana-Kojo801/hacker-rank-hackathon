# Independent test prompt (give this whole file to a fresh Claude session, and again to ChatGPT with code execution)

You are an independent QA engineer. Verify that the "Ghost Data Still Exists" deletion-audit agent in this repository
works. **Do not edit any file under `code/`, `dataset/` or `output.csv`.** Work in a scratch copy if you need to experiment.
Report findings only. Be adversarial: your job is to find failures, not to confirm success.

## 0. Context

* Repo: `nana-kojo801/hacker-rank-hackathon`, branch `ccr-c9f46477-fkdlnv`.
* Spec: `problem_statement.md` and `AGENTS.md` sections 6.1-6.8 (input/time contract, output contract, operations table,
  decision rules, evidence rules).
* Entry point: `python3 code/main.py`. Design notes: `code/README.md`.
* Ground truth exists only for the 32 public samples (`dataset/sample_output.csv`). Hidden answers exist for the 518
  real requests, so for those you can only check *consistency with the spec*, not correctness. Say so explicitly instead
  of claiming a percentage you cannot measure.

## 1. Setup

```bash
git clone https://github.com/nana-kojo801/hacker-rank-hackathon.git && cd hacker-rank-hackathon
git checkout ccr-c9f46477-fkdlnv
python3 -m pip install -r code/requirements.txt      # rapidocr-onnxruntime
# pdftotext (poppler-utils) must be installed
export OPENAI_API_KEY=...                            # only needed for the model-assisted run (section 3)
```

## 2. Hard gates (all must pass; report the exact command output for each)

1. `python3 code/main.py --no-llm` writes `output.csv`; then `python3 code/evaluation/validate_output.py` prints
   `518 rows, 0 problems` and exits 0.
2. `python3 code/main.py --samples --no-llm` reports `status_accuracy` 1.0 and `step_precision` 1.0. Record
   `step_recall` and `sequence_exact_match` (expected about 0.98 / 0.91; the 3 known misses are `account_004`,
   `audit_record_6645`, `audit_record_5569`, which appear nowhere in participant data - confirm that claim with grep).
3. `python3 code/evaluation/run_evaluation.py --no-llm` shows the 4 custom cases (x1-x4) all passing.
4. **Determinism:** run `python3 code/main.py --no-llm --output /tmp/a.csv` twice (also once after deleting
   `code/.cache`) and `diff` the files: they must be byte-identical.
5. **Format:** independently (do not reuse `validate_output.py`) parse `output.csv` and re-check from the spec: columns
   exactly `case_id,deletion_status,steps_json`; one row per `case_id` in `dataset/deletion_requests.csv`, sorted;
   `steps_json` valid JSON array; `step_no` 1..n; each step has exactly the 7 fields; operation/state pairs match the
   allowed-operations table; phase order FINDING -> REMEDIATION -> VERIFICATION; inside a phase, operation order from
   the table, then `system_id`, then `resource_id` ascending; `NOT_APPLICABLE` rows are exactly `[]`; `COMPLETE` rows
   contain only VERIFICATION steps; findings and COMPLETE verifications have a non-empty `evidence_id`; remediation and
   INCOMPLETE verification steps have an empty one.
6. **Time rule:** for every cited `evidence_id`, `captured_at` in `dataset/evidence_files.csv` must be <= that case's
   `audit_at`. Report any violation with the case id.
7. **No leakage:** grep `code/` for hard-coded case ids, golden labels or reads of `sample_output.csv` outside
   `code/evaluation/` and the `--samples` flag. Grep the repo for secrets (`sk-`, `OPENAI_API_KEY=` with a value). The
   `.env` file must not be tracked (`git ls-files | grep -i env`).
8. **Non-deletion cases:** exactly `case_533`..`case_542` should be `NOT_APPLICABLE` (read their `request_text`
   yourself and confirm each is genuinely not a deletion request, and that no deletion request is wrongly excluded).
   Check the multilingual requests (Spanish, French, Portuguese, Korean, Japanese) are treated as deletions.

## 3. Model-assisted run (needs the key)

```bash
rm -rf code/.cache/llm code/.cache/usage.jsonl
python3 code/main.py --output /tmp/llm.csv
python3 code/evaluation/usage_report.py
diff /tmp/a.csv /tmp/llm.csv        # expected: no differences (the model only classifies requests)
```

Report: number of model calls (expected <= number of distinct `request_text` values, about 375), tokens, estimated cost,
and any `deletion_status` or `steps_json` difference versus the deterministic run. If the model run changes any row,
list the case ids and the request texts. Also test that a missing/invalid key degrades gracefully with `--no-llm`.
The vision fallback in `code/llm.py::chat_vision` is untested: only exercise it if you can, by running with
`rapidocr-onnxruntime` uninstalled and a key set, and say clearly if you did not.

## 4. Adversarial review of the logic (read `code/engine.py`, `linking.py`, `planner.py`, `multimodal.py`)

For each item give PASS / FAIL / CANNOT-TELL with evidence (file, line, case id):

1. Evidence captured after `audit_at` never changes a case state or gets cited (check cases whose `audit_at` is
   earlier than most evidence, for example `case_526`-`case_532` and `case_46`/`case_52`).
2. Replication drift: a resource present in any replica table that is later missing from another store is still
   reported. Pick 5 INCOMPLETE cases that cite SQL replica files and verify against the raw `.sql` by running them in
   SQLite.
3. Historical identifiers: pick 10 requests whose email is an old one (`user_audit_log.csv`) and confirm records
   under the current email are found, and that a *similar but different* email (for example `g.silva76.jr@...`) is
   never matched.
4. Tombstones (`case_543`-`case_550`): stable `user_N` reference kept, direct identifiers must be redacted.
5. Retained records: security audit and legal-hold records get `VERIFY_RECORD_PRESENT` and are never deleted.
6. Hand-built screenshot/PDF cases (`case_33, 34, 35, 39, 45, 46, 50, 52, 53, 55, 61, 63`): open each image/PDF in
   `dataset/evidence/` and judge whether the output for that case is what a careful human auditor would write.
7. Resource-to-person linking for records with no identifier (`code/linking.py`): sample 15 cases that share a
   `reported_at` with other cases and check whether the account/analytics resource chosen is plausible; state the
   fraction you can verify and the fraction that is a guess.
8. Remediation ordering rule from `AGENTS.md` 6.5 (disable flows and block restores before changing dependent
   records; downstream copies before sources).

## 5. Deliverable format

```
GATES: 1 PASS/FAIL ... 8 PASS/FAIL (one line each, with the command output that proves it)
MODEL RUN: calls / tokens / cost / differences
LOGIC REVIEW: item -> PASS/FAIL/CANNOT-TELL + evidence
DEFECTS: numbered list: severity (blocker/major/minor), case ids, expected vs actual, exact spec reference
NOT VERIFIABLE: what you could not check and why
VERDICT: SHIP / DO NOT SHIP, plus the single most likely source of lost score on the hidden answers
```

Do not claim "100%" for the 518 real cases; there is no ground truth for them. State what fraction of your checks passed
instead.

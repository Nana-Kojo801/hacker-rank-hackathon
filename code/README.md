# Ghost Data Still Exists - deletion-audit agent

For every request in `dataset/deletion_requests.csv` the agent decides whether the deletion really happened and writes
`output.csv` (repo root): `case_id,deletion_status,steps_json`.

## Setup and run

```bash
python3 -m pip install -r code/requirements.txt     # OCR engine for screenshots (rapidocr-onnxruntime)
sudo apt-get install poppler-utils                   # pdftotext, used for the PDF evidence
export OPENAI_API_KEY=...                            # or put OPENAI_API_KEY=... in an uncommitted .env at the repo root
python3 code/main.py                                 # -> output.csv (518 rows, sorted by case_id)
python3 code/main.py --no-llm                        # same, without any model call (heuristic request triage)
python3 code/main.py --samples                       # score the 32 public samples against dataset/sample_output.csv
python3 code/evaluation/run_evaluation.py            # regenerates evaluation/evaluation_report.md
python3 code/evaluation/usage_report.py              # regenerates evaluation/usage_report.md from the call log
python3 code/package.py                              # builds code.zip (no dataset, caches or secrets)
```

Optional environment variables: `AUDIT_MODEL` (default `gpt-4o-mini`), `AUDIT_VISION_MODEL`, `OPENAI_BASE_URL`.
Secrets are only read from the environment / `.env`; nothing is hard-coded.  Python 3.10+, standard library only
apart from the OCR engine.

## Design: deterministic core, models only at the edges

Reported statuses and activity results are *claims*, so almost everything is rebuilt from evidence by code; a model is
used only where language understanding is genuinely needed.  That keeps the output reproducible and the cost near zero.

| stage | module | how |
| --- | --- | --- |
| 1. is deletion requested? | `classify.py`, `prompts/classify_request.txt` | one cached model call per distinct request text (any language); multilingual regex fallback with `--no-llm` |
| 2. identity resolution | `identity.py` | request e-mail -> `user_id` through current identities **and** `user_audit_log.csv` history; every e-mail/phone/hash/name ever used |
| 3. evidence -> observations | `evidence.py`, `multimodal.py` | SQL snapshots (executed with SQLite, every replica table), JSON bundles/exports, 5 log dialects (logfmt, JSON, pipe, syslog, structured), handover text, PDFs (`pdftotext`) and screenshots (offline OCR, optional vision-model fallback) are flattened to one `Obs(resource, time, identifiers, state attributes)` type |
| 4. which resources belong to the person | `engine.py`, `linking.py` | (a) exact identifier match (e-mail, hash, phone, `user_N`) on any evidence; (b) *catalog links* (`LINK_RESOURCE_IDENTITY`) for documents that show no identifier; (c) for identifier-less resources (404 account profiles, anonymised analytics rows) the deletion worker's activity stream: rows near `reported_at` whose result matches the reported status, resolved by elimination and by a self-calibrated sub-minute phase offset that rows of one case share |
| 5. state at `audit_at` | `engine.World.evaluate` | only evidence captured at/before `audit_at` and after `requested_at`; per *store* (origin + table/replica) the latest observation wins, a snapshot that does not list a resource counts as absence **for that store only**, and the resource is non-compliant if **any** store (primary, read/regional/reporting/failover replica, log, console) still violates the rule (replication drift) |
| 6. policy | `engine.py`, `planner.py` | the default action per system is read from `deletion_rules.csv` (category -> DELETE / REDACT / ANONYMIZE / RETAIN), refined by the operation the deletion worker attempted *before `audit_at`* (flow and restore checks have no rule row); retained records (security audit, legal hold) are verified present only if they were actually observed present |
| 7. steps | `planner.py` | findings -> remediation (disable flows, block restores, delete, redact, anonymise) -> verification, sorted by the operation table then `system_id`, `resource_id`; remediation/future verification carry an empty `evidence_id`; `COMPLETE` verifications cite the evidence that proves the state |

Other rules honoured: evidence captured after `audit_at` never changes a case or gets cited; later files are still
used to *identify* a resource (identity is time-invariant) but never to decide its state; tombstones keep only the
stable `user_id`; `NOT_APPLICABLE` rows are `[]`.

## Layout

```
code/main.py            CLI entry point            code/prompts/        model prompts
code/identity.py        identity resolution        code/evaluation/     reports, scoring, custom cases
code/evidence.py        evidence parsers           code/.cache/         OCR + model-call cache (git-ignored)
code/multimodal.py      screenshots / PDFs
code/linking.py         identifier-less resources
code/engine.py          state reconstruction       code/planner.py      status + ordered steps
code/classify.py        request triage             code/llm.py          cached OpenAI client + usage log
```

## Known limits

* A retained audit record that is visible only in evidence captured after `audit_at` is still listed as a future
  verification step (empty `evidence_id`) and is never cited for a `COMPLETE` proof; the public sample answers do the same
  (5 of 17 retained steps there are only visible later).
* `case_63`: the screenshot names a person who is not in `user_identities.csv`, while the data-catalog row ties the
  record to the requester. The agent follows the catalog row; the conflict is not flagged in the output.
* The vision-model fallback (used only when no OCR engine is installed and a key is set) is not equivalent to OCR and
  flips `case_53` and `case_63`; install the OCR engine. `--no-llm` disables it.

* Resources that appear nowhere in the evidence (for example some security audit records) cannot be reported.
* When several cases share a `reported_at` and none of their identifier-less rows carries an identifier, the phase
  heuristic may pair rows wrongly; it is calibrated on the data itself, never on `sample_output.csv`.
* `sample_output.csv` was used only for development scoring (`--samples`); no labels are hard-coded.

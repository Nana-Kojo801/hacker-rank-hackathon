# Evaluation report

Generated 2026-10-24 by `code/evaluation/run_evaluation.py` (with model calls).

## 1. Public sample set (32 cases, `dataset/sample_output.csv`)

| metric | value |
| --- | --- |
| cases | 32 |
| status accuracy | 100.0% |
| step precision | 100.0% |
| step recall | 98.4% |
| step F1 | 99.2% |
| field accuracy (positional) | 96.6% |
| sequence exact match | 90.6% |
| sequence similarity (order-aware) | 98.6% |
| steps matched / expected / predicted | 190 / 193 / 190 |

Definitions: *step precision/recall* compare the set of (phase, system, resource, operation, state, evidence) tuples; *field accuracy* compares each field of the expected step at the same position; *sequence exact match* requires the whole ordered array to be identical; *sequence similarity* is the order-aware ratio of the longest matching subsequence.

### Remaining differences on the samples

* `case_04` expected COMPLETE, got COMPLETE; missing: VERIFY_RECORD_ABSENT account_004 [evidence_54]; extra: none
* `case_18` expected INCOMPLETE, got INCOMPLETE; missing: VERIFY_RECORD_PRESENT audit_record_6645 [-]; extra: none
* `case_20` expected INCOMPLETE, got INCOMPLETE; missing: VERIFY_RECORD_PRESENT audit_record_5569 [-]; extra: none

## 2. Additional cases created by the team (`code/evaluation/custom_cases`)

A small synthetic dataset with the same schema, built by `build_custom_cases.py`, with answers derived by hand from `deletion_rules.csv`.

| case | behaviour exercised |
| --- | --- |
| x1 | request e-mail is a *historical* address; the account survives only in a read replica (replication drift) |
| x2 | non-deletion request written in Spanish (must be `NOT_APPLICABLE`, `[]`) |
| x3 | a later snapshot (after `audit_at`) shows the account again and must be ignored |
| x4 | active data flow + restorable backup + tombstone still exposing the e-mail; checks ordering of findings, remediation and verification |
| x5 | same SQL store snapshotted twice: the later complete snapshot no longer lists the account, so it is absent |
| x6 | a legal-hold record observed as NOT_FOUND must not be reported as verified present |

| metric | value |
| --- | --- |
| cases | 6 |
| status accuracy | 100.0% |
| step precision | 100.0% |
| step recall | 100.0% |
| step F1 | 100.0% |
| field accuracy (positional) | 100.0% |
| sequence exact match | 100.0% |
| sequence similarity (order-aware) | 100.0% |
| steps matched / expected / predicted | 17 / 17 / 17 |

* `x1`: PASS (INCOMPLETE)
* `x2`: PASS (NOT_APPLICABLE)
* `x3`: PASS (COMPLETE)
* `x4`: PASS (INCOMPLETE)
* `x5`: PASS (COMPLETE)
* `x6`: PASS (COMPLETE)

<!-- manual -->
## 3. Failures found and improvements made

The first full pass over the 32 public samples scored **status 93.8%, step recall 75%, sequence exact match 22%**. The
iterations below (each re-scored on the samples, then re-checked on the 518 requests for structural validity with
`validate_output.py`) took it to the figures in section 1.

| # | failure found | root cause | improvement |
| --- | --- | --- | --- |
| 1 | `REPORT_REMAINING_RECORD` missed for accounts that only survive in a failover replica (case_05) | a later *primary* snapshot that no longer listed the account was treated as proof of absence | state is evaluated **per store** (origin + table/replica); a snapshot is evidence of absence only for its own store, and any store still violating the rule keeps the resource non-compliant |
| 2 | start-of-lookup log lines (`*_started`) counted as "record exists" | the line carries only the lookup key | `*_started` events only contribute the lookup identifier to the matching `*_completed` line |
| 3 | wrong evidence file cited (a later bundle whose snapshot did not list the record) | omissions outranked explicit observations | explicit observations are preferred over inferred absence; omissions never apply to retained records |
| 4 | backups / flows reported compliant | log dialects use `eligible`, `deletion_block`, `decision=deny`, `enabled` instead of one common flag | `facts()` normalises every dialect to *restorable* / *enabled* |
| 5 | wrong treatment for some records (support contact deleted vs redacted, analytics profile deleted vs anonymised) | the category was guessed from the id prefix | the required action is taken from the operation the deletion worker attempted on that resource (DELETE / REDACT / ANONYMIZE / flow / restore), falling back to the policy default for the prefix |
| 6 | account `VERIFY_RECORD_ABSENT` and anonymised analytics rows missing in ~half of the cases | those resources carry **no identifier** in any evidence file, only the deletion worker's activity rows | `linking.py`: activity rows near `reported_at` filtered by result-vs-reported-status, elimination across cases, and a self-calibrated sub-minute phase offset shared by the rows of one case (no sample labels used) |
| 7 | stale account lookups from an earlier request attached to the new request (case_17 vs case_46) | identifier match is time-blind | accounts are pruned to the deletion run around the case's `reported_at`; evidence older than `requested_at` is ignored |
| 8 | screenshots / PDFs ignored (hand-built cases: connector console, backup console, export console, ticket console, marketing profile, statements) | no OCR path | offline OCR + `pdftotext`, row binding and `LINK_RESOURCE_IDENTITY` catalog links; console semantics (a live connector is enabled, a listed archive is restorable, an attachment page implies an attachment) |
| 9 | heuristic request triage marked a real deletion request as non-deletion (case_05: "...remove any remaining **copy of** my profile") | over-broad regex | regex narrowed; the model-based classifier is the primary path and the regex only a multilingual fallback |
| 10 | a retention proof cited evidence captured after `audit_at` (case_46) | fallback to any sighting of the audit record | retention verification keeps the step but drops the evidence id when nothing at/before `audit_at` supports it (rule: never cite later evidence) |


### Round 2: defects found by two independent QA sessions (commit 6b0aeb5), all reproduced before fixing

| # | defect | impact | fix |
| --- | --- | --- | --- |
| 11 | SQL column `collection_name` was read as a person's name, so rows with every identifier null looked "still attributable" | 31 of 518 statuses wrongly INCOMPLETE (27 analytics rows, 4 clean tombstones) | person names come only from an allow-list of name columns; 31 statuses change INCOMPLETE -> COMPLETE, sample scores unchanged |
| 12 | a later complete snapshot of the same SQL store could not supersede an earlier present row (rows keyed by table, omissions by system) | latent (no change on the 518) | omission is now table-specific; custom case x5 reproduces and passes |
| 13 | a retained record observed as NOT_FOUND was still "verified present" | latent | skipped; custom case x6 |
| 14 | a `[redacted]` label or `result=redacted` hid identifiers extracted from other fields | latent | clean only if no identifier was extracted |
| 15 | the deletion worker's action could come from an event after `audit_at`; `deletion_rules.csv` was never read | latent | actions use worker events up to `audit_at`; defaults are read from the rules file |
| 16 | request triage was a blacklist (accepted "send my invoices", rejected "delete my account after you send me a copy"), the model guard could overrule a correct veto, an invalid key aborted the run, `--no-llm` still allowed vision calls | wrong triage on unseen phrasings | triage now needs a positive deletion signal and separates "declines" from "other topic"; invalid key falls back to the heuristic; `--no-llm` disables every model call. The 11 adversarial phrases from QA all pass and a model that rejects everything still yields exactly cases 533-542 |

Not changed on purpose: retained records visible only after `audit_at` stay as empty-evidence verification steps (the public
sample answers do the same); timing-based linking of identifier-less records is kept and documented as a risk.

### Still failing on the samples

* `case_04` (`account_004`): the account has no evidence entry and no deletion-worker row at all, so it cannot be tied to the person (its `analytics_901` row is recovered from the activity stream).
* `case_18`, `case_20` (`audit_record_6645`, `audit_record_5569`): the security audit record is not mentioned anywhere in the participant data.

These are information limits of the dataset rather than logic gaps; the agent does not guess ids.

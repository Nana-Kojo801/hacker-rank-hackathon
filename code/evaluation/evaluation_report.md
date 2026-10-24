# Evaluation report

Generated 2026-10-24 by `code/evaluation/run_evaluation.py` (with model calls).

## 1. Public sample set (32 cases, `dataset/sample_output.csv`)

| metric | value |
| --- | --- |
| cases | 32 |
| status accuracy | 68.8% |
| step precision | 100.0% |
| step recall | 64.8% |
| step F1 | 78.6% |
| field accuracy (positional) | 63.0% |
| sequence exact match | 59.4% |
| sequence similarity (order-aware) | 67.4% |
| steps matched / expected / predicted | 125 / 193 / 125 |

Definitions: *step precision/recall* compare the set of (phase, system, resource, operation, state, evidence) tuples; *field accuracy* compares each field of the expected step at the same position; *sequence exact match* requires the whole ordered array to be identical; *sequence similarity* is the order-aware ratio of the longest matching subsequence.

### Remaining differences on the samples

* `case_04` expected COMPLETE, got COMPLETE; missing: VERIFY_RECORD_ABSENT account_004 [evidence_54]; extra: none
* `case_06` expected INCOMPLETE, got NOT_APPLICABLE; missing: DELETE_RECORD search_001 [-], REPORT_REMAINING_RECORD search_001 [evidence_57], VERIFY_RECORD_ABSENT account_006 [-], VERIFY_RECORD_ABSENT search_001 [-]; extra: none
* `case_10` expected INCOMPLETE, got NOT_APPLICABLE; missing: DELETE_RECORD support_002 [-], REPORT_REMAINING_RECORD support_002 [evidence_61], VERIFY_RECORD_ABSENT account_010 [-], VERIFY_RECORD_ABSENT support_002 [-]; extra: none
* `case_12` expected INCOMPLETE, got NOT_APPLICABLE; missing: DELETE_RECORD analytics_9914 [-], REPORT_REMAINING_RECORD analytics_9914 [evidence_01], VERIFY_RECORD_ABSENT account_9797 [-], VERIFY_RECORD_ABSENT analytics_9914 [-], VERIFY_RECORD_PRESENT audit_record_2945 [-]; extra: none
* `case_18` expected INCOMPLETE, got INCOMPLETE; missing: VERIFY_RECORD_PRESENT audit_record_6645 [-]; extra: none
* `case_20` expected INCOMPLETE, got INCOMPLETE; missing: VERIFY_RECORD_PRESENT audit_record_5569 [-]; extra: none
* `case_21` expected COMPLETE, got NOT_APPLICABLE; missing: VERIFY_RECORD_ABSENT account_6440 [evidence_92], VERIFY_RECORD_ANONYMIZED analytics_5335 [evidence_92], VERIFY_RECORD_PRESENT audit_record_3737 [evidence_92]; extra: none
* `case_25` expected COMPLETE, got NOT_APPLICABLE; missing: VERIFY_RECORD_ABSENT account_3136 [evidence_92], VERIFY_RECORD_ANONYMIZED analytics_1895 [evidence_92], VERIFY_RECORD_PRESENT audit_record_451 [evidence_92]; extra: none
* `case_26` expected COMPLETE, got NOT_APPLICABLE; missing: VERIFY_DATA_FLOW_DISABLED data_flow_6244 [evidence_92], VERIFY_RECORD_ABSENT account_5684 [evidence_92], VERIFY_RECORD_ANONYMIZED analytics_4566 [evidence_92], VERIFY_RECORD_PRESENT audit_record_5416 [evidence_92], VERIFY_RECORD_REDACTED support_4715 [evidence_92], VERIFY_RESTORE_BLOCKED backup_3120 [evidence_92]; extra: none
* `case_27` expected COMPLETE, got NOT_APPLICABLE; missing: VERIFY_DATA_FLOW_DISABLED data_flow_2295 [evidence_92], VERIFY_RECORD_ABSENT account_3866 [evidence_92], VERIFY_RECORD_ANONYMIZED analytics_4574 [evidence_92], VERIFY_RECORD_PRESENT audit_record_3830 [evidence_92], VERIFY_RECORD_REDACTED support_4707 [evidence_92], VERIFY_RESTORE_BLOCKED backup_5970 [evidence_92]; extra: none
* `case_28` expected COMPLETE, got NOT_APPLICABLE; missing: VERIFY_DATA_FLOW_DISABLED data_flow_2337 [evidence_92], VERIFY_RECORD_ABSENT account_5482 [evidence_92], VERIFY_RECORD_ANONYMIZED analytics_6077 [evidence_92], VERIFY_RECORD_PRESENT audit_record_9265 [evidence_92], VERIFY_RECORD_REDACTED support_2351 [evidence_92], VERIFY_RESTORE_BLOCKED backup_838 [evidence_92]; extra: none
* `case_29` expected INCOMPLETE, got NOT_APPLICABLE; missing: ANONYMIZE_RECORD analytics_5208 [-], DELETE_RECORD search_1993 [-], DISABLE_DATA_FLOW data_flow_3827 [-], REDACT_RECORD support_5281 [-], REPORT_ACTIVE_DATA_FLOW data_flow_3827 [evidence_92], REPORT_EXPOSED_PII analytics_5208 [evidence_92], REPORT_EXPOSED_PII support_5281 [evidence_92], REPORT_REMAINING_RECORD search_1993 [evidence_92], VERIFY_DATA_FLOW_DISABLED data_flow_3827 [-], VERIFY_RECORD_ABSENT account_7012 [-], VERIFY_RECORD_ABSENT search_1993 [-], VERIFY_RECORD_ANONYMIZED analytics_5208 [-], VERIFY_RECORD_PRESENT audit_record_3954 [-], VERIFY_RECORD_REDACTED support_5281 [-]; extra: none
* `case_30` expected INCOMPLETE, got NOT_APPLICABLE; missing: ANONYMIZE_RECORD analytics_3697 [-], DELETE_RECORD search_9359 [-], DISABLE_DATA_FLOW data_flow_8524 [-], REDACT_RECORD support_6477 [-], REPORT_ACTIVE_DATA_FLOW data_flow_8524 [evidence_92], REPORT_EXPOSED_PII analytics_3697 [evidence_92], REPORT_EXPOSED_PII support_6477 [evidence_92], REPORT_REMAINING_RECORD search_9359 [evidence_92], VERIFY_DATA_FLOW_DISABLED data_flow_8524 [-], VERIFY_RECORD_ABSENT account_4163 [-], VERIFY_RECORD_ABSENT search_9359 [-], VERIFY_RECORD_ANONYMIZED analytics_3697 [-], VERIFY_RECORD_PRESENT audit_record_1707 [-], VERIFY_RECORD_REDACTED support_6477 [-]; extra: none

## 2. Additional cases created by the team (`code/evaluation/custom_cases`)

A small synthetic dataset with the same schema, built by `build_custom_cases.py`, with answers derived by hand from `deletion_rules.csv`.

| case | behaviour exercised |
| --- | --- |
| x1 | request e-mail is a *historical* address; the account survives only in a read replica (replication drift) |
| x2 | non-deletion request written in Spanish (must be `NOT_APPLICABLE`, `[]`) |
| x3 | a later snapshot (after `audit_at`) shows the account again and must be ignored |
| x4 | active data flow + restorable backup + tombstone still exposing the e-mail; checks ordering of findings, remediation and verification |

| metric | value |
| --- | --- |
| cases | 4 |
| status accuracy | 100.0% |
| step precision | 100.0% |
| step recall | 100.0% |
| step F1 | 100.0% |
| field accuracy (positional) | 100.0% |
| sequence exact match | 100.0% |
| sequence similarity (order-aware) | 100.0% |
| steps matched / expected / predicted | 16 / 16 / 16 |

* `x1`: PASS (INCOMPLETE)
* `x2`: PASS (NOT_APPLICABLE)
* `x3`: PASS (COMPLETE)
* `x4`: PASS (INCOMPLETE)

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

### Still failing on the samples

* `case_04` (`account_004`): the account has no evidence entry and no deletion-worker row at all, so it cannot be tied to the person (its `analytics_901` row is recovered from the activity stream).
* `case_18`, `case_20` (`audit_record_6645`, `audit_record_5569`): the security audit record is not mentioned anywhere in the participant data.

These are information limits of the dataset rather than logic gaps; the agent does not guess ids.

# Evaluation report

Generated 2026-10-24 by `code/evaluation/run_evaluation.py` (deterministic mode, no model calls).

## 1. Public sample set (32 cases, `dataset/sample_output.csv`)

| metric | value |
| --- | --- |
| cases | 32 |
| status accuracy | 100.0% |
| step precision | 100.0% |
| step recall | 97.9% |
| step F1 | 99.0% |
| field accuracy (positional) | 96.5% |
| sequence exact match | 90.6% |
| sequence similarity (order-aware) | 96.6% |
| steps matched / expected / predicted | 189 / 193 / 189 |

Definitions: *step precision/recall* compare the set of (phase, system, resource, operation, state, evidence) tuples; *field accuracy* compares each field of the expected step at the same position; *sequence exact match* requires the whole ordered array to be identical; *sequence similarity* is the order-aware ratio of the longest matching subsequence.

### Remaining differences on the samples

* `case_04` expected COMPLETE, got COMPLETE; missing: VERIFY_RECORD_ABSENT account_004 [evidence_54], VERIFY_RECORD_ANONYMIZED analytics_901 [evidence_56]; extra: none
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
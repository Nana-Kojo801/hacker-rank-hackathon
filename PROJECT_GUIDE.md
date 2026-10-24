# Ghost Data Still Exists - complete project guide (for the AI interview)

Everything an interviewer can ask about this project, in one place. Numbers are from the repository at the commit
"Fix defects from independent QA"; where a number was measured by someone else it says so. Read sections 1-4 first, then
rehearse section 11 out loud.

---

## 1. The 60-second version

* **Problem.** A shop's deletion workflow said "Complete", yet a customer's data survived in search, support files,
  exports, analytics, logs and backups, and a sync job re-created some of it. We build an **auditor** that does not trust
  the workflow's claim.
* **Input.** 518 deletion requests, plus identity files, an activity log, a 15-row policy table and 94 evidence files
  (SQL snapshots, logs, JSON, PDFs, screenshots).
* **Output.** One row per request: `case_id, deletion_status, steps_json`. Status is `COMPLETE`, `INCOMPLETE` or
  `NOT_APPLICABLE`. Steps are findings, then remediation, then verification, in a fixed order.
* **Our answer.** Ordinary, testable code rebuilds each person's data footprint at the audit time and applies the policy.
  A language model is used for **one narrow job only**: reading a request (in any language) to decide whether it asks for
  deletion at all. Everything else is deterministic, so output is repeatable and the whole run costs about 3 cents.
* **Result.** On the 32 public samples: status accuracy 100%, step precision 100%, step recall 98.4%, 29 of 32 cases
  exactly right in order. For the 518 real cases there is no answer key, so we claim spec-consistency, not a percentage.

---

## 2. The task precisely

### 2.1 Files (all under `dataset/`)

| file | what it holds | size |
| --- | --- | --- |
| `deletion_requests.csv` | the 518 cases to answer (`case_33` ... `case_550`) | 518 |
| `sample_deletion_requests.csv`, `sample_output.csv` | 32 public cases and their correct answers (`case_01` ... `case_32`) | 32 |
| `user_identities.csv` | current name, email, phone, email hash per user | 850 users |
| `user_audit_log.csv` | history of changed emails/phones/names | 306 changes |
| `system_activity.csv` | deletion worker, syncs, exports, backups, restores, indexing | 4,011 events |
| `deletion_rules.csv` | required treatment per data category | 15 rules |
| `evidence_files.csv` + `evidence/` | manifest and the evidence itself | 94 files |

Request fields: `case_id, email, requested_at, reported_status, reported_at, audit_at, request_text`.
`reported_status` (`COMPLETE`, `PARTIALLY_COMPLETE`, `NOT_STARTED`) is the workflow's **claim**, not proof. `audit_at` is
the instant we must describe: evidence captured after it must not change the answer or be cited.

### 2.2 The policy (`deletion_rules.csv`)

| action | categories |
| --- | --- |
| DELETE | user profile, secondary identifier, search index entry, cache entry, user export, marketing profile, support attachment belonging only to the subject |
| REDACT (keep record, remove names/emails/phones/hashes) | shared support message, email delivery log, account tombstone |
| ANONYMIZE (cut the link to the person) | analytics profile, product telemetry |
| RETAIN | security audit log inside its retention period, legal-hold record, backup archive provided restore can be blocked |

**Tombstone:** a deleted account may keep only its stable `user_N` reference so retained records still point somewhere.
**COMPLETE** means: every copy has the required treatment, no active sync/import/restore path can re-create data, retained
records are still available.

### 2.3 Output contract

Each step has exactly: `step_no, phase, system_id, resource_id, operation, state, evidence_id`.

| phase | operation -> state |
| --- | --- |
| FINDING | REPORT_REMAINING_RECORD -> PRESENT; REPORT_EXPOSED_PII -> PRESENT; REPORT_ACTIVE_DATA_FLOW -> ACTIVE; REPORT_RESTORE_RISK -> ACTIVE |
| REMEDIATION | DISABLE_DATA_FLOW -> DISABLED; BLOCK_RESTORE -> BLOCKED; DELETE_RECORD -> ABSENT; REDACT_RECORD -> REDACTED; ANONYMIZE_RECORD -> ANONYMIZED |
| VERIFICATION | VERIFY_RECORD_ABSENT / PRESENT / REDACTED / ANONYMIZED; VERIFY_DATA_FLOW_DISABLED; VERIFY_RESTORE_BLOCKED |

Ordering: phase order, then the operation order above, then `system_id`, then `resource_id` (ascending).
`COMPLETE` rows contain only verification steps and each cites evidence; `INCOMPLETE` findings cite evidence, while
remediation and post-fix verification are future work with an **empty** `evidence_id`; `NOT_APPLICABLE` is `[]`.
Evidence ids are manifest file ids (`evidence_NN`), always captured at or before `audit_at`.

### 2.4 Scoring (as stated in the brief)

Hidden answers; scored on status, identity resolution, found records/risks, cited evidence, policy decisions, and step
completeness/order. Deliverables: `code.zip` (code, prompts, config, README, `evaluation/` with
`evaluation_report.md` and `usage_report.md`), `output.csv`, the chat transcript (`log.txt`), and an AI interview.

---

## 3. Architecture

```
request ──> [1 triage: deletion?] ──no──> NOT_APPLICABLE, []
              │yes
              v
        [2 identity]  email -> user_N + every old/new email, phone, hash, name
              v
        [3 evidence -> observations]  SQL, JSON, 5 log dialects, handover text, PDF, screenshots -> one Obs type
              v
        [4 which resources are theirs]  identifiers  +  catalog links  +  activity-stream matching
              v
        [5 state at audit_at]  per store, latest wins, any store still violating => violation
              v
        [6 policy]  required action per resource (rules file + what the worker attempted)
              v
        [7 plan]  findings -> remediation -> verification, ordered, evidence ids
```

| module | role |
| --- | --- |
| `code/main.py` | CLI: `python3 code/main.py [--no-llm] [--samples] [--dataset D] [--output F]` |
| `code/classify.py`, `prompts/classify_request.txt` | stage 1; the only model call in a normal run |
| `code/identity.py` | stage 2 |
| `code/evidence.py` | parsers for SQL (executed in SQLite), JSON, logs, handover text; `Obs` dataclass |
| `code/multimodal.py` | PDFs (`pdftotext`) and screenshots (offline OCR, cached); binds rows and catalog links |
| `code/linking.py` | stage 4c: identifier-less resources |
| `code/engine.py` | stages 5-6: `World.evaluate`, policy defaults, `facts()` |
| `code/planner.py` | stage 7 |
| `code/solve.py` | glue, account pruning |
| `code/llm.py` | tiny cached OpenAI client, `.env` loader, usage log |
| `code/evaluation/` | scoring, 6 custom cases, validator, report generators |

The core design rule: **claims are not facts.** `reported_status` and the activity log's `SUCCESS/FAILED` are never used
as proof of state; state comes from evidence. The activity log is used only to (a) learn what treatment a resource needed
(the operation the worker attempted) and (b) link identifier-less resources to a case.

---

## 4. How each stage works, and why

### Stage 1 - is deletion requested?
Ten requests (`case_533`-`case_542`) are not deletion requests ("change my phone number", "stop the promotional emails",
"send me a copy of my data"...) and must be `NOT_APPLICABLE` with `[]`. The text may be in any language (Spanish, French,
Portuguese, Korean, Japanese appear), so a model is used. Safeguards, each added after a real failure:

* The model returns two flags, `authorizes_deletion` and `explicitly_declines_deletion`. A request becomes
  NOT_APPLICABLE only if it declines explicitly; an unclear text defaults to "audit it".
* A deterministic guard (`heuristic`) can overrule a veto when the text is clearly a deletion/audit request.
* Requests to *verify, finish or repair* a deletion count as deletion requests ("I deleted my account, check nothing
  remains").
* Invalid key or outage: warn and fall back to the heuristic; `--no-llm` disables every model call.
* Test: even a model that rejects everything yields exactly cases 533-542.

### Stage 2 - identity resolution
`identity.py` maps the request email to a `user_id` via current identities **and** the change history, then gathers every
email, phone, email hash and name the person ever had. Across all 550 requests (518 + 32): 447 use a current email, 103 a
historical one, none unknown or ambiguous (QA-verified independently). Matching is exact on normalized values, so a
look-alike such as `g.silva76.jr@gmail.com` never matches `g.silva76@gmail.com`.

### Stage 3 - evidence -> observations
Every file becomes `Obs(file, time, resource_id, system, emails, hashes, users, phones, names, state attributes)`:

* **SQL**: executed in SQLite. Wide tables carry a JSON payload column that is unpacked. Snapshots can hold a primary and
  regional/reporting/failover replicas; each table is a separate *store*.
* **JSON**: snapshot bundles (with per-collection capture times, possibly empty), service exports, connector/audit ledgers.
* **Logs**: five dialects (logfmt, JSON lines, pipe-delimited, syslog, structured). `*_started` lines contribute only the
  lookup key to the matching `*_completed` line.
* **Handover text**: pipe-delimited lines.
* **PDFs and screenshots**: see Stage 3b.

Resource ids: `account_N`, `search_N`, `support_N`, `analytics_N`, `export_N`, `backup_N`, `data_flow_N`,
`audit_record_N`, `tombstone_N`, `marketing_N`, `object_N`, `legal_hold_N`; the prefix tells the system.

### Stage 3b - screenshots and PDFs
Screenshots go through offline OCR (RapidOCR), cached under `code/.cache/ocr/`; PDFs through `pdftotext`. Two ways to bind
a document to a resource: **row binding** (a resource id and identifiers on the same visual line describe the same
record) and **catalog links** (`LINK_RESOURCE_IDENTITY` activity rows map a resource id or an alias such as a statement
number or file name to its owner; a link applies to a document if its alias/id appears in the text and the link was logged
within 3 hours after the document's capture). Console semantics: a connector shown live is an enabled data flow; an archive
listed with no "restore blocked" text is restorable; an attachment page implies a support attachment. An optional
vision-model fallback exists for machines without OCR (not equivalent to OCR; `--no-llm` disables it).

### Stage 4 - which resources belong to this person
1. **Identifiers**: any observation containing one of the person's emails, hashes, phones or `user_N` links its resource.
   (Evidence captured later may still *identify* a resource; identity does not change with time. It never decides state.)
2. **Catalog links** for documents that show no identifier.
3. **Activity-stream matching** (`linking.py`) for resources with no identifier anywhere, e.g. an account profile that
   just returns 404, or an analytics row that is already anonymized:
   * The deletion worker logs rows for each case near `reported_at`; account rows sit about 0.6-1.4 h before it.
   * The row's result usually matches the reported status (SUCCESS / PARTIAL / FAILED <-> COMPLETE / PARTIALLY_COMPLETE /
     NOT_STARTED).
   * Candidates are narrowed by **elimination** (rows already claimed by identifier links are removed).
   * Remaining ambiguity (cases that share a `reported_at`) is resolved by a **timing fingerprint**: rows of one case keep
     a nearly constant offset in *seconds* from that case's account row, per row type. The offset histogram is learned from
     the data's own unambiguous cases, never from `sample_output.csv`.
   * Hand-built cases log the call right at `reported_at`, so a second narrower window is used.
   *Honest assessment:* strong on the samples (all assignments correct), unverifiable on the 518 (QA counted 112 accounts
   and 118 analytics rows depending on it). This is the part most likely to lose points, and we say so.

### Stage 5 - the state at `audit_at`
For each resource: take observations captured at or before `audit_at` and after `requested_at`. Group them into **stores**
(`origin + table/replica`). In each store the latest observation wins; a SQL snapshot that does not list the resource
counts as absence **for that table only** (table-level coverage; a primary lacking a row says nothing about a replica).
The resource is non-compliant if **any** store still violates the rule. This is how replication drift is caught: in
`case_05` (sample) the primary no longer lists `account_005`, but a failover replica captured earlier still holds it with
the person's name, email and phone, so the answer is INCOMPLETE.
Evidence cited: for a violation, the latest violating store's file; for compliance, explicit proof preferred over inferred
absence.

### Stage 6 - policy
Default action per system is read from `deletion_rules.csv` (category -> action). It is refined by the operation the
deletion worker attempted before `audit_at` (DELETE / REDACT / ANONYMIZE / flow check / restore check) - this is how a
"support contact" or "marketing profile" stored under an `analytics_` id is recognised as DELETE rather than ANONYMIZE.
`facts()` normalises every dialect to: exists, direct identifier present, attributable, flow enabled, restore allowed.
Violation tests: DELETE -> exists; REDACT -> exists with a direct identifier; ANONYMIZE -> exists and attributable;
FLOW -> enabled; RESTORE -> restore allowed. Person names come only from an allow-list of name columns (a bug where
`collection_name` was treated as a name had flipped 31 statuses).

### Stage 7 - the plan
`planner.py`: any violation -> `INCOMPLETE` = findings + remediation + verification. Otherwise `COMPLETE` = verification
steps with evidence. Verification covers the account (always), retained records (present), and every remediated resource.
Retained records seen as missing are skipped; ones seen only after `audit_at` appear as future verifications with no
cited evidence. The fixed sort gives flow/restore changes before record changes.

---

## 5. Results and evidence of quality

| measure | value | notes |
| --- | --- | --- |
| samples (32) status accuracy | 100% | tuned on these, so optimistic |
| samples step precision / recall / F1 | 100% / 98.4% / 99.2% | 190 of 193 expected steps |
| samples exact ordered match | 90.6% (29/32) | |
| samples sequence similarity | 98.6% | order-aware |
| custom cases (6) | 6/6, 17/17 steps | we wrote them, so weaker evidence |
| output validity | 518 rows, 0 problems | format, order, evidence rules, no evidence newer than `audit_at` |
| determinism | byte-identical across runs, cold cache, hash seeds | QA-verified |
| output mix | 353 INCOMPLETE, 155 COMPLETE, 10 NOT_APPLICABLE | 3,264-step output, 1,164 cited steps (QA count at the earlier commit) |
| model run | 375 calls, `gpt-4o-mini`, 146,416 tokens (~283 per request), ~USD 0.027 | one call per distinct request text |
| model effect on output | none (identical to no-model run) | model only triages requests |

**The three sample misses**: `account_004`, `audit_record_6645`, `audit_record_5569`. Each appears nowhere in participant
data (checked by grep, OCR and PDF text), so it cannot be derived; we do not guess ids.

**Cross-check on the hand-built cases** (screenshots/PDFs, cases 33, 34, 35, 39, 45, 46, 50, 52, 53, 55, 61, 63): QA viewed
the artifacts and judged the findings supported, except `case_63` (screenshot names a person not in the identity file
while the catalog ties the record to the requester; we follow the catalog and list it as a limit).

---

## 6. The failures we found and fixed (the "we test our own work" story)

| # | what happened | fix |
| --- | --- | --- |
| 1 | Replica drift: a later primary snapshot hid a replica still holding the account (case_05) | state per store; any violating store counts |
| 2 | Log `*_started` lines counted as "record exists" | they only carry the lookup key |
| 3 | Backups/flows reported compliant | normalised the different log dialects (`eligible`, `deletion_block`, `decision=deny`, `enabled`) |
| 4 | Wrong treatment (contact deleted vs redacted, marketing profile under an analytics id) | action from the worker's attempted operation + rules defaults |
| 5 | Account/analytics rows with no identifier were missing in about half of cases | activity-stream matching with elimination and timing fingerprint |
| 6 | Stale account lookups from an earlier request attached to a new request (case_17 vs case_46) | prune to the run near `reported_at`; ignore evidence older than `requested_at` |
| 7 | Screenshots/PDFs ignored | OCR + row binding + catalog links |
| 8 | First model run dropped sample accuracy to **68.8%**: the model called real requests ("I deleted my account, verify...") non-deletion and emptied those cases | prompt rewrite, explicit-decline flag, deterministic guard; a model that rejects everything now yields exactly the 10 true cases |
| 9 | Retention proof cited evidence newer than `audit_at` | step kept, evidence id dropped |
| 10 | QA round 2: `collection_name` read as a person's name | 31 statuses INCOMPLETE -> COMPLETE; allow-list of name columns |
| 11 | QA round 2: later same-store snapshot could not supersede an earlier row; retained record "not found" still verified present; `[redacted]` label hid other identifiers; worker actions from after `audit_at`; rules file never read; brittle triage; invalid key aborted; `--no-llm` still allowed vision | all fixed, with custom cases x5/x6 that fail on the old code |

Two independent QA sessions reviewed commit 6b0aeb5: all 8 hard gates passed, both found the `collection_name` defect,
and one also listed the items in row 11. Neither could measure hidden accuracy (no key was available to either for the
live model run).

---

## 7. Known limits (say these before they are asked)

1. **No answer key for the 518.** We claim consistency with the spec and independent verification, not an accuracy figure.
2. **Identifier-less matching is a strong heuristic, not proof.** Pairs that share a `reported_at` are separated by
   elimination and a timing fingerprint. The fingerprint is a property of how the data looks, not a business rule.
3. **Missing data can't be reported.** Some resources appear nowhere in the participant data.
4. **Retained records visible only after `audit_at`** are listed as future verifications without evidence (the public sample
   answers do the same for 5 of 17).
5. **`case_63` conflict** between a screenshot and a catalog row (follows the catalog).
6. **The OCR path is heuristic** (row binding by visual lines); the vision-model fallback is untested against OCR parity.
7. **Planner has no dependency graph.** Ordering follows the fixed sort required by the brief; a "downstream copy before its
   source" dependency beyond that is not modelled.
8. **Sample tuning.** Development used the 32 samples, so their scores are optimistic.

---

## 8. Design decisions and the reasons (interviewers love "why")

* **Why not let a model read all the evidence?** Cost, repeatability and testability. Ordering, ids and citations are easy
  for a free-form model to get slightly wrong and impossible to regression-test; code can be diffed, validated and replayed.
  Our run costs cents and is byte-identical every time.
* **Why still use a model at all?** Request intent in any language is genuinely a language problem, and the brief rewards
  multimodal/model use where it helps. We bounded its power so it cannot silently empty a case.
* **Why per-store state?** The brief explicitly mentions primary/replica drift. "Absent from the primary" is not "absent".
* **Why ignore evidence before `requested_at`?** Earlier snapshots describe history before the request; they cannot show
  that a deletion failed. (QA noted this can hide "never deleted" records; the choice is consistent with all 32 sample answers but unproven beyond them.)
* **Why trust the worker's attempted operation for the required action?** The rules table keys on data *category*, and the
  category of an id is sometimes not its prefix. The attempted operation is a claim about *what was needed*, not about
  the result; results are never trusted.
* **Why exact identifier matching?** Look-alike emails are deliberate decoys; a fuzzy match would attach another person's data.
* **Why cache and log?** OCR and model results are cached on disk; every model call is logged for the usage report.
* **Security.** Key only from `OPENAI_API_KEY` or an uncommitted `.env`; nothing hard-coded; no organizer files used;
  `sample_output.csv` is read only by `--samples` and the evaluation scripts.

---

## 9. Worked examples (real ids)

**`case_05` - replica drift (sample).** Leila Haddad, `leila.haddad@yahoo.com`; requested 27 Aug, workflow said COMPLETE on
28 Aug, audit 8 Sep. `evidence_90` (primary inventory snapshot, 5 Sep) does not list her account; `evidence_54` (failover
replica, 2 Sep 23:00) still holds `account_005` with name, email, phone. Output: INCOMPLETE; finding
`REPORT_REMAINING_RECORD account_005` citing `evidence_54`; `DELETE_RECORD account_005`; `VERIFY_RECORD_ABSENT account_005`
(last two with empty evidence).

**`case_11` - the full set (sample).** `novak.tomasz@icloud.com`. Findings: search entry `search_052` remains, analytics
`analytics_2034` and support message `support_864` expose PII, data flow `data_flow_9522` is active (all cite
`evidence_03`, a handover note). Remediation order: disable the flow, delete the search entry, redact the support message,
anonymize the analytics row. Verification: account absent, search absent, audit record present, support redacted,
analytics anonymized, flow disabled.

**`case_21` / `case_25`-`28` - identifier-less matching (samples).** `account_6440` returns 404 with no email anywhere;
it is linked to `amara-okeke@proton.me` by its position in the activity stream (and the audit record `audit_record_3737`
carries `user_21`). Cases 25/26 share a report time, as do 27/28; each pair is separated by elimination and offset.

**`case_31` / `case_32` - tombstones (samples).** `case_31`: `tombstone_440` already has name/email/phone/hash null and
keeps `user_541` -> COMPLETE with `VERIFY_RECORD_REDACTED`. `case_32`: `tombstone_9178` still shows name and email ->
INCOMPLETE, `REDACT_RECORD`.

**`case_533`-`542` - non-deletion.** e.g. `case_533` "replace my phone number and leave the account active" -> `NOT_APPLICABLE`, `[]`.

**Hand-built screenshot cases.** `case_39`: connector console shows `data_flow_1121` delivering events for
`jain.aditi@gmail.com` -> active flow finding. `case_55`: backup console lists `backup_9287` for `areed1433@gmail.com` ->
restore risk. `case_61`: object browser lists `delivery_confirmation_19.pdf`; a catalog row says `object_19` belongs only to
the requester -> delete the object. `case_46`: a registry shows only `user_17` -> retained tombstone, COMPLETE.

---

## 10. Commands

```bash
pip install -r code/requirements.txt ; apt-get install poppler-utils
export OPENAI_API_KEY=...                         # or uncommitted .env at repo root
python3 code/main.py                              # model-assisted run -> output.csv
python3 code/main.py --no-llm                     # deterministic run, zero model calls
python3 code/main.py --samples                    # score the 32 public samples
python3 code/evaluation/run_evaluation.py         # samples + 6 custom cases -> evaluation_report.md
python3 code/evaluation/validate_output.py        # format/order/evidence-time checks (expects 0 problems)
python3 code/evaluation/usage_report.py           # tokens and cost -> usage_report.md
python3 code/package.py                           # builds code.zip (no dataset, caches, keys)
```

Repo extras: `TESTING_PROMPT.md` (independent QA brief), `VIDEO_PROMPT.md` (explainer video), `log.txt` (AI transcript, one
entry per turn, required by `AGENTS.md`).

---

## 11. Interview Q&A (short answers to rehearse)

1. **Summarise your approach in one minute.** Section 1.
2. **How do you know it works without an answer key?** 32 public samples (100% status, 98.4% step recall), six hand-derived
   custom cases, a validator for the output contract, byte-identical reruns, two independent QA sessions, and every defect
   they found reproduced before fixing. We do not claim a percentage on the 518.
3. **What does the model do, and what happens if it is wrong or down?** It only decides whether a request asks for deletion.
   It cannot veto a clear deletion request (guard), an unclear text defaults to "audit it", an outage falls back to a
   heuristic, and the model run produced output identical to the no-model run.
4. **Tell me about the biggest mistake.** The first model-assisted run dropped sample accuracy to 68.8% because the model
   labelled real audit requests as non-deletion. We found it by reading the evaluation report, rewrote the prompt, added an
   explicit-decline flag and a deterministic guard, and proved that even a model that rejects everything gives exactly the
   10 true cases. Then QA found a second one: a column called `collection_name` read as a person's name, 31 wrong statuses.
5. **How do you handle replication drift?** State is tracked per store; a snapshot proves absence only for its own table;
   any store still holding the record keeps it non-compliant (`case_05`).
6. **How do you find resources that have no identifier?** Activity-stream matching: rows near the report time, result
   matching the reported status, elimination, and a self-calibrated seconds-offset fingerprint. Strong on samples, unverifiable
   on the 518; this is our main risk.
7. **How do you avoid using future evidence?** Only evidence captured at or before `audit_at` decides state or is cited.
   Later files may identify a resource (identity is time-invariant) but never its state. We know retained records seen only
   later are still listed as future checks, as the sample answers do.
8. **Why per-store rather than newest snapshot wins?** Different replicas can disagree; the brief tells us to compare them.
9. **What about tombstones?** Keep `user_N`, require name, email, phone and email hash to be gone; otherwise `REDACT_RECORD`.
10. **Why is the output order what it is?** The brief fixes it: findings, remediation, verification; operation order;
    `system_id`; `resource_id`. Flow and restore changes come before record changes by the operation order.
11. **What would you do with another week?** Ground the identifier-less matching with extra evidence checks, model
    dependencies between copies, flag conflicts like `case_63` in the output, test the vision fallback, and measure on a
    held-out set.
12. **How much did it cost?** 375 `gpt-4o-mini` calls, 146,416 tokens, about 2.7 cents, around 283 tokens per request.
13. **How is it deterministic?** No sampling in the core, temperature 0 on the model call, stable sorting, results cached;
    two runs (and a cold-cache run) are byte-identical.
14. **How did you use AI to build it?** Claude Code wrote and tested it; every turn is logged in `log.txt`; independent
    AI sessions reviewed it using a written QA brief (`TESTING_PROMPT.md`).
15. **What are the limits?** Section 7.

---

## 12. Numbers to remember

518 requests - 32 samples - 850 users - 4,011 activity events - 94 evidence files - 15 rules - 10 non-deletion cases
(533-542) - 353 / 155 / 10 (incomplete / complete / not applicable) - samples 100% status, 100% precision, 98.4% recall,
29/32 exact - 375 model calls, 146,416 tokens, ~USD 0.027 - 3 unrecoverable sample steps - 31 statuses fixed by the
`collection_name` bug fix - 68.8% -> 100% after the classifier fix.

## 13. Glossary

* **Ghost data**: personal data that survives a "completed" deletion.
* **Audit time (`audit_at`)**: the instant the state must describe.
* **Store**: one concrete copy of data (a database table, a replica, a log source).
* **Replication drift**: replicas disagreeing about whether a record exists.
* **Tombstone**: deleted account's residual record keeping only `user_N`.
* **Catalog link**: `LINK_RESOURCE_IDENTITY` activity row binding a resource to a person.
* **Observation (`Obs`)**: one sighting of a resource at a time with identifiers and state.
* **Identifier-less resource**: a resource with no email/hash/phone/user reference in any evidence.

---

## 14. Production viability and monitoring (the judge asks this late in the interview)

**Would you run this in production? Yes, as a decision-support auditor, with the limits below.**

* **Repeatable.** Same inputs give byte-identical output (checked across runs, cold cache and hash seeds). Any answer can
  be replayed and explained from the cited evidence file.
* **Validated before use.** `validate_output.py` rejects bad format, wrong order, missing/forbidden evidence ids and
  evidence newer than `audit_at`. In production it would run on every batch and block publishing on any problem.
* **Cheap and bounded model use.** One call per distinct request text, cached; 375 calls cost about 2.7 cents. Nothing the
  model returns can change a case's audit logic, only whether it is audited, and a clear deletion request cannot be vetoed.
* **Graceful degradation.** No key, invalid key or outage -> heuristic triage; `--no-llm` makes zero model calls.
* **What I would monitor:**
  1. Disagreement rate between the model's triage and the deterministic check (a jump means a prompt or model drift).
  2. Share of cases with identifier-less resources resolved by timing, and how many were ambiguous pairs (our weakest link).
  3. Counts per status and per finding type per batch; a sudden shift flags a parsing change in an upstream export.
  4. Evidence parsing coverage: files in the manifest that produced zero observations (a format change).
  5. Token and cost totals from the usage log.
* **Regression safety.** Re-run the 32 samples and the custom cases on every change (they run in seconds); a change that
  moves any status needs a reason. The two real regressions we shipped were caught this way or by independent QA.
* **What is not production-ready.** Matching by timing is a heuristic; real systems should write the case/resource link when
  the deletion job runs. The planner has no dependency graph. OCR rules are tuned to these console layouts. There is no
  unit-test suite beyond the sample, custom-case and format checks.

## 15. Know your code: a 5-minute walkthrough you can give

1. `main.py`: loads the world once, loops over requests; triage first; then `Solver.solve(q)`.
2. `evidence.py`: every evidence file becomes `Obs` records; `facts()` (in `engine.py`) reduces each to exists / identifier
   / flow enabled / restore allowed.
3. `engine.World.evaluate(rid, requested_at, audit_at)`: collects observations in the window, groups them into stores, takes
   the latest per store, and reports a violation if any store violates the required action for that resource.
4. `linking.py`: finds accounts and anonymized analytics rows that have no identifier, using the activity log (result
   matching, elimination, seconds-offset likelihood).
5. `planner.plan(states)`: any violation -> INCOMPLETE = findings + remediation + verification; otherwise COMPLETE =
   evidence-backed verifications; final sort enforces the required order.

**Dead code you should know about (honest):** `linking._window`, `linking._has_account_link`, `evidence.pdf_text` and two
unused imports in `multimodal.py` (`HASH_RE`, `RID_RE`) and one in `evidence.py` (`Path`) are leftovers. They do nothing.
The vision fallback in `llm.chat_vision` is untested against real calls. Say so rather than defend them.

## 16. What I directed versus what the AI did (for "how did you work with your tools")

Fill this in with your own words before the interview. Facts you can use: you chose the goal (win, finish today), required
independent testers and gave me their reports, rejected doing the interview before the video, asked for one file covering
everything, and decided what to submit. Decisions that came from reading evidence: the first model run's 68.8% result
(you flagged it), the `collection_name` defect (QA found it). Say which parts you understand and which you took on trust.

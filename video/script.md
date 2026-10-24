# Ghost Data Still Exists - explainer video narration

Voice: ElevenLabs "Alice" (`Xb7hH8MSUJpSbSDYk0k2`), model `eleven_multilingual_v2`. Generated from `video/src/chapters.py`; cue markers are removed.

## Chapter 1 - The ghost (plain language)

A shop called Northstar lost two point four million dollars because of one customer who was deleted, but not really gone. Every dashboard said the deletion was complete.

Weeks later, the same person tried to sign up again, and the system said: this email is already registered. The account was supposed to be gone, so where did that email come from?

Their data was still sitting in a database replica, a search index, support attachments, exports, analytics, logs and backups. And a sync job had even re-created some of it. So the word complete was a claim, not a fact.

Think of a building inspector. The builder says the job is done. The inspector walks into every room and checks for themselves.

Our job is to build an auditor that does not trust the word complete. For each deletion request, it checks what is really left, decides complete, incomplete, or not applicable, and lists the steps to fix it. Getting this wrong costs money and trust, so the auditor must show its evidence for every step.

## Chapter 2 - What we get and what we hand in (plain language)

Everything we get is in the dataset folder. There are 518 requests to audit, and 32 sample requests with the correct answers. There are 850 customers with their current details, and a history file of changed emails and phones. An activity log holds about four thousand events from the deletion worker, syncs, backups and exports. A rules table has 15 deletion rules. And there are 94 evidence files: database snapshots, logs, JSON exports, PDFs and screenshots. The evidence files do not say whose data they hold. We have to connect them through emails, phones, hashes and record ids.

Each request has an email, which may be a current or an old address, the time it was made, what the workflow claims: complete, partially complete, or not started, and the audit time: the moment we must describe. Anything that happened after the audit time does not count.

We hand in one row per request: the case id, a status, and an ordered list of steps. Each step is a finding, a fix, or a check. Findings come first, then fixes, then checks, and every finding must cite the evidence file that proves it.

## Chapter 3 - The rules (plain language)

The rules table decides what must happen to each kind of record. Delete: the profile, search entries, cache entries, user exports, marketing profiles, and attachments that belong only to this person.

Redact means keep the record, but remove names and emails. That applies to shared support messages and email logs. Anonymize means cut the link to the person. That applies to analytics and telemetry.

Retain covers security audit logs inside their retention period, legal holds, and backups, as long as restoring them can be blocked.

And one special case: the tombstone. A deleted account may keep only its internal user id, so other records still point somewhere. The name, email, phone and email hash are removed.

So, complete means three things. Every copy got the right treatment. Nothing can re-create the data. And what must be kept is still there.

## Chapter 4 - Our solution in one picture (plain language)

Our solution works in six steps. Step one: is this a deletion request at all? Ten requests, cases 533 to 542, ask for things like a new phone number, or no more promotional emails. They get not applicable, with no steps. Step two: who is this person? The request email may be an old one, so we use the history file to collect every email, phone and hash they ever had. Step three: read every evidence file into one common format: this resource, at this time, with these identifiers, in this state. Step four: decide which resources belong to the person. Step five: work out the state at the audit time, using only evidence captured by then, and apply the rules. Step six: write the findings, the fixes and the checks, in the required order.

The key design choice: ordinary code does steps two to six, so results are repeatable. The language model does one thing only: step one, reading a request in any language.

## Chapter 5 - The hard part: records with no name on them (plain language)

Some resources carry no email anywhere: an account that simply returns not found, or an analytics row that has already been anonymized. We still must report them.

The only clue is the deletion worker's activity log. Each case leaves a small cluster of rows near the time the workflow reported its result. And the result in the log usually matches the reported status: success, partial, or failed.

When several cases share the same report time, we narrow it down by elimination, and by a timing fingerprint: rows of one case keep the same offset in seconds from that case's account row. We measure that offset from the data itself, never from the answer key.

In the samples, cases 25 and 26 share a report time, and so do cases 27 and 28. Accounts 3136 and 5684, and accounts 3866 and 5482, are told apart this way. It is a strong clue, not a proof, which is why we list it as a limit later.

## Chapter 6 - One worked example: case 05 (plain language)

Here is one worked example: case 5. On 27 August, Leila Haddad asked us to remove any remaining copy of her profile. The workflow said complete on 28 August. The audit time is 8 September.

Evidence 90, a snapshot of the account service from 5 September, lists no account for her. A naive check says done. But evidence 54, a failover replica captured on 2 September at eleven at night, still holds account zero zero five, with her name, email and phone.

A snapshot only proves absence for its own database, not for every copy. So the account is still present, and the case is incomplete.

The output has three steps. A finding: report remaining record, account zero zero five, citing evidence 54. A fix: delete the record. A check: verify the record is absent. The fix and the check carry no evidence id, because they describe future work.

## Chapter 7 - Results, and the mistake we caught (interview language)

Now the results. On the 32 public samples: status accuracy is 100 percent, step precision 100 percent, step recall 98.4 percent, and 29 of 32 cases match the answer exactly, in order.

The three misses are account 004, and audit records 6645 and 5569. None of them appears anywhere in the participant data, so we do not guess ids.

There is no answer key for the 518 real cases, so we claim consistency with the spec, not a percentage. The full output passes a validator for format, for order, and for the rule that no evidence newer than the audit time is cited.

Now, the mistake we caught. Our first model-assisted run dropped sample status accuracy to 68.8 percent. GPT-4o mini labelled real requests, such as asking us to verify an account is gone, as not deletion requests, and that emptied those cases. We rewrote the prompt, made the model unable to veto without an explicit decline, and added a deterministic guard. Even a model that rejects everything now yields exactly cases 533 to 542.

The final run: 375 model calls, 146,396 tokens, about 2.7 cents, and output identical to the no-model run.

## Chapter 8 - Limits and the questions you will be asked (interview language)

First, the limits. Records that appear nowhere cannot be reported. The timing match for records without identifiers can pair wrongly when cases share a report time. The model path was only checked against the samples. And the vision fallback is untested.

Question one: how do you know it works with no answer key? The samples, four hand-built cases, a validator, a second no-model run that must be identical, and independent testers. We never claim a percentage on the 518.

Question two: what does the model do? It only decides whether a request asks for deletion. Everything else is code, so the output is repeatable and costs cents.

Question three: why not let the model read all the evidence? Cost, repeatability, and it is easy for a model to get ordering and evidence ids wrong. Code can be tested.

Question four: how do you handle replica drift? State is tracked per store. Any store still holding the record keeps it non-compliant.

Question five: what about evidence from the future? Anything captured after the audit time is never used for state, and never cited.

Question six: how are records without identifiers matched? By activity-log clusters near the report time, matched by result, by elimination, and by a self-calibrated seconds offset. This is the part most likely to lose points.

Question seven: what would you do next? Add more evidence-grounded checks for those matches, and test the vision fallback.

To sum up: 518 requests audited, 100 percent status accuracy on the samples, and under three cents of model cost. Don't trust the word complete. Check every copy.

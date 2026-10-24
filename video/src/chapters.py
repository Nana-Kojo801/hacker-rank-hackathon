"""Narration for the explainer video, split into chapters and scenes.

Each scene id matches a <section id="..."> in scenes.html.  A marker such as [1] inside the text is a cue:
it is removed before text-to-speech, and its position is mapped to a time with the voice alignment so the
scene can reveal an element exactly when that phrase is spoken.
"""

CHAPTERS = [
    {
        "title": "The ghost",
        "tag": "Plain language",
        "scenes": [
            ("c1_dashboard", "A shop called Northstar lost two point four million dollars because of one customer "
             "who was deleted, but not really gone. [1]Every dashboard said the deletion was complete."),
            ("c1_signup", "Weeks later, the same person tried to sign up again, and the system said: "
             "[1]this email is already registered. [2]The account was supposed to be gone, so where did that email come "
             "from?"),
            ("c1_systems", "Their data was still sitting in [1]a database replica, a search index, support attachments, exports, analytics, "
             "logs and backups. [2]And a sync job had even re-created some of it. [3]So the word complete was a "
             "claim, not a fact."),
            ("c1_inspector", "Think of a building inspector. [1]The builder says the job is done. [2]The inspector "
             "walks into every room and checks for themselves."),
            ("c1_job", "Our job is to build an auditor that does not trust the word complete. [1]For each deletion "
             "request, it checks what is really left, [2]decides complete, incomplete, or not applicable, "
             "[3]and lists the steps to fix it. [4]Getting this wrong costs money and "
             "trust, so the auditor must show its evidence for every step."),
        ],
    },
    {
        "title": "What we get and what we hand in",
        "tag": "Plain language",
        "scenes": [
            ("c2_inputs", "Everything we get is in the dataset folder. [1]There are 518 requests to audit, and 32 "
             "sample requests with the correct answers. [2]There are 850 customers with their current details, "
             "[3]and a history file of changed emails and phones. [4]An activity log holds about four thousand "
             "events from the deletion worker, syncs, backups and exports. [5]A rules table has 15 deletion rules. "
             "[6]And there are 94 evidence files: database snapshots, logs, JSON exports, PDFs and screenshots. [7]The evidence files do not say whose data they hold. We have to connect them "
             "through emails, phones, hashes and record ids."),
            ("c2_request", "Each request has an email, which may be a current or an old address, [1]the time it was "
             "made, [2]what the workflow claims: complete, partially complete, or not started, [3]and the audit "
             "time: the moment we must describe. Anything that happened after the audit time does not count."),
            ("c2_output", "We hand in one row per request: [1]the case id, a status, [2]and an ordered list of steps. "
             "[3]Each step is a finding, a fix, or a check. [4]Findings come first, then "
             "fixes, then checks, and every finding must cite the evidence file that proves it."),
        ],
    },
    {
        "title": "The rules",
        "tag": "Plain language",
        "scenes": [
            ("c3_delete", "The rules table decides what must happen to each kind of record. [1]Delete: the profile, "
             "search entries, cache entries, user exports, marketing profiles, and attachments that belong only to "
             "this person."),
            ("c3_redact", "[1]Redact means keep the record, but remove names and emails. That applies to shared "
             "support messages and email logs. [2]Anonymize means cut the link to the person. That applies to "
             "analytics and telemetry."),
            ("c3_retain", "[1]Retain covers security audit logs inside their retention period, [2]legal holds, "
             "[3]and backups, as long as restoring them can be blocked."),
            ("c3_tombstone", "And one special case: the tombstone. [1]A deleted account may keep only its internal "
             "user id, so other records still point somewhere. [2]The name, email, phone and email hash are removed."),
            ("c3_complete", "So, complete means three things. [1]Every copy got the right treatment. [2]Nothing can "
             "re-create the data. [3]And what must be kept is still there."),
        ],
    },
    {
        "title": "Our solution in one picture",
        "tag": "Plain language",
        "scenes": [
            ("c4_pipeline", "Our solution works in six steps. [1]Step one: is this a deletion request at all? Ten "
             "requests, cases 533 to 542, ask for things like a new phone number, or no more promotional emails. "
             "They get not applicable, with no steps. [2]Step two: who is this person? The request email may be an "
             "old one, so we use the history file to collect every email, phone and hash they ever had. [3]Step "
             "three: read every evidence file into one common format: this resource, at this time, with these "
             "identifiers, in this state. [4]Step four: decide which resources belong to the person. [5]Step five: "
             "work out the state at the audit time, using only evidence captured by then, and apply the rules. "
             "[6]Step six: write the findings, the fixes and the checks, in the required order."),
            ("c4_design", "The key design choice: [1]ordinary code does steps two to six, so results are repeatable. "
             "[2]The language model does one thing only: step one, reading a request in any language."),
        ],
    },
    {
        "title": "The hard part: records with no name on them",
        "tag": "Plain language",
        "scenes": [
            ("c5_noname", "Some resources carry no email anywhere: [1]an account that simply returns not found, "
             "[2]or an analytics row that has already been anonymized. [3]We still must report them."),
            ("c5_timeline", "The only clue is the deletion worker's activity log. [1]Each case leaves a small cluster "
             "of rows near the time the workflow reported its result. [2]And the result in the log usually matches "
             "the reported status: success, partial, or failed."),
            ("c5_offset", "When several cases share the same report time, we narrow it down by elimination, [1]and "
             "by a timing fingerprint: [2]rows of one case keep the same offset in seconds from that case's account "
             "row. [3]We measure that offset from the data itself, never from the answer key."),
            ("c5_example", "In the samples, cases 25 and 26 share a report time, and so do cases 27 and 28. "
             "[1]Accounts 3136 and 5684, [2]and accounts 3866 and 5482, are told apart this way. [3]It is a strong "
             "clue, not a proof, which is why we list it as a limit later."),
        ],
    },
    {
        "title": "One worked example: case 05",
        "tag": "Plain language",
        "scenes": [
            ("c6_case", "Here is one worked example: case 5. [1]On 27 August, Leila Haddad asked us to remove any "
             "remaining copy of her profile. [2]The workflow said complete on 28 August. [3]The audit time is "
             "8 September."),
            ("c6_snapshots", "Evidence 90, a snapshot of the account service from 5 September, lists no account for "
             "her. [1]A naive check says done. [2]But evidence 54, a failover replica captured on 2 September at "
             "eleven at night, still holds account zero zero five, with her name, email and phone."),
            ("c6_verdict", "A snapshot only proves absence for its own database, not for every copy. [1]So the "
             "account is still present, and the case is incomplete."),
            ("c6_steps", "The output has three steps. [1]A finding: report remaining record, account zero zero five, "
             "citing evidence 54. [2]A fix: delete the record. [3]A check: verify the record is absent. [4]The fix "
             "and the check carry no evidence id, because they describe future work."),
        ],
    },
    {
        "title": "Results, and the mistake we caught",
        "tag": "Interview language",
        "scenes": [
            ("c7_scores", "Now the results. On the 32 public samples: [1]status accuracy is 100 percent, [2]step "
             "precision 100 percent, [3]step recall 98.4 percent, [4]and 29 of 32 cases match the answer exactly, "
             "in order."),
            ("c7_misses", "The three misses are account 004, and audit records 6645 and 5569. [1]None of them "
             "appears anywhere in the participant data, so we do not guess ids."),
            ("c7_validator", "There is no answer key for the 518 real cases, so we claim consistency with the spec, "
             "not a percentage. [1]The full output passes a validator for format, [2]for order, [3]and for the rule "
             "that no evidence newer than the audit time is cited."),
            ("c7_mistake", "Now, the mistake we caught. [1]Our first model-assisted run dropped sample status "
             "accuracy to 68.8 percent. [2]GPT-4o mini labelled real requests, such as asking us to verify an "
             "account is gone, as not deletion requests, and that emptied those cases. [3]We rewrote the prompt, "
             "made the model unable to veto without an explicit decline, and added a deterministic guard. [4]Even "
             "a model that rejects everything now yields exactly cases 533 to 542."),
            ("c7_cost", "The final run: [1]375 model calls, [2]146,396 tokens, [3]about 2.7 cents, [4]and output "
             "identical to the no-model run."),
        ],
    },
    {
        "title": "Limits and the questions you will be asked",
        "tag": "Interview language",
        "scenes": [
            ("c8_limits", "First, the limits. [1]Records that appear nowhere cannot be reported. [2]The timing match "
             "for records without identifiers can pair wrongly when cases share a report time. [3]The model path was "
             "only checked against the samples. [4]And the vision fallback is untested."),
            ("c8_q1", "Question one: how do you know it works with no answer key? [1]The samples, four hand-built "
             "cases, a validator, a second no-model run that must be identical, and independent testers. We never "
             "claim a percentage on the 518."),
            ("c8_q2", "Question two: what does the model do? [1]It only decides whether a request asks for deletion. "
             "Everything else is code, so the output is repeatable and costs cents."),
            ("c8_q3", "Question three: why not let the model read all the evidence? [1]Cost, repeatability, and it "
             "is easy for a model to get ordering and evidence ids wrong. Code can be tested."),
            ("c8_q4", "Question four: how do you handle replica drift? [1]State is tracked per store. Any store still "
             "holding the record keeps it non-compliant."),
            ("c8_q5", "Question five: what about evidence from the future? [1]Anything captured after the audit time "
             "is never used for state, and never cited."),
            ("c8_q6", "Question six: how are records without identifiers matched? [1]By activity-log clusters near "
             "the report time, matched by result, by elimination, and by a self-calibrated seconds offset. This is "
             "the part most likely to lose points."),
            ("c8_q7", "Question seven: what would you do next? [1]Add more evidence-grounded checks for those "
             "matches, and test the vision fallback."),
            ("c8_close", "To sum up: 518 requests audited, 100 percent status accuracy on the samples, and under "
             "three cents of model cost. [1]Don't trust the word complete. Check every copy."),
        ],
    },
]

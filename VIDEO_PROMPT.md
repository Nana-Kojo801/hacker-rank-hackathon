# Prompt for the video-building session

Repo: nana-kojo801/hacker-rank-hackathon, branch ccr-c9f46477-fkdlnv. Read AGENTS.md first and follow its log.txt rules
(append a SESSION START entry and a per-turn entry; tool=Claude Code, model=the exact id you run as).

## Goal

Build an explainer video (target 10-12 minutes, 8 chapters, plus one MP4 per chapter) that teaches me, a beginner, the
HackerRank Orchestrate "Ghost Data Still Exists" problem and our solution, so that I can pass the AI interview about it.
Plain language in chapters 1-6, interview language in chapters 7-8. All facts must come from this repository; if you are
unsure of a number, compute it from the files rather than guessing. Do not change anything under `code/` or `dataset/`.

## Tools and secrets

* Voice: ElevenLabs. Read the key from the environment variable `ELEVENLABS_API_KEY` (check with
  `test -n "$ELEVENLABS_API_KEY"`; never print it, never commit it, never ask me to paste it in chat; if missing, stop).
  Pick a clear, calm English voice from the account's voice list, use one voice for the whole video, model
  `eleven_multilingual_v2`, and cache each chapter's MP3 so re-runs do not spend credits.
* Visuals: HTML/CSS/SVG scenes (labelled boxes, arrows, tables, highlighted rows) animated with CSS/JS, rendered with
  Playwright (Chromium is pre-installed; do not run `playwright install`), 1920x1080, 30 fps, recorded and muxed with
  ffmpeg. Scene timing must be driven by the narration audio durations (measure with ffprobe) so picture and voice stay in
  sync. Large readable text, high contrast, one idea per scene, no stock footage.
* Output into `video/` : `chapter_01.mp4` ... `chapter_08.mp4`, `full.mp4`, `script.md` (the exact narration with
  chapter headings), `captions.srt`. Burn captions in `full.mp4`. Commit `script.md`, `captions.srt` and the scene source;
  do not commit large binaries or audio caches (add them to .gitignore) - tell me where the MP4s are.

## Narration script (use verbatim as the base; tighten wording if a sentence is hard to say aloud)

### Chapter 1 - The ghost (plain language, ~1.5 min)
A shop called Northstar lost 2.4 million dollars because of a customer who was "deleted" but not really gone. Every
dashboard said the deletion was Complete. Weeks later the same person tried to sign up again and the system said: this
email is already registered. Their data was still sitting in a search index, support attachments, exports, analytics,
logs and backups, and a sync job had even re-created some of it. Our job: build an auditor that does not trust the word
"Complete". For each deletion request it must check what is really left, decide COMPLETE, INCOMPLETE or NOT_APPLICABLE,
and list the steps to fix it. Visual: a dashboard with a green "Complete" tick; a magnifier reveals records hiding in
eight systems; a sync arrow pulling a deleted record back.

### Chapter 2 - What we get and what we must hand in (~1.5 min)
Inputs, all in the `dataset` folder: 518 requests to audit and 32 sample requests with the correct answers; about 850
customers with current details and a history file of changed emails and phones; an activity log of about 4,000 events from
the deletion worker, syncs, backups and exports; a table of 15 deletion rules; and 94 evidence files: SQL database
snapshots, logs, JSON exports, PDFs and screenshots. Each request has an email, when it was made, what the workflow
claims, and the audit time - the moment we must describe. Output: one row per request: the case id, a status, and an
ordered list of steps, each step being a finding, a fix, or a check. Visual: file icons flowing into a funnel; the output
row shape `case_id | deletion_status | steps_json` with a sample step highlighted.

### Chapter 3 - The rules (~1.5 min)
The rules table decides what must happen to each kind of record. Delete: the profile, search entries, cache entries, user
exports, marketing profiles, attachments that belong only to this person. Redact, meaning keep the record but remove names
and emails: shared support messages and email logs. Anonymize, meaning cut the link to the person: analytics and
telemetry. Retain: security audit logs inside their retention period, legal holds, and backups, as long as restoring them
can be blocked. And one special case, the tombstone: a deleted account may keep only its internal user id so other
records still point somewhere, with the name, email, phone and email hash removed. Complete means every copy got the right
treatment, nothing can re-create the data, and what must be kept is still there. Visual: a three-lane table
(DELETE / REDACT-ANONYMIZE / RETAIN) with record types sliding into lanes; a tombstone card with fields struck out except
`user_id`.

### Chapter 4 - Our solution in one picture (~1.5 min)
Six steps. One: is this a deletion request at all? Ten requests, cases 533 to 542, are things like "change my phone
number" or "stop the promotional emails" and get NOT_APPLICABLE with no steps. Two: who is this person? The email in the
request may be an old one, so we use the history file to collect every email, phone and hash they ever had. Three: read
every evidence file into one common format: this resource, at this time, with these identifiers and this state. Four:
decide which resources belong to the person. Five: work out the state at the audit time, using only evidence captured by
then, and apply the rules. Six: write the findings, the fixes and the checks in the required order. The important design
choice: ordinary code does steps two to six, so results are repeatable. The language model is used for one thing only,
step one, reading a request in any language.
Visual: a left-to-right pipeline of six boxes; the "model" badge only on box one, "code" badges on the rest.

### Chapter 5 - The hard part: records with no name on them (~1.5 min)
Some resources carry no email anywhere: an account that simply returns "not found", or an analytics row that has already
been anonymized. We still must report them. The only clue is the deletion worker's activity log. Each case leaves a small
cluster of rows near the time the workflow reported its result, and the result in the log usually matches the reported status:
SUCCESS, PARTIAL or FAILED. When several cases share the same report time, we narrow it down by elimination, and by a
timing fingerprint: rows of one case keep the same offset in seconds from that case's account row. We measure that offset
from the data itself, never from the answer key. Example from the samples: cases 25 and 26 share a report time, and so do cases 27 and 28;
`account_3136` and `account_5684`, and `account_3866` and `account_5482`, are told apart this way. It is a strong clue, not a
proof, which is why we call it out as a limit later.
Visual: a timeline with colored dots per case; dots slide into case columns; a seconds-offset ruler snapping to a
repeating value.

### Chapter 6 - One worked example: case_05 (~1.5 min)
Leila Haddad asked to close her account on 27 August. The workflow said Complete on 28 August. The audit time is 8
September. Evidence_90, the primary database snapshot from 5 September, no longer lists her account. A naive check says
done. But evidence_54, a failover replica captured on 2 September at 23:00, still holds `account_005` with her name,
email and phone. A snapshot only proves absence for its own database, not for every copy, so the account is still
present: INCOMPLETE. The output: finding, report remaining record `account_005`, citing evidence_54; fix, delete the
record; check, verify the record is absent. The fix and the check carry no evidence id because they describe future work.
Visual: two database cards (primary: empty; failover replica: row highlighted in red) and the three output steps
appearing below.

### Chapter 7 - Results, and the mistake we caught (interview language, ~1.5 min)
On the 32 public samples: status accuracy 100 percent, step precision 100 percent, step recall 98.4 percent, and 29 of 32
cases match the answer exactly, in order. The three misses are `account_004`, `audit_record_6645` and `audit_record_5569`,
which appear nowhere in the participant data, so we do not guess ids. There is no answer key for the 518 real cases, so
we claim consistency with the spec, not a percentage. The full output passes a validator for format, order, and the rule
that no evidence newer than the audit time is cited. The mistake: our first model-assisted run dropped sample accuracy to
68.8 percent. gpt-4o-mini wrongly labelled real requests, such as "I deleted my account, please verify it is gone", as not
deletion requests, emptying those cases. We rewrote the prompt, made the model unable to veto without an explicit decline,
and added a deterministic guard; even a model that rejects everything now yields exactly cases 533 to 542. The final run:
375 model calls, 146,396 tokens, about 2.7 cents, output identical to the no-model run. Visual: a score card, a red 68.8%
bar turning into 100%, a cost counter.

### Chapter 8 - Limits and the questions you will be asked (interview language, ~2 min)
Limits: records that appear nowhere cannot be reported; the timing match for identifier-less records can pair wrongly
when cases share a report time; the model path was only checked against the samples; the vision fallback is untested.
Likely questions and short answers, shown one per card:
1. How do you know it works with no answer key? - Samples, four hand-built cases, a validator, a second no-model run
   that must be identical, and independent testers; we never claim a percentage on the 518.
2. What does the model do? - Only decides whether a request asks for deletion; everything else is code, so output is
   repeatable and costs cents.
3. Why not let the model read all the evidence? - Cost, repeatability, and it is easy to get ordering and evidence ids
   wrong; code can be tested.
4. How do you handle replica drift? - State is tracked per store; any store still holding the record keeps it non-compliant.
5. What about evidence from the future? - Anything captured after the audit time is never used for state and never cited.
6. How are records without identifiers matched? - Activity-log clusters near the report time, matched by result, elimination
   and a self-calibrated seconds offset; this is the part most likely to lose points.
7. What would you do next? - Add more evidence-grounded checks for those matches and test the vision fallback.
Visual: question cards flipping to answer cards, then a closing slide with the key numbers.

## Quality bar

* After rendering, extract one frame per scene (ffmpeg) and look at them: no overlapping text, nothing cut off, every
  number matches the repo. Run `ffprobe` and report total duration and per-chapter durations.
* Verify each number in the script against the repo (counts from the CSVs, scores from
  `code/evaluation/evaluation_report.md`, usage from `code/evaluation/usage_report.md`). List any you changed.
* Finish with: where the files are, durations, voice used, ElevenLabs characters consumed, and anything you could not do.

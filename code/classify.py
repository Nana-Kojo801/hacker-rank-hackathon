"""Does the request actually authorise deletion?  LLM when available, multilingual-safe heuristic otherwise."""
import re
import sys
from pathlib import Path

import llm

SYSTEM = (Path(__file__).parent / "prompts" / "classify_request.txt").read_text(encoding="utf-8").strip()

# the customer clearly refuses deletion, or only asks how it works
DECLINE = re.compile(
    r"not (asking|requesting|a request)|do not (close|delete|erase|remove|change)|don'?t (delete|close|remove|erase|change)|"
    r"(don'?t|do not) want you to|leave (the|my) (account|profile)|keep (the|my) (account|profile)|without removing|"
    r"how (do i|to|can i) (delete|close|erase)|explain the steps|"
    r"no (borren|eliminen|cierren|quiero que)|ne (supprimez|fermez|effacez) pas|"
    r"n[aã]o (apague|exclua|feche|quero (apagar|excluir))|nicht (l[oö]schen|schlie[sß]en)|"
    r"削除しないで|閉鎖しないで|삭제하지 (말|마)",
    re.I)
# the customer wants something else done with the account
OTHER_TOPIC = re.compile(
    r"marketing lists?|mailing list|promotional|information request|download my|portable format|"
    r"(need|send me|give me|want|get|access to) (a )?(copy of|my personal information|the information)|"
    r"invoices?|phone number|mobile number|replace it|misspelled|reset the login|change the email|"
    r"continue (using|to use)|what personal information|still (use|need|want)|update my|correct it|"
    r"s[oó]lo quiero actualizar|solo quiero actualizar",
    re.I)
# unambiguous request to delete the account / data
AFFIRMATIVE = re.compile(
    r"(delet\w*|eras\w*|remov\w*|clos\w*) (my|the|this|that|all|any)( \w+)? (account|profile|data|personal|export|"
    r"records?|copies|copy of my profile)|permanent(ly)? (delet|account)|account[- ]deletion|deletion (of|process|request)|"
    r"eliminaci[oó]n|suppression|suppr|exclus[aã]o|exclus|削除|消去|삭제|l[oö]schen",
    re.I)
STRONG_DELETION = re.compile(
    r"delet|erase|erasure|remove (my|the) (account|profile|data|personal)|close (my|this|the) account|closed|"
    r"permanent|elimin|borr|suppress|suppr|effac|exclu|apag|lösch|löschen|削除|消去|삭제|"
    r"traces?|remove (records|everything|any)|switch off|inspect the actual|privacy page|"
    r"still (found|exists?|recogni[sz]ed|appears?|works?|active)|remaining|nothing remains|verify|confirm that",
    re.I)


def heuristic(text):
    """Deterministic triage (also the guard around the model): a positive deletion signal is required."""
    if DECLINE.search(text):
        return False
    if AFFIRMATIVE.search(text):
        return True
    if OTHER_TOPIC.search(text):
        return False
    return bool(STRONG_DELETION.search(text))


def authorizes_deletion(text, use_llm=True):
    """Returns (bool, method).

    A request is treated as non-deletion only when the model says it does not authorise deletion *and* states that
    the customer explicitly declines it.  A wrong "not a deletion request" silently drops a whole audit, so the
    model may never veto on its own judgement of an unclear text; the deterministic fallback is used when no
    model is available.
    """
    if use_llm and llm.available():
        try:
            res = llm.chat_json(SYSTEM, text, purpose="classify_request")
        except RuntimeError as e:            # outage or invalid key: degrade to the deterministic triage
            print(f"warning: model unavailable ({str(e)[:80]}); using heuristic triage", file=sys.stderr)
            return heuristic(text), "heuristic"
        declines = bool(res.get("explicitly_declines_deletion")) and not bool(res.get("authorizes_deletion", True))
        # guard: clear deletion language with no limiting phrase can never be vetoed by the model alone
        if declines and heuristic(text):
            declines = False
        return (not declines), "llm"
    return heuristic(text), "heuristic"

"""Does the request actually authorise deletion?  LLM when available, multilingual-safe heuristic otherwise."""
import re
from pathlib import Path

import llm

SYSTEM = (Path(__file__).parent / "prompts" / "classify_request.txt").read_text(encoding="utf-8").strip()

NEGATIVE = re.compile(
    r"not (asking|requesting|a request)|do not (close|delete|erase|remove)|don'?t (delete|close|remove|change)|"
    r"leave (the|my) (account|profile)|keep (the|my) account|still (use|need|want)|marketing lists? only|"
    r"stop the promotional|information request|download my|(need|send me|give me|want|get) (a )?copy of|portable format|replace it|misspelled|"
    r"reset the login|change the email|continue (using|to use)|without removing|what personal information|"
    # the same ideas in other languages (fallback when no model is available)
    r"no (borren|eliminen|cierren|quiero (borrar|eliminar))|ne (supprimez|fermez|effacez) pas|"
    r"n[aã]o (apague|exclua|feche|quero (apagar|excluir))|nicht (l[oö]schen|schlie[sß]en)|"
    r"削除しないで|閉鎖しないで|삭제하지 (말|마)|sólo quiero actualizar|solo quiero actualizar",
    re.I)


STRONG_DELETION = re.compile(
    r"delet|erase|erasure|remove (my|the) (account|profile|data|personal)|close (my|this|the) account|closed|"
    r"permanent|elimin|borr|suppress|suppr|effac|exclu|apag|lösch|löschen|削除|消去|삭제|"
    r"traces?|remove (records|everything|any)|switch off|inspect the actual|privacy page|still (found|exists?|recogni[sz]ed|appears?|works?|active)|remaining|nothing remains|verify|confirm that",
    re.I)


def heuristic(text):
    return not NEGATIVE.search(text)


def authorizes_deletion(text, use_llm=True):
    """Returns (bool, method).

    A request is treated as non-deletion only when the model says it does not authorise deletion *and* states that
    the customer explicitly declines it.  A wrong "not a deletion request" silently drops a whole audit, so the
    model may never veto on its own judgement of an unclear text; the deterministic fallback is used when no
    model is available.
    """
    if use_llm and llm.available():
        res = llm.chat_json(SYSTEM, text, purpose="classify_request")
        declines = bool(res.get("explicitly_declines_deletion")) and not bool(res.get("authorizes_deletion", True))
        # guard: clear deletion language without any limiting phrase can never be vetoed by the model alone
        if declines and STRONG_DELETION.search(text) and not NEGATIVE.search(text):
            declines = False
        return (not declines), "llm"
    return heuristic(text), "heuristic"

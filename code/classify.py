"""Does the request actually authorise deletion?  LLM when available, multilingual-safe heuristic otherwise."""
import re

import llm

SYSTEM = (
    "You triage privacy requests for an online shop. Decide whether the customer is asking for their account "
    "and personal data to be deleted/erased/closed. Requests for access, a copy of data, correction, "
    "marketing opt-out, login help or changing details are NOT deletion requests, even if they mention "
    "words like remove or delete (for example 'remove me from marketing lists only' or 'do not close my "
    "account'). The text can be in any language. Reply with JSON: "
    '{"authorizes_deletion": true|false, "reason": "<short>"}'
)

NEGATIVE = re.compile(
    r"not (asking|requesting|a request)|do not (close|delete|erase|remove)|don'?t (delete|close|remove|change)|"
    r"leave (the|my) (account|profile)|keep (the|my) account|still (use|need|want)|marketing lists? only|"
    r"stop the promotional|information request|download my|copy of|portable format|replace it|misspelled|"
    r"reset the login|change the email|continue (using|to use)|without removing|what personal information",
    re.I)


def heuristic(text):
    return not NEGATIVE.search(text)


def authorizes_deletion(text, use_llm=True):
    """Returns (bool, method)."""
    if use_llm and llm.available():
        res = llm.chat_json(SYSTEM, text, purpose="classify_request")
        return bool(res.get("authorizes_deletion")), "llm"
    return heuristic(text), "heuristic"

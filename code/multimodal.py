"""Screenshots and PDFs -> observations.

Screenshots are read with an offline OCR engine (RapidOCR) whose output is cached under code/.cache/ocr/;
PDFs go through `pdftotext`.  Both end up as text lines which are bound to resources in two ways:

  * row binding   - a resource id and identifiers on the same visual line describe the same record;
  * catalog links - `LINK_RESOURCE_IDENTITY` activity rows map a resource id (and an alias such as a
                    statement number, file name or customer key shown in the document) to its owner.  A link
                    applies to a document when its alias/id occurs in the document text and the link was
                    logged within a few hours of the document's capture time.
"""
import csv
import json
import re
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

from evidence import (EMAIL_RE, HASH_RE, PHONE_RE, PREFIX_SYSTEM, RID_RE, USER_RE, Obs, norm_email, norm_phone,
                      system_of)

CACHE = Path(__file__).parent / ".cache" / "ocr"
TS = "%Y-%m-%dT%H:%M:%SZ"
LINK_RE = re.compile(r"(?P<rid>\w+_\w+) \((?P<alias>[^)]+)\).*? (?:to|only to) (?P<email>\S+@\S+) and (?P<user>user_\d+)")
LINK_RE2 = re.compile(r"(?P<rid>\w+_\w+) \((?P<alias>[^)]+)\) belongs only to (?P<email>\S+@\S+) and (?P<user>user_\d+)")
MONTHS = {m: i for i, m in enumerate(["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1)}


def ocr_lines(path):
    """OCR a screenshot into visual lines (list of text), cached on disk."""
    CACHE.mkdir(parents=True, exist_ok=True)
    cache = CACHE / (path.name + ".json")
    if cache.exists():
        items = json.loads(cache.read_text(encoding="utf-8"))
    else:
        try:
            from rapidocr_onnxruntime import RapidOCR
        except ImportError:
            return vision_lines(path)
        res, _ = RapidOCR()(str(path))
        items = [{"text": t, "x": b[0][0], "y": b[0][1]} for b, t, _c in (res or [])]
        cache.write_text(json.dumps(items), encoding="utf-8")
    items.sort(key=lambda i: (i["y"], i["x"]))
    lines, cur, cur_y = [], [], None
    for it in items:
        if cur_y is not None and abs(it["y"] - cur_y) > 12:
            lines.append(cur)
            cur = []
        if not cur:
            cur_y = it["y"]
        cur.append(it)
    if cur:
        lines.append(cur)
    # a panel on the right half shares y with the table on the left: keep halves apart
    out = []
    for ln in lines:
        left = " ".join(i["text"] for i in sorted(ln, key=lambda i: i["x"]) if i["x"] < 1400)
        right = " ".join(i["text"] for i in sorted(ln, key=lambda i: i["x"]) if i["x"] >= 1400)
        out += [t for t in (left, right) if t.strip()]
    return out


VISION_PROMPT = (Path(__file__).parent / "prompts" / "vision_transcribe.txt").read_text(encoding="utf-8").strip()


def vision_lines(path):
    """Fallback when no OCR engine is installed: ask a vision model to transcribe the screenshot."""
    import llm
    if not llm.available():
        return []
    return [l.strip() for l in llm.chat_vision(VISION_PROMPT, path).splitlines() if l.strip()]


def pdf_lines(path):
    txt = subprocess.run(["pdftotext", "-layout", str(path), "-"], capture_output=True, text=True).stdout
    return [re.sub(r"\s{2,}", " ", l).strip() for l in txt.splitlines() if l.strip()]


DOC_RID_RE = re.compile(r"(?:" + "|".join(PREFIX_SYSTEM) + r")_\d+")


def clean_line(ln):
    """OCR glues neighbouring cells together with dots/dashes; put the separators back."""
    ln = re.sub(r"(_\d+)[-\u00b7\u2022]", r"\1 ", ln)
    ln = re.sub(r"(?<=\d)(?=(?:" + "|".join(PREFIX_SYSTEM) + r")_\d)", " ", ln)
    return re.sub(r"[\u00b7\u2022]", " ", ln)


def squash(s):
    return re.sub(r"\s+", "", s)


def parse_retention(lines):
    """'retain until 25 Aug 2027 04 03 UTC' -> ISO timestamp."""
    for l in lines:
        m = re.search(r"retain until (\d{1,2}) (\w{3}) (\d{4}) (\d{2})\s+(\d{2})", l, re.I)
        if m:
            d, mon, y, hh, mm = m.groups()
            return f"{y}-{MONTHS[mon.title()]:02d}-{int(d):02d}T{hh}:{mm}:59Z"
    return None


def link_rows(dataset):
    out = []
    with open(dataset / "system_activity.csv", newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["event_type"] != "LINK_RESOURCE_IDENTITY":
                continue
            m = LINK_RE2.search(r["details"]) or LINK_RE.search(r["details"])
            if m:
                out.append({"rid": m["rid"], "alias": m["alias"], "email": norm_email(m["email"]),
                            "user": m["user"], "t": r["event_time"]})
    return out


def doc_observations(file_id, captured, path, links):
    suffix = path.suffix.lower()
    lines = ocr_lines(path) if suffix == ".png" else pdf_lines(path)
    if not lines:
        return []
    text = "\n".join(lines)
    flat = squash(text)
    cap = datetime.strptime(captured, TS)
    out = {}

    def get(rid):
        if rid not in out:
            out[rid] = Obs(file_id, captured, captured, rid, system_of(rid), "doc:" + suffix[1:])
        return out[rid]

    # row binding: a visual line that names a resource also carries that record's identifiers
    for ln in lines:
        ln = clean_line(ln)
        for rid in dict.fromkeys(m.group(0) for m in DOC_RID_RE.finditer(ln)):
            o = get(rid)
            for e in EMAIL_RE.findall(ln):
                o.emails.add(norm_email(e))
            for u in USER_RE.findall(ln):
                o.users.add(u)
            for p in PHONE_RE.findall(ln):
                o.phones.add(norm_phone(p))
    # single-subject documents: identifiers elsewhere on the page belong to the only resource named
    if len(out) == 1:
        (only,) = out.values()
        if not (only.emails or only.users or only.phones):
            for e in EMAIL_RE.findall(text):
                only.emails.add(norm_email(e))
            only.users |= set(USER_RE.findall(text))
    # catalog links
    for k in links:
        t = datetime.strptime(k["t"], TS)
        if not (timedelta(0) <= t - cap <= timedelta(hours=3)):
            continue
        if k["rid"] in flat or k["alias"].replace(" ", "") in flat:
            o = get(k["rid"])
            o.users.add(k["user"])
            if k["email"] in flat.lower():
                o.emails.add(k["email"])
            o.attrs["catalog_link"] = True
            o.emails_hidden = {k["email"]}
    ret = parse_retention(lines)
    low = text.lower()
    res = []
    for rid, o in out.items():
        if not (o.emails or o.users or o.phones or o.attrs.get("catalog_link")):
            continue          # a resource merely mentioned in a timeline, with nothing tying it to a person
        if rid.startswith("audit_record"):
            if not ret:
                continue          # policy retains an audit record only when a retention period is supplied
            o.attrs["retention_until"] = ret
        o.attrs["from_document"] = True
        if o.system == "integration_service":       # a connector shown live in a console is an enabled data flow
            o.attrs["enabled"] = not re.search(r"paused|disabled|stopped|inactive", low)
        if o.system == "backup_service":            # an archive listed as restorable unless the console says blocked
            o.attrs["restore_allowed"] = not re.search(r"restore (blocked|disabled|denied)|access blocked", low)
        if re.search(r"attachment", low) and o.system == "support_platform":
            o.attrs["attachment"] = True
        res.append(o)
    return res


def load_documents(dataset, manifest):
    links = link_rows(dataset)
    obs = []
    for fid, row in manifest.items():
        path = dataset / row["file_path"]
        if path.suffix.lower() in (".png", ".pdf"):
            obs += doc_observations(fid, row["captured_at"], path, links)
    return obs

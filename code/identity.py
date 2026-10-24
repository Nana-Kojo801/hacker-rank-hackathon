"""Identity resolution: request email -> user_id plus every current/historical identifier."""
import csv
from dataclasses import dataclass, field

from evidence import norm_email, norm_phone


@dataclass
class Identity:
    user_id: str
    name: str = ""
    emails: set = field(default_factory=set)
    phones: set = field(default_factory=set)
    hashes: set = field(default_factory=set)
    names: set = field(default_factory=set)
    current_email: str = ""
    ambiguous: bool = False


class IdentityBook:
    def __init__(self, dataset):
        self.users = {}
        with open(dataset / "user_identities.csv", newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                i = Identity(r["user_id"], r["name"], current_email=norm_email(r["email"]))
                i.emails.add(norm_email(r["email"]))
                i.phones.add(norm_phone(r["phone"]))
                i.hashes.add(r["email_hash"].lower())
                i.names.add(r["name"].strip().lower())
                self.users[i.user_id] = i
        self.by_email = {}
        for u in self.users.values():
            for e in u.emails:
                self.by_email.setdefault(e, set()).add(u.user_id)
        with open(dataset / "user_audit_log.csv", newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                u = self.users.get(r["user_id"])
                if not u:
                    continue
                field_name = r["field_name"].lower()
                for v in (r["old_value"], r["new_value"]):
                    if not v:
                        continue
                    if "email" in field_name and "hash" not in field_name:
                        u.emails.add(norm_email(v))
                        self.by_email.setdefault(norm_email(v), set()).add(u.user_id)
                    elif "phone" in field_name:
                        u.phones.add(norm_phone(v))
                    elif "hash" in field_name:
                        u.hashes.add(v.lower())
                    elif "name" in field_name:
                        u.names.add(v.strip().lower())

    def resolve(self, email):
        ids = self.by_email.get(norm_email(email), set())
        if not ids:
            return None
        if len(ids) == 1:
            return self.users[next(iter(ids))]
        # shared historical email: prefer the user for whom it is the current email
        cur = [i for i in ids if self.users[i].current_email == norm_email(email)]
        u = self.users[(cur or sorted(ids))[0]]
        u.ambiguous = len(ids) > 1
        return u

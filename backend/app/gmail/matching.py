"""Links an email to an existing application so nothing is stored twice.

The same job can reach the database two ways: the tailor flow (company + role
from the job description) and the inbox. Both write the same normalized
company/role keys, and every new email is matched against them first.
"""

import re
from dataclasses import dataclass
from typing import Any

from rapidfuzz import fuzz

ROLE_MATCH = 85      # token_set_ratio threshold for "same job title"
COMPANY_MATCH = 92   # tolerate "Acme" vs "Acme Corp" vs "ACME, Inc."

_SUFFIXES = re.compile(
    r"\b(inc|incorporated|llc|l\.l\.c|ltd|limited|corp|corporation|co|company|plc|gmbh|"
    r"technologies|technology|labs|group|holdings)\b\.?", re.I)
_ROLE_NOISE = re.compile(r"\(.*?\)|\b(remote|hybrid|onsite|on-site|us|usa|f/t|full[- ]time)\b|#?\d{4,}", re.I)


def norm_company(name: str) -> str:
    s = _SUFFIXES.sub(" ", name.lower())
    s = re.sub(r"[^a-z0-9& ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def norm_role(title: str) -> str:
    s = _ROLE_NOISE.sub(" ", title.lower())
    s = s.replace("sr.", "senior").replace("jr.", "junior")
    s = re.sub(r"[^a-z0-9+#/ ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


@dataclass
class Match:
    application: dict[str, Any] | None
    needs_review: bool = False


def find_match(apps: list[dict[str, Any]], company: str, role: str) -> Match:
    """apps: this user's applications (any order). Returns the best match, if any."""
    c, r = norm_company(company), norm_role(role)
    same_company = [a for a in apps
                    if a["company_norm"] == c or fuzz.ratio(a["company_norm"], c) >= COMPANY_MATCH]
    if not same_company:
        return Match(None)

    newest_first = sorted(same_company, key=lambda a: a["created_at"], reverse=True)

    if r:
        by_role = [a for a in newest_first
                   if a["role_norm"] and fuzz.token_set_ratio(a["role_norm"], r) >= ROLE_MATCH]
        if len(by_role) == 1:
            return Match(by_role[0])
        if len(by_role) > 1:
            return Match(by_role[0], needs_review=True)
        # A role was named but none of this company's applications match it:
        # it's a different job, unless the only existing row has no role yet.
        blank = [a for a in newest_first if not a["role_norm"]]
        return Match(blank[0]) if blank else Match(None)

    # Email names no role (common in rejections). Prefer still-open applications.
    open_apps = [a for a in newest_first if a["status"] not in ("rejected", "offer")] or newest_first
    if len(open_apps) == 1:
        return Match(open_apps[0])
    return Match(open_apps[0], needs_review=True)

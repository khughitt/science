"""Extract probeable claims from a plan body.

Design §6.2: 0 of 264 plan entities declare a `deliverables:` key, so they are
extracted rather than read. Extraction is auditable because probe.py records
exactly what was tested.

Conservative by construction: a token that cannot be resolved to a location is
not extracted at all, so it becomes an absent deliverable rather than a spurious
`absent` probe. Under-extraction shows up as `indeterminate` (honest); over-
extraction would manufacture mismatches (not).
"""

from __future__ import annotations

import re

_EXTENSIONS = "py|ts|tsx|js|jsx|md|yaml|yml|json|sh|R|toml|cfg|ini|sql|trig"

# Requires at least one "/" -- a bare `foo.py` names no location.
_PATH_RE = re.compile(rf"`([\w.-]+(?:/[\w.-]+)+\.(?:{_EXTENSIONS}))`")
_TASK_RE = re.compile(r"task:(t\d+)")


def _dedupe(items: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            out.append(item)
    return out


def extract_deliverables(body: str) -> list[str]:
    return _dedupe(_PATH_RE.findall(body))


def extract_task_refs(body: str) -> list[str]:
    return _dedupe(_TASK_RE.findall(body))

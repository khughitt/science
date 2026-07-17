"""Remove every authored progress claim from a plan.

Design §6.1. Three channels, not one: `status` is the obvious claim, but a
checked box and a "SHIPPED" banner are the same class of assertion, written by
the same hand. Scoring `status` against a checkbox is claim-vs-claim, not
correspondence.

PROGRESS_PATTERNS is PREDECLARED: it is fixed before the draw. A channel
discovered mid-run invalidates the affected adjudications (they are redrawn
after this list is amended and re-registered) -- it is never quietly extended.
"""

from __future__ import annotations

import re

_CHECKBOX_RE = re.compile(r"^(\s*[-*] )\[[ xX]\]", re.M)

PROGRESS_PATTERNS: tuple[re.Pattern[str], ...] = (
    # "**Status:** SHIPPED -- merged at abc1234." (a whole banner line)
    re.compile(r"^\s*\*\*Status:?\*\*.*$", re.M | re.I),
    # bare verdict words, whole-word so "completeness"/"draft parser" survive
    re.compile(r"\b(SHIPPED|DONE|COMPLETE|COMPLETED|MERGED|LANDED)\b"),
    # "merged to local main at `abc1234`", "landed in main"
    re.compile(r"\b(merged|landed)\s+(to|in|into)\b[^.\n]*", re.I),
    # "Design approved 2026-07-16", "approved by ..."
    re.compile(r"\bapproved\b[^.\n]*", re.I),
    # status emoji
    re.compile(r"[✅✔☑❌✖]"),
)

_REDACTED = "[REDACTED]"


def _strip_frontmatter(text: str) -> str:
    if not text.startswith("---\n"):
        return text
    end = text.find("\n---", 4)
    if end < 0:
        return text
    rest = text[end + 4 :]
    return rest.lstrip("\n")


def blind_plan(text: str) -> str:
    """Return the plan body with all three claim channels removed."""
    body = _strip_frontmatter(text)
    body = _CHECKBOX_RE.sub(r"\1[ ]", body)
    for pattern in PROGRESS_PATTERNS:
        body = pattern.sub(_REDACTED, body)
    return body

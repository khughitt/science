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

# A `status:` field line anywhere in the body -- real plans carry status inside
# sub-entity / task YAML blocks, not only in the stripped top frontmatter. Keep
# the key, redact the value: `- status: done` -> `- status: [REDACTED]`.
_STATUS_FIELD_RE = re.compile(r"^(\s*[-*]?\s*status:).*$", re.M | re.I)

# A status verdict standing alone in a markdown table cell: `| t466 | 0 | done |`.
# Lookahead on the closing pipe so adjacent verdict cells both redact. Bounded by
# pipes, so this never touches verdict WORDS in prose (those stay case-sensitive).
_TABLE_VERDICT_RE = re.compile(
    r"(\|\s*)(done|complete|completed|shipped|merged|landed)(\s*)(?=\|)", re.I
)

PROGRESS_PATTERNS: tuple[re.Pattern[str], ...] = (
    # "**Status:** SHIPPED -- merged at abc1234.", optionally list-prefixed
    # ("- **Status:** implemented"), a whole banner line.
    re.compile(r"^\s*(?:[-*]\s+)?\*\*Status:?\*\*.*$", re.M | re.I),
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
    """Return the plan body with all authored claim channels removed."""
    body = _strip_frontmatter(text)
    body = _CHECKBOX_RE.sub(r"\1[ ]", body)
    body = _STATUS_FIELD_RE.sub(r"\1 " + _REDACTED, body)
    body = _TABLE_VERDICT_RE.sub(r"\1" + _REDACTED + r"\3", body)
    for pattern in PROGRESS_PATTERNS:
        body = pattern.sub(_REDACTED, body)
    return body

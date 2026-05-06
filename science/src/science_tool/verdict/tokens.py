"""Five-token verdict vocabulary and body-verdict extractor."""

from __future__ import annotations

import re
from enum import Enum


class Token(str, Enum):
    """Verdict polarity tokens per spec v1.1.

    Polarity is with respect to the PREDICTED DIRECTION, not project valence.
    """

    POSITIVE = "[+]"
    NEGATIVE = "[-]"
    MIXED = "[~]"
    INCONCLUSIVE = "[?]"
    NON_ADJUDICATING = "[⌀]"

    @classmethod
    def from_str(cls, s: str) -> "Token":
        for t in cls:
            if t.value == s:
                return t
        raise ValueError(f"Unknown verdict token: {s!r}")


_BODY_VERDICT_RE = re.compile(
    r"\*\*Verdict:\*\*[^\S\r\n]*(\[[+\-~?⌀]\])[^\S\r\n]+(\S.*?)(?=\n\n|\n<!--|\Z)",
    re.DOTALL,
)


def parse_body_verdict(markdown: str) -> tuple[Token, str] | None:
    """Return (token, clause) from the first `**Verdict:** [X] ...` line.

    The clause runs up to the first blank line, HTML comment, or end
    of document. Returns None if no verdict line is present.
    """
    match = _BODY_VERDICT_RE.search(markdown)
    if match is None:
        return None
    token = Token.from_str(match.group(1))
    clause = match.group(2).strip()
    return token, clause

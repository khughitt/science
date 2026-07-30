"""One rule for deciding whether an `@` token is citation syntax.

The citation parser (`references.py`) and the prose linter (`prose_lint.py`)
both scan for `@key`-shaped tokens, and both must reach the same verdict on
tokens that merely look like citations: scoped package handles
(`@react-three/postprocessing`), email addresses (`author@example.edu`),
measurements (`VO2@VT`), and metrics (`P'@k`). Divergence here is a
correctness bug — the linter stays quiet while export fails closed, or vice
versa. This module owns the contextual decision so there is exactly one.

Callers keep their own token regex and their own handling of supported
`[@key]` blocks; only the classification lives here.
"""

from __future__ import annotations


def is_bare_citation_candidate(line: str, start: int, end: int) -> bool:
    """Return whether an `@token` span should be treated as citation syntax.

    `start` is the index of the `@`; `end` is one past the last character of
    the matched token, as produced by `re.Match.start()` / `.end()`.

    Raises:
        ValueError: if the span does not lie within `line`.
    """
    if not 0 <= start < end <= len(line):
        raise ValueError(f"invalid @token span ({start}, {end}) for line of length {len(line)}")
    if end < len(line) and line[end] == "/":
        return False  # scoped package handle: @react-three/postprocessing
    if start > 0 and line[start - 1] == "'":
        return False  # metric at a cutoff: P'@k
    if start == 0:
        return True
    return not line[start - 1].isalnum()

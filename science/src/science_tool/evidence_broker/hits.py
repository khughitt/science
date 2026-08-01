"""Pure parsing of the canonical ``git grep -n -z`` payload."""

from __future__ import annotations


def parse_hits(payload: bytes, commit: str) -> tuple[tuple[str, int], ...]:
    prefix = f"{commit}:".encode()
    hits: list[tuple[str, int]] = []
    for record in payload.split(b"\n"):
        if not record:
            continue
        try:
            descriptor, raw_line, _content = record.split(b"\0", 2)
        except ValueError as exc:
            raise ValueError("git grep record does not contain two NUL separators") from exc
        if not descriptor.startswith(prefix):
            raise ValueError("git grep record does not carry the pinned commit prefix")
        raw_path = descriptor.removeprefix(prefix)
        if not raw_path:
            raise ValueError("git grep record carries an empty path")
        try:
            path = raw_path.decode("utf-8")
            line = int(raw_line)
        except (UnicodeDecodeError, ValueError) as exc:
            raise ValueError("git grep record has an invalid UTF-8 path or line number") from exc
        if line < 1:
            raise ValueError("git grep line numbers are one-based")
        hits.append((path, line))
    return tuple(hits)

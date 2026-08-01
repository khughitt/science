"""Pure parsing of the canonical ``git grep -n -z`` payload."""

from __future__ import annotations


def parse_hits(payload: bytes, commit: str) -> tuple[tuple[str, int], ...]:
    prefix = f"{commit}:".encode()
    hits: list[tuple[str, int]] = []
    position = 0
    while position < len(payload):
        if not payload.startswith(prefix, position):
            raise ValueError("git grep record does not carry the pinned commit prefix")
        descriptor_end = payload.find(b"\0", position)
        if descriptor_end < 0:
            raise ValueError("git grep record does not contain two NUL separators")
        line_end = payload.find(b"\0", descriptor_end + 1)
        if line_end < 0:
            raise ValueError("git grep record does not contain two NUL separators")
        record_end = payload.find(b"\n", line_end + 1)
        if record_end < 0:
            raise ValueError("git grep record is not LF-terminated")
        raw_path = payload[position + len(prefix) : descriptor_end]
        if not raw_path:
            raise ValueError("git grep record carries an empty path")
        try:
            path = raw_path.decode("utf-8")
            line = int(payload[descriptor_end + 1 : line_end])
        except (UnicodeDecodeError, ValueError) as exc:
            raise ValueError("git grep record has an invalid UTF-8 path or line number") from exc
        if line < 1:
            raise ValueError("git grep line numbers are one-based")
        hits.append((path, line))
        position = record_end + 1
    return tuple(hits)

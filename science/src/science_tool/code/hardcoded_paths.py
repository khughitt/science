"""Hardcoded absolute-path detection (generalized from MM30's find_hardcoded_paths).

MM30 used a project-specific absolute-prefix list. Science ships a built-in
heuristic (absolute paths under common roots + a Windows drive letter) and lets a
project extend it via `hardcoded_path_patterns` in science.yaml. Matching is
substring-based, so a single line may produce several findings.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass

DEFAULT_HARDCODED_PREFIXES: tuple[str, ...] = (
    "/home/",
    "/Users/",
    "/mnt/",
    "/data/",
    "/opt/",
    "/srv/",
    "/proj/",
)
_WINDOWS_DRIVE_RE = re.compile(r"[A-Za-z]:\\(?![nrtbfav\"'])")
_TRIPLE_QUOTE_RE = re.compile(r'"""|\'\'\'')
# Full-line comment markers (Python/Snakemake `#`, C/JS `//`).
_COMMENT_PREFIXES = ("#", "//")
# When one of these immediately precedes a matched prefix, the match is a
# continuation of a longer token — a relative path (`../data/`), a URL segment
# (`host/data/`), or an identifier — not an absolute-path root.
_CONTINUATION_CHARS = frozenset(".~-/_")


@dataclass(frozen=True)
class HardcodedPathFinding:
    pattern: str
    line_number: int
    line: str


def _is_absolute_boundary(line: str, idx: int) -> bool:
    """True if a prefix match at `idx` starts at a token boundary (a genuine
    absolute path) rather than continuing a relative path / URL / identifier."""
    if idx == 0:
        return True
    prev = line[idx - 1]
    return not (prev.isalnum() or prev in _CONTINUATION_CHARS)


def find_hardcoded_paths(
    text: str, *, extra_prefixes: Iterable[str] = ()
) -> list[HardcodedPathFinding]:
    prefixes = DEFAULT_HARDCODED_PREFIXES + tuple(extra_prefixes)
    findings: list[HardcodedPathFinding] = []
    in_docstring = False
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        # Track triple-quoted docstring/string blocks so path-like prose inside
        # them is not flagged. An odd number of fences on a line toggles state.
        starts_in_docstring = in_docstring
        if len(_TRIPLE_QUOTE_RE.findall(raw_line)) % 2 == 1:
            in_docstring = not in_docstring
        if starts_in_docstring:
            continue
        if raw_line.lstrip().startswith(_COMMENT_PREFIXES):
            continue
        for prefix in prefixes:
            start = 0
            while (idx := raw_line.find(prefix, start)) != -1:
                if _is_absolute_boundary(raw_line, idx):
                    findings.append(
                        HardcodedPathFinding(prefix, line_number, raw_line.strip())
                    )
                    break  # one finding per prefix per line
                start = idx + 1
        if _WINDOWS_DRIVE_RE.search(raw_line):
            findings.append(
                HardcodedPathFinding("<windows-drive>", line_number, raw_line.strip())
            )
    return findings

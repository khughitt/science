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
_WINDOWS_DRIVE_RE = re.compile(r"[A-Za-z]:\\")


@dataclass(frozen=True)
class HardcodedPathFinding:
    pattern: str
    line_number: int
    line: str


def find_hardcoded_paths(
    text: str, *, extra_prefixes: Iterable[str] = ()
) -> list[HardcodedPathFinding]:
    prefixes = DEFAULT_HARDCODED_PREFIXES + tuple(extra_prefixes)
    findings: list[HardcodedPathFinding] = []
    for line_number, raw_line in enumerate(text.splitlines(), start=1):
        for prefix in prefixes:
            if prefix in raw_line:
                findings.append(
                    HardcodedPathFinding(prefix, line_number, raw_line.strip())
                )
        if _WINDOWS_DRIVE_RE.search(raw_line):
            findings.append(
                HardcodedPathFinding("<windows-drive>", line_number, raw_line.strip())
            )
    return findings

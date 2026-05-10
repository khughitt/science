"""Prose-quality lints derived from natural-systems's t466 citation-audit pilot.

Each detector function takes a markdown file Path and returns a list of
LintIssue records. The CLI orchestrator (`prose_lint_cli.py`) batches these
across a project tree and renders results.

See `docs/conventions/prose-lints.md` for the lint catalog and severity rules.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from science_tool.markdown_utils import (
    is_fence_line,
    parse_frontmatter,
    strip_inline_code,
)

CHECKS: tuple[str, ...] = (
    "bare-author-year",
    "short-form-ids",
    "frontmatter-inline-gap",
    "numeric-anchor",
)

DEFAULT_SEVERITY: dict[str, str] = {
    "bare-author-year": "warn",
    "short-form-ids": "warn",
    "frontmatter-inline-gap": "info",
    "numeric-anchor": "info",
}


@dataclass(frozen=True)
class LintIssue:
    file: Path
    line: int
    col: int
    check: str
    severity: str
    message: str


def severity_for(check: str, *, strict: bool) -> str:
    base = DEFAULT_SEVERITY[check]
    return "warn" if strict and base == "info" else base


# Capture: (Authorname) (Year), where Authorname starts with uppercase and is
# 3+ chars (excludes "I 2022", "A 2022"). Year is 1900-2099.
_BARE_AUTHOR_YEAR_RE = re.compile(
    r"\b([A-Z][A-Za-z]{2,}(?:\s(?:and|&)\s[A-Z][A-Za-z]{2,})?)\s(19\d\d|20\d\d)\b"
)
# Anchor: `[@key]` immediately following or preceding the match (within 30 chars)
_NEARBY_BIBTEX_RE = re.compile(r"\[@[A-Za-z][A-Za-z0-9_-]*\]")


def detect_bare_author_year(path: Path, *, strict: bool = False) -> list[LintIssue]:
    """Detect `<Capitalized> <Year>` mentions in body prose without [@key]."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return []
    _, body_start = parse_frontmatter(path)
    lines = text.splitlines()
    issues: list[LintIssue] = []
    in_fence = False
    for lineno_zero, raw_line in enumerate(lines):
        lineno = lineno_zero + 1
        if lineno < body_start:
            continue
        if is_fence_line(raw_line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        line = strip_inline_code(raw_line)
        for match in _BARE_AUTHOR_YEAR_RE.finditer(line):
            mention = f"{match.group(1)} {match.group(2)}"
            window_start = max(0, match.start() - 30)
            window_end = min(len(line), match.end() + 30)
            if _NEARBY_BIBTEX_RE.search(line[window_start:window_end]):
                continue
            issues.append(
                LintIssue(
                    file=path,
                    line=lineno,
                    col=match.start() + 1,
                    check="bare-author-year",
                    severity=severity_for("bare-author-year", strict=strict),
                    message=f"bare author-year mention '{mention}' has no adjacent [@key]",
                )
            )
    return issues

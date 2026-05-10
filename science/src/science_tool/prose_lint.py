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

# Short-form prefix → canonical kind mapping. Lowercase letter prefixes pulled
# from refs._LOCAL_ENTITY_KINDS first letters where a unique mapping exists;
# uppercase variants (Q1, T088) are common ad-hoc shorthand.
_SHORT_FORM_KIND_MAP: dict[str, str] = {
    "q": "question",
    "Q": "question",
    "h": "hypothesis",
    "H": "hypothesis",
    "t": "task",
    "T": "task",
    "d": "discussion",
    "D": "discussion",
    "i": "interpretation",
    "I": "interpretation",
}
_SHORT_FORM_RE = re.compile(r"\b([qQhHtTdDiI])(\d{1,4})\b")
# Canonical form check: `<kind>:<short>` should NOT be flagged.
_CANONICAL_PREFIX_RE = re.compile(r"\b(question|hypothesis|task|discussion|interpretation):")
# Task-list heading shape: `## [t088] Title`. Don't flag the bracketed ID
# inside such a header — it IS the canonical form for that file convention.
_TASK_HEADING_RE = re.compile(r"^\s*##+\s*\[[a-zA-Z]\d+\]")


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


def detect_short_form_ids(path: Path, *, strict: bool = False) -> list[LintIssue]:
    """Detect bare `Q1` / `t088` style refs that should be `question:q01-…` etc."""
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
        if _TASK_HEADING_RE.match(raw_line):
            continue
        line = strip_inline_code(raw_line)
        for match in _SHORT_FORM_RE.finditer(line):
            # Skip if preceded by `<kind>:` — already canonical.
            preceding = line[max(0, match.start() - 20) : match.start()]
            if _CANONICAL_PREFIX_RE.search(preceding):
                continue
            short = match.group(0)
            kind = _SHORT_FORM_KIND_MAP[match.group(1)]
            issues.append(
                LintIssue(
                    file=path,
                    line=lineno,
                    col=match.start() + 1,
                    check="short-form-ids",
                    severity=severity_for("short-form-ids", strict=strict),
                    message=f"short-form ID '{short}' should be canonical '{kind}:…'",
                )
            )
    return issues


def detect_frontmatter_inline_gaps(
    path: Path, *, strict: bool = False
) -> list[LintIssue]:
    """For each `related:` entry in frontmatter, flag if absent from body text.

    Reports all gaps at line 1 (the file is the unit, not the location).
    """
    data, body_start = parse_frontmatter(path)
    related = data.get("related") if isinstance(data, dict) else None
    if not isinstance(related, list) or not related:
        return []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return []
    body = "\n".join(lines[body_start - 1 :])
    issues: list[LintIssue] = []
    for ref in related:
        if not isinstance(ref, str) or not ref.strip():
            continue
        if ref in body:
            continue
        issues.append(
            LintIssue(
                file=path,
                line=1,
                col=1,
                check="frontmatter-inline-gap",
                severity=severity_for("frontmatter-inline-gap", strict=strict),
                message=f"frontmatter related entry '{ref}' never appears in body prose",
            )
        )
    return issues

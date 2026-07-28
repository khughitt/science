"""Port of validate.sh "Checking document structure..." block.

Checks direct markdown files under both new-layout entity roots and legacy
``$DOC_DIR`` paths:
- ``entities/topics/`` and ``$DOC_DIR/background/topics/``
- ``entities/papers/`` and ``$DOC_DIR/background/papers/``
- ``entities/books/``

and warns when required template sections are absent.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

from science_tool.validate.findings import validation_observation
from science_tool.validate.findings import declare_validation_rules
from science_tool.validate.checks import Check, CheckObservation
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Severity

_TOPIC_SECTIONS = (
    "## Summary",
    "## Key Concepts",
    "## Current State of Knowledge",
    "## Relevance to This Project",
    "## Key References",
)
_PAPER_SECTIONS = ("## Key Contribution", "## Methods", "## Key Findings", "## Relevance")
_PAPER_RUBRIC_EXEMPT_KINDS = {"literature-survey", "literature-review", "review", "survey"}
_BOOK_SECTIONS = (
    "## Overview",
    "## Whole-Book Synthesis",
    "## Chapter Map",
    "## Key Themes",
    "## Relevance",
    "## Limitations",
    "## Follow-up",
)
_FENCE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})")


SECTION, RULES = declare_validation_rules(
    section_id="document-structure",
    section_title="document structure",
    section_order=107,
    rule_ids=("document-structure.check",),
    severities=frozenset({"error", "warn", "info"}),
)


def _result(
    severity: Severity,
    path: str | None,
    message: str,
    *,
    key: list[str],
) -> CheckObservation:
    return validation_observation(
        severity=severity,
        path=Path(path) if path is not None else None,
        line=None,
        message=message,
        rule=RULES["document-structure.check"],
        task=None,
        qualifiers={"key": key},
    )


@Check(section=SECTION, order=4, producer_id="validate.document-structure", rules=tuple(RULES.values()))
def check_document_structure(ctx: ValidateContext) -> Iterator[CheckObservation]:
    topics_dir = ctx.project_root / "entities" / "topics"
    if topics_dir.is_dir():
        yield from _check_documents(ctx, topics_dir, _TOPIC_SECTIONS)
    papers_dir = ctx.project_root / "entities" / "papers"
    if papers_dir.is_dir():
        yield from _check_documents(ctx, papers_dir, _PAPER_SECTIONS, exempt_paper_kinds=_PAPER_RUBRIC_EXEMPT_KINDS)
    books_dir = ctx.project_root / "entities" / "books"
    if books_dir.is_dir():
        yield from _check_documents(ctx, books_dir, _BOOK_SECTIONS)


def _check_documents(
    ctx: ValidateContext,
    directory: Path,
    sections: tuple[str, ...],
    *,
    exempt_paper_kinds: set[str] | None = None,
) -> Iterator[CheckObservation]:
    if not directory.is_dir():
        return

    for path in sorted(directory.glob("*.md")):
        if not path.is_file():
            continue
        relative = path.relative_to(ctx.project_root).as_posix()
        yield _result(
            Severity.INFO,
            relative,
            f"Checking {relative}...",
            key=["progress"],
        )

        if exempt_paper_kinds is not None:
            paper_kind = str(ctx.frontmatter(path).get("paper_kind") or "").strip().lower()
            if paper_kind in exempt_paper_kinds:
                continue

        headings = set(_non_fenced_lines(ctx.read_text_cached(path).splitlines()))
        for section in sections:
            if section not in headings:
                yield _result(
                    Severity.WARN,
                    relative,
                    f"{relative} missing section: {section}",
                    key=["required-section", section],
                )


def _non_fenced_lines(lines: list[str]) -> Iterator[str]:
    fence_char: str | None = None
    for line in lines:
        match = _FENCE_RE.match(line)
        if match is not None:
            marker = match.group(1)
            char = marker[0]
            if fence_char is None:
                fence_char = char
                continue
            if char == fence_char:
                fence_char = None
                continue
        if fence_char is not None:
            continue
        yield line

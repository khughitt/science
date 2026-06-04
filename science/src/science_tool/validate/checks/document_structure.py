"""Port of validate.sh "Checking document structure..." block.

Checks direct markdown files under:
- "$DOC_DIR/background/topics/"*.md
- "$DOC_DIR/background/papers/"*.md

and warns when required template sections are absent.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
import re

from science_tool.validate.checks import Check
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Result, Severity

_TOPIC_SECTIONS = (
    "## Summary",
    "## Key Concepts",
    "## Current State of Knowledge",
    "## Relevance to This Project",
    "## Key References",
)
_PAPER_SECTIONS = ("## Key Contribution", "## Methods", "## Key Findings", "## Relevance")
_FENCE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})")


def _result(severity: Severity, path: str | None, message: str) -> Result:
    return Result(severity, Path(path) if path is not None else None, None, message, "document_structure", None)


@Check(section="document structure...", order=4)
def check_document_structure(ctx: ValidateContext) -> Iterator[Result]:
    for topics_dir in (ctx.project_root / "entities" / "topics", ctx.doc_dir / "background" / "topics"):
        if topics_dir.is_dir():
            yield from _check_documents(ctx, topics_dir, _TOPIC_SECTIONS)
    for papers_dir in (ctx.project_root / "entities" / "papers", ctx.doc_dir / "background" / "papers"):
        if papers_dir.is_dir():
            yield from _check_documents(ctx, papers_dir, _PAPER_SECTIONS)


def _check_documents(ctx: ValidateContext, directory: Path, sections: tuple[str, ...]) -> Iterator[Result]:
    if not directory.is_dir():
        return

    for path in sorted(directory.glob("*.md")):
        if not path.is_file():
            continue
        relative = path.relative_to(ctx.project_root).as_posix()
        yield _result(Severity.INFO, relative, f"Checking {relative}...")

        headings = set(_non_fenced_lines(ctx.read_text_cached(path).splitlines()))
        for section in sections:
            if section not in headings:
                yield _result(Severity.WARN, relative, f"{relative} missing section: {section}")


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

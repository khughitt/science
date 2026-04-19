"""Post-hoc validator for generated big-picture synthesis files."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from science_tool.big_picture.frontmatter import read_frontmatter
from science_tool.big_picture.resolver import resolve_questions

IssueKind = Literal[
    "nonexistent_reference",
    "thin_coverage_marker_mismatch",
    "orphan_count_mismatch",
]

# Matches "interpretation:<id>", "task:<id>", "question:<id>", "hypothesis:<id>".
REFERENCE_PATTERN = re.compile(r"\b(interpretation|task|question|hypothesis):([a-zA-Z0-9_\-.]+)\b")


@dataclass(frozen=True)
class ValidationIssue:
    kind: IssueKind
    message: str
    path: Path


def validate_synthesis_file(path: Path, project_root: Path) -> list[ValidationIssue]:
    """Return structural issues with a generated synthesis file."""
    issues: list[ValidationIssue] = []
    text = path.read_text(encoding="utf-8")

    known_ids = _collect_project_ids(project_root)
    for match in REFERENCE_PATTERN.finditer(text):
        kind, ident = match.group(1), match.group(2)
        full_id = f"{kind}:{ident}"
        if full_id not in known_ids:
            issues.append(
                ValidationIssue(
                    kind="nonexistent_reference",
                    message=f"Reference {full_id} does not exist in project.",
                    path=path,
                )
            )

    fm = read_frontmatter(path) or {}
    if fm.get("provenance_coverage") == "thin":
        arc = _extract_section(text, "Arc")
        word_count = len(arc.split())
        if word_count > 150:
            issues.append(
                ValidationIssue(
                    kind="thin_coverage_marker_mismatch",
                    message=(
                        f"provenance_coverage is 'thin' but Arc has {word_count} words "
                        "(expected ≤150 when thin)."
                    ),
                    path=path,
                )
            )

    return issues


def _collect_project_ids(project_root: Path) -> set[str]:
    ids: set[str] = set()
    for relative in (
        "specs/hypotheses",
        "doc/questions",
        "doc/interpretations",
        "tasks",
    ):
        directory = project_root / relative
        if not directory.is_dir():
            continue
        for path in directory.rglob("*.md"):
            fm = read_frontmatter(path)
            if fm and "id" in fm:
                ids.add(str(fm["id"]))
            if relative == "tasks":
                ids.update(_extract_aggregated_task_ids(path))
    return ids


# Matches "## [tNNN]" or "## [t-nnn]" headings used in aggregated task files
# (e.g., tasks/active.md, tasks/done/2026-04.md), where each heading is a task
# rather than each file being a task. Captures the ID (e.g., "t082").
AGGREGATED_TASK_HEADING = re.compile(r"^#{1,6}\s*\[([a-zA-Z][\w\-.]*)\]", re.MULTILINE)


def _extract_aggregated_task_ids(path: Path) -> set[str]:
    """Extract `task:<id>` entries from aggregated task files.

    Many Science projects (e.g., mm30) consolidate tasks into a single
    markdown file with `## [tNNN]` headings per task, rather than one file
    per task. This helper harvests those inlined task IDs.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return set()
    return {f"task:{m.group(1)}" for m in AGGREGATED_TASK_HEADING.finditer(text)}


def validate_rollup_file(path: Path, project_root: Path) -> list[ValidationIssue]:
    """Return structural issues with a generated rollup (synthesis.md)."""
    issues: list[ValidationIssue] = []
    fm = read_frontmatter(path) or {}

    claimed = fm.get("orphan_question_count")
    if claimed is not None:
        resolved = resolve_questions(project_root)
        actual = sum(1 for r in resolved.values() if r.primary_hypothesis is None)
        if int(claimed) != actual:
            issues.append(
                ValidationIssue(
                    kind="orphan_count_mismatch",
                    message=f"Rollup claims {claimed} orphans but resolver expected {actual}.",
                    path=path,
                )
            )

    return issues


def _extract_section(text: str, heading: str) -> str:
    """Extract the body of a markdown section by its heading."""
    lines = text.splitlines()
    out: list[str] = []
    in_section = False
    for line in lines:
        stripped = line.lstrip("#").strip()
        if line.startswith("#"):
            if in_section:
                break
            if stripped == heading:
                in_section = True
                continue
        if in_section:
            out.append(line)
    return "\n".join(out).strip()

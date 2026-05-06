"""Post-hoc validator for generated big-picture synthesis files."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from science_model.aspects import (
    SOFTWARE_ASPECT,
    load_project_aspects,
    matches_aspect_filter,
)
from science_tool.big_picture.frontmatter import read_frontmatter
from science_tool.big_picture.resolver import ResolverOutput, resolve_questions

IssueKind = Literal[
    "nonexistent_reference",
    "thin_coverage_marker_mismatch",
    "orphan_count_mismatch",
]

# Matches references that can still appear in generated synthesis text,
# including legacy `topic:` IDs used by the topic-coverage surfaces.
REFERENCE_PATTERN = re.compile(r"\b(interpretation|task|question|hypothesis|topic):([a-zA-Z0-9_\-.]+)\b")


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
                        f"provenance_coverage is 'thin' but Arc has {word_count} words (expected ≤150 when thin)."
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
        # Legacy topic coverage still needs to validate topic IDs that appear
        # in generated synthesis output.
        "doc/topics",
        "doc/background/topics",
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


def count_research_orphans(
    resolved: dict[str, ResolverOutput],
    project_root: Path,
) -> int:
    """Return the number of research orphans.

    A question counts as a research orphan iff it has no hypothesis match
    AND at least one of its resolved aspects is not ``software-development``.
    Pure-software questions without hypothesis matches are out of scope
    for research synthesis and therefore do not count.
    """
    project_aspects = load_project_aspects(project_root)
    research_filter = {a for a in project_aspects if a != SOFTWARE_ASPECT}
    count = 0
    for output in resolved.values():
        if output.primary_hypothesis is not None:
            continue
        if matches_aspect_filter(output.resolved_aspects, research_filter):
            count += 1
    return count


def validate_rollup_file(path: Path, project_root: Path) -> list[ValidationIssue]:
    """Return structural issues with a generated rollup (synthesis.md)."""
    issues: list[ValidationIssue] = []
    fm = read_frontmatter(path) or {}

    claimed = fm.get("orphan_question_count")
    if claimed is not None:
        resolved = resolve_questions(project_root)
        actual = count_research_orphans(resolved, project_root)
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

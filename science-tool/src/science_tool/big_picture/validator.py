"""Post-hoc validator for generated big-picture synthesis files."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from science_tool.big_picture.frontmatter import read_frontmatter

IssueKind = Literal["nonexistent_reference", "thin_coverage_marker_mismatch", "empty_section"]

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
    return ids

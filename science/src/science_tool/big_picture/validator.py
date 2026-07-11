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
from science_tool.entity_scan import iter_entity_markdown
from science_tool.instruments import InstrumentResult

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


def validate_synthesis_file(path: Path, project_root: Path) -> InstrumentResult[ValidationIssue]:
    """Return structural issues with a generated synthesis file.

    ``unwired`` when the project yields no IDs at all. This case is worse than a
    silent empty: with ``known_ids`` empty, the loop below flags EVERY reference in
    the file as ``nonexistent_reference`` -- a full sheet of false positives from a
    check that never had a corpus to check against. A withheld finding is bad; a
    manufactured one is worse.
    """
    issues: list[ValidationIssue] = []
    text = path.read_text(encoding="utf-8")

    known_ids = _collect_project_ids(project_root)
    if not known_ids:
        return InstrumentResult.unwired(
            code="no_project_ids",
            reason=(
                f"No entity or task IDs found under {project_root}. Reference validation "
                "cannot run; every reference would be reported as nonexistent."
            ),
        )

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

    return InstrumentResult.from_rows(issues)


def _collect_project_ids(project_root: Path) -> set[str]:
    ids: set[str] = set()
    # Canonical v3 layout: every authored entity (question, hypothesis,
    # interpretation, topic, …) lives under entities/<kind>/. Scanning the tree
    # covers all kinds whose IDs can appear in generated synthesis output.
    entities_root = project_root / "entities"
    if entities_root.is_dir():
        for path in iter_entity_markdown(entities_root):
            fm = read_frontmatter(path)
            if fm and "id" in fm:
                ids.add(str(fm["id"]))
    # Tasks are aggregated into markdown files with one heading per task.
    tasks_root = project_root / "tasks"
    if tasks_root.is_dir():
        for path in tasks_root.rglob("*.md"):
            fm = read_frontmatter(path)
            if fm and "id" in fm:
                ids.add(str(fm["id"]))
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


def list_research_orphans(
    resolved: dict[str, ResolverOutput],
    project_root: Path,
) -> InstrumentResult[str]:
    """Return the research orphans -- question IDs with no hypothesis match.

    A question is a research orphan iff it has no hypothesis match AND at least one
    of its resolved aspects is not ``software-development``. Pure-software questions
    without hypothesis matches are out of scope for research synthesis.

    There is deliberately NO ``count_research_orphans``: the count is
    ``len(result.rows)``. A separate counter is a second definition of the same
    predicate, and the two drifted in practice -- a rollup reported 40 orphans
    beside a hand-derived list of 31 (fb-2026-07-11-014). The surest way for two
    functions not to disagree is for there to be one function.
    """
    project_aspects = load_project_aspects(project_root)
    research_filter = {a for a in project_aspects if a != SOFTWARE_ASPECT}
    orphans = [
        qid
        for qid, output in resolved.items()
        if output.primary_hypothesis is None
        and matches_aspect_filter(output.resolved_aspects, research_filter)
    ]
    return InstrumentResult.from_rows(sorted(orphans))


def validate_rollup_file(path: Path, project_root: Path) -> InstrumentResult[ValidationIssue]:
    """Return structural issues with a generated rollup (synthesis.md).

    ``unwired`` when the frontmatter cannot be read. This previously returned ``[]``
    there -- via a ``read_frontmatter(path) or {}`` fallback -- and the CLI rendered
    that as a clean bill of health. A rollup that could not be parsed has not passed
    validation; it was never read.
    """
    fm = read_frontmatter(path)
    if fm is None:
        return InstrumentResult.unwired(
            code="frontmatter_unreadable",
            reason=f"{path.name} has no readable frontmatter; nothing could be checked.",
        )

    claimed = fm.get("orphan_question_count")
    if claimed is None:
        # The check RAN; the rollup simply claims no count, so there is nothing to
        # contradict. That is `empty`, not `unwired`.
        return InstrumentResult.from_rows(
            [],
            code="no_orphan_claim",
            reason=f"{path.name} claims no orphan_question_count; nothing to reconcile.",
        )

    resolved = resolve_questions(project_root)
    orphans = list_research_orphans(resolved, project_root)
    if orphans.status == "unwired":
        # Propagate. We cannot contradict a claim we were unable to compute --
        # treating an unwired orphan list as `actual = 0` would fabricate a mismatch.
        return InstrumentResult.unwired(code=orphans.code or "orphans_unwired", reason=orphans.reason)

    actual = len(orphans.rows)
    issues: list[ValidationIssue] = []
    if int(claimed) != actual:
        issues.append(
            ValidationIssue(
                kind="orphan_count_mismatch",
                message=f"Rollup claims {claimed} orphans but resolver expected {actual}.",
                path=path,
            )
        )

    return InstrumentResult.from_rows(issues)


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

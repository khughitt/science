"""Lingering-tags health check: legacy `tags:` fields in document and task metadata."""

from __future__ import annotations

import re
from pathlib import Path
from typing import TypedDict, cast

from pydantic import BaseModel, ConfigDict
from science_model.audit import FindingRule, FindingSection, PathSubject

from science_tool.findings.producers import FindingProducer
from science_tool.graph.health_checks.base import HealthCheck, HealthContext, composed_result
from science_tool.instruments import InstrumentResult


class LingeringTagsRecord(TypedDict):
    file: str
    values: list[str]


class LingeringTagsQualifiers(BaseModel):
    model_config = ConfigDict(extra="forbid")

    values: list[str]


SECTION = FindingSection(id="lingering-tags", title="Lingering tags", section_order=211)
RULE = FindingRule(
    id="tags.lingering",
    severities=frozenset({"warn"}),
    subject_types=frozenset({"path"}),
    qualifier_schema=LingeringTagsQualifiers,
    title="Lingering tags",
    section=SECTION.id,
    display_order=1,
)
PRODUCER = FindingProducer(
    producer_id="lingering_tags",
    namespace="health_checks",
    source_module="graph/health_checks/lingering_tags.py",
    rules=(RULE,),
    sections=(SECTION,),
)


_FRONTMATTER_TAGS_RE = re.compile(r"^tags:\s*\[(?P<body>[^\]]*)\]\s*$", re.MULTILINE)
_TASK_TAGS_RE = re.compile(r"^- tags:\s*\[(?P<body>[^\]]*)\]\s*$", re.MULTILINE)
_FRONTMATTER_BLOCK_RE = re.compile(r"\A---\s*\n(?P<body>.*?)\n---\s*\n", re.DOTALL)


def _extract_frontmatter_block(text: str) -> str:
    """Return the YAML frontmatter body, or empty string if none.

    Only the leading `---` … `---` block at the very top of the file is
    considered frontmatter. `tags:` lines elsewhere (e.g. inside markdown
    code fences that document an example frontmatter) are body content
    and must not be flagged as lingering tags.
    """
    match = _FRONTMATTER_BLOCK_RE.match(text)
    return match.group("body") if match else ""


def _parse_list_body(body: str) -> list[str]:
    items = [item.strip() for item in body.split(",") if item.strip()]
    cleaned: list[str] = []
    for item in items:
        if len(item) >= 2 and item[0] == item[-1] and item[0] in ('"', "'"):
            cleaned.append(item[1:-1])
        else:
            cleaned.append(item)
    return cleaned


_LINGERING_TAGS_SCAN_DIRS = ("doc", "entities", "tasks")


def collect_lingering_tags(project_root: Path) -> InstrumentResult[LingeringTagsRecord]:
    """Find any files still containing `tags:` lines (frontmatter or task).

    Each scan directory is skipped when absent. ``unwired`` when NONE of them exists:
    the scan then visits no file, and "no lingering tags" is a statement about an
    empty search, not about the project.
    """
    project_root = project_root.resolve()
    if not any((project_root / scan_dir).is_dir() for scan_dir in _LINGERING_TAGS_SCAN_DIRS):
        return InstrumentResult.unwired(
            code="scan_dirs_missing",
            reason=f"none of {', '.join(f'{name}/' for name in _LINGERING_TAGS_SCAN_DIRS)} exists; nothing was scanned",
        )
    results: list[LingeringTagsRecord] = []

    for scan_dir in ["doc", "entities"]:
        base = project_root / scan_dir
        if not base.is_dir():
            continue
        for md_file in sorted(base.rglob("*.md")):
            text = md_file.read_text(encoding="utf-8")
            frontmatter_body = _extract_frontmatter_block(text)
            if not frontmatter_body:
                continue
            for match in _FRONTMATTER_TAGS_RE.finditer(frontmatter_body):
                results.append(
                    {
                        "file": str(md_file.relative_to(project_root)),
                        "values": _parse_list_body(match.group("body")),
                    }
                )

    from science_tool.tasks import _task_search_paths

    candidate_task_files = _task_search_paths(project_root / "tasks")

    for task_file in candidate_task_files:
        text = task_file.read_text(encoding="utf-8")
        frontmatter_body = _extract_frontmatter_block(text)
        for match in _FRONTMATTER_TAGS_RE.finditer(frontmatter_body):
            results.append(
                {
                    "file": str(task_file.relative_to(project_root)),
                    "values": _parse_list_body(match.group("body")),
                }
            )
        if task_file.parent.name == "done":
            for match in _TASK_TAGS_RE.finditer(text):
                results.append(
                    {
                        "file": str(task_file.relative_to(project_root)),
                        "values": _parse_list_body(match.group("body")),
                    }
                )

    return InstrumentResult.from_rows(results)


def run_check(context: HealthContext):
    observed = collect_lingering_tags(context.project_root)
    findings = [
        RULE.build(
            subject=PathSubject(path=row["file"]),
            severity="warn",
            qualifiers={"values": row["values"]},
            message=f"Legacy tags field remains: {', '.join(row['values'])}.",
        )
        for row in observed.rows
    ]
    return composed_result(cast("InstrumentResult[object]", observed), findings)


CHECK = HealthCheck(
    name="lingering_tags",
    description="Find legacy tags fields in document and task metadata.",
    requires_sources=False,
    run=run_check,
    producer=PRODUCER,
)

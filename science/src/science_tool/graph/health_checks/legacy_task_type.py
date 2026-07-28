"""Legacy-task-type health check: tasks still carrying the legacy `type:` field."""

from __future__ import annotations

from pathlib import Path
from typing import TypedDict, cast

from pydantic import BaseModel, ConfigDict
from science_model.audit import EntitySubject, FindingRule, FindingSection, LocationEvidence

from science_tool.findings.producers import FindingProducer
from science_tool.graph.health_checks.base import HealthCheck, HealthContext, composed_result
from science_tool.instruments import InstrumentResult


class LegacyTaskTypeFinding(TypedDict):
    task_id: str
    legacy_type: str
    source_file: str


class LegacyTaskTypeQualifiers(BaseModel):
    model_config = ConfigDict(extra="forbid")

    legacy_type: str


SECTION = FindingSection(id="legacy-task-type", title="Legacy task type", section_order=213)
RULE = FindingRule(
    id="task.legacy-type",
    severities=frozenset({"warn"}),
    subject_types=frozenset({"entity"}),
    qualifier_schema=LegacyTaskTypeQualifiers,
    title="Legacy task type",
    section=SECTION.id,
    display_order=1,
)
PRODUCER = FindingProducer(
    producer_id="legacy_task_type",
    namespace="health_checks",
    source_module="graph/health_checks/legacy_task_type.py",
    rules=(RULE,),
    sections=(SECTION,),
)


def collect_legacy_task_type(project_root: Path) -> InstrumentResult[LegacyTaskTypeFinding]:
    """Return the tasks still carrying the legacy `type:` field.

    ``unwired`` when there is no ``tasks/`` directory: no task file was read, so
    "no legacy task types" is a claim about a backlog that was never opened.
    """
    from science_tool.tasks import _parse_path_tasks, _task_search_paths

    tasks_dir = project_root / "tasks"
    if not tasks_dir.is_dir():
        return InstrumentResult.unwired(
            code="tasks_dir_missing",
            reason=f"{tasks_dir.name}/ does not exist; no task file was read",
        )

    findings: list[LegacyTaskTypeFinding] = []
    for path in _task_search_paths(tasks_dir):
        for task in _parse_path_tasks(path):
            if task.type:
                findings.append(
                    LegacyTaskTypeFinding(
                        task_id=task.id,
                        legacy_type=task.type,
                        source_file=str(path.relative_to(project_root)),
                    )
                )
    return InstrumentResult.from_rows(findings)


def run_check(context: HealthContext):
    observed = collect_legacy_task_type(context.project_root)
    findings = [
        RULE.build(
            subject=EntitySubject(ref=f"task:{row['task_id']}"),
            severity="warn",
            qualifiers={"legacy_type": row["legacy_type"]},
            message=f"Task still uses legacy type {row['legacy_type']!r}.",
            evidence=[LocationEvidence(path=row["source_file"])],
        )
        for row in observed.rows
    ]
    return composed_result(cast("InstrumentResult[object]", observed), findings)


CHECK = HealthCheck(
    name="legacy_task_type",
    description="Find tasks still carrying the legacy type field.",
    requires_sources=False,
    run=run_check,
    producer=PRODUCER,
)

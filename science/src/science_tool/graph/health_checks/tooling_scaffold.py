"""Tooling-scaffold health check for the project-local Science dependency."""

from __future__ import annotations

import tomllib
from pathlib import Path
from typing import TypedDict, cast

from pydantic import BaseModel, ConfigDict
from science_model.audit import FindingRule, FindingSection, PathSubject, ProjectSubject, TextEvidence

from science_tool.findings.producers import FindingProducer
from science_tool.graph.health_checks.base import HealthCheck, HealthContext, composed_result
from science_tool.instruments import InstrumentResult
from science_tool.tooling_dependency import (
    CANONICAL_SCIENCE_SOURCE,
    ScienceSourceKind,
    inspect_science_dependency,
)


class ToolingScaffoldFinding(TypedDict):
    code: str  # pyproject_missing | pyproject_unreadable | science_tool_dep_missing | science_source_*
    detail: str  # human-readable description
    fix: str  # suggested remediation command


class ToolingScaffoldQualifiers(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str


SECTION = FindingSection(
    id="tooling-scaffold",
    title="Tooling scaffold",
    section_order=205,
)
RULE = FindingRule(
    id="tooling.scaffold",
    severities=frozenset({"error"}),
    subject_types=frozenset({"project", "path"}),
    qualifier_schema=ToolingScaffoldQualifiers,
    identity_qualifiers=("code",),
    title="Tooling scaffold",
    section=SECTION.id,
    display_order=1,
)
PRODUCER = FindingProducer(
    producer_id="tooling_scaffold",
    namespace="health_checks",
    source_module="graph/health_checks/tooling_scaffold.py",
    rules=(RULE,),
    sections=(SECTION,),
)


def collect_tooling_scaffold_findings(project_root: Path) -> InstrumentResult[ToolingScaffoldFinding]:
    """Check the project has the canonical science invocation scaffold.

    A compliant project has:
      - root `pyproject.toml` (so `uv run` resolves a project context)
      - `science` listed under `[dependency-groups].dev`
      - a Git or same-repository path source for `science`

    Without these, the documented project-local `uv run science <cmd>`
    invocation is missing or external path resolution breaks in nested
    worktrees. See `commands/create-project.md` (pyproject.toml section).

    This check has no unwired state. The absence of the manifest is its finding,
    so an empty return is unambiguous: the dependency scaffold is compliant.
    """
    findings: list[ToolingScaffoldFinding] = []

    pyproject_path = project_root / "pyproject.toml"
    if not pyproject_path.exists():
        findings.append(
            {
                "code": "pyproject_missing",
                "detail": "No root pyproject.toml — `uv run science ...` cannot resolve.",
                "fix": "Create pyproject.toml per commands/create-project.md and configure: "
                + CANONICAL_SCIENCE_SOURCE,
            }
        )
    else:
        try:
            dependency = inspect_science_dependency(project_root)
        except (OSError, tomllib.TOMLDecodeError) as exc:
            findings.append(
                {
                    "code": "pyproject_unreadable",
                    "detail": f"pyproject.toml could not be parsed: {exc}",
                    "fix": "Repair pyproject.toml — see commands/create-project.md for canonical shape.",
                }
            )
        else:
            if not dependency.dev_dependency_present:
                findings.append(
                    {
                        "code": "science_tool_dep_missing",
                        "detail": "pyproject.toml does not list `science` under [dependency-groups].dev.",
                        "fix": "Add `science` to the dev group and configure: " + CANONICAL_SCIENCE_SOURCE,
                    }
                )
            elif dependency.source_kind is ScienceSourceKind.MISSING:
                findings.append(
                    {
                        "code": "science_source_missing",
                        "detail": "The `science` dev dependency has no supported [tool.uv.sources] entry.",
                        "fix": "Configure: " + CANONICAL_SCIENCE_SOURCE,
                    }
                )
            elif dependency.source_kind is ScienceSourceKind.EXTERNAL_PATH:
                findings.append(
                    {
                        "code": "science_source_external_path",
                        "detail": "The external path source for `science` is not safe from nested worktrees.",
                        "fix": "Replace it with: " + CANONICAL_SCIENCE_SOURCE,
                    }
                )

    return InstrumentResult.from_rows(findings)


def run_check(context: HealthContext):
    observed = collect_tooling_scaffold_findings(context.project_root)
    findings = [
        RULE.build(
            subject=(ProjectSubject() if row["code"] == "pyproject_missing" else PathSubject(path="pyproject.toml")),
            severity="error",
            qualifiers={"code": row["code"]},
            message=row["detail"],
            evidence=[TextEvidence(label="fix", text=row["fix"])],
        )
        for row in observed.rows
    ]
    return composed_result(cast("InstrumentResult[object]", observed), findings)


CHECK = HealthCheck(
    name="tooling_scaffold",
    description="Check the project-local Science dependency and source.",
    requires_sources=False,
    run=run_check,
    producer=PRODUCER,
)

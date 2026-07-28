"""Unresolved-refs health check: refs that do not resolve to a known entity."""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path
from typing import TypedDict, cast

from pydantic import BaseModel, ConfigDict
from science_model.audit import (
    FindingRule,
    FindingSection,
    IdentifierSubject,
    LocationEvidence,
)

from science_tool.findings.producers import FindingProducer
from science_tool.graph.health_checks.base import (
    NO_ENTITIES_REASON,
    PROJECT_SOURCES_EMPTY,
    HealthCheck,
    HealthContext,
    composed_result,
    context_sources,
)
from science_tool.graph.migrate import audit_project_sources
from science_tool.graph.sources import ProjectSources, load_project_sources
from science_tool.instruments import InstrumentResult


class UnresolvedRef(TypedDict):
    target: str
    mention_count: int
    sources: list[str]
    looks_like: str  # "semantic-triage" | "task" | "hypothesis" | "question" | "unknown"


class UnresolvedRefQualifiers(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mention_count: int
    looks_like: str


SECTION = FindingSection(id="unresolved-refs", title="Unresolved references", section_order=209)
RULE = FindingRule(
    id="refs.unresolved",
    severities=frozenset({"warn"}),
    subject_types=frozenset({"identifier"}),
    identifier_namespaces=frozenset({"reference"}),
    qualifier_schema=UnresolvedRefQualifiers,
    title="Unresolved reference",
    section=SECTION.id,
    display_order=1,
)
PRODUCER = FindingProducer(
    producer_id="unresolved_refs",
    namespace="health_checks",
    source_module="graph/health_checks/unresolved_refs.py",
    rules=(RULE,),
    sections=(SECTION,),
)


# Heuristic patterns for classifying mis-prefixed `topic:` refs.
# All anchored at start; trailing slug (e.g. h01-some-suffix) is allowed since
# real entity IDs commonly have a numeric ID followed by a kebab-case slug.
_TASK_ID_RE = re.compile(r"^topic:t\d+", re.IGNORECASE)
_HYPOTHESIS_ID_RE = re.compile(r"^topic:h\d+", re.IGNORECASE)
_QUESTION_ID_RE = re.compile(r"^topic:q\d+", re.IGNORECASE)


def _classify(target: str) -> str:
    """Heuristic guess at what kind of entity a ref looks like it should be."""
    if _TASK_ID_RE.match(target):
        return "task"
    if _HYPOTHESIS_ID_RE.match(target):
        return "hypothesis"
    if _QUESTION_ID_RE.match(target):
        return "question"
    if target.startswith("topic:"):
        return "semantic-triage"
    return "unknown"


def collect_unresolved_refs(
    project_root: Path, *, sources: ProjectSources | None = None
) -> InstrumentResult[UnresolvedRef]:
    """Walk a project, run the audit, group unresolved refs by target.

    Rows are sorted by mention count (descending), then target (asc).
    Meta: refs are excluded (they're intentional metadata, not unresolved).

    ``unwired`` when the load produced no entities: an audit of nothing yields no
    dangling refs, which says nothing about the project's references.
    """
    if sources is None:
        sources = load_project_sources(project_root.resolve(), strict_identity=False)
    if not sources.entities:
        return InstrumentResult.unwired(code=PROJECT_SOURCES_EMPTY, reason=NO_ENTITIES_REASON)
    verdict = audit_project_sources(sources)
    if verdict.status == "unwired":
        # code is guaranteed non-None on an unwired verdict by ValidationVerdict's invariant.
        return InstrumentResult.unwired(code=cast(str, verdict.code), reason=verdict.reason)
    rows = verdict.rows

    # Group fail rows by target
    by_target: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        if row["status"] != "fail":
            continue
        if row["check"] == "identity_collision":
            # An identity_collision row's `target` is the owner scope (e.g.
            # "proj"), not an unresolved reference. Do not mislabel it.
            continue
        target = row["target"]
        source = row["source"]
        if source not in by_target[target]:
            by_target[target].append(source)

    result: list[UnresolvedRef] = [
        {
            "target": target,
            "mention_count": len(sources_list),
            "sources": sorted(sources_list),
            "looks_like": _classify(target),
        }
        for target, sources_list in by_target.items()
    ]
    result.sort(key=lambda r: (-r["mention_count"], r["target"]))
    return InstrumentResult.from_rows(result)


def run_check(context: HealthContext):
    observed = collect_unresolved_refs(
        context.project_root,
        sources=context_sources(context),
    )
    findings = [
        RULE.build(
            subject=IdentifierSubject(namespace="reference", value=row["target"]),
            severity="warn",
            qualifiers={
                "mention_count": row["mention_count"],
                "looks_like": row["looks_like"],
            },
            message=f"Unresolved reference {row['target']} ({row['mention_count']} mention(s)).",
            evidence=[LocationEvidence(path=path) for path in row["sources"]],
        )
        for row in observed.rows
    ]
    return composed_result(cast("InstrumentResult[object]", observed), findings)


CHECK = HealthCheck(
    name="unresolved_refs",
    description="Find project references that do not resolve to known entities.",
    requires_sources=True,
    run=run_check,
    producer=PRODUCER,
)

"""Aggregator for project health diagnostics.

Provides the data layer for `science health` — groups unresolved refs
by target, surfaces stale tasks, knowledge gaps, and schema issues. Output
is a structured dict suitable for both human display and agent consumption.
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field as dataclass_field
from pathlib import Path
from time import perf_counter
from typing import Callable, NotRequired, TypeVar, TypedDict, cast

import yaml as _yaml

from science_model.contracts.inventory_common import InventoryWarning
from science_model.entities import Entity
from science_tool.big_picture.literature_prefix import canonical_paper_id
from science_tool.entity_identity import collect_identity_warnings
from science_tool.graph.entity_registry import EntityKindNotRegisteredError
from science_tool.graph.migrate import (
    LayeredClaimMigrationReport,
    audit_project_sources,
    build_layered_claim_migration_report,
)
from science_tool.graph.sources import (
    ProjectSources,
    external_prefixes,
    is_bibliography_reference,
    is_external_reference,
    is_metadata_reference,
    load_project_sources,
)


DATASET_ANOMALY_CODES: tuple[str, ...] = (
    "dataset_consumed_but_unverified",
    "dataset_stale_review",
    "dataset_missing_source_url",
    "dataset_cached_field_drift",
    "dataset_invariant_violation",
    "dataset_derived_missing_workflow_run",
    "dataset_derived_asymmetric_edge",
    "dataset_derived_input_chain_broken",
    "dataset_origin_block_mismatch",
    "dataset_verified_but_unstageable",
    "dataset_research_package_asymmetric",
    "data_package_unmigrated",
)

_T = TypeVar("_T")


class UnresolvedRef(TypedDict):
    target: str
    mention_count: int
    sources: list[str]
    looks_like: str  # "semantic-triage" | "task" | "hypothesis" | "question" | "unknown"


class UnregisteredRefKind(TypedDict):
    kind: str
    field: str
    mention_count: int
    refs: list[str]
    sources: list[str]


class _UnregisteredRefKindAccumulator(TypedDict):
    mention_count: int
    refs: set[str]
    sources: set[str]


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


def collect_unresolved_refs(project_root: Path, *, sources: ProjectSources | None = None) -> list[UnresolvedRef]:
    """Walk a project, run the audit, group unresolved refs by target.

    Returns a list sorted by mention count (descending), then target (asc).
    Meta: refs are excluded (they're intentional metadata, not unresolved).
    """
    if sources is None:
        sources = load_project_sources(project_root.resolve())
    rows, _ = audit_project_sources(sources)

    # Group fail rows by target
    by_target: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        if row["status"] != "fail":
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
    return result


def collect_unregistered_ref_kinds(
    project_root: Path, *, sources: ProjectSources | None = None
) -> list[UnregisteredRefKind]:
    """Report identity refs whose CURIE prefix is not a registered entity kind."""
    if sources is None:
        sources = load_project_sources(project_root.resolve())
    external = external_prefixes(sources.ontology_catalogs)
    grouped: dict[tuple[str, str], _UnregisteredRefKindAccumulator] = {}

    for entity in sources.entities:
        source_path = entity.file_path
        for field in _IDENTITY_REFERENCE_FIELDS:
            for raw in _string_refs(getattr(entity, field, None)):
                if (
                    ":" not in raw
                    or is_metadata_reference(raw)
                    or (field in _BIBLIOGRAPHY_REFERENCE_FIELDS and is_bibliography_reference(raw))
                    or is_external_reference(raw)
                    or is_external_reference(raw, known_prefixes=external)
                ):
                    continue
                kind, _ = raw.split(":", 1)
                kind = kind.lower()
                try:
                    sources.registry.kind_class(kind)
                except EntityKindNotRegisteredError:
                    bucket = grouped.setdefault(
                        (kind, field),
                        {"mention_count": 0, "refs": set(), "sources": set()},
                    )
                    bucket["mention_count"] += 1
                    bucket["refs"].add(raw)
                    bucket["sources"].add(source_path)

    rows: list[UnregisteredRefKind] = []
    for (kind, field), bucket in grouped.items():
        rows.append(
            {
                "kind": kind,
                "field": field,
                "mention_count": bucket["mention_count"],
                "refs": sorted(bucket["refs"]),
                "sources": sorted(bucket["sources"]),
            }
        )
    return sorted(rows, key=lambda row: (row["kind"], row["field"]))


def _string_refs(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, (list, tuple, set)):
        return [item for item in value if isinstance(item, str)]
    return []


class LingeringTagsRecord(TypedDict):
    file: str
    values: list[str]


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


def collect_lingering_tags(project_root: Path) -> list[LingeringTagsRecord]:
    """Find any files still containing `tags:` lines (frontmatter or task)."""
    project_root = project_root.resolve()
    results: list[LingeringTagsRecord] = []

    for scan_dir in ["doc", "specs"]:
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

    tasks_dir = project_root / "tasks"
    candidate_task_files: list[Path] = []
    if (tasks_dir / "active.md").is_file():
        candidate_task_files.append(tasks_dir / "active.md")
    done_dir = tasks_dir / "done"
    if done_dir.is_dir():
        candidate_task_files.extend(sorted(done_dir.glob("*.md")))

    for task_file in candidate_task_files:
        text = task_file.read_text(encoding="utf-8")
        for match in _TASK_TAGS_RE.finditer(text):
            results.append(
                {
                    "file": str(task_file.relative_to(project_root)),
                    "values": _parse_list_body(match.group("body")),
                }
            )

    return results


class TaskArchiveLag(TypedDict):
    done_in_active: int
    retired_in_active: int
    missing_completed: int


class ToolingScaffoldFinding(TypedDict):
    code: str  # pyproject_missing | science_tool_dep_missing | env_missing | env_path_missing
    detail: str  # human-readable description
    fix: str  # suggested remediation command


class AgentContextFinding(TypedDict):
    code: str
    source_file: str
    detail: str
    fix: str


class EntityIdentityFinding(TypedDict):
    code: str
    severity: str
    message: str
    path: str | None
    canonical_id: str | None


class ValidationFinding(TypedDict):
    severity: str
    path: str | None
    line: int | None
    message: str
    rule: str | None
    task: str | None


class HealthReport(TypedDict):
    unresolved_refs: list[UnresolvedRef]
    unregistered_ref_kinds: list[UnregisteredRefKind]
    lingering_tags_lines: list[LingeringTagsRecord]
    agent_context: list[AgentContextFinding]
    identity_policy: list["IdentityPolicyFinding"]
    entity_identity: list[EntityIdentityFinding]
    layered_claims: "LayeredClaimHealthReport"
    legacy_task_type: list["LegacyTaskTypeFinding"]
    invalid_entity_aspects: list["InvalidEntityAspectsFinding"]
    legacy_structured_literature_prefixes: list["LegacyStructuredLiteraturePrefixFinding"]
    dataset_anomalies: list[dict]
    archive_lag: TaskArchiveLag
    managed_artifacts: list[dict]
    tooling_scaffold: list[ToolingScaffoldFinding]
    validation: list[ValidationFinding]
    total_issues: int
    _meta: NotRequired["HealthMeta"]


class HealthTiming(TypedDict):
    name: str
    duration_seconds: float


class HealthMeta(TypedDict):
    timings: list[HealthTiming]
    total_duration_seconds: float


@dataclass
class HealthContext:
    project_root: Path
    collect_timings: bool = False
    sources: ProjectSources | None = None
    selected_checks: tuple[HealthCheck, ...] = ()
    timings: list[HealthTiming] = dataclass_field(default_factory=list)

    def run(self, name: str, fn: Callable[[], _T]) -> _T:
        started = perf_counter()
        result = fn()
        if self.collect_timings:
            self.timings.append(
                {
                    "name": name,
                    "duration_seconds": perf_counter() - started,
                }
            )
        return result


@dataclass(frozen=True)
class HealthCheck:
    name: str
    description: str
    requires_sources: bool
    run: Callable[[HealthContext], object]


def _context_sources(context: HealthContext) -> ProjectSources:
    if context.sources is None:
        raise RuntimeError("health check requires loaded project sources")
    return context.sources


def _run_health_checks(context: HealthContext) -> dict[str, object]:
    results: dict[str, object] = {}
    for check in context.selected_checks:
        results[check.name] = context.run(check.name, lambda check=check: check.run(context))
    return results


def _entity_identity_finding(warning: InventoryWarning) -> EntityIdentityFinding:
    return {
        "code": warning.code,
        "severity": warning.severity,
        "message": warning.message,
        "path": warning.path,
        "canonical_id": warning.canonical_id,
    }


def _collect_entity_identity(context: HealthContext) -> list[EntityIdentityFinding]:
    sources = _context_sources(context)
    return [
        _entity_identity_finding(warning)
        for warning in collect_identity_warnings(context.project_root, sources=sources)
    ]


def collect_validation_findings(project_root: Path) -> list[ValidationFinding]:
    from science_tool.validate.context import ValidateContextError
    from science_tool.validate import runner as validate_runner
    from science_tool.validate.result import Severity

    try:
        run_result = validate_runner.run(project_root, strict=False, verbose=False, enable_python_sidecar=False)
    except ValidateContextError as exc:
        return [
            {
                "severity": "error",
                "path": None,
                "line": None,
                "message": str(exc),
                "rule": "validate.context",
                "task": None,
            }
        ]
    return [
        {
            "severity": _validation_health_severity(result.severity),
            "path": str(result.path) if result.path is not None else None,
            "line": result.line,
            "message": result.message,
            "rule": result.rule,
            "task": result.task,
        }
        for result in run_result.results
        if result.severity is not Severity.INFO
    ]


def _validation_health_severity(severity: object) -> str:
    from science_tool.validate.result import Severity

    if severity is Severity.WARN:
        return "warning"
    if severity is Severity.ERROR:
        return "error"
    raise ValueError(f"unsupported validation severity: {severity!r}")


class CoverageMetric(TypedDict):
    numerator: int
    denominator: int
    fraction: float


class RivalModelGap(TypedDict):
    proposition: str
    source_path: str
    packet_id: str


class LayeredClaimIssue(TypedDict):
    proposition: str
    source_path: str
    warnings: list[str]
    todos: list[str]


class LayeredClaimHealthReport(TypedDict):
    proposition_claim_layer_coverage: CoverageMetric
    causal_leaning_identification_coverage: CoverageMetric
    rival_model_packets_missing_discriminating_predictions: list[RivalModelGap]
    migration_issues: list[LayeredClaimIssue]


def _health_check_names() -> frozenset[str]:
    return frozenset(check.name for check in HEALTH_CHECKS)


def list_health_checks() -> list[dict[str, object]]:
    return [
        {
            "name": check.name,
            "description": check.description,
            "requires_sources": check.requires_sources,
        }
        for check in HEALTH_CHECKS
    ]


def _select_health_checks(
    *,
    checks: set[str] | frozenset[str] | None,
    skip_checks: set[str] | frozenset[str] | None,
    fast: bool,
) -> tuple[HealthCheck, ...]:
    known_names = _health_check_names()
    if fast and checks:
        raise ValueError("cannot combine --fast and --check")
    if fast:
        requested = frozenset(check.name for check in HEALTH_CHECKS if not check.requires_sources)
    else:
        requested = frozenset(checks or known_names)
    skipped = frozenset(skip_checks or ())
    unknown = (requested | skipped) - known_names
    if unknown:
        names = ", ".join(sorted(unknown))
        known = ", ".join(sorted(known_names))
        raise ValueError(f"unknown health check(s): {names}; known checks: {known}")
    selected_names = requested - skipped
    return tuple(check for check in HEALTH_CHECKS if check.name in selected_names)


def _empty_layered_claim_migration_report(project_root: Path) -> LayeredClaimMigrationReport:
    return {
        "project_root": str(project_root),
        "rows": [],
        "summary": {
            "proposition_count": 0,
            "authored_claim_layer_count": 0,
            "authored_identification_strength_count": 0,
            "warning_count": 0,
            "todo_count": 0,
        },
    }


def _empty_check_results(project_root: Path) -> dict[str, object]:
    return {
        "identity_policy": [],
        "entity_identity": [],
        "layered_claim_migration": _empty_layered_claim_migration_report(project_root),
        "archive_lag": {"done_in_active": 0, "retired_in_active": 0, "missing_completed": 0},
        "managed_artifacts": [],
        "tooling_scaffold": [],
        "validate": [],
        "unresolved_refs": [],
        "unregistered_ref_kinds": [],
        "lingering_tags": [],
        "agent_context": [],
        "legacy_structured_literature_prefixes": [],
        "dataset_anomalies": [],
        "legacy_task_type": [],
        "invalid_entity_aspects": [],
    }


def build_health_report(
    project_root: Path,
    *,
    collect_timings: bool = False,
    checks: set[str] | frozenset[str] | None = None,
    skip_checks: set[str] | frozenset[str] | None = None,
    fast: bool = False,
) -> HealthReport:
    """Aggregate all health checks for a project."""
    project_root = project_root.resolve()
    selected_checks = _select_health_checks(checks=checks, skip_checks=skip_checks, fast=fast)
    context = HealthContext(
        project_root=project_root,
        collect_timings=collect_timings,
        selected_checks=selected_checks,
    )
    total_started = perf_counter()
    needs_sources = any(check.requires_sources for check in selected_checks)
    if needs_sources:
        context.sources = context.run("load_project_sources", lambda: load_project_sources(project_root))
    check_results = _empty_check_results(project_root)
    check_results.update(_run_health_checks(context))
    identity_policy_findings = cast("list[IdentityPolicyFinding]", check_results["identity_policy"])
    entity_identity = cast("list[EntityIdentityFinding]", check_results.get("entity_identity", []))
    layered_claims_enabled = "layered_claim_migration" in {check.name for check in selected_checks}
    proposition_entities = (
        [entity for entity in _context_sources(context).entities if entity.kind == "proposition"]
        if layered_claims_enabled
        else []
    )
    migration_report = cast(LayeredClaimMigrationReport, check_results["layered_claim_migration"])
    causal_leaning_rows = [
        row
        for row in migration_report["rows"]
        if row["authored_claim_layer"] in {"causal_effect", "mechanistic_narrative"}
        or row["authored_identification_strength"] is not None
        or row["inferred_identification_strength"] is not None
        or any("mechanistic" in warning.lower() for warning in row["warnings"])
    ]
    rival_model_gaps: list[RivalModelGap] = []
    for entity in proposition_entities:
        # `rival_model_packet` lives on ProjectEntity; defensive getattr for bare Entity instances.
        packet = getattr(entity, "rival_model_packet", None)
        if packet is None or packet.discriminating_predictions:
            continue
        rival_model_gaps.append(
            {
                "proposition": entity.canonical_id,
                "source_path": entity.file_path,
                "packet_id": packet.packet_id,
            }
        )

    migration_issues: list[LayeredClaimIssue] = [
        {
            "proposition": row["proposition"],
            "source_path": row["source_path"],
            "warnings": row["warnings"],
            "todos": row["todos"],
        }
        for row in migration_report["rows"]
        if row["warnings"] or row["todos"]
    ]

    archive_lag = cast("TaskArchiveLag", check_results["archive_lag"])
    managed_artifacts = cast("list[dict]", check_results["managed_artifacts"])
    tooling_scaffold = cast("list[ToolingScaffoldFinding]", check_results["tooling_scaffold"])
    unresolved_refs = cast("list[UnresolvedRef]", check_results["unresolved_refs"])
    unregistered_ref_kinds = cast("list[UnregisteredRefKind]", check_results["unregistered_ref_kinds"])
    lingering_tags_lines = cast("list[LingeringTagsRecord]", check_results["lingering_tags"])
    agent_context = cast("list[AgentContextFinding]", check_results["agent_context"])
    legacy_structured_literature_prefixes = cast(
        "list[LegacyStructuredLiteraturePrefixFinding]",
        check_results["legacy_structured_literature_prefixes"],
    )
    dataset_anomalies = cast("list[dict]", check_results["dataset_anomalies"])
    legacy_task_type = cast("list[LegacyTaskTypeFinding]", check_results["legacy_task_type"])
    invalid_entity_aspects = cast("list[InvalidEntityAspectsFinding]", check_results["invalid_entity_aspects"])
    validation = cast("list[ValidationFinding]", check_results["validate"])

    layered_claim_issue_count = len(migration_issues) + len(rival_model_gaps)
    coverage_gaps = 0
    proposition_coverage = _coverage_metric(
        numerator=sum(1 for entity in proposition_entities if entity.claim_layer is not None),
        denominator=len(proposition_entities),
    )
    causal_coverage = _coverage_metric(
        numerator=sum(1 for row in causal_leaning_rows if row["authored_identification_strength"] is not None),
        denominator=len(causal_leaning_rows),
    )
    for metric in (proposition_coverage, causal_coverage):
        if metric["denominator"] > 0 and metric["numerator"] < metric["denominator"]:
            coverage_gaps += 1

    archive_lag_total = (
        archive_lag["done_in_active"] + archive_lag["retired_in_active"] + archive_lag["missing_completed"]
    )

    total_issues = (
        len(unresolved_refs)
        + len(unregistered_ref_kinds)
        + len(lingering_tags_lines)
        + len(agent_context)
        + len(identity_policy_findings)
        + len(entity_identity)
        + len(legacy_structured_literature_prefixes)
        + layered_claim_issue_count
        + coverage_gaps
        + len(dataset_anomalies)
        + (1 if archive_lag_total else 0)
        + sum(1 for f in managed_artifacts if f["counts_as_issue"])
        + len(tooling_scaffold)
        + len(validation)
    )

    report: HealthReport = {
        "unresolved_refs": unresolved_refs,
        "unregistered_ref_kinds": unregistered_ref_kinds,
        "lingering_tags_lines": lingering_tags_lines,
        "agent_context": agent_context,
        "identity_policy": identity_policy_findings,
        "entity_identity": entity_identity,
        "layered_claims": {
            "proposition_claim_layer_coverage": proposition_coverage,
            "causal_leaning_identification_coverage": causal_coverage,
            "rival_model_packets_missing_discriminating_predictions": rival_model_gaps,
            "migration_issues": migration_issues,
        },
        "legacy_task_type": legacy_task_type,
        "invalid_entity_aspects": invalid_entity_aspects,
        "legacy_structured_literature_prefixes": legacy_structured_literature_prefixes,
        "dataset_anomalies": dataset_anomalies,
        "archive_lag": cast("TaskArchiveLag", archive_lag),
        "managed_artifacts": cast("list[dict]", managed_artifacts),
        "tooling_scaffold": tooling_scaffold,
        "validation": validation,
        "total_issues": total_issues,
    }
    if collect_timings:
        report["_meta"] = {
            "timings": context.timings,
            "total_duration_seconds": perf_counter() - total_started,
        }
    return report


OVERVIEW_LINE_BUDGET = 150
OVERVIEW_WORD_BUDGET = 1200


def collect_agent_context_findings(project_root: Path) -> list[AgentContextFinding]:
    """Return drift that makes session-start agent context too large or fragmented."""
    from science_tool.curate.agents_md import collect_agents_md_state

    project_root = project_root.resolve()
    state = collect_agents_md_state(project_root)
    findings: list[AgentContextFinding] = []

    for include in state.claude_md_legacy_at_includes:
        findings.append(
            {
                "code": "claude_md_legacy_includes",
                "source_file": "CLAUDE.md",
                "detail": f"CLAUDE.md includes {include}; keep CLAUDE.md to a single @AGENTS.md pointer.",
                "fix": "Move durable guidance into AGENTS.md and keep core files as pointers.",
            }
        )
    if state.claude_md_present and not _claude_md_is_minimal(project_root / "CLAUDE.md"):
        findings.append(
            {
                "code": "claude_md_not_minimal",
                "source_file": "CLAUDE.md",
                "detail": "CLAUDE.md should contain only @AGENTS.md.",
                "fix": "Move project-specific guidance into AGENTS.md, then replace CLAUDE.md with @AGENTS.md.",
            }
        )

    for include in state.agents_md_legacy_at_includes:
        findings.append(
            {
                "code": "agents_md_legacy_includes",
                "source_file": "AGENTS.md",
                "detail": f"AGENTS.md includes {include}; @core/* directives inline large files into every session.",
                "fix": "Remove the @core/* directive and keep core files in the Pointers section.",
            }
        )

    if state.agents_md_present and not state.markers_present:
        findings.append(
            {
                "code": "agents_md_digest_markers_missing",
                "source_file": "AGENTS.md",
                "detail": "AGENTS.md is missing the managed load-bearing-constraints digest markers.",
                "fix": "Run /science:curate or add the canonical managed marker block from templates/agents-md.md.",
            }
        )

    overview = project_root / "core" / "overview.md"
    if overview.is_file():
        text = overview.read_text(encoding="utf-8")
        line_count = len(text.splitlines())
        word_count = len(text.split())
        if line_count > OVERVIEW_LINE_BUDGET or word_count > OVERVIEW_WORD_BUDGET:
            findings.append(
                {
                    "code": "overview_too_long",
                    "source_file": "core/overview.md",
                    "detail": (
                        f"core/overview.md is {line_count} lines / {word_count} words; "
                        f"budget is {OVERVIEW_LINE_BUDGET} lines / {OVERVIEW_WORD_BUDGET} words."
                    ),
                    "fix": "Keep overview as boot context and move detailed evidence narratives into canonical docs.",
                }
            )

    return findings


def _claude_md_is_minimal(path: Path) -> bool:
    if not path.is_file():
        return False
    lines = [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return lines == ["@AGENTS.md"]


def collect_tooling_scaffold_findings(project_root: Path) -> list[ToolingScaffoldFinding]:
    """Check the project has the canonical science invocation scaffold.

    A compliant project has:
      - root `pyproject.toml` (so `uv run` resolves a project context)
      - `science` listed under `[dependency-groups].dev`
      - `.env` containing `SCIENCE_TOOL_PATH=...`

    Without these, the documented `uv run science <cmd>` shorthand cannot
    work; users fall back to verbose `uv run --project ...` or `uv run --with ...`
    forms. See `commands/create-project.md` (pyproject.toml section).
    """
    findings: list[ToolingScaffoldFinding] = []

    pyproject_path = project_root / "pyproject.toml"
    if not pyproject_path.exists():
        findings.append(
            {
                "code": "pyproject_missing",
                "detail": "No root pyproject.toml — `uv run science ...` cannot resolve.",
                "fix": 'Create pyproject.toml per commands/create-project.md, then `uv add --dev --editable "$SCIENCE_TOOL_PATH"`.',
            }
        )
    else:
        has_dep = False
        try:
            text = pyproject_path.read_text(encoding="utf-8")
            try:
                import tomllib  # py3.11+
            except ModuleNotFoundError:  # pragma: no cover
                import tomli as tomllib  # type: ignore[import-not-found]
            data = tomllib.loads(text)
            dev_group = data.get("dependency-groups", {}).get("dev", [])
            for entry in dev_group:
                # entries can be strings ("science") or tables; we only need name match
                if isinstance(entry, str) and entry.split("[")[0].split(">=")[0].split("==")[0].strip() == "science":
                    has_dep = True
                    break
        except Exception as exc:
            findings.append(
                {
                    "code": "pyproject_unreadable",
                    "detail": f"pyproject.toml could not be parsed: {exc}",
                    "fix": "Repair pyproject.toml — see commands/create-project.md for canonical shape.",
                }
            )
            has_dep = True  # don't double-report; parsing already failed

        if not has_dep:
            findings.append(
                {
                    "code": "science_tool_dep_missing",
                    "detail": "pyproject.toml does not list `science` under [dependency-groups].dev.",
                    "fix": 'Run `uv add --dev --editable "$SCIENCE_TOOL_PATH"` from the project root.',
                }
            )

    env_path = project_root / ".env"
    if not env_path.exists():
        findings.append(
            {
                "code": "env_missing",
                "detail": "No .env file — SCIENCE_TOOL_PATH is unset for validate.sh and other tooling.",
                "fix": "Create .env with `SCIENCE_TOOL_PATH=<absolute-path-to-science>` (see create-project.md).",
            }
        )
    else:
        env_text = env_path.read_text(encoding="utf-8")
        if not any(line.strip().startswith("SCIENCE_TOOL_PATH=") for line in env_text.splitlines()):
            findings.append(
                {
                    "code": "env_path_missing",
                    "detail": ".env exists but does not define SCIENCE_TOOL_PATH.",
                    "fix": "Add `SCIENCE_TOOL_PATH=<absolute-path-to-science>` to .env.",
                }
            )

    return findings


def _coverage_metric(*, numerator: int, denominator: int) -> CoverageMetric:
    fraction = 1.0 if denominator == 0 else numerator / denominator
    return {
        "numerator": numerator,
        "denominator": denominator,
        "fraction": fraction,
    }


class LegacyTaskTypeFinding(TypedDict):
    task_id: str
    legacy_type: str
    source_file: str


def collect_legacy_task_type(project_root: Path) -> list[LegacyTaskTypeFinding]:
    """Return a list of tasks still carrying the legacy `type:` field."""
    from science_tool.tasks import parse_tasks

    findings: list[LegacyTaskTypeFinding] = []
    tasks_dir = project_root / "tasks"
    candidates = [tasks_dir / "active.md"]
    done_dir = tasks_dir / "done"
    if done_dir.is_dir():
        candidates.extend(sorted(done_dir.glob("*.md")))
    for path in candidates:
        if not path.is_file():
            continue
        for task in parse_tasks(path):
            if task.type:
                findings.append(
                    LegacyTaskTypeFinding(
                        task_id=task.id,
                        legacy_type=task.type,
                        source_file=str(path.relative_to(project_root)),
                    )
                )
    return findings


class InvalidEntityAspectsFinding(TypedDict):
    entity_id: str
    source_file: str
    message: str


class LegacyStructuredLiteraturePrefixFinding(TypedDict):
    source_file: str
    legacy_ref: str


class IdentityPolicyFinding(TypedDict):
    check: str
    entity_id: str
    source_file: str
    message: str


_LEGACY_ARTICLE_REF_RE = re.compile(r"\barticle:[A-Za-z0-9_.-]+\b")
_LOCAL_ID_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_IDENTITY_REQUIRED_KINDS = frozenset(
    {
        "gene",
        "protein",
        "disease",
        "drug",
        "chemical",
        "cell_type",
        "phenotype",
        "anatomy",
        "pathway",
        "process",
        "function",
    }
)
_TAXON_REQUIRED_KINDS = frozenset({"gene", "protein"})
_IDENTITY_REFERENCE_FIELDS = (
    "related",
    "commits_to",
    "source_refs",
    "evidence_refs",
    "same_as",
    "blocked_by",
    "consumed_by",
)
_BIBLIOGRAPHY_REFERENCE_FIELDS = frozenset({"source_refs", "evidence_refs"})


def _coerce_external_curie(raw: object) -> str | None:
    curie = getattr(raw, "curie", None)
    if isinstance(curie, str) and curie.strip():
        return curie.strip()
    if isinstance(raw, str):
        text = raw.strip()
        return text or None
    if isinstance(raw, dict):
        curie = raw.get("curie")
        if isinstance(curie, str) and curie.strip():
            return curie.strip()
        source = raw.get("source")
        identifier = raw.get("id")
        if isinstance(source, str) and isinstance(identifier, str) and source.strip() and identifier.strip():
            return f"{source.strip()}:{identifier.strip()}"
    return None


def collect_identity_policy_findings(
    project_root: Path, *, sources: ProjectSources | None = None
) -> list[IdentityPolicyFinding]:
    """Return identity-policy issues surfaced from loaded entities and relations."""
    if sources is None:
        sources = load_project_sources(project_root.resolve())
    findings: list[IdentityPolicyFinding] = []

    primary_claims: dict[str, list[tuple[str, str]]] = defaultdict(list)
    deprecated_to_canonical: dict[str, str] = {}
    for entity in sources.entities:
        canonical_id = entity.canonical_id
        source_file = entity.file_path
        primary = _coerce_external_curie(getattr(entity, "primary_external_id", None))
        if primary is not None:
            primary_claims[primary].append((canonical_id, source_file))
        for deprecated_id in [str(item) for item in getattr(entity, "deprecated_ids", []) if isinstance(item, str)]:
            deprecated_to_canonical[deprecated_id] = canonical_id

    for curie, claims in primary_claims.items():
        if len(claims) < 2:
            continue
        for canonical_id, source_file in sorted(claims, key=lambda row: row[0])[1:]:
            findings.append(
                IdentityPolicyFinding(
                    check="primary_external_id_collision",
                    entity_id=canonical_id,
                    source_file=source_file,
                    message=f"{curie} is already claimed by another entity",
                )
            )

    for entity in sources.entities:
        _collect_entity_identity_findings(
            entity=entity,
            findings=findings,
            deprecated_to_canonical=deprecated_to_canonical,
        )

    for relation in sources.relations:
        relation_stub = f"{relation.subject} {relation.predicate} {relation.object}".strip()
        for role, ref in (("subject", relation.subject), ("object", relation.object)):
            if ":" not in ref:
                findings.append(
                    IdentityPolicyFinding(
                        check="relation_endpoint_disambiguation",
                        entity_id=relation_stub,
                        source_file=relation.source_path,
                        message=f"{role} {ref!r} is missing a kind prefix",
                    )
                )

    findings.sort(key=lambda row: (row["check"], row["entity_id"], row["source_file"]))
    return findings


def _collect_entity_identity_findings(
    *,
    entity: Entity,
    findings: list[IdentityPolicyFinding],
    deprecated_to_canonical: dict[str, str],
) -> None:
    canonical_id = entity.canonical_id
    source_file = entity.file_path
    kind = entity.kind
    primary = _coerce_external_curie(getattr(entity, "primary_external_id", None))
    provisional = bool(getattr(entity, "provisional", False))
    taxon = getattr(entity, "taxon", None)

    if kind in _IDENTITY_REQUIRED_KINDS and primary is None and not provisional:
        findings.append(
            IdentityPolicyFinding(
                check="missing_primary_external_id",
                entity_id=canonical_id,
                source_file=source_file,
                message=f"{kind} entities should carry a primary external id",
            )
        )

    if kind in _TAXON_REQUIRED_KINDS and not taxon and not provisional:
        findings.append(
            IdentityPolicyFinding(
                check="missing_taxon",
                entity_id=canonical_id,
                source_file=source_file,
                message=f"{kind} entities should carry taxon metadata",
            )
        )

    if kind in {"concept", "method", "mechanism"}:
        local_id = canonical_id.split(":", 1)[1] if ":" in canonical_id else canonical_id
        if not _LOCAL_ID_RE.fullmatch(local_id):
            findings.append(
                IdentityPolicyFinding(
                    check="invalid_local_id_syntax",
                    entity_id=canonical_id,
                    source_file=source_file,
                    message="local ids must use lowercase kebab-case",
                )
            )

    for deprecated_id in [str(item) for item in getattr(entity, "deprecated_ids", []) if isinstance(item, str)]:
        deprecated_to_canonical[deprecated_id] = canonical_id

    for field_name in _IDENTITY_REFERENCE_FIELDS:
        refs = getattr(entity, field_name, None)
        if not isinstance(refs, list):
            continue
        for ref in [str(item) for item in refs if isinstance(item, str)]:
            target = deprecated_to_canonical.get(ref)
            if target is None:
                continue
            findings.append(
                IdentityPolicyFinding(
                    check="deprecated_id_inbound_ref",
                    entity_id=canonical_id,
                    source_file=source_file,
                    message=f"{field_name} references deprecated id {ref} from {target}",
                )
            )


def collect_invalid_entity_aspects(project_root: Path) -> list[InvalidEntityAspectsFinding]:
    """Return a list of entity files carrying invalid explicit `aspects:` values."""
    from science_model.aspects import (
        AspectValidationError,
        load_project_aspects,
        validate_entity_aspects,
    )
    from science_model.frontmatter import parse_frontmatter

    try:
        project_aspects = load_project_aspects(project_root)
    except FileNotFoundError:
        return []

    findings: list[InvalidEntityAspectsFinding] = []
    for relative in ("specs/hypotheses", "doc/questions", "doc/interpretations"):
        directory = project_root / relative
        if not directory.is_dir():
            continue
        for path in directory.rglob("*.md"):
            result = parse_frontmatter(path)
            if result is None:
                continue
            fm, _ = result
            if "aspects" not in fm:
                continue
            raw = fm.get("aspects")
            if not isinstance(raw, list):
                findings.append(
                    InvalidEntityAspectsFinding(
                        entity_id=str(fm.get("id", path.stem)),
                        source_file=str(path.relative_to(project_root)),
                        message="aspects must be a list",
                    )
                )
                continue
            try:
                validate_entity_aspects([str(a) for a in raw], project_aspects)
            except AspectValidationError as exc:
                findings.append(
                    InvalidEntityAspectsFinding(
                        entity_id=str(fm.get("id", path.stem)),
                        source_file=str(path.relative_to(project_root)),
                        message=str(exc),
                    )
                )
    return findings


def collect_legacy_structured_literature_prefixes(project_root: Path) -> list[LegacyStructuredLiteraturePrefixFinding]:
    """Return legacy `article:` refs still present in structured KG source YAML."""
    findings: list[LegacyStructuredLiteraturePrefixFinding] = []
    sources_dir = project_root / "knowledge" / "sources"
    if not sources_dir.is_dir():
        return findings

    for path in sorted(sources_dir.rglob("*.yaml")):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        seen: set[str] = set()
        for match in _LEGACY_ARTICLE_REF_RE.finditer(text):
            legacy_ref = match.group(0)
            if canonical_paper_id(legacy_ref) == legacy_ref or legacy_ref in seen:
                continue
            seen.add(legacy_ref)
            findings.append(
                LegacyStructuredLiteraturePrefixFinding(
                    source_file=str(path.relative_to(project_root)),
                    legacy_ref=legacy_ref,
                )
            )
    return findings


def _passes_gate(
    entity_id: str,
    datasets_by_id: dict[str, dict],  # raw-frontmatter dict per id
    *,
    in_progress: frozenset[str],
    memo: dict[str, tuple[bool, str]],
) -> tuple[bool, str]:
    """Recursively check whether `entity_id` transitively passes the gate.

    Cycle detection uses `in_progress` (DFS path stack — IMMUTABLE per recursion frame).
    Memoization uses `memo` (already-computed pass/fail per entity_id).
    Sibling branches sharing an upstream both succeed because the upstream's result is
    memoized after the first descent — no false-positive cycle detection.
    """
    if entity_id in in_progress:
        return False, f"cycle through {entity_id}"
    if entity_id in memo:
        return memo[entity_id]
    fm = datasets_by_id.get(entity_id)
    if fm is None:
        memo[entity_id] = (False, f"missing entity {entity_id}")
        return memo[entity_id]
    origin = fm.get("origin", "external")
    if origin == "external":
        access = fm.get("access") or {}
        if isinstance(access, str):
            access = {"level": access, "verified": False}
        verified = bool(access.get("verified", False))
        exception_mode = (access.get("exception") or {}).get("mode", "")
        if verified or exception_mode:
            memo[entity_id] = (True, "")
        else:
            memo[entity_id] = (False, f"external {entity_id} unverified and no exception")
        return memo[entity_id]
    if origin == "derived":
        derivation = fm.get("derivation") or {}
        next_in_progress = in_progress | {entity_id}
        for inp in list(derivation.get("inputs") or []):
            ok, msg = _passes_gate(str(inp), datasets_by_id, in_progress=next_in_progress, memo=memo)
            if not ok:
                memo[entity_id] = (False, f"{entity_id} -> {msg}")
                return memo[entity_id]
        memo[entity_id] = (True, "")
        return memo[entity_id]
    memo[entity_id] = (False, f"{entity_id} has no origin")
    return memo[entity_id]


def _load_research_packages(project_root: Path) -> dict[str, list[str]]:
    """Map research-package:<slug> -> displays list."""
    from science_model.frontmatter import parse_frontmatter

    rps: dict[str, list[str]] = {}
    rp_root = project_root / "research" / "packages"
    if not rp_root.exists():
        return rps
    for md in rp_root.rglob("research-package.md"):
        result = parse_frontmatter(md)
        if not result:
            continue
        fm, _ = result
        if fm.get("type") == "research-package" and fm.get("id"):
            rps[str(fm["id"])] = list(fm.get("displays") or [])
    return rps


def _load_runtime_pkg(project_root: Path, datapackage_path: str) -> dict | None:
    p = project_root / datapackage_path
    if not p.exists():
        return None
    try:
        return _yaml.safe_load(p.read_text(encoding="utf-8"))
    except _yaml.YAMLError:
        return None


def check_dataset_anomalies(project_root: Path) -> list[dict]:
    """Run dataset-related health checks and return found anomalies.

    Each anomaly dict has: code, severity, entity_id, file_path, message.

    Uses raw frontmatter dicts (not the Pydantic model) so that invariant
    violations — which cause model_validator to raise — can still be flagged.
    """
    from science_model.frontmatter import parse_frontmatter

    issues: list[dict] = []
    workflow_runs = _load_workflow_runs(project_root)

    datasets_dir = project_root / "doc" / "datasets"

    # Build datasets_by_id for transitive gate walk (task 6.5)
    datasets_by_id: dict[str, dict] = {}
    if datasets_dir.exists():
        for md in datasets_dir.rglob("*.md"):
            result = parse_frontmatter(md)
            if not result:
                continue
            fm, _ = result
            if fm.get("type") == "dataset" and fm.get("id"):
                datasets_by_id[str(fm["id"])] = fm
    gate_memo: dict[str, tuple[bool, str]] = {}

    # Load research packages for symmetry check (task 6.7)
    research_packages = _load_research_packages(project_root)

    if datasets_dir.exists():
        for md in datasets_dir.rglob("*.md"):
            result = parse_frontmatter(md)
            if not result:
                continue
            fm, _ = result
            if fm.get("type") != "dataset":
                continue
            entity_id = str(fm.get("id", md.stem))
            origin = fm.get("origin", "external")  # legacy default

            # Invariant #7: external must not carry derivation:
            if origin == "external" and "derivation" in fm:
                issues.append(
                    {
                        "code": "dataset_origin_block_mismatch",
                        "severity": "error",
                        "entity_id": entity_id,
                        "file_path": str(md),
                        "message": "origin: external entity carries a derivation: block (invariant #7)",
                    }
                )

            # Invariant #8: derived must not carry access:, accessions:, or local_path:
            if origin == "derived":
                forbidden = []
                if "access" in fm:
                    forbidden.append("access")
                if fm.get("accessions"):
                    forbidden.append("accessions")
                if fm.get("local_path"):
                    forbidden.append("local_path")
                if forbidden:
                    issues.append(
                        {
                            "code": "dataset_origin_block_mismatch",
                            "severity": "error",
                            "entity_id": entity_id,
                            "file_path": str(md),
                            "message": f"origin: derived entity carries forbidden field(s): {', '.join(forbidden)} (invariant #8)",
                        }
                    )

            # External-access anomalies
            if origin == "external":
                access = fm.get("access") or {}
                if isinstance(access, str):  # legacy flat shorthand
                    access = {"level": access, "verified": False}
                verified = bool(access.get("verified", False))
                exception_mode = (access.get("exception") or {}).get("mode", "")
                consumed_by = list(fm.get("consumed_by") or [])

                # Consumed but unverified (with no exception)
                if consumed_by and not verified and not exception_mode:
                    issues.append(
                        {
                            "code": "dataset_consumed_but_unverified",
                            "severity": "error",
                            "entity_id": entity_id,
                            "file_path": str(md),
                            "message": f"consumed by {consumed_by} but access.verified is false and no exception is set",
                        }
                    )

                # Stale review (verified + last_reviewed > 365 days ago)
                last_reviewed = access.get("last_reviewed", "")
                if verified and last_reviewed:
                    from datetime import date

                    try:
                        reviewed = date.fromisoformat(last_reviewed)
                        if (date.today() - reviewed).days > 365:
                            issues.append(
                                {
                                    "code": "dataset_stale_review",
                                    "severity": "warning",
                                    "entity_id": entity_id,
                                    "file_path": str(md),
                                    "message": f"last_reviewed {last_reviewed} is older than 12 months",
                                }
                            )
                    except ValueError:
                        pass

                # Missing source_url on verified entity
                if verified and not access.get("source_url"):
                    issues.append(
                        {
                            "code": "dataset_missing_source_url",
                            "severity": "warning",
                            "entity_id": entity_id,
                            "file_path": str(md),
                            "message": "access.verified is true but source_url is empty",
                        }
                    )

                # Task 6.6: verified but unstageable
                datapackage = fm.get("datapackage", "")
                local_path = fm.get("local_path", "")
                stageable_path = datapackage or local_path
                # evaluate-next / track are not-yet-staged triage tiers, where a
                # verified dataset means "confirmed reachable", not "staged" — so
                # absence of datapackage/local_path is expected, not an anomaly.
                not_yet_staged = (fm.get("tier") or "").strip() in ("evaluate-next", "track")
                if (verified or exception_mode) and not stageable_path and not not_yet_staged:
                    issues.append(
                        {
                            "code": "dataset_verified_but_unstageable",
                            "severity": "warning",
                            "entity_id": entity_id,
                            "file_path": str(md),
                            "message": "verified entity has neither datapackage: nor local_path:",
                        }
                    )
                elif stageable_path:
                    full = project_root / stageable_path
                    if not full.exists():
                        issues.append(
                            {
                                "code": "dataset_verified_but_unstageable",
                                "severity": "warning",
                                "entity_id": entity_id,
                                "file_path": str(md),
                                "message": f"runtime path {stageable_path} does not exist on disk",
                            }
                        )

            # Derived workflow-run checks (invariant #9)
            if origin == "derived":
                derivation = fm.get("derivation") or {}
                wf_run_id = str(derivation.get("workflow_run", ""))
                if wf_run_id:
                    run_fm = workflow_runs.get(wf_run_id)
                    if run_fm is None:
                        issues.append(
                            {
                                "code": "dataset_derived_missing_workflow_run",
                                "severity": "error",
                                "entity_id": entity_id,
                                "file_path": str(md),
                                "message": f"derivation.workflow_run {wf_run_id} does not resolve to a workflow-run entity",
                            }
                        )
                    else:
                        produces = list(run_fm.get("produces") or [])
                        if entity_id not in produces:
                            issues.append(
                                {
                                    "code": "dataset_derived_asymmetric_edge",
                                    "severity": "error",
                                    "entity_id": entity_id,
                                    "file_path": str(md),
                                    "message": f"workflow-run {wf_run_id} does not list {entity_id} in produces:",
                                }
                            )

                # Task 6.5: transitive input chain (cycle-safe)
                for inp in list(derivation.get("inputs") or []):
                    ok, msg = _passes_gate(str(inp), datasets_by_id, in_progress=frozenset({entity_id}), memo=gate_memo)
                    if not ok:
                        issues.append(
                            {
                                "code": "dataset_derived_input_chain_broken",
                                "severity": "error",
                                "entity_id": entity_id,
                                "file_path": str(md),
                                "message": f"input chain broken: {msg}",
                            }
                        )
                        break  # one error per entity is enough

            # Task 6.7: research-package symmetry (forward: dataset.consumed_by -> rp.displays)
            consumed_by_list = list(fm.get("consumed_by") or [])
            for cons in consumed_by_list:
                if str(cons).startswith("research-package:"):
                    rp_displays = research_packages.get(str(cons))
                    if rp_displays is None:
                        issues.append(
                            {
                                "code": "dataset_research_package_asymmetric",
                                "severity": "error",
                                "entity_id": entity_id,
                                "file_path": str(md),
                                "message": f"consumed_by lists {cons} but it doesn't resolve to a research-package",
                            }
                        )
                    elif entity_id not in rp_displays:
                        issues.append(
                            {
                                "code": "dataset_research_package_asymmetric",
                                "severity": "error",
                                "entity_id": entity_id,
                                "file_path": str(md),
                                "message": f"consumed_by lists {cons} but its displays: doesn't include {entity_id}",
                            }
                        )

            # Task 6.10: cached-field drift (datapackage YAML vs entity frontmatter)
            datapackage_path = fm.get("datapackage", "")
            if datapackage_path:
                rt = _load_runtime_pkg(project_root, datapackage_path)
                if rt is not None:
                    fm_license = fm.get("license", "")
                    rt_license = rt.get("license", "")
                    if fm_license and rt_license and fm_license != rt_license:
                        issues.append(
                            {
                                "code": "dataset_cached_field_drift",
                                "severity": "warning",
                                "entity_id": entity_id,
                                "file_path": str(md),
                                "message": f"license drift: entity={fm_license!r} runtime={rt_license!r}",
                            }
                        )
                    fm_ot = sorted(list(fm.get("ontology_terms") or []))
                    rt_ot = sorted(list(rt.get("ontology_terms") or []))
                    if fm_ot and rt_ot and fm_ot != rt_ot:
                        issues.append(
                            {
                                "code": "dataset_cached_field_drift",
                                "severity": "warning",
                                "entity_id": entity_id,
                                "file_path": str(md),
                                "message": f"ontology_terms drift: entity={fm_ot} runtime={rt_ot}",
                            }
                        )
                    fm_uc = fm.get("update_cadence", "")
                    rt_uc = rt.get("update_cadence", "")
                    if fm_uc and rt_uc and fm_uc != rt_uc:
                        issues.append(
                            {
                                "code": "dataset_cached_field_drift",
                                "severity": "warning",
                                "entity_id": entity_id,
                                "file_path": str(md),
                                "message": f"update_cadence drift: entity={fm_uc!r} runtime={rt_uc!r}",
                            }
                        )

    # Task 6.9: umbrella + lineage invariants (cross-entity, done after per-entity loop)
    # #1: an umbrella entity (has siblings:) must not appear in any other entity's consumed_by
    umbrella_ids = {ds_id for ds_id, fm in datasets_by_id.items() if fm.get("siblings")}
    for ds_id, fm in datasets_by_id.items():
        for cons in list(fm.get("consumed_by") or []):
            if str(cons) in umbrella_ids:
                issues.append(
                    {
                        "code": "dataset_invariant_violation",
                        "severity": "warning",
                        "entity_id": ds_id,
                        "file_path": "",
                        "message": f"umbrella {cons} appears in {ds_id}.consumed_by (invariant #1)",
                    }
                )

    # #5: lineage symmetry: parent_dataset ↔ siblings
    for ds_id, fm in datasets_by_id.items():
        for sib_id in list(fm.get("siblings") or []):
            sib_id_str = str(sib_id)
            child_fm = datasets_by_id.get(sib_id_str)
            if child_fm is not None and str(child_fm.get("parent_dataset", "")) != ds_id:
                issues.append(
                    {
                        "code": "dataset_invariant_violation",
                        "severity": "warning",
                        "entity_id": ds_id,
                        "file_path": "",
                        "message": f"lineage drift: {ds_id} lists sibling {sib_id_str} but {sib_id_str}.parent_dataset != {ds_id}",
                    }
                )

    # Task 6.7: reverse check (rp.displays -> dataset.consumed_by)
    # Re-use already-built datasets_by_id to avoid a third rglob pass.
    ds_consumed_by: dict[str, list[str]] = {
        ds_id: list(fm.get("consumed_by") or []) for ds_id, fm in datasets_by_id.items()
    }
    for rp_id, displays in research_packages.items():
        for ds_id in displays:
            ds_id = str(ds_id)
            cb = ds_consumed_by.get(ds_id)
            if cb is None:
                issues.append(
                    {
                        "code": "dataset_research_package_asymmetric",
                        "severity": "error",
                        "entity_id": rp_id,
                        "file_path": "",
                        "message": f"research-package.displays lists {ds_id} but no such dataset entity",
                    }
                )
            elif rp_id not in cb:
                issues.append(
                    {
                        "code": "dataset_research_package_asymmetric",
                        "severity": "error",
                        "entity_id": rp_id,
                        "file_path": "",
                        "message": f"{rp_id} displays {ds_id} but the dataset's consumed_by doesn't include the research-package",
                    }
                )

    # Task 6.8: data_package_unmigrated
    dp_dir = project_root / "doc" / "data-packages"
    if dp_dir.exists():
        for md in dp_dir.rglob("*.md"):
            result = parse_frontmatter(md)
            if not result:
                continue
            fm, _ = result
            if fm.get("type") != "data-package":
                continue
            if fm.get("status") != "superseded":
                issues.append(
                    {
                        "code": "data_package_unmigrated",
                        "severity": "error",
                        "entity_id": str(fm.get("id", "")),
                        "file_path": str(md),
                        "message": "unmigrated data-package; run `science data-package migrate` to split into derived dataset(s) + research-package",
                    }
                )

    return issues


def _load_workflow_runs(project_root: Path) -> dict[str, dict]:
    """Map workflow-run:<slug> -> raw frontmatter dict."""
    from science_model.frontmatter import parse_frontmatter

    runs: dict[str, dict] = {}
    runs_dir = project_root / "doc" / "workflow-runs"
    if not runs_dir.exists():
        return runs
    for md in runs_dir.rglob("*.md"):
        result = parse_frontmatter(md)
        if not result:
            continue
        fm, _ = result
        if fm.get("type") == "workflow-run" and fm.get("id"):
            runs[str(fm["id"])] = fm
    return runs


def _collect_archive_lag(context: HealthContext) -> TaskArchiveLag:
    from science_tool.tasks_archive import count_archivable

    return cast("TaskArchiveLag", count_archivable(context.project_root / "tasks"))


def _collect_managed_artifacts(context: HealthContext) -> list[dict]:
    from science_tool.project_artifacts.health_integration import health_findings

    return cast("list[dict]", health_findings(context.project_root))


HEALTH_CHECKS: tuple[HealthCheck, ...] = (
    HealthCheck(
        name="identity_policy",
        description="Validate entity identity policy and relation endpoint disambiguation.",
        requires_sources=True,
        run=lambda context: collect_identity_policy_findings(context.project_root, sources=_context_sources(context)),
    ),
    HealthCheck(
        name="entity_identity",
        description="Validate canonical entity identifiers, baseline status, and prose references.",
        requires_sources=True,
        run=_collect_entity_identity,
    ),
    HealthCheck(
        name="layered_claim_migration",
        description="Report layered-claim adoption gaps and migration issues.",
        requires_sources=True,
        run=lambda context: build_layered_claim_migration_report(
            context.project_root, sources=_context_sources(context)
        ),
    ),
    HealthCheck(
        name="archive_lag",
        description="Count completed tasks that should be archived.",
        requires_sources=False,
        run=_collect_archive_lag,
    ),
    HealthCheck(
        name="managed_artifacts",
        description="Check installed managed artifacts against canonical versions.",
        requires_sources=False,
        run=_collect_managed_artifacts,
    ),
    HealthCheck(
        name="tooling_scaffold",
        description="Check pyproject and environment scaffold for science tooling.",
        requires_sources=False,
        run=lambda context: collect_tooling_scaffold_findings(context.project_root),
    ),
    HealthCheck(
        name="validate",
        description="Run canonical project validation and surface warnings/errors.",
        requires_sources=False,
        run=lambda context: collect_validation_findings(context.project_root),
    ),
    HealthCheck(
        name="agent_context",
        description="Check CLAUDE.md, AGENTS.md, and core/overview.md for session-context drift.",
        requires_sources=False,
        run=lambda context: collect_agent_context_findings(context.project_root),
    ),
    HealthCheck(
        name="unresolved_refs",
        description="Find project references that do not resolve to known entities.",
        requires_sources=True,
        run=lambda context: collect_unresolved_refs(context.project_root, sources=_context_sources(context)),
    ),
    HealthCheck(
        name="unregistered_ref_kinds",
        description="Find identity refs whose prefix is not a registered entity kind.",
        requires_sources=True,
        run=lambda context: collect_unregistered_ref_kinds(context.project_root, sources=_context_sources(context)),
    ),
    HealthCheck(
        name="lingering_tags",
        description="Find legacy tags fields in document and task metadata.",
        requires_sources=False,
        run=lambda context: collect_lingering_tags(context.project_root),
    ),
    HealthCheck(
        name="legacy_structured_literature_prefixes",
        description="Find legacy article: refs in structured literature sources.",
        requires_sources=False,
        run=lambda context: collect_legacy_structured_literature_prefixes(context.project_root),
    ),
    HealthCheck(
        name="dataset_anomalies",
        description="Run dataset lineage, access, and package invariant checks.",
        requires_sources=False,
        run=lambda context: check_dataset_anomalies(context.project_root),
    ),
    HealthCheck(
        name="legacy_task_type",
        description="Find tasks still carrying the legacy type field.",
        requires_sources=False,
        run=lambda context: collect_legacy_task_type(context.project_root),
    ),
    HealthCheck(
        name="invalid_entity_aspects",
        description="Validate explicit entity aspects against the project aspect catalog.",
        requires_sources=False,
        run=lambda context: collect_invalid_entity_aspects(context.project_root),
    ),
)

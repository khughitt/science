"""Aggregator for project health diagnostics.

Provides the data layer for `science-tool health` — groups unresolved refs
by target, surfaces stale tasks, knowledge gaps, and schema issues. Output
is a structured dict suitable for both human display and agent consumption.
"""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path
from typing import TypedDict

from science_tool.big_picture.literature_prefix import canonical_paper_id
from science_tool.graph.migrate import audit_project_sources, build_layered_claim_migration_report
from science_tool.graph.sources import load_project_sources


class UnresolvedRef(TypedDict):
    target: str
    mention_count: int
    sources: list[str]
    looks_like: str  # "topic" | "task" | "hypothesis" | "unknown"


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
        return "topic"
    return "unknown"


def collect_unresolved_refs(project_root: Path) -> list[UnresolvedRef]:
    """Walk a project, run the audit, group unresolved refs by target.

    Returns a list sorted by mention count (descending), then target (asc).
    Meta: refs are excluded (they're intentional metadata, not unresolved).
    """
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


class LingeringTagsRecord(TypedDict):
    file: str
    values: list[str]


_FRONTMATTER_TAGS_RE = re.compile(
    r"^tags:\s*\[(?P<body>[^\]]*)\]\s*$", re.MULTILINE
)
_TASK_TAGS_RE = re.compile(
    r"^- tags:\s*\[(?P<body>[^\]]*)\]\s*$", re.MULTILINE
)
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
                results.append({
                    "file": str(md_file.relative_to(project_root)),
                    "values": _parse_list_body(match.group("body")),
                })

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
            results.append({
                "file": str(task_file.relative_to(project_root)),
                "values": _parse_list_body(match.group("body")),
            })

    return results


class HealthReport(TypedDict):
    unresolved_refs: list[UnresolvedRef]
    lingering_tags_lines: list[LingeringTagsRecord]
    layered_claims: "LayeredClaimHealthReport"
    legacy_task_type: list["LegacyTaskTypeFinding"]
    invalid_entity_aspects: list["InvalidEntityAspectsFinding"]
    legacy_structured_literature_prefixes: list["LegacyStructuredLiteraturePrefixFinding"]


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


def build_health_report(project_root: Path) -> HealthReport:
    """Aggregate all health checks for a project."""
    project_root = project_root.resolve()
    sources = load_project_sources(project_root)
    proposition_entities = [entity for entity in sources.entities if entity.kind == "proposition"]
    migration_report = build_layered_claim_migration_report(project_root)
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
        packet = entity.rival_model_packet
        if packet is None or packet.discriminating_predictions:
            continue
        rival_model_gaps.append(
            {
                "proposition": entity.canonical_id,
                "source_path": entity.source_path,
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

    return {
        "unresolved_refs": collect_unresolved_refs(project_root),
        "lingering_tags_lines": collect_lingering_tags(project_root),
        "layered_claims": {
            "proposition_claim_layer_coverage": _coverage_metric(
                numerator=sum(1 for entity in proposition_entities if entity.claim_layer is not None),
                denominator=len(proposition_entities),
            ),
            "causal_leaning_identification_coverage": _coverage_metric(
                numerator=sum(1 for row in causal_leaning_rows if row["authored_identification_strength"] is not None),
                denominator=len(causal_leaning_rows),
            ),
            "rival_model_packets_missing_discriminating_predictions": rival_model_gaps,
            "migration_issues": migration_issues,
        },
        "legacy_task_type": collect_legacy_task_type(project_root),
        "invalid_entity_aspects": collect_invalid_entity_aspects(project_root),
        "legacy_structured_literature_prefixes": collect_legacy_structured_literature_prefixes(project_root),
    }


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


_LEGACY_ARTICLE_REF_RE = re.compile(r"\barticle:[A-Za-z0-9_.-]+\b")


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

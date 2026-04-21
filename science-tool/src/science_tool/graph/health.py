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

import yaml as _yaml

from science_tool.big_picture.literature_prefix import canonical_paper_id
from science_tool.graph.migrate import audit_project_sources, build_layered_claim_migration_report
from science_tool.graph.sources import load_project_sources


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


class HealthReport(TypedDict):
    unresolved_refs: list[UnresolvedRef]
    lingering_tags_lines: list[LingeringTagsRecord]
    layered_claims: "LayeredClaimHealthReport"
    legacy_task_type: list["LegacyTaskTypeFinding"]
    invalid_entity_aspects: list["InvalidEntityAspectsFinding"]
    legacy_structured_literature_prefixes: list["LegacyStructuredLiteraturePrefixFinding"]
    dataset_anomalies: list[dict]


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
    proposition_entities = [entity for entity in sources.entities if entity.type.value == "proposition"]
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
        "dataset_anomalies": check_dataset_anomalies(project_root),
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
                if (verified or exception_mode) and not stageable_path:
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
                        "message": "unmigrated data-package; run `science-tool data-package migrate` to split into derived dataset(s) + research-package",
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

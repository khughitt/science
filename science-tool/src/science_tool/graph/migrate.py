"""Audit helpers for migrating projects onto canonical graph materialization."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import TypedDict

import yaml
from science_model import normalize_alias
from science_model.frontmatter import parse_frontmatter

from science_tool.graph.sources import (
    AliasCollisionError,
    ProjectSources,
    SourceBinding,
    SourceEntity,
    SourceRelation,
    build_alias_map,
    is_external_reference,
    is_metadata_reference,
    load_project_sources,
    local_profile_sources_dir,
)
from science_tool.paths import resolve_paths


class AuditRow(TypedDict):
    """One canonical-reference audit result row."""

    check: str
    status: str
    source: str
    field: str
    target: str
    details: str


class AuditProjectReport(TypedDict):
    """Structured migration-audit report for a project."""

    project_root: str
    local_profile: str
    has_failures: bool
    unresolved_reference_count: int
    rows: list[AuditRow]
    alias_map: dict[str, str]
    manual_aliases: dict[str, str]


class LayeredClaimMigrationRow(TypedDict):
    """One proposition-focused layered-claim migration suggestion row."""

    proposition: str
    source_path: str
    authored_claim_layer: str | None
    authored_identification_strength: str | None
    inferred_claim_layer: str | None
    inferred_identification_strength: str | None
    warnings: list[str]
    todos: list[str]


class LayeredClaimMigrationSummary(TypedDict):
    """Aggregate counts for layered-claim migration guidance."""

    proposition_count: int
    authored_claim_layer_count: int
    authored_identification_strength_count: int
    warning_count: int
    todo_count: int


class LayeredClaimMigrationReport(TypedDict):
    """Structured proposition scan for layered-claim migration."""

    project_root: str
    rows: list[LayeredClaimMigrationRow]
    summary: LayeredClaimMigrationSummary


_INTERVENTIONAL_RE = re.compile(
    r"\b(crispr|knockout|knockdown|perturb(?:ation)?|randomi[sz]ed(?: intervention)?)\b",
    re.IGNORECASE,
)
_LONGITUDINAL_RE = re.compile(
    r"\b(before[- ]after|follow[- ]up|longitudinal|time[- ]course|pre[- ]post)\b",
    re.IGNORECASE,
)
_STRUCTURAL_RE = re.compile(
    r"\b(benchmark|model structure|defines? the model structure|definitional|mathematical relationship|equation|by definition)\b",
    re.IGNORECASE,
)
_OBSERVATIONAL_RE = re.compile(
    r"\b(association|associated|correlation|correlated|linked to|empirical association)\b",
    re.IGNORECASE,
)
_PROXY_RE = re.compile(r"\b(proxy|latent)\b", re.IGNORECASE)
_MECHANISTIC_RE = re.compile(
    r"\b(mechanistic|activates?|inhibits?|suppresses?|cascade|pathway|through)\b",
    re.IGNORECASE,
)


def audit_project_sources(sources: ProjectSources) -> tuple[list[AuditRow], bool]:
    """Validate that structured project sources resolve canonically."""
    try:
        alias_map = build_alias_map(sources.entities, manual_aliases=sources.manual_aliases)
    except AliasCollisionError as exc:
        return (
            [
                {
                    "check": "ambiguous_alias",
                    "status": "fail",
                    "source": exc.first_canonical_id,
                    "field": "aliases",
                    "target": exc.alias,
                    "details": f"conflicts with {exc.second_canonical_id}",
                }
            ],
            True,
        )
    rows: list[AuditRow] = []

    for entity in sources.entities:
        rows.extend(_audit_entity(entity, alias_map))
    for relation in sources.relations:
        rows.extend(_audit_relation(relation, alias_map))
    for binding in sources.bindings:
        rows.extend(_audit_binding(binding, alias_map))

    rows.sort(key=lambda row: (row["source"], row["target"]))
    has_failures = any(row["status"] == "fail" for row in rows)
    return rows, has_failures


def audit_project_graph(project_root: Path) -> AuditProjectReport:
    """Load a project, audit canonical references, and summarize the result."""
    sources = load_project_sources(project_root)
    rows, has_failures = audit_project_sources(sources)
    try:
        alias_map = build_alias_map(sources.entities, manual_aliases=sources.manual_aliases)
    except AliasCollisionError:
        alias_map = sources.manual_aliases.copy()

    unresolved_rows = [row for row in rows if row["check"] == "unresolved_reference"]
    return {
        "project_root": str(project_root.resolve()),
        "local_profile": sources.profiles.local,
        "has_failures": has_failures,
        "unresolved_reference_count": len(unresolved_rows),
        "rows": rows,
        "alias_map": dict(sorted(alias_map.items())),
        "manual_aliases": dict(sorted(sources.manual_aliases.items())),
    }


def build_layered_claim_migration_report(project_root: Path) -> LayeredClaimMigrationReport:
    """Scan proposition sources and emit conservative layered-claim migration guidance."""
    project_root = project_root.resolve()
    sources = load_project_sources(project_root)

    rows: list[LayeredClaimMigrationRow] = []
    for entity in sources.entities:
        if entity.kind != "proposition":
            continue
        rows.append(_build_layered_claim_row(project_root, entity))

    rows.sort(key=lambda row: row["proposition"])
    return {
        "project_root": str(project_root),
        "rows": rows,
        "summary": {
            "proposition_count": len(rows),
            "authored_claim_layer_count": sum(1 for row in rows if row["authored_claim_layer"]),
            "authored_identification_strength_count": sum(1 for row in rows if row["authored_identification_strength"]),
            "warning_count": sum(len(row["warnings"]) for row in rows),
            "todo_count": sum(len(row["todos"]) for row in rows),
        },
    }


_LIST_FIELD_RE = re.compile(
    r"(?P<prefix>(?:^|\n)(?:-\s+)?(?P<field>related|blocked-by|source_refs):\s*\[)(?P<body>[^\]]*)(?P<suffix>\])"
)


def migrate_project_ids(text: str, alias_map: dict[str, str]) -> str:
    """Rewrite bracketed reference lists using a canonical alias map."""

    def replace(match: re.Match[str]) -> str:
        body = match.group("body")
        items = [item.strip() for item in body.split(",") if item.strip()]
        rewritten: list[str] = []
        for item in items:
            quote = ""
            value = item
            if value[0] in {'"', "'"} and value[-1] == value[0]:
                quote = value[0]
                value = value[1:-1]

            canonical = alias_map.get(value)
            if canonical is None:
                canonical = _resolve_kind_safe_alias(value, alias_map)
            rewritten_value = canonical or value
            if quote:
                rewritten.append(f"{quote}{rewritten_value}{quote}")
            else:
                rewritten.append(rewritten_value)

        return f"{match.group('prefix')}{', '.join(rewritten)}{match.group('suffix')}"

    return _LIST_FIELD_RE.sub(replace, text)


def write_local_sources(project_root: Path, report: dict[str, object]) -> None:
    """Write structured migration artifacts for the configured local profile."""
    local_profile = _coerce_local_profile(report.get("local_profile"))
    base = local_profile_sources_dir(project_root, local_profile=local_profile)
    base.mkdir(parents=True, exist_ok=True)
    raw_rows = report.get("rows", [])
    unresolved_rows = (
        [row for row in raw_rows if isinstance(row, dict) and row.get("check") == "unresolved_reference"]
        if isinstance(raw_rows, list)
        else []
    )
    entities = _merge_entities(
        _load_entity_records(base / "entities.yaml"),
        [
            _placeholder_entity(row["target"], local_profile=local_profile)
            for row in unresolved_rows
            if isinstance(row.get("target"), str)
        ],
    )
    relations = _load_relation_records(base / "relations.yaml")
    mappings = _load_alias_records(base / "mappings.yaml")
    mappings.update(_coerce_alias_map(report.get("manual_aliases")))

    (base / "entities.yaml").write_text(
        yaml.safe_dump({"entities": entities}, sort_keys=False),
        encoding="utf-8",
    )
    (base / "relations.yaml").write_text(
        yaml.safe_dump({"relations": relations}, sort_keys=False),
        encoding="utf-8",
    )
    (base / "mappings.yaml").write_text(
        yaml.safe_dump({"aliases": mappings}, sort_keys=True),
        encoding="utf-8",
    )


def rewrite_project_ids_in_sources(project_root: Path, alias_map: dict[str, str]) -> list[str]:
    """Rewrite resolvable alias references across markdown and task source files."""
    rewritten_paths: list[str] = []
    for path in _migration_target_paths(project_root):
        original = path.read_text(encoding="utf-8")
        updated = migrate_project_ids(original, alias_map)
        if updated == original:
            continue
        path.write_text(updated, encoding="utf-8")
        rewritten_paths.append(path.relative_to(project_root).as_posix())
    return rewritten_paths


def write_migration_report(project_root: Path, report: dict[str, object]) -> Path:
    """Persist the migration audit report under the project's knowledge reports directory."""
    report_path = migration_report_path(project_root)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(f"{json.dumps(report, indent=2, sort_keys=True)}\n", encoding="utf-8")
    return report_path


def migration_report_path(project_root: Path) -> Path:
    """Return the canonical path for KG migration audit output."""
    paths = resolve_paths(project_root)
    return paths.knowledge_dir / "reports" / "kg-migration-audit.json"


def _audit_entity(entity: SourceEntity, alias_map: dict[str, str]) -> list[AuditRow]:
    rows: list[AuditRow] = []
    for target in entity.related:
        rows.extend(_audit_reference(entity, "related", target, alias_map))
    for target in entity.blocked_by:
        rows.extend(_audit_reference(entity, "blocked_by", target, alias_map))
    for target in entity.source_refs:
        rows.extend(_audit_reference(entity, "source_refs", target, alias_map))
    return rows


def _build_layered_claim_row(project_root: Path, entity: SourceEntity) -> LayeredClaimMigrationRow:
    text = _read_entity_body(project_root, entity)
    inferred_claim_layer = _infer_claim_layer(text)
    inferred_identification_strength = _infer_identification_strength(text)
    warnings: list[str] = []
    todos: list[str] = []

    authored_claim_layer = str(entity.claim_layer) if entity.claim_layer is not None else None
    authored_identification_strength = (
        str(entity.identification_strength) if entity.identification_strength is not None else None
    )

    if authored_claim_layer is None and inferred_claim_layer is None:
        todos.append("TODO: classify claim_layer manually")
    if authored_identification_strength is None and inferred_identification_strength is None and inferred_claim_layer != "structural_claim":
        todos.append("TODO: classify identification_strength manually")

    if _is_proxy_mediated(entity, text) and entity.measurement_model is None:
        warnings.append("Proxy-mediated proposition lacks measurement metadata.")
        todos.append("TODO: add measurement_model or justify why the proxy is treated as direct.")

    if _is_mechanistic(entity, text) and not _has_lower_layer_support(entity):
        warnings.append("Mechanistic proposition lacks linked lower-layer supporting propositions or observations.")
        todos.append("TODO: link lower-layer empirical support or mark the mechanistic claim as provisional.")

    return {
        "proposition": entity.canonical_id,
        "source_path": entity.source_path,
        "authored_claim_layer": authored_claim_layer,
        "authored_identification_strength": authored_identification_strength,
        "inferred_claim_layer": None if authored_claim_layer is not None else inferred_claim_layer,
        "inferred_identification_strength": (
            None if authored_identification_strength is not None else inferred_identification_strength
        ),
        "warnings": _dedupe_preserve_order(warnings),
        "todos": _dedupe_preserve_order(todos),
    }


def _read_entity_body(project_root: Path, entity: SourceEntity) -> str:
    source_path = project_root / entity.source_path
    frontmatter = parse_frontmatter(source_path) if source_path.is_file() else None
    if frontmatter is not None:
        _, body = frontmatter
        if body.strip():
            return body
    return entity.content_preview


def _infer_claim_layer(text: str) -> str | None:
    if _STRUCTURAL_RE.search(text):
        return "structural_claim"
    return None


def _infer_identification_strength(text: str) -> str | None:
    if _INTERVENTIONAL_RE.search(text):
        return "interventional"
    if _LONGITUDINAL_RE.search(text):
        return "longitudinal"
    if _OBSERVATIONAL_RE.search(text):
        return "observational"
    return None


def _is_proxy_mediated(entity: SourceEntity, text: str) -> bool:
    return str(entity.proxy_directness) in {"indirect", "derived"} or bool(_PROXY_RE.search(text))


def _is_mechanistic(entity: SourceEntity, text: str) -> bool:
    return str(entity.claim_layer) == "mechanistic_narrative" or bool(_MECHANISTIC_RE.search(text))


def _has_lower_layer_support(entity: SourceEntity) -> bool:
    support_prefixes = ("proposition:", "observation:", "finding:")
    return any(target.startswith(support_prefixes) for target in [*entity.related, *entity.source_refs])


def _dedupe_preserve_order(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def _audit_relation(relation: SourceRelation, alias_map: dict[str, str]) -> list[AuditRow]:
    rows: list[AuditRow] = []
    rows.extend(_audit_relation_endpoint(relation, "subject", relation.subject, alias_map))
    rows.extend(_audit_relation_endpoint(relation, "object", relation.object, alias_map))
    return rows


def _audit_binding(binding: SourceBinding, alias_map: dict[str, str]) -> list[AuditRow]:
    rows: list[AuditRow] = []
    rows.extend(_audit_binding_endpoint(binding, "model", binding.model, alias_map))
    rows.extend(_audit_binding_endpoint(binding, "parameter", binding.parameter, alias_map))
    for target in binding.source_refs:
        rows.extend(_audit_binding_endpoint(binding, "source_refs", target, alias_map, allow_external=True))
    return rows


def _audit_binding_endpoint(
    binding: SourceBinding,
    field_name: str,
    raw_target: str,
    alias_map: dict[str, str],
    *,
    allow_external: bool = False,
) -> list[AuditRow]:
    if allow_external and is_external_reference(raw_target):
        return []

    resolved = normalize_alias(raw_target, alias_map)
    if resolved == raw_target and raw_target not in alias_map:
        return [
            {
                "check": "unresolved_reference",
                "status": "fail",
                "source": f"{binding.model} -> {binding.parameter}",
                "field": field_name,
                "target": raw_target,
                "details": f"{binding.source_path} references an unknown canonical entity",
            }
        ]

    return []


def _audit_relation_endpoint(
    relation: SourceRelation,
    field_name: str,
    raw_target: str,
    alias_map: dict[str, str],
) -> list[AuditRow]:
    if field_name == "object" and is_external_reference(raw_target):
        return []
    if field_name == "subject" and is_external_reference(raw_target):
        return [
            {
                "check": "unresolved_reference",
                "status": "fail",
                "source": f"{relation.subject} {relation.predicate} {relation.object}",
                "field": field_name,
                "target": raw_target,
                "details": f"{relation.source_path} uses an external term as a relation subject",
            }
        ]

    resolved = normalize_alias(raw_target, alias_map)
    if resolved == raw_target and raw_target not in alias_map:
        return [
            {
                "check": "unresolved_reference",
                "status": "fail",
                "source": f"{relation.subject} {relation.predicate} {relation.object}",
                "field": field_name,
                "target": raw_target,
                "details": f"{relation.source_path} references an unknown canonical entity",
            }
        ]

    return []


def _audit_reference(
    entity: SourceEntity,
    field_name: str,
    raw_target: str,
    alias_map: dict[str, str],
) -> list[AuditRow]:
    if is_external_reference(raw_target):
        return []
    if is_metadata_reference(raw_target):
        return []

    resolved = normalize_alias(raw_target, alias_map)
    if resolved == raw_target and raw_target not in alias_map:
        return [
            {
                "check": "unresolved_reference",
                "status": "fail",
                "source": entity.canonical_id,
                "field": field_name,
                "target": raw_target,
                "details": f"{entity.source_path} references an unknown canonical entity",
            }
        ]

    return []


def _placeholder_entity(target: str, *, local_profile: str) -> dict[str, str] | None:
    if is_external_reference(target) or ":" not in target:
        return None

    kind, _ = target.split(":", 1)
    return {
        "canonical_id": target,
        "kind": kind,
        "title": _humanize_canonical_id(target),
        "profile": local_profile,
        "source_path": "migration:audit",
    }


def _humanize_canonical_id(canonical_id: str) -> str:
    _, slug = canonical_id.split(":", 1)
    tokens = [token for token in re.split(r"[-_]+", slug) if token]
    words: list[str] = []
    for token in tokens:
        if re.fullmatch(r"[a-z]\d+", token, re.IGNORECASE):
            words.append(token.upper())
        else:
            words.append(token.capitalize())
    return " ".join(words)


def _coerce_alias_map(value: object) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    result: dict[str, str] = {}
    for alias, canonical_id in value.items():
        if isinstance(alias, str) and isinstance(canonical_id, str):
            result[alias] = canonical_id
    return result


def _coerce_local_profile(value: object) -> str:
    if isinstance(value, str) and value.strip():
        return value
    return "local"


def _migration_target_paths(project_root: Path) -> list[Path]:
    paths = resolve_paths(project_root)
    targets: list[Path] = []

    for root in [paths.doc_dir, paths.specs_dir]:
        if not root.is_dir():
            continue
        targets.extend(sorted(root.rglob("*.md")))

    active_path = paths.tasks_dir / "active.md"
    if active_path.is_file():
        targets.append(active_path)

    done_dir = paths.tasks_dir / "done"
    if done_dir.is_dir():
        targets.extend(sorted(done_dir.glob("*.md")))

    return targets


def _resolve_kind_safe_alias(value: str, alias_map: dict[str, str]) -> str | None:
    if ":" not in value:
        return None

    kind, suffix = value.split(":", 1)
    canonical = alias_map.get(suffix)
    if canonical is None or ":" not in canonical:
        return None
    canonical_kind, _ = canonical.split(":", 1)
    if canonical_kind != kind:
        return None
    return canonical


def _merge_entities(
    existing: list[dict[str, str]],
    additions: list[dict[str, str] | None],
) -> list[dict[str, str]]:
    entity_map: dict[str, dict[str, str]] = {}
    for entity in existing:
        canonical_id = entity.get("canonical_id")
        if isinstance(canonical_id, str) and canonical_id:
            entity_map[canonical_id] = entity

    for entity in additions:
        if entity is None:
            continue
        entity_map.setdefault(entity["canonical_id"], entity)

    return [entity_map[key] for key in sorted(entity_map)]


def _load_entity_records(path: Path) -> list[dict[str, str]]:
    data = _load_yaml(path)
    items = data.get("entities") if isinstance(data, dict) else None
    if not isinstance(items, list):
        return []
    return [item for item in items if isinstance(item, dict)]


def _load_relation_records(path: Path) -> list[dict[str, object]]:
    data = _load_yaml(path)
    items = data.get("relations") if isinstance(data, dict) else None
    if not isinstance(items, list):
        return []
    return [item for item in items if isinstance(item, dict)]


def _load_alias_records(path: Path) -> dict[str, str]:
    data = _load_yaml(path)
    aliases = data.get("aliases") if isinstance(data, dict) else None
    return _coerce_alias_map(aliases)


def _load_yaml(path: Path) -> object:
    if not path.is_file():
        return {}
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}

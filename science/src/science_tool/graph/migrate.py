"""Audit helpers for migrating projects onto canonical graph materialization."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import TypedDict

import yaml
from science_model.entities import Entity
from science_model.frontmatter import parse_frontmatter

from science_tool.addressing import is_address
from science_tool.bibliography import is_bibliography_reference
from science_tool.commons.geneset import GenesetCollectionError, parse_geneset_rows
from science_tool.commons.geneset_resources import dataset_geneset_frontmatter, read_member_rows
from science_tool.graph.identity_table import IdentityTable, build_identity_table
from science_tool.graph.reference_resolution import ReferenceResolver
from science_tool.graph.sources import (
    AliasCollisionError,
    ProjectSources,
    SourceBinding,
    SourceRelation,
    external_prefixes,
    is_external_reference,
    is_metadata_reference,
    load_project_sources,
    local_profile_sources_dir,
)
from science_tool.graph.store import PROJECT_ENTITY_PREFIXES
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
_COMMONS_TYPE_TO_DIR = {"dataset": "datasets", "paper": "papers", "topic": "topics", "theme": "themes"}


def _commons_hint_for(target: str) -> str:
    if ":" not in target:
        return ""
    # A `project:kind:slug` address points at a peer project's entity, which
    # cannot be commons-promoted from here. Cross-project links belong in prose.
    if target.count(":") >= 2:
        return (
            f" (no local entity for {target}; cross-project references to peer-project "
            f"entities are not commons-promotable -- link them in prose rather than "
            f"structured frontmatter, or check the ref's spelling)"
        )
    type_part, slug = target.split(":", 1)
    type_dir = _COMMONS_TYPE_TO_DIR.get(type_part)
    if type_dir is None:
        # Only dataset/paper/topic/theme are commons-promotable; for any other
        # kind, suggesting `commons promote` is a dead end.
        return (
            f" (no local entity for {target}; '{type_part}' is not a commons-promotable "
            f"kind -- check the ref's spelling, or link cross-cutting references in prose)"
        )
    if type_part == "dataset":
        canonical_path = f"~/d/science-commons/datasets/{slug}/entity.md"
        promote_command = f"science commons promote dataset --slug {slug} --from <project>"
    else:
        canonical_path = f"~/d/science-commons/{type_dir}/{slug}.md"
        promote_command = f"science commons promote {type_part} --from <project>"
    return (
        f" (no local entity, no commons canonical at {canonical_path} -- "
        f"run `{promote_command}` if {target} "
        f"should be promoted, or check the ref's spelling)"
    )


def audit_identity_table(table: IdentityTable) -> list[AuditRow]:
    """Turn identity-table collisions into graph-audit rows (design §B3, §C2).

    A genuine duplicate (>=2 non-deprecated owners) is `fail` (blocks the strict build
    gate via has_failures); a transitional stub-shadow is `warn` — carried until §B5
    retirement, not a build blocker (§C4). Grade via the shared IdentityCollision
    predicate so this path, the migrator, and the validate check never diverge.
    """
    rows: list[AuditRow] = []
    for collision in table.collisions():
        paths = [(r.source_ref.path if r.source_ref else "<unknown>") for r in collision.rows]
        rows.append(
            {
                "check": "identity_collision",
                "status": "fail" if collision.is_genuine else "warn",
                "source": collision.canonical_id,
                "field": "owner_scope",
                "target": collision.owner_scope,
                "details": "owned by " + " and ".join(paths),
            }
        )
    return rows


def audit_project_sources(sources: ProjectSources) -> tuple[list[AuditRow], bool]:
    """Validate that structured project sources resolve canonically."""
    rows: list[AuditRow] = []
    identity_table = build_identity_table(sources)
    try:
        resolver = ReferenceResolver.from_entities(
            sources.entities, manual_aliases=sources.manual_aliases, identity_table=identity_table
        )
    except AliasCollisionError as exc:
        # Alias collision short-circuits the reference checks (no resolver), but we
        # still fall through to the additive identity-table audit below so an alias
        # collision and an identity collision can both surface in one report.
        rows.append(
            {
                "check": "ambiguous_alias",
                "status": "fail",
                "source": exc.first_canonical_id,
                "field": "aliases",
                "target": exc.alias,
                "details": f"conflicts with {exc.second_canonical_id}",
            }
        )
    else:
        ext_prefixes = external_prefixes(sources.ontology_catalogs)
        peer_ids = sources.peer_ids

        for entity in sources.entities:
            rows.extend(_audit_entity(entity, resolver, ext_prefixes=ext_prefixes, peer_ids=peer_ids))
        rows.extend(_audit_geneset_row_dataset_usage(sources, resolver, ext_prefixes=ext_prefixes))
        for relation in sources.relations:
            rows.extend(_audit_relation(relation, resolver, ext_prefixes=ext_prefixes))
        for binding in sources.bindings:
            rows.extend(_audit_binding(binding, resolver, ext_prefixes=ext_prefixes))

        # Surface entities dropped during load (unknown kind, failed schema validation)
        # as warn rows so they are visible to graph audit / validate instead of only
        # being logged. status=warn keeps them from flipping the build to failed.
        for skipped in sources.skipped_entities:
            rows.append(
                {
                    "check": skipped.reason,
                    "status": "warn",
                    "source": skipped.path,
                    "field": "kind",
                    "target": skipped.kind,
                    "details": skipped.details,
                }
            )

    # Additive identity-table audit (design §C2): consume the compiled model.
    rows.extend(audit_identity_table(identity_table))

    rows.sort(key=lambda row: (row["source"], row["target"]))
    has_failures = any(row["status"] == "fail" for row in rows)
    return rows, has_failures


def _audit_geneset_row_dataset_usage(
    sources: ProjectSources,
    resolver: ReferenceResolver,
    *,
    ext_prefixes: frozenset[str],
) -> list[AuditRow]:
    rows: list[AuditRow] = []
    project_root = Path(sources.project_root)
    for entity in sources.entities:
        if entity.kind != "dataset":
            continue
        fm = dataset_geneset_frontmatter(
            project_root,
            entity.file_path,
            entity_adapter=sources.entity_source_adapters.get(entity.canonical_id),
            datapackage_rel=sources.dataset_datapackages.get(entity.canonical_id),
        )
        if fm is None:
            continue
        raw_rows = read_member_rows(project_root, fm)
        if raw_rows is None or isinstance(raw_rows, Exception):
            continue
        try:
            geneset_rows = parse_geneset_rows(raw_rows)
        except GenesetCollectionError:
            continue
        for geneset_row in geneset_rows:
            for usage in geneset_row.dataset_usage:
                rows.extend(
                    _audit_dataset_reference(
                        entity,
                        "members_resource.dataset_usage",
                        str(usage["ref"]),
                        resolver,
                        ext_prefixes=ext_prefixes,
                        allow_cross_kind_fallback=False,
                        allow_tag=False,
                    )
                )
    return rows


def audit_project_graph(project_root: Path) -> AuditProjectReport:
    """Load a project, audit canonical references, and summarize the result."""
    sources = load_project_sources(project_root)
    rows, has_failures = audit_project_sources(sources)
    try:
        alias_map = ReferenceResolver.from_entities(sources.entities, manual_aliases=sources.manual_aliases).alias_map
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


def build_layered_claim_migration_report(
    project_root: Path, *, sources: ProjectSources | None = None
) -> LayeredClaimMigrationReport:
    """Scan proposition sources and emit conservative layered-claim migration guidance."""
    project_root = project_root.resolve()
    if sources is None:
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


def preview_project_id_rewrites(project_root: Path, alias_map: dict[str, str]) -> list[str]:
    """List source files that would be rewritten by alias migration without mutating them."""
    rewritten_paths: list[str] = []
    for path in _migration_target_paths(project_root):
        original = path.read_text(encoding="utf-8")
        updated = migrate_project_ids(original, alias_map)
        if updated == original:
            continue
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


def _audit_entity(
    entity: Entity,
    resolver: ReferenceResolver,
    *,
    ext_prefixes: frozenset[str],
    peer_ids: frozenset[str] = frozenset(),
) -> list[AuditRow]:
    rows: list[AuditRow] = []
    for target in entity.related:
        rows.extend(
            _audit_reference(
                entity,
                "related",
                target,
                resolver,
                ext_prefixes=ext_prefixes,
                allow_cross_kind_fallback=True,
                allow_tag=True,
                peer_ids=peer_ids,
            )
        )
    for target in getattr(entity, "commits_to", None) or []:
        rows.extend(
            _audit_reference(
                entity,
                "commits_to",
                target,
                resolver,
                ext_prefixes=ext_prefixes,
                allow_cross_kind_fallback=True,
                allow_tag=True,
                peer_ids=peer_ids,
            )
        )
    # `blocked_by` lives on ProjectEntity; defensive getattr for bare Entity instances.
    for target in getattr(entity, "blocked_by", []) or []:
        rows.extend(
            _audit_reference(entity, "blocked_by", target, resolver, ext_prefixes=ext_prefixes, peer_ids=peer_ids)
        )
    for target in entity.source_refs:
        rows.extend(
            _audit_reference(
                entity,
                "source_refs",
                target,
                resolver,
                ext_prefixes=ext_prefixes,
                allow_cross_kind_fallback=True,
                peer_ids=peer_ids,
            )
        )
    for target in getattr(entity, "evidence_refs", []) or []:
        rows.extend(
            _audit_reference(
                entity,
                "evidence_refs",
                target,
                resolver,
                ext_prefixes=ext_prefixes,
                allow_cross_kind_fallback=True,
                allow_cross_project_address=True,
                peer_ids=peer_ids,
            )
        )
    for usage in getattr(entity, "dataset_usage", []) or []:
        rows.extend(
            _audit_dataset_reference(
                entity,
                "dataset_usage",
                str(usage.ref),
                resolver,
                ext_prefixes=ext_prefixes,
                allow_cross_kind_fallback=False,
                allow_tag=False,
            )
        )
    if entity.kind == "paper":
        for target in getattr(entity, "datasets", []) or []:
            rows.extend(
                _audit_dataset_reference(
                    entity,
                    "datasets",
                    str(target),
                    resolver,
                    ext_prefixes=ext_prefixes,
                    allow_cross_kind_fallback=False,
                    allow_tag=False,
                )
            )
    derivation = getattr(entity, "derivation", None)
    for target in getattr(derivation, "inputs", []) or []:
        rows.extend(
            _audit_dataset_reference(
                entity,
                "derivation.inputs",
                str(target),
                resolver,
                ext_prefixes=ext_prefixes,
                allow_cross_kind_fallback=False,
                allow_tag=False,
            )
        )
    for target in getattr(entity, "chain", None) or []:
        rows.extend(
            _audit_reference(
                entity,
                "chain",
                target,
                resolver,
                ext_prefixes=ext_prefixes,
                allow_cross_kind_fallback=False,
                allow_tag=False,
                peer_ids=peer_ids,
            )
        )
    audits_target = getattr(entity, "audits", None)
    if audits_target:
        rows.extend(
            _audit_reference(
                entity,
                "audits",
                audits_target,
                resolver,
                ext_prefixes=ext_prefixes,
                allow_cross_kind_fallback=False,
                allow_tag=False,
                peer_ids=peer_ids,
            )
        )
    for target in getattr(entity, "proposition_refs", None) or []:
        rows.extend(
            _audit_reference(
                entity,
                "proposition_refs",
                target,
                resolver,
                ext_prefixes=ext_prefixes,
                allow_cross_kind_fallback=False,
                allow_tag=False,
                peer_ids=peer_ids,
            )
        )
    for target in entity.same_as:
        rows.extend(_audit_reference(entity, "same_as", target, resolver, ext_prefixes=ext_prefixes, peer_ids=peer_ids))
    return rows


def _build_layered_claim_row(project_root: Path, entity: Entity) -> LayeredClaimMigrationRow:
    text = _read_entity_body(project_root, entity)
    inferred_claim_layer = _infer_claim_layer(text)
    inferred_identification_strength = _infer_identification_strength(text)
    warnings: list[str] = []
    todos: list[str] = []

    authored_claim_layer = str(entity.claim_layer) if entity.claim_layer is not None else None
    authored_identification_strength = (
        str(entity.identification_strength) if entity.identification_strength is not None else None
    )
    resolved_claim_layer = authored_claim_layer or inferred_claim_layer

    if authored_claim_layer is None and inferred_claim_layer is None:
        todos.append("TODO: classify claim_layer manually")
    if (
        authored_identification_strength is None
        and inferred_identification_strength is None
        and resolved_claim_layer != "structural_claim"
    ):
        todos.append("TODO: classify identification_strength manually")

    if _is_proxy_mediated(entity, text) and entity.measurement_model is None:
        warnings.append("Proxy-mediated proposition lacks measurement metadata.")
        todos.append("TODO: add measurement_model or justify why the proxy is treated as direct.")

    if _is_mechanistic(entity, text) and not _has_lower_layer_support(entity):
        warnings.append("Mechanistic proposition lacks linked lower-layer supporting propositions or observations.")
        todos.append("TODO: link lower-layer empirical support or mark the mechanistic claim as provisional.")

    return {
        "proposition": entity.canonical_id,
        "source_path": entity.file_path,
        "authored_claim_layer": authored_claim_layer,
        "authored_identification_strength": authored_identification_strength,
        "inferred_claim_layer": None if authored_claim_layer is not None else inferred_claim_layer,
        "inferred_identification_strength": (
            None if authored_identification_strength is not None else inferred_identification_strength
        ),
        "warnings": _dedupe_preserve_order(warnings),
        "todos": _dedupe_preserve_order(todos),
    }


def _read_entity_body(project_root: Path, entity: Entity) -> str:
    source_path = project_root / entity.file_path
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


def _is_proxy_mediated(entity: Entity, text: str) -> bool:
    return str(entity.proxy_directness) in {"indirect", "derived"} or bool(_PROXY_RE.search(text))


def _is_mechanistic(entity: Entity, text: str) -> bool:
    return str(entity.claim_layer) == "mechanistic_narrative" or bool(_MECHANISTIC_RE.search(text))


def _has_lower_layer_support(entity: Entity) -> bool:
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


def _audit_relation(
    relation: SourceRelation,
    resolver: ReferenceResolver,
    *,
    ext_prefixes: frozenset[str],
) -> list[AuditRow]:
    rows: list[AuditRow] = []
    rows.extend(_audit_relation_endpoint(relation, "subject", relation.subject, resolver, ext_prefixes=ext_prefixes))
    rows.extend(_audit_relation_endpoint(relation, "object", relation.object, resolver, ext_prefixes=ext_prefixes))
    return rows


def _audit_binding(
    binding: SourceBinding,
    resolver: ReferenceResolver,
    *,
    ext_prefixes: frozenset[str],
) -> list[AuditRow]:
    rows: list[AuditRow] = []
    rows.extend(_audit_binding_endpoint(binding, "model", binding.model, resolver, ext_prefixes=ext_prefixes))
    rows.extend(_audit_binding_endpoint(binding, "parameter", binding.parameter, resolver, ext_prefixes=ext_prefixes))
    for target in binding.source_refs:
        rows.extend(
            _audit_binding_endpoint(
                binding,
                "source_refs",
                target,
                resolver,
                ext_prefixes=ext_prefixes,
                allow_external=True,
            )
        )
    return rows


def _audit_binding_endpoint(
    binding: SourceBinding,
    field_name: str,
    raw_target: str,
    resolver: ReferenceResolver,
    *,
    ext_prefixes: frozenset[str],
    allow_external: bool = False,
) -> list[AuditRow]:
    if field_name == "source_refs" and is_bibliography_reference(raw_target):
        return []
    if allow_external and is_external_reference(raw_target, known_prefixes=ext_prefixes):
        return []

    resolution = resolver.resolve(raw_target)
    if resolution.status != "resolved":
        return [
            {
                "check": "unresolved_reference",
                "status": "fail",
                "source": f"{binding.model} -> {binding.parameter}",
                "field": field_name,
                "target": raw_target,
                "details": f"{binding.source_path} references an unknown canonical entity{_commons_hint_for(raw_target)}",
            }
        ]

    return []


def _audit_relation_endpoint(
    relation: SourceRelation,
    field_name: str,
    raw_target: str,
    resolver: ReferenceResolver,
    *,
    ext_prefixes: frozenset[str],
) -> list[AuditRow]:
    if field_name == "object" and is_external_reference(raw_target, known_prefixes=ext_prefixes):
        return []
    if field_name == "subject" and is_external_reference(raw_target, known_prefixes=ext_prefixes):
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

    resolution = resolver.resolve(raw_target)
    if resolution.status != "resolved":
        return [
            {
                "check": "unresolved_reference",
                "status": "fail",
                "source": f"{relation.subject} {relation.predicate} {relation.object}",
                "field": field_name,
                "target": raw_target,
                "details": f"{relation.source_path} references an unknown canonical entity{_commons_hint_for(raw_target)}",
            }
        ]

    return []


def _audit_dataset_reference(
    entity: Entity,
    field_name: str,
    raw_target: str,
    resolver: ReferenceResolver,
    *,
    ext_prefixes: frozenset[str],
    allow_cross_kind_fallback: bool = False,
    allow_tag: bool = False,
) -> list[AuditRow]:
    if (
        is_external_reference(raw_target, known_prefixes=ext_prefixes)
        or is_metadata_reference(raw_target)
        or not raw_target.startswith("dataset:")
    ):
        return [_invalid_dataset_reference_row(entity, field_name, raw_target)]

    resolution = resolver.resolve(
        raw_target,
        allow_cross_kind_fallback=allow_cross_kind_fallback,
        allow_tag=allow_tag,
    )
    if resolution.status == "ambiguous":
        return [
            {
                "check": "ambiguous_cross_kind_reference",
                "status": "fail",
                "source": entity.canonical_id,
                "field": field_name,
                "target": raw_target,
                "details": (
                    f"{entity.file_path} resolves to multiple canonical identities: " + ", ".join(resolution.candidates)
                ),
            }
        ]
    if resolution.status != "resolved" or resolution.canonical_id is None:
        return [
            {
                "check": "unresolved_reference",
                "status": "fail",
                "source": entity.canonical_id,
                "field": field_name,
                "target": raw_target,
                "details": f"{entity.file_path} references an unknown dataset entity{_commons_hint_for(raw_target)}",
            }
        ]
    if not resolution.canonical_id.startswith("dataset:"):
        return [_invalid_dataset_reference_row(entity, field_name, raw_target, canonical_id=resolution.canonical_id)]

    return []


def _invalid_dataset_reference_row(
    entity: Entity,
    field_name: str,
    raw_target: str,
    *,
    canonical_id: str | None = None,
) -> AuditRow:
    resolved_suffix = f" resolved to non-dataset entity {canonical_id}" if canonical_id is not None else ""
    return {
        "check": "invalid_dataset_reference",
        "status": "fail",
        "source": entity.canonical_id,
        "field": field_name,
        "target": raw_target,
        "details": f"{entity.file_path} {field_name} must reference a dataset:<slug> entity{resolved_suffix}",
    }


def _audit_reference(
    entity: Entity,
    field_name: str,
    raw_target: str,
    resolver: ReferenceResolver,
    *,
    ext_prefixes: frozenset[str],
    allow_cross_kind_fallback: bool = False,
    allow_tag: bool = False,
    allow_cross_project_address: bool = False,
    peer_ids: frozenset[str] = frozenset(),
) -> list[AuditRow]:
    if field_name == "source_refs" and raw_target.startswith("annotation:"):
        # An `annotation:<relpath>#<frag>` source ref points back to a source-annotation,
        # which is not an entity; the materializer mints a stable annotation URI directly.
        return []
    if field_name in {"source_refs", "evidence_refs"} and is_bibliography_reference(raw_target):
        return []
    if is_external_reference(raw_target, known_prefixes=ext_prefixes):
        return []
    if is_metadata_reference(raw_target):
        return []
    # A scoped `<peer>:<kind>:<slug>` ref to a registered peer is the design's
    # forward-compatible structured form (§B3a); local resolution is deferred to
    # federation (t068, §D4), so accept it here rather than flag unresolved.
    if _is_registered_peer_address(raw_target, peer_ids):
        return []

    resolution = resolver.resolve(
        raw_target,
        allow_cross_kind_fallback=allow_cross_kind_fallback,
        allow_tag=allow_tag,
    )
    if resolution.status in {"resolved", "tag"}:
        return []
    if resolution.status == "ambiguous":
        return [
            {
                "check": "ambiguous_cross_kind_reference",
                "status": "fail",
                "source": entity.canonical_id,
                "field": field_name,
                "target": raw_target,
                "details": (
                    f"{entity.file_path} resolves to multiple canonical identities: " + ", ".join(resolution.candidates)
                ),
            }
        ]
    if resolution.status == "scope_ambiguous":
        scopes = ", ".join(resolution.candidates)
        # candidates is sorted and always has >=2 entries here (scope_ambiguous fires
        # only on multi-scope ownership); suggest the alphabetically-first scope.
        suggestion = f"{resolution.candidates[0]}:{raw_target}"
        return [
            {
                "check": "ambiguous_reference",
                "status": "fail",
                "source": entity.canonical_id,
                "field": field_name,
                "target": raw_target,
                "details": (
                    f"{entity.file_path} reference '{raw_target}' is owned in multiple loaded scopes "
                    f"({scopes}); disambiguate with a scoped form, e.g. {suggestion}"
                ),
            }
        ]
    if resolution.status == "unresolved":
        if allow_cross_project_address and _is_cross_project_address(raw_target):
            return []
        return [
            {
                "check": "unresolved_reference",
                "status": "fail",
                "source": entity.canonical_id,
                "field": field_name,
                "target": raw_target,
                "details": f"{entity.file_path} references an unknown canonical entity{_commons_hint_for(raw_target)}",
            }
        ]

    return []


def _is_cross_project_address(raw_target: str) -> bool:
    if not is_address(raw_target):
        return False
    prefix, _ = raw_target.split(":", 1)
    return prefix not in PROJECT_ENTITY_PREFIXES


def _is_registered_peer_address(raw_target: str, peer_ids: frozenset[str]) -> bool:
    """True for a `<scope>:<kind>:<slug>` address whose scope is a registered peer.

    Such scoped cross-project references are the design's forward-compatible
    structured form (§B3a); the local resolver cannot verify a cross-scope owner
    until the federation primitive t068 lands (§D4), so the audit ACCEPTS them
    rather than flagging `unresolved_reference`. This keeps the graph audit
    consistent with `refs check` (classify_entity_ref accepts a peer-scoped
    address) and with the existing `evidence_refs` cross-project allowance.

    An UNREGISTERED prefix (a typo, or a project not declared in `peers:`) is not
    accepted here — it still falls through to a genuine unresolved-reference fail.
    """
    if not peer_ids or not is_address(raw_target):
        return False
    scope, artifact = raw_target.split(":", 1)
    # Require the `<kind>:<slug>` tail (a 3-part address), matching the design's
    # `project:kind:slug` form; a bare `<scope>:<slug>` is not a peer entity ref.
    return ":" in artifact and scope in peer_ids


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

from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator

import yaml
from rdflib import URIRef

from science_tool.bibliography import load_bib_entries
from science_tool.project_package.core import content_version, file_resource
from science_tool.graph.store import canonical_id_from_entity_uri, export_graph_payload, shorten_uri
from science_tool.graph.store.dataset import _load_dataset
from science_tool.graph.store.identity import _graph_uri
from science_tool.markdown_utils import parse_frontmatter, strip_html_comments_preserving_code
from science_tool.project_config import load_project_config
from science_tool.references import MarkdownPayload, build_reference_bundle, validate_exported_markdown
from science_tool.entity_scan import iter_entity_markdown

PROJECT_SCHEMA_VERSION = "science-project-package.v1"
ENTITY_CONTRACT = "science.entities"
PROSE_CONTRACT = "science.entity_prose"
LINK_CONTRACT = "science.entity_links"
BUNDLE_SCHEMA_VERSION = "1"

FINDING_TYPES = {"hypothesis", "proposition", "synthesis"}
ENTITY_CLASS_BY_TYPE = {
    "hypothesis": "epistemic",
    "proposition": "epistemic",
    "synthesis": "epistemic",
    "question": "epistemic",
    "dataset": "source",
    "method": "workflow",
    "search": "source",
    "workflow": "workflow",
    "workflow_run": "workflow",
    "paper": "reference",
}
DEFAULT_VIEW_BY_TYPE = {
    "hypothesis": {
        "surface": "findings",
        "route": "/findings/hypothesis",
        "label": "Hypotheses",
        "order": 10,
    },
    "proposition": {
        "surface": "findings",
        "route": "/findings/proposition",
        "label": "Propositions",
        "order": 20,
    },
    "synthesis": {
        "surface": "findings",
        "route": "/findings/synthesis",
        "label": "Synthesis",
        "order": 30,
    },
    "question": {"surface": "explore", "route": "/explore/question", "label": "Questions", "order": 40},
    "dataset": {"surface": "explore", "route": "/explore/dataset", "label": "Datasets", "order": 50},
    "method": {"surface": "explore", "route": "/explore/method", "label": "Methods", "order": 60},
    "search": {"surface": "explore", "route": "/explore/search", "label": "Searches", "order": 70},
    "workflow": {
        "surface": "explore",
        "route": "/explore/workflow",
        "label": "Workflows",
        "order": 80,
    },
    "workflow_run": {
        "surface": "explore",
        "route": "/explore/workflow-run",
        "label": "Workflow Runs",
        "order": 90,
    },
    "paper": {
        "surface": "explore",
        "route": "/explore/paper",
        "label": "Papers",
        "order": 100,
        "hidden": True,
    },
}
TYPE_DIR_MAP = {
    "hypotheses": "hypothesis",
    "propositions": "proposition",
    "synthesis": "synthesis",
    "questions": "question",
    "datasets": "dataset",
    "methods": "method",
    "searches": "search",
    "workflows": "workflow",
    "workflow-runs": "workflow_run",
    "papers": "paper",
}
PUBLIC_ACCESS_LEVELS = {"public", "open", "open-access", "unrestricted"}
BACKLINK_ROLES = {
    "supports",
    "contradicts",
    "related",
    "addresses",
    "synthesizes",
    "grounds",
    "tests",
    "amends",
    "supersedes",
    "mechanism",
    "evidence",
    "subject",
    "object",
}
PREDICATE_ROLE = {
    "cito:supports": ("supports", True),
    "supports": ("supports", True),
    "cito:disputes": ("contradicts", True),
    "disputes": ("contradicts", True),
    "cito:discusses": ("related", True),
    "skos:related": ("related", True),
    "mentions": ("related", True),
    "about": ("related", True),
    "related": ("related", True),
    "sci:addresses": ("addresses", True),
    "addresses": ("addresses", True),
    "sci:synthesizes": ("synthesizes", True),
    "synthesizes": ("synthesizes", True),
    "sci:grounds": ("grounds", True),
    "sci:groundedby": ("grounds", True),
    "sci:grounded_by": ("grounds", True),
    "grounds": ("grounds", True),
    "grounded_by": ("grounds", True),
    "sci:tests": ("tests", True),
    "tests": ("tests", True),
    "sci:amends": ("amends", True),
    "amends": ("amends", True),
    "sci:supersedes": ("supersedes", True),
    "sci:supersedesclaim": ("supersedes", True),
    "sci:supersedes_claim": ("supersedes", True),
    "supersedes": ("supersedes", True),
    "supersedes_claim": ("supersedes", True),
    "sci:hasproposition": ("has_proposition", False),
    "has_proposition": ("has_proposition", False),
    "sci:feedsinto": ("feeds_into", False),
    "feeds_into": ("feeds_into", False),
    "sci:bearson": ("bears_on", False),
    "bears_on": ("bears_on", False),
    "sci:realizes": ("realizes", False),
    "realizes": ("realizes", False),
    "sci:implements": ("implements", False),
    "implements": ("implements", False),
    "cito:usesmethodin": ("uses", False),
    "uses": ("uses", False),
    "uses_method_in": ("uses", False),
}
GRAPH_LINK_PREDICATES = {
    key
    for key, (_role, backlink) in PREDICATE_ROLE.items()
    if backlink
}
CITO_PREDICATES = {
    "cito:supports",
    "cito:disputes",
    "cito:discusses",
}


@dataclass(frozen=True)
class ExportedEntity:
    record: dict[str, Any]
    markdown: str
    frontmatter: dict[str, Any]
    source_path: str


@dataclass(frozen=True)
class SourceSemanticRecord:
    entity_id: str
    entity_type: str
    label: str
    source_path: str


def _readable_ref_label(entity_id: str) -> str:
    local = entity_id.split(":", 1)[1] if ":" in entity_id else entity_id
    return local.replace("-", " ").replace("_", " ")


def _source_semantic_record(entity_id: str, raw: dict[str, Any], source_path: str) -> SourceSemanticRecord:
    entity_type = entity_id.split(":", 1)[0] if ":" in entity_id else "semantic_ref"
    label = raw.get("title") or raw.get("name") or raw.get("label") or _readable_ref_label(entity_id)
    return SourceSemanticRecord(
        entity_id=entity_id,
        entity_type=entity_type,
        label=str(label),
        source_path=source_path,
    )


def _content_prose_semantic_records(project_root: Path) -> dict[str, SourceSemanticRecord]:
    content_root = project_root / "content" / "prose"
    if not content_root.exists():
        return {}
    records: dict[str, SourceSemanticRecord] = {}
    normalized: dict[str, tuple[str, str, str]] = {}
    for path in sorted([*content_root.rglob("*.yml"), *content_root.rglob("*.yaml")]):
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if not isinstance(raw, dict):
            continue
        entity_id = raw.get("entityRef")
        if not isinstance(entity_id, str) or not entity_id:
            continue
        source_path = path.relative_to(project_root).as_posix()
        record = _source_semantic_record(entity_id, raw, source_path)
        key = (record.entity_type, record.label, record.source_path)
        if entity_id in normalized and normalized[entity_id] != key:
            raise ValueError(f"duplicate source semantic entityRef with different records: {entity_id}")
        normalized[entity_id] = key
        records[entity_id] = record
    return records


def _graph_semantic_records(project_root: Path) -> dict[str, SourceSemanticRecord]:
    graph_path = project_root / "knowledge" / "graph.trig"
    if not graph_path.exists():
        return {}
    payload = export_graph_payload(graph_path, overlays=[])
    records: dict[str, SourceSemanticRecord] = {}
    for node in payload.nodes:
        entity_id = canonical_id_from_entity_uri(node.id)
        if entity_id is None:
            continue
        entity_type = entity_id.split(":", 1)[0] if ":" in entity_id else "semantic_ref"
        records[entity_id] = SourceSemanticRecord(
            entity_id=entity_id,
            entity_type=entity_type,
            label=node.label or _readable_ref_label(entity_id),
            source_path="knowledge/graph.trig",
        )
    return records


def _json_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _json_resource(name: str, path: str, kind: str, root: Path) -> dict[str, Any]:
    fr = file_resource(root, path)
    return {
        "name": name,
        "path": path,
        "kind": kind,
        "sensitivity": "public",
        "bytes": fr.bytes,
        "sha256": fr.sha256,
        "media_type": "application/json",
    }


def _load_raw_project_yaml(project_root: Path) -> dict[str, Any]:
    science_yaml = project_root / "science.yaml"
    if not science_yaml.exists():
        raise FileNotFoundError(f"missing science.yaml: {science_yaml}")
    return yaml.safe_load(science_yaml.read_text(encoding="utf-8")) or {}


def _read_markdown_body(path: Path, body_start_line: int) -> str:
    lines = path.read_text(encoding="utf-8").splitlines()
    return "\n".join(lines[body_start_line - 1 :]).lstrip("\n")


def _title_from_frontmatter(frontmatter: dict[str, Any], entity_id: str) -> str:
    value = frontmatter.get("title") or frontmatter.get("name") or frontmatter.get("label")
    return str(value) if value else entity_id


def _entity_type_for_path(path: Path, frontmatter: dict[str, Any]) -> str:
    declared = frontmatter.get("type")
    if isinstance(declared, str) and declared.strip():
        return declared.strip().replace("-", "_")
    parent = path.parent.name
    return TYPE_DIR_MAP.get(parent, parent.rstrip("s").replace("-", "_"))


def _section_key(title: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", title.strip().lower()).strip("_")
    return normalized or "body"


def _sections_from_markdown(markdown: str) -> list[dict[str, str]]:
    lines = markdown.splitlines()
    sections: list[dict[str, str]] = []
    current_title: str | None = None
    current_lines: list[str] = []
    for line in lines:
        if line.startswith("# "):
            if current_title is not None:
                sections.append(
                    {
                        "key": _section_key(current_title),
                        "title": current_title,
                        "markdown": "\n".join(current_lines).strip(),
                    }
                )
            current_title = line[2:].strip()
            current_lines = []
        else:
            current_lines.append(line)
    if current_title is not None:
        sections.append(
            {
                "key": _section_key(current_title),
                "title": current_title,
                "markdown": "\n".join(current_lines).strip(),
            }
        )
    if sections:
        return sections
    return [{"key": "body", "title": "Body", "markdown": markdown.strip()}]


def _is_public_frontmatter(frontmatter: dict[str, Any]) -> bool:
    sensitivity = str(frontmatter.get("sensitivity", "public")).strip().lower()
    if sensitivity != "public":
        return False
    access = frontmatter.get("access")
    if isinstance(access, dict) and "level" in access:
        return str(access["level"]).strip().lower() in PUBLIC_ACCESS_LEVELS
    return True


def _source_ref_citekeys(value: Any) -> list[str]:
    if isinstance(value, str):
        stripped = value.strip()
        return [stripped.removeprefix("cite:").strip()] if stripped.startswith("cite:") else []
    if isinstance(value, dict):
        keys = []
        cite = value.get("cite")
        if isinstance(cite, str) and cite.strip():
            keys.append(cite.strip())
        for nested in value.values():
            if nested is cite:
                continue
            keys.extend(_source_ref_citekeys(nested))
        return keys
    if isinstance(value, list):
        keys = []
        for item in value:
            keys.extend(_source_ref_citekeys(item))
        return keys
    return []


def _validate_source_refs(frontmatter: dict[str, Any], known_citekeys: set[str], source_path: str) -> None:
    missing = sorted(set(_source_ref_citekeys(frontmatter.get("source_refs"))) - known_citekeys)
    if missing:
        raise ValueError(f"unresolved source_refs citation in {source_path}: {', '.join(missing)}")


def _predicate_key(value: object) -> str:
    return str(value or "").strip().replace("-", "_").lower()


def _predicate_curie(uri_or_curie: object) -> str:
    value = str(uri_or_curie or "").strip()
    return shorten_uri(value) if value.startswith(("http://", "https://")) else value


def _warning(message: str, source_path: str | None = None) -> dict[str, str]:
    payload = {"message": message}
    if source_path:
        payload["source_path"] = source_path
    return payload


def _role_for_predicate(
    predicate: str,
    warnings: list[dict[str, str]],
    source_path: str,
) -> tuple[str, bool]:
    mapped = PREDICATE_ROLE.get(_predicate_key(predicate))
    if mapped:
        return mapped
    warnings.append(_warning(f"unknown link predicate kept generic: {predicate}", source_path))
    return "related", False


def _role_for_discusses(
    value: object,
    warnings: list[dict[str, str]],
    source_path: str,
) -> tuple[str, bool]:
    role = str(value or "related").strip().replace("-", "_").lower()
    if role in BACKLINK_ROLES:
        return role, True
    warnings.append(_warning(f"unknown discusses role kept generic: {role}", source_path))
    return role, False


def _is_finding_entity(entity_id: str, entity_type_by_id: dict[str, str]) -> bool:
    return entity_type_by_id.get(entity_id) in FINDING_TYPES


def _finding_backlink(
    *,
    source_id: str,
    target_id: str,
    backlink: bool,
    type_by_id: dict[str, str],
) -> bool:
    if not backlink:
        return False
    if _is_finding_entity(target_id, type_by_id):
        return True
    if not _is_finding_entity(source_id, type_by_id):
        return False
    return ENTITY_CLASS_BY_TYPE.get(type_by_id.get(target_id, ""), "source") != "workflow"


def _emit_link_row(
    rows: list[dict[str, Any]],
    *,
    source_id: str,
    target: object,
    predicate: str,
    role: str,
    backlink: bool,
    source_path: str,
    exported_ids: set[str],
    restricted_ids: set[str],
    type_by_id: dict[str, str],
    warnings: list[dict[str, str]],
) -> None:
    if not isinstance(target, str) or not target:
        warnings.append(_warning(f"link target is missing for predicate {predicate}", source_path))
        return
    if target not in exported_ids:
        message = "link target omitted because it is not exported"
        if target not in restricted_ids:
            message = f"{message}: {target}"
        warnings.append(_warning(message, source_path))
        return
    rows.append(
        {
            "source": source_id,
            "target": target,
            "predicate": predicate,
            "label": role.replace("_", " "),
            "link_role": role,
            "finding_backlink": _finding_backlink(
                source_id=source_id,
                target_id=target,
                backlink=backlink,
                type_by_id=type_by_id,
            ),
            "source_path": source_path,
        }
    )


def _discover_entities(
    project_root: Path,
    known_citekeys: set[str],
) -> tuple[list[ExportedEntity], bool, set[str]]:
    entity_root = project_root / "entities"
    if not entity_root.exists():
        return [], False, set()
    exported: list[ExportedEntity] = []
    restricted_present = False
    restricted_ids: set[str] = set()
    seen: set[str] = set()
    for path in iter_entity_markdown(entity_root):
        frontmatter, body_start_line = parse_frontmatter(path)
        body = _read_markdown_body(path, body_start_line)
        entity_id = frontmatter.get("id")
        if not isinstance(entity_id, str) or not entity_id:
            raise ValueError(f"{path}: missing entity id")
        if entity_id in seen:
            raise ValueError(f"duplicate exported entity id: {entity_id}")
        seen.add(entity_id)
        if not _is_public_frontmatter(frontmatter):
            restricted_present = True
            restricted_ids.add(entity_id)
            continue
        entity_type = _entity_type_for_path(path, frontmatter)
        source_path = path.relative_to(project_root).as_posix()
        validate_exported_markdown(
            [MarkdownPayload(path=source_path, field="body", text=body)],
            known_citekeys,
        )
        _validate_source_refs(frontmatter, known_citekeys, source_path)
        metadata = {
            key: value
            for key, value in frontmatter.items()
            if key
            not in {
                "id",
                "type",
                "title",
                "name",
                "label",
                "sensitivity",
                "aliases",
                "tags",
                "status",
                "discusses",
                "related",
                "relations",
            }
            and isinstance(value, (str, int, float, bool, list, dict))
        }
        record = {
            "id": entity_id,
            "type": entity_type,
            "class": ENTITY_CLASS_BY_TYPE.get(
                entity_type,
                "epistemic" if entity_type in FINDING_TYPES else "source",
            ),
            "display_name": _title_from_frontmatter(frontmatter, entity_id),
            "summary": frontmatter.get("summary"),
            "status": frontmatter.get("status"),
            "route": None,
            "source_path": source_path,
            "metadata": metadata,
            "aliases": frontmatter.get("aliases") or [],
            "tags": frontmatter.get("tags") or [],
            "source_refs": frontmatter.get("source_refs") or [],
        }
        exported.append(
            ExportedEntity(record=record, markdown=body, frontmatter=frontmatter, source_path=source_path)
        )
    return exported, restricted_present, restricted_ids


def _data_version(project_root: Path, raw_config: dict[str, Any], entities: list[ExportedEntity]) -> str:
    base = str(raw_config.get("last_modified") or raw_config.get("version") or "0")

    def chunks() -> Iterator[bytes]:
        yield (project_root / "science.yaml").read_bytes()
        bib = project_root / "papers" / "references.bib"
        if bib.exists():
            yield bib.read_bytes()
        graph = project_root / "knowledge" / "graph.trig"
        if graph.exists():
            yield graph.read_bytes()
        for entity in entities:
            yield entity.source_path.encode("utf-8")
            yield json.dumps(entity.frontmatter, sort_keys=True, default=str).encode("utf-8")
            yield json.dumps(entity.record, sort_keys=True, default=str).encode("utf-8")
            yield entity.markdown.encode("utf-8")

    return content_version(base, chunks())


def _view_config_for_type(entity_type: str, raw_config: dict[str, Any]) -> dict[str, Any]:
    overrides = ((raw_config.get("labnote") or {}).get("views") or {})
    base = dict(
        DEFAULT_VIEW_BY_TYPE.get(
            entity_type,
            {
                "surface": "explore",
                "route": f"/explore/{entity_type.replace('_', '-')}",
                "label": entity_type.replace("_", " ").title(),
                "order": 500,
            },
        )
    )
    override = overrides.get(entity_type) or {}
    unknown = set(override) - {"label", "order", "surface", "hidden"}
    if unknown:
        raise ValueError(f"invalid labnote view override for {entity_type}: {sorted(unknown)}")
    base.update(override)
    return base


def _filter_hidden_entities(
    entities: list[ExportedEntity],
    raw_config: dict[str, Any],
) -> list[ExportedEntity]:
    return [
        entity
        for entity in entities
        if not _view_config_for_type(entity.record["type"], raw_config).get("hidden")
    ]


def _views_for_entities(entities: list[ExportedEntity], raw_config: dict[str, Any]) -> dict[str, Any]:
    seen_types = sorted({entity.record["type"] for entity in entities})
    views = []
    for entity_type in seen_types:
        base = _view_config_for_type(entity_type, raw_config)
        if base.get("hidden"):
            continue
        views.append(
            {
                "id": entity_type,
                "label": base["label"],
                "surface": base["surface"],
                "route": base["route"],
                "order": base["order"],
                "modules": [],
            }
        )
    return {"views": sorted(views, key=lambda view: (view["order"], view["id"]))}


def _validate_capabilities(project: dict[str, Any], views: dict[str, Any]) -> None:
    has_graph_module = any(
        module.get("id") == "graph" or module.get("type") == "graph"
        for view in views["views"]
        for module in view.get("modules", [])
    )
    if has_graph_module and project["capabilities"].get("graphs") is False:
        raise ValueError("capabilities.graphs is false but views declare a graph module")


def _entity_bundle(entities: list[ExportedEntity]) -> dict[str, Any]:
    return {
        "contract": ENTITY_CONTRACT,
        "schema_version": BUNDLE_SCHEMA_VERSION,
        "entities": [entity.record for entity in entities],
    }


def _prose_bundle(entities: list[ExportedEntity]) -> dict[str, Any]:
    records: dict[str, Any] = {}
    for entity in entities:
        markdown = strip_html_comments_preserving_code(entity.markdown)
        if not markdown.strip():
            continue
        records[entity.record["id"]] = {
            "markdown": markdown,
            "sections": _sections_from_markdown(markdown),
            "source_path": entity.source_path,
        }
    return {
        "contract": PROSE_CONTRACT,
        "schema_version": BUNDLE_SCHEMA_VERSION,
        "entities": records,
    }


def _frontmatter_link_rows(
    entities: list[ExportedEntity],
    restricted_ids: set[str],
    warnings: list[dict[str, str]],
) -> list[dict[str, Any]]:
    exported_ids = {entity.record["id"] for entity in entities}
    type_by_id = {entity.record["id"]: entity.record["type"] for entity in entities}
    rows: list[dict[str, Any]] = []
    for entity in entities:
        source_id = entity.record["id"]
        source_path = entity.source_path
        frontmatter = entity.frontmatter
        for item in frontmatter.get("discusses") or []:
            if isinstance(item, str):
                _emit_link_row(
                    rows,
                    source_id=source_id,
                    target=item,
                    predicate="cito:discusses",
                    role="related",
                    backlink=True,
                    source_path=source_path,
                    exported_ids=exported_ids,
                    restricted_ids=restricted_ids,
                    type_by_id=type_by_id,
                    warnings=warnings,
                )
                continue
            if isinstance(item, dict):
                target = item.get("frame") or item.get("target") or item.get("entity")
                role, backlink = _role_for_discusses(item.get("role"), warnings, source_path)
                _emit_link_row(
                    rows,
                    source_id=source_id,
                    target=target,
                    predicate="cito:discusses",
                    role=role,
                    backlink=backlink,
                    source_path=source_path,
                    exported_ids=exported_ids,
                    restricted_ids=restricted_ids,
                    type_by_id=type_by_id,
                    warnings=warnings,
                )
                continue
            warnings.append(_warning("unsupported discusses entry omitted", source_path))
        for target in frontmatter.get("related") or []:
            _emit_link_row(
                rows,
                source_id=source_id,
                target=target,
                predicate="skos:related",
                role="related",
                backlink=True,
                source_path=source_path,
                exported_ids=exported_ids,
                restricted_ids=restricted_ids,
                type_by_id=type_by_id,
                warnings=warnings,
            )
        for item in frontmatter.get("relations") or []:
            if not isinstance(item, dict):
                warnings.append(_warning("unsupported relations entry omitted", source_path))
                continue
            predicate = str(item.get("predicate") or item.get("relation") or "related")
            role, backlink = _role_for_predicate(predicate, warnings, source_path)
            _emit_link_row(
                rows,
                source_id=source_id,
                target=item.get("target") or item.get("object"),
                predicate=predicate,
                role=role,
                backlink=backlink,
                source_path=source_path,
                exported_ids=exported_ids,
                restricted_ids=restricted_ids,
                type_by_id=type_by_id,
                warnings=warnings,
            )
    return rows


def _graph_link_rows(
    project_root: Path,
    entities: list[ExportedEntity],
    restricted_ids: set[str],
    warnings: list[dict[str, str]],
) -> list[dict[str, Any]]:
    graph_path = project_root / "knowledge" / "graph.trig"
    if not graph_path.exists():
        return []
    exported_ids = {entity.record["id"] for entity in entities}
    type_by_id = {entity.record["id"]: entity.record["type"] for entity in entities}
    rows: list[dict[str, Any]] = _graph_cito_link_rows(
        graph_path,
        exported_ids=exported_ids,
        restricted_ids=restricted_ids,
        type_by_id=type_by_id,
        warnings=warnings,
    )
    payload = export_graph_payload(graph_path, overlays=[])
    skipped = {"non_knowledge_layer": 0, "structural_predicate": 0, "unexported_endpoint": 0}
    for edge in payload.edges:
        if edge.graph_layer != "graph/knowledge":
            skipped["non_knowledge_layer"] += 1
            continue
        predicate = _predicate_curie(edge.predicate)
        if _predicate_key(predicate) not in GRAPH_LINK_PREDICATES:
            skipped["structural_predicate"] += 1
            continue
        source_id = canonical_id_from_entity_uri(edge.subject)
        target_id = canonical_id_from_entity_uri(edge.object)
        if source_id is None or target_id is None:
            skipped["unexported_endpoint"] += 1
            continue
        if source_id not in exported_ids or target_id not in exported_ids:
            skipped["unexported_endpoint"] += 1
            continue
        role, backlink = _role_for_predicate(predicate, warnings, "knowledge/graph.trig")
        _emit_link_row(
            rows,
            source_id=source_id,
            target=target_id,
            predicate=predicate,
            role=role,
            backlink=backlink,
            source_path="knowledge/graph.trig",
            exported_ids=exported_ids,
            restricted_ids=restricted_ids,
            type_by_id=type_by_id,
            warnings=warnings,
        )
    skipped_total = sum(skipped.values())
    if skipped_total:
        warnings.append(
            _warning(
                "graph links skipped: "
                f"{skipped['non_knowledge_layer']} non-knowledge-layer, "
                f"{skipped['structural_predicate']} structural predicate, "
                f"{skipped['unexported_endpoint']} unexported endpoint",
                "knowledge/graph.trig",
            )
        )
    return rows


def _graph_cito_link_rows(
    graph_path: Path,
    *,
    exported_ids: set[str],
    restricted_ids: set[str],
    type_by_id: dict[str, str],
    warnings: list[dict[str, str]],
) -> list[dict[str, Any]]:
    dataset = _load_dataset(graph_path)
    knowledge = dataset.graph(_graph_uri("graph/knowledge"))
    rows: list[dict[str, Any]] = []
    for subject, predicate, target in knowledge.triples((None, None, None)):
        predicate_curie = _predicate_curie(str(predicate))
        if predicate_curie not in CITO_PREDICATES:
            continue
        if not isinstance(subject, URIRef) or not isinstance(target, URIRef):
            continue
        source_id = canonical_id_from_entity_uri(str(subject))
        target_id = canonical_id_from_entity_uri(str(target))
        if source_id not in exported_ids or target_id not in exported_ids:
            continue
        role, backlink = _role_for_predicate(predicate_curie, warnings, "knowledge/graph.trig")
        _emit_link_row(
            rows,
            source_id=source_id,
            target=target_id,
            predicate=predicate_curie,
            role=role,
            backlink=backlink,
            source_path="knowledge/graph.trig",
            exported_ids=exported_ids,
            restricted_ids=restricted_ids,
            type_by_id=type_by_id,
            warnings=warnings,
        )
    return rows


def _link_identity(row: dict[str, Any]) -> tuple[str, str, str, str]:
    return (row["source"], row["target"], row["predicate"], row["link_role"])


def _dedupe_link_rows(
    frontmatter_rows: list[dict[str, Any]],
    graph_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    rows_by_identity: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for row in frontmatter_rows:
        rows_by_identity[_link_identity(row)] = row
    for row in graph_rows:
        rows_by_identity[_link_identity(row)] = row
    return list(rows_by_identity.values())


def _link_rows(
    project_root: Path,
    entities: list[ExportedEntity],
    restricted_ids: set[str],
    warnings: list[dict[str, str]],
) -> list[dict[str, Any]]:
    frontmatter_rows = _frontmatter_link_rows(entities, restricted_ids, warnings)
    graph_rows = _graph_link_rows(project_root, entities, restricted_ids, warnings)
    return _dedupe_link_rows(frontmatter_rows, graph_rows)


def _link_bundle(
    project_root: Path,
    entities: list[ExportedEntity],
    restricted_ids: set[str],
    warnings: list[dict[str, str]],
) -> dict[str, Any]:
    return {
        "contract": LINK_CONTRACT,
        "schema_version": BUNDLE_SCHEMA_VERSION,
        "links": _link_rows(project_root, entities, restricted_ids, warnings),
    }


def export_labnote_package(project_root: Path, out_dir: Path) -> dict[str, Any]:
    project_root = project_root.expanduser().resolve()
    out_dir = out_dir.expanduser().resolve()
    raw_config = _load_raw_project_yaml(project_root)
    config = load_project_config(project_root)
    if not config.id:
        raise ValueError("science.yaml must declare a non-empty project id")
    known_citekeys = set(load_bib_entries(project_root))
    entities, restricted_present, restricted_ids = _discover_entities(project_root, known_citekeys)
    entities = _filter_hidden_entities(entities, raw_config)
    data_version = _data_version(project_root, raw_config, entities)
    label = str(((raw_config.get("labnote") or {}).get("label")) or raw_config.get("name") or config.id)
    project = {
        "schema_version": PROJECT_SCHEMA_VERSION,
        "project": {
            "id": config.id,
            "label": label,
            "profile": "research",
            "summary": raw_config.get("summary"),
        },
        "package": {
            "data_version": data_version,
            "source_project": config.id,
        },
        "capabilities": {
            "entity_search": True,
            "findings": any(entity.record["type"] in FINDING_TYPES for entity in entities),
            "graphs": False,
            "dataset_support": False,
            "quantitative_tables": False,
            "restricted_resources_present": restricted_present,
        },
    }
    views = _views_for_entities(entities, raw_config)
    _validate_capabilities(project, views)

    shutil.rmtree(out_dir, ignore_errors=True)
    out_dir.mkdir(parents=True, exist_ok=True)
    _json_write(out_dir / "project.json", project)
    _json_write(out_dir / "views.json", views)
    _json_write(out_dir / "entities" / "index.json", _entity_bundle(entities))
    _json_write(out_dir / "prose_bundles" / "entity_prose_bundles.json", _prose_bundle(entities))
    _json_write(out_dir / "references" / "index.json", build_reference_bundle(project_root))
    diagnostics = {"errors": [], "warnings": []}
    _json_write(
        out_dir / "links" / "index.json",
        _link_bundle(project_root, entities, restricted_ids, diagnostics["warnings"]),
    )
    _json_write(out_dir / "export_diagnostics.json", diagnostics)

    manifest = {
        "data_version": data_version,
        "resources": [
            _json_resource("project.json", "project.json", "descriptor", out_dir),
            _json_resource("views.json", "views.json", "descriptor", out_dir),
            _json_resource("references", "references/index.json", "bundle", out_dir),
            _json_resource("entities", "entities/index.json", "bundle", out_dir),
            _json_resource("entity_prose", "prose_bundles/entity_prose_bundles.json", "bundle", out_dir),
            _json_resource("entity_links", "links/index.json", "bundle", out_dir),
            _json_resource("export_diagnostics", "export_diagnostics.json", "descriptor", out_dir),
        ],
    }
    _json_write(out_dir / "manifest.json", manifest)
    return diagnostics

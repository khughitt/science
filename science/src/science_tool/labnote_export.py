from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from science_tool.bibliography import load_bib_entries
from science_tool.markdown_utils import parse_frontmatter
from science_tool.project_config import load_project_config
from science_tool.references import MarkdownPayload, build_reference_bundle, validate_exported_markdown

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


@dataclass(frozen=True)
class ExportedEntity:
    record: dict[str, Any]
    markdown: str
    frontmatter: dict[str, Any]
    source_path: str


def _json_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json_resource(name: str, path: str, kind: str, root: Path) -> dict[str, Any]:
    file_path = root / path
    return {
        "name": name,
        "path": path,
        "kind": kind,
        "sensitivity": "public",
        "bytes": file_path.stat().st_size,
        "sha256": _sha256(file_path),
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


def _discover_entities(project_root: Path, known_citekeys: set[str]) -> tuple[list[ExportedEntity], bool]:
    entity_root = project_root / "entities"
    if not entity_root.exists():
        return [], False
    exported: list[ExportedEntity] = []
    restricted_present = False
    seen: set[str] = set()
    for path in sorted(entity_root.rglob("*.md")):
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
    return exported, restricted_present


def _data_version(project_root: Path, raw_config: dict[str, Any], entities: list[ExportedEntity]) -> str:
    base = str(raw_config.get("last_modified") or raw_config.get("version") or "0")
    digest = hashlib.sha256()
    digest.update((project_root / "science.yaml").read_bytes())
    bib = project_root / "papers" / "references.bib"
    if bib.exists():
        digest.update(bib.read_bytes())
    for entity in entities:
        digest.update(entity.source_path.encode("utf-8"))
        digest.update(json.dumps(entity.frontmatter, sort_keys=True, default=str).encode("utf-8"))
        digest.update(json.dumps(entity.record, sort_keys=True, default=str).encode("utf-8"))
        digest.update(entity.markdown.encode("utf-8"))
    return f"{base}+{digest.hexdigest()[:12]}"


def _views_for_entities(entities: list[ExportedEntity], raw_config: dict[str, Any]) -> dict[str, Any]:
    overrides = ((raw_config.get("labnote") or {}).get("views") or {})
    seen_types = sorted({entity.record["type"] for entity in entities})
    views = []
    for entity_type in seen_types:
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
    return {
        "contract": PROSE_CONTRACT,
        "schema_version": BUNDLE_SCHEMA_VERSION,
        "entities": {
            entity.record["id"]: {
                "markdown": entity.markdown,
                "sections": _sections_from_markdown(entity.markdown),
                "source_path": entity.source_path,
            }
            for entity in entities
            if entity.markdown.strip()
        },
    }


def _empty_link_bundle() -> dict[str, Any]:
    return {"contract": LINK_CONTRACT, "schema_version": BUNDLE_SCHEMA_VERSION, "links": []}


def export_labnote_package(project_root: Path, out_dir: Path) -> dict[str, Any]:
    project_root = project_root.expanduser().resolve()
    out_dir = out_dir.expanduser().resolve()
    config = load_project_config(project_root)
    if not config.id:
        raise ValueError("science.yaml must declare a non-empty project id")
    raw_config = _load_raw_project_yaml(project_root)
    known_citekeys = set(load_bib_entries(project_root))
    entities, restricted_present = _discover_entities(project_root, known_citekeys)
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

    out_dir.mkdir(parents=True, exist_ok=True)
    _json_write(out_dir / "project.json", project)
    _json_write(out_dir / "views.json", views)
    _json_write(out_dir / "entities" / "index.json", _entity_bundle(entities))
    _json_write(out_dir / "prose_bundles" / "entity_prose_bundles.json", _prose_bundle(entities))
    _json_write(out_dir / "references" / "index.json", build_reference_bundle(project_root))
    _json_write(out_dir / "links" / "index.json", _empty_link_bundle())
    diagnostics = {"errors": [], "warnings": []}
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

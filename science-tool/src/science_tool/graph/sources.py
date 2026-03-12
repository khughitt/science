"""Structured upstream sources for deterministic graph materialization."""

from __future__ import annotations

import re
from pathlib import Path

import yaml
from pydantic import BaseModel, Field

from science_model.frontmatter import parse_entity_file, parse_frontmatter
from science_model.profiles import CORE_PROFILE
from science_tool.paths import resolve_paths
from science_tool.tasks import parse_tasks


_SHORT_ID_RE = re.compile(r"^(?P<token>[a-z]\d+)(?:[-_].*)?$", re.IGNORECASE)
_EXTERNAL_PREFIXES = frozenset({"go", "mesh", "doid", "hp", "so", "ncbitaxon", "ncbigene", "ensembl"})
_CORE_KINDS = frozenset(kind.name for kind in CORE_PROFILE.entity_kinds)


class AliasCollisionError(ValueError):
    """Raised when two canonical entities claim the same alias."""

    def __init__(self, alias: str, first_canonical_id: str, second_canonical_id: str) -> None:
        self.alias = alias
        self.first_canonical_id = first_canonical_id
        self.second_canonical_id = second_canonical_id
        super().__init__(f"Alias '{alias}' maps to both {first_canonical_id} and {second_canonical_id}")


class SourceEntity(BaseModel):
    """A canonical entity collected from project source files."""

    canonical_id: str
    kind: str
    title: str
    profile: str
    source_path: str
    status: str | None = None
    content_preview: str = ""
    related: list[str] = Field(default_factory=list)
    blocked_by: list[str] = Field(default_factory=list)
    source_refs: list[str] = Field(default_factory=list)
    ontology_terms: list[str] = Field(default_factory=list)
    aliases: list[str] = Field(default_factory=list)


class KnowledgeProfiles(BaseModel):
    """Selected knowledge profiles for a project."""

    curated: list[str] = Field(default_factory=list)
    local: str = "project_specific"


class ProjectSources(BaseModel):
    """Structured source bundle used to materialize a project graph."""

    project_name: str
    project_root: str
    profiles: KnowledgeProfiles
    entities: list[SourceEntity]


def load_project_sources(project_root: Path) -> ProjectSources:
    """Load typed project entities from markdown docs and task files."""
    project_root = project_root.resolve()
    config = _read_project_config(project_root)
    paths = resolve_paths(project_root)

    entities: list[SourceEntity] = []
    entities.extend(_load_markdown_entities(project_root, [paths.doc_dir, paths.specs_dir]))
    entities.extend(_load_task_entities(project_root, paths.tasks_dir))
    entities.sort(key=lambda entity: entity.canonical_id)

    return ProjectSources(
        project_name=str(config["name"]),
        project_root=str(project_root),
        profiles=KnowledgeProfiles.model_validate(config["knowledge_profiles"]),
        entities=entities,
    )


def build_alias_map(entities: list[SourceEntity]) -> dict[str, str]:
    """Build a best-effort alias map for canonical entity resolution."""
    alias_map: dict[str, str] = {}
    for entity in entities:
        _register_alias(alias_map, entity.canonical_id, entity.canonical_id)
        _register_alias(alias_map, entity.canonical_id.lower(), entity.canonical_id)
        for alias in entity.aliases:
            _register_alias(alias_map, alias, entity.canonical_id)
            _register_alias(alias_map, alias.lower(), entity.canonical_id)
    return alias_map


def is_external_reference(raw: str) -> bool:
    """Return True when a reference points outside the project graph."""
    if raw.startswith(("http://", "https://")):
        return True
    if ":" not in raw:
        return False
    prefix, _ = raw.split(":", 1)
    return prefix.lower() in _EXTERNAL_PREFIXES


def _load_markdown_entities(project_root: Path, roots: list[Path]) -> list[SourceEntity]:
    entities: list[SourceEntity] = []
    for root in roots:
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*.md")):
            entity = parse_entity_file(path, project_slug=project_root.name)
            if entity is None:
                continue

            frontmatter = parse_frontmatter(path)
            raw_aliases: list[str] = []
            raw_profile = _default_profile_for_kind(entity.type.value)
            if frontmatter is not None:
                fm, _ = frontmatter
                aliases = fm.get("aliases") or []
                if isinstance(aliases, list):
                    raw_aliases = [str(alias) for alias in aliases]
                profile = fm.get("profile")
                if isinstance(profile, str) and profile.strip():
                    raw_profile = profile

            entities.append(
                SourceEntity(
                    canonical_id=entity.canonical_id,
                    kind=entity.type.value,
                    title=entity.title,
                    profile=raw_profile,
                    source_path=entity.file_path,
                    status=entity.status,
                    content_preview=entity.content_preview,
                    related=entity.related,
                    source_refs=entity.source_refs,
                    ontology_terms=entity.ontology_terms,
                    aliases=_derive_aliases(entity.canonical_id, raw_aliases),
                )
            )
    return entities


def _load_task_entities(project_root: Path, tasks_dir: Path) -> list[SourceEntity]:
    entities: list[SourceEntity] = []
    for path in _task_paths(tasks_dir):
        rel_path = path.relative_to(project_root).as_posix()
        for task in parse_tasks(path):
            canonical_id = f"task:{task.id.lower()}"
            entities.append(
                SourceEntity(
                    canonical_id=canonical_id,
                    kind="task",
                    title=task.title,
                    profile=_default_profile_for_kind("task"),
                    source_path=rel_path,
                    status=task.status,
                    content_preview=task.description,
                    related=task.related,
                    blocked_by=task.blocked_by,
                    aliases=_derive_aliases(canonical_id, [task.id, task.id.upper()]),
                )
            )
    return entities


def _task_paths(tasks_dir: Path) -> list[Path]:
    paths: list[Path] = []
    active_path = tasks_dir / "active.md"
    if active_path.is_file():
        paths.append(active_path)

    done_dir = tasks_dir / "done"
    if done_dir.is_dir():
        paths.extend(sorted(done_dir.glob("*.md")))
    return paths


def _read_project_config(project_root: Path) -> dict[str, object]:
    yaml_path = project_root / "science.yaml"
    data: dict[str, object] = {}
    if yaml_path.is_file():
        data = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}

    knowledge_profiles = data.get("knowledge_profiles") or {}
    if not isinstance(knowledge_profiles, dict):
        knowledge_profiles = {}

    return {
        "name": str(data.get("name") or project_root.name),
        "knowledge_profiles": {
            "curated": list(knowledge_profiles.get("curated") or []),
            "local": str(knowledge_profiles.get("local") or "project_specific"),
        },
    }


def _derive_aliases(canonical_id: str, explicit_aliases: list[str]) -> list[str]:
    aliases: list[str] = []
    seen: set[str] = set()

    def add(alias: str) -> None:
        cleaned = alias.strip()
        if not cleaned or cleaned == canonical_id or cleaned in seen:
            return
        seen.add(cleaned)
        aliases.append(cleaned)

    for alias in explicit_aliases:
        add(alias)

    kind, slug = canonical_id.split(":", 1)
    match = _SHORT_ID_RE.match(slug)
    if match is None:
        head = slug.split("-", 1)[0]
        match = _SHORT_ID_RE.match(head)
    if match is not None:
        token = match.group("token")
        add(f"{kind}:{token.lower()}")
        add(f"{kind}:{token.upper()}")
        add(token.lower())
        add(token.upper())

    return aliases


def _register_alias(alias_map: dict[str, str], alias: str, canonical_id: str) -> None:
    existing = alias_map.get(alias)
    if existing is not None and existing != canonical_id:
        raise AliasCollisionError(alias=alias, first_canonical_id=existing, second_canonical_id=canonical_id)
    alias_map[alias] = canonical_id


def _default_profile_for_kind(kind: str) -> str:
    if kind in _CORE_KINDS:
        return "core"
    return "project_specific"

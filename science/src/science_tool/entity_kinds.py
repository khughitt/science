from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import ValidationError
from science_model.entities import EntityClass
from science_model.ontologies import load_catalogs_for_names
from science_model.profiles import CORE_PROFILE, LOCAL_PROFILE
from science_model.profiles.schema import ProfileManifest

from science_tool.graph.entity_registry import EntityRegistry
from science_tool.graph.sources import local_profile_sources_dir


def register_local_kind(project_root: Path, kind: str, entity_class: str) -> str:
    validated_entity_class = _validate_entity_class(entity_class)
    config = _read_project_config(project_root)
    _reject_reserved_kind(config, kind)
    local_profile = _local_profile_name(project_root)
    manifest_path = local_profile_sources_dir(project_root, local_profile=local_profile) / "manifest.yaml"
    manifest = _read_manifest(manifest_path)
    _ensure_manifest_defaults(manifest, local_profile)
    _validate_manifest_shape(manifest_path, manifest)
    entity_kinds = manifest["entity_kinds"]

    requested = {
        "name": kind,
        "canonical_prefix": kind,
        "layer": "layer/local",
        "description": f"Project-local {kind} entity kind.",
        "entity_class": validated_entity_class,
    }
    for entry in entity_kinds:
        if entry.get("name") != kind:
            continue
        if entry.get("entity_class") == validated_entity_class:
            manifest_path.parent.mkdir(parents=True, exist_ok=True)
            manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
            return "already registered"
        msg = f"kind {kind!r} already registered with different metadata"
        raise ValueError(msg)

    entity_kinds.append(requested)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    return "registered"


def _validate_entity_class(entity_class: str) -> str:
    try:
        return EntityClass(entity_class).value
    except ValueError as exc:
        allowed = ", ".join(item.value for item in EntityClass)
        msg = f"Invalid entity_class {entity_class!r}; expected one of: {allowed}"
        raise ValueError(msg) from exc


def _reject_reserved_kind(config: dict, kind: str) -> None:
    builtin_kinds = {
        entity_kind.name for profile in (CORE_PROFILE, LOCAL_PROFILE) for entity_kind in profile.entity_kinds
    }
    builtin_kinds.update(EntityRegistry.with_core_types().all_kind_classes())
    if kind in builtin_kinds:
        msg = f"kind {kind!r} is a built-in entity kind and cannot be registered locally"
        raise ValueError(msg)
    for catalog in load_catalogs_for_names(_active_ontology_names(config)):
        if any(entity_type.name == kind for entity_type in catalog.entity_types):
            msg = f"kind {kind!r} is an active ontology entity kind and cannot be registered locally"
            raise ValueError(msg)


def _read_manifest(manifest_path: Path) -> dict:
    if not manifest_path.exists():
        return {}
    loaded = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    if not isinstance(loaded, dict):
        msg = f"{manifest_path}: must contain a YAML mapping"
        raise ValueError(msg)
    return loaded


def _ensure_manifest_defaults(manifest: dict, local_profile: str) -> None:
    if not manifest.get("name"):
        manifest["name"] = local_profile
    if manifest.get("imports") is None:
        manifest["imports"] = []
    if not manifest.get("strictness"):
        manifest["strictness"] = "typed-extension"
    manifest.setdefault("entity_kinds", [])
    if manifest.get("relation_kinds") is None:
        manifest["relation_kinds"] = []


def _validate_manifest_shape(manifest_path: Path, manifest: dict) -> None:
    entity_kinds = manifest.get("entity_kinds")
    if not isinstance(entity_kinds, list):
        msg = f"{manifest_path}: entity_kinds must be a list"
        raise ValueError(msg)
    for entry in entity_kinds:
        if not isinstance(entry, dict):
            msg = f"{manifest_path}: entity_kinds entries must be mappings"
            raise ValueError(msg)
    try:
        ProfileManifest.model_validate(manifest)
    except ValidationError as exc:
        msg = f"{manifest_path}: invalid profile manifest: {_format_validation_error(exc)}"
        raise ValueError(msg) from exc


def _format_validation_error(exc: ValidationError) -> str:
    parts: list[str] = []
    for error in exc.errors():
        loc = ".".join(str(part) for part in error.get("loc", ()))
        detail = error.get("msg", "invalid")
        parts.append(f"{loc}: {detail}" if loc else detail)
    return "; ".join(parts) if parts else str(exc)


def _read_project_config(project_root: Path) -> dict:
    config_path = project_root / "science.yaml"
    if not config_path.exists():
        return {}
    config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    if not isinstance(config, dict):
        return {}
    return config


def _active_ontology_names(config: dict) -> list[str]:
    raw_ontologies = config.get("ontologies") or []
    if not isinstance(raw_ontologies, list):
        return []
    return [str(ontology) for ontology in raw_ontologies]


def _local_profile_name(project_root: Path) -> str:
    config = _read_project_config(project_root)
    knowledge_profiles = config.get("knowledge_profiles") or {}
    if not isinstance(knowledge_profiles, dict):
        knowledge_profiles = {}
    if not knowledge_profiles:
        profiles = config.get("profiles") or {}
        if isinstance(profiles, dict):
            knowledge_profiles = profiles
    local_profile = knowledge_profiles.get("local")
    if local_profile:
        return str(local_profile)
    return "local"

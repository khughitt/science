from __future__ import annotations

from pathlib import Path

import yaml

from science_tool.graph.sources import local_profile_sources_dir


def register_local_kind(project_root: Path, kind: str, entity_class: str) -> str:
    local_profile = _local_profile_name(project_root)
    manifest_path = local_profile_sources_dir(project_root, local_profile=local_profile) / "manifest.yaml"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest = _read_manifest(manifest_path)
    entity_kinds = manifest.setdefault("entity_kinds", [])
    if not isinstance(entity_kinds, list):
        msg = f"{manifest_path}: entity_kinds must be a list"
        raise ValueError(msg)

    requested = {
        "name": kind,
        "canonical_prefix": kind,
        "layer": "layer/local",
        "description": f"Project-local {kind} entity kind.",
        "entity_class": entity_class,
    }
    for entry in entity_kinds:
        if not isinstance(entry, dict):
            msg = f"{manifest_path}: entity_kinds entries must be mappings"
            raise ValueError(msg)
        if entry.get("name") != kind:
            continue
        if entry.get("entity_class") == entity_class:
            _ensure_manifest_defaults(manifest, local_profile)
            manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
            return "already registered"
        msg = f"kind {kind!r} already registered with different metadata"
        raise ValueError(msg)

    _ensure_manifest_defaults(manifest, local_profile)
    entity_kinds.append(requested)
    manifest_path.write_text(yaml.safe_dump(manifest, sort_keys=False), encoding="utf-8")
    return "registered"


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


def _local_profile_name(project_root: Path) -> str:
    config_path = project_root / "science.yaml"
    if not config_path.exists():
        return "local"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    if not isinstance(config, dict):
        return "local"
    knowledge_profiles = config.get("knowledge_profiles") or {}
    if not isinstance(knowledge_profiles, dict):
        return "local"
    local_profile = knowledge_profiles.get("local")
    if local_profile:
        return str(local_profile)
    return "local"

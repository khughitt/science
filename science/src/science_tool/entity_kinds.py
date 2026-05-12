from __future__ import annotations

from pathlib import Path

import yaml


def register_local_kind(project_root: Path, kind: str, entity_class: str) -> str:
    profile_path = _local_profile_path(project_root)
    profile_path.parent.mkdir(parents=True, exist_ok=True)
    profile = yaml.safe_load(profile_path.read_text(encoding="utf-8")) if profile_path.exists() else {}
    if not isinstance(profile, dict):
        profile = {}
    kinds = profile.setdefault("kinds", {})
    existing = kinds.get(kind)
    requested = {"class": entity_class}
    if existing == requested:
        return "already registered"
    if existing is not None and existing != requested:
        msg = f"kind {kind!r} already registered with different metadata"
        raise ValueError(msg)
    kinds[kind] = requested
    profile_path.write_text(yaml.safe_dump(profile, sort_keys=True), encoding="utf-8")
    return "registered"


def _local_profile_path(project_root: Path) -> Path:
    config_path = project_root / "science.yaml"
    if not config_path.exists():
        return project_root / "knowledge" / "profiles" / "local.yaml"
    config = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    local_path = (config.get("knowledge_profiles") or {}).get("local")
    if local_path:
        return project_root / str(local_path)
    return project_root / "knowledge" / "profiles" / "local.yaml"

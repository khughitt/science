"""Project alias mapping helpers shared by graph and validate paths."""

from __future__ import annotations

from pathlib import Path

import yaml


def load_manual_aliases(project_root: Path, *, local_profile: str) -> dict[str, str]:
    mappings_path = project_root / "knowledge" / "sources" / local_profile / "mappings.yaml"
    if not mappings_path.is_file():
        return {}

    data = yaml.safe_load(mappings_path.read_text(encoding="utf-8")) or {}
    aliases = data.get("aliases") if isinstance(data, dict) else None
    if not isinstance(aliases, dict):
        return {}

    result: dict[str, str] = {}
    for alias, canonical_id in aliases.items():
        if isinstance(alias, str) and isinstance(canonical_id, str):
            result[alias] = canonical_id
    return result

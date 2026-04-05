"""Migration script: convert project sources from old entity model to Project Model."""

from __future__ import annotations

import re
from pathlib import Path

import yaml

# Entity type renames
_TYPE_RENAMES = {
    "claim": "proposition",
    "relation_claim": "proposition",
    "evidence": "observation",
    "artifact": "data-package",
}

# ID prefix renames (same as type renames, plus paper→article)
_PREFIX_RENAMES = {
    "claim": "proposition",
    "relation_claim": "proposition",
    "evidence": "observation",
    "artifact": "data-package",
    "paper": "article",
}


def migrate_entity_sources(project_root: Path) -> dict[str, int]:
    """Migrate all entity source files in a project to the new model."""
    stats = {"migrated": 0, "skipped": 0, "errors": 0}

    for md_dir in ["doc", "specs"]:
        scan_dir = project_root / md_dir
        if not scan_dir.exists():
            continue
        for md_file in sorted(scan_dir.rglob("*.md")):
            try:
                if _migrate_file(md_file):
                    stats["migrated"] += 1
                else:
                    stats["skipped"] += 1
            except Exception:
                stats["errors"] += 1

    sources_dir = project_root / "knowledge" / "sources"
    if sources_dir.exists():
        for yaml_file in sorted(sources_dir.rglob("*.yaml")):
            try:
                if _migrate_yaml_source(yaml_file):
                    stats["migrated"] += 1
                else:
                    stats["skipped"] += 1
            except Exception:
                stats["errors"] += 1

    return stats


def _migrate_file(path: Path) -> bool:
    """Migrate a single markdown file. Returns True if changes were made."""
    text = path.read_text(encoding="utf-8")
    match = re.match(r"^---\n(.*?)\n---\n?(.*)", text, re.DOTALL)
    if not match:
        return False

    fm_text = match.group(1)
    body = match.group(2)

    try:
        fm = yaml.safe_load(fm_text)
    except yaml.YAMLError:
        return False

    if not isinstance(fm, dict):
        return False

    changed = False
    entity_type = fm.get("type", "")

    if entity_type in _TYPE_RENAMES:
        fm["type"] = _TYPE_RENAMES[entity_type]
        changed = True
    elif entity_type == "paper":
        fm["type"] = "article"
        changed = True

    entity_id = fm.get("id", "")
    if ":" in entity_id:
        prefix, slug = entity_id.split(":", 1)
        if prefix in _PREFIX_RENAMES:
            fm["id"] = f"{_PREFIX_RENAMES[prefix]}:{slug}"
            changed = True

    for field in ("related", "source_refs", "blocked_by"):
        refs = fm.get(field, [])
        if isinstance(refs, list):
            new_refs = [_rename_ref(r) for r in refs]
            if new_refs != refs:
                fm[field] = new_refs
                changed = True

    if not changed:
        return False

    new_fm_text = yaml.dump(fm, default_flow_style=False, sort_keys=False, allow_unicode=True).rstrip()
    path.write_text(f"---\n{new_fm_text}\n---\n{body}", encoding="utf-8")
    return True


def _migrate_yaml_source(path: Path) -> bool:
    """Migrate a structured YAML source file."""
    text = path.read_text(encoding="utf-8")
    new_text = text
    for old, new in _PREFIX_RENAMES.items():
        new_text = new_text.replace(f"{old}:", f"{new}:")
    for old, new in _TYPE_RENAMES.items():
        new_text = re.sub(rf"type:\s*{old}\b", f"type: {new}", new_text)
    if new_text != text:
        path.write_text(new_text, encoding="utf-8")
        return True
    return False


def _rename_ref(ref: str) -> str:
    """Rename a cross-reference prefix if it matches an old entity type."""
    if ":" not in ref:
        return ref
    prefix, slug = ref.split(":", 1)
    if prefix in _PREFIX_RENAMES:
        return f"{_PREFIX_RENAMES[prefix]}:{slug}"
    return ref

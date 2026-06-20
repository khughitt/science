from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

CANONICAL_ID_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*:[A-Za-z0-9][A-Za-z0-9_.-]*$")


def audit_identifiers(project_root: Path) -> dict[str, Any]:
    missing: list[str] = []
    invalid: list[str] = []
    for path in _markdown_paths(project_root):
        rel_path = path.relative_to(project_root).as_posix()
        frontmatter = _frontmatter(path.read_text(encoding="utf-8"))
        if not frontmatter.get("kind"):
            continue
        if "id" not in frontmatter:
            missing.append(rel_path)
            continue
        entity_id = frontmatter["id"]
        if not isinstance(entity_id, str) or not CANONICAL_ID_PATTERN.match(entity_id):
            invalid.append(rel_path)
    return {"missing_canonical_ids": missing, "invalid_canonical_ids": invalid}


def migrate_identifiers(project_root: Path, *, apply: bool) -> dict[str, Any]:
    planned_changes: list[dict[str, str]] = []
    invalid_generated_ids: list[dict[str, str]] = []
    existing_by_id = _existing_canonical_ids(project_root)
    planned_by_id: dict[str, list[str]] = {entity_id: paths.copy() for entity_id, paths in existing_by_id.items()}
    for path in _markdown_paths(project_root):
        text = path.read_text(encoding="utf-8")
        frontmatter = _frontmatter(text)
        kind = frontmatter.get("kind")
        if not isinstance(kind, str) or not kind or "id" in frontmatter:
            continue
        rel_path = path.relative_to(project_root).as_posix()
        new_id = f"{kind}:{path.stem}"
        if not CANONICAL_ID_PATTERN.match(new_id):
            invalid_generated_ids.append({"path": rel_path, "new_id": new_id})
            continue
        planned_changes.append({"path": rel_path, "new_id": new_id})
        planned_by_id.setdefault(new_id, []).append(rel_path)
    planned_ids = {change["new_id"] for change in planned_changes}
    collisions = [
        {"new_id": new_id, "paths": paths}
        for new_id, paths in sorted(planned_by_id.items())
        if len(paths) > 1 and new_id in planned_ids
    ]
    if apply and invalid_generated_ids:
        msg = f"invalid generated identifiers prevent migration: {invalid_generated_ids}"
        raise ValueError(msg)
    if apply and collisions:
        msg = f"identifier collisions prevent migration: {collisions}"
        raise ValueError(msg)
    if apply:
        for change in planned_changes:
            path = project_root / change["path"]
            _write_frontmatter_id(path, path.read_text(encoding="utf-8"), change["new_id"])
    return {
        "planned_changes": planned_changes,
        "collisions": collisions,
        "invalid_generated_ids": invalid_generated_ids,
        "applied": apply,
    }


def _existing_canonical_ids(project_root: Path) -> dict[str, list[str]]:
    existing: dict[str, list[str]] = {}
    for path in _markdown_paths(project_root):
        frontmatter = _frontmatter(path.read_text(encoding="utf-8"))
        entity_id = frontmatter.get("id")
        if isinstance(entity_id, str) and CANONICAL_ID_PATTERN.match(entity_id):
            rel_path = path.relative_to(project_root).as_posix()
            existing.setdefault(entity_id, []).append(rel_path)
    return existing


def _markdown_paths(project_root: Path) -> list[Path]:
    return [
        path
        for path in sorted(project_root.glob("**/*.md"))
        if path.relative_to(project_root).parts[:1] != ("templates",)
    ]


def _frontmatter(text: str) -> dict[str, Any]:
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---", 4)
    if end == -1:
        return {}
    try:
        value = yaml.safe_load(text[4:end]) or {}
    except yaml.YAMLError:
        return {}
    return value if isinstance(value, dict) else {}


def _write_frontmatter_id(path: Path, text: str, new_id: str) -> None:
    end = text.find("\n---", 4)
    frontmatter_lines = text[4:end].splitlines()
    insert_at = next((index + 1 for index, line in enumerate(frontmatter_lines) if line.startswith("kind:")), 0)
    frontmatter_lines.insert(insert_at, f"id: {new_id}")
    body = text[end + 4 :]
    rendered = "---\n" + "\n".join(frontmatter_lines) + "\n---" + body
    path.write_text(rendered, encoding="utf-8")

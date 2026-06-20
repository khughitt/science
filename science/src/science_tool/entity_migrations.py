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

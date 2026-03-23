"""YAML frontmatter parser for Science markdown documents."""

from __future__ import annotations

from datetime import date
from pathlib import Path

import yaml

from science_model.entities import Entity, EntityType


def parse_frontmatter(path: Path) -> tuple[dict, str] | None:
    """Parse YAML frontmatter and body from a markdown file.

    Returns (frontmatter_dict, body_text) or None if file doesn't exist.
    """
    if not path.is_file():
        return None

    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}, text

    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text

    fm = yaml.safe_load(parts[1]) or {}
    body = parts[2].strip()
    return fm, body


def _coerce_date(val: str | date | None) -> date | None:
    if val is None:
        return None
    if isinstance(val, date):
        return val
    return date.fromisoformat(str(val))


def _resolve_type(raw: str) -> EntityType:
    try:
        return EntityType(raw)
    except ValueError:
        return EntityType.UNKNOWN


def parse_entity_file(path: Path, project_slug: str) -> Entity | None:
    """Parse a markdown file into an Entity. Returns None on parse failure."""
    result = parse_frontmatter(path)
    if result is None:
        return None

    fm, body = result
    if not fm.get("type"):
        return None

    rel_path = str(path)
    # Try to make relative to project root
    for parent in path.parents:
        if (parent / "science.yaml").exists():
            rel_path = str(path.relative_to(parent))
            break

    return Entity(
        id=fm.get("id", f"{fm['type']}:{path.stem}"),
        type=_resolve_type(fm["type"]),
        title=fm.get("title", path.stem),
        status=fm.get("status"),
        project=project_slug,
        domain=None,  # computed later by domain assignment
        tags=fm.get("tags") or [],
        ontology_terms=fm.get("ontology_terms") or [],
        created=_coerce_date(fm.get("created")),
        updated=_coerce_date(fm.get("updated")),
        related=fm.get("related") or [],
        source_refs=fm.get("source_refs") or [],
        content_preview=body[:200] if body else "",
        content=body or "",
        file_path=rel_path,
        maturity=fm.get("maturity"),
        confidence=fm.get("confidence"),
        datasets=fm.get("datasets"),
    )

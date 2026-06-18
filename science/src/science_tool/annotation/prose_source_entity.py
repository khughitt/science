from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path

from science_tool.entities import (
    EntityCommandError,
    _atomic_replace_text,
    _parse_markdown_file,
    _render_markdown,
    create_entity,
    find_entity,
)


@dataclass(frozen=True)
class ProseSourceResolution:
    entity_id: str
    path: Path
    created: bool


def resolve_or_create_prose_source(
    *,
    project_root: Path,
    slug: str,
    title: str,
    source_path: Path,
    content_hash: str,
    artifact_id: str,
    today: date | None = None,
) -> ProseSourceResolution:
    ref = f"prose-source:{slug}"
    created = False
    try:
        location = find_entity(project_root, ref)
        path = location.path
    except EntityCommandError:
        result = create_entity(
            project_root=project_root,
            kind="prose-source",
            title=title,
            slug=slug,
            today=today,
            no_hints=True,
        )
        path = result.path
        created = True

    frontmatter, body = _parse_markdown_file(path)
    frontmatter["source_path"] = _display_path(project_root, source_path)
    frontmatter["content_hash"] = content_hash
    frontmatter["latest_decomposition_artifact"] = artifact_id
    frontmatter["updated"] = (today or date.today()).isoformat()
    _atomic_replace_text(path, _render_markdown(frontmatter, body))
    return ProseSourceResolution(entity_id=ref, path=path, created=created)


def _display_path(project_root: Path, source_path: Path) -> str:
    root = project_root.resolve(strict=False)
    candidate = source_path if source_path.is_absolute() else project_root / source_path
    resolved = candidate.resolve(strict=False)
    try:
        relative = resolved.relative_to(root)
    except ValueError:
        return str(source_path)
    return str(Path("~/d/science") / relative)

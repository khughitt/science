"""Project-overlay discovery and read-time merge for the commons store.

A project carries a thin overlay file (`<project>/doc/<type>/<slug>.md`) for a
commons entity. This module discovers, parses, and validates overlay files,
and merges them onto the canonical entity per the schema's `science:merge`
policy. Git `pin_version` resolution is deferred to Phase E; D1 parses the
field but the merge always uses the live canonical entity.

See docs/plans/2026-05-14-commons-overlay-merge-design.md.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from science_model.entity_schema import EntityValidationError, EntityValidator

from science_tool.commons.errors import OverlayValidationError
from science_tool.markdown_utils import parse_frontmatter

_TYPE_TO_DIR = {
    "dataset": "datasets",
    "paper": "papers",
    "topic": "topics",
    "theme": "themes",
}


def _read_markdown_body(path: Path) -> str:
    """Return the markdown body of `path`: everything after the frontmatter."""
    _, body_start = parse_frontmatter(path)
    lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
    return "".join(lines[body_start - 1 :])


@dataclass(frozen=True, slots=True)
class OverlayRecord:
    """One validated project overlay for a commons entity."""

    canonical_id: str
    type: str
    slug: str
    project: str
    project_root: Path
    overlay_path: Path
    frontmatter: dict[str, Any]
    body: str
    pin_version: str | None
    pin_effective_version: str | None


class OverlayAdapter:
    """Discover, parse, and validate overlay files in one registered project."""

    def __init__(
        self,
        project_root: Path,
        project: str,
        validator: EntityValidator | None = None,
    ) -> None:
        self._project_root = project_root
        self._project = project
        self._validator = validator or EntityValidator()

    def load(self, canonical_id: str) -> OverlayRecord | None:
        """Load the overlay for `canonical_id`, or None if no overlay file exists.

        Raises OverlayValidationError on a malformed id, unparseable frontmatter,
        a schema failure, or an `overlay_of` that does not match the path-derived
        canonical id.
        """
        type_dir, slug = self._split_id(canonical_id)
        overlay_path = self._project_root / "doc" / type_dir / f"{slug}.md"
        if not overlay_path.is_file():
            return None
        return self._build(canonical_id, overlay_path)

    def _split_id(self, canonical_id: str) -> tuple[str, str]:
        if ":" not in canonical_id:
            raise OverlayValidationError(
                self._project_root,
                canonical_id=None,
                cause=ValueError(
                    f"canonical id {canonical_id!r} is not in '<type>:<slug>' form"
                ),
            )
        type_name, slug = canonical_id.split(":", 1)
        type_dir = _TYPE_TO_DIR.get(type_name)
        if type_dir is None:
            raise OverlayValidationError(
                self._project_root,
                canonical_id=canonical_id,
                cause=ValueError(f"unknown entity type {type_name!r}"),
            )
        if not slug:
            raise OverlayValidationError(
                self._project_root,
                canonical_id=canonical_id,
                cause=ValueError(f"canonical id {canonical_id!r} has an empty slug"),
            )
        if ":" in slug:
            raise OverlayValidationError(
                self._project_root,
                canonical_id=canonical_id,
                cause=ValueError(
                    f"canonical id {canonical_id!r} has an invalid ':' in slug"
                ),
            )
        if "/" in slug or "\\" in slug:
            raise OverlayValidationError(
                self._project_root,
                canonical_id=canonical_id,
                cause=ValueError(
                    f"canonical id {canonical_id!r} has a path separator in slug"
                ),
            )
        return type_dir, slug

    def _build(self, canonical_id: str, overlay_path: Path) -> OverlayRecord:
        type_name, slug = canonical_id.split(":", 1)
        try:
            frontmatter, _ = parse_frontmatter(overlay_path)
            if not frontmatter:
                raise EntityValidationError(
                    f"{overlay_path} has no parseable frontmatter"
                )
            self._validator.validate_overlay(frontmatter)
            declared = frontmatter.get("overlay_of")
            if declared != canonical_id:
                raise EntityValidationError(
                    f"overlay_of {declared!r} does not match path-derived "
                    f"canonical id {canonical_id!r}"
                )
        except EntityValidationError as exc:
            raise OverlayValidationError(
                overlay_path, canonical_id=canonical_id, cause=exc
            ) from exc

        return OverlayRecord(
            canonical_id=canonical_id,
            type=type_name,
            slug=slug,
            project=self._project,
            project_root=self._project_root,
            overlay_path=overlay_path,
            frontmatter=frontmatter,
            body=_read_markdown_body(overlay_path),
            pin_version=frontmatter.get("pin_version") or None,
            pin_effective_version=frontmatter.get("pin_effective_version") or None,
        )

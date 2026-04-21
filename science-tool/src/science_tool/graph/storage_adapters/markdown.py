"""MarkdownAdapter — single-entity markdown with YAML frontmatter."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from science_model.source_ref import SourceRef

from science_tool.graph.storage_adapters.base import StorageAdapter


class MarkdownAdapter(StorageAdapter):
    name = "markdown"

    def __init__(self, scan_roots: list[str] | None = None) -> None:
        # Roots relative to project_root. Defaults mirror the previous MarkdownProvider.
        self._scan_roots = scan_roots or ["doc", "specs", "research/packages"]

    def discover(self, project_root: Path) -> list[SourceRef]:
        refs: list[SourceRef] = []
        for rel in self._scan_roots:
            root = project_root / rel
            if not root.is_dir():
                continue
            for path in sorted(root.rglob("*.md")):
                try:
                    rel_path = str(path.relative_to(project_root))
                except ValueError:
                    rel_path = str(path)
                refs.append(SourceRef(adapter_name=self.name, path=rel_path))
        return refs

    def load_raw(self, ref: SourceRef) -> dict[str, Any]:
        path = Path(ref.path)
        if not path.is_absolute():
            path = Path.cwd() / path
        fm, body = _parse_markdown(path)
        raw: dict[str, Any] = dict(fm)
        raw["content"] = body
        raw["file_path"] = ref.path
        # Normalize `type` → `kind` for registry dispatch while keeping `type` for
        # back-compat with existing Entity code that reads `.type`.
        if "kind" not in raw and "type" in raw:
            raw["kind"] = raw["type"]
        # Normalize `id` → `canonical_id` for registry dispatch.
        if "canonical_id" not in raw and "id" in raw:
            raw["canonical_id"] = raw["id"]
        return raw


def _parse_markdown(path: Path) -> tuple[dict[str, Any], str]:
    """Return (frontmatter_dict, body_string). Missing frontmatter → ({}, full_text)."""
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return ({}, text)
    try:
        _, fm_raw, body = text.split("---\n", 2)
    except ValueError:
        return ({}, text)
    fm = yaml.safe_load(fm_raw) or {}
    if not isinstance(fm, dict):
        return ({}, body)
    return (fm, body.lstrip("\n"))

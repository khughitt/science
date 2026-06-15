"""MarkdownAdapter — single-entity markdown with YAML frontmatter."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from science_model.source_ref import SourceRef

from science_tool.graph.source_records import MarkdownSourceDocument
from science_tool.graph.storage_adapters.base import StorageAdapter

# Anchor-surface sidecars (paper `.source.md`) live inside entity roots but are
# NOT entities; never ingest them as source records.
SIDECAR_MARKDOWN_SUFFIX = ".source.md"


class MarkdownAdapter(StorageAdapter):
    name = "markdown"
    skip_core_on_missing_identity = True

    def __init__(self, scan_roots: list[str] | None = None, virtual_files: dict[str, str] | None = None) -> None:
        # Roots relative to project_root. Defaults mirror the previous MarkdownProvider.
        self._scan_roots = scan_roots or ["entities", "research/packages"]
        self._virtual_files = dict(virtual_files or {})

    @property
    def scan_roots(self) -> tuple[str, ...]:
        return tuple(self._scan_roots)

    def discover(self, project_root: Path) -> list[SourceRef]:
        refs_by_path: dict[str, SourceRef] = {}
        for rel in self._scan_roots:
            root = project_root / rel
            if not root.is_dir():
                continue
            for path in sorted(root.rglob("*.md")):
                if path.name.endswith(SIDECAR_MARKDOWN_SUFFIX):
                    continue
                try:
                    rel_path = str(path.relative_to(project_root))
                except ValueError:
                    rel_path = str(path)
                refs_by_path[rel_path] = SourceRef(adapter_name=self.name, path=rel_path)
        for rel_path in self._virtual_files:
            if rel_path.endswith(".md") and not rel_path.endswith(SIDECAR_MARKDOWN_SUFFIX):
                refs_by_path[rel_path] = SourceRef(adapter_name=self.name, path=rel_path)
        return [refs_by_path[path] for path in sorted(refs_by_path)]

    def load_raw(self, ref: SourceRef) -> dict[str, Any]:
        if ref.path in self._virtual_files:
            fm, body = _parse_markdown_text(self._virtual_files[ref.path])
        else:
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

    def source_document(self, ref: SourceRef, raw: dict[str, Any]) -> MarkdownSourceDocument | None:
        return MarkdownSourceDocument(
            path=ref.path,
            frontmatter={key: value for key, value in raw.items() if key != "content"},
            body=str(raw.get("content") or ""),
        )


def _parse_markdown(path: Path) -> tuple[dict[str, Any], str]:
    """Return (frontmatter_dict, body_string). Missing frontmatter → ({}, full_text)."""
    return _parse_markdown_text(path.read_text(encoding="utf-8"))


def _parse_markdown_text(text: str) -> tuple[dict[str, Any], str]:
    """Return (frontmatter_dict, body_string). Missing frontmatter → ({}, full_text)."""
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

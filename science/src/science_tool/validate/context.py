from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeVar, cast

import yaml

from science_tool.paths import resolve_paths

if TYPE_CHECKING:
    from rdflib import Dataset

    from science_tool.graph.sources import ProjectSources

_T = TypeVar("_T")


class ValidateContextError(Exception):
    """Validation context could not be built from the project."""


@dataclass
class ValidateContext:
    project_root: Path
    doc_dir: Path
    specs_dir: Path
    papers_dir: Path
    provenance_dir: Path | None
    themes_dir: Path | None
    manifest: dict[str, Any]
    strict: bool
    verbose: bool
    include_all_checks: bool = False
    _text_cache: dict[tuple[Path, int], str] = field(default_factory=dict, init=False, repr=False)
    _yaml_cache: dict[tuple[Path, int], Any] = field(default_factory=dict, init=False, repr=False)
    _frontmatter_cache: dict[tuple[Path, int], dict[str, Any]] = field(default_factory=dict, init=False, repr=False)
    _resource_cache: dict[tuple[object, ...], Any] = field(default_factory=dict, init=False, repr=False)

    @classmethod
    def from_project_root(
        cls,
        project_root: Path,
        *,
        strict: bool,
        verbose: bool,
        include_all_checks: bool = False,
    ) -> "ValidateContext":
        root = project_root.resolve()
        manifest_path = root / "science.yaml"
        if not manifest_path.is_file():
            raise ValidateContextError(f"science.yaml not found at {manifest_path}")

        manifest_data = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
        if not isinstance(manifest_data, dict):
            raise ValidateContextError(f"science.yaml must contain a YAML mapping: {manifest_path}")

        try:
            paths = resolve_paths(root)
        except ValueError as exc:
            raise ValidateContextError(str(exc)) from exc
        doc_dir = paths.doc_dir
        return cls(
            project_root=root,
            doc_dir=doc_dir,
            specs_dir=paths.specs_dir,
            papers_dir=doc_dir / "papers",
            provenance_dir=doc_dir / "provenance",
            themes_dir=doc_dir / "themes",
            manifest=manifest_data,
            strict=strict,
            verbose=verbose,
            include_all_checks=include_all_checks,
        )

    def _cache_key(self, path: Path) -> tuple[Path, int]:
        absolute = path.resolve()
        return (absolute, absolute.stat().st_mtime_ns)

    def read_text_cached(self, path: Path) -> str:
        key = self._cache_key(path)
        if key not in self._text_cache:
            self._text_cache[key] = key[0].read_text(encoding="utf-8")
        return self._text_cache[key]

    def read_yaml(self, path: Path) -> Any:
        key = self._cache_key(path)
        if key not in self._yaml_cache:
            self._yaml_cache[key] = yaml.safe_load(self.read_text_cached(key[0])) or {}
        return self._yaml_cache[key]

    def frontmatter(self, path: Path) -> dict[str, Any]:
        key = self._cache_key(path)
        if key not in self._frontmatter_cache:
            self._frontmatter_cache[key] = self._parse_frontmatter(self.read_text_cached(key[0]))
        return self._frontmatter_cache[key]

    def cached_resource(self, key: tuple[object, ...], factory: Callable[[], _T]) -> _T:
        if key not in self._resource_cache:
            self._resource_cache[key] = factory()
        return cast(_T, self._resource_cache[key])

    def project_sources(
        self,
        *,
        include_commons: bool = True,
        strict_core_schema: bool = True,
        strict_identity: bool = True,
    ) -> ProjectSources:
        from science_tool.graph.sources import load_project_sources

        return self.cached_resource(
            ("project_sources", include_commons, strict_core_schema, strict_identity),
            lambda: load_project_sources(
                self.project_root,
                include_commons=include_commons,
                strict_core_schema=strict_core_schema,
                strict_identity=strict_identity,
            ),
        )

    def graph_dataset(self, graph_path: Path) -> Dataset:
        from science_tool.graph.store import dataset as dataset_module

        absolute = graph_path.resolve()
        key = ("graph_dataset", absolute, absolute.stat().st_mtime_ns)
        return self.cached_resource(key, lambda: dataset_module._load_dataset(absolute))

    @staticmethod
    def _parse_frontmatter(text: str) -> dict[str, Any]:
        if not text.startswith("---\n"):
            return {}
        try:
            _, raw, _body = text.split("---\n", 2)
        except ValueError:
            return {}
        data = yaml.safe_load(raw) or {}
        if not isinstance(data, dict):
            return {}
        return data

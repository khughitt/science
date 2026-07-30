from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeVar, cast

import yaml
from science_model.frontmatter import split_frontmatter

from science_tool.data_root import project_config_path
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
    _text_cache: dict[Path, str] = field(default_factory=dict, init=False, repr=False)
    _yaml_cache: dict[Path, Any] = field(default_factory=dict, init=False, repr=False)
    _split_cache: dict[Path, tuple[dict[str, Any], str]] = field(default_factory=dict, init=False, repr=False)
    _resource_cache: dict[tuple[object, ...], Any] = field(default_factory=dict, init=False, repr=False)

    @classmethod
    def from_project_root(
        cls,
        project_root: Path,
        *,
        strict: bool,
        verbose: bool,
        include_all_checks: bool = False,
        project_sources: ProjectSources | None = None,
    ) -> "ValidateContext":
        root = project_root.resolve()
        manifest_path = project_config_path(root)
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
        context = cls(
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
        if project_sources is not None:
            context._resource_cache[("project_sources", True)] = project_sources
        return context

    def _cache_key(self, path: Path) -> Path:
        return path.absolute()

    def read_text_cached(self, path: Path) -> str:
        key = self._cache_key(path)
        if key not in self._text_cache:
            self._text_cache[key] = key.read_text(encoding="utf-8")
        return self._text_cache[key]

    def read_yaml(self, path: Path) -> Any:
        key = self._cache_key(path)
        if key not in self._yaml_cache:
            self._yaml_cache[key] = yaml.safe_load(self.read_text_cached(key)) or {}
        return self._yaml_cache[key]

    def _split(self, path: Path) -> tuple[dict[str, Any], str]:
        # `read_text_cached` applies universal-newline translation, so `body()` is
        # LF-normalized rather than byte-verbatim (split_frontmatter's newline="" contract
        # is intentionally not honored here). That is fine for validation: body() only feeds
        # regex extraction and validation never rewrites files. Do not "fix" this to newline=""
        # without checking every read_text_cached consumer.
        key = self._cache_key(path)
        if key not in self._split_cache:
            fm, body = split_frontmatter(self.read_text_cached(key))
            self._split_cache[key] = (fm if isinstance(fm, dict) else {}, body)
        return self._split_cache[key]

    def frontmatter(self, path: Path) -> dict[str, Any]:
        return self._split(path)[0]

    def body(self, path: Path) -> str:
        return self._split(path)[1]

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
        from science_tool.graph.sources import (
            enforce_project_source_strictness,
            load_project_sources,
        )

        sources = self.cached_resource(
            ("project_sources", include_commons),
            lambda: load_project_sources(
                self.project_root,
                include_commons=include_commons,
                strict_core_schema=False,
                strict_identity=False,
            ),
        )
        return enforce_project_source_strictness(
            sources,
            strict_core_schema=strict_core_schema,
            strict_identity=strict_identity,
        )

    def graph_dataset(self, graph_path: Path) -> Dataset:
        from science_tool.graph.store import dataset as dataset_module

        absolute = graph_path.resolve()
        key = ("graph_dataset", absolute, absolute.stat().st_mtime_ns)
        return self.cached_resource(key, lambda: dataset_module._load_dataset(absolute))

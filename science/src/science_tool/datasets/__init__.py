"""Dataset adapter registry and shared search interface."""

from __future__ import annotations

from collections.abc import Callable
import logging

from science_tool.datasets._base import DatasetAdapter, DatasetResult, FileInfo

__all__ = [
    "DatasetAdapter",
    "DatasetResult",
    "FileInfo",
    "available_adapters",
    "get_adapter",
    "register",
    "search_all",
]

_ADAPTERS: dict[str, type[DatasetAdapter]] = {}


def register(name: str, cls: type[DatasetAdapter]) -> None:
    """Register a dataset adapter class by name."""
    _ADAPTERS[name] = cls


def get_adapter(name: str) -> DatasetAdapter:
    """Instantiate a registered adapter by name. Raises KeyError if unknown."""
    if name not in _ADAPTERS:
        raise KeyError(f"Unknown dataset adapter: {name!r}. Available: {sorted(_ADAPTERS)}")
    return _ADAPTERS[name]()


def available_adapters() -> list[str]:
    """Return sorted list of registered adapter names."""
    return sorted(_ADAPTERS)


def search_all(
    query: str,
    *,
    sources: list[str] | None = None,
    max_per_source: int = 10,
    on_error: Callable[[str, Exception], None] | None = None,
) -> list[DatasetResult]:
    """Fan out search across multiple adapters, merge results.

    A single adapter failing (e.g. a rate-limited source returning HTTP 429)
    must not abort the whole fan-out: the failing source is skipped and the
    other adapters' results are still returned. Each failure is reported via
    ``on_error(name, exc)`` if provided, otherwise logged as a warning, so the
    degradation is never silent.
    """
    targets = sources or list(_ADAPTERS)
    results: list[DatasetResult] = []
    for name in targets:
        adapter = get_adapter(name)
        try:
            results.extend(adapter.search(query, max_results=max_per_source))
        except Exception as exc:  # noqa: BLE001 - degrade per-source, never abort the fan-out
            if on_error is not None:
                on_error(name, exc)
            else:
                logging.getLogger(__name__).warning("dataset source %r failed: %s", name, exc)
    return results


def _auto_register() -> None:
    """Register all built-in adapters. Called on import."""
    try:
        from science_tool.datasets.zenodo import ZenodoAdapter

        register("zenodo", ZenodoAdapter)
    except ImportError:
        pass
    try:
        from science_tool.datasets.dryad import DryadAdapter

        register("dryad", DryadAdapter)
    except ImportError:
        pass
    try:
        from science_tool.datasets.geo import GEOAdapter

        register("geo", GEOAdapter)
    except ImportError:
        pass
    try:
        from science_tool.datasets.semantic_scholar import SemanticScholarAdapter

        register("semantic_scholar", SemanticScholarAdapter)
    except ImportError:
        pass


_auto_register()

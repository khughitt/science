"""Dataset adapter registry and shared search interface."""

from __future__ import annotations

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
) -> list[DatasetResult]:
    """Fan out search across multiple adapters, merge results."""
    targets = sources or list(_ADAPTERS)
    results: list[DatasetResult] = []
    for name in targets:
        adapter = get_adapter(name)
        results.extend(adapter.search(query, max_results=max_per_source))
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

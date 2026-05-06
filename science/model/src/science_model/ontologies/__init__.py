"""Ontology registry and term catalog loading."""

from __future__ import annotations

from importlib.resources import as_file, files
from pathlib import Path

import yaml

from science_model.ontologies.schema import OntologyCatalog, OntologyRegistryEntry

_PACKAGE = "science_model.ontologies"


def _package_path(relative: str) -> Path:
    """Resolve a package-relative path to an absolute path."""
    ref = files(_PACKAGE).joinpath(relative)
    with as_file(ref) as path:
        return Path(path)


def load_registry() -> list[OntologyRegistryEntry]:
    """Load the built-in ontology registry from package data."""
    registry_path = _package_path("registry.yaml")
    data = yaml.safe_load(registry_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        msg = f"Invalid ontology registry at {registry_path}"
        raise ValueError(msg)
    entries = data.get("ontologies") or []
    if not isinstance(entries, list):
        msg = f"Invalid ontology registry entries at {registry_path}"
        raise ValueError(msg)
    return [OntologyRegistryEntry.model_validate(entry) for entry in entries]


def load_catalog(entry: OntologyRegistryEntry) -> OntologyCatalog:
    """Load a specific ontology catalog from package data."""
    catalog_path = _package_path(entry.catalog_path)
    data = yaml.safe_load(catalog_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        msg = f"Invalid ontology catalog at {catalog_path}"
        raise ValueError(msg)
    return OntologyCatalog.model_validate(data)


def load_catalogs_for_names(names: list[str]) -> list[OntologyCatalog]:
    """Load ontology catalogs for declared ontology names.

    Raises ValueError for unknown ontology names.
    """
    registry = load_registry()
    registry_by_name = {entry.name: entry for entry in registry}
    available = sorted(registry_by_name.keys())

    catalogs: list[OntologyCatalog] = []
    for name in names:
        entry = registry_by_name.get(name)
        if entry is None:
            msg = f"Unknown ontology '{name}'. Available: {', '.join(available)}"
            raise ValueError(msg)
        catalogs.append(load_catalog(entry))
    return catalogs


def available_ontology_names() -> list[str]:
    """Return names of all registered ontologies."""
    return [entry.name for entry in load_registry()]


__all__ = [
    "OntologyCatalog",
    "OntologyRegistryEntry",
    "available_ontology_names",
    "load_catalog",
    "load_catalogs_for_names",
    "load_registry",
]

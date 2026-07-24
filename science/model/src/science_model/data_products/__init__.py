"""Load the packaged data-product term catalog."""

from __future__ import annotations

from importlib.resources import as_file, files
from pathlib import Path

import yaml

from science_model.data_products.schema import (
    CatalogError, DataProductCatalog, DataProductTerm, build_catalog,
)

_PACKAGE = "science_model.data_products"
_CATALOG_FILE = "catalog.yaml"


def load_catalog_from(path: Path) -> DataProductCatalog:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return build_catalog(raw)


def load_catalog() -> DataProductCatalog:
    ref = files(_PACKAGE).joinpath(_CATALOG_FILE)
    with as_file(ref) as path:                      # read WITHIN the lifetime
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    return build_catalog(raw)


__all__ = [
    "CatalogError", "DataProductCatalog", "DataProductTerm",
    "build_catalog", "load_catalog", "load_catalog_from",
]

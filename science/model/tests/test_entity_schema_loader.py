from __future__ import annotations

import pytest

from science_model.entity_schema.loader import (
    SchemaLoader,
    SchemaNotFoundError,
    _filename_for,
)
from science_model.entity_schema.profile import ProfileComponent


def test_filename_for_base() -> None:
    component = ProfileComponent(name="science-entity-base", version="1.0")
    assert _filename_for(component) == "science-entity-base-1.0.json"


def test_filename_for_mixin() -> None:
    assert _filename_for(ProfileComponent(name="dataset", version="1.0")) == "mixin-dataset-1.0.json"
    assert _filename_for(ProfileComponent(name="paper", version="1.0")) == "mixin-paper-1.0.json"


def test_filename_for_extension_flattens_dots() -> None:
    component = ProfileComponent(name="bio.rnaseq", version="1.0")
    assert _filename_for(component) == "extension-bio-rnaseq-1.0.json"


def test_loader_raises_schema_not_found_for_unknown_component() -> None:
    loader = SchemaLoader()
    with pytest.raises(SchemaNotFoundError, match="nonexistent"):
        loader.load(ProfileComponent(name="nonexistent", version="1.0"))


def test_loader_caches_lookups_per_component() -> None:
    # Cache hit returns the same dict instance without re-loading. Prime the
    # private cache directly to avoid depending on schema files that don't
    # exist yet in this task.
    loader = SchemaLoader()
    fake = {"$id": "stub.json"}
    loader._cache[("science-entity-base", "1.0")] = fake
    first = loader.load(ProfileComponent(name="science-entity-base", version="1.0"))
    second = loader.load(ProfileComponent(name="science-entity-base", version="1.0"))
    assert first is fake
    assert first is second

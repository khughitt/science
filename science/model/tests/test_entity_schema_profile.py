from __future__ import annotations

import pytest

from science_model.entity_schema.profile import (
    ProfileComponent,
    ProfileParseError,
    ProfileString,
    parse_profile,
)


def test_parse_minimal_base_only() -> None:
    parsed = parse_profile("science-entity-base/1.0")
    assert parsed.base == ProfileComponent(name="science-entity-base", version="1.0")
    assert parsed.mixin is None
    assert parsed.extensions == ()


def test_parse_base_plus_dataset_mixin() -> None:
    parsed = parse_profile("science-entity-base/1.0+dataset/1.0")
    assert parsed.base.name == "science-entity-base"
    assert parsed.mixin == ProfileComponent(name="dataset", version="1.0")
    assert parsed.extensions == ()


def test_parse_base_plus_mixin_plus_extension() -> None:
    parsed = parse_profile("science-entity-base/1.0+dataset/1.0+bio.rnaseq/1.0")
    assert parsed.mixin.name == "dataset"
    assert parsed.extensions == (ProfileComponent(name="bio.rnaseq", version="1.0"),)


def test_parse_multiple_extensions_preserves_order() -> None:
    parsed = parse_profile(
        "science-entity-base/1.0+dataset/1.0+bio.rnaseq/1.0+bio.scrna/1.0"
    )
    assert [ext.name for ext in parsed.extensions] == ["bio.rnaseq", "bio.scrna"]


def test_parse_rejects_missing_base() -> None:
    with pytest.raises(ProfileParseError, match="must start with science-entity-base"):
        parse_profile("dataset/1.0")


def test_parse_rejects_missing_version() -> None:
    with pytest.raises(ProfileParseError, match="missing version"):
        parse_profile("science-entity-base+dataset/1.0")


def test_parse_rejects_empty_string() -> None:
    with pytest.raises(ProfileParseError, match="empty"):
        parse_profile("")


def test_parse_rejects_unknown_mixin_position() -> None:
    # A second base-name in mixin slot is invalid.
    with pytest.raises(ProfileParseError, match="mixin"):
        parse_profile("science-entity-base/1.0+science-entity-base/1.0")


def test_render_round_trips() -> None:
    raw = "science-entity-base/1.0+dataset/1.0+bio.rnaseq/1.0"
    assert parse_profile(raw).render() == raw

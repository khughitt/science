from __future__ import annotations

import pytest

from science_model.entity_schema.loader import SchemaLoader
from science_model.entity_schema.profile import ProfileComponent
from science_model.entity_schema.validator import EntityValidationError, EntityValidator


def _base_collection(**extra: object) -> dict[str, object]:
    return {
        "schema_profile": "science-entity-base/1.0+dataset/1.0+bio.reference_graph/1.0",
        "id": "dataset:mondo",
        "type": "dataset",
        "title": "MONDO disease ontology reference graph",
        "version": "1.0.0",
        "created": "2026-05-31",
        "updated": "2026-05-31",
        "datapackage": "datapackage.yaml",
        "origin": "external",
        "tier": "use-now",
        "source_class": "reference",
        "access": {"level": "public", "verified": True},
        "graph_resource": "graph",
        "graph_format": "rdf_ntriples",
        "member_key_space": {
            "kind": "curie",
            "prefixes": ["MONDO"],
            "resolution_status": "resolved",
        },
        "node_index_resource": "nodes",
        "member_count": 2,
    } | extra


def _base_member(**extra: object) -> dict[str, object]:
    return {
        "schema_profile": "science-entity-base/1.0+dataset/1.0+bio.reference_graph.member/1.0",
        "id": "dataset:mondo-0005148",
        "type": "dataset",
        "title": "MONDO:0005148",
        "version": "1.0.0",
        "created": "2026-05-31",
        "updated": "2026-05-31",
        "datapackage": "virtual:member-of",
        "origin": "derived",
        "tier": "use-now",
        "source_class": "reference",
        "parent_dataset": "dataset:mondo",
        "derivation": {
            "kind": "member_of",
            "parent_dataset": "dataset:mondo",
            "member_key": "MONDO:0005148",
        },
        "member_kind": "term",
        "label": "multiple myeloma",
        "status": "active",
    } | extra


def test_loader_resolves_reference_graph_schema() -> None:
    schema = SchemaLoader().load(ProfileComponent(name="bio.reference_graph", version="1.0"))
    assert schema["$id"].endswith("extension-bio-reference_graph-1.0.json")


def test_loader_resolves_reference_graph_member_schema() -> None:
    schema = SchemaLoader().load(ProfileComponent(name="bio.reference_graph.member", version="1.0"))
    assert schema["$id"].endswith("extension-bio-reference_graph-member-1.0.json")


def test_minimal_reference_graph_collection_validates() -> None:
    EntityValidator().validate(_base_collection())


@pytest.mark.parametrize(
    "field",
    [
        "graph_resource",
        "graph_format",
        "member_key_space",
        "node_index_resource",
        "member_count",
    ],
)
def test_reference_graph_requires_collection_fields(field: str) -> None:
    entity = _base_collection()
    del entity[field]
    with pytest.raises(EntityValidationError, match=field):
        EntityValidator().validate(entity)


def test_reference_graph_rejects_unknown_graph_format() -> None:
    with pytest.raises(EntityValidationError, match="graph_format"):
        EntityValidator().validate(_base_collection(graph_format="obo"))


def test_reference_graph_accepts_obograph_json_format() -> None:
    EntityValidator().validate(_base_collection(graph_format="obograph_json"))


@pytest.mark.parametrize(
    ("member_key_space", "match"),
    [
        (
            {"kind": "gene", "prefixes": ["MONDO"], "resolution_status": "resolved"},
            "kind",
        ),
        (
            {"kind": "curie", "prefixes": ["MONDO"], "resolution_status": "pending"},
            "resolution_status",
        ),
        (
            {"kind": "curie", "prefixes": [], "resolution_status": "resolved"},
            "prefixes",
        ),
        (
            {
                "kind": "curie",
                "prefixes": ["MONDO", "MONDO"],
                "resolution_status": "resolved",
            },
            "prefixes",
        ),
        (
            {"kind": "curie", "prefixes": [""], "resolution_status": "resolved"},
            "prefixes",
        ),
        (
            {"kind": "curie", "prefixes": [1], "resolution_status": "resolved"},
            "prefixes",
        ),
        (
            {
                "kind": "curie",
                "prefixes": ["MONDO"],
                "resolution_status": "resolved",
                "example": "MONDO:0005148",
            },
            "example",
        ),
    ],
)
def test_reference_graph_rejects_invalid_member_key_space(
    member_key_space: dict[str, object],
    match: str,
) -> None:
    entity = _base_collection(member_key_space=member_key_space)
    with pytest.raises(EntityValidationError, match=match):
        EntityValidator().validate(entity)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("graph_resource", ""),
        ("node_index_resource", ""),
        ("edge_resource", ""),
    ],
)
def test_reference_graph_rejects_empty_resource_names(field: str, value: str) -> None:
    with pytest.raises(EntityValidationError, match=field):
        EntityValidator().validate(_base_collection(**{field: value}))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("member_count", 0),
        ("edge_count", -1),
    ],
)
def test_reference_graph_rejects_invalid_counts(field: str, value: int) -> None:
    with pytest.raises(EntityValidationError, match=field):
        EntityValidator().validate(_base_collection(**{field: value}))


@pytest.mark.parametrize("field", ["member_kind", "label", "status"])
def test_reference_graph_member_requires_fields(field: str) -> None:
    entity = _base_member()
    del entity[field]
    with pytest.raises(EntityValidationError, match=field):
        EntityValidator().validate(entity)


def test_reference_graph_member_validates_without_scalar_member_key_duplicate() -> None:
    EntityValidator().validate(_base_member())


def test_reference_graph_member_rejects_top_level_member_key_duplicate() -> None:
    with pytest.raises(EntityValidationError, match="member_key"):
        EntityValidator().validate(_base_member(member_key="MONDO:0005148"))


def test_reference_graph_member_rejects_invalid_status() -> None:
    with pytest.raises(EntityValidationError, match="status"):
        EntityValidator().validate(_base_member(status="obsolete"))


def test_reference_graph_member_rejects_duplicate_replaced_by() -> None:
    with pytest.raises(EntityValidationError, match="replaced_by"):
        EntityValidator().validate(
            _base_member(replaced_by=["MONDO:0000001", "MONDO:0000001"])
        )

from science_model.identity import EntityScope, ExternalId


def test_external_id_structured_round_trip() -> None:
    identity = ExternalId(
        source="HGNC",
        id="3527",
        curie="HGNC:3527",
        provenance="manual",
    )
    assert identity.curie == "HGNC:3527"
    assert identity.source == "HGNC"


def test_entity_scope_values_are_explicit() -> None:
    assert EntityScope.PROJECT == "project"
    assert EntityScope.SHARED == "shared"

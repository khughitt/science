from science_model.profiles.schema import RelationKind


def test_relation_kind_restricts_endpoints() -> None:
    relation = RelationKind(
        name="tests",
        predicate="sci:tests",
        source_kinds=["task", "experiment"],
        target_kinds=["hypothesis", "question"],
        layer="layer/core",
    )
    assert "hypothesis" in relation.target_kinds
    assert relation.layer == "layer/core"

from science_model.entities import EntityClass

from science_tool.graph.entity_registry import EntityRegistry


def test_construct_and_outcome_are_reference_kinds():
    r = EntityRegistry.with_core_types()
    for kind in ("construct", "outcome"):
        assert r.kind_class(kind) == EntityClass.REFERENCE

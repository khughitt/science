from __future__ import annotations


def test_entity_schema_module_importable() -> None:
    import science_model.entity_schema as es

    assert hasattr(es, "__all__")
    assert isinstance(es.__all__, list)

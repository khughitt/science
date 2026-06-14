from __future__ import annotations


def test_synthesis_is_a_local_entity_kind() -> None:
    from science_tool.refs import _LOCAL_ENTITY_KINDS
    from science_tool.styles import ENTITY_KIND_STYLES
    from science_tool.validate.checks.cross_references import LOCAL_KINDS

    assert "synthesis" in _LOCAL_ENTITY_KINDS
    assert "synthesis" in LOCAL_KINDS
    assert "synthesis" in ENTITY_KIND_STYLES


def test_book_is_a_local_entity_kind() -> None:
    from science_tool.refs import _LOCAL_ENTITY_KINDS
    from science_tool.validate.checks.cross_references import LOCAL_KINDS

    assert "book" in _LOCAL_ENTITY_KINDS
    assert "book" in LOCAL_KINDS


def test_discover_ancestor_registry_prefers_entities(tmp_path) -> None:
    from science_tool.verdict.cli import _discover_ancestor_registry

    (tmp_path / "entities").mkdir()
    reg = tmp_path / "entities" / "claim-registry.yaml"
    reg.write_text("version: 1\nclaims: []\n", encoding="utf-8")
    nested = tmp_path / "entities" / "syntheses" / "0001-x.md"
    nested.parent.mkdir(parents=True)
    nested.write_text("x", encoding="utf-8")
    assert _discover_ancestor_registry(nested) == reg

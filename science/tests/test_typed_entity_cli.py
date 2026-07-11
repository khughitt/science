import inspect

from science_tool import entities as ent
from science_tool import typed_entity_cli as tec


def test_typed_entity_adapters_present():
    for name in (
        "create_typed_entity",
        "show_typed_entity",
        "list_typed_entities",
        "ENTITY_LIST_TITLES",
        "build_origin_frontmatter",
        "emit_entity_show",
        "emit_entity_warnings",
    ):
        assert hasattr(tec, name), name
    assert tec.ENTITY_LIST_TITLES["hypothesis"] == "Hypotheses"


def test_entities_domain_module_stays_click_free():
    # Task 1 must not push CLI code into the domain module.
    assert "import click" not in inspect.getsource(ent)

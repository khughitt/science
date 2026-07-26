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


def test_emit_entity_warnings_summarizes_preexisting_by_default(capsys):
    """The central lever for the write-audit-leak fix (slice 1b-3 WL).

    Every typed-entity `create` command (discussions/hypotheses/interpretations/
    propositions/questions/evidence-lines) routes through `create_typed_entity` ->
    `emit_entity_warnings`, so fixing it here is what makes their EXEMPTIONS
    classification ("Echoes exactly one 'Created <id> at <path>' line plus the
    created entity's own validation warnings") actually true.
    """
    own = ["forward reference to hypothesis:h01 not yet resolved"]
    preexisting = [f"pre-existing audit failure: check {i} on source:{i}: detail" for i in range(50)]

    tec.emit_entity_warnings(own + preexisting)
    out = capsys.readouterr().out
    assert "WARNING: forward reference" in out
    assert "pre-existing audit failure:" not in out
    assert "50 pre-existing project audit warning" in out
    assert out.count("\n") == 2  # one own WARNING line + one summary note

    tec.emit_entity_warnings(own + preexisting, show_preexisting=True)
    shown = capsys.readouterr().out
    assert shown.count("pre-existing audit failure:") == 50
    assert "WARNING: forward reference" in shown

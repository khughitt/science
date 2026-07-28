"""A top-level frontmatter field that materializes no triples is an ERROR (fb-2026-07-11-017).

The graph reads supersession/amendment from a `relations:` entry with the predicate, never
from a top-level `supersedes:`/`amends:` key. Such a key looks authoritative and produces
ZERO triples, silently -- and big-picture then derives a wrong `provenance_coverage`.

S2 retired `workflow-run.supersedes`; there is no legitimate top-level use, so this check has
no exemptions.
"""

from __future__ import annotations

from pathlib import Path

from science_tool.validate.checks.materialization import check_non_materializing_fields
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Severity


def _entity(root: Path, rel: str, *, entity_id: str, kind: str, extra: str) -> None:
    """Seed one entity markdown file. `extra` is raw frontmatter lines (already newline-terminated)."""
    path = root / "entities" / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f'---\nid: "{entity_id}"\nkind: {kind}\ntitle: "T"\nstatus: "active"\n{extra}---\n\nBody.\n',
        encoding="utf-8",
    )


def _results(root: Path) -> list:
    (root / "science.yaml").write_text("name: fixture\nprofile: research\n", encoding="utf-8")
    ctx = ValidateContext.from_project_root(root, strict=False, verbose=False)
    return list(check_non_materializing_fields(ctx))


def test_top_level_supersedes_on_interpretation_is_an_error(tmp_path: Path) -> None:
    _entity(
        tmp_path, "interpretations/0001-x.md",
        entity_id="interpretation:0001-x", kind="interpretation",
        extra="supersedes: interpretation:0000-y\n",
    )
    results = _results(tmp_path)
    assert [r.severity for r in results] == [Severity.ERROR]
    msg = results[0].message
    # every required element (design §2)
    assert "interpretation:0001-x" in msg     # the entity id
    assert "top-level 'supersedes:'" in msg   # the authored key, not just the predicate
    assert "relations:" in msg                # the replacement form
    assert "sci:supersedes" in msg            # the predicate
    assert "target" in msg and "<target-id>" in msg   # current field name, schematic target
    assert "interpretation:0000-y" not in msg  # must NOT echo the authored value
    assert results[0].rule_id == "materialization.non-materializing-field"


def test_top_level_amends_on_interpretation_is_an_error(tmp_path: Path) -> None:
    _entity(
        tmp_path, "interpretations/0001-x.md",
        entity_id="interpretation:0001-x", kind="interpretation",
        extra="amends: interpretation:0000-y\n",
    )
    results = _results(tmp_path)
    assert [r.severity for r in results] == [Severity.ERROR]
    assert "interpretation:0001-x" in results[0].message
    assert "top-level 'amends:'" in results[0].message
    assert "sci:amends" in results[0].message


def test_relations_form_is_accepted(tmp_path: Path) -> None:
    _entity(
        tmp_path, "interpretations/0001-x.md",
        entity_id="interpretation:0001-x", kind="interpretation",
        extra="relations:\n  - predicate: sci:supersedes\n    target: interpretation:0000-y\n",
    )
    assert _results(tmp_path) == []


def test_supersedes_on_workflow_run_is_an_error(tmp_path: Path) -> None:
    """S2 retired the field: it materialized no triple and no consumer read it."""
    _entity(
        tmp_path, "workflow-runs/0001-x.md",
        entity_id="workflow-run:0001-x", kind="workflow-run",
        extra="supersedes: workflow-run:0000-y\n",
    )
    results = _results(tmp_path)
    assert [r.severity for r in results] == [Severity.ERROR]
    assert "workflow-run:0001-x" in results[0].message


def test_amends_on_workflow_run_is_an_error(tmp_path: Path) -> None:
    """Top-level `amends:` is independently and unconditionally rejected; there are no exemptions."""
    _entity(
        tmp_path, "workflow-runs/0001-x.md",
        entity_id="workflow-run:0001-x", kind="workflow-run",
        extra="amends: workflow-run:0000-y\n",
    )
    results = _results(tmp_path)
    assert [r.severity for r in results] == [Severity.ERROR]
    assert "sci:amends" in results[0].message


def test_malformed_non_string_kind_still_flags_and_does_not_crash(tmp_path: Path) -> None:
    """A list/mapping `kind` must still receive its rule, and the check must not error out."""
    _entity(
        tmp_path, "interpretations/0001-x.md",
        entity_id="interpretation:0001-x", kind="[oops]",  # YAML flow sequence -> unhashable list
        extra="supersedes: interpretation:0000-y\n",
    )
    results = _results(tmp_path)
    assert [r.severity for r in results] == [Severity.ERROR]
    assert results[0].rule_id == "materialization.non-materializing-field"


def test_null_valued_supersedes_is_an_error(tmp_path: Path) -> None:
    """Guards against `fm.get(key) is None`-style detection: presence is the defect, not value."""
    _entity(
        tmp_path, "interpretations/0001-x.md",
        entity_id="interpretation:0001-x", kind="interpretation",
        extra="supersedes: null\n",
    )
    assert [r.severity for r in _results(tmp_path)] == [Severity.ERROR]


def test_empty_list_supersedes_is_an_error(tmp_path: Path) -> None:
    _entity(
        tmp_path, "interpretations/0001-x.md",
        entity_id="interpretation:0001-x", kind="interpretation",
        extra="supersedes: []\n",
    )
    assert [r.severity for r in _results(tmp_path)] == [Severity.ERROR]


# The remediation must be one the graph will actually accept. After S2, every kind that can reach
# `superseded` can author a `sci:supersedes` edge; the remaining 32 non-supersedable kinds cannot.
# Prescribing the relations: form to them would send an author to a dead end whose only exit was
# deleting the authored lineage.


def test_inadmissible_kind_is_not_told_to_author_the_relation(tmp_path: Path) -> None:
    """`question` cannot be a `sci:supersedes` source, so the relations: form must NOT be prescribed."""
    _entity(
        tmp_path, "questions/0001-x.md",
        entity_id="question:0001-x", kind="question",
        extra="supersedes: question:0000-y\n",
    )
    results = _results(tmp_path)
    assert [r.severity for r in results] == [Severity.ERROR]
    msg = results[0].message
    assert "question:0001-x" in msg
    assert "top-level 'supersedes:'" in msg
    # The dead-end prescription must be gone...
    assert "relations:" not in msg
    assert "<target-id>" not in msg
    # ...replaced by the reason it cannot be authored at all.
    assert "cannot" in msg
    assert "question" in msg
    assert results[0].rule_id == "materialization.non-materializing-field"


def test_admissible_kind_still_gets_the_relations_prescription(tmp_path: Path) -> None:
    """The kind-awareness must not weaken the message where the edge IS authorable."""
    _entity(
        tmp_path, "specs/0001-x.md",
        entity_id="spec:0001-x", kind="spec",
        extra="supersedes: spec:0000-y\n",
    )
    results = _results(tmp_path)
    assert [r.severity for r in results] == [Severity.ERROR]
    assert "relations:" in results[0].message
    assert "sci:supersedes" in results[0].message


def test_amends_on_a_kind_that_cannot_author_it(tmp_path: Path) -> None:
    """`amends` admits only the 6 conclusion kinds -- `hypothesis` is not one of them, even
    though `hypothesis` CAN author `supersedes`. The two relations are judged independently."""
    _entity(
        tmp_path, "hypotheses/0001-x.md",
        entity_id="hypothesis:0001-x", kind="hypothesis",
        extra="amends: hypothesis:0000-y\n",
    )
    results = _results(tmp_path)
    assert [r.severity for r in results] == [Severity.ERROR]
    msg = results[0].message
    assert "relations:" not in msg
    assert "cannot" in msg


def test_malformed_kind_keeps_the_schematic_prescription(tmp_path: Path) -> None:
    """A non-string kind cannot be tested for admissibility. It must still flag, and must not
    claim the kind 'cannot' author the edge -- that would be an assertion we cannot support."""
    _entity(
        tmp_path, "interpretations/0001-x.md",
        entity_id="interpretation:0001-x", kind="[oops]",
        extra="supersedes: interpretation:0000-y\n",
    )
    results = _results(tmp_path)
    assert [r.severity for r in results] == [Severity.ERROR]
    assert "relations:" in results[0].message


def test_clean_entity_yields_nothing(tmp_path: Path) -> None:
    """Non-vacuity guard: with no offending key, the check is silent -- so the ERROR cases
    prove it can fire, not that it fires on everything."""
    _entity(
        tmp_path, "interpretations/0001-x.md",
        entity_id="interpretation:0001-x", kind="interpretation",
        extra="",
    )
    assert _results(tmp_path) == []

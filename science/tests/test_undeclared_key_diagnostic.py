from __future__ import annotations

import ast
import inspect
import textwrap
from pathlib import Path

import pytest
import yaml

from science_model.entities import Entity
from science_model.entity_schema import PROJECT_MIXIN_NAMES
from science_model.source_contracts import StructuredEntitySource
from science_tool.graph import migrate as _migrate
from science_tool.graph.entity_registry import EntityRegistry
from science_tool.graph.migrate import (
    REFERENCE_FIELD_NAMES,
    _audit_entity,
    _audit_undeclared_reference_keys,
    _declared,
    _format_kinds,
    _stringify_extra_value,
    audit_project_sources,
)
from science_tool.graph.reference_resolution import ReferenceResolver
from science_tool.graph.sources import ProjectSources, load_project_sources


def _write_project(root: Path, *, pinned: bool) -> None:
    root.mkdir(parents=True, exist_ok=True)
    pin = "entity_schema_version: 2\n" if pinned else ""
    (root / "science.yaml").write_text(f"name: demo\n{pin}", encoding="utf-8")
    hyp = root / "entities" / "hypotheses" / "h1.md"
    hyp.parent.mkdir(parents=True)
    hyp.write_text(
        '---\nid: "hypothesis:h1"\nkind: "hypothesis"\ntitle: "H1"\nstatus: "active"\n'
        'related: []\nsource_refs: []\ncreated: "2026-03-12"\nupdated: "2026-03-12"\n'
        "---\nBody.\n",
        encoding="utf-8",
    )


def test_project_sources_has_strict_schema_kinds_field_default() -> None:
    field = ProjectSources.model_fields["strict_schema_kinds"]
    assert field.get_default(call_default_factory=True) == frozenset()


def test_unpinned_project_strict_schema_kinds_is_empty(tmp_path: Path) -> None:
    _write_project(tmp_path / "p", pinned=False)
    assert load_project_sources(tmp_path / "p").strict_schema_kinds == frozenset()


def test_pinned_project_strict_schema_kinds_is_mixin_names(tmp_path: Path) -> None:
    _write_project(tmp_path / "p", pinned=True)
    assert load_project_sources(tmp_path / "p").strict_schema_kinds == PROJECT_MIXIN_NAMES


def test_structured_source_PRESERVES_an_unknown_reference_key() -> None:
    # Inverted deliberately (schema-closure mechanism, Task 4). The contract is `extra="allow"`
    # so unknown keys survive to be REFUSED by the composed schema on a closed kind -- and, on an
    # open kind, to be REPORTED by the undeclared_key audit. The previous assertion pinned the
    # silence, not the correctness: a `method:` key on a kind that does not declare it is exactly
    # what the diagnostic is for, and it was unreportable only because the row was stripped first.
    record = StructuredEntitySource.model_validate(
        {"canonical_id": "workflow:w", "title": "W", "kind": "workflow", "method": "phantom"}
    )
    assert record.model_extra == {"kind": "workflow", "method": "phantom"}


def test_integration_unpinned_workflow_method_warns_not_fails(tmp_path: Path) -> None:
    root = tmp_path / "p"
    root.mkdir()
    (root / "science.yaml").write_text("name: demo\n", encoding="utf-8")  # unpinned
    wf = root / "entities" / "workflows" / "w1.md"
    wf.parent.mkdir(parents=True)
    wf.write_text(
        '---\nid: "workflow:w1"\nkind: "workflow"\ntitle: "W1"\n'
        'method: "w1-snakemake"\nrelated: []\nsource_refs: []\n'
        'created: "2026-03-12"\nupdated: "2026-03-12"\n---\nBody.\n',
        encoding="utf-8",
    )
    verdict = audit_project_sources(load_project_sources(root))
    unresolved = [r for r in verdict.rows if r["check"] == "unresolved_reference" and r["field"] == "method"]
    undeclared = [r for r in verdict.rows if r["check"] == "undeclared_key"]
    assert unresolved == []  # no phantom
    assert len(undeclared) == 1 and undeclared[0]["status"] == "warn"
    assert verdict.status != "failed"  # WARN does not block


_BASE = {
    "project": "demo",
    "ontology_terms": [],
    "related": [],
    "source_refs": [],
    "content_preview": "",
    "file_path": "entities/x/x.md",
}


def _entity(kind: str, **extra) -> Entity:
    cls = EntityRegistry.with_core_types().resolve(kind)
    raw = {"id": f"{kind}:x", "canonical_id": f"{kind}:x", "kind": kind, "title": "X", **_BASE, **extra}
    return cls.model_validate(raw)


def _bare_entity(**extra) -> Entity:
    # A base Entity does not declare blocked_by, so a blocked_by here is a stray extra key.
    raw = {"id": "thing:x", "canonical_id": "thing:x", "kind": "thing", "title": "X", **_BASE, **extra}
    return Entity.model_validate(raw)


def _declaring_kinds() -> dict[str, tuple[str, ...]]:
    reg = EntityRegistry.with_core_types()
    return {
        field: tuple(k for k, c in reg.registered_kinds().items() if field in c.model_fields)
        for field in REFERENCE_FIELD_NAMES
    }


def _audit(entity: Entity, *, strict: frozenset[str] = frozenset()) -> list:
    resolver = ReferenceResolver.from_entities([entity])
    return _audit_entity(
        entity,
        resolver,
        ext_prefixes=frozenset(),
        peer_ids=frozenset(),
        strict_schema_kinds=strict,
        declaring_kinds=_declaring_kinds(),
    )


def _cases() -> list[tuple[str, Entity]]:
    # All six subset-declared fields, each on a kind that does not declare it.
    return [
        ("method", _entity("workflow", method="phantom")),
        ("workflow", _entity("task", workflow="phantom")),
        ("audits", _entity("task", audits="phantom")),
        ("chain", _entity("task", chain=["phantom"])),
        ("proposition_refs", _entity("task", proposition_refs=["phantom"])),
        ("blocked_by", _bare_entity(blocked_by=["phantom"])),
    ]


@pytest.mark.parametrize("field,entity", _cases())
def test_gate_and_warn_for_each_misplaced_field(field: str, entity: Entity) -> None:
    rows = _audit(entity)
    phantom = [r for r in rows if r["check"] == "unresolved_reference" and r["field"] == field]
    warns = [r for r in rows if r["check"] == "undeclared_key" and r["field"] == field]
    assert phantom == []  # zero phantom failures
    assert len(warns) == 1  # exactly one WARN


def test_declared_reads_undeclared_field_as_default() -> None:
    workflow = _entity("workflow", method="phantom")  # ProjectEntity: no `method`
    assert _declared(workflow, "method", "DFLT") == "DFLT"


def test_declared_reads_declared_field_as_value() -> None:
    step = _entity("workflow-step", method="m1")  # WorkflowStepEntity declares `method`
    assert _declared(step, "method", "DFLT") == "m1"


def test_gate_preserves_genuine_unresolved_on_declared_field() -> None:
    # Regression: the gate must NOT stop auditing a field the kind DOES declare.
    step = _entity("workflow-step", method="does-not-exist")
    rows = _audit(step)
    assert any(r["check"] == "unresolved_reference" and r["field"] == "method" for r in rows)


def test_resolvable_declared_method_yields_no_rows() -> None:
    # A resolvable method reference produces neither a phantom nor a WARN.
    method_target = _entity("method")  # canonical_id "method:x"
    step = _entity("workflow-step", method="method:x")
    resolver = ReferenceResolver.from_entities([step, method_target])
    rows = _audit_entity(
        step,
        resolver,
        ext_prefixes=frozenset(),
        peer_ids=frozenset(),
        strict_schema_kinds=frozenset(),
        declaring_kinds=_declaring_kinds(),
    )
    assert [r for r in rows if r["field"] == "method"] == []


def test_undeclared_key_full_row_exact() -> None:
    entity = _entity("workflow", method="phantom")
    rows = _audit_undeclared_reference_keys(entity, declaring_kinds=_declaring_kinds())
    assert rows == [
        {
            "check": "undeclared_key",
            "status": "warn",
            "source": "workflow:x",
            "field": "method",
            "target": "phantom",
            "details": (
                "`method` is not a declared field of kind `workflow`; it is declared by "
                "`workflow-step`. It is an unvouched extra key on this kind, not wired into "
                "the graph — move it to the owning kind or remove it."
            ),
        }
    ]


def test_undeclared_key_ignores_non_reference_extra_key() -> None:
    entity = _entity("workflow", custom_note="hi")
    assert _audit_undeclared_reference_keys(entity, declaring_kinds=_declaring_kinds()) == []


def test_strict_schema_kind_suppresses_undeclared_key() -> None:
    entity = _entity("hypothesis", status="active", method="phantom")
    rows = _audit(entity, strict=frozenset({"hypothesis"}))
    assert [r for r in rows if r["check"] == "undeclared_key"] == []


def test_unvalidated_kind_on_pinned_project_still_warns() -> None:
    # workflow is NOT in PROJECT_MIXIN_NAMES, so a pinned project still warns.
    entity = _entity("workflow", method="phantom")
    rows = _audit(entity, strict=frozenset({"hypothesis"}))
    assert [r for r in rows if r["check"] == "undeclared_key"][0]["field"] == "method"


def test_stringify_and_format_kinds() -> None:
    assert _stringify_extra_value("a") == "a"
    assert _stringify_extra_value(["b", "a"]) == "b, a"
    assert _stringify_extra_value(("b", "a")) == "b, a"  # tuple
    assert _stringify_extra_value({"y": 1, "x": 2}) == '{"x": 2, "y": 1}'
    assert _stringify_extra_value(7) == "7"
    assert _format_kinds(("workflow-run", "workflow-step")) == "`workflow-run`, `workflow-step`"


def test_undeclared_key_formats_nested_yaml_native_values() -> None:
    method = yaml.safe_load(
        """
        alpha:
          - 2026-07-16
          - nested:
              at: 2026-07-16T12:34:56+00:00
              enabled: true
        zeta: null
        """
    )
    entity = _entity("workflow", method=method)

    rows = _audit_undeclared_reference_keys(entity, declaring_kinds=_declaring_kinds())

    assert len(rows) == 1
    assert rows[0]["status"] == "warn"
    assert rows[0]["target"] == (
        '{"alpha": ["2026-07-16", {"nested": {"at": "2026-07-16T12:34:56+00:00", '
        '"enabled": true}}], "zeta": null}'
    )


def _audit_entity_ast() -> ast.FunctionDef:
    src = textwrap.dedent(inspect.getsource(_migrate._audit_entity))
    return next(n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.FunctionDef))


def _declared_field_names(fn: ast.FunctionDef) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(fn):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "_declared"
            and len(node.args) >= 2
            and isinstance(node.args[0], ast.Name)
            and node.args[0].id == "entity"  # first arg must be the entity
            and isinstance(node.args[1], ast.Constant)
            and isinstance(node.args[1].value, str)
        ):
            names.add(node.args[1].value)
    return names


def _audited_field_names(fn: ast.FunctionDef) -> set[str]:
    """Top-level prefixes of the field_name label of every audit call.

    Fails closed: a non-literal / missing label raises, so an unverifiable audit
    site cannot slip through. Accepts both positional index 1 and keyword field_name.
    """
    audit_fns = {"_audit_reference", "_audit_dataset_reference"}
    names: set[str] = set()
    for node in ast.walk(fn):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in audit_fns:
            label = node.args[1] if len(node.args) >= 2 else None
            for kw in node.keywords:
                if kw.arg == "field_name":
                    label = kw.value
            assert isinstance(label, ast.Constant) and isinstance(label.value, str), (
                f"audit call with a non-literal field_name at line {node.lineno}"
            )
            names.add(label.value.split(".")[0])
    return names


def _assert_no_direct_audited_field_access(fn: ast.FunctionDef) -> None:
    for node in ast.walk(fn):
        if (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == "entity"
            and node.attr in _migrate._AUDITED_REFERENCE_FIELDS
        ):
            raise AssertionError(f"direct entity.{node.attr} at line {node.lineno}; use _declared")


def test_no_bare_entity_getattr_in_audit_entity() -> None:
    fn = _audit_entity_ast()
    for node in ast.walk(fn):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "getattr"
            and node.args
            and isinstance(node.args[0], ast.Name)
            and node.args[0].id == "entity"
        ):
            raise AssertionError(f"bare getattr(entity, ...) at line {node.lineno}; use _declared")


def test_no_direct_audited_field_access_in_audit_entity() -> None:
    _assert_no_direct_audited_field_access(_audit_entity_ast())


def test_every_audited_field_is_gated() -> None:
    fn = _audit_entity_ast()
    assert _audited_field_names(fn) <= _declared_field_names(fn)


def test_declared_reads_match_named_constant() -> None:
    fn = _audit_entity_ast()
    assert _declared_field_names(fn) == set(_migrate._AUDITED_REFERENCE_FIELDS)


def test_drift_guard_rejects_a_bare_getattr_bypass() -> None:
    src = textwrap.dedent(
        '''
        def _audit_entity(entity, resolver):
            rows = []
            for t in getattr(entity, "foo", []):
                rows.extend(_audit_reference(entity, "foo", t, resolver))
            return rows
        '''
    )
    fn = next(n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.FunctionDef))
    assert not (_audited_field_names(fn) <= _declared_field_names(fn))


def test_drift_guard_rejects_a_keyword_form_bypass() -> None:
    src = textwrap.dedent(
        '''
        def _audit_entity(entity, resolver):
            return _audit_reference(entity, field_name="foo", target=entity.foo, resolver=resolver)
        '''
    )
    fn = next(n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.FunctionDef))
    # "foo" is audited (via keyword field_name) but not gated -> caught.
    assert not (_audited_field_names(fn) <= _declared_field_names(fn))


def test_drift_guard_rejects_same_label_direct_attribute_bypass() -> None:
    src = textwrap.dedent(
        '''
        def _audit_entity(entity, resolver):
            method = _declared(entity, "method", "")
            rows = _audit_reference(entity, "method", method, resolver)
            rows += _audit_reference(entity, "method", entity.method, resolver)
            return rows
        '''
    )
    fn = next(n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.FunctionDef))
    assert _audited_field_names(fn) <= _declared_field_names(fn)
    with pytest.raises(AssertionError, match=r"direct entity\.method"):
        _assert_no_direct_audited_field_access(fn)


def test_drift_guard_rejects_a_nonliteral_label() -> None:
    src = textwrap.dedent(
        '''
        def _audit_entity(entity, resolver):
            label = "foo"
            return _audit_reference(entity, label, "t", resolver)
        '''
    )
    fn = next(n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.FunctionDef))
    with pytest.raises(AssertionError):
        _audited_field_names(fn)

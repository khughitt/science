# Audit `undeclared_key` Diagnostic Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the `_audit_entity` getattr misfire (fb-2026-07-16-003) so a reference field on a kind that does not declare it is no longer audited as a phantom `unresolved_reference`, and add a narrow `undeclared_key` WARN that reports the real defect — gated on the strict-schema kind set so it never fires on a schema-vouched extension field.

**Architecture:** Route every audited reference read in `graph/migrate.py::_audit_entity` through one `_declared(entity, name, default)` helper that reads a field only when the concrete kind declares it (`name in type(entity).model_fields`). A once-per-entity `_audit_undeclared_reference_keys` helper scans `model_extra` for known reference-field names and emits a `status="warn"` row, but only for entities whose `kind` is outside `ProjectSources.strict_schema_kinds` (the kinds the loader schema-checked). An AST drift guard forbids any reference read that bypasses `_declared`.

**Tech Stack:** Python 3, Pydantic v2 (`extra="allow"` on `Entity`, `type(x).model_fields`, `x.model_extra`), pytest. All package work runs from `science/`.

## Global Constraints

- Run all validation from `science/`: `cd science && uv run --frozen pytest`. Lint/types: `uv run ruff check` and `uv run pyright` from `science/`.
- Default pytest excludes the `snapshot` and `real_projects` markers; opt in with `-m snapshot` when checking snapshot fixtures.
- Behavior-additive for declared fields: existing audit behavior must not change. The only new severity is WARN — `undeclared_key` is always `status="warn"`.
- The diagnostic fires **only** when `entity.kind not in strict_schema_kinds`. `strict_schema_kinds = PROJECT_MIXIN_NAMES if project_schema is not None else frozenset()`; `PROJECT_MIXIN_NAMES = frozenset({"hypothesis"})` today.
- The six subset-declared reference fields are `method`, `workflow`, `chain`, `audits`, `proposition_refs`, `blocked_by`. The seven base-`Entity` fields (`related`, `source_refs`, `same_as`, `evidence_refs`, `dataset_usage`, `derivation`, `commits_to`) are declared on every kind and cannot misfire.
- `registry.resolve("workflow")` returns `ProjectEntity` (only `workflow-step`/`workflow-run` bind dedicated classes). Every kind requires `id`, `kind`, `title`, `project`, `ontology_terms`, `related`, `source_refs`, `content_preview`, `file_path`. `StructuredEntitySource` requires `canonical_id` (not `id`) and has no `kind` field.
- All test-file imports live in one block at the top of the file (Ruff isort). When a task needs a new symbol, extend that top block — never append `import` lines mid-file.
- No AI-attribution trailers on commits. Use `~/d/` for any doc filepaths.
- Branch: `audit-undeclared-key` (already holds the design commits). Do not push.

---

## File Structure

- `science/src/science_tool/graph/entity_registry.py` — add `registered_kinds()` (all registered kind → model, sorted).
- `science/src/science_tool/graph/sources.py` — add `ProjectSources.strict_schema_kinds` field; set it at the single construction site (`:663`) from the computed pin.
- `science/src/science_tool/graph/migrate.py` — core change: `_declared` gate, `_AUDITED_REFERENCE_FIELDS`/`REFERENCE_FIELD_NAMES`, `_audit_undeclared_reference_keys` + `_stringify_extra_value`/`_format_kinds`, `_audit_entity` signature/body, `audit_project_sources` threading.
- `science/model/src/science_model/entities.py` — correct the `Entity` docstring (`:314-317`) to the per-kind reality.
- `docs/plans/2026-07-12-authoritative-entity-schema-design.md` — one NOTE pointer near the undeclared-key inventory (`:454`).
- `science/tests/test_entity_registry.py` — `registered_kinds()` test.
- `science/tests/test_undeclared_key_diagnostic.py` — new file: field wiring, structured-source invariant, integration regression, gate+warn (×6), suppression, pinned-warn, resolvable, full-row, formatters, drift guard.

---

## Task 1: `EntityRegistry.registered_kinds()`

**Files:**
- Modify: `science/src/science_tool/graph/entity_registry.py` (insert after `all_kind_classes`, `:196-197`)
- Test: `science/tests/test_entity_registry.py`

**Interfaces:**
- Produces: `EntityRegistry.registered_kinds() -> dict[str, type[Entity]]` — every registered kind (core + profile + catalog + extension) → bound model class, ordered by kind name.

- [ ] **Step 1: Write the failing test**

Add to `science/tests/test_entity_registry.py`:

```python
def test_registered_kinds_returns_all_registered_sorted() -> None:
    from science_tool.graph.entity_registry import EntityRegistry
    from science_model.entities import Entity
    from science_model.identity import EntityClass

    registry = EntityRegistry.with_core_types()

    class WidgetEntity(Entity):
        pass

    registry.register_extension_kind("widget", WidgetEntity, entity_class=EntityClass.OPERATIONAL)

    kinds = registry.registered_kinds()
    assert kinds["workflow-step"].__name__ == "WorkflowStepEntity"
    assert kinds["widget"] is WidgetEntity
    assert list(kinds) == sorted(kinds)
    declaring = [k for k, cls in kinds.items() if "method" in cls.model_fields]
    assert declaring == ["workflow-step"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && uv run --frozen pytest tests/test_entity_registry.py::test_registered_kinds_returns_all_registered_sorted -v`
Expected: FAIL — `AttributeError: 'EntityRegistry' object has no attribute 'registered_kinds'`.

- [ ] **Step 3: Add the method**

In `science/src/science_tool/graph/entity_registry.py`, immediately after `all_kind_classes` (`:196-197`):

```python
    def registered_kinds(self) -> dict[str, type[Entity]]:
        """All registered kind -> bound model, deterministic by kind name.

        Merges core, profile, catalog, and extension registrations. Used to map a
        reference field back to the kinds that declare it (graph audit's
        undeclared_key diagnostic).
        """
        merged = {**self._core, **self._profile, **self._catalog, **self._extensions}
        return dict(sorted(merged.items()))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd science && uv run --frozen pytest tests/test_entity_registry.py::test_registered_kinds_returns_all_registered_sorted -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/graph/entity_registry.py science/tests/test_entity_registry.py
git commit -m "feat(registry): add registered_kinds() enumeration for reference-field ownership"
```

---

## Task 2: `ProjectSources.strict_schema_kinds`

**Files:**
- Modify: `science/src/science_tool/graph/sources.py` — field on `ProjectSources` (after `dataset_parents`, `:198`) and the construction site (`:663-683`)
- Test: `science/tests/test_undeclared_key_diagnostic.py` (new)

**Interfaces:**
- Consumes: `PROJECT_MIXIN_NAMES` (imported at `sources.py:45`), `project_schema` (local in `load_project_sources`, `:245-249`).
- Produces: `ProjectSources.strict_schema_kinds: frozenset[str]` — kinds whose extra-preserving load was schema-checked (`PROJECT_MIXIN_NAMES` when pinned, else empty). Default `frozenset()`.

- [ ] **Step 1: Write the failing tests**

Create `science/tests/test_undeclared_key_diagnostic.py` (all imports at top; only stdlib + existing symbols here — migrate's new symbols are added in Task 3):

```python
from __future__ import annotations

from pathlib import Path

from science_model.entity_schema import PROJECT_MIXIN_NAMES
from science_model.source_contracts import StructuredEntitySource
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


def test_structured_source_drops_unknown_reference_key() -> None:
    # The extra-preserving-path invariant: structured sources cannot carry a stray
    # reference-named key into model_extra (extra="ignore"), so the diagnostic can
    # never misfire on them. StructuredEntitySource requires canonical_id and has no
    # `kind` field; both `kind` and `method` here are unknown keys and are dropped.
    record = StructuredEntitySource.model_validate(
        {"canonical_id": "workflow:w", "title": "W", "kind": "workflow", "method": "phantom"}
    )
    assert not (record.model_extra or {})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd science && uv run --frozen pytest tests/test_undeclared_key_diagnostic.py -v`
Expected: the three `strict_schema_kinds` tests FAIL with `KeyError: 'strict_schema_kinds'`; `test_structured_source_drops_unknown_reference_key` PASSES (it asserts existing `extra="ignore"` behavior — the invariant guard, kept green).

- [ ] **Step 3: Add the field**

In `science/src/science_tool/graph/sources.py`, in `class ProjectSources` immediately after `dataset_parents` (`:198`):

```python
    # The kinds whose extra-preserving load was schema-checked (unevaluatedProperties:
    # false), i.e. PROJECT_MIXIN_NAMES when the project is pinned, else empty. The graph
    # audit's undeclared_key diagnostic fires only for kinds OUTSIDE this set: a key that
    # survives load on an in-set kind is schema-blessed; an out-of-set kind's extras were
    # never vouched. Default empty is conservative (diagnostic may fire).
    strict_schema_kinds: frozenset[str] = Field(default_factory=frozenset)
```

- [ ] **Step 4: Set it at construction**

In `load_project_sources`, in the `return ProjectSources(...)` (`:663-683`), add after `dataset_parents=dataset_parents,`:

```python
        strict_schema_kinds=PROJECT_MIXIN_NAMES if project_schema is not None else frozenset(),
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd science && uv run --frozen pytest tests/test_undeclared_key_diagnostic.py -v`
Expected: all four PASS.

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/graph/sources.py science/tests/test_undeclared_key_diagnostic.py
git commit -m "feat(sources): record strict_schema_kinds on ProjectSources for the audit gate"
```

---

## Task 3: The audit fix — gate, diagnostic, drift guard

**Files:**
- Modify: `science/src/science_tool/graph/migrate.py` — imports (`:1-30`), `_audit_entity` (`:285-427`), `audit_project_sources` (`:184-185`); add module constants and four helpers.
- Test: `science/tests/test_undeclared_key_diagnostic.py`

**Interfaces:**
- Consumes: `EntityRegistry.registered_kinds()` (Task 1); `ProjectSources.strict_schema_kinds` (Task 2).
- Produces:
  - `_declared(entity: Entity, name: str, default: Any) -> Any`
  - `_AUDITED_REFERENCE_FIELDS: tuple[str, ...]` — the 13 top-level attribute names read for auditing in `_audit_entity`.
  - `REFERENCE_FIELD_NAMES: frozenset[str]` = `frozenset(_AUDITED_REFERENCE_FIELDS) - set(Entity.model_fields)` — the 6 subset-declared fields.
  - `_stringify_extra_value(value: object) -> str`, `_format_kinds(kinds: tuple[str, ...]) -> str`
  - `_audit_undeclared_reference_keys(entity: Entity, *, declaring_kinds: Mapping[str, tuple[str, ...]]) -> list[AuditRow]`
  - `_audit_entity(entity, resolver, *, ext_prefixes, peer_ids, strict_schema_kinds: frozenset[str], declaring_kinds: Mapping[str, tuple[str, ...]]) -> list[AuditRow]` (two new **required** keyword params)

### Sub-part 0 — the behavioral red (the reported bug)

- [ ] **Step 1: Write the integration regression test**

Extend the top import block of `science/tests/test_undeclared_key_diagnostic.py` to add:

```python
from science_tool.graph.migrate import audit_project_sources
```

Append the test:

```python
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
    assert unresolved == []                         # no phantom
    assert len(undeclared) == 1 and undeclared[0]["status"] == "warn"
    assert verdict.status != "failed"               # WARN does not block
```

- [ ] **Step 2: Run it and confirm it fails ON THE BUG (not on import)**

Run: `cd science && uv run --frozen pytest tests/test_undeclared_key_diagnostic.py::test_integration_unpinned_workflow_method_warns_not_fails -v`
Expected: FAIL — the current code emits `unresolved_reference`/`fail` on `method -> w1-snakemake`, so `unresolved != []` and `verdict.status == "failed"`. This is the genuine red; the fix turns it green. (Verified: this exact fixture reproduces the reported defect against the current code.)

### Sub-part A — the `_declared` gate

- [ ] **Step 3: Add imports and the `_declared` helper**

In `science/src/science_tool/graph/migrate.py`, add `import json` to the stdlib block and replace `from typing import TypedDict` with:

```python
import json
from collections.abc import Mapping
from typing import Any, TypedDict
```

(`ast`/`inspect`/`textwrap` are test-file only; never import them in the module.)

Add, after the `AuditRow`/`LayeredClaimMigrationRow` TypedDicts (`:41-51`):

```python
def _declared(entity: Entity, name: str, default: Any) -> Any:
    """Read a reference field only when the entity's concrete kind declares it.

    Under extra="allow" a stray same-named key lives in model_extra, not in
    model_fields; reading it via getattr would audit it as a real reference.
    Returns Any deliberately: it replaces getattr(entity, name, default) (already
    Any), so the audited call sites keep their typing with no casts.
    """
    if name in type(entity).model_fields:
        return getattr(entity, name, default)
    return default
```

- [ ] **Step 4: Route every reference read through `_declared`**

In `_audit_entity` (`:285-427`), replace each reference read:

| Current | Replacement |
|---|---|
| `for target in entity.related:` | `for target in _declared(entity, "related", []):` |
| `for target in getattr(entity, "commits_to", None) or []:` | `for target in _declared(entity, "commits_to", None) or []:` |
| `for target in getattr(entity, "blocked_by", []) or []:` | `for target in _declared(entity, "blocked_by", []) or []:` |
| `workflow_ref = getattr(entity, "workflow", "")` | `workflow_ref = _declared(entity, "workflow", "")` |
| `method_ref = getattr(entity, "method", "")` | `method_ref = _declared(entity, "method", "")` |
| `for target in entity.source_refs:` | `for target in _declared(entity, "source_refs", []):` |
| `for target in getattr(entity, "evidence_refs", []) or []:` | `for target in _declared(entity, "evidence_refs", []) or []:` |
| `for usage in getattr(entity, "dataset_usage", []) or []:` | `for usage in _declared(entity, "dataset_usage", []) or []:` |
| `derivation = getattr(entity, "derivation", None)` | `derivation = _declared(entity, "derivation", None)` |
| `for target in getattr(entity, "chain", None) or []:` | `for target in _declared(entity, "chain", None) or []:` |
| `audits_target = getattr(entity, "audits", None)` | `audits_target = _declared(entity, "audits", None)` |
| `for target in getattr(entity, "proposition_refs", None) or []:` | `for target in _declared(entity, "proposition_refs", None) or []:` |
| `for target in entity.same_as:` | `for target in _declared(entity, "same_as", []):` |

Leave the inner `getattr(derivation, "inputs", [])` unchanged — `inputs` is a field of the `derivation` object, not of `entity`.

- [ ] **Step 5: Add the two required keyword params to `_audit_entity`**

Change the signature (`:285-291`) to:

```python
def _audit_entity(
    entity: Entity,
    resolver: ReferenceResolver,
    *,
    ext_prefixes: frozenset[str],
    peer_ids: frozenset[str] = frozenset(),
    strict_schema_kinds: frozenset[str],
    declaring_kinds: Mapping[str, tuple[str, ...]],
) -> list[AuditRow]:
```

(The two params are consumed in Sub-part B's Step 9; add the module constants and helper before wiring them so the module imports cleanly. Do not commit between Sub-parts A and B.)

- [ ] **Step 6: Add constants, formatters, and the diagnostic helper**

In `science/src/science_tool/graph/migrate.py`, after `_declared`:

```python
# The top-level attribute names _audit_entity reads for auditing. The drift-guard test
# AST-pins this to the actual reads, so it cannot silently drift.
_AUDITED_REFERENCE_FIELDS: tuple[str, ...] = (
    "related",
    "commits_to",
    "blocked_by",
    "workflow",
    "method",
    "source_refs",
    "evidence_refs",
    "dataset_usage",
    "derivation",
    "chain",
    "audits",
    "proposition_refs",
    "same_as",
)

# The subset-declared reference fields: those a stray same-named key can misplace onto a
# kind that does not declare them. Base-Entity fields are declared everywhere and can never
# appear as a stray model_extra key, so they are excluded.
REFERENCE_FIELD_NAMES: frozenset[str] = frozenset(_AUDITED_REFERENCE_FIELDS) - set(Entity.model_fields)


def _stringify_extra_value(value: object) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, (list, tuple)):
        return ", ".join(_stringify_extra_value(item) for item in value)
    if isinstance(value, dict):
        return json.dumps(value, sort_keys=True, ensure_ascii=False)
    return str(value)


def _format_kinds(kinds: tuple[str, ...]) -> str:
    return ", ".join(f"`{kind}`" for kind in kinds)


def _audit_undeclared_reference_keys(
    entity: Entity,
    *,
    declaring_kinds: Mapping[str, tuple[str, ...]],
) -> list[AuditRow]:
    """WARN for a reference-named key present on a kind that does not declare it.

    Only reference-field names are flagged; a non-reference extension field is
    preserved silently (D3.3). Caller gates this on entity.kind being outside the
    strict-schema kind set — a schema-vouched extension never reaches here.
    """
    rows: list[AuditRow] = []
    for key in sorted(entity.model_extra or {}):
        if key not in REFERENCE_FIELD_NAMES:
            continue
        owners = declaring_kinds.get(key, ())
        owner_clause = f"; it is declared by {_format_kinds(owners)}" if owners else ""
        rows.append(
            {
                "check": "undeclared_key",
                "status": "warn",
                "source": entity.canonical_id,
                "field": key,
                "target": _stringify_extra_value((entity.model_extra or {})[key]),
                "details": (
                    f"`{key}` is not a declared field of kind `{entity.kind}`{owner_clause}. "
                    "It is an unvouched extra key on this kind, not wired into the graph — "
                    "move it to the owning kind or remove it."
                ),
            }
        )
    return rows
```

### Sub-part B — wire the diagnostic and thread the params

- [ ] **Step 7: Wire the diagnostic into `_audit_entity`**

At the end of `_audit_entity`, immediately before `return rows` (`:427`):

```python
    if entity.kind not in strict_schema_kinds:
        rows.extend(_audit_undeclared_reference_keys(entity, declaring_kinds=declaring_kinds))
    return rows
```

- [ ] **Step 8: Thread the params from `audit_project_sources`**

In `audit_project_sources`, replace the loop at `:184-185`:

```python
        strict_schema_kinds = sources.strict_schema_kinds
        declaring_kinds = {
            field: tuple(
                kind for kind, cls in sources.registry.registered_kinds().items()
                if field in cls.model_fields
            )
            for field in REFERENCE_FIELD_NAMES
        }
        for entity in sources.entities:
            rows.extend(
                _audit_entity(
                    entity, resolver, ext_prefixes=ext_prefixes, peer_ids=peer_ids,
                    strict_schema_kinds=strict_schema_kinds, declaring_kinds=declaring_kinds,
                )
            )
```

- [ ] **Step 9: Run the integration regression — it must now pass**

Run: `cd science && uv run --frozen pytest tests/test_undeclared_key_diagnostic.py::test_integration_unpinned_workflow_method_warns_not_fails -v`
Expected: PASS — the phantom is gone, one `undeclared_key`/`warn` row is present, and `verdict.status != "failed"`.

### Sub-part C — unit coverage (gate, diagnostic, formatters)

- [ ] **Step 10: Add the shared test helpers and unit tests**

Extend the top import block of `science/tests/test_undeclared_key_diagnostic.py` to add:

```python
import pytest

from science_model.entities import Entity
from science_tool.graph.entity_registry import EntityRegistry
from science_tool.graph.migrate import (
    REFERENCE_FIELD_NAMES,
    _audit_entity,
    _audit_undeclared_reference_keys,
    _declared,
    _format_kinds,
    _stringify_extra_value,
)
from science_tool.graph.reference_resolution import ReferenceResolver
```

Append the helpers and tests:

```python
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
        entity, resolver, ext_prefixes=frozenset(), peer_ids=frozenset(),
        strict_schema_kinds=strict, declaring_kinds=_declaring_kinds(),
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
    assert phantom == []          # zero phantom failures
    assert len(warns) == 1        # exactly one WARN


def test_declared_reads_undeclared_field_as_default() -> None:
    workflow = _entity("workflow", method="phantom")   # ProjectEntity: no `method`
    assert _declared(workflow, "method", "DFLT") == "DFLT"


def test_declared_reads_declared_field_as_value() -> None:
    step = _entity("workflow-step", method="m1")        # WorkflowStepEntity declares `method`
    assert _declared(step, "method", "DFLT") == "m1"


def test_gate_preserves_genuine_unresolved_on_declared_field() -> None:
    # Regression: the gate must NOT stop auditing a field the kind DOES declare.
    step = _entity("workflow-step", method="does-not-exist")
    rows = _audit(step)
    assert any(r["check"] == "unresolved_reference" and r["field"] == "method" for r in rows)


def test_resolvable_declared_method_yields_no_rows() -> None:
    # A resolvable method reference produces neither a phantom nor a WARN.
    method_target = _entity("method")                    # canonical_id "method:x"
    step = _entity("workflow-step", method="method:x")
    resolver = ReferenceResolver.from_entities([step, method_target])
    rows = _audit_entity(
        step, resolver, ext_prefixes=frozenset(), peer_ids=frozenset(),
        strict_schema_kinds=frozenset(), declaring_kinds=_declaring_kinds(),
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
    assert _stringify_extra_value(("b", "a")) == "b, a"       # tuple
    assert _stringify_extra_value({"y": 1, "x": 2}) == '{"x": 2, "y": 1}'
    assert _stringify_extra_value(7) == "7"
    assert _format_kinds(("workflow-run", "workflow-step")) == "`workflow-run`, `workflow-step`"
```

- [ ] **Step 11: Run the unit tests**

Run: `cd science && uv run --frozen pytest tests/test_undeclared_key_diagnostic.py -v`
Expected: all PASS (gate ×6, `_declared` reads, regression, resolvable, full-row, suppression, pinned-warn, formatters, plus Task 2 and the integration test).

### Sub-part D — the drift guard

- [ ] **Step 12: Add the drift-guard tests**

Extend the top import block to add:

```python
import ast
import inspect
import textwrap

from science_tool.graph import migrate as _migrate
```

Append:

```python
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
            and node.args[0].id == "entity"           # first arg must be the entity
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
```

- [ ] **Step 13: Run the drift-guard tests**

Run: `cd science && uv run --frozen pytest tests/test_undeclared_key_diagnostic.py -k "drift or getattr or audited_field or declared_reads_match" -v`
Expected: PASS — the real `_audit_entity` has no bare `getattr(entity, ...)`, every audited field is gated, `GATED == _AUDITED_REFERENCE_FIELDS`, and the three synthetic bypass/non-literal bodies are rejected.

### Sub-part E — full suite, lint, types, snapshots

- [ ] **Step 14: Run the module regression suite**

Run: `cd science && uv run --frozen pytest tests/test_undeclared_key_diagnostic.py tests/test_graph_migrate.py tests/test_references.py tests/test_entities.py -v`
Expected: all PASS (existing audit behavior for declared fields unchanged).

- [ ] **Step 15: Lint, types, full default suite**

Run:
```bash
cd science && uv run ruff check && uv run pyright && uv run --frozen pytest
```
Expected: ruff clean (imports at top, no unused), pyright clean (no new errors), full suite green.

- [ ] **Step 16: Check snapshot fixtures**

Run: `cd science && uv run --frozen pytest -m snapshot`
Expected: PASS. If a snapshot fixture contains a reference-named key on an unpinned kind, a new `undeclared_key` WARN row appears; regenerate that snapshot per the repo convention and confirm the diff is only the expected added WARN. If unaffected, no change.

- [ ] **Step 17: Commit**

```bash
git add science/src/science_tool/graph/migrate.py science/tests/test_undeclared_key_diagnostic.py
git commit -m "fix(audit): gate reference audits on declared-by-kind, add undeclared_key WARN (fb-2026-07-16-003)"
```

---

## Task 4: Correct the `Entity` docstring, add the D5 pointer, record the resolution

**Files:**
- Modify: `science/model/src/science_model/entities.py:314-317`
- Modify: `docs/plans/2026-07-12-authoritative-entity-schema-design.md` (NOTE near the undeclared-key inventory, `:454-458`)
- Modify: `docs/plans/2026-07-16-audit-undeclared-key-diagnostic-design.md` (Status → implemented-pending-merge)

**Interfaces:**
- Consumes: Task 3 (the diagnostic now exists; the docs must describe the per-kind reality it depends on).

- [ ] **Step 1: Correct the `Entity` docstring**

In `science/model/src/science_model/entities.py`, the `Entity` docstring (`:314-317`) currently reads:

```
    This is safe ONLY because the schema is checked FIRST. `extra="allow"` on its own would preserve
    every typo and every deleted key; `unevaluatedProperties: false` on the composed profile is what
    refuses them, and `load_project_sources` runs it before constructing this model on any project
    pinned to `entity_schema_version: 2`. The two are one contract: the SCHEMA refuses what it does
    not know, the PROJECTION preserves what it admitted. Separated, each is a defect.
```

Replace with:

```
    This is safe ONLY because the schema is checked FIRST. `extra="allow"` on its own would preserve
    every typo and every deleted key; `unevaluatedProperties: false` on the composed profile is what
    refuses them. On a project pinned to `entity_schema_version: 2`, `load_project_sources` runs that
    check before constructing this model — but only for the kinds in `PROJECT_MIXIN_NAMES` (today just
    `hypothesis`); other kinds are not schema-checked yet, so their extra keys are preserved unvouched
    and the graph audit's `undeclared_key` diagnostic is what surfaces a misplaced reference field on
    them. The two are one contract: the SCHEMA refuses what it does not know, the PROJECTION preserves
    what it admitted. Separated, each is a defect.
```

- [ ] **Step 2: Verify no test asserts the old wording**

Run: `cd science && rg -n "runs it before constructing this model on any project" model/src/science_model/entities.py || echo "no stale references"`
Expected: `no stale references` (the sentence lived only in the docstring, now rewritten).

- [ ] **Step 3: Add the D5 inventory pointer**

In `docs/plans/2026-07-12-authoritative-entity-schema-design.md`, the P0 bullet's undeclared-key inventory ends at the line "including commons wherever a shared field is touched.**" (immediately before "- **P1 — Absorb the real subsystems.**", around `:458-459`). Insert this indented note immediately after that bullet, before the `- **P1` line:

```
  > **NOTE 2026-07-16 (fb-2026-07-16-003).** Misplaced *known reference* fields (a
  > reference-field name appearing on a kind that does not declare it) are now handled
  > generally by the graph audit's `undeclared_key` WARN
  > (`2026-07-16-audit-undeclared-key-diagnostic-design.md`), not by a per-field entry
  > in this inventory.
```

- [ ] **Step 4: Update the design Status to implemented-pending-merge**

In `docs/plans/2026-07-16-audit-undeclared-key-diagnostic-design.md`, change the Status line from `**Decision-ready.**` to `**IMPLEMENTED on branch \`audit-undeclared-key\`; pending merge.**` (keep the rest of the Status paragraph). Do not mark SHIPPED/CLOSED until merged.

- [ ] **Step 5: Run the model suite**

Run: `cd science/model && uv run --frozen pytest`
Expected: PASS (docstring-only change to the model package).

- [ ] **Step 6: Commit**

```bash
git add science/model/src/science_model/entities.py docs/plans/2026-07-12-authoritative-entity-schema-design.md docs/plans/2026-07-16-audit-undeclared-key-diagnostic-design.md
git commit -m "docs: correct schema-first docstring to per-kind reality; record undeclared_key in D5 inventory; mark design implemented"
```

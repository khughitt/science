# Audit `undeclared_key` Diagnostic Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the `_audit_entity` getattr misfire (fb-2026-07-16-003) so a reference field on a kind that does not declare it is no longer audited as a phantom `unresolved_reference`, and add a narrow `undeclared_key` WARN that reports the real defect — gated on the strict-schema kind set so it never fires on a schema-vouched extension field.

**Architecture:** Route every audited reference read in `graph/migrate.py::_audit_entity` through one `_declared(entity, name, default)` helper that reads a field only when the concrete kind declares it (`name in type(entity).model_fields`). A once-per-entity `_audit_undeclared_reference_keys` helper scans `model_extra` for known reference-field names and emits a `status="warn"` row, but only for entities whose `kind` is outside `ProjectSources.strict_schema_kinds` (the kinds the loader schema-checked). An AST drift guard forbids any reference read that bypasses `_declared`.

**Tech Stack:** Python 3, Pydantic v2 (`extra="allow"` on `Entity`, `type(x).model_fields`, `x.model_extra`), pytest. All package work runs from `science/`.

## Global Constraints

- Run all validation from `science/`: `cd science && uv run --frozen pytest`. Lint/types: `uv run ruff check` and `uv run pyright` from `science/`.
- Default pytest excludes the `snapshot` and `real_projects` markers; opt in with `-m snapshot` when checking snapshot fixtures.
- The diagnostic is **docs+code**, behavior-additive: existing audit behavior for declared fields must not change. The only new fail-severity is none — `undeclared_key` is always `status="warn"`.
- `undeclared_key` fires **only** when `entity.kind not in strict_schema_kinds`. `strict_schema_kinds = PROJECT_MIXIN_NAMES if project_schema is not None else frozenset()`; `PROJECT_MIXIN_NAMES = frozenset({"hypothesis"})` today.
- The six subset-declared reference fields are `method`, `workflow`, `chain`, `audits`, `proposition_refs`, `blocked_by`. The seven base-`Entity` fields (`related`, `source_refs`, `same_as`, `evidence_refs`, `dataset_usage`, `derivation`, `commits_to`) are declared on every kind and cannot misfire.
- No AI-attribution trailers on commits. Use `~/d/` for any doc filepaths.
- Branch: `audit-undeclared-key` (already exists, holds the design commits). Do not push.

---

## File Structure

- `science/src/science_tool/graph/entity_registry.py` — add `registered_kinds()` (all registered kind → model, sorted). Foundation for the declaring-kinds map.
- `science/src/science_tool/graph/sources.py` — add `ProjectSources.strict_schema_kinds` field and set it at the single construction site (`:663`) from the computed pin.
- `science/src/science_tool/graph/migrate.py` — the core change: `_declared` gate, `_AUDITED_REFERENCE_FIELDS`/`REFERENCE_FIELD_NAMES`, `_audit_undeclared_reference_keys` + `_stringify_extra_value`/`_format_kinds`, `_audit_entity` signature/body, `audit_project_sources` threading.
- `science/model/src/science_model/entities.py` — correct the `Entity` docstring (`:314-317`) from the whole-project-pin premise to the per-kind reality.
- `science/tests/test_entity_registry.py` — `registered_kinds()` test.
- `science/tests/test_undeclared_key_diagnostic.py` — new file: gate (×6), suppression, pinned-workflow-warns, structured-source invariant, diagnostic full-row, formatters, drift guard, integration.

---

## Task 1: `EntityRegistry.registered_kinds()`

**Files:**
- Modify: `science/src/science_tool/graph/entity_registry.py` (insert after `all_kind_classes`, `:196-197`)
- Test: `science/tests/test_entity_registry.py`

**Interfaces:**
- Produces: `EntityRegistry.registered_kinds() -> dict[str, type[Entity]]` — every registered kind (core + profile + catalog + extension) mapped to its bound model class, ordered by kind name.

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
    # Core kinds present, extension present, deterministic sorted order.
    assert kinds["workflow-step"].__name__ == "WorkflowStepEntity"
    assert kinds["widget"] is WidgetEntity
    assert list(kinds) == sorted(kinds)
    # method is declared only by workflow-step among registered kinds.
    declaring = [k for k, cls in kinds.items() if "method" in cls.model_fields]
    assert declaring == ["workflow-step"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && uv run --frozen pytest tests/test_entity_registry.py::test_registered_kinds_returns_all_registered_sorted -v`
Expected: FAIL with `AttributeError: 'EntityRegistry' object has no attribute 'registered_kinds'`.

- [ ] **Step 3: Add the method**

In `science/src/science_tool/graph/entity_registry.py`, immediately after `all_kind_classes` (currently `:196-197`):

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
- Modify: `science/src/science_tool/graph/sources.py` — field on `ProjectSources` (`:198`, after `dataset_parents`), and the construction site (`:663-683`)
- Test: `science/tests/test_undeclared_key_diagnostic.py` (new)

**Interfaces:**
- Consumes: `PROJECT_MIXIN_NAMES` (already imported at `sources.py:45`), `project_schema` (local in `load_project_sources`, computed `:245-249`).
- Produces: `ProjectSources.strict_schema_kinds: frozenset[str]` — the kinds whose extra-preserving load was schema-checked (`PROJECT_MIXIN_NAMES` when pinned, else empty). Default `frozenset()`.

- [ ] **Step 1: Write the failing tests**

Create `science/tests/test_undeclared_key_diagnostic.py`:

```python
from __future__ import annotations

from pathlib import Path

from science_model.source_contracts import StructuredEntitySource
from science_tool.graph.sources import ProjectSources, load_project_sources


def _write_project(root: Path, *, pinned: bool) -> None:
    root.mkdir(parents=True, exist_ok=True)
    pin = "entity_schema_version: 2\n" if pinned else ""
    (root / "science.yaml").write_text(f"name: demo\n{pin}", encoding="utf-8")
    hyp = root / "entities" / "hypotheses" / "h1.md"
    hyp.parent.mkdir(parents=True)
    hyp.write_text(
        '---\nid: "hypothesis:h1"\nkind: "hypothesis"\ntitle: "H1"\n'
        'related: []\nsource_refs: []\ncreated: "2026-03-12"\nupdated: "2026-03-12"\n'
        "---\nBody.\n",
        encoding="utf-8",
    )


def test_project_sources_has_strict_schema_kinds_field_default() -> None:
    # The field exists and defaults to empty (conservative: nothing vouched).
    assert ProjectSources.model_fields["strict_schema_kinds"].default == frozenset()


def test_unpinned_project_strict_schema_kinds_is_empty(tmp_path: Path) -> None:
    _write_project(tmp_path / "p", pinned=False)
    sources = load_project_sources(tmp_path / "p")
    assert sources.strict_schema_kinds == frozenset()


def test_pinned_project_strict_schema_kinds_is_mixin_names(tmp_path: Path) -> None:
    from science_model.entity_schema import PROJECT_MIXIN_NAMES

    _write_project(tmp_path / "p", pinned=True)
    sources = load_project_sources(tmp_path / "p")
    assert sources.strict_schema_kinds == PROJECT_MIXIN_NAMES


def test_structured_source_drops_unknown_reference_key() -> None:
    # The extra-preserving-path invariant: structured sources cannot carry a stray
    # reference-named key into model_extra (extra="ignore"), so the diagnostic
    # can never misfire on them regardless of kind.
    record = StructuredEntitySource.model_validate(
        {"id": "workflow:w", "kind": "workflow", "title": "W", "method": "phantom"}
    )
    assert not (record.model_extra or {})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd science && uv run --frozen pytest tests/test_undeclared_key_diagnostic.py -v`
Expected: the three `strict_schema_kinds` tests FAIL with `KeyError: 'strict_schema_kinds'` / `AttributeError`; `test_structured_source_drops_unknown_reference_key` PASSES already (it asserts existing `extra="ignore"` behavior — it is the invariant guard, kept green).

- [ ] **Step 3: Add the field**

In `science/src/science_tool/graph/sources.py`, in `class ProjectSources` immediately after `dataset_parents` (`:198`):

```python
    # The kinds whose extra-preserving load was schema-checked (unevaluatedProperties:
    # false), i.e. PROJECT_MIXIN_NAMES when the project is pinned, else empty. The graph
    # audit's undeclared_key diagnostic fires only for kinds OUTSIDE this set: a key that
    # survives load on an in-set kind is schema-blessed, an out-of-set kind's extras were
    # never vouched. Default empty is conservative (diagnostic may fire).
    strict_schema_kinds: frozenset[str] = Field(default_factory=frozenset)
```

- [ ] **Step 4: Set it at construction**

In `load_project_sources`, in the `return ProjectSources(...)` at `:663-683`, add (after `dataset_parents=dataset_parents,`):

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

### Sub-part A — the gate (kills the misfire)

- [ ] **Step 1: Write the failing gate tests**

Append to `science/tests/test_undeclared_key_diagnostic.py`. `registry.resolve("workflow")` returns `ProjectEntity` (only `workflow-step`/`workflow-run` bind the dedicated classes), and every kind requires `project`, `ontology_terms`, `related`, `source_refs`, `content_preview`, `file_path` — so the helper supplies them. `ReferenceResolver.from_entities` takes an optional `identity_table`, so a single-entity resolver needs no table.

```python
import pytest

from science_model.entities import Entity
from science_tool.graph.entity_registry import EntityRegistry
from science_tool.graph.migrate import (
    REFERENCE_FIELD_NAMES,
    _audit_entity,
    _audit_undeclared_reference_keys,
    _declared,
)
from science_tool.graph.reference_resolution import ReferenceResolver

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


# (field, a kind whose class does NOT declare it, is-scalar). blocked_by is omitted:
# it is declared by ~48 kinds and misplaceable only onto chain-audit/structural-chain
# (heavy required fields); its gate is covered by _declared + the drift guard below.
_MISPLACED = [
    ("method", "workflow", True),
    ("workflow", "task", True),
    ("audits", "task", True),
    ("chain", "task", False),
    ("proposition_refs", "task", False),
]


@pytest.mark.parametrize("field,kind,scalar", _MISPLACED)
def test_gate_suppresses_phantom_unresolved_reference(field: str, kind: str, scalar: bool) -> None:
    value = "phantom-target" if scalar else ["phantom-target"]
    entity = _entity(kind, **{field: value})
    rows = _audit(entity)
    unresolved = [r for r in rows if r["check"] == "unresolved_reference" and r["field"] == field]
    assert unresolved == []


def test_declared_reads_undeclared_field_as_default() -> None:
    # Piece 1: an undeclared reference name (incl. blocked_by on a kind that lacks it)
    # returns the default, so it is never audited as a reference.
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
```

- [ ] **Step 2: Run to verify failure**

Run: `cd science && uv run --frozen pytest tests/test_undeclared_key_diagnostic.py -k gate_suppresses -v`
Expected: FAIL — `ImportError` (`REFERENCE_FIELD_NAMES`/`_audit_undeclared_reference_keys` do not exist) and/or `_audit_entity` missing the new keyword params.

- [ ] **Step 3: Add imports and the `_declared` helper**

In `science/src/science_tool/graph/migrate.py`, extend the imports (`:1-30`). Add `import json` to the stdlib block, and replace `from typing import TypedDict` with:

```python
import json
from collections.abc import Mapping
from typing import Any, TypedDict
```

(`ast`/`inspect`/`textwrap` belong only in the test file's drift-guard helpers, never in the module.)

Add, near the top-level helpers (after the `AuditRow`/`LayeredClaimMigrationRow` TypedDicts, `:41-51`):

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

(The diagnostic call is wired in Sub-part B; for now the two params are accepted and unused, which the very next steps consume — do not commit between A and B.)

- [ ] **Step 6: Thread the params from `audit_project_sources`**

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

### Sub-part B — the diagnostic

- [ ] **Step 7: Write the failing diagnostic tests**

Append to `science/tests/test_undeclared_key_diagnostic.py`:

```python
def test_undeclared_key_warns_with_owner_and_wording() -> None:
    entity = _entity("workflow", method="phantom")
    rows = _audit_undeclared_reference_keys(entity, declaring_kinds=_declaring_kinds())
    assert len(rows) == 1
    row = rows[0]
    assert row["check"] == "undeclared_key"
    assert row["status"] == "warn"
    assert row["source"] == "workflow:x"
    assert row["field"] == "method"
    assert row["target"] == "phantom"
    assert "`workflow-step`" in row["details"]
    assert "not a declared field of kind `workflow`" in row["details"]
    assert "unvouched extra key" in row["details"]


def test_undeclared_key_ignores_non_reference_extra_key() -> None:
    entity = _entity("workflow", custom_note="hi")
    assert _audit_undeclared_reference_keys(entity, declaring_kinds=_declaring_kinds()) == []


def test_strict_schema_kind_suppresses_undeclared_key() -> None:
    # A kind IN the strict set: a stray reference key is treated as schema-vouched.
    entity = _entity("hypothesis", method="phantom")
    rows = _audit(entity, strict=frozenset({"hypothesis"}))
    assert [r for r in rows if r["check"] == "undeclared_key"] == []


def test_unvalidated_kind_on_pinned_project_still_warns() -> None:
    # workflow is NOT in PROJECT_MIXIN_NAMES, so a pinned project still warns.
    entity = _entity("workflow", method="phantom")
    rows = _audit(entity, strict=frozenset({"hypothesis"}))
    assert [r for r in rows if r["check"] == "undeclared_key"][0]["field"] == "method"


def test_stringify_and_format_kinds() -> None:
    from science_tool.graph.migrate import _format_kinds, _stringify_extra_value

    assert _stringify_extra_value("a") == "a"
    assert _stringify_extra_value(["b", "a"]) == "b, a"
    assert _stringify_extra_value({"y": 1, "x": 2}) == '{"x": 2, "y": 1}'
    assert _stringify_extra_value(7) == "7"
    assert _format_kinds(("workflow-run", "workflow-step")) == "`workflow-run`, `workflow-step`"
```

- [ ] **Step 8: Run to verify failure**

Run: `cd science && uv run --frozen pytest tests/test_undeclared_key_diagnostic.py -k "undeclared_key or stringify or unvalidated or strict_schema_kind_supp" -v`
Expected: FAIL — helpers `_audit_undeclared_reference_keys`/`_stringify_extra_value`/`_format_kinds` not defined; suppression/warn tests fail because the diagnostic is not yet wired into `_audit_entity`.

- [ ] **Step 9: Add the constants, formatters, and diagnostic helper**

In `science/src/science_tool/graph/migrate.py`, after `_declared` (from Sub-part A):

```python
# The top-level attribute names _audit_entity reads for auditing. The drift-guard
# test (test_undeclared_key_diagnostic.py) AST-pins this to the actual reads, so it
# cannot silently drift.
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

# The subset-declared reference fields: those a stray same-named key can misplace onto
# a kind that does not declare them. Base-Entity fields are declared everywhere and can
# never appear as a stray model_extra key, so they are excluded.
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

- [ ] **Step 10: Wire the diagnostic into `_audit_entity`**

At the end of `_audit_entity`, immediately before `return rows` (`:427`):

```python
    if entity.kind not in strict_schema_kinds:
        rows.extend(_audit_undeclared_reference_keys(entity, declaring_kinds=declaring_kinds))
    return rows
```

- [ ] **Step 11: Run gate + diagnostic tests**

Run: `cd science && uv run --frozen pytest tests/test_undeclared_key_diagnostic.py -v`
Expected: all gate, diagnostic, suppression, pinned-warn, and formatter tests PASS.

### Sub-part C — the drift guard

- [ ] **Step 12: Write the drift-guard test**

Append to `science/tests/test_undeclared_key_diagnostic.py`:

```python
import ast
import inspect
import textwrap

from science_tool.graph import migrate as _migrate


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
            and isinstance(node.args[1], ast.Constant)
            and isinstance(node.args[1].value, str)
        ):
            names.add(node.args[1].value)
    return names


def _audited_field_names(fn: ast.FunctionDef) -> set[str]:
    """Top-level prefixes of the field_name label of every audit call.

    Fails closed: a non-literal / missing label raises, so an unverifiable audit
    site cannot slip through.
    """
    audit_fns = {"_audit_reference", "_audit_dataset_reference"}
    names: set[str] = set()
    for node in ast.walk(fn):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in audit_fns:
            label = None
            if len(node.args) >= 2:
                label = node.args[1]
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
    gated = _declared_field_names(fn)
    audited = _audited_field_names(fn)
    assert audited <= gated, f"ungated audited fields: {audited - gated}"


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
    # audited has "foo" but gated does not -> the equality/subset guards catch it.
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

Run: `cd science && uv run --frozen pytest tests/test_undeclared_key_diagnostic.py -k "drift or getattr or audited_field or declared_reads" -v`
Expected: PASS — the real `_audit_entity` has no bare `getattr(entity, ...)`, every audited field is gated, `GATED == _AUDITED_REFERENCE_FIELDS`, and the synthetic bypass/non-literal bodies are rejected.

### Sub-part D — integration + full suite

- [ ] **Step 14: Write the integration test (unpinned project, real path)**

Append to `science/tests/test_undeclared_key_diagnostic.py`:

```python
from science_tool.graph.migrate import audit_project_sources


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
    undeclared = [r for r in verdict.rows if r["check"] == "undeclared_key"]
    unresolved = [r for r in verdict.rows if r["check"] == "unresolved_reference" and r["field"] == "method"]
    assert unresolved == []                       # no phantom
    assert len(undeclared) == 1 and undeclared[0]["status"] == "warn"
    assert verdict.status != "failed"             # WARN does not block
```

(This exact fixture was verified to reproduce the bug against the current code — it emits `unresolved_reference`/`fail` on `method -> w1-snakemake` today, which the fix turns into the `undeclared_key`/`warn` row the test asserts.)

- [ ] **Step 15: Run the new test file, then the module regression suite**

Run: `cd science && uv run --frozen pytest tests/test_undeclared_key_diagnostic.py tests/test_graph_migrate.py tests/test_references.py tests/test_entities.py -v`
Expected: all PASS (existing audit behavior for declared fields unchanged).

- [ ] **Step 16: Lint, types, and full default suite**

Run:
```bash
cd science && uv run ruff check && uv run pyright && uv run --frozen pytest
```
Expected: ruff clean, pyright clean (no new errors), full suite green. If `ast`/`inspect` imports were added to the module but are unused there, move them to the test file only to keep ruff clean.

- [ ] **Step 17: Check snapshot fixtures**

Run: `cd science && uv run --frozen pytest -m snapshot`
Expected: PASS. If a snapshot fixture legitimately contains a reference-named key on an unpinned kind, a new `undeclared_key` WARN row appears; regenerate that snapshot per the repo's snapshot-update convention and confirm the diff is only the expected added WARN row. If snapshots are unaffected, no change.

- [ ] **Step 18: Commit**

```bash
git add science/src/science_tool/graph/migrate.py science/tests/test_undeclared_key_diagnostic.py
git commit -m "fix(audit): gate reference audits on declared-by-kind, add undeclared_key WARN (fb-2026-07-16-003)"
```

---

## Task 4: Correct the `Entity` docstring and record the resolution

**Files:**
- Modify: `science/model/src/science_model/entities.py:314-317`
- Modify: `docs/plans/2026-07-16-audit-undeclared-key-diagnostic-design.md` (Status → shipped-pending-merge)

**Interfaces:**
- Consumes: Task 3 (the diagnostic now exists; the docstring must describe the per-kind reality it depends on).

- [ ] **Step 1: Correct the docstring**

In `science/model/src/science_model/entities.py`, the `Entity` docstring (`:314-317`) currently reads:

```
    This is safe ONLY because the schema is checked FIRST. `extra="allow"` on its own would preserve
    every typo and every deleted key; `unevaluatedProperties: false` on the composed profile is what
    refuses them, and `load_project_sources` runs it before constructing this model on any project
    pinned to `entity_schema_version: 2`. The two are one contract: the SCHEMA refuses what it does
    not know, the PROJECTION preserves what it admitted. Separated, each is a defect.
```

Replace the middle sentence so it states the per-kind reality:

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

Run: `cd science && rg -n "runs it before constructing this model on any project" .. || echo "no stale references"`
Expected: `no stale references` (the sentence was only in the docstring).

- [ ] **Step 3: Run the model suite**

Run: `cd science/model && uv run --frozen pytest`
Expected: PASS (docstring-only change).

- [ ] **Step 4: Update the design Status to shipped-pending-merge**

In `docs/plans/2026-07-16-audit-undeclared-key-diagnostic-design.md`, change the Status line from `**Decision-ready.**` to:

```
**IMPLEMENTED on branch `audit-undeclared-key`; pending merge.** ...
```

(keep the rest of the Status paragraph). Do not mark SHIPPED/CLOSED until merged.

- [ ] **Step 5: Commit**

```bash
git add science/model/src/science_model/entities.py docs/plans/2026-07-16-audit-undeclared-key-diagnostic-design.md
git commit -m "docs(entities): correct schema-first docstring to per-kind reality; mark design implemented"
```

---

## Notes on the D5 inventory pointer

Record-correction #4 in the design (a pointer in `2026-07-12-authoritative-entity-schema-design.md` that misplaced reference fields are now handled by `undeclared_key`) is a one-line note. Fold it into Task 4 Step 4's commit if that design doc is present and writable; if it is a large historical doc, append a single `> **NOTE 2026-07-16.**` line near its undeclared-key inventory (~line 453) rather than editing the inventory in place. This is optional polish, not a gate — skip if the file is absent.

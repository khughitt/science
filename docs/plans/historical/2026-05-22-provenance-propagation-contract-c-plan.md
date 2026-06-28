# Provenance Propagation Contract (Plan C) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a decision-bearing code edit propagate to downstream findings by adding a code-only `produced_by` edge authored on a `dataset`, which derives `bears_on` (`code-file bears_on dataset`) and composes through the existing data→finding derivers and freshness engine.

**Architecture:** A data artifact (`dataset` entity) declares the `code-file`(s) that produced it via a new code-only `produced_by` field. The materializer emits a `sci:producedBy` triple per *resolved* code-file ref (lenient, skip-on-miss), a new deriver turns each into `code-file bears_on dataset` filtered to propagation-eligible code files, and the existing `close_bears_on` + freshness layer carry it to the finding. A relaxed derived-dataset schema/invariant lets a derived dataset record code provenance without a `workflow_run` block. No workflow DAG, no synthetic nodes.

**Tech Stack:** Python 3.12, pydantic v2, rdflib, jsonschema, pytest, `uv`. Two packages: `science-model` (`science/model/`, tests `science/model/tests/`, run with `cd science/model && uv run pytest …`) and `science_tool` (`science/`, tests `science/tests/`, run with `cd science && uv run pytest …`).

**Spec:** `docs/plans/historical/2026-05-21-provenance-propagation-contract-c-design.md` (rev 3).

**Note on file placement (deviation from spec §8):** The spec named a new `graph/provenance_edges.py`. To follow the established codebase pattern, the new `bears_on` deriver lives in `graph/freshness.py` beside the other `derive_bears_on_from_*` functions (it reuses the private `_emit_bears_on_edge`), the materialization helpers live in `graph/materialize.py` beside the other `_add_*`/`_build_*` helpers, and the tool-path→id normalizer lives in a new `code/provenance.py`. No new `provenance_edges.py` module.

**Branch:** Work on a feature branch off the current `docs/spec2-provenance-contract` branch (which carries the committed design). All commits are local; do **not** push.

---

### Task 1: Extend the `produced_by` relation kind to accept code-file targets

**Files:**
- Modify: `science/model/src/science_model/profiles/core.py:302-309`
- Test: `science/model/tests/test_produced_by_relation.py` (create)

- [ ] **Step 1: Write the failing test**

```python
# science/model/tests/test_produced_by_relation.py
from science_model.profiles.core import CORE_PROFILE
from science_model.relations import build_relation_registry, relation_allows_kinds


def test_produced_by_allows_dataset_and_data_package_to_code_file() -> None:
    registry = build_relation_registry(CORE_PROFILE.relation_kinds)
    produced_by = registry["produced_by"]
    assert relation_allows_kinds(produced_by, "dataset", "code-file")
    assert relation_allows_kinds(produced_by, "data-package", "code-file")
    # The pre-existing run-producer pairing must still be permitted.
    assert relation_allows_kinds(produced_by, "data-package", "workflow-run")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science/model && uv run pytest tests/test_produced_by_relation.py -v`
Expected: FAIL — `relation_allows_kinds(produced_by, "dataset", "code-file")` is `False` (current `source_kinds=["data-package"]`, `target_kinds=["workflow-run"]`).

- [ ] **Step 3: Edit the relation kind**

In `science/model/src/science_model/profiles/core.py`, replace the `produced_by` RelationKind:

```python
        RelationKind(
            name="produced_by",
            predicate="sci:producedBy",
            source_kinds=["data-package", "dataset"],
            target_kinds=["workflow-run", "code-file"],
            layer="layer/core",
            description="A data artifact was produced by a workflow run or by code.",
        ),
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd science/model && uv run pytest tests/test_produced_by_relation.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/model/src/science_model/profiles/core.py science/model/tests/test_produced_by_relation.py
git commit -m "feat(model): allow produced_by to target code-file"
```

---

### Task 2: Add the code-only `produced_by` field to the entity model + frontmatter

**Files:**
- Modify: `science/model/src/science_model/entities.py` (base `Entity`, near `consumed_by` at line ~280)
- Modify: `science/model/src/science_model/frontmatter.py` (entity_kwargs, near `consumed_by` at line ~348)
- Test: `science/model/tests/test_produced_by_field.py` (create)

- [ ] **Step 1: Write the failing test**

```python
# science/model/tests/test_produced_by_field.py
from pathlib import Path

import pytest

from science_model.entities import Entity, core_entity_type_for_kind
from science_model.frontmatter import parse_entity_file


def _write(p: Path, text: str) -> Path:
    p.write_text(text, encoding="utf-8")
    return p


def _base_kwargs(kind: str, id_: str) -> dict:
    # Include `type` so the entity passes the kind/type-consistency validator;
    # otherwise the test depends on validator ordering to surface the
    # produced_by error before the type-mismatch error.
    return dict(
        id=id_, kind=kind, type=core_entity_type_for_kind(kind), title="X", project="demo",
        ontology_terms=[], related=[], source_refs=[], content_preview="", file_path=f"doc/{kind}/x.md",
    )


def test_produced_by_parsed_from_frontmatter(tmp_path: Path) -> None:
    md = _write(
        tmp_path / "d.md",
        "---\n"
        "id: dataset:x\n"
        "kind: dataset\n"
        "title: X\n"
        "status: active\n"
        "produced_by:\n"
        "  - code-file:stages/run.py\n"
        "---\nbody\n",
    )
    entity = parse_entity_file(md, project_slug="demo")
    assert entity.produced_by == ["code-file:stages/run.py"]


def test_produced_by_defaults_empty(tmp_path: Path) -> None:
    md = _write(
        tmp_path / "d.md",
        "---\nid: dataset:y\nkind: dataset\ntitle: Y\nstatus: active\n---\nbody\n",
    )
    entity = parse_entity_file(md, project_slug="demo")
    assert entity.produced_by == []


def test_produced_by_rejected_on_non_data_artifact() -> None:
    with pytest.raises(ValueError, match="dataset/data-package"):
        Entity(**_base_kwargs("hypothesis", "hypothesis:h1"), produced_by=["code-file:x.py"])


def test_produced_by_must_be_code_file_refs() -> None:
    with pytest.raises(ValueError, match="code-file:"):
        Entity(**_base_kwargs("dataset", "dataset:x"), produced_by=["workflow-run:wf-r1"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science/model && uv run pytest tests/test_produced_by_field.py -v`
Expected: FAIL — `Entity` has no attribute / kwarg `produced_by`.

> If `parse_entity_file`'s exact signature differs, mirror the call style used in the existing `science/model/tests/` frontmatter tests; the assertions on `.produced_by` are what matters.

- [ ] **Step 3: Add the field and parse it**

In `science/model/src/science_model/entities.py`, in the base `Entity` class, add directly **after** the `consumed_by` field (line ~280):

```python
    consumed_by: list[str] = Field(default_factory=list)
    produced_by: list[str] = Field(default_factory=list)
```

Also add a base `Entity` validator (next to the other `Entity` `@model_validator`s) so the rule holds for **every** kind — not just `DatasetEntity` — including `data-package` and any generic entity:

```python
    @model_validator(mode="after")
    def _validate_produced_by(self) -> "Entity":
        if not self.produced_by:
            return self
        if self.kind not in ("dataset", "data-package"):
            raise ValueError(f"produced_by is only allowed on dataset/data-package entities, not {self.kind!r}")
        for ref in self.produced_by:
            if not ref.startswith("code-file:"):
                raise ValueError(f"produced_by entries must be code-file:<id> references, got {ref!r}")
        return self
```

In `science/model/src/science_model/frontmatter.py`, in the `entity_kwargs` dict, add directly **after** the `consumed_by` entry (line ~348):

```python
        "consumed_by": list(fm.get("consumed_by") or []),
        "produced_by": list(fm.get("produced_by") or []),
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd science/model && uv run pytest tests/test_produced_by_field.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/model/src/science_model/entities.py science/model/src/science_model/frontmatter.py science/model/tests/test_produced_by_field.py
git commit -m "feat(model): add produced_by field parsed from frontmatter"
```

---

### Task 3: Add `produced_by` to the JSON schema + the datapackage adapter

**Files:**
- Modify: `science/model/src/science_model/schemas/science-pkg-entity-1.0.json`
- Modify: `science/src/science_tool/graph/storage_adapters/datapackage.py:15-37`
- Test: `science/model/tests/test_science_pkg_schema.py` (add), `science/tests/test_datapackage_adapter_produced_by.py` (create)

- [ ] **Step 1: Write the failing tests**

Add to `science/model/tests/test_science_pkg_schema.py`:

```python
def test_produced_by_code_ref_validates(entity_schema: dict) -> None:
    # Task 3 only adds the produced_by property; the derived branch still
    # requires `derivation` until Task 4. Keep derivation present here.
    entity = _valid_derived_entity()
    entity["produced_by"] = ["code-file:stages/run.py"]
    jsonschema.validate(entity, entity_schema)


def test_produced_by_workflow_run_ref_rejected(entity_schema: dict) -> None:
    entity = _valid_derived_entity()
    entity["produced_by"] = ["workflow-run:wf-r1"]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(entity, entity_schema)
```

Create `science/tests/test_datapackage_adapter_produced_by.py`:

```python
from pathlib import Path

from science_model.source_ref import SourceRef

from science_tool.graph.storage_adapters.datapackage import DatapackageAdapter


def test_adapter_surfaces_produced_by(tmp_path: Path) -> None:
    dp = tmp_path / "data" / "x" / "datapackage.yaml"
    dp.parent.mkdir(parents=True)
    dp.write_text(
        "profiles: [science-pkg-entity-1.0]\n"
        "id: dataset:x\n"
        "type: dataset\n"
        "title: X\n"
        "status: active\n"
        "origin: derived\n"
        "tier: use-now\n"
        "produced_by: [code-file:stages/run.py]\n",
        encoding="utf-8",
    )
    raw = DatapackageAdapter().load_raw(SourceRef(adapter_name="datapackage", path=str(dp)))
    assert raw["produced_by"] == ["code-file:stages/run.py"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd science/model && uv run pytest tests/test_science_pkg_schema.py -k produced_by -v`
Run: `cd science && uv run pytest tests/test_datapackage_adapter_produced_by.py -v`
Expected: schema test — `test_produced_by_workflow_run_ref_rejected` does NOT raise (no `produced_by` constraint yet); adapter test — `KeyError`/missing `produced_by` (not in `_ENTITY_FIELDS`).

- [ ] **Step 3: Add the schema property and the adapter field**

In `science/model/src/science_model/schemas/science-pkg-entity-1.0.json`, add to `properties` (after `"related"`):

```json
    "produced_by": {"type": "array", "items": {"type": "string", "pattern": "^code-file:"}, "minItems": 1},
```

In `science/src/science_tool/graph/storage_adapters/datapackage.py`, add `"produced_by",` to `_ENTITY_FIELDS` (after `"consumed_by",`):

```python
    "consumed_by",
    "produced_by",
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science/model && uv run pytest tests/test_science_pkg_schema.py -k produced_by -v`
Run: `cd science && uv run pytest tests/test_datapackage_adapter_produced_by.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/model/src/science_model/schemas/science-pkg-entity-1.0.json science/src/science_tool/graph/storage_adapters/datapackage.py science/model/tests/test_science_pkg_schema.py science/tests/test_datapackage_adapter_produced_by.py
git commit -m "feat: surface code-only produced_by in schema and datapackage adapter"
```

---

### Task 4: Relax the derived-dataset invariant (derivation OR code provenance); forbid produced_by on external

**Files:**
- Modify: `science/model/src/science_model/entities.py:543-563` (`_enforce_dataset_invariants`)
- Modify: `science/model/src/science_model/schemas/science-pkg-entity-1.0.json` (`allOf`)
- Test: `science/model/tests/test_dataset_models.py` (add), `science/model/tests/test_science_pkg_schema.py` (add)

- [ ] **Step 1: Write the failing tests**

Add to `science/model/tests/test_dataset_models.py` (uses the existing `_entity_kwargs`, `_ext_access`, `_der_block` helpers in that file):

```python
def test_derived_with_produced_by_no_derivation_is_valid() -> None:
    ds = DatasetEntity(**_entity_kwargs(), origin="derived", produced_by=["code-file:stages/run.py"])
    assert ds.produced_by == ["code-file:stages/run.py"]


def test_derived_with_neither_derivation_nor_produced_by_rejects() -> None:
    with pytest.raises(ValueError, match="derivation or produced_by"):
        DatasetEntity(**_entity_kwargs(), origin="derived")


def test_external_with_produced_by_rejects() -> None:
    with pytest.raises(ValueError, match="produced_by"):
        DatasetEntity(**_entity_kwargs(), origin="external", access=_ext_access(), produced_by=["code-file:x.py"])


def test_derived_with_empty_produced_by_rejects() -> None:
    # Empty list is not a provenance path; with no derivation this must fail.
    with pytest.raises(ValueError, match="derivation or produced_by"):
        DatasetEntity(**_entity_kwargs(), origin="derived", produced_by=[])
```

(The code-only-refs rule is now exercised by the base-Entity tests in Task 2.)

Add to `science/model/tests/test_science_pkg_schema.py`:

```python
def test_derived_with_produced_by_no_derivation_validates(entity_schema: dict) -> None:
    # The relaxed `origin: derived` branch (anyOf) accepts code provenance alone.
    entity = _valid_derived_entity()
    entity.pop("derivation")
    entity["produced_by"] = ["code-file:stages/run.py"]
    jsonschema.validate(entity, entity_schema)


def test_external_with_produced_by_rejected(entity_schema: dict) -> None:
    entity = _valid_external_entity()
    entity["produced_by"] = ["code-file:x.py"]
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(entity, entity_schema)


def test_produced_by_empty_list_rejected(entity_schema: dict) -> None:
    # minItems:1 rejects []; with no derivation the derived branch also fails.
    entity = _valid_derived_entity()
    entity.pop("derivation")
    entity["produced_by"] = []
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(entity, entity_schema)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd science/model && uv run pytest tests/test_dataset_models.py tests/test_science_pkg_schema.py -v`
Expected: the four new `test_dataset_models` cases FAIL (derived currently *requires* `derivation`, and the invariant neither accepts `produced_by` as a provenance path nor forbids it on external). Of the three new schema cases, two FAIL — `test_derived_with_produced_by_no_derivation_validates` (derived still requires `derivation`) and `test_external_with_produced_by_rejected` (schema doesn't yet forbid `produced_by` on external). The third, `test_produced_by_empty_list_rejected`, already *passes* before the change for an incidental reason — popping `derivation` makes the still-strict derived branch raise before `minItems` matters; after the relaxation it passes for the intended reason (`minItems: 1` rejects `[]`). (Pre-existing tests still pass.)

- [ ] **Step 3: Edit the invariant and the schema**

In `science/model/src/science_model/entities.py`, replace the body of `_enforce_dataset_invariants`:

```python
    @model_validator(mode="after")
    def _enforce_dataset_invariants(self) -> "DatasetEntity":
        """Invariants #7/#8: origin ⟺ which provenance applies.

        (produced_by is constrained to code-file refs and to dataset/data-package
        kinds by the base Entity validator added in Task 2; here we only enforce
        the origin-specific rules.)

        external: access required; no derivation, no produced_by (raw input
        cannot claim code produced it).
        derived: at least one provenance path — a derivation block and/or
        non-empty code-only produced_by; no access/accessions/local_path.
        """
        if self.origin is None:
            return self
        if self.origin == "external":
            if self.access is None:
                raise ValueError(f"{self.id}: origin=external requires an access block (invariant #7)")
            if self.derivation is not None:
                raise ValueError(f"{self.id}: origin=external must not carry a derivation block (invariant #7)")
            if self.produced_by:
                raise ValueError(f"{self.id}: origin=external must not carry produced_by (invariant #7)")
        elif self.origin == "derived":
            if self.derivation is None and not self.produced_by:
                raise ValueError(f"{self.id}: origin=derived requires a derivation or produced_by block (invariant #8)")
            if self.access is not None:
                raise ValueError(f"{self.id}: origin=derived must not carry an access block (invariant #8)")
            if self.accessions:
                raise ValueError(f"{self.id}: origin=derived must not carry accessions (invariant #8)")
            if self.local_path:
                raise ValueError(f"{self.id}: origin=derived must not carry local_path (invariant #8)")
        else:
            raise ValueError(f"{self.id}: origin must be 'external' or 'derived', got {self.origin!r}")
        return self
```

In `science/model/src/science_model/schemas/science-pkg-entity-1.0.json`, replace the `allOf` block:

```json
  "allOf": [
    {
      "if": {"properties": {"origin": {"const": "external"}}},
      "then": {
        "required": ["access"],
        "not": {"anyOf": [{"required": ["derivation"]}, {"required": ["produced_by"]}]}
      }
    },
    {
      "if": {"properties": {"origin": {"const": "derived"}}},
      "then": {
        "anyOf": [{"required": ["derivation"]}, {"required": ["produced_by"]}],
        "not": {"anyOf": [{"required": ["access"]}, {"required": ["accessions"]}, {"required": ["local_path"]}]}
      }
    }
  ],
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science/model && uv run pytest tests/test_dataset_models.py tests/test_science_pkg_schema.py -v`
Expected: PASS (including the pre-existing dataset/schema tests — the `external requires access` / `derived requires …` paths still hold).

- [ ] **Step 5: Commit**

```bash
git add science/model/src/science_model/entities.py science/model/src/science_model/schemas/science-pkg-entity-1.0.json science/model/tests/test_dataset_models.py science/model/tests/test_science_pkg_schema.py
git commit -m "feat(model): derived datasets may use code provenance; external forbids produced_by"
```

---

### Task 5: Branch `_derived_readiness` for code-provenance-only datasets

**Files:**
- Modify: `science/model/src/science_model/entities.py:597-606` (`_derived_readiness`)
- Test: `science/model/tests/test_dataset_models.py` (add)

- [ ] **Step 1: Write the failing test**

Add to `science/model/tests/test_dataset_models.py`:

```python
def test_code_provenance_derived_readiness_is_ready() -> None:
    ds = DatasetEntity(**_entity_kwargs(), origin="derived", produced_by=["code-file:stages/run.py"])
    r = ds.readiness()  # no resolver needed for code provenance
    assert r.ready is True
    assert r.state == "derived-via-code"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science/model && uv run pytest tests/test_dataset_models.py -k code_provenance_derived_readiness -v`
Expected: FAIL — `_derived_readiness` returns `unknown` (no resolver) or `missing-derivation-block`.

- [ ] **Step 3: Edit `_derived_readiness`**

In `science/model/src/science_model/entities.py`, replace `_derived_readiness`:

```python
    def _derived_readiness(self, resolver: ReadinessResolverProtocol | None) -> Readiness:
        if self.derivation is None:
            if self.produced_by:
                return Readiness(ready=True, state="derived-via-code")
            return Readiness(ready=False, state="missing-provenance")
        if resolver is None:
            return Readiness(
                ready=False,
                state="unknown",
                detail="derived dataset readiness requires resolver context",
            )
        return resolver.resolve_ref(self.derivation.workflow_run)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd science/model && uv run pytest tests/test_dataset_models.py -v`
Expected: PASS (pre-existing derivation-backed readiness tests still pass — the `derivation is not None` path is unchanged).

- [ ] **Step 5: Commit**

```bash
git add science/model/src/science_model/entities.py science/model/tests/test_dataset_models.py
git commit -m "feat(model): readiness for code-provenance-only derived datasets"
```

---

### Task 6: `CodeFileEntity` carries `decision_bearing: bool | None` + `executable`; CodeAdapter populates them

**Files:**
- Modify: `science/model/src/science_model/entities.py:627-638` (`CodeFileEntity`)
- Modify: `science/src/science_tool/graph/storage_adapters/code.py:46-69` (`load_raw`)
- Test: `science/tests/test_code_adapter.py` (add)
- Modify: `science/model/tests/test_typed_entities.py:130` (the existing default assertion changes from `False` to `None` — without this the model suite fails late)

- [ ] **Step 1: Write the failing test**

Add to `science/tests/test_code_adapter.py` (mirrors the existing `_adapter`/`load_raw` idiom there):

```python
def test_load_raw_decision_bearing_none_when_absent(tmp_path: Path) -> None:
    import os

    from science_model.source_ref import SourceRef

    (tmp_path / "code").mkdir()
    f = tmp_path / "code" / "run.py"
    f.write_text(
        '# science:code\n# status: workflow-owned\n# science:end\nif __name__ == "__main__":\n    pass\n',
        encoding="utf-8",
    )
    prev = os.getcwd()
    os.chdir(tmp_path)
    try:
        raw = _adapter(tmp_path).load_raw(SourceRef(adapter_name="code-file", path="code/run.py"))
    finally:
        os.chdir(prev)
    assert raw["decision_bearing"] is None        # absent in block -> None (fail-closed default applied later)
    assert raw["executable"] is True              # has __main__ entrypoint
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && uv run pytest tests/test_code_adapter.py -k decision_bearing_none -v`
Expected: FAIL — `decision_bearing` is `False` (current `bool(fields.get("decision_bearing", False))`), and `executable` key is absent.

- [ ] **Step 3: Add the entity fields and populate them in the adapter**

In `science/model/src/science_model/entities.py`, replace `CodeFileEntity`'s fields:

```python
    decision_bearing: bool | None = None
    executable: bool = False
    task_ids: list[str] = Field(default_factory=list)
```

In `science/src/science_tool/graph/storage_adapters/code.py`, add the import at the top (with the other `science_tool.code` imports):

```python
from science_tool.code.classification import is_executable
```

Then in `load_raw`, capture the text once and set the two fields. Replace the body from the `metadata = …` line through the `return {…}`:

```python
    def load_raw(self, ref: SourceRef) -> dict[str, Any]:
        path = Path(ref.path)
        abs_path = path if path.is_absolute() else Path.cwd() / path
        text = abs_path.read_text(errors="replace")
        metadata = parse_code_metadata(text)
        if not metadata.valid:
            # absent OR invalid block -> no kind -> skipped by the loader.
            # Plan B distinguishes the two (ghost vs malformed) via metadata.error.
            return {"file_path": ref.path}
        fields = metadata.fields or {}
        local_id = self._local_id(ref.path)
        canonical_id = f"code-file:{local_id}"
        raw_task_ids = fields.get("task_ids")
        declared = fields.get("decision_bearing")
        return {
            "id": canonical_id,
            "canonical_id": canonical_id,
            "kind": "code-file",
            "title": local_id,
            "status": str(fields.get("status") or ""),
            "decision_bearing": declared if isinstance(declared, bool) else None,
            "executable": is_executable(ref.path, text),
            "task_ids": [str(t) for t in raw_task_ids] if isinstance(raw_task_ids, list) else [],
            "updated": last_content_change_date(ref.path, repo_root=self._repo_root),
            "content_preview": "",
            "file_path": ref.path,
        }
```

- [ ] **Step 4: Update the existing model default assertion**

In `science/model/tests/test_typed_entities.py`, in `test_code_file_entity_defaults_and_fields`, change the default assertion (the new default is `None`, and assert the new `executable` default):

```python
    cf = CodeFileEntity(**_minimal(EntityType.CODE_FILE, "code-file:stages/run.py"))
    assert isinstance(cf, ProjectEntity)
    assert cf.decision_bearing is None
    assert cf.executable is False
    assert cf.task_ids == []
```

- [ ] **Step 5: Run tests (both packages) to verify they pass**

Run: `cd science && uv run pytest tests/test_code_adapter.py -v`
Run: `cd science/model && uv run pytest tests/test_typed_entities.py -v`
Expected: PASS. The adapter's `test_load_raw_builds_code_file_record` still passes (`decision_bearing: true` in its block → `True`); the model default test now asserts `None`/`False`.

> If any other test asserts an absent-block file gets `decision_bearing is False`, update it to `is None` — this is the intended Plan-B-adjacent change.

- [ ] **Step 6: Commit**

```bash
git add science/model/src/science_model/entities.py science/src/science_tool/graph/storage_adapters/code.py science/tests/test_code_adapter.py science/model/tests/test_typed_entities.py
git commit -m "feat: code-file carries decision_bearing None-when-absent + executable"
```

---

### Task 7: Tool-path → code-file canonical-id normalizer

**Role/consumer (explicit):** This is a **migration/authoring helper**, not on the runtime materialization path (`produced_by` stores canonical `code-file:` ids directly, resolved by entity-index lookup in Task 9). It is the canonical implementation of the §5 id-normalization rule, consumed by the MM30 datapackage migration (out of C's code scope) and referenced from the conventions doc in Task 12. Shipping it tested de-risks the id-mismatch the review flagged.

**Files:**
- Create: `science/src/science_tool/code/provenance.py`
- Test: `science/tests/code/test_provenance_normalizer.py` (create; the `tests/code/` dir has no `__init__.py` by design)

- [ ] **Step 1: Write the failing test**

```python
# science/tests/code/test_provenance_normalizer.py
from science_tool.code.provenance import code_file_id_from_tool_path


def test_strips_function_suffix_and_code_root() -> None:
    assert (
        code_file_id_from_tool_path("scripts/signatures/build.py::build_combined_corpus", code_root_names=("scripts",))
        == "code-file:signatures/build.py"
    )


def test_no_function_suffix_and_code_root() -> None:
    assert code_file_id_from_tool_path("code/stages/run.py", code_root_names=("code",)) == "code-file:stages/run.py"


def test_path_outside_declared_roots_kept_whole() -> None:
    assert code_file_id_from_tool_path("misc/run.py", code_root_names=("code",)) == "code-file:misc/run.py"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && uv run pytest tests/code/test_provenance_normalizer.py -v`
Expected: FAIL — module `science_tool.code.provenance` does not exist.

- [ ] **Step 3: Implement the normalizer**

```python
# science/src/science_tool/code/provenance.py
"""Normalize an MM30-style provenance tool reference to a code-file canonical id.

A tool reference like ``scripts/signatures/build.py::build_combined_corpus`` becomes
``code-file:signatures/build.py``: the ``::function`` suffix is dropped, the declared
code-root prefix is stripped (matching CodeAdapter._local_id), and the ``code-file:``
prefix is added. This mirrors how CodeAdapter assigns code-file ids so authored
``produced_by`` refs line up with the registered entities.
"""

from __future__ import annotations


def code_file_id_from_tool_path(tool_path: str, *, code_root_names: tuple[str, ...]) -> str:
    path = tool_path.split("::", 1)[0].strip()
    for root in code_root_names:
        prefix = f"{root}/"
        if path == root:
            path = path.rsplit("/", 1)[-1]
            break
        if path.startswith(prefix):
            path = path[len(prefix) :]
            break
    return f"code-file:{path}"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd science && uv run pytest tests/code/test_provenance_normalizer.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/code/provenance.py science/tests/code/test_provenance_normalizer.py
git commit -m "feat(code): tool-path to code-file id normalizer"
```

---

### Task 8: The `bears_on` deriver for `produced_by` code edges

**Files:**
- Modify: `science/src/science_tool/graph/freshness.py` (add a new deriver beside the others)
- Test: `science/tests/test_produced_by_bears_on.py` (create)

- [ ] **Step 1: Write the failing test**

```python
# science/tests/test_produced_by_bears_on.py
from rdflib import Dataset, URIRef

from science_tool.graph.freshness import derive_bears_on_from_produced_by_code
from science_tool.graph.store import PROJECT_NS, SCI_NS


def _u(local: str) -> URIRef:
    return URIRef(PROJECT_NS[local])


def _bears_on_pairs(ds: Dataset) -> set[tuple[str, str]]:
    knowledge = ds.graph(PROJECT_NS["graph/knowledge"])
    return {(str(s), str(o)) for s, _, o in knowledge.triples((None, SCI_NS.bearsOn, None))}


def _ds_with_produced_by() -> Dataset:
    ds = Dataset()
    knowledge = ds.graph(PROJECT_NS["graph/knowledge"])
    knowledge.add((_u("dataset/d1"), SCI_NS.producedBy, _u("code-file/run.py")))
    return ds


def test_eligible_code_file_bears_on_dataset() -> None:
    ds = _ds_with_produced_by()
    derive_bears_on_from_produced_by_code(ds, eligible_code_files={_u("code-file/run.py")})
    assert (str(_u("code-file/run.py")), str(_u("dataset/d1"))) in _bears_on_pairs(ds)


def test_ineligible_code_file_emits_nothing() -> None:
    ds = _ds_with_produced_by()
    derive_bears_on_from_produced_by_code(ds, eligible_code_files=set())
    assert _bears_on_pairs(ds) == set()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && uv run pytest tests/test_produced_by_bears_on.py -v`
Expected: FAIL — `derive_bears_on_from_produced_by_code` does not exist.

- [ ] **Step 3: Implement the deriver**

In `science/src/science_tool/graph/freshness.py`, add after `derive_bears_on_from_provenance` (and add the function name to the module docstring's "Public surface" list):

```python
def derive_bears_on_from_produced_by_code(
    dataset: Dataset,
    *,
    eligible_code_files: set[URIRef],
) -> None:
    """Emit `bears_on` from `sci:producedBy` code edges (Plan C).

    Rule: `?dataset sci:producedBy ?code_file` -> `?code_file bears_on ?dataset`,
    only when `?code_file` is propagation-eligible (decision-bearing, fail-closed;
    set built by the materializer). Operational data artifacts are valid direct
    bears_on conduit targets; `close_bears_on` walks through them to epistemic
    findings.
    """
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
    for dataset_uri, _, code_uri in knowledge.triples((None, SCI_NS.producedBy, None)):
        if not isinstance(dataset_uri, URIRef) or not isinstance(code_uri, URIRef):
            continue
        if code_uri not in eligible_code_files:
            continue
        knowledge.add((code_uri, SCI_NS.bearsOn, dataset_uri))
        _emit_bears_on_edge(knowledge, code_uri, dataset_uri, 1)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd science && uv run pytest tests/test_produced_by_bears_on.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/graph/freshness.py science/tests/test_produced_by_bears_on.py
git commit -m "feat(graph): derive bears_on from produced_by code edges"
```

---

### Task 9: Materialize `sci:producedBy` (lenient) + build the eligible set + wire the deriver

**Files:**
- Modify: `science/src/science_tool/graph/materialize.py` (add `_add_produced_by_edges`, `_eligible_code_files`; call them in `_build_dataset_from_sources`; thread `eligible_code_files` through `_derive_bears_on_layer`)
- Test: `science/tests/test_produced_by_materialize.py` (create)

- [ ] **Step 1: Write the failing test** (uses the verified temp-project idiom from `tests/test_code_sources_integration.py`)

```python
# science/tests/test_produced_by_materialize.py
import os
import subprocess
from pathlib import Path
from types import SimpleNamespace

from rdflib import URIRef

from science_model.entities import CodeFileEntity
from science_tool.graph.materialize import _build_dataset_from_sources, _eligible_code_files
from science_tool.graph.sources import load_project_sources
from science_tool.graph.store import PROJECT_NS, SCI_NS

_MANIFEST = (
    "name: demo\ncreated: 2026-01-01\nlast_modified: 2026-01-02\nstatus: active\n"
    "summary: demo\nprofile: research\nlayout_version: 1\n"
    "knowledge_profiles:\n  local: knowledge/local\n"
)


def _git(repo: Path, *args: str, env: dict | None = None) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True, env=env)


def _code(local_id: str, *, decision_bearing, executable: bool, status: str = "workflow-owned") -> CodeFileEntity:
    return CodeFileEntity(
        id=f"code-file:{local_id}",
        canonical_id=f"code-file:{local_id}",
        kind="code-file",
        title=local_id,
        project="demo",
        ontology_terms=[],
        related=[],
        source_refs=[],
        content_preview="",
        file_path=f"code/{local_id}",
        status=status,
        decision_bearing=decision_bearing,
        executable=executable,
    )


def test_eligible_code_files_matrix() -> None:
    entities = [
        _code("a.py", decision_bearing=True, executable=False),    # declared true -> eligible
        _code("b.py", decision_bearing=False, executable=True),    # declared false -> excluded
        _code("c.py", decision_bearing=None, executable=True),     # absent + executable -> eligible (fail-closed)
        _code("d.py", decision_bearing=None, executable=False),    # absent + non-executable library -> excluded
        _code("e.py", decision_bearing=True, executable=True, status="exploratory"),  # exempt -> excluded
        _code("f.py", decision_bearing=True, executable=True, status="retired"),      # exempt -> excluded
    ]
    eligible = _eligible_code_files(SimpleNamespace(entities=entities))
    assert eligible == {URIRef(PROJECT_NS["code-file/a.py"]), URIRef(PROJECT_NS["code-file/c.py"])}


def _project(tmp_path: Path) -> None:
    (tmp_path / "science.yaml").write_text(_MANIFEST, encoding="utf-8")
    (tmp_path / "knowledge" / "local").mkdir(parents=True)
    code = tmp_path / "code"
    code.mkdir()
    (code / "run.py").write_text(
        '# science:code\n# decision_bearing: true\n# status: workflow-owned\n# science:end\n'
        'if __name__ == "__main__":\n    pass\n',
        encoding="utf-8",
    )
    dp = tmp_path / "data" / "x" / "datapackage.yaml"
    dp.parent.mkdir(parents=True)
    dp.write_text(
        "profiles: [science-pkg-entity-1.0]\nid: dataset:x\ntype: dataset\ntitle: X\n"
        "status: active\norigin: derived\ntier: use-now\nproduced_by: [code-file:run.py]\n",
        encoding="utf-8",
    )
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "t@example.com")
    _git(tmp_path, "config", "user.name", "Tester")
    _git(tmp_path, "add", "-A")
    env = {**os.environ, "GIT_COMMITTER_DATE": "2026-04-01T00:00:00", "GIT_AUTHOR_DATE": "2026-04-01T00:00:00"}
    _git(tmp_path, "commit", "-m", "init", env=env)


def _bears_on_pairs(ds) -> set[tuple[str, str]]:
    knowledge = ds.graph(PROJECT_NS["graph/knowledge"])
    return {(str(s), str(o)) for s, _, o in knowledge.triples((None, SCI_NS.bearsOn, None))}


def test_decision_bearing_code_bears_on_its_dataset(tmp_path: Path) -> None:
    _project(tmp_path)
    prev = os.getcwd()
    os.chdir(tmp_path)
    try:
        sources = load_project_sources(tmp_path, include_commons=False)
        ds = _build_dataset_from_sources(sources)
    finally:
        os.chdir(prev)
    code_uri = str(URIRef(PROJECT_NS["code-file/run.py"]))
    dataset_uri = str(URIRef(PROJECT_NS["dataset/x"]))
    assert (code_uri, dataset_uri) in _bears_on_pairs(ds)


def test_produced_by_dangling_ref_does_not_raise(tmp_path: Path) -> None:
    _project(tmp_path)
    # Point produced_by at a code-file that has no block (ghost) -> skip-on-miss.
    dp = tmp_path / "data" / "x" / "datapackage.yaml"
    dp.write_text(dp.read_text().replace("code-file:run.py", "code-file:missing.py"), encoding="utf-8")
    prev = os.getcwd()
    os.chdir(tmp_path)
    try:
        sources = load_project_sources(tmp_path, include_commons=False)
        ds = _build_dataset_from_sources(sources)  # must not raise
    finally:
        os.chdir(prev)
    assert ds is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd science && uv run pytest tests/test_produced_by_materialize.py -v`
Expected: FAIL — `_eligible_code_files` does not exist yet (import error), and no `sci:producedBy`/`bears_on` edge is produced.

- [ ] **Step 3: Add the helpers and wire them**

In `science/src/science_tool/graph/materialize.py`, add the import (with the other `science_tool.code` / lifecycle imports near the top):

```python
from science_tool.code.lifecycle import ORPHAN_GATING_EXEMPT_STATUSES
from science_tool.graph.freshness import derive_bears_on_from_produced_by_code
```

Add two helpers (next to `_pre_registration_commitment_targets`):

```python
def _add_produced_by_edges(
    sources: ProjectSources,
    *,
    entity_index: dict[str, Entity],
    knowledge,
) -> None:
    """Materialize `sci:producedBy` from datasets' code-only `produced_by` field.

    Lenient: a ref that does not resolve to a registered code-file entity is
    skipped (surfaced by the `code.produced-by-unresolved` validate check),
    never a hard-fail — preserving the fragility firewall. Not routed through
    `audit_project_sources`.
    """
    for entity in sources.entities:
        if entity.kind not in ("dataset", "data-package"):
            continue  # produced_by is a data-artifact field (relation source kinds)
        for ref in getattr(entity, "produced_by", []) or []:
            target = entity_index.get(ref)
            if target is None or target.kind != "code-file":
                continue
            knowledge.add(
                (_entity_uri(entity.canonical_id), SCI_NS.producedBy, _entity_uri(target.canonical_id))
            )


def _eligible_code_files(sources: ProjectSources) -> set[URIRef]:
    """Code-file URIs whose edits propagate freshness: decision-bearing, fail-closed
    (un-annotated executable counts), exempting exploratory/retired."""
    eligible: set[URIRef] = set()
    for entity in sources.entities:
        if entity.kind != "code-file":
            continue
        if (entity.status or "") in ORPHAN_GATING_EXEMPT_STATUSES:
            continue
        declared = getattr(entity, "decision_bearing", None)
        effective = declared if declared is not None else getattr(entity, "executable", False)
        if effective:
            eligible.add(_entity_uri(entity.canonical_id))
    return eligible
```

`SCI_NS` is already imported in `materialize.py` (used elsewhere); if not, add it from `science_tool.graph.store`.

In `_build_dataset_from_sources`, after the `_add_relations` loop and before `kind_class = _classify_entities(sources)`, add:

```python
    _add_produced_by_edges(sources, entity_index=entity_index, knowledge=knowledge)
```

Then change the `_derive_bears_on_layer(...)` call to pass the eligible set:

```python
    _derive_bears_on_layer(
        dataset,
        kind_class=kind_class,
        pre_registration_targets=pre_registration_targets,
        eligible_code_files=_eligible_code_files(sources),
    )
```

And extend `_derive_bears_on_layer` to accept and use it:

```python
def _derive_bears_on_layer(
    dataset: Dataset,
    *,
    kind_class: dict[str, EntityClass],
    pre_registration_targets: dict[URIRef, list[URIRef]],
    eligible_code_files: set[URIRef],
) -> None:
    """Derive sci:bearsOn triples (typed-edge + provenance + produced_by + closure)."""
    derive_bears_on_from_typed_edges(dataset, kind_class=kind_class)
    derive_bears_on_from_chain_links(dataset)
    derive_bears_on_from_audits(dataset)
    derive_bears_on_from_pre_registrations(
        dataset,
        pre_registration_targets=pre_registration_targets,
        kind_class=kind_class,
    )
    derive_bears_on_from_provenance(dataset, kind_class=kind_class)
    derive_bears_on_from_produced_by_code(dataset, eligible_code_files=eligible_code_files)
    close_bears_on(dataset, kind_class=kind_class)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science && uv run pytest tests/test_produced_by_materialize.py -v`
Expected: PASS — the eligibility matrix, the bears_on edge, and the skip-on-miss-no-raise behavior.

- [ ] **Step 5: Run the broader graph suite for regressions**

Run: `cd science && uv run pytest tests/ -k "bears_on or materialize or freshness" -q`
Expected: PASS (any other `_derive_bears_on_layer` caller now passes `eligible_code_files`; grep for callers and update — there is one in `_build_dataset_from_sources`; the freshness in-memory sweep reuses `_build_dataset_from_sources`).

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/graph/materialize.py science/tests/test_produced_by_materialize.py
git commit -m "feat(graph): materialize produced_by edges and derive code->dataset bears_on"
```

---

### Task 10: Validate check `code.produced-by-unresolved` + hygiene gate

**Files:**
- Modify: `science/src/science_tool/validate/checks/code_files.py` (add the check function **here** — it is an already-imported check module, so the `@Check` decorator auto-registers the new check into `CANONICAL_CHECKS`; do **not** create a separate module the loader won't import)
- Modify: `science/src/science_tool/validate/gates.py:31-38`
- Test: `science/tests/validate/test_produced_by_check.py` (create), `science/tests/validate/test_gates.py` (add)

- [ ] **Step 1: Write the failing tests**

```python
# science/tests/validate/test_produced_by_check.py
from pathlib import Path

from science_tool.validate.checks.code_files import check_produced_by_unresolved
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Severity

_MANIFEST = (
    "name: demo\ncreated: 2026-01-01\nlast_modified: 2026-01-02\nstatus: active\n"
    "summary: demo\nprofile: research\nlayout_version: 1\n"
    "knowledge_profiles:\n  local: knowledge/local\n"
)


def _ctx(root: Path) -> ValidateContext:
    root.joinpath("science.yaml").write_text(_MANIFEST, encoding="utf-8")
    (root / "knowledge" / "local").mkdir(parents=True)
    return ValidateContext.from_project_root(root, strict=False, verbose=False)


def test_dangling_produced_by_is_flagged(tmp_path: Path) -> None:
    dp = tmp_path / "data" / "x" / "datapackage.yaml"
    dp.parent.mkdir(parents=True)
    dp.write_text(
        "profiles: [science-pkg-entity-1.0]\nid: dataset:x\ntype: dataset\ntitle: X\n"
        "status: active\norigin: derived\ntier: use-now\nproduced_by: [code-file:missing.py]\n",
        encoding="utf-8",
    )
    ctx = _ctx(tmp_path)
    results = list(check_produced_by_unresolved(ctx))
    assert len(results) == 1
    assert results[0].rule == "code.produced-by-unresolved"
    assert results[0].severity is Severity.WARN


def test_check_registered_in_canonical_checks() -> None:
    # Importing the module runs the @Check decorator, which appends to the
    # registry the CLI validate runner iterates. Proves the check is wired in,
    # not merely importable.
    import science_tool.validate.checks.code_files  # noqa: F401

    from science_tool.validate.checks import CANONICAL_CHECKS

    names = {entry.fn.__name__ for entry in CANONICAL_CHECKS}
    assert "check_produced_by_unresolved" in names
```

```python
# add to science/tests/validate/test_gates.py
from science_tool.validate.gates import cumulative_rules


def test_produced_by_unresolved_gated_at_hygiene() -> None:
    assert "code.produced-by-unresolved" in cumulative_rules("hygiene")
    assert "code.produced-by-unresolved" not in cumulative_rules("decision-bearing-orphans")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd science && uv run pytest tests/validate/test_produced_by_check.py tests/validate/test_gates.py -k produced_by -v`
Expected: FAIL — `check_produced_by_unresolved` does not exist; the rule is not in the hygiene tier.

- [ ] **Step 3: Implement the check and register the gate rule**

In `science/src/science_tool/validate/checks/code_files.py`, add (uses `load_project_sources` to inspect datasets' `produced_by` against registered code-file ids):

```python
from science_tool.graph.sources import load_project_sources


@Check(section="code provenance", order=7)
def check_produced_by_unresolved(ctx: ValidateContext) -> Iterator[Result]:
    """A dataset's produced_by ref that does not resolve to a registered code-file."""
    sources = load_project_sources(ctx.project_root, include_commons=False)
    code_ids = {e.canonical_id for e in sources.entities if e.kind == "code-file"}
    for entity in sources.entities:
        for ref in getattr(entity, "produced_by", []) or []:
            if ref not in code_ids:
                yield _result(
                    Severity.WARN,
                    entity.file_path,
                    f"produced_by references unregistered code-file {ref!r}",
                    "code.produced-by-unresolved",
                )
```

> Confirm `ValidateContext` exposes `project_root` (used elsewhere in this module via `resolve_paths(ctx...)`); if the accessor differs, use the same one the sibling checks use.

In `science/src/science_tool/validate/gates.py`, add the rule to the hygiene tier:

```python
    "hygiene": frozenset(
        {
            "code.metadata-gap",
            "code.unresolved-task",
            "code.uncommitted",
            "code.hardcoded-path",
            "code.produced-by-unresolved",
        }
    ),
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd science && uv run pytest tests/validate/test_produced_by_check.py tests/validate/test_gates.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/validate/checks/code_files.py science/src/science_tool/validate/gates.py science/tests/validate/test_produced_by_check.py science/tests/validate/test_gates.py
git commit -m "feat(validate): flag unresolved produced_by refs and gate at hygiene"
```

---

### Task 11: End-to-end — a decision-bearing code edit flips a downstream finding to needs-review

**Files:**
- Test: `science/tests/test_produced_by_freshness_e2e.py` (create)

This is an integration test only (no new source). It proves the headline guarantee end-to-end: `code-file --produced_by--> dataset` + `finding --source_refs--> dataset` ⇒ `code-file bears_on finding` (closure) ⇒ the finding's freshness flips to `needs-review` because the code file's last-commit `updated` is newer than the finding's baseline.

- [ ] **Step 1: Write the test**

```python
# science/tests/test_produced_by_freshness_e2e.py
import os
import subprocess
from pathlib import Path

from rdflib import Literal, URIRef

from science_tool.graph.materialize import _build_dataset_from_sources
from science_tool.graph.sources import load_project_sources
from science_tool.graph.store import PROJECT_NS, SCI_NS

_MANIFEST = (
    "name: demo\ncreated: 2026-01-01\nlast_modified: 2026-01-02\nstatus: active\n"
    "summary: demo\nprofile: research\nlayout_version: 1\n"
    "knowledge_profiles:\n  local: knowledge/local\n"
)


def _git(repo: Path, *args: str, env: dict | None = None) -> None:
    subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True, env=env)


def test_code_edit_flips_finding_to_needs_review(tmp_path: Path) -> None:
    (tmp_path / "science.yaml").write_text(_MANIFEST, encoding="utf-8")
    local = tmp_path / "knowledge" / "local"
    local.mkdir(parents=True)
    (tmp_path / "code").mkdir()
    (tmp_path / "code" / "run.py").write_text(
        '# science:code\n# decision_bearing: true\n# status: workflow-owned\n# science:end\n'
        'if __name__ == "__main__":\n    pass\n',
        encoding="utf-8",
    )
    dp = tmp_path / "data" / "x" / "datapackage.yaml"
    dp.parent.mkdir(parents=True)
    dp.write_text(
        "profiles: [science-pkg-entity-1.0]\nid: dataset:x\ntype: dataset\ntitle: X\n"
        "status: active\norigin: derived\ntier: use-now\nproduced_by: [code-file:run.py]\n",
        encoding="utf-8",
    )
    # A finding reviewed in January, citing the dataset as a source.
    # Markdown entities are scanned under doc/ (MarkdownAdapter default roots:
    # ["doc", "specs", "research/packages"]) — NOT knowledge/local, which is for
    # aggregate YAML sources.
    findings = tmp_path / "doc" / "findings"
    findings.mkdir(parents=True)
    (findings / "f1.md").write_text(
        "---\nid: finding:f1\nkind: finding\ntitle: F1\nstatus: active\n"
        "created: 2026-01-01\nsource_refs:\n  - dataset:x\n"
        "review_state:\n  last_reviewed: 2026-01-15\n---\nbody\n",
        encoding="utf-8",
    )
    _git(tmp_path, "init")
    _git(tmp_path, "config", "user.email", "t@example.com")
    _git(tmp_path, "config", "user.name", "Tester")
    _git(tmp_path, "add", "-A")
    # Code file's last content-changing commit is in April — newer than the finding's baseline.
    env = {**os.environ, "GIT_COMMITTER_DATE": "2026-04-01T00:00:00", "GIT_AUTHOR_DATE": "2026-04-01T00:00:00"}
    _git(tmp_path, "commit", "-m", "init", env=env)

    prev = os.getcwd()
    os.chdir(tmp_path)
    try:
        sources = load_project_sources(tmp_path, include_commons=False)
        ds = _build_dataset_from_sources(sources)
    finally:
        os.chdir(prev)

    knowledge = ds.graph(PROJECT_NS["graph/knowledge"])
    code_uri = URIRef(PROJECT_NS["code-file/run.py"])
    finding_uri = URIRef(PROJECT_NS["finding/f1"])

    # Closure: code-file bears_on finding (through the operational dataset conduit).
    pairs = {(str(s), str(o)) for s, _, o in knowledge.triples((None, SCI_NS.bearsOn, None))}
    assert (str(code_uri), str(finding_uri)) in pairs

    # Freshness: the finding flips to needs-review, triggered by the code file.
    assert (finding_uri, SCI_NS.freshnessState, Literal("needs-review")) in knowledge
    assert (finding_uri, SCI_NS.triggeredBy, code_uri) in knowledge
```

- [ ] **Step 2: Run the test**

Run: `cd science && uv run pytest tests/test_produced_by_freshness_e2e.py -v`
Expected: PASS. (If the finding frontmatter shape — `review_state.last_reviewed`, `source_refs` — needs adjusting to match the loader, align it with an existing finding fixture under `science/tests/`; the three assertions are the contract.)

- [ ] **Step 3: Commit**

```bash
git add science/tests/test_produced_by_freshness_e2e.py
git commit -m "test(graph): code edit propagates to finding via produced_by (e2e)"
```

---

### Task 12: Document the contract in docs/conventions

**Files:**
- Modify: `docs/conventions/validate.md` (repo-root `docs/`, the file B2 extended — add the `code.produced-by-unresolved` rule row + hygiene-tier note + a "Code provenance (`produced_by`)" subsection)

- [ ] **Step 1: Add the rule row + provenance section**

In the validate conventions doc, add a rule-table row:

```markdown
| `code.produced-by-unresolved` | WARN | hygiene | A `dataset`'s `produced_by` references a code-file id that is not a registered code-file entity. |
```

Add a short "Code provenance (`produced_by`)" subsection documenting:
- A `dataset` declares the decision-bearing code that produced it via a **code-only** `produced_by: [code-file:<local-id>]` field (authored at the artifact).
- A derived dataset may use `produced_by` **instead of** a `derivation` block (no `workflow_run` required); an external dataset must not carry `produced_by`.
- `produced_by` derives `code-file bears_on dataset` (decision-bearing, fail-closed; `exploratory`/`retired` exempt), so a code edit propagates to findings that cite the dataset via `source_refs`/`evidence_refs`.
- Authoring ids: drop any `::function` suffix and the declared code-root prefix (e.g. tool `scripts/sig/build.py::fn` with code root `scripts/` → `code-file:sig/build.py`), implemented by the helper `science_tool.code.provenance.code_file_id_from_tool_path` (Task 7) for migration tooling.

````markdown
```yaml
# data/derived/.../datapackage.yaml
profiles: [science-pkg-entity-1.0]
id: dataset:my-result
type: dataset
title: My result
status: active
origin: derived
tier: use-now
produced_by:
  - code-file:signatures/build_my_result.py
```
````

- [ ] **Step 2: Verify docs build / no broken links**

Run: `cd science && uv run pytest tests/ -k "docs or conventions" -q` (if such tests exist; otherwise visually confirm the table renders).
Expected: PASS / clean.

- [ ] **Step 3: Commit**

```bash
git add docs/conventions/validate.md
git commit -m "docs(conventions): document produced_by code-provenance edge"
```

---

## Final verification

- [ ] Run the full suites:
  - `cd science/model && uv run pytest -q`
  - `cd science && uv run pytest -q`
  Expected: green (modulo the documented `decision_bearing is None` test updates in Task 6).
- [ ] Confirm the acceptance behavior is exercised by Task 11 (code edit → finding `needs-review`).
- [ ] Hand off to `superpowers:finishing-a-development-branch`.

## Spec coverage map

| Spec (rev 3) section | Task |
|---|---|
| §3.1 produced_by modeled field (code-only) + adapter + relation kind | 1, 2, 3 |
| §3.1 lenient materialization (skip-on-miss) | 9 |
| §3.2 derived: derivation OR non-empty code produced_by; external forbids it; readiness | 4, 5 |
| §3.3 deriver + eligibility carrier (`eligible_code_files`) | 6, 8, 9 |
| §4 firewall + `code.produced-by-unresolved` (WARN, hygiene) | 9, 10 |
| §5 tool-path → code-file id normalization | 7 |
| §6 test matrix | 1–11 |
| §7 MM30 acceptance shape (fixture mirror) | 11 |
| docs | 12 |

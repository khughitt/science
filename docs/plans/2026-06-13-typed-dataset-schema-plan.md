# Typed Dataset Resource Schema + Science Profile — Implementation Plan (Spec 1)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish the typed Data Resource schema as the single source of truth for a dataset's shape and quality contract — Pydantic models (native Frictionless invariants + a tiny `qa:` distribution extension), an emitted offline `$schema` profile, and additive descriptor validation in `science datasets validate`.

**Architecture:** New module `science_tool/datasets/schema.py` holds Pydantic v2 models (the SSOT) with fail-fast `model_validator`s for all within-descriptor invariants, a pure `package_consistency_issues()` for cross-resource foreign-key checks, and `emit_profile()`/`--emit` to (re)generate the committed JSON Schema profile. `datasets/validate.py` gains an additive descriptor-validation pass that surfaces Pydantic errors as `fail` rows. `science_qa` is untouched (consumption = Spec 2).

**Tech Stack:** Python 3, Pydantic v2 (2.12.x, already a dep), `jsonschema` (already a dep, not needed here), Frictionless Data Package / Table Schema v2.

---

## Reference: spec

Design doc: `docs/plans/2026-06-13-typed-dataset-schema-design.md`. Read §3 (two zones = two severities), §4 (vocabulary), §5 (models), §6 (profile emission), §7 (validate integration), §8 (type-applicability boundary). This plan implements that design; where they differ, the design wins — but note one deliberate implementation choice below.

**Implementation choice (consistent with design §7/§8):** all *within-descriptor* self-consistency guardrails are implemented as Pydantic `model_validator`s (parse-time, fail-fast — they surface as `fail` rows automatically through `model_validate`). Only the *cross-resource* foreign-key resolution needs whole-package context, so it lives in a separate pure function `package_consistency_issues()`.

## Workspace, conventions & test recipe

**Workspace (execution-time):** implement in an isolated git worktree created **off local `main`** (NOT `feat/review-books`, which carries an unrelated workstream's WIP). The using-git-worktrees skill handles this. As a one-time setup before Task 1, copy the two spec docs into the worktree and commit them so the branch is self-contained:

```bash
# from the worktree root (off main):
cp ~/d/science/docs/plans/2026-06-13-typed-dataset-schema-design.md docs/plans/
cp ~/d/science/docs/plans/2026-06-13-typed-dataset-schema-plan.md   docs/plans/
git add docs/plans/2026-06-13-typed-dataset-schema-*.md
git commit -m "docs(typed-schema): add Spec 1 design + implementation plan"
```

**Test recipe (use for every test step).** The framework venv (`~/d/science/science/.venv`) has pydantic 2.12 + jsonschema; point `PYTHONPATH` at the worktree's `src` so imports resolve to the branch code:

```bash
cd <worktree>/science
PY=~/d/science/science/.venv/bin/python
PYTHONPATH=src $PY -m pytest tests/test_datasets_schema.py -v          # schema model tests
PYTHONPATH=src $PY -m pytest tests/test_datasets_validate.py -v        # integration tests
```

**Commit hygiene:** `git add` only the explicit files named in each task — never `-A`/`.` (the `.git` metadata is Dropbox-synced and an unrelated workstream may advance HEAD mid-session; staging everything risks capturing foreign changes). If you find conflict markers or changes in files outside your task's scope, STOP and report BLOCKED.

**No Co-Authored-By trailers** in commits. Use `~/d/` (not absolute Dropbox paths) in any doc/code text.

## File structure

| File | Responsibility |
|---|---|
| `science/src/science_tool/datasets/schema.py` (**create**) | Pydantic SSOT models + within-descriptor validators + `package_consistency_issues()` + `emit_profile()`/`write_profile()`/`--emit` |
| `science/src/science_tool/datasets/profiles/science-data-resource-v1.json` (**create, generated**) | Committed JSON Schema profile, emitted from the models; the `$schema` target |
| `science/src/science_tool/datasets/validate.py` (**modify**) | Add additive `_validate_resource_descriptors()` pass + call it from `validate_data_packages` |
| `science/tests/test_datasets_schema.py` (**create**) | Model unit tests, validators, cross-resource consistency, golden profile-emission |
| `science/tests/test_datasets_validate.py` (**modify**) | Integration tests for the new descriptor pass |

---

## Task 1: Field value models — `MissingValue`, `FieldConstraints`, `FieldQA`

**Files:**
- Create: `science/src/science_tool/datasets/schema.py`
- Test: `science/tests/test_datasets_schema.py`

- [ ] **Step 1: Write the failing tests**

Create `science/tests/test_datasets_schema.py`:

```python
"""Tests for the typed Data Resource schema models (Spec 1)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from science_tool.datasets.schema import FieldConstraints, FieldQA, MissingValue


class TestFieldValueModels:
    def test_missing_value_bare_and_labelled(self) -> None:
        assert MissingValue(value="NA").label == ""
        assert MissingValue(value="-999", label="sensor error").label == "sensor error"

    def test_constraints_defaults(self) -> None:
        c = FieldConstraints()
        assert c.required is False and c.unique is False
        assert c.minimum is None and c.enum is None

    def test_constraints_bounds_accept_str_int_float(self) -> None:
        c = FieldConstraints(minimum=0, maximum=1.0, exclusiveMinimum="2020-01-01")
        assert c.minimum == 0 and c.maximum == 1.0 and c.exclusiveMinimum == "2020-01-01"

    def test_constraints_extra_allowed(self) -> None:
        c = FieldConstraints.model_validate({"required": True, "futureProp": 7})
        assert c.required is True

    def test_enum_present_must_be_non_empty(self) -> None:
        FieldConstraints(enum=["a"])  # ok
        with pytest.raises(ValidationError, match="enum"):
            FieldConstraints(enum=[])

    def test_field_qa_defaults_and_closed_namespace(self) -> None:
        assert FieldQA().low_variance is False
        with pytest.raises(ValidationError):
            FieldQA.model_validate({"low_varianse": True})  # typo rejected (extra=forbid)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `PYTHONPATH=src $PY -m pytest tests/test_datasets_schema.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'science_tool.datasets.schema'`.

- [ ] **Step 3: Create the module with the three models**

Create `science/src/science_tool/datasets/schema.py`:

```python
"""Pydantic v2 models for the science Data Resource profile (Spec 1).

Native Frictionless Table Schema (invariants) + a small `qa:` extension
(distribution checks). Targets Data Package Standard v2 while accepting v1
compatibility forms for primaryKey and foreignKeys. These models are the single
source of truth; the published JSON Schema profile is emitted from them.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

PROFILE_MARKER = "science-data-resource/v1"
PROFILE_PATH = Path(__file__).parent / "profiles" / "science-data-resource-v1.json"

FrictionlessType = Literal[
    "string", "number", "integer", "boolean", "object", "array", "list",
    "datetime", "date", "time", "year", "yearmonth", "duration",
    "geopoint", "geojson", "any",
]

NUMERIC_TYPES = {"integer", "number"}
TEMPORAL_TYPES = {"date", "datetime", "time", "year", "yearmonth", "duration"}
QA_STAT_TYPES = {"integer", "number", "boolean"}
FLAG_TYPES = {"boolean", "integer"}


def _as_list(value: str | list[str]) -> list[str]:
    return [value] if isinstance(value, str) else list(value)


class MissingValue(BaseModel):
    """A null sentinel: a bare string, or a labelled object (DP v2)."""

    model_config = ConfigDict(extra="allow")
    value: str
    label: str = ""


class FieldConstraints(BaseModel):
    model_config = ConfigDict(extra="allow")
    required: bool = False
    unique: bool = False
    minimum: str | int | float | None = None
    maximum: str | int | float | None = None
    exclusiveMinimum: str | int | float | None = None
    exclusiveMaximum: str | int | float | None = None
    enum: list[object] | None = None
    pattern: str | None = None

    @model_validator(mode="after")
    def _enum_non_empty(self) -> "FieldConstraints":
        if self.enum is not None and len(self.enum) == 0:
            raise ValueError("enum, when present, must be non-empty")
        return self


class FieldQA(BaseModel):
    """The distribution-severity extension carried per field (closed namespace)."""

    model_config = ConfigDict(extra="forbid")
    low_variance: bool = False
    zero_fraction: bool = False
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `PYTHONPATH=src $PY -m pytest tests/test_datasets_schema.py -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/datasets/schema.py science/tests/test_datasets_schema.py
git commit -m "feat(typed-schema): field value models (MissingValue, FieldConstraints, FieldQA)"
```

---

## Task 2: `FieldSpec` with applicability validators

**Files:**
- Modify: `science/src/science_tool/datasets/schema.py`
- Test: `science/tests/test_datasets_schema.py`

- [ ] **Step 1: Write the failing tests**

Append to `science/tests/test_datasets_schema.py` (and add `FieldSpec` to the import from Task 1):

```python
from science_tool.datasets.schema import FieldSpec  # add to existing import line


class TestFieldSpec:
    def test_default_type_is_any(self) -> None:
        f = FieldSpec(name="x")
        assert f.type == "any"          # DP v2: omitted type ⇒ any, NOT string
        assert f.constraints.required is False
        assert f.qa.low_variance is False
        assert f.missingValues is None

    def test_field_level_missing_values_accepted(self) -> None:
        f = FieldSpec.model_validate({"name": "x", "type": "number", "missingValues": ["NA"]})
        assert f.missingValues == ["NA"]

    def test_bounds_require_numeric_or_temporal_type(self) -> None:
        FieldSpec(name="plddt", type="number", constraints={"minimum": 0, "maximum": 100})  # ok
        FieldSpec(name="d", type="date", constraints={"minimum": "2020-01-01"})              # ok
        with pytest.raises(ValidationError, match="numeric or temporal"):
            FieldSpec(name="s", type="string", constraints={"minimum": 0})

    def test_qa_stats_require_numeric_or_boolean_type(self) -> None:
        FieldSpec(name="n", type="integer", qa={"low_variance": True})                       # ok
        FieldSpec(name="b", type="boolean", qa={"zero_fraction": True})                      # ok
        with pytest.raises(ValidationError, match="integer/number/boolean"):
            FieldSpec(name="s", type="string", qa={"low_variance": True})

    def test_field_extra_allowed(self) -> None:
        f = FieldSpec.model_validate({"name": "x", "title": "X", "description": "d"})
        assert f.name == "x"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `PYTHONPATH=src $PY -m pytest tests/test_datasets_schema.py::TestFieldSpec -v`
Expected: FAIL — `ImportError: cannot import name 'FieldSpec'`.

- [ ] **Step 3: Add `FieldSpec` to the module**

Append to `science/src/science_tool/datasets/schema.py` (after `FieldQA`):

```python
class FieldSpec(BaseModel):
    model_config = ConfigDict(extra="allow")
    name: str
    type: FrictionlessType = "any"          # DP v2: omitted type ⇒ "any" (NOT "string")
    constraints: FieldConstraints = Field(default_factory=FieldConstraints)
    # Field-level missingValues override (DP v2) — accepted/round-tripped, but not
    # consumed until a later spec; table-level missingValues remains the primary path.
    missingValues: list[str | MissingValue] | None = None
    qa: FieldQA = Field(default_factory=FieldQA)

    @model_validator(mode="after")
    def _semantic_applicability(self) -> "FieldSpec":
        has_bound = any(
            getattr(self.constraints, b) is not None
            for b in ("minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum")
        )
        if has_bound and self.type not in (NUMERIC_TYPES | TEMPORAL_TYPES):
            raise ValueError(
                f"field {self.name!r}: bounds require a numeric or temporal type, "
                f"got {self.type!r}"
            )
        if (self.qa.low_variance or self.qa.zero_fraction) and self.type not in QA_STAT_TYPES:
            raise ValueError(
                f"field {self.name!r}: qa.low_variance/zero_fraction require an "
                f"integer/number/boolean type, got {self.type!r}"
            )
        return self
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `PYTHONPATH=src $PY -m pytest tests/test_datasets_schema.py -v`
Expected: PASS (11 tests total).

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/datasets/schema.py science/tests/test_datasets_schema.py
git commit -m "feat(typed-schema): FieldSpec with bounds/qa type-applicability validators"
```

---

## Task 3: Foreign keys — `ForeignKeyReference`, `ForeignKey`

**Files:**
- Modify: `science/src/science_tool/datasets/schema.py`
- Test: `science/tests/test_datasets_schema.py`

- [ ] **Step 1: Write the failing tests**

Append to `science/tests/test_datasets_schema.py` (add `ForeignKey` to imports):

```python
from science_tool.datasets.schema import ForeignKey  # add to existing import line


class TestForeignKey:
    def test_single_string_form(self) -> None:
        fk = ForeignKey.model_validate({"fields": "uniprot_id", "reference": {"resource": "proteins", "fields": "id"}})
        assert fk.fields == "uniprot_id"
        assert fk.reference.resource == "proteins"

    def test_self_reference_default_resource(self) -> None:
        fk = ForeignKey.model_validate({"fields": "parent_id", "reference": {"fields": "id"}})
        assert fk.reference.resource == ""          # "" ⇒ self

    def test_list_form_matched_cardinality(self) -> None:
        fk = ForeignKey.model_validate(
            {"fields": ["a", "b"], "reference": {"resource": "r", "fields": ["x", "y"]}}
        )
        assert fk.fields == ["a", "b"]

    def test_cardinality_mismatch_rejected(self) -> None:
        with pytest.raises(ValidationError, match="cardinality"):
            ForeignKey.model_validate(
                {"fields": ["a", "b"], "reference": {"resource": "r", "fields": "x"}}
            )
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `PYTHONPATH=src $PY -m pytest tests/test_datasets_schema.py::TestForeignKey -v`
Expected: FAIL — `ImportError: cannot import name 'ForeignKey'`.

- [ ] **Step 3: Add the foreign-key models**

Append to `science/src/science_tool/datasets/schema.py` (after `FieldSpec`):

```python
class ForeignKeyReference(BaseModel):
    model_config = ConfigDict(extra="allow")
    resource: str = ""                       # "" (or absent) = self-reference
    fields: str | list[str]


class ForeignKey(BaseModel):
    model_config = ConfigDict(extra="allow")
    fields: str | list[str]
    reference: ForeignKeyReference

    @model_validator(mode="after")
    def _cardinality(self) -> "ForeignKey":
        if len(_as_list(self.fields)) != len(_as_list(self.reference.fields)):
            raise ValueError(
                "foreignKey cardinality mismatch between fields and reference.fields"
            )
        return self
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `PYTHONPATH=src $PY -m pytest tests/test_datasets_schema.py -v`
Expected: PASS (15 tests total).

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/datasets/schema.py science/tests/test_datasets_schema.py
git commit -m "feat(typed-schema): foreignKey models with cardinality validator"
```

---

## Task 4: `TableQA` + `TableSchema` shape & self-validators

**Files:**
- Modify: `science/src/science_tool/datasets/schema.py`
- Test: `science/tests/test_datasets_schema.py`

- [ ] **Step 1: Write the failing tests**

Append to `science/tests/test_datasets_schema.py` (add `TableSchema, TableQA` to imports):

```python
from science_tool.datasets.schema import TableQA, TableSchema  # add to existing import line


def _fields(*names: str) -> list[dict]:
    return [{"name": n} for n in names]


class TestTableSchemaShape:
    def test_minimal(self) -> None:
        t = TableSchema.model_validate({"fields": _fields("a", "b")})
        assert [f.name for f in t.fields] == ["a", "b"]
        assert t.uniqueKeys is None                 # absent
        assert t.missingValues == [""]              # DP v2 default
        assert t.qa.exclusive_flags == []

    def test_table_qa_closed_namespace(self) -> None:
        with pytest.raises(ValidationError):
            TableQA.model_validate({"exclusive_flagz": []})

    def test_unique_keys_absent_vs_empty(self) -> None:
        with pytest.raises(ValidationError, match="uniqueKeys.*non-empty"):
            TableSchema.model_validate({"fields": _fields("a"), "uniqueKeys": []})

    def test_unique_keys_inner_group_non_empty(self) -> None:
        with pytest.raises(ValidationError, match="group must be non-empty"):
            TableSchema.model_validate({"fields": _fields("a"), "uniqueKeys": [[]]})

    def test_missing_values_must_be_unique(self) -> None:
        TableSchema.model_validate({"fields": _fields("a"), "missingValues": ["", "NA"]})  # ok
        with pytest.raises(ValidationError, match="unique"):
            TableSchema.model_validate({"fields": _fields("a"), "missingValues": ["NA", "NA"]})

    def test_duplicate_field_names_rejected(self) -> None:
        with pytest.raises(ValidationError, match="duplicate field name"):
            TableSchema.model_validate({"fields": _fields("a", "a")})
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `PYTHONPATH=src $PY -m pytest tests/test_datasets_schema.py::TestTableSchemaShape -v`
Expected: FAIL — `ImportError: cannot import name 'TableSchema'`.

- [ ] **Step 3: Add `TableQA` and `TableSchema` with the self-validator**

Append to `science/src/science_tool/datasets/schema.py` (after `ForeignKey`):

```python
class TableQA(BaseModel):
    """The distribution-severity extension carried at table level (closed namespace)."""

    model_config = ConfigDict(extra="forbid")
    exclusive_flags: list[tuple[str, str]] = Field(default_factory=list)


class TableSchema(BaseModel):
    model_config = ConfigDict(extra="allow")
    fields: list[FieldSpec]
    primaryKey: str | list[str] | None = None
    # `None` = absent. When present, DP v2 requires uniqueKeys non-empty with non-empty
    # inner groups; the validator distinguishes absent from explicit `[]`.
    uniqueKeys: list[list[str]] | None = None
    foreignKeys: list[ForeignKey] = Field(default_factory=list)
    missingValues: list[str | MissingValue] = Field(default_factory=lambda: [""])
    qa: TableQA = Field(default_factory=TableQA)

    @model_validator(mode="after")
    def _unique_and_missing(self) -> "TableSchema":
        field_names = [f.name for f in self.fields]
        dupes = sorted({n for n in field_names if field_names.count(n) > 1})
        if dupes:
            raise ValueError(f"duplicate field name(s): {dupes}")
        if self.uniqueKeys is not None:
            if not self.uniqueKeys:
                raise ValueError("uniqueKeys, when present, must be non-empty")
            if any(not group for group in self.uniqueKeys):
                raise ValueError("each uniqueKeys group must be non-empty")
        # Sentinel *values* are the key and must be unique; labels are descriptive
        # and intentionally NOT required to be unique.
        seen: set[str] = set()
        for mv in self.missingValues:
            key = mv if isinstance(mv, str) else mv.value
            if key in seen:
                raise ValueError(f"missingValues entries must be unique; duplicate {key!r}")
            seen.add(key)
        return self
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `PYTHONPATH=src $PY -m pytest tests/test_datasets_schema.py -v`
Expected: PASS (21 tests total).

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/datasets/schema.py science/tests/test_datasets_schema.py
git commit -m "feat(typed-schema): TableSchema shape + uniqueKeys/missingValues validators"
```

---

## Task 5: `TableSchema` cross-field reference & type guardrails

**Files:**
- Modify: `science/src/science_tool/datasets/schema.py`
- Test: `science/tests/test_datasets_schema.py`

- [ ] **Step 1: Write the failing tests**

Append to `science/tests/test_datasets_schema.py`:

```python
class TestTableSchemaReferences:
    def test_primary_key_must_reference_known_field(self) -> None:
        TableSchema.model_validate({"fields": _fields("id"), "primaryKey": "id"})  # ok
        with pytest.raises(ValidationError, match="primaryKey references unknown"):
            TableSchema.model_validate({"fields": _fields("id"), "primaryKey": "nope"})

    def test_unique_keys_reference_known_fields(self) -> None:
        with pytest.raises(ValidationError, match="uniqueKeys references unknown"):
            TableSchema.model_validate({"fields": _fields("a"), "uniqueKeys": [["a", "b"]]})

    def test_foreign_key_local_field_must_exist(self) -> None:
        with pytest.raises(ValidationError, match="unknown local field"):
            TableSchema.model_validate(
                {"fields": _fields("a"),
                 "foreignKeys": [{"fields": "b", "reference": {"resource": "r", "fields": "x"}}]}
            )

    def test_exclusive_flags_reference_known_fields(self) -> None:
        with pytest.raises(ValidationError, match="exclusive_flags references unknown"):
            TableSchema.model_validate(
                {"fields": [{"name": "is_a", "type": "boolean"}],
                 "qa": {"exclusive_flags": [["is_a", "is_b"]]}}
            )

    def test_exclusive_flags_require_flag_typed_fields(self) -> None:
        TableSchema.model_validate(
            {"fields": [{"name": "is_a", "type": "boolean"}, {"name": "is_b", "type": "integer"}],
             "qa": {"exclusive_flags": [["is_a", "is_b"]]}}
        )  # ok
        with pytest.raises(ValidationError, match="must be boolean/integer"):
            TableSchema.model_validate(
                {"fields": [{"name": "is_a", "type": "boolean"}, {"name": "s", "type": "string"}],
                 "qa": {"exclusive_flags": [["is_a", "s"]]}}
            )
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `PYTHONPATH=src $PY -m pytest tests/test_datasets_schema.py::TestTableSchemaReferences -v`
Expected: FAIL — validators not present, so the `pytest.raises` blocks do not raise.

- [ ] **Step 3: Add a second `model_validator` for cross-field checks**

Append this method inside the `TableSchema` class in `science/src/science_tool/datasets/schema.py` (after `_unique_and_missing`):

```python
    @model_validator(mode="after")
    def _reference_checks(self) -> "TableSchema":
        names = {f.name for f in self.fields}
        types = {f.name: f.type for f in self.fields}

        for key in (_as_list(self.primaryKey) if self.primaryKey is not None else []):
            if key not in names:
                raise ValueError(f"primaryKey references unknown field {key!r}")
        for group in (self.uniqueKeys or []):
            for key in group:
                if key not in names:
                    raise ValueError(f"uniqueKeys references unknown field {key!r}")
        for fk in self.foreignKeys:
            for key in _as_list(fk.fields):
                if key not in names:
                    raise ValueError(f"foreignKey references unknown local field {key!r}")
        for a, b in self.qa.exclusive_flags:
            for key in (a, b):
                if key not in names:
                    raise ValueError(f"qa.exclusive_flags references unknown field {key!r}")
            for key in (a, b):
                if types[key] not in FLAG_TYPES:
                    raise ValueError(
                        f"qa.exclusive_flags field {key!r} must be boolean/integer, "
                        f"got {types[key]!r}"
                    )
        return self
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `PYTHONPATH=src $PY -m pytest tests/test_datasets_schema.py -v`
Expected: PASS (26 tests total).

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/datasets/schema.py science/tests/test_datasets_schema.py
git commit -m "feat(typed-schema): TableSchema cross-field reference + flag-type guardrails"
```

---

## Task 6: `ResourceDescriptor` (`$schema` marker, `schema` alias)

**Files:**
- Modify: `science/src/science_tool/datasets/schema.py`
- Test: `science/tests/test_datasets_schema.py`

- [ ] **Step 1: Write the failing tests**

Append to `science/tests/test_datasets_schema.py` (add `ResourceDescriptor` to imports):

```python
from science_tool.datasets.schema import ResourceDescriptor  # add to existing import line


class TestResourceDescriptor:
    def test_minimal(self) -> None:
        d = ResourceDescriptor.model_validate({"name": "obs", "path": "obs.csv"})
        assert d.name == "obs" and d.path == "obs.csv"
        assert d.schema_ is None and d.profile is None

    def test_schema_alias_roundtrip(self) -> None:
        d = ResourceDescriptor.model_validate(
            {"name": "obs", "path": "obs.csv", "schema": {"fields": [{"name": "a"}]}}
        )
        assert d.schema_ is not None and d.schema_.fields[0].name == "a"
        dumped = d.model_dump(by_alias=True, exclude_none=True)
        assert "schema" in dumped and "schema_" not in dumped

    def test_profile_marker_validated(self) -> None:
        d = ResourceDescriptor.model_validate(
            {"$schema": "science-data-resource/v1", "name": "o", "path": "o.csv"}
        )
        assert d.profile == "science-data-resource/v1"
        with pytest.raises(ValidationError):
            ResourceDescriptor.model_validate({"$schema": "bogus/v9", "name": "o", "path": "o.csv"})

    def test_extra_standard_props_allowed(self) -> None:
        d = ResourceDescriptor.model_validate(
            {"name": "o", "path": "o.csv", "format": "csv", "mediatype": "text/csv"}
        )
        assert d.name == "o"
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `PYTHONPATH=src $PY -m pytest tests/test_datasets_schema.py::TestResourceDescriptor -v`
Expected: FAIL — `ImportError: cannot import name 'ResourceDescriptor'`.

- [ ] **Step 3: Add `ResourceDescriptor`**

Append to `science/src/science_tool/datasets/schema.py` (after `TableSchema`):

```python
class ResourceDescriptor(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)
    # Explicitly modelled so the marker is documented in the emitted profile and an
    # invalid value fails rather than passing silently via extra="allow".
    profile: Literal["science-data-resource/v1"] | None = Field(default=None, alias="$schema")
    name: str
    path: str                                # required in Spec 1 (no inline-data support yet)
    schema_: TableSchema | None = Field(default=None, alias="schema")
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `PYTHONPATH=src $PY -m pytest tests/test_datasets_schema.py -v`
Expected: PASS (30 tests total).

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/datasets/schema.py science/tests/test_datasets_schema.py
git commit -m "feat(typed-schema): ResourceDescriptor with \$schema marker + schema alias"
```

---

## Task 7: Cross-resource `package_consistency_issues()`

**Files:**
- Modify: `science/src/science_tool/datasets/schema.py`
- Test: `science/tests/test_datasets_schema.py`

- [ ] **Step 1: Write the failing tests**

Append to `science/tests/test_datasets_schema.py` (add `package_consistency_issues` to imports):

```python
from science_tool.datasets.schema import package_consistency_issues  # add to existing import line


def _resource(name: str, fields: list[dict], foreign_keys: list[dict] | None = None) -> ResourceDescriptor:
    schema: dict = {"fields": fields}
    if foreign_keys is not None:
        schema["foreignKeys"] = foreign_keys
    return ResourceDescriptor.model_validate({"name": name, "path": f"{name}.csv", "schema": schema})


class TestPackageConsistency:
    def test_resolvable_cross_resource_fk_has_no_issues(self) -> None:
        proteins = _resource("proteins", [{"name": "id"}])
        edges = _resource(
            "edges", [{"name": "src"}],
            foreign_keys=[{"fields": "src", "reference": {"resource": "proteins", "fields": "id"}}],
        )
        assert package_consistency_issues([proteins, edges]) == []

    def test_unknown_target_resource_is_an_issue(self) -> None:
        edges = _resource(
            "edges", [{"name": "src"}],
            foreign_keys=[{"fields": "src", "reference": {"resource": "ghost", "fields": "id"}}],
        )
        issues = package_consistency_issues([edges])
        assert any("unknown resource" in i for i in issues)

    def test_unknown_target_field_is_an_issue(self) -> None:
        proteins = _resource("proteins", [{"name": "id"}])
        edges = _resource(
            "edges", [{"name": "src"}],
            foreign_keys=[{"fields": "src", "reference": {"resource": "proteins", "fields": "nope"}}],
        )
        issues = package_consistency_issues([proteins, edges])
        assert any("reference field" in i for i in issues)

    def test_self_reference_resolves_against_own_fields(self) -> None:
        tree = _resource(
            "tree", [{"name": "id"}, {"name": "parent"}],
            foreign_keys=[{"fields": "parent", "reference": {"fields": "id"}}],
        )
        assert package_consistency_issues([tree]) == []

    def test_duplicate_resource_names_flagged(self) -> None:
        a = _resource("dup", [{"name": "x"}])
        b = _resource("dup", [{"name": "y"}])
        issues = package_consistency_issues([a, b])
        assert any("duplicate resource name" in i for i in issues)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `PYTHONPATH=src $PY -m pytest tests/test_datasets_schema.py::TestPackageConsistency -v`
Expected: FAIL — `ImportError: cannot import name 'package_consistency_issues'`.

- [ ] **Step 3: Add the function**

Append to `science/src/science_tool/datasets/schema.py` (after `ResourceDescriptor`):

```python
def package_consistency_issues(descriptors: list[ResourceDescriptor]) -> list[str]:
    """Cross-resource checks needing whole-package context (foreign-key resolution).

    Returns human-readable issue strings (empty list = consistent). Within-descriptor
    invariants are enforced at parse time by the model validators, not here.
    """
    issues: list[str] = []
    seen: set[str] = set()
    for d in descriptors:
        if d.name in seen:
            issues.append(f"duplicate resource name {d.name!r}")
        seen.add(d.name)
    by_name: dict[str, ResourceDescriptor] = {d.name: d for d in descriptors}
    for d in descriptors:
        if d.schema_ is None:
            continue
        for fk in d.schema_.foreignKeys:
            ref = fk.reference
            target = d if ref.resource == "" else by_name.get(ref.resource)
            if target is None:
                issues.append(f"{d.name}: foreignKey references unknown resource {ref.resource!r}")
                continue
            if target.schema_ is None:
                issues.append(
                    f"{d.name}: foreignKey target resource {ref.resource!r} has no schema"
                )
                continue
            target_names = {f.name for f in target.schema_.fields}
            for key in _as_list(ref.fields):
                if key not in target_names:
                    issues.append(
                        f"{d.name}: foreignKey reference field {key!r} not in resource "
                        f"{(ref.resource or d.name)!r}"
                    )
    return issues
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `PYTHONPATH=src $PY -m pytest tests/test_datasets_schema.py -v`
Expected: PASS (35 tests total).

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/datasets/schema.py science/tests/test_datasets_schema.py
git commit -m "feat(typed-schema): cross-resource package_consistency_issues()"
```

---

## Task 8: Profile emission + golden drift test

**Files:**
- Modify: `science/src/science_tool/datasets/schema.py`
- Create (generated): `science/src/science_tool/datasets/profiles/science-data-resource-v1.json`
- Test: `science/tests/test_datasets_schema.py`

- [ ] **Step 1: Add `emit_profile`, `write_profile`, and the `--emit` entrypoint**

Append to `science/src/science_tool/datasets/schema.py`:

```python
def emit_profile() -> str:
    """Deterministic JSON Schema for the Data Resource descriptor (the $schema target)."""
    schema = ResourceDescriptor.model_json_schema(by_alias=True)
    return json.dumps(schema, indent=2, sort_keys=True) + "\n"


def write_profile() -> Path:
    PROFILE_PATH.parent.mkdir(parents=True, exist_ok=True)
    PROFILE_PATH.write_text(emit_profile(), encoding="utf-8")
    return PROFILE_PATH


if __name__ == "__main__":  # pragma: no cover
    import argparse

    parser = argparse.ArgumentParser(description="science Data Resource profile tools")
    parser.add_argument(
        "--emit", action="store_true", help="(re)write the committed JSON Schema profile"
    )
    args = parser.parse_args()
    if args.emit:
        print(f"wrote {write_profile()}")
    else:
        parser.error("nothing to do; pass --emit")
```

- [ ] **Step 2: Generate the committed profile artifact**

Run:
```bash
PYTHONPATH=src $PY -m science_tool.datasets.schema --emit
```
Expected: prints `wrote .../datasets/profiles/science-data-resource-v1.json`; the file now exists.

- [ ] **Step 3: Write the golden drift test**

Append to `science/tests/test_datasets_schema.py` (add `emit_profile, PROFILE_PATH` to imports):

```python
from science_tool.datasets.schema import PROFILE_PATH, emit_profile  # add to existing import line


class TestProfileEmission:
    def test_emit_is_deterministic(self) -> None:
        assert emit_profile() == emit_profile()
        assert emit_profile().endswith("\n")

    def test_committed_profile_matches_models(self) -> None:
        assert PROFILE_PATH.exists(), "run: python -m science_tool.datasets.schema --emit"
        assert PROFILE_PATH.read_text(encoding="utf-8") == emit_profile(), (
            "profile drifted from models; regenerate with "
            "`python -m science_tool.datasets.schema --emit`"
        )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `PYTHONPATH=src $PY -m pytest tests/test_datasets_schema.py -v`
Expected: PASS (37 tests total).

- [ ] **Step 5: Commit (include the generated profile)**

```bash
git add science/src/science_tool/datasets/schema.py \
        science/src/science_tool/datasets/profiles/science-data-resource-v1.json \
        science/tests/test_datasets_schema.py
git commit -m "feat(typed-schema): emit + golden-test the science-data-resource-v1 profile"
```

---

## Task 9: Wire descriptor validation into `science datasets validate`

**Files:**
- Modify: `science/src/science_tool/datasets/validate.py`
- Test (modify): `science/tests/test_datasets_validate.py`

- [ ] **Step 1: Write the failing integration tests**

Append to `science/tests/test_datasets_validate.py`:

```python
def _write_pkg(tmp_path: Path, pkg: dict, csv: str = "a\n1\n") -> Path:
    raw = tmp_path / "data" / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    (raw / "x.csv").write_text(csv)  # data file so the file-exists check passes
    (raw / "datapackage.json").write_text(json.dumps(pkg))
    return tmp_path / "data"


class TestDescriptorValidation:
    def test_rich_valid_descriptor_has_no_descriptor_failures(self, tmp_path: Path) -> None:
        pkg = {
            "name": "p",
            "resources": [{
                "name": "x", "path": "x.csv",
                "schema": {
                    "fields": [
                        {"name": "a", "type": "integer", "constraints": {"required": True, "unique": True}},
                        {"name": "v", "type": "number", "constraints": {"minimum": 0}, "qa": {"low_variance": True}},
                    ],
                    "primaryKey": "a",
                },
            }],
        }
        # CSV columns match the declared fields so the case is valid end-to-end.
        results = validate_data_packages(_write_pkg(tmp_path, pkg, csv="a,v\n1,0.5\n"))
        descriptor_fails = [r for r in results if "descriptor" in r["check"] and r["status"] == "fail"]
        assert descriptor_fails == []

    def test_qa_on_string_field_fails_descriptor(self, tmp_path: Path) -> None:
        pkg = {
            "name": "p",
            "resources": [{
                "name": "x", "path": "x.csv",
                "schema": {"fields": [{"name": "a", "type": "string", "qa": {"low_variance": True}}]},
            }],
        }
        results = validate_data_packages(_write_pkg(tmp_path, pkg))
        assert any("descriptor" in r["check"] and r["status"] == "fail" for r in results)

    def test_dangling_exclusive_flags_fails(self, tmp_path: Path) -> None:
        pkg = {
            "name": "p",
            "resources": [{
                "name": "x", "path": "x.csv",
                "schema": {"fields": [{"name": "is_a", "type": "boolean"}],
                           "qa": {"exclusive_flags": [["is_a", "is_b"]]}},
            }],
        }
        results = validate_data_packages(_write_pkg(tmp_path, pkg))
        assert any("descriptor" in r["check"] and r["status"] == "fail" for r in results)

    def test_unresolved_cross_resource_fk_fails(self, tmp_path: Path) -> None:
        pkg = {
            "name": "p",
            "resources": [{
                "name": "edges", "path": "x.csv",
                "schema": {"fields": [{"name": "src"}],
                           "foreignKeys": [{"fields": "src", "reference": {"resource": "ghost", "fields": "id"}}]},
            }],
        }
        results = validate_data_packages(_write_pkg(tmp_path, pkg))
        assert any("consistency" in r["check"] and r["status"] == "fail" for r in results)

    def test_legacy_name_type_only_still_passes(self, data_dir: Path) -> None:
        # data_dir fixture: name/type-only schema, no constraints/qa — must remain clean.
        results = validate_data_packages(data_dir)
        descriptor_fails = [r for r in results if "descriptor" in r["check"] and r["status"] == "fail"]
        assert descriptor_fails == []
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `PYTHONPATH=src $PY -m pytest tests/test_datasets_validate.py::TestDescriptorValidation -v`
Expected: FAIL — no rows whose `check` contains "descriptor"/"consistency" yet, so the assertions fail.

- [ ] **Step 3: Add the descriptor-validation helper and call it**

In `science/src/science_tool/datasets/validate.py`, add imports near the top (after the existing `from pathlib import Path`):

```python
from pydantic import ValidationError

from science_tool.datasets.schema import ResourceDescriptor, package_consistency_issues
```

Add this helper at module scope (e.g. just above `_validate_resource_schema`):

```python
def _validate_resource_descriptors(resources: list[dict], prefix: str) -> list[dict[str, str]]:
    """Additive descriptor-validation pass (Spec 1): parse each resource against the
    typed-schema models and run cross-resource consistency. Emits pass|fail rows."""
    rows: list[dict[str, str]] = []
    descriptors: list[ResourceDescriptor] = []
    for res in resources:
        res_name = res.get("name", res.get("path", "unknown"))
        try:
            descriptors.append(ResourceDescriptor.model_validate(res))
        except ValidationError as exc:
            # One fail row per error → rich, located authoring feedback (design §7).
            for err in exc.errors():
                loc = ".".join(str(p) for p in err.get("loc", ()))
                msg = str(err.get("msg", ""))
                rows.append({
                    "check": f"{prefix}/{res_name} descriptor",
                    "status": "fail",
                    "details": f"{loc}: {msg}" if loc else msg,
                })
            continue
        rows.append({
            "check": f"{prefix}/{res_name} descriptor",
            "status": "pass",
            "details": "resource descriptor valid",
        })
    for issue in package_consistency_issues(descriptors):
        rows.append({
            "check": f"{prefix} descriptor consistency",
            "status": "fail",
            "details": issue,
        })
    return rows
```

Then, inside `validate_data_packages`, immediately after the Check 3 block (the `if not resources:` / `continue`) and before the `# Check 4` loop, insert:

```python
        # Check 3.5: typed-schema descriptor validation (Spec 1, additive)
        results.extend(_validate_resource_descriptors(resources, subdir_name))
```

- [ ] **Step 4: Run the tests to verify they pass**

Run:
```bash
PYTHONPATH=src $PY -m pytest tests/test_datasets_validate.py -v
```
Expected: PASS — the new `TestDescriptorValidation` class plus the pre-existing `TestValidateDataPackages` tests all green.

- [ ] **Step 5: Run the full datasets test slice to confirm no regressions**

Run:
```bash
PYTHONPATH=src $PY -m pytest tests/test_datasets_schema.py tests/test_datasets_validate.py tests/test_datasets_cli.py -v
```
Expected: PASS (all green).

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/datasets/validate.py science/tests/test_datasets_validate.py
git commit -m "feat(typed-schema): additive descriptor validation in datasets validate"
```

---

## Final verification (after all tasks)

- [ ] Run the broader `science_tool` suite to confirm nothing else broke (the descriptor pass is additive):

```bash
cd <worktree>/science
PYTHONPATH=src ~/d/science/science/.venv/bin/python -m pytest tests -q
```
Expected: the pre-existing suite stays green; +35 new schema tests +5 new integration tests pass.

- [ ] Confirm the committed profile is in sync (golden test already covers this; re-run if the models changed):

```bash
PYTHONPATH=src ~/d/science/science/.venv/bin/python -m pytest tests/test_datasets_schema.py::TestProfileEmission -v
```

---

## Self-review (filled in by plan author)

**1. Spec coverage** (design §→task):
- §3 two zones / severities → encoded structurally: native fields/constraints (Tasks 1–6) vs `qa:` `FieldQA`/`TableQA` (Tasks 1, 4). Severity *mapping to checks* is Spec 2; Spec 1 only fixes the zones. ✓
- §4.1 invariants vocabulary → `FieldConstraints` (T1), `FieldSpec.type` default `any` (T2), `primaryKey`/`uniqueKeys`/`foreignKeys`/`missingValues` (T3, T4). ✓
- §4.2 `qa:` residue (`low_variance`, `zero_fraction`, `exclusive_flags`) → `FieldQA` (T1), `TableQA` (T4). ✓
- §5 models (explicit `$schema` marker, `extra="allow"` everywhere / `forbid` on `qa:`, `default_factory`, ForeignKey shape, `schema_` alias, v2-targeting) → T1–T6. ✓
- §6 profile (emit, determinism, golden test, offline, version marker) → T8. ✓
- §7 validate integration (well-formedness + self-consistency guardrails; additive; `fail` rows) → guardrails as model validators (T2, T4, T5) + cross-resource fn (T7) + wiring (T9). ✓
- §8 type-applicability boundary → declared-type checks in T2 (bounds, qa-stats) + T5 (exclusive_flags); runtime-dtype explicitly deferred to Spec 2. ✓
- §10 testing strategy → model unit tests (T1–T7), golden (T8), integration (T9). ✓

**2. Placeholder scan:** none — every code step shows complete code; the only deferrals are explicit Spec 2/3 scope, not TODOs.

**3. Type consistency:** `_as_list` used consistently (T1 defn, T3/T5/T7 use); `schema_`/`profile` aliases consistent (T6, used in T9 via `model_validate`); `FLAG_TYPES`/`QA_STAT_TYPES`/`NUMERIC_TYPES`/`TEMPORAL_TYPES` defined T1, used T2/T5; `package_consistency_issues` signature stable (T7 defn, T9 call); `PROFILE_PATH`/`emit_profile` defined T1/T8, used T8.

**Note on test counts:** the running totals (6→11→15→20→25→29→33→35) are guidance; if your local pydantic emits a different `model_json_schema` shape, the golden test in T8 pins the committed file to *your* emitter — regenerate with `--emit` and commit, rather than editing the expected bytes by hand.

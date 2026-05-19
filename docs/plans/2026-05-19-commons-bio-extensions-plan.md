# Phase H — Bio extensions implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add five bio-domain JSON Schema mixins (`bio.matrix`, `bio.table`, `bio.rnaseq`, `bio.scrna`, `bio.cna`) plus a `--mixin` option on `science commons promote dataset` so promoted datasets carry typed bio metadata in their canonical surface.

**Architecture:** Three orthogonal pieces. (1) Five small JSON Schema files under `science/model/src/science_model/schemas/`; (2) profile/loader/validator infrastructure is unchanged — existing code already composes `+`-stacked extensions via `allOf`; (3) `commons/promote.py` threads an "active profile" (kind default + resolved extensions tuple) through `plan_promote` so `read_merge_policy`, `read_canonical_body_sections`, and `_render_canonical` see the bio mixin fields and emit the extended `schema_profile`. CLI registers `--mixin` inline on `promote dataset` only.

**Tech Stack:** Python 3.12, `jsonschema` (Draft 2020-12), Click, pytest, ruff. Project uses `uv run` for executing commands.

**Design spec:** `docs/plans/2026-05-19-commons-bio-extensions-design.md` (commit `bca04e04`).

**Parent design:** `docs/plans/2026-05-13-multiproject-schema-and-shared-store-design.md` §9 Phase H + §3.6 Domain extensions.

---

## Pre-flight

Before starting, run these to confirm baseline state:

```bash
cd /mnt/ssd/Dropbox/science
git status                         # working tree clean
git rev-parse HEAD                 # note SHA for rollback if needed
uv run pytest science/model/tests/ science/tests/ -q   # baseline green
```

Re-read these sections of the spec before authoring:
- §3 (architecture, layered mixins, stacking rules, field bucketing)
- §4 (the five schemas; note `additionalProperties: false` is kept only on bio.table's inner column descriptor)
- §6.3 (pipeline plumbing — `_active_profile`, `plan_promote` signature, `_render_canonical`)
- §6.5 (the two new error classes; both subclass `PromoteInputError`)

Key infrastructure (already in place; **do not modify**):
- `science/model/src/science_model/entity_schema/profile.py` — parses `+`-stacked extensions.
- `science/model/src/science_model/entity_schema/loader.py:39-48` — maps `bio.X` → `extension-bio-X-<ver>.json` via dot→hyphen.
- `science/model/src/science_model/entity_schema/loader.py:56-60` — raises `SchemaNotFoundError` for missing extension files.
- `science/model/src/science_model/entity_schema/validator.py:82-87` — `allOf`-composes profile components.
- `science/model/src/science_model/entity_schema/merge.py:22-31` — `read_merge_policy(profile)` walks ALL profile components (base + mixin + extensions).

---

## Phase H.1 — Schema authoring (Tasks 1–5)

### Task 1: Add `bio.matrix/1.0` schema

**Files:**
- Create: `science/model/src/science_model/schemas/extension-bio-matrix-1.0.json`
- Test: `science/model/tests/test_bio_extension_matrix.py`

- [ ] **Step 1: Write failing tests**

Create `science/model/tests/test_bio_extension_matrix.py`:

```python
from __future__ import annotations

import pytest

from science_model.entity_schema.profile import ProfileComponent
from science_model.entity_schema.loader import SchemaLoader
from science_model.entity_schema.validator import EntityValidationError, EntityValidator


@pytest.fixture
def base_matrix_entity() -> dict:
    return {
        "schema_profile": "science-entity-base/1.0+dataset/1.0+bio.matrix/1.0",
        "id": "dataset:example-matrix",
        "type": "dataset",
        "title": "Example matrix dataset",
        "version": "1.0.0",
        "created": "2026-05-19",
        "updated": "2026-05-19",
        "datapackage": "datapackage.yaml",
        "origin": "external",
        "tier": "use-now",
        "access": {"level": "public", "verified": True},
        # bio.matrix required fields:
        "n_rows": 20000,
        "n_cols": 500,
        "value_dtype": "int32",
        "feature_axis": "rows",
    }


def test_loader_resolves_bio_matrix_schema() -> None:
    schema = SchemaLoader().load(ProfileComponent(name="bio.matrix", version="1.0"))
    assert schema["$id"].endswith("extension-bio-matrix-1.0.json")


def test_minimal_valid_matrix_passes(base_matrix_entity: dict) -> None:
    EntityValidator().validate(base_matrix_entity)


def test_missing_n_rows_fails(base_matrix_entity: dict) -> None:
    fm = {k: v for k, v in base_matrix_entity.items() if k != "n_rows"}
    with pytest.raises(EntityValidationError, match="n_rows"):
        EntityValidator().validate(fm)


def test_missing_n_cols_fails(base_matrix_entity: dict) -> None:
    fm = {k: v for k, v in base_matrix_entity.items() if k != "n_cols"}
    with pytest.raises(EntityValidationError, match="n_cols"):
        EntityValidator().validate(fm)


def test_missing_value_dtype_fails(base_matrix_entity: dict) -> None:
    fm = {k: v for k, v in base_matrix_entity.items() if k != "value_dtype"}
    with pytest.raises(EntityValidationError, match="value_dtype"):
        EntityValidator().validate(fm)


def test_missing_feature_axis_fails(base_matrix_entity: dict) -> None:
    fm = {k: v for k, v in base_matrix_entity.items() if k != "feature_axis"}
    with pytest.raises(EntityValidationError, match="feature_axis"):
        EntityValidator().validate(fm)


def test_value_dtype_enum_rejects_invalid(base_matrix_entity: dict) -> None:
    base_matrix_entity["value_dtype"] = "complex128"
    with pytest.raises(EntityValidationError):
        EntityValidator().validate(base_matrix_entity)


def test_feature_axis_enum_rejects_invalid(base_matrix_entity: dict) -> None:
    base_matrix_entity["feature_axis"] = "diagonal"
    with pytest.raises(EntityValidationError):
        EntityValidator().validate(base_matrix_entity)


def test_n_rows_must_be_positive_int(base_matrix_entity: dict) -> None:
    base_matrix_entity["n_rows"] = 0
    with pytest.raises(EntityValidationError):
        EntityValidator().validate(base_matrix_entity)


def test_optional_row_col_kind_pass(base_matrix_entity: dict) -> None:
    base_matrix_entity["row_kind"] = "gene"
    base_matrix_entity["col_kind"] = "sample"
    EntityValidator().validate(base_matrix_entity)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest science/model/tests/test_bio_extension_matrix.py -v`
Expected: All fail with `SchemaNotFoundError: schema resource 'extension-bio-matrix-1.0.json' not found`.

- [ ] **Step 3: Create the schema**

Write `science/model/src/science_model/schemas/extension-bio-matrix-1.0.json`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://schemas.science/extension-bio-matrix-1.0.json",
  "title": "science entity bio.matrix extension",
  "type": "object",
  "required": ["n_rows", "n_cols", "value_dtype", "feature_axis"],
  "properties": {
    "n_rows": {"type": "integer", "minimum": 1},
    "n_cols": {"type": "integer", "minimum": 1},
    "value_dtype": {
      "enum": ["float32", "float64", "int32", "int64", "uint8", "uint16", "uint32", "bool"]
    },
    "feature_axis": {"enum": ["rows", "cols"]},
    "row_kind": {"type": "string", "minLength": 1},
    "col_kind": {"type": "string", "minLength": 1}
  }
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest science/model/tests/test_bio_extension_matrix.py -v`
Expected: 10 passed.

- [ ] **Step 5: Commit**

```bash
git add science/model/src/science_model/schemas/extension-bio-matrix-1.0.json \
        science/model/tests/test_bio_extension_matrix.py
git commit -m "feat(schemas): add bio.matrix/1.0 extension schema"
```

---

### Task 2: Add `bio.table/1.0` schema

**Files:**
- Create: `science/model/src/science_model/schemas/extension-bio-table-1.0.json`
- Test: `science/model/tests/test_bio_extension_table.py`

- [ ] **Step 1: Write failing tests**

Create `science/model/tests/test_bio_extension_table.py`:

```python
from __future__ import annotations

import pytest

from science_model.entity_schema.profile import ProfileComponent
from science_model.entity_schema.loader import SchemaLoader
from science_model.entity_schema.validator import EntityValidationError, EntityValidator


@pytest.fixture
def base_table_entity() -> dict:
    return {
        "schema_profile": "science-entity-base/1.0+dataset/1.0+bio.table/1.0",
        "id": "dataset:example-table",
        "type": "dataset",
        "title": "Example table dataset",
        "version": "1.0.0",
        "created": "2026-05-19",
        "updated": "2026-05-19",
        "datapackage": "datapackage.yaml",
        "origin": "external",
        "tier": "use-now",
        "access": {"level": "public", "verified": True},
        # bio.table required fields:
        "n_records": 18000,
        "columns": [
            {"name": "gene_id", "dtype": "string", "kind": "feature-id"},
            {"name": "log2fc", "dtype": "float", "kind": "log2fc"},
            {"name": "padj", "dtype": "float", "kind": "padj"},
        ],
    }


def test_loader_resolves_bio_table_schema() -> None:
    schema = SchemaLoader().load(ProfileComponent(name="bio.table", version="1.0"))
    assert schema["$id"].endswith("extension-bio-table-1.0.json")


def test_minimal_valid_table_passes(base_table_entity: dict) -> None:
    EntityValidator().validate(base_table_entity)


def test_missing_n_records_fails(base_table_entity: dict) -> None:
    fm = {k: v for k, v in base_table_entity.items() if k != "n_records"}
    with pytest.raises(EntityValidationError, match="n_records"):
        EntityValidator().validate(fm)


def test_missing_columns_fails(base_table_entity: dict) -> None:
    fm = {k: v for k, v in base_table_entity.items() if k != "columns"}
    with pytest.raises(EntityValidationError, match="columns"):
        EntityValidator().validate(fm)


def test_empty_columns_fails(base_table_entity: dict) -> None:
    base_table_entity["columns"] = []
    with pytest.raises(EntityValidationError):
        EntityValidator().validate(base_table_entity)


def test_column_missing_kind_fails(base_table_entity: dict) -> None:
    base_table_entity["columns"][0].pop("kind")
    with pytest.raises(EntityValidationError):
        EntityValidator().validate(base_table_entity)


def test_column_unknown_key_fails(base_table_entity: dict) -> None:
    """Inner column descriptor uses additionalProperties: false."""
    base_table_entity["columns"][0]["bogus"] = "x"
    with pytest.raises(EntityValidationError):
        EntityValidator().validate(base_table_entity)


def test_column_dtype_enum_rejects_invalid(base_table_entity: dict) -> None:
    base_table_entity["columns"][0]["dtype"] = "complex128"
    with pytest.raises(EntityValidationError):
        EntityValidator().validate(base_table_entity)
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest science/model/tests/test_bio_extension_table.py -v`
Expected: SchemaNotFoundError for `extension-bio-table-1.0.json`.

- [ ] **Step 3: Create the schema**

Write `science/model/src/science_model/schemas/extension-bio-table-1.0.json`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://schemas.science/extension-bio-table-1.0.json",
  "title": "science entity bio.table extension",
  "type": "object",
  "required": ["n_records", "columns"],
  "properties": {
    "n_records": {"type": "integer", "minimum": 1},
    "columns": {
      "type": "array",
      "minItems": 1,
      "items": {
        "type": "object",
        "required": ["name", "dtype", "kind"],
        "properties": {
          "name": {"type": "string", "minLength": 1},
          "dtype": {
            "enum": ["string", "integer", "float", "boolean", "date", "datetime", "categorical"]
          },
          "kind": {"type": "string", "minLength": 1}
        },
        "additionalProperties": false
      }
    }
  }
}
```

- [ ] **Step 4: Run to verify they pass**

Run: `uv run pytest science/model/tests/test_bio_extension_table.py -v`
Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add science/model/src/science_model/schemas/extension-bio-table-1.0.json \
        science/model/tests/test_bio_extension_table.py
git commit -m "feat(schemas): add bio.table/1.0 extension schema"
```

---

### Task 3: Add `bio.scrna/1.0` schema

**Files:**
- Create: `science/model/src/science_model/schemas/extension-bio-scrna-1.0.json`
- Test: `science/model/tests/test_bio_extension_scrna.py`

- [ ] **Step 1: Write failing tests**

Create `science/model/tests/test_bio_extension_scrna.py`:

```python
from __future__ import annotations

import pytest

from science_model.entity_schema.profile import ProfileComponent
from science_model.entity_schema.loader import SchemaLoader
from science_model.entity_schema.validator import EntityValidationError, EntityValidator


@pytest.fixture
def base_scrna_entity() -> dict:
    return {
        "schema_profile": "science-entity-base/1.0+dataset/1.0+bio.scrna/1.0",
        "id": "dataset:example-scrna",
        "type": "dataset",
        "title": "Example scRNA-seq dataset",
        "version": "1.0.0",
        "created": "2026-05-19",
        "updated": "2026-05-19",
        "datapackage": "datapackage.yaml",
        "origin": "external",
        "tier": "use-now",
        "access": {"level": "public", "verified": True},
        # bio.scrna required:
        "species": ["Homo sapiens"],
        "assay": "10x-chromium-3prime",
    }


def test_loader_resolves_bio_scrna_schema() -> None:
    schema = SchemaLoader().load(ProfileComponent(name="bio.scrna", version="1.0"))
    assert schema["$id"].endswith("extension-bio-scrna-1.0.json")


def test_minimal_valid_scrna_passes(base_scrna_entity: dict) -> None:
    EntityValidator().validate(base_scrna_entity)


def test_species_as_array_passes(base_scrna_entity: dict) -> None:
    base_scrna_entity["species"] = ["Homo sapiens", "Mus musculus"]
    EntityValidator().validate(base_scrna_entity)


def test_species_as_string_fails(base_scrna_entity: dict) -> None:
    base_scrna_entity["species"] = "Homo sapiens"
    with pytest.raises(EntityValidationError):
        EntityValidator().validate(base_scrna_entity)


def test_species_empty_array_fails(base_scrna_entity: dict) -> None:
    base_scrna_entity["species"] = []
    with pytest.raises(EntityValidationError):
        EntityValidator().validate(base_scrna_entity)


def test_assay_enum_accepts_known(base_scrna_entity: dict) -> None:
    for assay in ("smart-seq2", "drop-seq", "split-seq", "perturb-seq"):
        base_scrna_entity["assay"] = assay
        EntityValidator().validate(base_scrna_entity)


def test_assay_enum_rejects_unknown(base_scrna_entity: dict) -> None:
    base_scrna_entity["assay"] = "bulk-rnaseq"
    with pytest.raises(EntityValidationError):
        EntityValidator().validate(base_scrna_entity)


def test_missing_assay_fails(base_scrna_entity: dict) -> None:
    fm = {k: v for k, v in base_scrna_entity.items() if k != "assay"}
    with pytest.raises(EntityValidationError, match="assay"):
        EntityValidator().validate(fm)


def test_optional_tissue_passes(base_scrna_entity: dict) -> None:
    base_scrna_entity["tissue"] = "bone marrow"
    EntityValidator().validate(base_scrna_entity)
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest science/model/tests/test_bio_extension_scrna.py -v`
Expected: SchemaNotFoundError.

- [ ] **Step 3: Create the schema**

Write `science/model/src/science_model/schemas/extension-bio-scrna-1.0.json`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://schemas.science/extension-bio-scrna-1.0.json",
  "title": "science entity bio.scrna extension",
  "type": "object",
  "required": ["species", "assay"],
  "properties": {
    "species": {
      "type": "array",
      "minItems": 1,
      "items": {"type": "string", "minLength": 1}
    },
    "assay": {
      "enum": [
        "10x-chromium-3prime",
        "10x-chromium-5prime",
        "drop-seq",
        "mars-seq",
        "smart-seq2",
        "smart-seq3",
        "perturb-seq",
        "split-seq",
        "indrops"
      ]
    },
    "tissue": {"type": "string", "minLength": 1},
    "library_prep": {"type": "string", "minLength": 1},
    "reference_genome": {"type": "string", "minLength": 1},
    "preprocessing_version": {"type": "string", "minLength": 1}
  }
}
```

- [ ] **Step 4: Run to verify they pass**

Run: `uv run pytest science/model/tests/test_bio_extension_scrna.py -v`
Expected: 9 passed.

- [ ] **Step 5: Commit**

```bash
git add science/model/src/science_model/schemas/extension-bio-scrna-1.0.json \
        science/model/tests/test_bio_extension_scrna.py
git commit -m "feat(schemas): add bio.scrna/1.0 extension schema"
```

---

### Task 4: Add `bio.cna/1.0` schema

**Files:**
- Create: `science/model/src/science_model/schemas/extension-bio-cna-1.0.json`
- Test: `science/model/tests/test_bio_extension_cna.py`

- [ ] **Step 1: Write failing tests**

Create `science/model/tests/test_bio_extension_cna.py`:

```python
from __future__ import annotations

import pytest

from science_model.entity_schema.profile import ProfileComponent
from science_model.entity_schema.loader import SchemaLoader
from science_model.entity_schema.validator import EntityValidationError, EntityValidator


@pytest.fixture
def base_cna_entity() -> dict:
    return {
        "schema_profile": "science-entity-base/1.0+dataset/1.0+bio.cna/1.0",
        "id": "dataset:example-cna",
        "type": "dataset",
        "title": "Example CNA dataset",
        "version": "1.0.0",
        "created": "2026-05-19",
        "updated": "2026-05-19",
        "datapackage": "datapackage.yaml",
        "origin": "external",
        "tier": "use-now",
        "access": {"level": "public", "verified": True},
        # bio.cna required:
        "species": ["Homo sapiens"],
        "assay": "snp-array",
    }


def test_loader_resolves_bio_cna_schema() -> None:
    schema = SchemaLoader().load(ProfileComponent(name="bio.cna", version="1.0"))
    assert schema["$id"].endswith("extension-bio-cna-1.0.json")


def test_minimal_valid_cna_passes(base_cna_entity: dict) -> None:
    EntityValidator().validate(base_cna_entity)


def test_assay_enum_accepts_known(base_cna_entity: dict) -> None:
    for assay in ("snp-array", "array-cgh", "wes-cna", "wgs-cna", "shallow-wgs"):
        base_cna_entity["assay"] = assay
        EntityValidator().validate(base_cna_entity)


def test_assay_enum_rejects_unknown(base_cna_entity: dict) -> None:
    base_cna_entity["assay"] = "bulk-rnaseq"
    with pytest.raises(EntityValidationError):
        EntityValidator().validate(base_cna_entity)


def test_species_array_required(base_cna_entity: dict) -> None:
    base_cna_entity["species"] = "Homo sapiens"
    with pytest.raises(EntityValidationError):
        EntityValidator().validate(base_cna_entity)


def test_optional_segmentation_method_passes(base_cna_entity: dict) -> None:
    base_cna_entity["segmentation_method"] = "CBS"
    EntityValidator().validate(base_cna_entity)
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest science/model/tests/test_bio_extension_cna.py -v`
Expected: SchemaNotFoundError.

- [ ] **Step 3: Create the schema**

Write `science/model/src/science_model/schemas/extension-bio-cna-1.0.json`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://schemas.science/extension-bio-cna-1.0.json",
  "title": "science entity bio.cna extension",
  "type": "object",
  "required": ["species", "assay"],
  "properties": {
    "species": {
      "type": "array",
      "minItems": 1,
      "items": {"type": "string", "minLength": 1}
    },
    "assay": {
      "enum": ["snp-array", "array-cgh", "wes-cna", "wgs-cna", "shallow-wgs"]
    },
    "segmentation_method": {"type": "string", "minLength": 1},
    "reference_genome": {"type": "string", "minLength": 1},
    "preprocessing_version": {"type": "string", "minLength": 1}
  }
}
```

- [ ] **Step 4: Run to verify they pass**

Run: `uv run pytest science/model/tests/test_bio_extension_cna.py -v`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add science/model/src/science_model/schemas/extension-bio-cna-1.0.json \
        science/model/tests/test_bio_extension_cna.py
git commit -m "feat(schemas): add bio.cna/1.0 extension schema"
```

---

### Task 5: Patch `bio.rnaseq/1.0` and migrate three in-repo consumers

**Files:**
- Modify: `science/model/src/science_model/schemas/extension-bio-rnaseq-1.0.json` (full rewrite)
- Modify: `science/model/tests/test_entity_schema_extension_bio.py` (species → array; drop n_samples references)
- Modify: `science/tests/fixtures/commons/valid/datasets/rnaseq-example/entity.md` (species → array)
- Modify: `science/tests/test_commons_adapter.py:135` (assertion species → array)

- [ ] **Step 1: Read each existing file first to capture exact text**

Read all four:

```bash
cat science/model/src/science_model/schemas/extension-bio-rnaseq-1.0.json
cat science/model/tests/test_entity_schema_extension_bio.py
cat science/tests/fixtures/commons/valid/datasets/rnaseq-example/entity.md
sed -n '120,150p' science/tests/test_commons_adapter.py
```

- [ ] **Step 2: Rewrite the schema**

Overwrite `science/model/src/science_model/schemas/extension-bio-rnaseq-1.0.json`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://schemas.science/extension-bio-rnaseq-1.0.json",
  "title": "science entity bio.rnaseq extension",
  "type": "object",
  "required": ["species", "assay"],
  "properties": {
    "species": {
      "type": "array",
      "minItems": 1,
      "items": {"type": "string", "minLength": 1}
    },
    "assay": {
      "enum": ["bulk-rnaseq", "ribo-zero-rnaseq", "polya-rnaseq", "3prime-tag-rnaseq"]
    },
    "library_prep": {"type": "string", "minLength": 1},
    "reference_genome": {"type": "string", "minLength": 1},
    "preprocessing_version": {"type": "string", "minLength": 1}
  }
}
```

- [ ] **Step 3: Migrate `test_entity_schema_extension_bio.py`**

The existing `base_rnaseq_entity` fixture uses `species: "Homo sapiens"` and `n_samples: 1080`. Edit the fixture to:

```python
@pytest.fixture
def base_rnaseq_entity() -> dict:
    return {
        "schema_profile": "science-entity-base/1.0+dataset/1.0+bio.rnaseq/1.0",
        "id": "dataset:tcga-brca-rnaseq",
        "type": "dataset",
        "title": "TCGA-BRCA RNA-seq",
        "version": "1.0.0",
        "created": "2026-05-13",
        "updated": "2026-05-13",
        "datapackage": "datapackage.yaml",
        "origin": "external",
        "tier": "use-now",
        "access": {"level": "public", "verified": True},
        "species": ["Homo sapiens"],
        "assay": "bulk-rnaseq",
    }
```

Then update any tests in that file that referenced `n_samples`, `n_genes`, or `species` as a string — they were testing the structural fields that have now moved to `bio.matrix`. For each such test, either:
- Delete the test if it was specifically asserting structural-field behavior (those tests belong in `test_bio_extension_matrix.py`, where they already exist as of Task 1).
- Adjust to assert array-shaped species behavior, mirroring what is in `test_bio_extension_scrna.py` and `test_bio_extension_cna.py`.

- [ ] **Step 4: Migrate the rnaseq-example fixture**

Edit `science/tests/fixtures/commons/valid/datasets/rnaseq-example/entity.md` — change `species: "Homo sapiens"` to `species: ["Homo sapiens"]`. Leave everything else.

- [ ] **Step 5: Migrate `test_commons_adapter.py`**

Change the assertion at line ~135:

```python
# Before:
assert rnaseq.frontmatter["species"] == "Homo sapiens"
# After:
assert rnaseq.frontmatter["species"] == ["Homo sapiens"]
```

- [ ] **Step 6: Run all model tests**

Run: `uv run pytest science/model/tests/ science/tests/test_commons_adapter.py -v`
Expected: All pass. If any `n_samples` / `n_genes` references remain in the migrated test file, delete those test cases (the fields are no longer on bio.rnaseq).

- [ ] **Step 7: Commit**

```bash
git add science/model/src/science_model/schemas/extension-bio-rnaseq-1.0.json \
        science/model/tests/test_entity_schema_extension_bio.py \
        science/tests/fixtures/commons/valid/datasets/rnaseq-example/entity.md \
        science/tests/test_commons_adapter.py
git commit -m "refactor(schemas): patch bio.rnaseq/1.0 — species as array, structural counts ceded to bio.matrix

Widens species from string to array (supports mixed-species datasets
like host-pathogen). Removes n_samples / n_genes from the domain
mixin; those structural fields belong on bio.matrix (Task 1). Migrates
the three existing in-repo consumers (extension-bio test fixture,
rnaseq-example commons fixture, and commons-adapter assertion) in
place to the new shape."
```

---

## Phase H.2 — Validator composition (Tasks 6–7)

### Task 6: Stacked composition tests

**Files:**
- Test: `science/model/tests/test_entity_schema_validator_stacked.py` (new)

- [ ] **Step 1: Write failing tests**

Create the new test file (the validator code itself needs no changes, but we need explicit tests of stacked-extension composition):

```python
"""Tests for the validator with stacked bio extensions.

The composition pipeline (profile parsing + loader + allOf in
validator._compose) is already in place pre-Phase H. These tests
confirm it handles two- and three-segment stacks of bio extensions,
exposes the right errors, and caches schemas across repeated calls.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from science_model.entity_schema.loader import SchemaLoader, SchemaNotFoundError
from science_model.entity_schema.profile import ProfileComponent, parse_profile
from science_model.entity_schema.validator import EntityValidationError, EntityValidator


@pytest.fixture
def stacked_rnaseq_matrix_entity() -> dict:
    return {
        "schema_profile": "science-entity-base/1.0+dataset/1.0+bio.matrix/1.0+bio.rnaseq/1.0",
        "id": "dataset:tcga-brca-rnaseq",
        "type": "dataset",
        "title": "TCGA-BRCA RNA-seq counts matrix",
        "version": "1.0.0",
        "created": "2026-05-19",
        "updated": "2026-05-19",
        "datapackage": "datapackage.yaml",
        "origin": "external",
        "tier": "use-now",
        "access": {"level": "public", "verified": True},
        # bio.matrix required:
        "n_rows": 20530,
        "n_cols": 1080,
        "value_dtype": "int32",
        "feature_axis": "rows",
        # bio.rnaseq required:
        "species": ["Homo sapiens"],
        "assay": "bulk-rnaseq",
    }


def test_profile_parses_four_segments() -> None:
    profile = parse_profile(
        "science-entity-base/1.0+dataset/1.0+bio.matrix/1.0+bio.rnaseq/1.0"
    )
    assert profile.base == ProfileComponent("science-entity-base", "1.0")
    assert profile.mixin == ProfileComponent("dataset", "1.0")
    assert profile.extensions == (
        ProfileComponent("bio.matrix", "1.0"),
        ProfileComponent("bio.rnaseq", "1.0"),
    )


def test_stacked_rnaseq_matrix_valid_entity_passes(
    stacked_rnaseq_matrix_entity: dict,
) -> None:
    EntityValidator().validate(stacked_rnaseq_matrix_entity)


def test_stacked_rnaseq_matrix_missing_bio_rnaseq_required_fails(
    stacked_rnaseq_matrix_entity: dict,
) -> None:
    """The composed allOf fails when one mixin's required field is absent."""
    fm = {k: v for k, v in stacked_rnaseq_matrix_entity.items() if k != "assay"}
    with pytest.raises(EntityValidationError, match="assay"):
        EntityValidator().validate(fm)


def test_stacked_rnaseq_matrix_missing_bio_matrix_required_fails(
    stacked_rnaseq_matrix_entity: dict,
) -> None:
    fm = {k: v for k, v in stacked_rnaseq_matrix_entity.items() if k != "value_dtype"}
    with pytest.raises(EntityValidationError, match="value_dtype"):
        EntityValidator().validate(fm)


def test_stacked_table_scrna_valid_entity_passes() -> None:
    fm = {
        "schema_profile": "science-entity-base/1.0+dataset/1.0+bio.table/1.0+bio.scrna/1.0",
        "id": "dataset:scrna-deg-table",
        "type": "dataset",
        "title": "scRNA-seq DEG table",
        "version": "1.0.0",
        "created": "2026-05-19",
        "updated": "2026-05-19",
        "datapackage": "datapackage.yaml",
        "origin": "external",
        "tier": "use-now",
        "access": {"level": "public", "verified": True},
        "n_records": 5000,
        "columns": [
            {"name": "gene_id", "dtype": "string", "kind": "feature-id"},
            {"name": "log2fc", "dtype": "float", "kind": "log2fc"},
        ],
        "species": ["Homo sapiens"],
        "assay": "10x-chromium-3prime",
    }
    EntityValidator().validate(fm)


def test_schema_loader_caches_extensions() -> None:
    """Loading the same extension twice hits the schema cache, not the disk."""
    loader = SchemaLoader()
    comp = ProfileComponent(name="bio.matrix", version="1.0")
    first = loader.load(comp)
    # Patch the resource read; second call must NOT trigger it.
    with patch(
        "science_model.entity_schema.loader._load_resource",
    ) as mock_read:
        second = loader.load(comp)
    assert mock_read.call_count == 0
    assert first is second
```

- [ ] **Step 2: Run to verify they pass**

Run: `uv run pytest science/model/tests/test_entity_schema_validator_stacked.py -v`
Expected: 6 passed. (No source changes — the validator already supports this; tests just confirm.)

- [ ] **Step 3: Commit**

```bash
git add science/model/tests/test_entity_schema_validator_stacked.py
git commit -m "test(schemas): cover validator allOf-composition for stacked bio extensions"
```

---

### Task 7: Unknown-extension error tests

**Files:**
- Test: extend `science/model/tests/test_entity_schema_validator_stacked.py` (created in Task 6)

- [ ] **Step 1: Append failing tests**

Append to `science/model/tests/test_entity_schema_validator_stacked.py`:

```python
def test_unknown_extension_raises_schema_not_found(
    stacked_rnaseq_matrix_entity: dict,
) -> None:
    """An entity referencing an uninstalled extension fails loud."""
    stacked_rnaseq_matrix_entity["schema_profile"] = (
        "science-entity-base/1.0+dataset/1.0+bio.bogus/1.0"
    )
    with pytest.raises(SchemaNotFoundError, match="extension-bio-bogus-1.0.json"):
        EntityValidator().validate(stacked_rnaseq_matrix_entity)


def test_unknown_extension_in_middle_of_stack_also_raises() -> None:
    """Order doesn't matter — any unknown segment fails the composition."""
    fm = {
        "schema_profile": (
            "science-entity-base/1.0+dataset/1.0+bio.unknownmiddle/1.0+bio.rnaseq/1.0"
        ),
        "id": "dataset:x",
        "type": "dataset",
        "title": "x",
        "version": "1.0.0",
        "created": "2026-05-19",
        "updated": "2026-05-19",
        "datapackage": "datapackage.yaml",
        "origin": "external",
        "tier": "use-now",
        "access": {"level": "public", "verified": True},
        "species": ["Homo sapiens"],
        "assay": "bulk-rnaseq",
    }
    with pytest.raises(SchemaNotFoundError):
        EntityValidator().validate(fm)
```

- [ ] **Step 2: Run to verify they pass**

Run: `uv run pytest science/model/tests/test_entity_schema_validator_stacked.py::test_unknown_extension_raises_schema_not_found science/model/tests/test_entity_schema_validator_stacked.py::test_unknown_extension_in_middle_of_stack_also_raises -v`
Expected: 2 passed.

- [ ] **Step 3: Commit**

```bash
git add science/model/tests/test_entity_schema_validator_stacked.py
git commit -m "test(schemas): unknown bio extension surfaces SchemaNotFoundError"
```

---

## Phase H.3 — Promote integration (Tasks 8–18)

### Task 8: Add new error classes

**Files:**
- Modify: `science/src/science_tool/commons/errors.py` (append two classes)
- Test: `science/tests/test_commons_promote_mixin_errors.py` (new)

- [ ] **Step 1: Write failing tests**

Create `science/tests/test_commons_promote_mixin_errors.py`:

```python
"""Unit tests for the new mixin-related promote error classes."""
from __future__ import annotations

import pytest

from science_tool.commons.errors import (
    CommonsError,
    PromoteInputError,
    PromoteMixinResolutionError,
    PromoteMixinStackingError,
)


def test_stacking_error_is_promote_input_error() -> None:
    err = PromoteMixinStackingError("two structural mixins not allowed")
    assert isinstance(err, PromoteInputError)
    assert isinstance(err, CommonsError)
    assert "two structural" in str(err)


def test_resolution_error_is_promote_input_error() -> None:
    err = PromoteMixinResolutionError("no installed bio.bogus")
    assert isinstance(err, PromoteInputError)
    assert isinstance(err, CommonsError)
    assert "no installed" in str(err)
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest science/tests/test_commons_promote_mixin_errors.py -v`
Expected: ImportError — the two classes don't exist yet.

- [ ] **Step 3: Append the classes**

Append to `science/src/science_tool/commons/errors.py` (after `PromoteInputError`, around line 162):

```python
class PromoteMixinStackingError(PromoteInputError):
    """`--mixin` flag violated the stacking rule (more than one structural
    mixin, or more than one domain mixin). Raised at CLI parse time, before
    plan_promote runs.
    """


class PromoteMixinResolutionError(PromoteInputError):
    """`--mixin` could not be resolved to an installed bio extension schema.

    Raised for two paths, unified for operator UX:
    - Sugar form (`--mixin bio.bogus`): no `extension-bio-bogus-*.json` on disk.
    - Explicit form (`--mixin bio.bogus/1.0`): SchemaNotFoundError surfaces
      during `EntityValidator._compose` and is caught + rewrapped by
      `_validate_artifact` (commons/promote.py:783-797).
    """
```

- [ ] **Step 4: Run to verify they pass**

Run: `uv run pytest science/tests/test_commons_promote_mixin_errors.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/commons/errors.py \
        science/tests/test_commons_promote_mixin_errors.py
git commit -m "feat(commons): add PromoteMixinStackingError and PromoteMixinResolutionError"
```

---

### Task 9: Add `_validate_mixin_stacking` helper

**Files:**
- Modify: `science/src/science_tool/commons/promote.py` (add helper)
- Test: `science/tests/test_commons_promote_mixin_stacking.py` (new)

- [ ] **Step 1: Write failing tests**

Create `science/tests/test_commons_promote_mixin_stacking.py`:

```python
"""Tests for `_validate_mixin_stacking` — the rule guard for `--mixin`."""
from __future__ import annotations

import pytest

from science_model.entity_schema.profile import ProfileComponent
from science_tool.commons.errors import PromoteMixinStackingError
from science_tool.commons.promote import _validate_mixin_stacking


def _c(name: str, version: str = "1.0") -> ProfileComponent:
    return ProfileComponent(name=name, version=version)


def test_empty_tuple_ok() -> None:
    _validate_mixin_stacking(())


def test_single_structural_ok() -> None:
    _validate_mixin_stacking((_c("bio.matrix"),))
    _validate_mixin_stacking((_c("bio.table"),))


def test_single_domain_ok() -> None:
    _validate_mixin_stacking((_c("bio.rnaseq"),))
    _validate_mixin_stacking((_c("bio.scrna"),))
    _validate_mixin_stacking((_c("bio.cna"),))


def test_one_structural_plus_one_domain_ok() -> None:
    _validate_mixin_stacking((_c("bio.matrix"), _c("bio.rnaseq")))
    _validate_mixin_stacking((_c("bio.table"), _c("bio.scrna")))


def test_two_structural_rejected() -> None:
    with pytest.raises(PromoteMixinStackingError, match="structural"):
        _validate_mixin_stacking((_c("bio.matrix"), _c("bio.table")))


def test_two_domain_rejected() -> None:
    with pytest.raises(PromoteMixinStackingError, match="domain"):
        _validate_mixin_stacking((_c("bio.rnaseq"), _c("bio.cna")))


def test_three_with_two_domain_rejected() -> None:
    with pytest.raises(PromoteMixinStackingError, match="domain"):
        _validate_mixin_stacking(
            (_c("bio.matrix"), _c("bio.rnaseq"), _c("bio.cna"))
        )


def test_unknown_bio_extension_passes_stacking_check() -> None:
    """Unknown bio.* names are NOT rejected at the stacking-rule layer.
    Sugar form is caught earlier by _resolve_mixin_arg in cli.py;
    explicit form (e.g. --mixin bio.bogus/1.0) is expected to parse
    syntactically, pass stacking, and fail at validator composition
    (where SchemaNotFoundError is caught and rewrapped by
    _validate_artifact as PromoteMixinResolutionError — see Task 13)."""
    _validate_mixin_stacking((_c("bio.weird"),))  # no exception
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest science/tests/test_commons_promote_mixin_stacking.py -v`
Expected: ImportError on `_validate_mixin_stacking`.

- [ ] **Step 3: Add the helper to `commons/promote.py`**

Find a stable location (right after the `PROMOTE_KIND_DATASET` definition near line 210 is a natural spot). Add:

```python
# Bio extension classification used by `_validate_mixin_stacking`.
_STRUCTURAL_BIO_EXTENSIONS = frozenset({"bio.matrix", "bio.table"})
_DOMAIN_BIO_EXTENSIONS = frozenset({"bio.rnaseq", "bio.scrna", "bio.cna"})


def _validate_mixin_stacking(
    extensions: tuple["ProfileComponent", ...],
) -> None:
    """Enforce Phase H stacking rules on a resolved `--mixin` tuple.

    Rules:
      - At most one structural mixin (bio.matrix xor bio.table).
      - At most one domain mixin (bio.rnaseq xor bio.scrna xor bio.cna).

    Unknown bio.* names (e.g. `--mixin bio.bogus/1.0` in explicit form)
    are NOT rejected here. They sail through to validator composition
    where the loader raises `SchemaNotFoundError`, which
    `_validate_artifact` (Task 13) catches and rewraps as
    `PromoteMixinResolutionError`. Sugar form (`--mixin bio.bogus`) is
    caught earlier by `_resolve_mixin_arg` in cli.py.
    """
    from science_tool.commons.errors import PromoteMixinStackingError

    structural: list[str] = []
    domain: list[str] = []
    for ext in extensions:
        if ext.name in _STRUCTURAL_BIO_EXTENSIONS:
            structural.append(ext.name)
        elif ext.name in _DOMAIN_BIO_EXTENSIONS:
            domain.append(ext.name)
        # else: unknown bio.* extension — silently sails through;
        # validator composition will fail loud via SchemaNotFoundError.
    if len(structural) > 1:
        raise PromoteMixinStackingError(
            f"--mixin: at most one structural bio extension allowed "
            f"(got {structural})."
        )
    if len(domain) > 1:
        raise PromoteMixinStackingError(
            f"--mixin: at most one domain bio extension allowed "
            f"(got {domain})."
        )
```

`ProfileComponent` is already imported at the top of `promote.py` (line 34 imports `default_profile_for_kind`; the `ProfileString` import on line 129 also brings `ProfileComponent` in scope via `from science_model.entity_schema.profile import ...`). If the import isn't present, add it next to the other entity_schema imports.

- [ ] **Step 4: Run to verify they pass**

Run: `uv run pytest science/tests/test_commons_promote_mixin_stacking.py -v`
Expected: 8 passed (the "unknown extension passes stacking" test is now an assertion of no exception, not a `pytest.raises` block).

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/commons/promote.py \
        science/tests/test_commons_promote_mixin_stacking.py
git commit -m "feat(commons): add _validate_mixin_stacking guard for --mixin tuple"
```

---

### Task 10: Add `_active_profile` helper

**Files:**
- Modify: `science/src/science_tool/commons/promote.py`
- Test: `science/tests/test_commons_promote_active_profile.py` (new)

- [ ] **Step 1: Write failing tests**

Create `science/tests/test_commons_promote_active_profile.py`:

```python
"""Tests for `_active_profile` — builds the runtime ProfileString from
PromoteKindConfig + mixin extensions tuple."""
from __future__ import annotations

from science_model.entity_schema.profile import ProfileComponent
from science_tool.commons.promote import (
    PROMOTE_KIND_DATASET,
    PROMOTE_KIND_PAPER,
    _active_profile,
)


def test_no_extensions_returns_kind_default() -> None:
    profile = _active_profile(PROMOTE_KIND_PAPER, ())
    assert profile.base.name == "science-entity-base"
    assert profile.mixin is not None
    assert profile.mixin.name == "paper"
    assert profile.extensions == ()


def test_dataset_with_matrix_and_rnaseq() -> None:
    extensions = (
        ProfileComponent(name="bio.matrix", version="1.0"),
        ProfileComponent(name="bio.rnaseq", version="1.0"),
    )
    profile = _active_profile(PROMOTE_KIND_DATASET, extensions)
    assert profile.mixin is not None
    assert profile.mixin.name == "dataset"
    assert profile.extensions == extensions
    rendered = profile.render()
    assert rendered.endswith("+bio.matrix/1.0+bio.rnaseq/1.0")
    assert rendered.startswith("science-entity-base/1.0+dataset/1.0")


def test_returned_profile_is_a_new_object() -> None:
    """Doesn't mutate the PromoteKindConfig's frozen default_profile."""
    extensions = (ProfileComponent(name="bio.matrix", version="1.0"),)
    profile = _active_profile(PROMOTE_KIND_DATASET, extensions)
    assert PROMOTE_KIND_DATASET.default_profile.extensions == ()
    assert profile.extensions == extensions
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest science/tests/test_commons_promote_active_profile.py -v`
Expected: ImportError on `_active_profile`.

- [ ] **Step 3: Add the helper to `commons/promote.py`**

Add right after `_validate_mixin_stacking` (introduced in Task 9):

```python
def _active_profile(
    kind: PromoteKindConfig,
    extensions: tuple["ProfileComponent", ...],
) -> "ProfileString":
    """Build the per-call ProfileString from a kind's default plus extensions.

    Used by plan_promote to drive merge policy, body sections, and
    canonical rendering through `read_merge_policy(active_profile)` etc.,
    instead of `kind.default_profile` which omits the Phase H extensions.
    """
    from science_model.entity_schema.profile import ProfileString

    return ProfileString(
        base=kind.default_profile.base,
        mixin=kind.default_profile.mixin,
        extensions=tuple(extensions),
    )
```

`ProfileString` needs to be importable in scope. If it isn't, add it to the existing entity_schema imports at the top of `promote.py`.

- [ ] **Step 4: Run to verify they pass**

Run: `uv run pytest science/tests/test_commons_promote_active_profile.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/commons/promote.py \
        science/tests/test_commons_promote_active_profile.py
git commit -m "feat(commons): add _active_profile helper for kind + mixin composition"
```

---

### Task 11: Update `_render_canonical` to accept `active_profile`

**Files:**
- Modify: `science/src/science_tool/commons/promote.py:2276-2313` (signature + body)
- Modify: `science/src/science_tool/commons/promote.py:648` (only call site — update kwargs)

- [ ] **Step 1: Read both sites first**

```bash
sed -n '640,660p' science/src/science_tool/commons/promote.py
sed -n '2276,2314p' science/src/science_tool/commons/promote.py
```

- [ ] **Step 2: Update `_render_canonical` signature, body, AND the only call site (atomic edit)**

There is exactly one caller (line ~648 in `plan_promote`). This task changes the signature **and** that one call site in a single edit, so the parameter is required, not defaulted. (Per repo guideline: explicit > defensive; no compatibility layer.)

Replace the existing definition (`commons/promote.py:2276-2313`) with:

```python
def _render_canonical(
    decision: PromoteDecision,
    *,
    canonical_fields: dict,
    canonical_body: dict[str, str],
    created: date,
    updated: date,
    kind: PromoteKindConfig,
    active_profile: "ProfileString",
) -> str:
    """Render the commons-side <commons_subdir>/<slug>.md content.

    Emits schema_profile from `active_profile` (which equals
    `kind.default_profile` for bare promotes, or `kind.default_profile`
    augmented with `--mixin` extensions for Phase H bio promotes). id
    from kind.id_prefix, type from kind.kind. For paper kind only, also
    emits a `bibkey:` field (preserved from Phase E; not in topic/theme
    mixins).
    """
    profile_str = active_profile.render()
    head: dict = {
        "schema_profile": profile_str,
        "id": f"{kind.id_prefix}{decision.slug}",
        "type": kind.kind,
        "title": canonical_fields.get("title", ""),
        "version": decision.canonical_version,
        "created": _coerce_date_for_yaml(created),
        "updated": _coerce_date_for_yaml(updated),
    }
    if kind.kind == "paper":
        head["bibkey"] = decision.slug
    head["tags"] = []
    for k, v in canonical_fields.items():
        if k == "bibkey" and kind.kind != "paper":
            continue
        if k in head:
            continue
        head[k] = v

    fm = _render_frontmatter(head)
    body = _render_body(canonical_body)
    return f"---\n{fm}---\n{body}"
```

Then update the **single** caller (around line 648):

```python
canonical_content = _render_canonical(
    canonical_decision,
    canonical_fields=merged,
    canonical_body=canonical_body,
    created=date.today(),
    updated=date.today(),
    kind=kind,
    active_profile=kind.default_profile,   # NEW; Task 12 replaces this with
                                            #      the computed active_profile.
)
```

For now (this task) we pass `kind.default_profile` so behavior is byte-identical to pre-Task-11. Task 12 replaces this argument with the locally-computed `active_profile` derived from `mixin_extensions`.

- [ ] **Step 3: Run all existing promote tests**

Run: `uv run pytest science/tests/ -k promote -q`

Expected: All pass. Phase G behavior is preserved because `kind.default_profile.render()` produces the same string `_render_canonical` was emitting before.

- [ ] **Step 4: Commit**

```bash
git add science/src/science_tool/commons/promote.py
git commit -m "refactor(commons): _render_canonical requires active_profile

The single existing caller now passes kind.default_profile explicitly,
preserving Phase G behavior byte-identically. Task 12 swaps the
argument to the locally-computed active_profile (kind.default_profile
+ mixin_extensions) so the emitted schema_profile carries any --mixin
segments. No compatibility shim — the new invariant (active_profile
is always supplied) is explicit at every call site."
```

---

### Task 12: Thread `mixin_extensions` through `plan_promote`

**Files:**
- Modify: `science/src/science_tool/commons/promote.py:415-440` (signature + merge_policy / body_sections derivation)
- Modify: `science/src/science_tool/commons/promote.py:648-654` (pass `active_profile` to `_render_canonical`)
- Test: `science/tests/test_commons_promote_active_profile.py` (extend with end-to-end coverage)

- [ ] **Step 1: Re-read the existing function signature and the first ~30 lines of its body**

```bash
sed -n '415,460p' science/src/science_tool/commons/promote.py
```

- [ ] **Step 2: Update signature and the merge_policy / body_sections lines**

Change the function signature from:

```python
def plan_promote(
    discovery: DiscoveryResult,
    *,
    commons_root: Path,
    kind: PromoteKindConfig,
    resolve_conflict: Callable[[FieldConflict], Any] | None = None,
    from_order: list[str] | None = None,
) -> PromotePlan:
```

To:

```python
def plan_promote(
    discovery: DiscoveryResult,
    *,
    commons_root: Path,
    kind: PromoteKindConfig,
    resolve_conflict: Callable[[FieldConflict], Any] | None = None,
    from_order: list[str] | None = None,
    mixin_extensions: tuple["ProfileComponent", ...] = (),
) -> PromotePlan:
```

Inside the body, replace lines 439–440:

```python
# Before:
merge_policy = read_merge_policy(kind.default_profile)
body_sections = read_canonical_body_sections(kind.default_profile)
# After:
active_profile = _active_profile(kind, mixin_extensions)
merge_policy = read_merge_policy(active_profile)
body_sections = read_canonical_body_sections(active_profile)
```

- [ ] **Step 3: Pass `active_profile` to `_render_canonical`**

Find the call at line ~648 and add the new kwarg:

```python
canonical_content = _render_canonical(
    canonical_decision,
    canonical_fields=merged,
    canonical_body=canonical_body,
    created=date.today(),
    updated=date.today(),
    kind=kind,
    active_profile=active_profile,    # NEW
)
```

- [ ] **Step 4: Append an integration test**

The test mirrors the canonical pattern from
`science/tests/test_commons_promote_dataset_discovery.py:14-36`: build a
project tree, init it as a git repo, monkeypatch
`science_tool.commons.promote.resolve_project_by_id` to return the temp
project root. The datapackage is JSON (not YAML — the loader uses
`json.loads`, `promote.py:1519`). Every resource path declared in the
datapackage must exist on disk, otherwise discovery raises
`PromoteResourceMissingError` (`promote.py:1550`).

Add to `science/tests/test_commons_promote_active_profile.py`:

```python
import json
import subprocess
from pathlib import Path

import pytest

from science_model.entity_schema.profile import ProfileComponent


def _project_tree_with_rnaseq(tmp_path: Path) -> Path:
    """Build a minimal source project with one data-mockrna.md dataset
    carrying bio.matrix + bio.rnaseq fields in its frontmatter, plus a
    JSON datapackage and the resource file the datapackage references."""
    proj = tmp_path / "proj-rnaseq"
    (proj / "doc" / "datasets").mkdir(parents=True)
    (proj / "data" / "mockrna").mkdir(parents=True)

    (proj / "doc" / "datasets" / "data-mockrna.md").write_text(
        """---
id: dataset:mockrna
type: dataset
title: Mock RNA-seq dataset
description: Synthetic fixture for Phase H integration tests.
datapackage: data/mockrna/datapackage.json
origin: external
tier: use-now
access:
  level: public
  verified: true
created: "2026-05-19"
updated: "2026-05-19"
species: ["Homo sapiens"]
assay: bulk-rnaseq
n_rows: 20530
n_cols: 100
value_dtype: int32
feature_axis: rows
---

# Mock RNA-seq

Body content.
""",
        encoding="utf-8",
    )

    (proj / "data" / "mockrna" / "datapackage.json").write_text(
        json.dumps(
            {
                "name": "mockrna",
                "resources": [
                    {
                        "name": "counts",
                        "path": "counts.tsv",
                        "format": "tsv",
                        "mediatype": "text/tab-separated-values",
                    }
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (proj / "data" / "mockrna" / "counts.tsv").write_text("gene\ts1\n", encoding="utf-8")

    # Discovery walks `git ls-files` (per Phase F/G), so the project must
    # be a committed git repo (mirrors test_commons_promote_dataset_discovery.py).
    subprocess.run(["git", "init", "-q", str(proj)], check=True)
    subprocess.run(["git", "-C", str(proj), "add", "."], check=True)
    subprocess.run(
        [
            "git", "-C", str(proj),
            "-c", "user.email=t@t",
            "-c", "user.name=t",
            "commit", "-q", "-m", "init",
        ],
        check=True,
    )
    return proj


def test_plan_promote_with_mixin_extensions_emits_extended_schema_profile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """End-to-end: invoking plan_promote with non-empty mixin_extensions
    routes bio fields to canonical (via merge_policy from the active
    profile) and emits the full schema_profile in the rendered entity."""
    from science_tool.commons.bootstrap import init_commons
    from science_tool.commons.promote import (
        PROMOTE_KIND_DATASET,
        discover_candidates,
        plan_promote,
    )

    proj = _project_tree_with_rnaseq(tmp_path)
    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda _slug: proj,
    )

    commons = tmp_path / "commons"
    init_commons(commons)

    discovery = discover_candidates(["proj-rnaseq"], PROMOTE_KIND_DATASET)
    assert "mockrna" in discovery.candidates_by_slug
    assert discovery.failed_candidates == []

    plan = plan_promote(
        discovery,
        commons_root=commons,
        kind=PROMOTE_KIND_DATASET,
        mixin_extensions=(
            ProfileComponent(name="bio.matrix", version="1.0"),
            ProfileComponent(name="bio.rnaseq", version="1.0"),
        ),
    )

    assert len(plan.decisions) == 1
    canonical = plan.decisions[0].canonical_artifacts[0]
    assert "+bio.matrix/1.0+bio.rnaseq/1.0" in canonical.content
    # Bio fields routed to canonical, not overlay:
    assert "assay: bulk-rnaseq" in canonical.content
    assert "value_dtype: int32" in canonical.content
    assert "feature_axis: rows" in canonical.content
    assert "Homo sapiens" in canonical.content
```

- [ ] **Step 5: Run to verify it passes**

Run: `uv run pytest science/tests/test_commons_promote_active_profile.py -v`
Expected: All tests pass, including the new integration test.

Also run all existing promote tests to confirm Phase G regression-free:

Run: `uv run pytest science/tests/ -k promote -q`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/commons/promote.py \
        science/tests/test_commons_promote_active_profile.py
git commit -m "feat(commons): thread mixin_extensions through plan_promote

plan_promote gains a mixin_extensions kwarg defaulting to (). When
non-empty, it builds an active ProfileString (via _active_profile)
and uses it for read_merge_policy, read_canonical_body_sections, and
the _render_canonical call — so bio fields are in the canonical
merge bucket and the emitted schema_profile carries the full
+bio.*/N.N segments. Empty tuple preserves Phase G behavior verbatim."
```

---

### Task 13: SchemaNotFoundError catch in `_validate_artifact`

**Files:**
- Modify: `science/src/science_tool/commons/promote.py:783-797` (`entity-mixin` branch of `_validate_artifact`)
- Test: `science/tests/test_commons_promote_artifact_validation.py` (new)

- [ ] **Step 1: Re-read the current branch**

```bash
sed -n '775,800p' science/src/science_tool/commons/promote.py
```

- [ ] **Step 2: Write failing test**

Create `science/tests/test_commons_promote_artifact_validation.py`:

```python
"""Tests for _validate_artifact's handling of unknown bio extensions."""
from __future__ import annotations

import pytest

from science_tool.commons.errors import PromoteMixinResolutionError
from science_tool.commons.promote import CanonicalArtifact, _validate_artifact


def test_validate_artifact_wraps_schema_not_found_as_resolution_error() -> None:
    """When canonical content cites an unknown bio.* extension, the
    SchemaNotFoundError raised by EntityValidator._compose is caught and
    re-raised as PromoteMixinResolutionError for consistent CLI UX."""
    content = (
        "---\n"
        "schema_profile: science-entity-base/1.0+dataset/1.0+bio.bogus/1.0\n"
        "id: dataset:x\n"
        "type: dataset\n"
        "title: x\n"
        "version: 1.0.0\n"
        "created: '2026-05-19'\n"
        "updated: '2026-05-19'\n"
        "datapackage: datapackage.yaml\n"
        "origin: external\n"
        "tier: use-now\n"
        "access:\n"
        "  level: public\n"
        "  verified: true\n"
        "---\n"
        "Body.\n"
    )
    artifact = CanonicalArtifact(
        path="datasets/x/entity.md",
        content=content,
        validator="entity-mixin",
    )
    with pytest.raises(PromoteMixinResolutionError, match="bio.bogus"):
        _validate_artifact(artifact, decision_slug="x", project_id=None)
```

- [ ] **Step 3: Run to verify it fails**

Run: `uv run pytest science/tests/test_commons_promote_artifact_validation.py -v`
Expected: Fails with an unwrapped `SchemaNotFoundError` (or with `FileNotFoundError`) — not the expected `PromoteMixinResolutionError`.

- [ ] **Step 4: Update `_validate_artifact`**

Find the `entity-mixin` branch at line ~783 and replace:

```python
# Before:
if artifact.validator == "entity-mixin":
    from science_model.entity_schema import EntityValidator
    from science_model.entity_schema.validator import EntityValidationError

    fm = _parse_frontmatter_only(artifact.content)
    try:
        EntityValidator().validate(fm)
    except EntityValidationError as exc:
        raise PromoteValidationError(
            decision_slug=decision_slug,
            target_kind="canonical",
            project_id=project_id,
            schema_message=str(exc),
        ) from exc
    return
```

With:

```python
# After:
if artifact.validator == "entity-mixin":
    from science_model.entity_schema import EntityValidator
    from science_model.entity_schema.loader import SchemaNotFoundError
    from science_model.entity_schema.validator import EntityValidationError

    fm = _parse_frontmatter_only(artifact.content)
    try:
        EntityValidator().validate(fm)
    except SchemaNotFoundError as exc:
        # Explicit-form unknown bio extension (--mixin bio.bogus/1.0)
        # surfaces here. Rewrap as PromoteMixinResolutionError so the
        # CLI's standard CommonsError → ClickException path catches it,
        # and to match the sugar-form path (which also raises
        # PromoteMixinResolutionError at parse time).
        raise PromoteMixinResolutionError(
            f"schema_profile references an unknown extension: {exc}"
        ) from exc
    except EntityValidationError as exc:
        raise PromoteValidationError(
            decision_slug=decision_slug,
            target_kind="canonical",
            project_id=project_id,
            schema_message=str(exc),
        ) from exc
    return
```

Also: ensure `PromoteMixinResolutionError` is imported at the top of the file alongside the other promote errors.

- [ ] **Step 5: Run to verify it passes**

Run: `uv run pytest science/tests/test_commons_promote_artifact_validation.py -v`
Expected: 1 passed.

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/commons/promote.py \
        science/tests/test_commons_promote_artifact_validation.py
git commit -m "feat(commons): wrap SchemaNotFoundError as PromoteMixinResolutionError

In _validate_artifact's entity-mixin branch, catch SchemaNotFoundError
(raised by the loader when an unknown bio.* extension is referenced
in schema_profile) and rewrap as PromoteMixinResolutionError. Routes
explicit-form (--mixin bio.bogus/1.0) and sugar-form (--mixin
bio.bogus) unknown extensions through the same operator-facing error
class for consistent CLI UX."
```

---

### Task 14: Extend audit-log shape with `mixin_extensions`

**Files:**
- Modify: `science/src/science_tool/commons/promote.py:316-340` (`PromoteResult` dataclass)
- Modify: `science/src/science_tool/commons/promote.py:980-1010` (the `apply_promote` site that constructs `PromoteResult` — pass through the extensions)
- Modify: `science/src/science_tool/commons/promote.py:2407-2460` (`_render_audit_log_yaml`)
- Test: `science/tests/test_commons_promote_audit_mixin.py` (new)

- [ ] **Step 1: Re-read the three sites**

```bash
sed -n '316,345p' science/src/science_tool/commons/promote.py
sed -n '975,1010p' science/src/science_tool/commons/promote.py
sed -n '2407,2460p' science/src/science_tool/commons/promote.py
```

- [ ] **Step 2: Write failing test**

Create `science/tests/test_commons_promote_audit_mixin.py`:

```python
"""Audit-log shape extension for mixin_extensions."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import yaml

from science_model.entity_schema.profile import ProfileComponent
from science_tool.commons.promote import (
    PROMOTE_KIND_DATASET,
    PromoteResult,
    _render_audit_log_yaml,
)


def _empty_result(mixin_extensions: tuple[ProfileComponent, ...] = ()) -> PromoteResult:
    now = datetime.now(timezone.utc)
    return PromoteResult(
        op_id="op-test",
        started_at=now,
        finished_at=now,
        commons_commit=None,
        tags_created=[],
        decisions=[],
        failed_candidates=[],
        audit_log_path=None,
        status="ok",
        failure_stage=None,
        failure_detail=None,
        projects_touched=[],
        kind=PROMOTE_KIND_DATASET,
        mixin_extensions=mixin_extensions,
    )


def test_audit_log_omits_mixin_extensions_when_empty(tmp_path: Path) -> None:
    yaml_text = _render_audit_log_yaml(_empty_result(), tmp_path, invocation="x")
    parsed = yaml.safe_load(yaml_text)
    assert "mixin_extensions" not in parsed


def test_audit_log_emits_mixin_extensions_when_non_empty(tmp_path: Path) -> None:
    extensions = (
        ProfileComponent(name="bio.matrix", version="1.0"),
        ProfileComponent(name="bio.rnaseq", version="1.0"),
    )
    yaml_text = _render_audit_log_yaml(
        _empty_result(extensions), tmp_path, invocation="x"
    )
    parsed = yaml.safe_load(yaml_text)
    assert parsed["mixin_extensions"] == ["bio.matrix/1.0", "bio.rnaseq/1.0"]
```

Note: if `PromoteResult` already has more or fewer constructor args than the helper above shows, adjust `_empty_result` to match. Inspect the actual dataclass definition (`commons/promote.py:316`) when running this task.

- [ ] **Step 3: Run to verify failure**

Run: `uv run pytest science/tests/test_commons_promote_audit_mixin.py -v`
Expected: Either the test fails because `mixin_extensions` isn't a field on `PromoteResult`, or because `_render_audit_log_yaml` doesn't emit it. Either is fine.

- [ ] **Step 4: Add `mixin_extensions` to `PromoteResult`**

Locate `PromoteResult` (line 316). Add the new field at the end of the dataclass, defaulted so existing call sites don't need to change:

```python
@dataclass(frozen=True, slots=True)
class PromoteResult:
    # ... existing fields, unchanged ...
    mixin_extensions: tuple["ProfileComponent", ...] = ()
```

- [ ] **Step 5: Plumb the value through `apply_promote`**

`apply_promote` currently builds `PromoteResult` from a `PromotePlan`. Add `mixin_extensions` to `PromotePlan` too so the value flows from plan_promote into apply_promote → PromoteResult.

Edit `PromotePlan` (line 309):

```python
@dataclass(frozen=True, slots=True)
class PromotePlan:
    decisions: list[PromoteDecision]
    failed_candidates: list[FailedCandidate]
    kind: PromoteKindConfig
    dataset_audit_extras: dict[str, dict[str, Any]] = field(default_factory=dict)
    mixin_extensions: tuple["ProfileComponent", ...] = ()    # NEW
```

In `plan_promote`, when building the returned `PromotePlan`, include the tuple. The return statement is typically at the end of `plan_promote`; add `mixin_extensions=mixin_extensions` to the constructor call.

In `apply_promote` (around line 985, where the success-path `PromoteResult(...)` is constructed), pass `mixin_extensions=plan.mixin_extensions`. Do the same at every other `PromoteResult(...)` construction site in this file (lines ~1076, ~1287, ~1337 based on earlier grep). Each of those needs the field, even if defaulting to `()` is fine for the failure cases.

- [ ] **Step 6: Update `_render_audit_log_yaml`**

In `_render_audit_log_yaml` (around line 2439), where the `log` dict is being built, add the new field conditionally:

```python
log: dict = {
    "op_id": result.op_id,
    "type": result.kind.kind,
    "invocation": invocation,
    "status": result.status,
    # ... existing fields unchanged ...
}
if result.mixin_extensions:
    log["mixin_extensions"] = [
        f"{c.name}/{c.version}" for c in result.mixin_extensions
    ]
```

- [ ] **Step 7: Run all tests**

Run: `uv run pytest science/tests/test_commons_promote_audit_mixin.py -v`
Expected: 2 passed.

Run: `uv run pytest science/tests/ -k promote -q`
Expected: all pass — adding a defaulted field is backward-compatible.

- [ ] **Step 8: Commit**

```bash
git add science/src/science_tool/commons/promote.py \
        science/tests/test_commons_promote_audit_mixin.py
git commit -m "feat(commons): audit log carries mixin_extensions when non-empty

Adds mixin_extensions tuple to PromotePlan and PromoteResult,
defaulted to (). _render_audit_log_yaml emits it as
[\"bio.matrix/1.0\", \"bio.rnaseq/1.0\"] when non-empty and omits the
field entirely otherwise — no audit-shape change for paper/topic/
theme/bare-dataset promotes."
```

---

### Task 15: Register `--mixin` on the dataset CLI command

**Files:**
- Modify: `science/src/science_tool/commons/cli.py:475-502` (the `promote dataset` command)

- [ ] **Step 1: Re-read the current dataset command**

```bash
sed -n '475,505p' science/src/science_tool/commons/cli.py
```

- [ ] **Step 2: Add sugar resolver helper**

Add a private helper at module scope in `cli.py` (near the top of the promote section, around line 395):

```python
def _resolve_mixin_arg(raw: str) -> "ProfileComponent":
    """Parse one --mixin argument into a ProfileComponent.

    Accepts either:
      - Explicit: 'bio.matrix/1.0' → ProfileComponent('bio.matrix', '1.0')
      - Sugar: 'bio.matrix' → resolved to the highest installed version
        by scanning extension-bio-matrix-*.json under the schemas package.

    Raises PromoteMixinResolutionError on malformed input or missing
    extension for sugar form.
    """
    from importlib import resources

    from science_model.entity_schema.profile import ProfileComponent
    from science_tool.commons.errors import PromoteMixinResolutionError

    raw = raw.strip()
    if not raw or raw.startswith("/") or raw.endswith("/"):
        raise PromoteMixinResolutionError(f"--mixin {raw!r}: malformed argument")

    if "/" in raw:
        name, version = raw.split("/", 1)
        if not name or not version:
            raise PromoteMixinResolutionError(
                f"--mixin {raw!r}: expected '<name>/<version>'"
            )
        return ProfileComponent(name=name, version=version)

    # Sugar: enumerate extension files for this name.
    name = raw
    flat = name.replace(".", "-")
    prefix = f"extension-{flat}-"
    candidates: list[str] = []
    for r in resources.files("science_model.schemas").iterdir():
        rname = r.name
        if rname.startswith(prefix) and rname.endswith(".json"):
            version = rname[len(prefix):-len(".json")]
            candidates.append(version)
    if not candidates:
        raise PromoteMixinResolutionError(
            f"--mixin {raw!r}: no installed extension-{flat}-*.json schema. "
            "Known bio extensions: bio.matrix, bio.table, bio.rnaseq, "
            "bio.scrna, bio.cna."
        )
    # Lexicographic max works for two-segment N.N versioning; if a
    # future schema bumps to a different versioning scheme, this picker
    # gets revisited.
    highest = max(candidates)
    return ProfileComponent(name=name, version=highest)
```

- [ ] **Step 3: Update the `promote dataset` command params and handler**

Replace the existing dataset command definition (line 475–502) with:

```python
@promote_group.command(
    "dataset",
    params=_promote_from_options(PROMOTE_KIND_DATASET)
    + [
        click.Option(
            ["--slug"],
            required=True,
            help="Dataset slug to promote (required in v1; batch deferred to v1.1).",
        ),
        click.Option(
            ["--mixin", "mixin_args"],
            multiple=True,
            default=(),
            help=(
                "Bio-domain mixin to stack onto schema_profile, "
                "e.g. \"bio.matrix/1.0\" or \"bio.rnaseq\". Repeatable. "
                "At most one structural mixin (bio.matrix or bio.table) AND "
                "at most one domain mixin (bio.rnaseq, bio.scrna, or "
                "bio.cna). A dataset has one bio modality; multi-modality "
                "resources are represented as multiple datasets."
            ),
        ),
    ],
)
def promote_dataset_cmd(
    entity_id: str | None,
    from_: tuple[str, ...],
    apply_flag: bool,
    limit: int | None,
    slug: str,
    mixin_args: tuple[str, ...],
) -> None:
    """Promote one dataset entity into the commons store."""
    if entity_id is not None:
        raise click.UsageError(
            "dataset promotion uses --slug; do not pass a positional <entity_id>"
        )
    # Resolve --mixin (sugar form to explicit) and validate stacking BEFORE
    # plan_promote. Both _resolve_mixin_arg and _validate_mixin_stacking
    # raise PromoteInputError subclasses on failure, which the standard
    # CLI try/except (line ~575) wraps as ClickException.
    from science_tool.commons.promote import _validate_mixin_stacking

    try:
        mixin_extensions = tuple(_resolve_mixin_arg(m) for m in mixin_args)
        _validate_mixin_stacking(mixin_extensions)
    except CommonsError as exc:
        raise click.ClickException(str(exc)) from exc

    _promote_kind_cmd(
        kind=PROMOTE_KIND_DATASET,
        entity_id=f"dataset:{slug}",
        from_=from_,
        apply_=apply_flag,
        limit=limit,
        mixin_extensions=mixin_extensions,
    )
```

Notes:
- `CommonsError` must be importable at the top of cli.py (it likely already is; verify before adding an import).
- The kwarg `mixin_extensions=` is passed through `_promote_kind_cmd` to `plan_promote`. The next step is wiring `_promote_kind_cmd` to accept and forward it.

- [ ] **Step 4: Forward `mixin_extensions` through `_promote_kind_cmd`**

Find `_promote_kind_cmd` in `cli.py` (it's the shared handler used by paper/topic/theme/dataset). Add `mixin_extensions: tuple[ProfileComponent, ...] = ()` as a keyword-only parameter, defaulted so paper/topic/theme callers don't need to pass it:

```python
def _promote_kind_cmd(
    *,
    kind: PromoteKindConfig,
    entity_id: str | None,
    from_: tuple[str, ...],
    apply_: bool,
    limit: int | None,
    mixin_extensions: tuple["ProfileComponent", ...] = (),
) -> None:
    # ... existing body ...
    plan = plan_promote(
        discovery,
        commons_root=root,
        kind=kind,
        from_order=list(from_),
        mixin_extensions=mixin_extensions,    # NEW
    )
    # ... rest unchanged ...
```

The exact location of the `plan_promote(...)` call inside `_promote_kind_cmd` is at `cli.py:568` (per the earlier grep). The fix is one extra kwarg on that call site.

- [ ] **Step 5: Run targeted tests**

Run: `uv run pytest science/tests/ -k 'promote and dataset' -v -q`
Expected: existing dataset promote tests still pass (since `mixin_extensions=()` by default).

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/commons/cli.py
git commit -m "feat(commons-cli): add --mixin to promote dataset

Registers --mixin (repeatable) on `science commons promote dataset`
only. Sugar form (\"bio.matrix\") resolves to the highest installed
extension-bio-matrix-*.json version; explicit form (\"bio.matrix/1.0\")
is parsed verbatim. Resolved tuple is validated for stacking rules
(≤1 structural, ≤1 domain) before plan_promote runs. Paper/topic/
theme keep their existing surface — --mixin is not registered on
those, so Click emits its standard \"no such option\" UsageError if
attempted."
```

---

### Task 16: CLI happy-path integration test

**Files:**
- Test: `science/tests/test_commons_promote_dataset_mixin.py` (new)

- [ ] **Step 1: Write the integration test**

The fixture pattern mirrors `science/tests/test_commons_promote_dataset_discovery.py:14-36`. Key requirements that the in-tree implementation enforces and that must be reproduced:

- Project is a committed git repo (discovery walks `git ls-files`).
- Datapackage is **JSON** (`promote.py:1519`), named `datapackage.json`.
- Every resource path declared in the datapackage must exist on disk (`promote.py:1550` raises `PromoteResourceMissingError` if not).
- `--from <slug>` resolves through `science_tool.commons.promote.resolve_project_by_id` (`promote.py:371`); tests monkeypatch this to return the temp directory.
- Commons root env var is **`SCIENCE_COMMONS_ROOT`**, not `COMMONS_ROOT` (`config.py:35`).

Create `science/tests/test_commons_promote_dataset_mixin.py`:

```python
"""End-to-end CLI tests for `science commons promote dataset --mixin`."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest
from click.testing import CliRunner

from science_tool.commons.cli import commons_group


def _make_project_tree(tmp_path: Path) -> Path:
    """Build a minimal project source tree with one bulk RNA-seq dataset,
    committed to git so discovery's `git ls-files` finds it."""
    proj = tmp_path / "proj-rnaseq"
    (proj / "doc" / "datasets").mkdir(parents=True)
    (proj / "data" / "mockrna").mkdir(parents=True)

    (proj / "doc" / "datasets" / "data-mockrna.md").write_text(
        """---
id: dataset:mockrna
type: dataset
title: Mock RNA-seq dataset
description: Synthetic fixture for Phase H CLI tests.
datapackage: data/mockrna/datapackage.json
origin: external
tier: use-now
access:
  level: public
  verified: true
created: "2026-05-19"
updated: "2026-05-19"
species: ["Homo sapiens"]
assay: bulk-rnaseq
n_rows: 20530
n_cols: 100
value_dtype: int32
feature_axis: rows
---

# Mock RNA-seq

Body content.
""",
        encoding="utf-8",
    )
    (proj / "data" / "mockrna" / "datapackage.json").write_text(
        json.dumps(
            {
                "name": "mockrna",
                "resources": [
                    {
                        "name": "counts",
                        "path": "counts.tsv",
                        "format": "tsv",
                        "mediatype": "text/tab-separated-values",
                    }
                ],
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    (proj / "data" / "mockrna" / "counts.tsv").write_text("gene\ts1\n", encoding="utf-8")

    subprocess.run(["git", "init", "-q", str(proj)], check=True)
    subprocess.run(["git", "-C", str(proj), "add", "."], check=True)
    subprocess.run(
        [
            "git", "-C", str(proj),
            "-c", "user.email=t@t",
            "-c", "user.name=t",
            "commit", "-q", "-m", "init",
        ],
        check=True,
    )
    return proj


def _setup_proj_and_commons(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> tuple[Path, Path]:
    """Build proj tree, init commons, monkeypatch the project resolver, set
    the SCIENCE_COMMONS_ROOT env var. Returns (proj_root, commons_root)."""
    from science_tool.commons.bootstrap import init_commons

    proj = _make_project_tree(tmp_path)
    commons = tmp_path / "commons"
    init_commons(commons)

    monkeypatch.setattr(
        "science_tool.commons.promote.resolve_project_by_id",
        lambda _slug: proj,
    )
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(commons))
    return proj, commons


def test_promote_dataset_with_matrix_and_rnaseq_succeeds(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Promote a bulk-rnaseq dataset with --mixin bio.matrix --mixin bio.rnaseq.
    Canonical entity.md carries the four-segment schema_profile and the bio
    fields in canonical (not overlay)."""
    _proj, commons = _setup_proj_and_commons(tmp_path, monkeypatch)

    result = CliRunner().invoke(
        commons_group,
        [
            "promote", "dataset",
            "--from", "proj-rnaseq",
            "--slug", "mockrna",
            "--mixin", "bio.matrix",
            "--mixin", "bio.rnaseq",
            "--apply",
        ],
    )
    assert result.exit_code == 0, result.output

    entity_path = commons / "datasets" / "mockrna" / "entity.md"
    assert entity_path.is_file(), f"expected canonical entity.md at {entity_path}"
    entity = entity_path.read_text()
    assert (
        "schema_profile: "
        "science-entity-base/1.0+dataset/1.0+bio.matrix/1.0+bio.rnaseq/1.0"
        in entity
    )
    # Bio fields landed in canonical:
    assert "value_dtype: int32" in entity
    assert "assay: bulk-rnaseq" in entity
    assert "feature_axis: rows" in entity
    assert "Homo sapiens" in entity
```

- [ ] **Step 2: Run to verify it passes**

Run: `uv run pytest science/tests/test_commons_promote_dataset_mixin.py -v`
Expected: 1 passed.

- [ ] **Step 3: Commit**

```bash
git add science/tests/test_commons_promote_dataset_mixin.py
git commit -m "test(commons-cli): promote dataset --mixin bio.matrix bio.rnaseq happy path"
```

---

### Task 17: CLI failure-case integration tests

**Files:**
- Modify: `science/tests/test_commons_promote_dataset_mixin.py` (append failure cases)

- [ ] **Step 1: Append the failure-case tests**

Append to `science/tests/test_commons_promote_dataset_mixin.py`:

```python
def _invoke_with(
    args: list[str], tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    """Set up proj + commons (with monkeypatched project resolver +
    SCIENCE_COMMONS_ROOT env var), then invoke commons_group with the
    given extra args."""
    _setup_proj_and_commons(tmp_path, monkeypatch)
    return CliRunner().invoke(
        commons_group,
        ["promote", "dataset", "--from", "proj-rnaseq", "--slug", "mockrna", *args],
    )


def test_two_structural_mixins_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = _invoke_with(
        ["--mixin", "bio.matrix", "--mixin", "bio.table", "--apply"],
        tmp_path, monkeypatch,
    )
    assert result.exit_code != 0
    assert "structural" in result.output.lower()
    # No commons write happened (atomic abort):
    assert not (tmp_path / "commons" / "datasets" / "mockrna" / "entity.md").exists()


def test_two_domain_mixins_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = _invoke_with(
        ["--mixin", "bio.rnaseq", "--mixin", "bio.cna", "--apply"],
        tmp_path, monkeypatch,
    )
    assert result.exit_code != 0
    assert "domain" in result.output.lower()


def test_sugar_form_unknown_mixin_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    result = _invoke_with(
        ["--mixin", "bio.bogus", "--apply"], tmp_path, monkeypatch,
    )
    assert result.exit_code != 0
    assert "bio.bogus" in result.output


def test_explicit_form_unknown_mixin_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Explicit form (bio.bogus/1.0) parses syntactically and passes the
    stacking-rule guard; the missing schema surfaces during validator
    composition and is rewrapped by _validate_artifact as
    PromoteMixinResolutionError."""
    result = _invoke_with(
        ["--mixin", "bio.bogus/1.0", "--apply"], tmp_path, monkeypatch,
    )
    assert result.exit_code != 0
    assert "bio.bogus" in result.output


def test_mixin_on_paper_kind_yields_usage_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`promote paper --mixin ...` must fail with Click's `No such option`
    error — --mixin is not registered on the paper command."""
    # Same setup so the paper command can attempt discovery (it should
    # fail earlier with Click's option-parse error, but using the same
    # fixture avoids accidentally exercising a different failure mode).
    _setup_proj_and_commons(tmp_path, monkeypatch)
    result = CliRunner().invoke(
        commons_group,
        [
            "promote", "paper",
            "--from", "proj-rnaseq",
            "--mixin", "bio.rnaseq",
        ],
    )
    assert result.exit_code != 0
    assert "no such option" in result.output.lower() or "--mixin" in result.output
```

- [ ] **Step 2: Run to verify they pass**

Run: `uv run pytest science/tests/test_commons_promote_dataset_mixin.py -v`
Expected: all (1 happy-path + 5 failure-case) tests pass.

- [ ] **Step 3: Commit**

```bash
git add science/tests/test_commons_promote_dataset_mixin.py
git commit -m "test(commons-cli): cover --mixin stacking violations and unknown extensions"
```

---

### Task 18: Make sure nothing in Phase G regressed

**Files:**
- (No code changes — verification only.)

- [ ] **Step 1: Full repo test**

Run: `uv run pytest science/model/tests/ science/tests/ -q`
Expected: all green.

If any test fails:
- For tests in `science/model/tests/`: likely a schema test mismatch — re-check Task 5 fixture migration.
- For tests in `science/tests/`: likely a promote-side regression — re-check Task 11 (signature change) or Task 14 (PromoteResult/PromotePlan default fields).

- [ ] **Step 2: Lint**

Run: `uv run ruff check science/src/science_tool/commons/ science/model/src/science_model/entity_schema/ science/model/src/science_model/schemas/`
Expected: clean (or only pre-existing warnings).

- [ ] **Step 3: Commit (only if there were any cleanup fixes)**

If anything had to be touched as cleanup:

```bash
git add <files>
git commit -m "fix(phase-h): regression sweep after bio extensions land"
```

Otherwise skip this commit.

---

## Phase H.4 — Pilot smoke test runbook (Task 19)

### Task 19: Pilot — promote `dataset:GSE131651` with bio mixins

**Files:**
- Modify: `multiple-myeloma/doc/datasets/data-gse131651-shah2019-nsd2.md` (hand-edit frontmatter to add bio fields). Path resolves under `~/d/cancer/cancer-types/multiple-myeloma/`.
- Document: append to `docs/plans/2026-05-19-commons-bio-extensions-plan.md` (this file) a "Pilot outcome" section.

This task is a **runbook**, not unit testing. The point is to take one real MM dataset through the end-to-end promote-with-mixin flow and validate the result by inspection.

- [ ] **Step 1: Inspect the existing project entity**

```bash
sed -n '1,40p' ~/d/cancer/cancer-types/multiple-myeloma/doc/datasets/data-gse131651-shah2019-nsd2.md
```

Note the existing frontmatter — id slug, accessions, modality references in the body.

- [ ] **Step 2: Add bio frontmatter fields to the project-side entity**

Hand-edit `~/d/cancer/cancer-types/multiple-myeloma/doc/datasets/data-gse131651-shah2019-nsd2.md`:

Add (or amend, if already present) under the existing YAML frontmatter:

```yaml
# bio.matrix fields:
n_rows: <count of genes/probes>
n_cols: <count of samples>
value_dtype: "int32"          # or float32 — set by what the data file actually contains
feature_axis: "rows"

# bio.rnaseq fields:
species: ["Homo sapiens"]
assay: "bulk-rnaseq"          # confirm against the GEO record
reference_genome: "GRCh38"    # confirm against the GEO record
```

Concrete counts (`n_rows`, `n_cols`) should come from inspecting the dataset; if the data isn't readily available, use the metadata-reported sample count and gene count.

- [ ] **Step 3: Run the promote with mixins**

```bash
cd /mnt/ssd/Dropbox/science
uv run science commons promote dataset \
    --from multiple-myeloma \
    --slug GSE131651 \
    --mixin bio.matrix \
    --mixin bio.rnaseq \
    --apply
```

(`--from` takes the registered project id from `science.yaml` —
`multiple-myeloma` per `~/d/cancer/cancer-types/multiple-myeloma/science.yaml`.
Pass the id, not a path.)

Expected output:
- `Plan: 1 canonical entities, ...`
- A commit on the commons repo recording the dataset promote.
- An audit log file under `~/d/science-shared/.migrations/`.

- [ ] **Step 4: Verify the canonical entity**

```bash
cat ~/d/science-shared/datasets/GSE131651/entity.md | head -25
```

Verify:
- `schema_profile: science-entity-base/1.0+dataset/1.0+bio.matrix/1.0+bio.rnaseq/1.0`
- `n_rows`, `n_cols`, `value_dtype`, `feature_axis` present.
- `species` is an array.
- `assay: bulk-rnaseq`.

- [ ] **Step 5: Verify the audit log**

```bash
ls ~/d/science-shared/.migrations/ | tail -3
cat ~/d/science-shared/.migrations/<latest>.yaml | grep -A2 mixin_extensions
```

Verify:
- `mixin_extensions: [bio.matrix/1.0, bio.rnaseq/1.0]`

- [ ] **Step 6: Verify `science commons show` round-trips**

```bash
uv run science commons show dataset:GSE131651
```

Expected: no validation errors; the show output includes the composed schema_profile and all bio fields.

- [ ] **Step 7: Append pilot outcome to this plan**

Append a short section at the end of `docs/plans/2026-05-19-commons-bio-extensions-plan.md`:

```markdown
## Pilot outcome (Task 19)

**Date run:** YYYY-MM-DD
**Dataset:** dataset:GSE131651 (Shah 2019 — NSD2 KO bulk RNA-seq)
**Mixins applied:** bio.matrix/1.0 + bio.rnaseq/1.0

- canonical schema_profile: science-entity-base/1.0+dataset/1.0+bio.matrix/1.0+bio.rnaseq/1.0
- audit log: ~/d/science-shared/.migrations/<filename>.yaml
- commons commit: <SHA>

Notes / surprises: <any issues encountered, hand-fixes applied,
follow-ons to file>.
```

- [ ] **Step 8: Commit the pilot outcome (NOT the commons repo)**

```bash
cd /mnt/ssd/Dropbox/science
git add docs/plans/2026-05-19-commons-bio-extensions-plan.md
git commit -m "docs(phase-h): record pilot outcome for dataset:GSE131651"
```

The commons-repo commit from the promote itself happens in `~/d/science-shared/`, which is a separate repo and is not pushed to GitHub.

---

## Self-review notes (writing-plans skill, step 7)

**Spec coverage:**
- §3.1 (mixin map) → Tasks 1–5 (schemas + rnaseq patch).
- §3.2 (stacking rules: ≤1 structural, ≤1 domain) → Task 9.
- §3.3 (field bucketing via merge policy from active profile) → Tasks 10–12.
- §3.4 (composition > inheritance) — design property, satisfied by schemas in Tasks 1–5.
- §4 (per-mixin field definitions) → Tasks 1–5.
- §5 (no validator changes) — verified by Tasks 6–7 (tests only).
- §6.1–§6.2 (CLI shape, sugar resolver, validation order) → Task 15.
- §6.3 (pipeline plumbing — `_active_profile`, plan_promote signature, `_render_canonical`) → Tasks 10, 11, 12.
- §6.4 (help text matching stacking rule) → Task 15.
- §6.5 (`PromoteMixinStackingError`, `PromoteMixinResolutionError` subclass `PromoteInputError`; `_validate_artifact` catch) → Tasks 8, 13.
- §7 (data flow) — assembled across Tasks 11–17.
- §8.1 (per-mixin unit tests) → Tasks 1–5.
- §8.2 (validator composition tests) → Tasks 6–7.
- §8.3 (stacking-rule unit tests) → Task 9.
- §8.4 (promote integration tests) → Tasks 12, 16, 17.
- §8.5 (pilot runbook) → Task 19.
- §9 (sub-phases H.1–H.4) → all tasks grouped by phase.
- §10 (open questions) — design-level, no implementation tasks.
- §11 (files touched) → coverage verified across Tasks 1–17.
- §12 (acceptance criteria) — each criterion has at least one test in Tasks 1–17.

**Type / signature consistency:**
- `_active_profile(kind, extensions) -> ProfileString` — defined Task 10; used in Tasks 11, 12.
- `_validate_mixin_stacking(extensions) -> None` — defined Task 9; used in Task 15.
- `mixin_extensions: tuple[ProfileComponent, ...]` — name + type consistent across Tasks 11, 14, 15.
- `PromoteMixinStackingError` / `PromoteMixinResolutionError` — defined Task 8 as subclasses of `PromoteInputError`; used in Tasks 9, 13, 15.
- `_render_canonical(..., active_profile=)` — Task 11 adds the kwarg; Task 12 passes it.

**Placeholders:** none. Every step has either exact code, exact commands, or explicit "look at this existing fixture file" pointers.

---

## Execution

Plan complete and saved to `docs/plans/2026-05-19-commons-bio-extensions-plan.md`.

Two execution options:

1. **Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration. Cleaner isolation per task; good for a 19-task plan.
2. **Inline Execution** — Execute tasks in this session using `executing-plans`, batch execution with checkpoints for review.

Which approach?

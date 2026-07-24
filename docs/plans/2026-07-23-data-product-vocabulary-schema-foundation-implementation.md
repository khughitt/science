# Data-Product Vocabulary & Schema Foundation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Establish a canonical data-product term catalog in `science-model` and repair the live capability-schema drift by introducing entity-schema generation 3, so that a single `{data_product, qualifiers}` capability shape is validated and matched consistently across enrolled bio/assay projects — while generation-2 projects remain byte-for-byte untouched.

**Architecture:** A new `science_model/data_products/` catalog (plain-Pydantic contract + `importlib.resources` loader, mirroring `ontologies/`) becomes the sole owner of data-product terms and their `broader` DAG. Entity-schema versioning gains a **generation matrix**: the single `ENTITY_SCHEMA_VERSION` constant is replaced by a generation-aware dispatch (gen 2 → dataset/2.0 + hypothesis/1.0; gen 3 → dataset/3.0 + hypothesis/2.0), selected by the project's *declared* `entity_schema_version`, never by input shape. New `mixin-dataset-3.0.json` and `mixin-hypothesis-2.0.json` retype the capability field to `{data_product, qualifiers}`. One canonical generation-aware capability parser backs both the `validate` check and the matcher; the matcher keeps its existing string-map path as the gen-1/2 branch. Migration is a single transactional per-project operation mirroring the hypothesis migrator (`migrate_hypothesis.py`): plan → journal post-images → write → set the pin to 3 **last** → confirm → clear journal, with `--resume`. A human-authored `value→term` crosswalk with adjudicated dispositions drives it, gated by a review checkpoint.

**Tech Stack:** Python 3.12, Pydantic v2, JSON Schema (draft 2020-12), Click, `uv`, pytest, `importlib.resources`, hatchling.

## Global Constraints

- **No AI-attribution trailers/footers** on any commit, PR, or comment (no `Co-Authored-By`, no "Generated with Claude Code").
- **No "legacy"/"compatibility" layers** and **no `Unified` prefix**; composition over inheritance; explicit over defensive; **fail early — no silent fallbacks**.
- **Never tune metadata/content to silence a check** — a check must be able to fail; if evidence and a conclusion conflict, ask rather than adjust.
- In doc/code path text use **`~/d/`**, never `/home/keith/d/` or `/mnt/ssd/Dropbox/`.
- **All `uv run` from the package directory** (`science/` or `science/model/`) — there is no root `pyproject.toml`.
- **CLI/package tests:** `cd science && uv run --frozen pytest`. **Model tests:** `cd science/model && uv run --frozen pytest`. Lint/types from `science/`: `uv run ruff check`, `uv run pyright`.
- **Pyright** is configured once by `/pyrightconfig.json` (repo root); do not add `[tool.pyright]` to any package.
- **Versioning is copy-then-bump:** new versions are new files; `mixin-dataset-2.0.json` and `mixin-hypothesis-1.0.json` are **retained** as rollback targets — never edited in place, never deleted.
- **The pin is the sole authority:** `entity_schema_version` is an authored declaration read through `validated_entity_schema_version`; absence means generation 1. Nothing infers the generation from file shape.
- **`Entity` uses `extra="allow"`/`extra="ignore"`** — capability fields stay **preserved-raw**; do NOT add a typed capability object field to `Entity`.
- **Generation-2 projects must remain untouched** by every change in this plan. Every task that touches a generation-sensitive path carries an explicit gen-2 regression test.
- **Commit after each task's review passes.** Commit/push to `origin` only when the user asks; work on a branch (worktree), never `main` directly.
- **Tasks 12–14 are human-review checkpoints** — they touch `~/d/r/mm30`, `~/d/r/cbioportal`, `~/d/health/processes/post-acute-infection`, and `~/d/science-commons`, and encode granularity decisions. Do NOT execute them as blind subagent work; stop and get explicit human approval at each.

---

## File Structure

**New (science-model):**
- `science/model/src/science_model/data_products/__init__.py` — loader (mirrors `ontologies/__init__.py`), reads within the `importlib.resources` lifetime.
- `science/model/src/science_model/data_products/schema.py` — closed Pydantic models + `build_catalog()` (raises `CatalogError`).
- `science/model/src/science_model/data_products/catalog.yaml` — term catalog (contents authored in Task 12).
- `science/model/src/science_model/schemas/mixin-dataset-3.0.json`, `mixin-hypothesis-2.0.json`.
- `science/model/tests/test_data_products.py`, `test_mixin_dataset_3_0.py`, `test_mixin_hypothesis_2_0.py`, `test_entity_schema_generation.py`.

**Modified (science-model):**
- `science/model/src/science_model/entity_schema/profile.py` — generation-aware default profile selection.
- `resolve_profile` (in `science_model/entity_schema/`) — forward a `generation` argument.

**New (science CLI):**
- `science/src/science_tool/datasets/capability_shape.py` — the single canonical generation-aware capability parser/shape validator.
- `science/src/science_tool/datasets/capability_pairs.py` — observed-shape enumeration.
- `science/src/science_tool/datasets/capability_crosswalk.py` — crosswalk loader with strict contract + dispositions.
- `science/src/science_tool/datasets/capability_migration.py` — transactional per-project capability migrator (mirrors `migrate_hypothesis.py`).
- `science/src/science_tool/datasets/capability_crosswalk.yaml` — the authored crosswalk (Task 12).

**Modified (science CLI):**
- `science/src/science_tool/project_config.py:249` — widen the Literal.
- `science/src/science_tool/entity_profiles.py` — `ARMED_SCHEMA_GENERATIONS`; thread generation.
- `science/src/science_tool/migrate_hypothesis.py:42,245,250,253` — local `_TARGET_GENERATION = 2`.
- `science/src/science_tool/graph/sources.py` — arm for gen 2 & 3; dataset gen-3 hook.
- `science/src/science_tool/datasets/capabilities.py` — generation-aware matcher (gen-1/2 string-map branch preserved).
- `science/src/science_tool/dataset_prioritize.py:541` — pass generation + catalog to `capability_fit`.
- `science/src/science_tool/validate/checks/dataset_capabilities.py` — generation-aware shape check via `capability_shape`.
- `science/src/science_tool/datasets/cli.py` — `capability-pairs`, `migrate-capabilities` subcommands.

**Test locations (confirmed present):**
- Schema-first load: `science/tests/test_schema_first_load.py`.
- Capability check: `science/tests/validate/test_checks_dataset_capabilities.py`.
- Dataset CLI group: `science/src/science_tool/datasets/cli.py`.

**Validation entry points (confirmed):**
- Project: `cd science && uv run --frozen science validate --project-root <path>`.
- Commons: `cd science && SCIENCE_COMMONS_ROOT=~/d/science-commons uv run --frozen science commons validate`.

---

## Task 1: Data-product catalog contract (science-model)

**Files:**
- Create: `science/model/src/science_model/data_products/schema.py`
- Create: `science/model/src/science_model/data_products/__init__.py`
- Create: `science/model/src/science_model/data_products/catalog.yaml` (skeleton — real contents in Task 12)
- Test: `science/model/tests/test_data_products.py`

**Interfaces:**
- Produces: `DataProductTerm` and `DataProductCatalog` (both `extra="forbid"`); `build_catalog(payload: dict) -> DataProductCatalog` raising `CatalogError` for semantic violations; `load_catalog() -> DataProductCatalog`; `load_catalog_from(path: Path) -> DataProductCatalog`. `DataProductCatalog` exposes `by_id: dict[str, DataProductTerm]` and `descends(child_id, ancestor_id) -> bool` (reflexive + transitive). Structural violations (bad `schema_version`, unknown keys, malformed ids) raise `pydantic.ValidationError`; semantic violations (duplicate ids, unresolved/self/cyclic `broader`) raise `CatalogError`.

- [ ] **Step 1: Write the failing tests**

```python
# science/model/tests/test_data_products.py
import pytest
from pydantic import ValidationError
from science_model.data_products import (
    DataProductCatalog, CatalogError, build_catalog, load_catalog,
)


def _cat(terms, version="1"):
    return {"schema_version": version, "terms": terms}


def _term(tid, broader=None, assay="ge"):
    return {"id": tid, "label": tid, "assay": assay, "technology": "", "broader": broader or []}


def test_round_trip():
    cat = build_catalog(_cat([
        _term("data-product:gene-expression"),
        _term("data-product:gene-expression-bulk-rna", ["data-product:gene-expression"]),
    ]))
    assert cat.model_dump()["terms"][1]["broader"] == ["data-product:gene-expression"]


def test_rejects_bad_schema_version():
    with pytest.raises(ValidationError):
        build_catalog(_cat([], version="2"))


def test_rejects_unknown_field_on_term():
    with pytest.raises(ValidationError):
        build_catalog(_cat([{**_term("data-product:x"), "broarder": []}]))  # typo'd key


def test_rejects_malformed_id():
    with pytest.raises(ValidationError):
        build_catalog(_cat([_term("gene-expression")]))  # missing data-product: prefix


def test_rejects_empty_mappings_ok_but_empty_label():
    with pytest.raises(ValidationError):
        build_catalog(_cat([{"id": "data-product:x", "label": "", "assay": "ge",
                             "technology": "", "broader": []}]))


def test_rejects_duplicate_ids():
    with pytest.raises(CatalogError):
        build_catalog(_cat([_term("data-product:x"), _term("data-product:x")]))


def test_rejects_unresolved_broader():
    with pytest.raises(CatalogError):
        build_catalog(_cat([_term("data-product:x", ["data-product:missing"])]))


def test_rejects_self_broader():
    with pytest.raises(CatalogError):
        build_catalog(_cat([_term("data-product:x", ["data-product:x"])]))


def test_rejects_cyclic_broader():
    with pytest.raises(CatalogError):
        build_catalog(_cat([
            _term("data-product:a", ["data-product:b"]),
            _term("data-product:b", ["data-product:a"]),
        ]))


def test_descends_is_reflexive_and_transitive():
    cat = build_catalog(_cat([
        _term("data-product:root"),
        _term("data-product:mid", ["data-product:root"]),
        _term("data-product:leaf", ["data-product:mid"]),
    ]))
    assert cat.descends("data-product:leaf", "data-product:leaf")
    assert cat.descends("data-product:leaf", "data-product:root")
    assert not cat.descends("data-product:root", "data-product:leaf")


def test_packaged_catalog_loads():
    cat = load_catalog()
    assert cat.schema_version == "1"
    assert isinstance(cat.by_id, dict)
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd science/model && uv run --frozen pytest tests/test_data_products.py -q`
Expected: FAIL (module missing).

- [ ] **Step 3: Write `schema.py` (closed models + boundary validation)**

```python
# science/model/src/science_model/data_products/schema.py
"""The canonical data-product term catalog contract.

One owner for data-product terms and their `broader` DAG. Plain Pydantic, mirroring
ontologies. Models are CLOSED (extra="forbid") so a typo'd key fails loudly instead
of vanishing. Structural checks are the models'; semantic (dup/DAG) checks are
`build_catalog`'s, which raises CatalogError at the loader boundary -- so callers
get one clean exception type, not a Pydantic wrapper.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

_ID_PATTERN = r"^data-product:[a-z0-9][a-z0-9-]*$"


class CatalogError(ValueError):
    """The data-product catalog is semantically invalid (dup id or broken broader DAG)."""


class DataProductTerm(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str = Field(pattern=_ID_PATTERN)
    label: str = Field(min_length=1)
    assay: str = Field(min_length=1)
    technology: str = ""
    broader: list[str] = Field(default_factory=list)


class DataProductCatalog(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: Literal["1"]
    terms: list[DataProductTerm]

    @property
    def by_id(self) -> dict[str, DataProductTerm]:
        return {t.id: t for t in self.terms}

    def descends(self, child_id: str, ancestor_id: str) -> bool:
        index = self.by_id
        if child_id not in index or ancestor_id not in index:
            return False
        seen: set[str] = set()
        stack = [child_id]
        while stack:
            current = stack.pop()
            if current == ancestor_id:
                return True
            if current in seen:
                continue
            seen.add(current)
            stack.extend(index[current].broader)
        return False


def build_catalog(payload: dict) -> DataProductCatalog:
    """Validate structure (Pydantic) then integrity (CatalogError), returning the catalog."""
    catalog = DataProductCatalog.model_validate(payload)
    index: dict[str, DataProductTerm] = {}
    for term in catalog.terms:
        if term.id in index:
            raise CatalogError(f"duplicate term id {term.id!r}")
        index[term.id] = term
    for term in catalog.terms:
        for parent in term.broader:
            if parent == term.id:
                raise CatalogError(f"term {term.id!r} lists itself as broader")
            if parent not in index:
                raise CatalogError(f"term {term.id!r} broader {parent!r} does not resolve")
    _reject_cycles(index)
    return catalog


def _reject_cycles(index: dict[str, DataProductTerm]) -> None:
    WHITE, GREY, BLACK = 0, 1, 2
    colour = {tid: WHITE for tid in index}

    def visit(tid: str, path: list[str]) -> None:
        colour[tid] = GREY
        for parent in index[tid].broader:
            if colour[parent] == GREY:
                raise CatalogError(f"broader cycle: {' -> '.join([*path, tid, parent])}")
            if colour[parent] == WHITE:
                visit(parent, [*path, tid])
        colour[tid] = BLACK

    for tid in index:
        if colour[tid] == WHITE:
            visit(tid, [])
```

- [ ] **Step 4: Write `__init__.py` (read inside the resource lifetime)**

```python
# science/model/src/science_model/data_products/__init__.py
"""Load the packaged data-product term catalog."""

from __future__ import annotations

from importlib.resources import as_file, files
from pathlib import Path

import yaml

from science_model.data_products.schema import (
    CatalogError, DataProductCatalog, DataProductTerm, build_catalog,
)

_PACKAGE = "science_model.data_products"
_CATALOG_FILE = "catalog.yaml"


def load_catalog_from(path: Path) -> DataProductCatalog:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return build_catalog(raw)


def load_catalog() -> DataProductCatalog:
    ref = files(_PACKAGE).joinpath(_CATALOG_FILE)
    with as_file(ref) as path:                      # read WITHIN the lifetime
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    return build_catalog(raw)


__all__ = [
    "CatalogError", "DataProductCatalog", "DataProductTerm",
    "build_catalog", "load_catalog", "load_catalog_from",
]
```

- [ ] **Step 5: Write the skeleton `catalog.yaml` (real contents in Task 12)**

```yaml
# science/model/src/science_model/data_products/catalog.yaml
# Canonical data-product term catalog. SEED ONLY — full population in Task 12
# (the value->term crosswalk authoring, human review checkpoint).
schema_version: "1"
terms:
  - id: data-product:gene-expression
    label: Gene-expression measurement
    assay: gene-expression
    technology: ""
    broader: []
  - id: data-product:gene-expression-bulk-rna
    label: Bulk RNA gene-expression matrix
    assay: gene-expression
    technology: bulk-rna
    broader: [data-product:gene-expression]
```

- [ ] **Step 6: Run to verify it passes**

Run: `cd science/model && uv run --frozen pytest tests/test_data_products.py -q`
Expected: PASS (all cases).

- [ ] **Step 7: Lint/type and commit**

Run: `cd science && uv run ruff check && uv run pyright`
```bash
git add science/model/src/science_model/data_products science/model/tests/test_data_products.py
git commit -m "feat(model): add closed data-product catalog contract with broader DAG validation"
```

---

## Task 2: Widen `entity_schema_version` to admit generation 3

**Files:**
- Modify: `science/src/science_tool/project_config.py:249`
- Test: `science/tests/test_project_config.py` (add cases; the file exists)

**Interfaces:**
- Produces: `entity_schema_version: Literal[1, 2, 3] | None`. `validated_entity_schema_version` accepts `3`, rejects `"3"` and near-miss keys.

- [ ] **Step 1: Write the failing test**

```python
# add to science/tests/test_project_config.py
import pytest
from science_tool.project_config import validated_entity_schema_version


def test_generation_3_is_accepted():
    assert validated_entity_schema_version({"entity_schema_version": 3}) == 3


def test_generation_3_as_string_is_rejected():
    with pytest.raises(Exception):
        validated_entity_schema_version({"entity_schema_version": "3"})
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd science && uv run --frozen pytest tests/test_project_config.py -k generation -q`
Expected: FAIL.

- [ ] **Step 3: Widen the Literal**

`science/src/science_tool/project_config.py:249`:
```python
    entity_schema_version: Literal[1, 2, 3] | None = None
```
Read `validated_entity_schema_version`; if it hardcodes the allowed set `{1, 2}`, extend it to `{1, 2, 3}`. Leave `_reject_near_miss_keys` unchanged.

- [ ] **Step 4: Run to verify it passes**

Run: `cd science && uv run --frozen pytest tests/test_project_config.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/project_config.py science/tests/test_project_config.py
git commit -m "feat(config): admit entity_schema_version generation 3"
```

---

## Task 3: `mixin-dataset-3.0.json` — dataset capability shape gen 3

**Files:**
- Create: `science/model/src/science_model/schemas/mixin-dataset-3.0.json`
- Test: `science/model/tests/test_mixin_dataset_3_0.py`

**Interfaces:**
- Produces: `mixin-dataset-3.0.json` — a copy of `mixin-dataset-2.0.json` with `provided_capabilities` retyped to an array of `{data_product, qualifiers}` objects (closed, `data_product` required, pattern `^data-product:[a-z0-9][a-z0-9-]*$`). `mixin-dataset-2.0.json` untouched.

- [ ] **Step 1: Write the failing test** (note: dataset ids need ≥2 chars after the prefix per `^dataset:[a-z0-9][a-z0-9-]{1,63}$`)

```python
# science/model/tests/test_mixin_dataset_3_0.py
import json
from pathlib import Path
from jsonschema import Draft202012Validator

SCHEMAS = Path(__file__).resolve().parents[1] / "src" / "science_model" / "schemas"


def _schema():
    return json.loads((SCHEMAS / "mixin-dataset-3.0.json").read_text())


def _base(**caps):
    return {"id": "dataset:demo", "kind": "dataset", "origin": "derived", "tier": "track",
            "datapackage": "dp",
            "derivation": {"kind": "member_of", "parent_dataset": "dataset:parent", "member_key": "k"},
            **caps}


def test_object_capability_validates():
    Draft202012Validator(_schema()).validate(_base(provided_capabilities=[
        {"data_product": "data-product:gene-expression-bulk-rna",
         "qualifiers": {"cohort_design": "case-control"}}]))


def test_legacy_string_capability_is_rejected():
    errors = list(Draft202012Validator(_schema()).iter_errors(
        _base(provided_capabilities=["gene-expression"])))
    assert errors


def test_unknown_key_in_capability_is_rejected():
    errors = list(Draft202012Validator(_schema()).iter_errors(_base(provided_capabilities=[
        {"data_product": "data-product:gene-expression", "assay": "x"}])))
    assert errors


def test_2_0_still_types_strings():
    two = json.loads((SCHEMAS / "mixin-dataset-2.0.json").read_text())
    assert two["properties"]["provided_capabilities"]["items"] == {"type": "string"}
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd science/model && uv run --frozen pytest tests/test_mixin_dataset_3_0.py -q`
Expected: FAIL (file missing).

- [ ] **Step 3: Create `mixin-dataset-3.0.json`**

Copy `mixin-dataset-2.0.json` verbatim. Change the header:
```json
  "$id": "https://schemas.science/mixin-dataset-3.0.json",
  "title": "science entity dataset mixin",
  "$comment": "3.0 retypes provided_capabilities from an array of strings to an array of {data_product, qualifiers} objects (capability-drift repair; docs/plans/2026-07-23-data-product-vocabulary-and-skill-coverage-design.md). mixin-dataset-2.0.json is RETAINED as rollback and for pre-3.0 consumers. Do not edit or delete it.",
```
Replace the `provided_capabilities` property:
```json
    "provided_capabilities": {"type": "array", "items": {"$ref": "#/$defs/data_product_capability"}},
```
Add to `$defs`:
```json
    "data_product_capability": {
      "type": "object",
      "additionalProperties": false,
      "required": ["data_product"],
      "properties": {
        "data_product": {"type": "string", "pattern": "^data-product:[a-z0-9][a-z0-9-]*$"},
        "qualifiers": {
          "type": "object",
          "propertyNames": {"pattern": "\\S"},
          "additionalProperties": {"type": "string", "pattern": "\\S"}
        }
      }
    }
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd science/model && uv run --frozen pytest tests/test_mixin_dataset_3_0.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/model/src/science_model/schemas/mixin-dataset-3.0.json science/model/tests/test_mixin_dataset_3_0.py
git commit -m "feat(model): add mixin-dataset-3.0 with data-product capability shape"
```

---

## Task 4: `mixin-hypothesis-2.0.json` — required-capability shape gen 3

**Files:**
- Create: `science/model/src/science_model/schemas/mixin-hypothesis-2.0.json`
- Test: `science/model/tests/test_mixin_hypothesis_2_0.py`

**Interfaces:**
- Produces: `mixin-hypothesis-2.0.json` — a copy of `mixin-hypothesis-1.0.json` with `required_capabilities`'s `capability_map` `$def` replaced by the `{data_product, qualifiers}` object. `mixin-hypothesis-1.0.json` untouched.

- [ ] **Step 1: Write the failing test**

```python
# science/model/tests/test_mixin_hypothesis_2_0.py
import json
from pathlib import Path
from jsonschema import Draft202012Validator

SCHEMAS = Path(__file__).resolve().parents[1] / "src" / "science_model" / "schemas"


def _schema():
    return json.loads((SCHEMAS / "mixin-hypothesis-2.0.json").read_text())


def _base(caps):
    return {"id": "hypothesis:0001", "kind": "hypothesis", "status": "active",
            "required_capabilities": caps}


def test_object_required_capability_validates():
    Draft202012Validator(_schema()).validate(_base([
        {"data_product": "data-product:gene-expression",
         "qualifiers": {"analysis_role": "mr_exposure"}}]))


def test_legacy_string_map_capability_is_rejected():
    assert list(Draft202012Validator(_schema()).iter_errors(
        _base([{"assay": "gene-expression", "modality": "bulk-rna"}])))


def test_unknown_key_in_capability_is_rejected():
    assert list(Draft202012Validator(_schema()).iter_errors(
        _base([{"data_product": "data-product:x", "modality": "bulk-rna"}])))


def test_1_0_capability_map_unchanged():
    one = json.loads((SCHEMAS / "mixin-hypothesis-1.0.json").read_text())
    assert one["$defs"]["capability_map"]["additionalProperties"] == {"type": "string", "pattern": "\\S"}
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd science/model && uv run --frozen pytest tests/test_mixin_hypothesis_2_0.py -q`
Expected: FAIL (file missing).

- [ ] **Step 3: Create `mixin-hypothesis-2.0.json`**

Copy `mixin-hypothesis-1.0.json` verbatim. Change `$id` to `https://schemas.science/mixin-hypothesis-2.0.json`; prepend to `$comment`: `"2.0 retypes required_capabilities entries to {data_product, qualifiers}; 1.0 is RETAINED as rollback. "`. Replace the `required_capabilities` property and its `$def`:
```json
    "required_capabilities": {
      "type": "array",
      "items": { "$ref": "#/$defs/data_product_capability" },
      "$comment": "Gen-3 shape: {data_product, qualifiers}. NO minItems: `[]` is `missing` to the WARN check; the schema must not promote it to a hard failure."
    },
```
Replace `$defs.capability_map` with:
```json
    "data_product_capability": {
      "type": "object",
      "additionalProperties": false,
      "required": ["data_product"],
      "properties": {
        "data_product": { "type": "string", "pattern": "^data-product:[a-z0-9][a-z0-9-]*$" },
        "qualifiers": {
          "type": "object",
          "propertyNames": { "pattern": "\\S" },
          "additionalProperties": { "type": "string", "pattern": "\\S" }
        }
      }
    }
```
Keep every other `$def` unchanged.

- [ ] **Step 4: Run to verify it passes**

Run: `cd science/model && uv run --frozen pytest tests/test_mixin_hypothesis_2_0.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/model/src/science_model/schemas/mixin-hypothesis-2.0.json science/model/tests/test_mixin_hypothesis_2_0.py
git commit -m "feat(model): add mixin-hypothesis-2.0 with data-product required-capability shape"
```

---

## Task 5: Generation matrix — generation-aware profile selection + gate arming

**Files:**
- Modify: `science/model/src/science_model/entity_schema/profile.py:88-121`
- Modify: `science/model/src/science_model/entity_schema/` — `resolve_profile` (find it: `rg "def resolve_profile" science/model/src`)
- Modify: `science/src/science_tool/entity_profiles.py:45,60-118`
- Modify: `science/src/science_tool/migrate_hypothesis.py:42,245,250,253`
- Modify: `science/src/science_tool/graph/sources.py:363-367`
- Test: `science/model/tests/test_entity_schema_generation.py`
- Test: `science/tests/test_schema_first_load.py` (gen-3 arming case + gen-2 regression)

**Interfaces:**
- Consumes: `mixin-dataset-3.0.json`, `mixin-hypothesis-2.0.json`.
- Produces: `default_profile_for_kind(kind, *, generation: int = 2) -> ProfileString`; `resolve_profile(kind, *, extensions, loader, generation: int = 2)`; `ARMED_SCHEMA_GENERATIONS = frozenset({2, 3})`; `load_project_schema(project_root, config=None, *, generation: int = 2)`; `ProjectSchema` gains `_generation: int`. `migrate_hypothesis.py` gets a module-local `_TARGET_GENERATION = 2` and stops importing `ENTITY_SCHEMA_VERSION`.

- [ ] **Step 1: Write the failing tests**

```python
# science/model/tests/test_entity_schema_generation.py
from science_model.entity_schema.profile import default_profile_for_kind


def test_generation_2_defaults_unchanged():
    assert default_profile_for_kind("dataset", generation=2).render().endswith("+dataset/2.0")
    assert default_profile_for_kind("hypothesis", generation=2).render().endswith("+hypothesis/1.0")


def test_generation_3_selects_new_mixins():
    assert default_profile_for_kind("dataset", generation=3).render().endswith("+dataset/3.0")
    assert default_profile_for_kind("hypothesis", generation=3).render().endswith("+hypothesis/2.0")


def test_generation_3_leaves_other_kinds_at_2_0():
    assert default_profile_for_kind("paper", generation=3).render().endswith("+paper/2.0")


def test_default_generation_is_2():
    assert default_profile_for_kind("dataset").render().endswith("+dataset/2.0")
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd science/model && uv run --frozen pytest tests/test_entity_schema_generation.py -q`
Expected: FAIL (`default_profile_for_kind` takes no `generation`).

- [ ] **Step 3: Make `default_profile_for_kind` generation-aware**

In `profile.py`, replace `_DEFAULT_MIXIN_VERSION` + `default_profile_for_kind` (keep `_BASE_VERSION_FOR_MIXIN`):
```python
_MIXIN_VERSION_BY_GENERATION: dict[int, dict[str, str]] = {
    2: {"dataset": "2.0", "paper": "2.0", "topic": "2.0", "theme": "2.0", "hypothesis": "1.0"},
    3: {"dataset": "3.0", "paper": "2.0", "topic": "2.0", "theme": "2.0", "hypothesis": "2.0"},
}


def default_profile_for_kind(kind: str, *, generation: int = 2) -> ProfileString:
    versions = _MIXIN_VERSION_BY_GENERATION.get(generation)
    if versions is None:
        raise ProfileParseError(
            f"unknown entity-schema generation {generation!r}; "
            f"expected one of {sorted(_MIXIN_VERSION_BY_GENERATION)}"
        )
    if kind not in versions:
        raise ProfileParseError(f"unknown kind {kind!r}; expected one of {sorted(versions)}")
    return parse_profile(f"{BASE_NAME}/{_BASE_VERSION_FOR_MIXIN[kind]}+{kind}/{versions[kind]}")
```
Extend `resolve_profile`'s signature with `generation: int = 2` and forward it to `default_profile_for_kind`.

- [ ] **Step 4: Fix the hypothesis migrator's constant import**

`migrate_hypothesis.py:42` currently imports `ENTITY_SCHEMA_VERSION`. Replace with a module-local target and drop the import:
```python
from science_tool.entity_profiles import ProjectSchema, load_project_schema
...
# This migrator's TARGET generation (gen-1 -> gen-2 hypotheses). Local and explicit:
# it is a migration destination, not the toolkit's armed-generation set.
_TARGET_GENERATION = 2
```
Update `_commit` (lines 245/250/253): `_set_entity_schema_version(project_root, _TARGET_GENERATION)`, `validated_entity_schema_version(raw) != _TARGET_GENERATION`, and the message.

- [ ] **Step 5: Arm the toolkit gate for gen 2 and gen 3**

`entity_profiles.py`: replace `ENTITY_SCHEMA_VERSION = 2` with
```python
# The generations that ARM schema-first validation. Absent/1 = unmigrated (untouched).
ARMED_SCHEMA_GENERATIONS = frozenset({2, 3})
```
Thread the generation through `ProjectSchema`/`load_project_schema`/`load_project_schema_if_pinned`:
```python
@dataclass(frozen=True, slots=True)
class ProjectSchema:
    validator: EntityValidator
    _extensions: dict[str, list[str]]
    _loader: SchemaLoader
    _generation: int = 2

    def profile_for(self, kind: str) -> ProfileString:
        return resolve_profile(kind, extensions=self._extensions.get(kind, []),
                               loader=self._loader, generation=self._generation)


def load_project_schema(project_root, config=None, *, generation: int = 2) -> ProjectSchema:
    ...
    schema = ProjectSchema(validator=EntityValidator(loader), _extensions=config.entity_extensions,
                           _loader=loader, _generation=generation)
    ...


def load_project_schema_if_pinned(project_root):
    ...
    version = validated_entity_schema_version(raw)
    if version not in ARMED_SCHEMA_GENERATIONS:
        return None
    return load_project_schema(project_root, load_project_config(project_root), generation=version)
```
Grep for `ENTITY_SCHEMA_VERSION` across the tree (`rg ENTITY_SCHEMA_VERSION science/`) and update every reference (there is the sources.py gate below; there may be tests — update those to `ARMED_SCHEMA_GENERATIONS`).

- [ ] **Step 6: Arm the load-path gate in `sources.py`**

`sources.py:363-367`:
```python
    declared = config.get("entity_schema_version")
    project_schema = (
        load_project_schema(project_root, generation=declared)
        if declared in ARMED_SCHEMA_GENERATIONS
        else None
    )
```
Update its import from `entity_profiles`.

- [ ] **Step 7: Add the arming/regression tests**

In `science/tests/test_schema_first_load.py`, add: a gen-3-pinned fixture project whose hypothesis composes `hypothesis/2.0` (arming works for 3); and a gen-2 fixture that still composes `hypothesis/1.0` unchanged (regression). Also add a fast unit test that `migrate_hypothesis` still targets 2:
```python
def test_hypothesis_migrator_targets_generation_2():
    from science_tool import migrate_hypothesis
    assert migrate_hypothesis._TARGET_GENERATION == 2
```

- [ ] **Step 8: Run tests**

Run: `cd science/model && uv run --frozen pytest tests/test_entity_schema_generation.py tests/test_entity_schema_profile.py -q`
Run: `cd science && uv run --frozen pytest tests/test_schema_first_load.py -q && uv run --frozen pytest -k migrate_hypothesis -q`
Expected: PASS (gen-2 unchanged; gen-3 arms; migrator targets 2).

- [ ] **Step 9: Lint/type and commit**

Run: `cd science && uv run ruff check && uv run pyright`
```bash
git add science/model/src/science_model/entity_schema/profile.py science/src/science_tool/entity_profiles.py science/src/science_tool/migrate_hypothesis.py science/src/science_tool/graph/sources.py science/model/tests/test_entity_schema_generation.py science/tests/test_schema_first_load.py
git commit -m "feat(schema): replace the schema-version constant with a generation matrix; keep the hypothesis migrator targeting gen 2"
```

---

## Task 6: Dataset gen-3 capability validation hook

**Files:**
- Modify: `science/src/science_tool/graph/sources.py` (the per-entity validation path near `_validate_against_schema`, `:1278`)
- Test: `science/tests/test_schema_first_load.py`

**Interfaces:**
- Consumes: gen-3 arming (Task 5), `mixin-dataset-3.0.json` (Task 3).
- Produces: under a gen-3 project a dataset whose frontmatter violates dataset/3.0 raises `ValueError` at load; under gen 2 the dataset path is unchanged (dataset stays out of `PROJECT_MIXIN_NAMES`).

**Context:** `_validate_against_schema` (`sources.py:1278`) returns early unless `kind in PROJECT_MIXIN_NAMES` (`{hypothesis}`). Dataset is a commons kind and must NOT join that frozenset. Add a **separate** generation-gated dataset hook.

- [ ] **Step 1: Write the failing tests**

```python
# add to science/tests/test_schema_first_load.py — reuse its fixture-project builders
def test_gen3_dataset_bad_capability_shape_fails(tmp_path):
    # scaffold a project pinned entity_schema_version: 3 with a dataset whose
    # provided_capabilities is [{"assay": "x"}] (legacy shape, no data_product)
    root = _build_project(tmp_path, generation=3, entities=[_dataset_md(
        "dataset:demo", provided_capabilities=[{"assay": "x"}])])
    with pytest.raises(ValueError, match="dataset/3.0"):
        load_sources(root)


def test_gen2_dataset_capability_shape_untouched(tmp_path):
    root = _build_project(tmp_path, generation=2, entities=[_dataset_md(
        "dataset:demo", provided_capabilities=[{"assay": "x", "modality": "bulk-rna"}])])
    load_sources(root)  # no error under gen 2
```
(Use the file's existing project/dataset fixture helpers; the names above are illustrative — match the real ones in the file.)

- [ ] **Step 2: Run to verify it fails**

Run: `cd science && uv run --frozen pytest tests/test_schema_first_load.py -k gen3_dataset -q`
Expected: FAIL.

- [ ] **Step 3: Add the generation-gated dataset hook**

At the per-entity validation call site, add (and call it alongside `_validate_against_schema`):
```python
def _validate_dataset_gen3(kind, raw, path, project_schema, generation):
    if project_schema is None or generation != 3 or kind != "dataset":
        return
    authored = {k: v for k, v in raw.items() if k not in MarkdownAdapter.INJECTED_KEYS}
    try:
        project_schema.validator.validate_as(authored, project_schema.profile_for("dataset"))
    except EntityValidationError as exc:
        raise ValueError(
            f"{path}: dataset frontmatter does not satisfy dataset/3.0 "
            f"(project is pinned to entity_schema_version: 3)\n  {exc}"
        ) from exc
```
Thread `generation = config.get("entity_schema_version")` to the call site. Leave `_validate_against_schema` (hypothesis) unchanged.

- [ ] **Step 4: Run to verify it passes**

Run: `cd science && uv run --frozen pytest tests/test_schema_first_load.py -k "gen3_dataset or gen2_dataset" -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/graph/sources.py science/tests/test_schema_first_load.py
git commit -m "feat(schema): validate dataset gen-3 capability shape via a generation-gated hook"
```

---

## Task 7: Canonical capability shape parser + generation-aware `validate` check

**Files:**
- Create: `science/src/science_tool/datasets/capability_shape.py`
- Modify: `science/src/science_tool/validate/checks/dataset_capabilities.py:217-230,114-179`
- Test: `science/tests/test_capability_shape.py`
- Test: `science/tests/validate/test_checks_dataset_capabilities.py`

**Interfaces:**
- Produces: the **single** canonical parser reused by the check (this task) and the matcher (Task 8):
  - `gen3_shape_issue(value) -> str | None` — `"missing"` (None/`[]`), `"malformed"`, or `None` (valid). Valid entry = a `Mapping` whose **only** keys are `data_product` (matching `^data-product:[a-z0-9][a-z0-9-]*$`) and optional `qualifiers` (non-empty `str→str`); any extra top-level key is malformed.
  - `parse_gen3_capabilities(value) -> list[Capability]` (used by the matcher).
  - `legacy_map_shape_issue(value) -> str | None` — the existing `{str: str}` rule, extracted verbatim.
  - `capability_shape_issue(value, *, generation) -> str | None` — dispatches by generation.
- The check imports these; gen-3 WARN messages say `must be {data_product, qualifiers} objects` (never "string mappings").

- [ ] **Step 1: Write the failing tests**

```python
# science/tests/test_capability_shape.py
from science_tool.datasets.capability_shape import (
    gen3_shape_issue, legacy_map_shape_issue, capability_shape_issue,
)


def test_gen3_accepts_data_product_only():
    assert gen3_shape_issue([{"data_product": "data-product:x"}]) is None


def test_gen3_accepts_qualifiers():
    assert gen3_shape_issue([{"data_product": "data-product:x",
                              "qualifiers": {"cohort_design": "case-control"}}]) is None


def test_gen3_rejects_extra_top_level_key():
    assert gen3_shape_issue([{"data_product": "data-product:x", "assay": "y"}]) == "malformed"


def test_gen3_rejects_bad_data_product_pattern():
    assert gen3_shape_issue([{"data_product": "gene-expression"}]) == "malformed"


def test_gen3_rejects_empty_qualifier_value():
    assert gen3_shape_issue([{"data_product": "data-product:x", "qualifiers": {"a": ""}}]) == "malformed"


def test_gen3_missing_and_absent():
    assert gen3_shape_issue([]) == "missing"
    assert gen3_shape_issue(None) == "missing"


def test_legacy_accepts_string_map():
    assert legacy_map_shape_issue([{"assay": "x"}]) is None


def test_dispatch_by_generation():
    assert capability_shape_issue([{"assay": "x"}], generation=2) is None
    assert capability_shape_issue([{"assay": "x"}], generation=3) == "malformed"
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd science && uv run --frozen pytest tests/test_capability_shape.py -q`
Expected: FAIL (module missing).

- [ ] **Step 3: Write `capability_shape.py`**

```python
"""The single canonical capability shape parser — shared by validate + the matcher."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

_DP_PREFIX = "data-product:"
_ALLOWED_GEN3_KEYS = {"data_product", "qualifiers"}


@dataclass(frozen=True)
class Capability:
    data_product: str
    qualifiers: dict[str, str] = field(default_factory=dict)


def _valid_dp(value: object) -> bool:
    if not isinstance(value, str) or not value.startswith(_DP_PREFIX):
        return False
    slug = value[len(_DP_PREFIX):]
    return bool(slug) and slug[0].isalnum() and all(c.isalnum() or c == "-" for c in slug)


def _valid_qualifiers(value: object) -> bool:
    if not isinstance(value, Mapping):
        return False
    for key, raw in value.items():
        if not isinstance(key, str) or not key.strip():
            return False
        if not isinstance(raw, str) or not raw.strip():
            return False
    return True


def gen3_shape_issue(value: object) -> str | None:
    if value is None or value == []:
        return "missing"
    if not isinstance(value, list):
        return "malformed"
    for entry in value:
        if not isinstance(entry, Mapping) or not entry:
            return "malformed"
        if set(entry.keys()) - _ALLOWED_GEN3_KEYS:
            return "malformed"
        if not _valid_dp(entry.get("data_product")):
            return "malformed"
        if "qualifiers" in entry and not _valid_qualifiers(entry["qualifiers"]):
            return "malformed"
    return None


def parse_gen3_capabilities(value: object) -> list[Capability]:
    """Parse a validated-shape gen-3 capability list. Entries failing the shape are skipped."""
    if not isinstance(value, list):
        return []
    out: list[Capability] = []
    for entry in value:
        if not isinstance(entry, Mapping):
            continue
        if not _valid_dp(entry.get("data_product")):
            continue
        quals_raw = entry.get("qualifiers", {})
        quals = {k.strip(): v.strip() for k, v in quals_raw.items()} if _valid_qualifiers(quals_raw) else {}
        out.append(Capability(data_product=str(entry["data_product"]), qualifiers=quals))
    return out


def legacy_map_shape_issue(value: object) -> str | None:
    if value is None or value == []:
        return "missing"
    if not isinstance(value, list):
        return "malformed"
    for entry in value:
        if not isinstance(entry, Mapping) or not entry:
            return "malformed"
        for key, raw in entry.items():
            if not isinstance(key, str) or not key.strip():
                return "malformed"
            if not isinstance(raw, str) or not raw.strip():
                return "malformed"
    return None


def capability_shape_issue(value: object, *, generation: int = 2) -> str | None:
    return gen3_shape_issue(value) if generation >= 3 else legacy_map_shape_issue(value)
```

- [ ] **Step 4: Rewire the `validate` check**

In `dataset_capabilities.py`: delete the local `_capability_shape_issue`; import `capability_shape_issue` from `capability_shape`. Thread the project generation into `evaluate_dataset_capabilities` (read `entity_schema_version` from the project config via `validated_entity_schema_version`, default 2) and pass `generation=` to both call sites (dataset `:136`, q/h `:161`). Change the gen-3 malformed messages to `"provided_capabilities must be a list of {data_product, qualifiers} objects"` / `"required_capabilities must be a list of {data_product, qualifiers} objects"`, selecting by generation. Add to `test_checks_dataset_capabilities.py`: gen-3 legacy-map → malformed WARN with the new message; gen-2 legacy-map → no malformed WARN (regression).

- [ ] **Step 5: Run tests**

Run: `cd science && uv run --frozen pytest tests/test_capability_shape.py tests/validate/test_checks_dataset_capabilities.py -q`
Expected: PASS.

- [ ] **Step 6: Lint/type and commit**

Run: `cd science && uv run ruff check && uv run pyright`
```bash
git add science/src/science_tool/datasets/capability_shape.py science/src/science_tool/validate/checks/dataset_capabilities.py science/tests/test_capability_shape.py science/tests/validate/test_checks_dataset_capabilities.py
git commit -m "feat(datasets): add one canonical capability parser; make the validate check generation-aware"
```

---

## Task 8: Generation-aware matcher (gen-1/2 string-map preserved, gen-3 catalog descent)

**Files:**
- Modify: `science/src/science_tool/datasets/capabilities.py` (add gen-3 branch; keep gen-1/2 branch)
- Modify: `science/src/science_tool/dataset_prioritize.py:541`
- Test: `science/tests/test_capabilities.py`

**Interfaces:**
- Consumes: `DataProductCatalog` (Task 1), `parse_gen3_capabilities` (Task 7).
- Produces: `capability_fit(required, provided, *, generation: int, catalog: DataProductCatalog | None = None) -> CapabilityFit`.
  - **gen ≤ 2:** the existing string-map logic, byte-for-byte (subset match over `{str: str}` sets). Unchanged.
  - **gen 3:** parse both sides via `parse_gen3_capabilities`; a provided capability satisfies a required one when provided `data_product` **equals-or-descends** required `data_product` (`catalog.descends`) AND every required qualifier equals the provided (subset); `compatible` = OR across pairs. `catalog` is required for gen 3 (raise `ValueError` if `None`).
- Caller `dataset_prioritize.py:541` passes `generation=` (from the project pin) and `catalog=load_catalog()`.

- [ ] **Step 1: Write the failing tests (both branches + the e2e gen-2 path)**

```python
# science/tests/test_capabilities.py
import pytest
from science_model.data_products import build_catalog
from science_tool.datasets.capabilities import capability_fit


def _catalog():
    return build_catalog({"schema_version": "1", "terms": [
        {"id": "data-product:gene-expression", "label": "GE", "assay": "ge", "technology": "", "broader": []},
        {"id": "data-product:gene-expression-bulk-rna", "label": "b", "assay": "ge",
         "technology": "bulk-rna", "broader": ["data-product:gene-expression"]},
        {"id": "data-product:gene-expression-scrna", "label": "s", "assay": "ge",
         "technology": "scrna", "broader": ["data-product:gene-expression"]},
    ]})


def _c(dp, **q):
    return {"data_product": dp, "qualifiers": dict(q)}


# --- gen 3 ---
def test_gen3_exact_term_matches():
    assert capability_fit([_c("data-product:gene-expression-bulk-rna")],
                          [_c("data-product:gene-expression-bulk-rna")],
                          generation=3, catalog=_catalog()).compatible


def test_gen3_provided_descendant_satisfies_broader_requirement():
    assert capability_fit([_c("data-product:gene-expression")],
                          [_c("data-product:gene-expression-bulk-rna")],
                          generation=3, catalog=_catalog()).compatible


def test_gen3_ancestor_does_not_satisfy_specific():
    assert not capability_fit([_c("data-product:gene-expression-bulk-rna")],
                              [_c("data-product:gene-expression")],
                              generation=3, catalog=_catalog()).compatible


def test_gen3_siblings_do_not_match():
    assert not capability_fit([_c("data-product:gene-expression-bulk-rna")],
                              [_c("data-product:gene-expression-scrna")],
                              generation=3, catalog=_catalog()).compatible


def test_gen3_qualifier_subset_gates():
    req = [_c("data-product:gene-expression", analysis_role="mr_exposure")]
    cat = _catalog()
    assert not capability_fit(req, [_c("data-product:gene-expression-bulk-rna")],
                              generation=3, catalog=cat).compatible
    assert capability_fit(req, [_c("data-product:gene-expression-bulk-rna", analysis_role="mr_exposure")],
                          generation=3, catalog=cat).compatible


def test_gen3_requires_catalog():
    with pytest.raises(ValueError):
        capability_fit([_c("data-product:x")], [_c("data-product:x")], generation=3, catalog=None)


# --- gen 2 (unchanged string-map) ---
def test_gen2_string_map_subset_still_matches():
    fit = capability_fit([{"assay": "gene-expression"}],
                         [{"assay": "gene-expression", "modality": "microarray"}], generation=2)
    assert fit.compatible


def test_gen2_string_map_mismatch():
    fit = capability_fit([{"assay": "gene-expression", "modality": "single-cell"}],
                         [{"assay": "gene-expression", "modality": "microarray"}], generation=2)
    assert not fit.compatible
```

Add an end-to-end gen-2 coverage test that exercises the real caller (`dataset_prioritize`) against a small gen-2 fixture project and asserts a compatible dataset is still credited (mirror an existing coverage test in `science/tests/` — `rg "prioritize.*coverage" science/tests` — and pin `entity_schema_version: 2`).

- [ ] **Step 2: Run to verify it fails**

Run: `cd science && uv run --frozen pytest tests/test_capabilities.py -q`
Expected: FAIL.

- [ ] **Step 3: Add the gen-3 branch (preserve gen ≤2)**

Keep the current `CapabilitySet`, `capability_sets_from`, `compatible`, `_satisfies` as the gen-≤2 path. Rename the current `capability_fit` body into `_capability_fit_legacy(required, provided)`. Add:
```python
from science_model.data_products import DataProductCatalog
from science_tool.datasets.capability_shape import Capability, parse_gen3_capabilities


def capability_fit(required, provided, *, generation: int,
                   catalog: DataProductCatalog | None = None) -> CapabilityFit:
    if generation >= 3:
        if catalog is None:
            raise ValueError("gen-3 capability_fit requires a catalog")
        return _capability_fit_gen3(required, provided, catalog)
    return _capability_fit_legacy(required, provided)


def _capability_fit_gen3(required, provided, catalog):
    req = parse_gen3_capabilities(required)
    prov = parse_gen3_capabilities(provided)
    if not req:
        return CapabilityFit(False, "missing-required-capabilities", req, prov)
    if not prov:
        return CapabilityFit(False, "missing-provided-capabilities", req, prov)
    if any(_gen3_satisfies(r, p, catalog) for r in req for p in prov):
        return CapabilityFit(True, "compatible", req, prov)
    return CapabilityFit(False, "capability-mismatch", req, prov)


def _gen3_satisfies(required: Capability, provided: Capability, catalog: DataProductCatalog) -> bool:
    if not catalog.descends(provided.data_product, required.data_product):
        return False
    return all(provided.qualifiers.get(k) == v for k, v in required.qualifiers.items())
```
`CapabilityFit`'s `required`/`provided` fields become `list[object]` (they hold `CapabilitySet` in the legacy path and `Capability` in the gen-3 path) — adjust the type annotation accordingly, or keep them as the reason-carrying opaque lists they already are.

- [ ] **Step 4: Update the caller**

`dataset_prioritize.py:541` — read the project generation once (via `validated_entity_schema_version` on the project config, default 2), load the catalog once (`from science_model.data_products import load_catalog`; only when generation ≥ 3), and pass both:
```python
            fit = capability_fit(
                target_fm.get("required_capabilities") if isinstance(target_fm, dict) else None,
                dataset_fm.get("provided_capabilities"),
                generation=project_generation,
                catalog=catalog,   # None under gen ≤2
            )
```

- [ ] **Step 5: Run tests**

Run: `cd science && uv run --frozen pytest tests/test_capabilities.py -q`
Run: `cd science && uv run --frozen pytest -k "coverage or prioritize" -q`
Expected: PASS (both branches; gen-2 e2e still credits coverage).

- [ ] **Step 6: Lint/type and commit**

Run: `cd science && uv run ruff check && uv run pyright`
```bash
git add science/src/science_tool/datasets/capabilities.py science/src/science_tool/dataset_prioritize.py science/tests/test_capabilities.py
git commit -m "feat(datasets): add a gen-3 catalog-descent matcher branch; preserve the gen-2 string-map matcher"
```

---

## Task 9: Observed-shape enumeration (`dataset capability-pairs`)

**Files:**
- Create: `science/src/science_tool/datasets/capability_pairs.py`
- Modify: `science/src/science_tool/datasets/cli.py`
- Test: `science/tests/test_capability_pairs.py`

**Interfaces:**
- Produces: `enumerate_pairs(records: list[dict]) -> list[ObservedShape]` — `ObservedShape(raw: dict[str, str], count: int, example_ids: list[str])` over both `provided_capabilities` and `required_capabilities`. The CLI dumps JSON so a human can author the crosswalk (Task 12). **Inputs are explicit** (a corpus is passed in), so the command works for project layouts, the commons store, and a single record directory alike:
  - `dataset capability-pairs --project-root PATH` — enumerate a project's entities.
  - `dataset capability-pairs --commons-root PATH` — enumerate commons dataset records (`datasets/<slug>/entity.md`).
  - `dataset capability-pairs --file PATH` — enumerate a single entity file.
  These are mutually exclusive; exactly one is required. Read-only.

- [ ] **Step 1: Write the failing test**

```python
# science/tests/test_capability_pairs.py
from science_tool.datasets.capability_pairs import enumerate_pairs


def test_distinct_shapes_counted_with_examples():
    records = [
        {"id": "dataset:aa", "kind": "dataset",
         "provided_capabilities": [{"assay": "gene-expression", "modality": "microarray"}]},
        {"id": "dataset:bb", "kind": "dataset",
         "provided_capabilities": [{"assay": "gene-expression", "modality": "microarray"}]},
        {"id": "hypothesis:1", "kind": "hypothesis",
         "required_capabilities": [{"case_definition": "who-lc"}]},
    ]
    shapes = enumerate_pairs(records)
    micro = next(s for s in shapes if s.raw == {"assay": "gene-expression", "modality": "microarray"})
    assert micro.count == 2
    assert set(micro.example_ids) == {"dataset:aa", "dataset:bb"}
    assert any(s.raw == {"case_definition": "who-lc"} for s in shapes)
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd science && uv run --frozen pytest tests/test_capability_pairs.py -q`
Expected: FAIL (module missing).

- [ ] **Step 3: Implement `capability_pairs.py`**

```python
"""Enumerate distinct raw capability shapes across a corpus, to seed the crosswalk."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

_FIELDS = ("provided_capabilities", "required_capabilities")


@dataclass
class ObservedShape:
    raw: dict[str, str]
    count: int = 0
    example_ids: list[str] = field(default_factory=list)


def enumerate_pairs(records: list[dict]) -> list[ObservedShape]:
    index: dict[tuple[tuple[str, str], ...], ObservedShape] = {}
    for fm in records:
        ident = fm.get("id")
        if not isinstance(ident, str):
            continue
        for name in _FIELDS:
            value = fm.get(name)
            if not isinstance(value, list):
                continue
            for entry in value:
                if not isinstance(entry, Mapping):
                    continue
                raw = {str(k): str(v) for k, v in entry.items()}
                key = tuple(sorted(raw.items()))
                shape = index.setdefault(key, ObservedShape(raw=raw))
                shape.count += 1
                if ident not in shape.example_ids and len(shape.example_ids) < 5:
                    shape.example_ids.append(ident)
    return sorted(index.values(), key=lambda s: (-s.count, tuple(sorted(s.raw.items()))))
```
Wire `dataset capability-pairs` in `cli.py` with the three mutually-exclusive inputs. For `--project-root`, reuse the entity loader the coverage command uses. For `--commons-root`, glob `datasets/*/entity.md` and parse frontmatter via `split_frontmatter`. For `--file`, parse one file. Emit `json.dumps([{ "raw":…, "count":…, "example_ids":… }, …], indent=2)` via the existing `emit` helper.

- [ ] **Step 4: Run to verify it passes**

Run: `cd science && uv run --frozen pytest tests/test_capability_pairs.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/datasets/capability_pairs.py science/src/science_tool/datasets/cli.py science/tests/test_capability_pairs.py
git commit -m "feat(datasets): enumerate observed capability shapes (project/commons/file inputs)"
```

---

## Task 10: Crosswalk loader — strict contract + adjudicated dispositions

**Files:**
- Create: `science/src/science_tool/datasets/capability_crosswalk.py`
- Test: `science/tests/test_capability_crosswalk.py`

**Interfaces:**
- Produces: `Crosswalk.load(path: Path, *, catalog_ids: set[str]) -> Crosswalk`; `Crosswalk.rewrite(entry: Mapping) -> RewriteResult`. A `RewriteResult` is one of: `Mapped(capability: dict)` (`{data_product, qualifiers}`), `Dropped(rationale: str)` (out-of-scope, delete the entry), or `Refused(rationale: str)` (author must act first — migration aborts). An unmapped raw shape raises `CrosswalkError`.
- **Strict contract (all enforced at load, each with a test):** `schema_version == "1"`; `mappings` is a non-empty list; each mapping is a **closed** object (unknown keys rejected); `match` is a non-empty map; **exactly one** of `data_product` (a `str` present in `catalog_ids`) or `out_of_scope` (an object); `qualifiers` optional and non-empty `str→str`; a mapping's `match` key is **unique** (duplicate → error); `out_of_scope` carries `disposition ∈ {drop, refuse}` + non-empty `rationale`, and **no** `data_product`/`qualifiers`. `out_of_scope` must be a real object (not a bare bool) — no `bool("false")` coercion.

- [ ] **Step 1: Write the failing tests**

```python
# science/tests/test_capability_crosswalk.py
import pytest
from science_tool.datasets.capability_crosswalk import (
    Crosswalk, CrosswalkError, Mapped, Dropped, Refused,
)

CAT = {"data-product:gene-expression-microarray"}


def _write(tmp_path, body):
    p = tmp_path / "cw.yaml"
    p.write_text("schema_version: \"1\"\nmappings:\n" + body)
    return p


_GOOD = (
    "  - match: {assay: gene-expression, modality: microarray}\n"
    "    data_product: data-product:gene-expression-microarray\n"
    "    qualifiers: {}\n"
    "  - match: {case_definition: who-lc}\n"
    "    out_of_scope: {disposition: drop, rationale: epidemiological facet}\n"
)


def test_maps_pair(tmp_path):
    cw = Crosswalk.load(_write(tmp_path, _GOOD), catalog_ids=CAT)
    r = cw.rewrite({"assay": "gene-expression", "modality": "microarray"})
    assert isinstance(r, Mapped) and r.capability == {
        "data_product": "data-product:gene-expression-microarray", "qualifiers": {}}


def test_out_of_scope_drop(tmp_path):
    cw = Crosswalk.load(_write(tmp_path, _GOOD), catalog_ids=CAT)
    assert isinstance(cw.rewrite({"case_definition": "who-lc"}), Dropped)


def test_refuse_disposition(tmp_path):
    body = ("  - match: {trait: x}\n"
            "    out_of_scope: {disposition: refuse, rationale: author must remodel}\n")
    cw = Crosswalk.load(_write(tmp_path, body), catalog_ids=CAT)
    assert isinstance(cw.rewrite({"trait": "x"}), Refused)


def test_unknown_shape_fails_early(tmp_path):
    cw = Crosswalk.load(_write(tmp_path, _GOOD), catalog_ids=CAT)
    with pytest.raises(CrosswalkError):
        cw.rewrite({"assay": "made-up"})


def test_rejects_empty_mappings(tmp_path):
    p = tmp_path / "cw.yaml"
    p.write_text("schema_version: \"1\"\nmappings: []\n")
    with pytest.raises(CrosswalkError):
        Crosswalk.load(p, catalog_ids=CAT)


def test_rejects_duplicate_match(tmp_path):
    body = _GOOD + ("  - match: {assay: gene-expression, modality: microarray}\n"
                    "    data_product: data-product:gene-expression-microarray\n")
    with pytest.raises(CrosswalkError):
        Crosswalk.load(_write(tmp_path, body), catalog_ids=CAT)


def test_rejects_both_data_product_and_out_of_scope(tmp_path):
    body = ("  - match: {a: b}\n"
            "    data_product: data-product:gene-expression-microarray\n"
            "    out_of_scope: {disposition: drop, rationale: x}\n")
    with pytest.raises(CrosswalkError):
        Crosswalk.load(_write(tmp_path, body), catalog_ids=CAT)


def test_rejects_unknown_mapping_key(tmp_path):
    body = ("  - match: {a: b}\n    data_product: data-product:gene-expression-microarray\n"
            "    notes: nope\n")
    with pytest.raises(CrosswalkError):
        Crosswalk.load(_write(tmp_path, body), catalog_ids=CAT)


def test_rejects_data_product_absent_from_catalog(tmp_path):
    with pytest.raises(CrosswalkError):
        Crosswalk.load(_write(tmp_path, _GOOD), catalog_ids=set())


def test_rejects_bad_disposition(tmp_path):
    body = "  - match: {a: b}\n    out_of_scope: {disposition: nuke, rationale: x}\n"
    with pytest.raises(CrosswalkError):
        Crosswalk.load(_write(tmp_path, body), catalog_ids=CAT)
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd science && uv run --frozen pytest tests/test_capability_crosswalk.py -q`
Expected: FAIL (module missing).

- [ ] **Step 3: Implement `capability_crosswalk.py`**

```python
"""Load the value->term crosswalk (strict contract, adjudicated dispositions)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

import yaml

_DISPOSITIONS = {"drop", "refuse"}
_MAPPING_KEYS = {"match", "data_product", "qualifiers", "out_of_scope"}


class CrosswalkError(ValueError):
    """The crosswalk is invalid, or a raw capability shape is unmapped."""


@dataclass(frozen=True)
class Mapped:
    capability: dict


@dataclass(frozen=True)
class Dropped:
    rationale: str


@dataclass(frozen=True)
class Refused:
    rationale: str


RewriteResult = Mapped | Dropped | Refused


@dataclass(frozen=True)
class _Entry:
    data_product: str | None
    qualifiers: dict[str, str]
    disposition: str | None
    rationale: str


@dataclass
class Crosswalk:
    _by_match: dict[tuple[tuple[str, str], ...], _Entry]

    @staticmethod
    def _key(raw: Mapping) -> tuple[tuple[str, str], ...]:
        return tuple(sorted((str(k), str(v)) for k, v in raw.items()))

    @classmethod
    def load(cls, path: Path, *, catalog_ids: set[str]) -> "Crosswalk":
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        if data.get("schema_version") != "1":
            raise CrosswalkError(f"schema_version must be '1', got {data.get('schema_version')!r}")
        mappings = data.get("mappings")
        if not isinstance(mappings, list) or not mappings:
            raise CrosswalkError("mappings must be a non-empty list")
        by_match: dict[tuple[tuple[str, str], ...], _Entry] = {}
        for m in mappings:
            if not isinstance(m, Mapping) or set(m) - _MAPPING_KEYS:
                raise CrosswalkError(f"mapping has unknown or missing keys: {m!r}")
            match = m.get("match")
            if not isinstance(match, Mapping) or not match:
                raise CrosswalkError(f"mapping needs a non-empty match: {m!r}")
            key = cls._key(match)
            if key in by_match:
                raise CrosswalkError(f"duplicate match {dict(match)!r}")
            has_dp = "data_product" in m
            has_oos = "out_of_scope" in m
            if has_dp == has_oos:
                raise CrosswalkError(f"mapping {dict(match)!r} needs exactly one of data_product / out_of_scope")
            if has_dp:
                dp = m["data_product"]
                if not isinstance(dp, str) or dp not in catalog_ids:
                    raise CrosswalkError(f"mapping {dict(match)!r} data_product {dp!r} absent from catalog")
                quals = m.get("qualifiers", {})
                if not _valid_quals(quals):
                    raise CrosswalkError(f"mapping {dict(match)!r} qualifiers must be non-empty str->str")
                by_match[key] = _Entry(dp, dict(quals), None, "")
            else:
                oos = m["out_of_scope"]
                if not isinstance(oos, Mapping) or set(oos) - {"disposition", "rationale"}:
                    raise CrosswalkError(f"mapping {dict(match)!r} out_of_scope must be {{disposition, rationale}}")
                disp, rat = oos.get("disposition"), oos.get("rationale")
                if disp not in _DISPOSITIONS or not isinstance(rat, str) or not rat.strip():
                    raise CrosswalkError(f"mapping {dict(match)!r} needs disposition in {_DISPOSITIONS} + rationale")
                by_match[key] = _Entry(None, {}, disp, rat.strip())
        return cls(_by_match=by_match)

    def rewrite(self, entry: Mapping) -> RewriteResult:
        found = self._by_match.get(self._key(entry))
        if found is None:
            raise CrosswalkError(f"no crosswalk entry for raw capability {dict(entry)!r}")
        if found.disposition == "drop":
            return Dropped(found.rationale)
        if found.disposition == "refuse":
            return Refused(found.rationale)
        return Mapped({"data_product": found.data_product, "qualifiers": dict(found.qualifiers)})


def _valid_quals(value: object) -> bool:
    if not isinstance(value, Mapping):
        return False
    return all(isinstance(k, str) and k.strip() and isinstance(v, str) and v.strip()
               for k, v in value.items())
```

- [ ] **Step 4: Run to verify it passes**

Run: `cd science && uv run --frozen pytest tests/test_capability_crosswalk.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/datasets/capability_crosswalk.py science/tests/test_capability_crosswalk.py
git commit -m "feat(datasets): add strict crosswalk loader with adjudicated dispositions"
```

---

## Task 11: Transactional capability migrator (`dataset migrate-capabilities`)

**Files:**
- Create: `science/src/science_tool/datasets/capability_migration.py`
- Modify: `science/src/science_tool/datasets/cli.py`
- Test: `science/tests/test_capability_migration.py`

**Interfaces:**
- Consumes: `Crosswalk` (Task 10), `load_catalog` (Task 1), the gen-3 dataset/hypothesis schemas (Tasks 3, 4), and the frontmatter helpers `split_frontmatter`/`render_frontmatter`/`atomic_write_text` from `science_model.frontmatter`.
- Produces: a **transactional** migrator mirroring `migrate_hypothesis.py` (`plan → journal → write → set pin LAST → confirm → clear journal`), plus `--resume`. Command: `dataset migrate-capabilities --project-root PATH --crosswalk PATH [--apply] [--resume]`. `--crosswalk` is **required** (there is no packaged default in this plan; a packaged default may be added post-Task-12). Semantics:
  - **Plan** every entity: rewrite each `provided_capabilities`/`required_capabilities` entry via the crosswalk. `Mapped` → replace; `Dropped` → remove the entry (recorded with rationale); `Refused` → collect. A raw shape unmapped by the crosswalk → collect. **If any `Refused` or unmapped shape exists, abort — write nothing.** Validate every planned post-image against the composed dataset/3.0 or hypothesis/2.0 profile before writing.
  - **Dry-run (default):** print a per-entity report — for each changed entity, the field, and each entry's disposition (`mapped`→term, `dropped`→rationale). This report is the Task-12 review artifact.
  - **`--apply`:** journal all `(path, before_sha256, after)` post-images (`.science/capability-migration.journal`), write them, then `_set_entity_schema_version(project_root, 3)` **last**, confirm via `validated_entity_schema_version`, then clear the journal. A pre-existing journal blocks re-planning (finish with `--resume`).
  - **`--resume`:** the three-state resume from the journal (post-image → skip; pre-image → write; neither → refuse), then pin+confirm+clear — identical discipline to `migrate_hypothesis.resume`.

- [ ] **Step 1: Write the failing tests**

```python
# science/tests/test_capability_migration.py
import hashlib, json
from pathlib import Path
import pytest
from science_tool.datasets.capability_migration import migrate, resume, MigrationRefused


def _project(tmp_path, datasets, *, generation=2):
    root = tmp_path / "proj"
    (root / "entities" / "datasets").mkdir(parents=True)
    (root / "science.yaml").write_text(f"name: p\nentity_schema_version: {generation}\n")
    for name, caps in datasets:
        (root / "entities" / "datasets" / f"{name}.md").write_text(
            f"---\nid: dataset:{name}\nkind: dataset\nprovided_capabilities:\n"
            f"- {{{caps}}}\n---\nbody\n")
    return root


def _crosswalk(tmp_path):
    p = tmp_path / "cw.yaml"
    p.write_text(
        "schema_version: \"1\"\nmappings:\n"
        "  - match: {assay: gene-expression, modality: microarray}\n"
        "    data_product: data-product:gene-expression-microarray\n"
        "  - match: {case_definition: who-lc}\n"
        "    out_of_scope: {disposition: drop, rationale: epi facet}\n")
    return p


def test_dry_run_writes_nothing(tmp_path):
    root = _project(tmp_path, [("aa", "assay: gene-expression, modality: microarray")])
    before = (root / "entities/datasets/aa.md").read_text()
    migrate(root, crosswalk_path=_crosswalk(tmp_path), apply=False)  # catalog patched in test to include the term
    assert (root / "entities/datasets/aa.md").read_text() == before
    assert (root / "science.yaml").read_text().strip().endswith("entity_schema_version: 2")


def test_apply_rewrites_and_pins_last(tmp_path):
    root = _project(tmp_path, [("aa", "assay: gene-expression, modality: microarray")])
    migrate(root, crosswalk_path=_crosswalk(tmp_path), apply=True)
    text = (root / "entities/datasets/aa.md").read_text()
    assert "data-product:gene-expression-microarray" in text
    assert "entity_schema_version: 3" in (root / "science.yaml").read_text()
    assert not (root / ".science/capability-migration.journal").exists()


def test_unmapped_shape_aborts_writing_nothing(tmp_path):
    root = _project(tmp_path, [("aa", "assay: made-up")])
    before = (root / "entities/datasets/aa.md").read_text()
    with pytest.raises(MigrationRefused):
        migrate(root, crosswalk_path=_crosswalk(tmp_path), apply=True)
    assert (root / "entities/datasets/aa.md").read_text() == before
    assert "entity_schema_version: 2" in (root / "science.yaml").read_text()
```
(The test patches `load_catalog` — or points a test crosswalk at a catalog fixture — so the term id `data-product:gene-expression-microarray` resolves. Use the same fixture approach the repo already uses for catalog-dependent tests.)

- [ ] **Step 2: Run to verify it fails**

Run: `cd science && uv run --frozen pytest tests/test_capability_migration.py -q`
Expected: FAIL (module missing).

- [ ] **Step 3: Implement `capability_migration.py`**

Mirror `migrate_hypothesis.py` structure: `JOURNAL_PATH = Path(".science/capability-migration.journal")`; `MigrationRefused`; `@dataclass PlannedWrite(path, text)`; `_journal_write`, `_set_entity_schema_version` (reuse the hypothesis migrator's `_is_top_level_pin` helper — import it), `_commit` (write all → set pin to `3` last → confirm via `validated_entity_schema_version` → clear journal), `resume`, and `migrate`:
```python
_TARGET_GENERATION = 3


def migrate(project_root: Path, *, crosswalk_path: Path, apply: bool = False) -> list[Path]:
    project_root = project_root.resolve()
    if (project_root / JOURNAL_PATH).is_file():
        raise MigrationRefused(f"{JOURNAL_PATH} exists: finish the interrupted pass with --resume")
    catalog = load_catalog()
    crosswalk = Crosswalk.load(crosswalk_path, catalog_ids=set(catalog.by_id))
    project_schema = load_project_schema(project_root, generation=_TARGET_GENERATION)
    planned, refusals, report = _plan(project_root, crosswalk, project_schema)
    if refusals:
        raise MigrationRefused("migration refused:\n" + "\n".join(f"  {r}" for r in refusals))
    if not apply:
        _print_report(report)
        return [p.path for p in planned]
    return _commit(project_root, planned)
```
`_plan` walks every entity file, rewrites the two capability fields entry-by-entry via `crosswalk.rewrite`, drops `Dropped` entries (append to `report`), collects `Refused`/`CrosswalkError` into `refusals`, renders the post-image with `render_frontmatter`, and validates it via `project_schema.validator.validate_as(authored, project_schema.profile_for(kind))`. Preserve field order and body. Never write in `_plan`.

Wire `dataset migrate-capabilities` in `cli.py` with `--project-root`, `--crosswalk` (required), `--apply`, `--resume`; on `--resume` call `resume(project_root)`.

- [ ] **Step 4: Run to verify it passes**

Run: `cd science && uv run --frozen pytest tests/test_capability_migration.py -q`
Expected: PASS.

- [ ] **Step 5: Lint/type and commit**

Run: `cd science && uv run ruff check && uv run pyright`
```bash
git add science/src/science_tool/datasets/capability_migration.py science/src/science_tool/datasets/cli.py science/tests/test_capability_migration.py
git commit -m "feat(datasets): transactional capability migrator (journal, pin-last, resume)"
```

---

## Task 12: Author the catalog + crosswalk — HUMAN REVIEW CHECKPOINT

> **Data-authoring, not mechanical. Do NOT auto-generate and commit. Stop for human review before Tasks 13/14 consume it.**

**Files:**
- Modify: `science/model/src/science_model/data_products/catalog.yaml`
- Create: `science/src/science_tool/datasets/capability_crosswalk.yaml`

**Process:**

- [ ] **Step 1: Enumerate** — run `dataset capability-pairs` (Task 9) against each project (`--project-root ~/d/r/mm30`, `~/d/r/cbioportal`, `~/d/health/processes/post-acute-infection`) and `--commons-root ~/d/science-commons`. Collect the distinct raw shapes + counts.
- [ ] **Step 2: Draft the catalog** — for every molecular `(assay, modality)` pair, mint a `data-product:<slug>` term (`assay`, `technology`=modality, `broader`→ the assay-family term). Seed families from `~/d/r/mm30/doc/plans/capabilities-vocab.yaml` (17 families); add terms for observed pairs the seed omits (metabolomics/imaging, histone-modification/cut-and-run, cbioportal analysis-product modalities). Handle **assay-only** entries (mm30 `{assay: gene-expression}`) → map to the family term.
- [ ] **Step 3: Draft the crosswalk** — one `match:` per distinct raw shape. Molecular shapes → `data_product` (+ `qualifiers` for the non-identity facets: `trigger`, `cohort_design`, `case_definition`, `stratification`, `analysis_role`, `trait`, `outcome`, `sample_type`). Non-molecular / facet-only shapes (health `{case_definition: who-lc}`, `{stratification: frailty}`, MR-only requirements) → `out_of_scope` with an adjudicated `disposition` (`drop` = non-molecular, safe to remove; `refuse` = the author must re-model first) and a `rationale`.
- [ ] **Step 4: Present for review** — surface (a) the catalog, (b) the crosswalk, (c) the pair inventory, and (d) the dry-run reports from `dataset migrate-capabilities --project-root <each> --crosswalk <draft>` (no `--apply`), which list every entry's disposition. Flag every `out_of_scope`/`refuse` decision and every granularity split/merge. **Use `ohai` to notify.** Do not proceed until approved.
- [ ] **Step 5: On approval, commit**

```bash
git add science/model/src/science_model/data_products/catalog.yaml science/src/science_tool/datasets/capability_crosswalk.yaml
git commit -m "feat: author data-product catalog and value->term crosswalk"
```

---

## Task 13: Migrate commons dataset records to dataset/3.0 — HUMAN-GATED

> Touches `~/d/science-commons` (shared store). Get explicit approval before writing.

**Process:**

- [ ] **Step 1:** Bump every commons dataset record's `schema_profile` from `science-entity-base/1.0+dataset/2.0` to `+dataset/3.0` (37 plain + 10 `+bio.*` records — the bio records bump only the dataset component). Confirm the count is 47.
- [ ] **Step 2:** Reshape the one record with capabilities — `~/d/science-commons/datasets/hmcl-drug-screen/entity.md`, `[{assay: drug-sensitivity, modality: cell-line-viability}]` → `[{data_product: <term>, qualifiers: {}}]` per the crosswalk.
- [ ] **Step 3:** Validate: `cd science && SCIENCE_COMMONS_ROOT=~/d/science-commons uv run --frozen science commons validate`. Expected: all 47 records valid on dataset/3.0.
- [ ] **Step 4:** Commit in the commons repo (do NOT push). Use `ohai` to report the diff summary.

---

## Task 14: Migrate enrolled projects to generation 3 — HUMAN-GATED, one at a time

> Touches three external research repos (~470 entities). The pin flip is **inside** the transactional migrate (Task 11) — there is no separate pin step. Run one project at a time; validate after each; get approval before the next.

**Process (repeat per project: mm30, cbioportal, health):**

- [ ] **Step 1:** Dry-run: `cd science && uv run --frozen science dataset migrate-capabilities --project-root <path> --crosswalk src/science_tool/datasets/capability_crosswalk.yaml`. Review the per-entity disposition report; confirm zero unmapped shapes and zero `refuse` (either means the crosswalk is incomplete — return to Task 12; do not force).
- [ ] **Step 2:** Apply: add `--apply`. This rewrites the capability blocks and flips `entity_schema_version` to `3` atomically (journal → write → pin-last → confirm → clear). If interrupted, re-run with `--resume`.
- [ ] **Step 3:** Validate: `cd science && uv run --frozen science validate --project-root <path>`. Expected: dataset gen-3 hook (Task 6) + hypothesis/2.0 pass; no capability-shape WARN regresses. Confirm health's facet-only requirements were `drop`-dispositioned as intended (no molecular coverage lost).
- [ ] **Step 4:** Commit in that project's repo (do NOT push; mm30/health are Dropbox repos — never push). Use `ohai` to report per-project completion.

---

## Self-Review

**Spec coverage** (design → task): term catalog + DAG → Task 1; generation matrix / no input-shape dispatch → Tasks 2, 5; dataset/3.0 + hypothesis/2.0 (copy-then-bump, prior retained) → Tasks 3, 4; dataset gen-3 hook (not `PROJECT_MIXIN_NAMES`) → Task 6; one canonical generation-aware parser + validator-level question/plan enforcement → Task 7; matcher term-descent + qualifier-subset + OR, **gen-2 preserved** → Task 8; crosswalk + enumeration + transactional migration → Tasks 9, 10, 11; enrolled-project + 47-commons migration → Tasks 12–14.

**Review findings addressed:** generation-aware matcher with a preserved gen-2 branch and the migrate_hypothesis constant fix (F1); transactional journal/pin-last/resume migration (F2); `--crosswalk` interface + strict loader contract (F3); adjudicated `drop`/`refuse` dispositions, never a silent delete (F4); one canonical shape parser shared by check + matcher, extra-key-strict, gen-3 messages corrected (F5); closed catalog models + `build_catalog`/`CatalogError` boundary + read-within-lifetime loader (F6); real test/CLI paths, `dataset:demo` ids, explicit enumeration inputs (F7).

**Placeholder scan:** no `<file>`/`...`/"find the command" remain — every task names concrete paths (`test_schema_first_load.py`, `validate/test_checks_dataset_capabilities.py`, `datasets/cli.py`) and concrete commands (`science validate --project-root`, `SCIENCE_COMMONS_ROOT=… science commons validate`). Tasks 12–14 are intentionally process-only (human checkpoints) with commands + validation gates.

**Type consistency:** `Capability{data_product, qualifiers}` (Task 7) is the matcher's parse target (Task 8) and matches the schema shape (Tasks 3, 4). `capability_fit(required, provided, *, generation, catalog)` (Task 8) is called with both at `dataset_prioritize.py:541`. `capability_shape_issue(value, *, generation)` (Task 7) backs the check. `Crosswalk.rewrite → Mapped|Dropped|Refused` (Task 10) is consumed by `_plan` (Task 11). `_set_entity_schema_version(root, 3)` (Task 11) and `_TARGET_GENERATION = 2` (Task 5, migrate_hypothesis) are distinct targets.

**Deferred to Plan 2:** `skills_loaded` absorption, packaged skill inventory, `covers:` authoring, overlay, two-set coverage, the enrollment declaration shape (its `entity_schema_version: 3` cross-field rule), `science skills coverage`. Task 14 flips the pin so Plan 2 can enroll on top.

## Execution Handoff

Tasks 1–11 are subagent-executable TDD in a toolkit worktree; Tasks 12–14 are human-review checkpoints touching external repos. The executing controller must stop and get approval at each of 12, 13, 14. On completion and merge, Plan 2 is written against the real merged interfaces.

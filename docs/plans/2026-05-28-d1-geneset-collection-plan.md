# D1 Gene-Set Collection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the D1 `bio.geneset` collection profile, row-contract parser, and validate check for flat gene-set/pathway/signature collections.

**Architecture:** D1 is collection-only. A gene-set collection remains a `dataset` with `schema_profile: science-entity-base/1.0+dataset/1.0+bio.geneset/1.0`; each set remains a row addressed by `set_key`. The implementation adds a JSON Schema extension, a pure `science_tool.commons.geneset` row parser, and a tolerant `science validate` check that reads raw dataset frontmatter plus the declared members resource.

**Tech Stack:** Python 3.12, Pydantic model layer via `science_model`, JSON Schema profiles, CSV/Frictionless datapackage resources, pytest.

---

## Scope

This plan implements **D1 only** from `docs/plans/2026-05-26-bio-geneset-type-design.md`:

- `bio.geneset` collection extension.
- `member_key_column: set_key`.
- `members_resource` naming the Frictionless datapackage resource that contains collection member rows.
- `identifier_space` declaration over the existing C2/C3 identity registries.
- row contract for the members resource: unique `set_key`, non-empty member identifiers, optional per-set provenance columns.
- validate check `genesets` at order 34.

`members_resource` is a Frictionless resource **name**, not a file path. `set_size_summary.median` uses
Python's `statistics.median` convention over per-set member counts; the validate check compares it with a
small numeric tolerance so `x.5` even-count medians do not false-fail due to YAML float representation.

This plan deliberately does **not** implement `bio.geneset.member`, promotion commands, `member_of` changes, or virtual member payload resolution. Those remain D2.

---

## File Map

- Create `science/model/src/science_model/schemas/extension-bio-geneset-1.0.json`
  JSON Schema extension for collection-level fields.
- Create `science/model/tests/test_bio_extension_geneset.py`
  Schema loader and validation tests.
- Create `science/src/science_tool/commons/geneset.py`
  Pure CSV-row parser and constants for D1 row contract.
- Create `science/tests/test_commons_geneset.py`
  Pure parser tests.
- Create `science/src/science_tool/validate/checks/genesets.py`
  Tolerant validate check over raw dataset frontmatter and the members resource.
- Create `science/tests/validate/test_checks_genesets.py`
  Pure and integration tests for the validate check.
- Modify `science/src/science_tool/validate/checks/__init__.py`
  Register `genesets` after `variant_identity`.
- Modify validate parity/snapshot test module lists:
  - `science/tests/validate/test_formatter_snapshots.py`
  - `science/tests/validate/test_parity_corpus.py`
  - `science/tests/validate/test_parity_canonical_body.py`
  - `science/tests/validate/test_runner.py`
- Modify docs:
  - `docs/plans/2026-05-26-bio-geneset-type-design.md`
  - `docs/plans/2026-05-26-bio-data-architecture-umbrella-design.md`

---

### Task 1: Add The `bio.geneset` JSON Schema Extension

**Files:**
- Create: `science/model/src/science_model/schemas/extension-bio-geneset-1.0.json`
- Create: `science/model/tests/test_bio_extension_geneset.py`

- [ ] **Step 1: Write failing schema tests**

Create `science/model/tests/test_bio_extension_geneset.py`:

```python
from __future__ import annotations

import pytest

from science_model.entity_schema.loader import SchemaLoader
from science_model.entity_schema.profile import ProfileComponent
from science_model.entity_schema.validator import EntityValidationError, EntityValidator


@pytest.fixture
def base_geneset_entity() -> dict:
    return {
        "schema_profile": "science-entity-base/1.0+dataset/1.0+bio.geneset/1.0",
        "id": "dataset:reactome-v89",
        "type": "dataset",
        "title": "Reactome v89 gene-set collection",
        "version": "1.0.0",
        "created": "2026-05-28",
        "updated": "2026-05-28",
        "datapackage": "datapackage.yaml",
        "origin": "external",
        "tier": "use-now",
        "source_class": "reference",
        "access": {"level": "public", "verified": True},
        "member_key_column": "set_key",
        "members_resource": "sets",
        "n_sets": 2,
        "set_size_summary": {"min": 3, "median": 4, "max": 5},
        "identifier_space": {
            "tier": "gene",
            "namespace": "hgnc_id",
            "registry": "dataset:gene-crosswalk-hgnc",
            "resolution_status": "resolved",
        },
    }


def test_loader_resolves_geneset_schema() -> None:
    schema = SchemaLoader().load(ProfileComponent(name="bio.geneset", version="1.0"))
    assert schema["$id"].endswith("extension-bio-geneset-1.0.json")


def test_minimal_valid_geneset_collection_passes(base_geneset_entity: dict) -> None:
    EntityValidator().validate(base_geneset_entity)


def test_member_key_column_must_be_set_key(base_geneset_entity: dict) -> None:
    base_geneset_entity["member_key_column"] = "pathway_id"
    with pytest.raises(EntityValidationError):
        EntityValidator().validate(base_geneset_entity)


def test_identifier_space_requires_supported_tier_shape(base_geneset_entity: dict) -> None:
    del base_geneset_entity["identifier_space"]["namespace"]
    with pytest.raises(EntityValidationError, match="namespace"):
        EntityValidator().validate(base_geneset_entity)
```

- [ ] **Step 2: Run tests to verify failure**

Run from `~/d/science/science`:

```bash
rtk uv run pytest model/tests/test_bio_extension_geneset.py -q
```

Expected: FAIL because `extension-bio-geneset-1.0.json` does not exist.

- [ ] **Step 3: Add the schema**

Create `science/model/src/science_model/schemas/extension-bio-geneset-1.0.json`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://schemas.science/extension-bio-geneset-1.0.json",
  "title": "science entity bio.geneset extension",
  "type": "object",
  "required": [
    "member_key_column",
    "members_resource",
    "n_sets",
    "set_size_summary",
    "identifier_space"
  ],
  "properties": {
    "member_key_column": {"const": "set_key"},
    "members_resource": {"type": "string", "minLength": 1},
    "n_sets": {"type": "integer", "minimum": 1},
    "set_size_summary": {
      "type": "object",
      "required": ["min", "median", "max"],
      "properties": {
        "min": {"type": "integer", "minimum": 0},
        "median": {"type": "number", "minimum": 0},
        "max": {"type": "integer", "minimum": 0}
      },
      "additionalProperties": false
    },
    "identifier_space": {
      "type": "object",
      "required": ["tier", "namespace"],
      "properties": {
        "tier": {"enum": ["gene", "protein"]},
        "namespace": {"type": "string", "minLength": 1},
        "registry": {"type": "string", "pattern": "^dataset:"},
        "resolution_status": {"enum": ["resolved", "declared_unresolved"]}
      },
      "additionalProperties": false
    }
  }
}
```

Cross-field consistency for `set_size_summary` is tested in Task 3, because the project's JSON Schema
validator does not support Ajv-style `$data` comparisons.

- [ ] **Step 4: Run schema tests**

Run:

```bash
rtk uv run pytest model/tests/test_bio_extension_geneset.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
rtk git add science/model/src/science_model/schemas/extension-bio-geneset-1.0.json science/model/tests/test_bio_extension_geneset.py
rtk git commit -m "schema: add bio geneset collection extension"
```

---

### Task 2: Add Pure Gene-Set Row Parser

**Files:**
- Create: `science/src/science_tool/commons/geneset.py`
- Create: `science/tests/test_commons_geneset.py`

- [ ] **Step 1: Write failing parser tests**

Create `science/tests/test_commons_geneset.py`:

```python
from __future__ import annotations

import pytest

from science_tool.commons.geneset import (
    GENESET_MEMBER_KEY_COLUMN,
    GenesetCollectionError,
    parse_geneset_rows,
)


def test_member_key_column_constant() -> None:
    assert GENESET_MEMBER_KEY_COLUMN == "set_key"


def test_parse_valid_rows() -> None:
    rows = parse_geneset_rows(
        [
            {
                "set_key": "R-HSA-1",
                "name": "Cell cycle",
                "member_ids": "HGNC:1;HGNC:2",
                "source_class": "reference",
                "dataset_usage": '[{"ref":"dataset:study-a","role":"set_definition_source","overlap":"full"}]',
                "source_pmids": "12345;PMID:67890",
            }
        ]
    )
    assert len(rows) == 1
    assert rows[0].set_key == "R-HSA-1"
    assert rows[0].member_ids == ("HGNC:1", "HGNC:2")
    assert rows[0].n_members == 2
    assert rows[0].dataset_usage[0]["role"] == "set_definition_source"
    assert rows[0].source_pmids == ("12345", "PMID:67890")


def test_duplicate_set_key_errors() -> None:
    with pytest.raises(GenesetCollectionError, match="duplicate set_key"):
        parse_geneset_rows(
            [
                {"set_key": "A", "name": "one", "member_ids": "HGNC:1"},
                {"set_key": "A", "name": "two", "member_ids": "HGNC:2"},
            ]
        )


def test_blank_member_ids_errors() -> None:
    with pytest.raises(GenesetCollectionError, match="member_ids"):
        parse_geneset_rows([{"set_key": "A", "name": "one", "member_ids": ""}])


def test_dataset_usage_must_be_json_list() -> None:
    with pytest.raises(GenesetCollectionError, match="dataset_usage"):
        parse_geneset_rows(
            [{"set_key": "A", "name": "one", "member_ids": "HGNC:1", "dataset_usage": '{"ref":"dataset:x"}'}]
        )


def test_dataset_usage_accepts_full_canonical_role_vocabulary() -> None:
    rows = parse_geneset_rows(
        [
            {
                "set_key": "A",
                "name": "one",
                "member_ids": "HGNC:1",
                "dataset_usage": '[{"ref":"dataset:x","role":"training"}]',
            }
        ]
    )
    assert rows[0].dataset_usage[0]["role"] == "training"


def test_dataset_usage_rejects_noncanonical_role() -> None:
    with pytest.raises(GenesetCollectionError, match="role"):
        parse_geneset_rows(
            [
                {
                    "set_key": "A",
                    "name": "one",
                    "member_ids": "HGNC:1",
                    "dataset_usage": '[{"ref":"dataset:x","role":"made_up"}]',
                }
            ]
        )


def test_derived_source_class_requires_derived_kind() -> None:
    with pytest.raises(GenesetCollectionError, match="derived_kind"):
        parse_geneset_rows([{"set_key": "A", "name": "one", "member_ids": "HGNC:1", "source_class": "derived"}])
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
rtk uv run pytest tests/test_commons_geneset.py -q
```

Expected: FAIL because `science_tool.commons.geneset` does not exist.

- [ ] **Step 3: Implement `science_tool.commons.geneset`**

Create `science/src/science_tool/commons/geneset.py`:

```python
"""D1 parser for bio.geneset collection member rows.

Rows are collection members, not promoted entities. The set identity is the
opaque `set_key`; member identifiers are interpreted in the collection-level
`identifier_space`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, get_args

from science_model.entity_schema.loader import SchemaLoader
from science_model.entity_schema.profile import ProfileComponent
from science_model.packages.schema import DatasetUsage

GENESET_MEMBER_KEY_COLUMN = "set_key"
GENESET_REQUIRED_COLUMNS = frozenset({"set_key", "name", "member_ids"})
_DATASET_SCHEMA = SchemaLoader().load(ProfileComponent(name="dataset", version="1.0"))
GENESET_SOURCE_CLASSES = frozenset(_DATASET_SCHEMA["properties"]["source_class"]["enum"])
GENESET_DERIVED_KINDS = frozenset(_DATASET_SCHEMA["properties"]["derived_kind"]["enum"])
GENESET_USAGE_ROLES = frozenset(get_args(DatasetUsage.model_fields["role"].annotation))
GENESET_USAGE_OVERLAPS = frozenset(get_args(DatasetUsage.model_fields["overlap"].annotation))


class GenesetCollectionError(ValueError):
    """A bio.geneset collection row violates the D1 row contract."""


@dataclass(frozen=True, slots=True)
class GenesetRow:
    set_key: str
    name: str
    member_ids: tuple[str, ...]
    source_class: str | None
    derived_kind: str | None
    dataset_usage: tuple[dict[str, Any], ...]
    source_pmids: tuple[str, ...]

    @property
    def n_members(self) -> int:
        return len(self.member_ids)


def _split_semicolon(raw: str) -> tuple[str, ...]:
    return tuple(part.strip() for part in raw.split(";") if part.strip())


def _dataset_usage_defect(entry: Any) -> str | None:
    if not isinstance(entry, dict):
        return "entry is not an object"
    ref = entry.get("ref")
    if not isinstance(ref, str) or not ref.startswith("dataset:"):
        return "ref must be a 'dataset:' reference"
    role = entry.get("role")
    if role not in GENESET_USAGE_ROLES:
        return f"role must be one of {sorted(GENESET_USAGE_ROLES)}"
    overlap = entry.get("overlap")
    if overlap is not None and overlap not in GENESET_USAGE_OVERLAPS:
        return f"overlap must be one of {sorted(GENESET_USAGE_OVERLAPS)}"
    return None


def _parse_dataset_usage(raw: str, *, row_number: int) -> tuple[dict[str, Any], ...]:
    text = raw.strip()
    if not text:
        return ()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise GenesetCollectionError(f"row {row_number}: dataset_usage is not valid JSON: {exc.msg}") from exc
    if not isinstance(parsed, list):
        raise GenesetCollectionError(f"row {row_number}: dataset_usage must be a JSON list")
    out: list[dict[str, Any]] = []
    for index, entry in enumerate(parsed):
        defect = _dataset_usage_defect(entry)
        if defect is not None:
            raise GenesetCollectionError(f"row {row_number}: dataset_usage[{index}] malformed -- {defect}")
        out.append(entry)
    return tuple(out)


def _source_class_defect(source_class: str | None, derived_kind: str | None) -> str | None:
    if source_class is not None and source_class not in GENESET_SOURCE_CLASSES:
        return f"source_class must be one of {sorted(GENESET_SOURCE_CLASSES)}"
    if source_class == "derived":
        if derived_kind not in GENESET_DERIVED_KINDS:
            return f"source_class=derived requires derived_kind one of {sorted(GENESET_DERIVED_KINDS)}"
    elif derived_kind is not None:
        return "derived_kind is only allowed when source_class=derived"
    return None


def parse_geneset_rows(rows: list[dict[str, Any]]) -> list[GenesetRow]:
    out: list[GenesetRow] = []
    seen: set[str] = set()
    for row_number, row in enumerate(rows, start=1):
        missing = [col for col in sorted(GENESET_REQUIRED_COLUMNS) if col not in row]
        if missing:
            raise GenesetCollectionError(f"row {row_number}: missing required columns {missing}")
        set_key = str(row.get("set_key") or "").strip()
        if not set_key:
            raise GenesetCollectionError(f"row {row_number}: blank set_key")
        if set_key in seen:
            raise GenesetCollectionError(f"duplicate set_key {set_key!r}")
        seen.add(set_key)
        name = str(row.get("name") or "").strip()
        if not name:
            raise GenesetCollectionError(f"row {row_number}: blank name")
        member_ids = _split_semicolon(str(row.get("member_ids") or ""))
        if not member_ids:
            raise GenesetCollectionError(f"row {row_number}: member_ids must contain at least one identifier")
        source_class = str(row["source_class"]).strip() if row.get("source_class") not in (None, "") else None
        derived_kind = str(row["derived_kind"]).strip() if row.get("derived_kind") not in (None, "") else None
        defect = _source_class_defect(source_class, derived_kind)
        if defect is not None:
            raise GenesetCollectionError(f"row {row_number}: {defect}")
        out.append(
            GenesetRow(
                set_key=set_key,
                name=name,
                member_ids=member_ids,
                source_class=source_class,
                derived_kind=derived_kind,
                dataset_usage=_parse_dataset_usage(str(row.get("dataset_usage") or ""), row_number=row_number),
                source_pmids=_split_semicolon(str(row.get("source_pmids") or "")),
            )
        )
    return out
```

- [ ] **Step 4: Run parser tests**

Run:

```bash
rtk uv run pytest tests/test_commons_geneset.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
rtk git add science/src/science_tool/commons/geneset.py science/tests/test_commons_geneset.py
rtk git commit -m "commons: parse geneset collection rows"
```

---

### Task 3: Add The Gene-Set Validate Check

**Files:**
- Create: `science/src/science_tool/validate/checks/genesets.py`
- Create: `science/tests/validate/test_checks_genesets.py`
- Modify: `science/src/science_tool/validate/checks/__init__.py`
- Modify: validate parity module lists.

- [ ] **Step 1: Write failing pure tests for D1 collection evaluation**

Create the first half of `science/tests/validate/test_checks_genesets.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest

from science_tool.validate.checks.genesets import evaluate_geneset_collections
from science_tool.validate.result import Severity


_GENE_REGISTRY = "dataset:gene-crosswalk-hgnc"
_VALID_GENE_META = {
    "schema_profile": "science-entity-base/1.0+dataset/1.0+bio.gene_crosswalk/1.0",
    "member_key_column": "gene_key",
}


def _geneset(**extra) -> dict:
    return {
        "id": "dataset:reactome-v89",
        "type": "dataset",
        "schema_profile": "science-entity-base/1.0+dataset/1.0+bio.geneset/1.0",
        "_path": "data/reactome/datapackage.yaml",
        "source_class": "reference",
        "member_key_column": "set_key",
        "members_resource": "sets",
        "n_sets": 1,
        "set_size_summary": {"min": 2, "median": 2, "max": 2},
        "identifier_space": {
            "tier": "gene",
            "namespace": "hgnc_id",
            "registry": _GENE_REGISTRY,
            "resolution_status": "resolved",
        },
        **extra,
    }


def _row(**extra) -> dict:
    return {"set_key": "R-HSA-1", "name": "Cell cycle", "member_ids": "HGNC:1;HGNC:2", **extra}


def _rules(results) -> list[str]:
    return [r.rule for r in results]


def test_valid_geneset_collection_passes_silently() -> None:
    results = list(
        evaluate_geneset_collections(
            [_geneset()],
            rows_by_dataset_id={"dataset:reactome-v89": [_row()]},
            registry_meta_by_id={_GENE_REGISTRY: _VALID_GENE_META},
        )
    )
    assert results == []


def test_malformed_collection_errors() -> None:
    fm = _geneset(member_key_column="pathway_id")
    results = list(
        evaluate_geneset_collections(
            [fm],
            rows_by_dataset_id={"dataset:reactome-v89": [_row()]},
            registry_meta_by_id={_GENE_REGISTRY: _VALID_GENE_META},
        )
    )
    assert _rules(results) == ["geneset.collection-malformed"]
    assert results[0].severity is Severity.ERROR


def test_n_sets_mismatch_errors() -> None:
    fm = _geneset(n_sets=2)
    results = list(
        evaluate_geneset_collections(
            [fm],
            rows_by_dataset_id={"dataset:reactome-v89": [_row()]},
            registry_meta_by_id={_GENE_REGISTRY: _VALID_GENE_META},
        )
    )
    assert _rules(results) == ["geneset.n-sets-mismatch"]


def test_set_size_summary_mismatch_errors() -> None:
    fm = _geneset(set_size_summary={"min": 1, "median": 1, "max": 1})
    results = list(
        evaluate_geneset_collections(
            [fm],
            rows_by_dataset_id={"dataset:reactome-v89": [_row()]},
            registry_meta_by_id={_GENE_REGISTRY: _VALID_GENE_META},
        )
    )
    assert _rules(results) == ["geneset.set-size-summary-mismatch"]


def test_unsupported_identifier_namespace_errors() -> None:
    fm = _geneset(identifier_space={"tier": "gene", "namespace": "refseq"})
    results = list(
        evaluate_geneset_collections(
            [fm],
            rows_by_dataset_id={"dataset:reactome-v89": [_row()]},
            registry_meta_by_id={_GENE_REGISTRY: _VALID_GENE_META},
        )
    )
    assert _rules(results) == ["geneset.identifier-namespace-unsupported"]


def test_unavailable_registry_infos() -> None:
    results = list(
        evaluate_geneset_collections(
            [_geneset()],
            rows_by_dataset_id={"dataset:reactome-v89": [_row()]},
            registry_meta_by_id={_GENE_REGISTRY: None},
        )
    )
    assert _rules(results) == ["geneset.identifier-registry-unavailable"]
    assert results[0].severity is Severity.INFO


def test_declared_unresolved_infos_and_skips_registry_validation() -> None:
    fm = _geneset(identifier_space={"tier": "gene", "namespace": "hgnc_id", "resolution_status": "declared_unresolved"})
    results = list(
        evaluate_geneset_collections(
            [fm],
            rows_by_dataset_id={"dataset:reactome-v89": [_row()]},
            registry_meta_by_id={},
        )
    )
    assert _rules(results) == ["geneset.identifier-declared-unresolved"]
    assert results[0].severity is Severity.INFO
```

- [ ] **Step 2: Run pure tests to verify failure**

Run:

```bash
rtk uv run pytest tests/validate/test_checks_genesets.py -q
```

Expected: FAIL because `science_tool.validate.checks.genesets` does not exist.

- [ ] **Step 3: Implement the validate check core**

Create `science/src/science_tool/validate/checks/genesets.py` with this structure:

```python
"""Gene-set collection checks (Pillar D1).

Reads raw dataset frontmatter by tolerant discovery, then validates the declared
members resource as collection rows. D1 does not mint or validate promoted
members; every set remains a row addressed by set_key.
"""

from __future__ import annotations

import csv
import math
from collections.abc import Iterable, Iterator
from pathlib import Path
from statistics import median
from typing import Any

import yaml

from science_tool.commons.adapter import CommonsEntityAdapter
from science_tool.commons.config import resolve_commons_root
from science_tool.commons.errors import CommonsError
from science_tool.commons.gene_crosswalk import (
    GENE_CROSSWALK_ID,
    MEMBER_KEY_COLUMN as GENE_KEY_COLUMN,
    SUPPORTED_GENE_NAMESPACES,
)
from science_tool.commons.geneset import (
    GENESET_MEMBER_KEY_COLUMN,
    GenesetCollectionError,
    GenesetRow,
    parse_geneset_rows,
)
from science_tool.commons.protein_crosswalk import (
    MEMBER_KEY_COLUMN as PROTEIN_KEY_COLUMN,
    PROTEIN_CROSSWALK_ID,
    SUPPORTED_PROTEIN_NAMESPACES,
)
from science_tool.validate._helpers import dataset_frontmatters
from science_tool.validate.checks import Check
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Result, Severity

_PROFILE_TOKEN = "+bio.geneset/"
_SUPPORTED_BY_TIER = {
    "gene": (SUPPORTED_GENE_NAMESPACES, GENE_CROSSWALK_ID, "+bio.gene_crosswalk/", GENE_KEY_COLUMN),
    "protein": (SUPPORTED_PROTEIN_NAMESPACES, PROTEIN_CROSSWALK_ID, "+bio.protein_crosswalk/", PROTEIN_KEY_COLUMN),
}


def _result(severity: Severity, path: str | None, message: str, rule: str) -> Result:
    return Result(severity, Path(path) if path else None, None, message, rule, None)


def _is_geneset(fm: dict[str, Any]) -> bool:
    profile = str(fm.get("schema_profile") or "")
    return (fm.get("kind") or fm.get("type")) == "dataset" and _PROFILE_TOKEN in f"+{profile}"


def _collection_defect(fm: dict[str, Any]) -> str | None:
    if fm.get("member_key_column") != GENESET_MEMBER_KEY_COLUMN:
        return "member_key_column must be 'set_key'"
    resource = fm.get("members_resource")
    if not isinstance(resource, str) or not resource.strip():
        return "members_resource must name a Frictionless resource"
    n_sets = fm.get("n_sets")
    if not isinstance(n_sets, int) or n_sets < 1:
        return "n_sets must be a positive integer"
    summary = fm.get("set_size_summary")
    if not isinstance(summary, dict):
        return "set_size_summary must be an object"
    for key in ("min", "median", "max"):
        value = summary.get(key)
        if not isinstance(value, (int, float)) or value < 0:
            return f"set_size_summary.{key} must be a non-negative number"
    if not (summary["min"] <= summary["median"] <= summary["max"]):
        return "set_size_summary must satisfy min <= median <= max"
    ident = fm.get("identifier_space")
    if not isinstance(ident, dict):
        return "identifier_space must be an object"
    tier = ident.get("tier")
    if tier not in _SUPPORTED_BY_TIER:
        return "identifier_space.tier must be 'gene' or 'protein'"
    namespace = ident.get("namespace")
    if not isinstance(namespace, str) or not namespace.strip():
        return "identifier_space.namespace is required"
    registry = ident.get("registry")
    if registry is not None and (not isinstance(registry, str) or not registry.startswith("dataset:")):
        return "identifier_space.registry must be a 'dataset:' reference"
    status = ident.get("resolution_status")
    if status not in (None, "resolved", "declared_unresolved"):
        return "identifier_space.resolution_status must be 'resolved' or 'declared_unresolved'"
    return None


def _registry_id(ident: dict[str, Any]) -> str:
    tier = str(ident["tier"])
    return ident["registry"] if isinstance(ident.get("registry"), str) else _SUPPORTED_BY_TIER[tier][1]


def _is_expected_registry(meta: dict[str, Any], *, tier: str) -> bool:
    _namespaces, _default_id, profile_token, key_column = _SUPPORTED_BY_TIER[tier]
    profile = str(meta.get("schema_profile") or "")
    return profile_token in f"+{profile}" and meta.get("member_key_column") == key_column


def _row_stats(rows: list[GenesetRow]) -> tuple[int, float, int]:
    sizes = sorted(row.n_members for row in rows)
    return sizes[0], float(median(sizes)), sizes[-1]


def _summary_matches(summary: dict[str, Any], rows: list[GenesetRow]) -> bool:
    min_size, median_size, max_size = _row_stats(rows)
    return (
        summary.get("min") == min_size
        and math.isclose(float(summary.get("median")), median_size, rel_tol=0.0, abs_tol=1e-9)
        and summary.get("max") == max_size
    )


def evaluate_geneset_collections(
    datasets: Iterable[dict[str, Any]],
    *,
    rows_by_dataset_id: dict[str, list[dict[str, Any]] | Exception],
    registry_meta_by_id: dict[str, dict[str, Any] | None],
) -> Iterator[Result]:
    for fm in datasets:
        if not _is_geneset(fm):
            continue
        ident = str(fm.get("id") or "?")
        path = fm.get("_path")
        defect = _collection_defect(fm)
        if defect is not None:
            yield _result(Severity.ERROR, path, f"{ident}: malformed bio.geneset collection -- {defect}", "geneset.collection-malformed")
            continue
        raw_rows = rows_by_dataset_id.get(ident)
        if raw_rows is None:
            yield _result(Severity.INFO, path, f"{ident}: members_resource is unavailable; row contract cannot be verified", "geneset.members-resource-unavailable")
            continue
        if isinstance(raw_rows, Exception):
            yield _result(Severity.ERROR, path, f"{ident}: members_resource malformed -- {raw_rows}", "geneset.members-resource-malformed")
            continue
        try:
            rows = parse_geneset_rows(raw_rows)
        except GenesetCollectionError as exc:
            yield _result(Severity.ERROR, path, f"{ident}: members_resource malformed -- {exc}", "geneset.members-resource-malformed")
            continue
        if len(rows) != fm["n_sets"]:
            yield _result(Severity.ERROR, path, f"{ident}: n_sets={fm['n_sets']} but members_resource has {len(rows)} rows", "geneset.n-sets-mismatch")
            continue
        if not _summary_matches(fm["set_size_summary"], rows):
            yield _result(Severity.ERROR, path, f"{ident}: set_size_summary does not match members_resource member counts", "geneset.set-size-summary-mismatch")
            continue
        ident_space = fm["identifier_space"]
        tier = str(ident_space["tier"])
        supported_namespaces = _SUPPORTED_BY_TIER[tier][0]
        namespace = str(ident_space["namespace"])
        if namespace not in supported_namespaces:
            yield _result(Severity.ERROR, path, f"{ident}: identifier_space namespace {namespace!r} is not supported for {tier}", "geneset.identifier-namespace-unsupported")
            continue
        if ident_space.get("resolution_status") == "declared_unresolved":
            yield _result(Severity.INFO, path, f"{ident}: identifier_space declared_unresolved (honoured, RCM-D2)", "geneset.identifier-declared-unresolved")
            continue
        registry_id = _registry_id(ident_space)
        meta = registry_meta_by_id.get(registry_id)
        if meta is None:
            yield _result(Severity.INFO, path, f"{ident}: identifier registry {registry_id!r} unavailable; namespace cannot be verified", "geneset.identifier-registry-unavailable")
            continue
        if not _is_expected_registry(meta, tier=tier):
            yield _result(Severity.ERROR, path, f"{ident}: identifier registry {registry_id!r} is not a {tier} crosswalk collection", "geneset.identifier-registry-invalid")
```

Then add runtime helpers below the pure core:

```python
def _resource_path_for_members(project_root: Path, fm: dict[str, Any]) -> Path | None:
    rel = fm.get("_path")
    resource_name = fm.get("members_resource")
    if not isinstance(rel, str) or not isinstance(resource_name, str):
        return None
    dp_path = project_root / rel
    try:
        doc = yaml.safe_load(dp_path.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError):
        return None
    resources = doc.get("resources")
    if not isinstance(resources, list):
        return None
    for resource in resources:
        if not isinstance(resource, dict):
            continue
        if resource.get("name") == resource_name and isinstance(resource.get("path"), str):
            return dp_path.parent / resource["path"]
    return None


def _read_member_rows(project_root: Path, fm: dict[str, Any]) -> list[dict[str, Any]] | Exception | None:
    path = _resource_path_for_members(project_root, fm)
    if path is None or not path.is_file():
        return None
    try:
        with path.open(encoding="utf-8", newline="") as fh:
            return list(csv.DictReader(fh))
    except OSError as exc:
        return exc


def _load_registry_meta(
    registry_id: str,
    *,
    local_by_id: dict[str, dict[str, Any]],
    commons_cache: dict[str, dict[str, Any] | None],
) -> dict[str, Any] | None:
    if registry_id in local_by_id:
        fm = local_by_id[registry_id]
        return {"schema_profile": fm.get("schema_profile", ""), "member_key_column": fm.get("member_key_column")}
    if registry_id in commons_cache:
        return commons_cache[registry_id]
    root = resolve_commons_root()
    meta: dict[str, Any] | None = None
    if root.is_dir():
        try:
            record = CommonsEntityAdapter(root).load(registry_id)
            fm = record.frontmatter
            meta = {"schema_profile": fm.get("schema_profile", ""), "member_key_column": fm.get("member_key_column")}
        except CommonsError:
            meta = None
    commons_cache[registry_id] = meta
    return meta


@Check(section="gene-set collections", order=34)
def check_genesets(ctx: ValidateContext) -> Iterator[Result]:
    datasets = dataset_frontmatters(ctx)
    genesets = [fm for fm in datasets if _is_geneset(fm)]
    local_by_id = {fm["id"]: fm for fm in datasets if isinstance(fm.get("id"), str) and fm["id"]}
    rows_by_dataset_id = {
        str(fm["id"]): _read_member_rows(ctx.project_root, fm)
        for fm in genesets
        if isinstance(fm.get("id"), str) and fm["id"]
    }
    declared_registries: set[str] = set()
    for fm in genesets:
        ident = fm.get("identifier_space")
        if not isinstance(ident, dict) or ident.get("resolution_status") == "declared_unresolved":
            continue
        tier = ident.get("tier")
        namespace = ident.get("namespace")
        if tier in _SUPPORTED_BY_TIER and isinstance(namespace, str) and namespace in _SUPPORTED_BY_TIER[str(tier)][0]:
            declared_registries.add(_registry_id(ident))
    commons_cache: dict[str, dict[str, Any] | None] = {}
    registry_meta_by_id = {
        registry_id: _load_registry_meta(registry_id, local_by_id=local_by_id, commons_cache=commons_cache)
        for registry_id in declared_registries
    }
    yield from evaluate_geneset_collections(
        genesets,
        rows_by_dataset_id=rows_by_dataset_id,
        registry_meta_by_id=registry_meta_by_id,
    )
```

- [ ] **Step 4: Register the check**

In `science/src/science_tool/validate/checks/__init__.py`, insert `"genesets"` immediately after `"variant_identity"` and before `"prose_lints"`:

```python
        "dataset_taxonomy",
        "variant_identity",
        "genesets",
        "prose_lints",
```

Add `"genesets"` in the same position in the `CHECK_MODULES` tuples in:

- `science/tests/validate/test_formatter_snapshots.py`
- `science/tests/validate/test_parity_corpus.py`
- `science/tests/validate/test_parity_canonical_body.py`

Update `science/tests/validate/test_runner.py` expected module/order assertions to include `genesets`.

- [ ] **Step 5: Run pure tests**

Run:

```bash
rtk uv run pytest tests/validate/test_checks_genesets.py -q
```

Expected: PASS for the pure tests added so far.

- [ ] **Step 6: Commit**

```bash
rtk git add science/src/science_tool/validate/checks/genesets.py science/src/science_tool/validate/checks/__init__.py science/tests/validate/test_checks_genesets.py science/tests/validate/test_formatter_snapshots.py science/tests/validate/test_parity_corpus.py science/tests/validate/test_parity_canonical_body.py science/tests/validate/test_runner.py
rtk git commit -m "validate: add geneset collection check"
```

---

### Task 4: Add Integration Tests For Members Resources And Commons Registries

**Files:**
- Modify: `science/tests/validate/test_checks_genesets.py`

- [ ] **Step 1: Add fixture scaffolding and integration tests**

Append to `science/tests/validate/test_checks_genesets.py`:

```python
from science_tool.validate.checks.genesets import check_genesets
from science_tool.validate.context import ValidateContext

_MANIFEST = (
    "name: demo\ncreated: 2026-01-01\nlast_modified: 2026-01-02\nstatus: active\n"
    "summary: demo\nprofile: research\nlayout_version: 1\n"
    "knowledge_profiles:\n  local: knowledge/local\n"
)


def _ctx(project_root: Path) -> ValidateContext:
    return ValidateContext.from_project_root(project_root, strict=False, verbose=False)


def _scaffold_project(tmp_path: Path) -> None:
    tmp_path.joinpath("science.yaml").write_text(_MANIFEST, encoding="utf-8")
    (tmp_path / "knowledge" / "local").mkdir(parents=True)


def _write_geneset_dataset(tmp_path: Path, *, rows: str, n_sets: int = 1) -> None:
    dataset_dir = tmp_path / "data" / "reactome"
    dataset_dir.mkdir(parents=True)
    (dataset_dir / "sets.csv").write_text(rows, encoding="utf-8")
    (dataset_dir / "datapackage.yaml").write_text(
        f'''\
profiles: [science-pkg-entity-1.0]
schema_profile: "science-entity-base/1.0+dataset/1.0+bio.geneset/1.0"
id: dataset:reactome-v89
type: dataset
title: Reactome v89
status: active
origin: external
tier: use-now
source_class: reference
access: {{level: public, verified: true}}
member_key_column: set_key
members_resource: sets
n_sets: {n_sets}
set_size_summary: {{min: 2, median: 2, max: 2}}
identifier_space:
  tier: gene
  namespace: hgnc_id
  registry: dataset:gene-crosswalk-hgnc
resources:
  - name: sets
    path: sets.csv
''',
        encoding="utf-8",
    )


def _write_gene_crosswalk_dataset(tmp_path: Path) -> None:
    dataset_dir = tmp_path / "data" / "gene-crosswalk"
    dataset_dir.mkdir(parents=True)
    (dataset_dir / "datapackage.yaml").write_text(
        '''\
profiles: [science-pkg-entity-1.0]
schema_profile: "science-entity-base/1.0+dataset/1.0+bio.gene_crosswalk/1.0"
id: dataset:gene-crosswalk-hgnc
type: dataset
title: HGNC crosswalk
status: active
origin: external
tier: use-now
source_class: reference
access: {level: public, verified: true}
member_key_column: gene_key
resources:
  - name: crosswalk
    path: crosswalk.csv
''',
        encoding="utf-8",
    )


def _write_gene_crosswalk_commons(tmp_path: Path) -> Path:
    commons = tmp_path / "commons"
    dataset_dir = commons / "datasets" / "gene-crosswalk-hgnc"
    dataset_dir.mkdir(parents=True)
    (dataset_dir / "entity.md").write_text(
        '''\
---
schema_profile: "science-entity-base/1.0+dataset/1.0+bio.gene_crosswalk/1.0"
id: dataset:gene-crosswalk-hgnc
type: dataset
title: HGNC crosswalk
version: 1.0.0
status: active
created: 2026-05-28
updated: 2026-05-28
datapackage: datapackage.yaml
origin: external
tier: use-now
source_class: reference
access: {level: public, verified: true}
member_key_column: gene_key
---

# HGNC crosswalk
''',
        encoding="utf-8",
    )
    (dataset_dir / "datapackage.yaml").write_text(
        '''\
name: gene-crosswalk-hgnc
resources:
  - name: crosswalk
    path: crosswalk.csv
    hash: "sha256:0000000000000000000000000000000000000000000000000000000000000000"
    bytes: 0
''',
        encoding="utf-8",
    )
    return commons


def test_check_genesets_reads_local_members_resource(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(tmp_path / "empty-commons"))
    (tmp_path / "empty-commons").mkdir()
    _scaffold_project(tmp_path)
    _write_gene_crosswalk_dataset(tmp_path)
    _write_geneset_dataset(
        tmp_path,
        rows="set_key,name,member_ids,dataset_usage,source_pmids\n"
        'R-HSA-1,Cell cycle,HGNC:1;HGNC:2,"[{""ref"":""dataset:study-a"",""role"":""set_definition_source""}]",12345\n',
    )
    results = list(check_genesets(_ctx(tmp_path)))
    assert results == []


def test_check_genesets_resolves_identifier_registry_from_commons(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _scaffold_project(tmp_path)
    commons = _write_gene_crosswalk_commons(tmp_path)
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(commons))
    _write_geneset_dataset(
        tmp_path,
        rows="set_key,name,member_ids,dataset_usage,source_pmids\n"
        'R-HSA-1,Cell cycle,HGNC:1;HGNC:2,"[{""ref"":""dataset:study-a"",""role"":""training""}]",12345\n',
    )
    results = list(check_genesets(_ctx(tmp_path)))
    assert results == []


def test_check_genesets_reports_malformed_rows(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(tmp_path / "empty-commons"))
    (tmp_path / "empty-commons").mkdir()
    _scaffold_project(tmp_path)
    _write_gene_crosswalk_dataset(tmp_path)
    _write_geneset_dataset(
        tmp_path,
        rows="set_key,name,member_ids\nR-HSA-1,Cell cycle,\n",
    )
    results = list(check_genesets(_ctx(tmp_path)))
    assert [r.rule for r in results] == ["geneset.members-resource-malformed"]
    assert results[0].severity is Severity.ERROR


def test_check_genesets_unbuilt_members_resource_infos(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(tmp_path / "empty-commons"))
    (tmp_path / "empty-commons").mkdir()
    _scaffold_project(tmp_path)
    _write_gene_crosswalk_dataset(tmp_path)
    _write_geneset_dataset(tmp_path, rows="set_key,name,member_ids\nR-HSA-1,Cell cycle,HGNC:1;HGNC:2\n")
    (tmp_path / "data" / "reactome" / "sets.csv").unlink()
    results = list(check_genesets(_ctx(tmp_path)))
    assert [r.rule for r in results] == ["geneset.members-resource-unavailable"]
    assert results[0].severity is Severity.INFO
```

- [ ] **Step 2: Run integration tests**

Run:

```bash
rtk uv run pytest tests/validate/test_checks_genesets.py -q
```

Expected: PASS.

- [ ] **Step 3: Run validate registry/parity checks**

Run:

```bash
rtk uv run pytest tests/validate/test_runner.py tests/validate/test_formatter_snapshots.py tests/validate/test_parity_corpus.py tests/validate/test_parity_canonical_body.py -q
```

Expected: PASS. If snapshot output changes only because the new section appears, regenerate snapshots using the repository's existing snapshot update workflow and inspect the diff before committing.

- [ ] **Step 4: Commit**

```bash
rtk git add science/tests/validate/test_checks_genesets.py science/tests/validate/test_runner.py science/tests/validate/test_formatter_snapshots.py science/tests/validate/test_parity_corpus.py science/tests/validate/test_parity_canonical_body.py science/tests/validate/snapshots/json_default.json science/tests/validate/snapshots/text_default.txt
rtk git commit -m "test: cover geneset collection validation"
```

---

### Task 5: Add Graph/Parse-Path Coverage If Needed

**Files:**
- Modify only if tests prove extension fields are dropped:
  - `science/src/science_tool/graph/storage_adapters/datapackage.py`
  - `science/model/src/science_model/frontmatter.py`
  - `science/model/src/science_model/entities.py`
- Test:
  - `science/tests/test_storage_adapters/test_datapackage.py`
  - `science/model/tests/test_frontmatter_dataset.py`

- [ ] **Step 1: Write a guard test for datapackage raw field retention**

Add this test to `science/tests/test_storage_adapters/test_datapackage.py`:

```python
def test_datapackage_adapter_preserves_geneset_extension_fields(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from science_tool.graph.storage_adapters.datapackage import DatapackageAdapter
    from science_model.source_ref import SourceRef

    dp = tmp_path / "data" / "reactome" / "datapackage.yaml"
    dp.parent.mkdir(parents=True)
    dp.write_text(
        """\
profiles: [science-pkg-entity-1.0]
id: dataset:reactome-v89
type: dataset
title: Reactome v89
status: active
origin: external
tier: use-now
member_key_column: set_key
members_resource: sets
n_sets: 1
set_size_summary: {min: 2, median: 2, max: 2}
identifier_space: {tier: gene, namespace: hgnc_id}
""",
        encoding="utf-8",
    )
    monkeypatch.chdir(tmp_path)
    raw = DatapackageAdapter().load_raw(SourceRef(adapter_name="datapackage", path="data/reactome/datapackage.yaml"))
    assert raw["member_key_column"] == "set_key"
    assert raw["members_resource"] == "sets"
    assert raw["identifier_space"]["namespace"] == "hgnc_id"
```

- [ ] **Step 2: Run the guard test**

Run:

```bash
rtk uv run pytest tests/test_storage_adapters/test_datapackage.py::test_datapackage_adapter_preserves_geneset_extension_fields -q
```

Expected before implementation: FAIL because `_ENTITY_FIELDS` does not include the D1 fields.

- [ ] **Step 3: Preserve D1 fields in the graph adapter**

In `science/src/science_tool/graph/storage_adapters/datapackage.py`, extend `_ENTITY_FIELDS`:

```python
    "member_key_column",
    "members_resource",
    "n_sets",
    "set_size_summary",
    "identifier_space",
```

Do not add Pydantic fields unless a parse-path test proves they are needed. The schema wrapper already captures unknown extension fields in `extra`, and the validate check reads raw frontmatter via `dataset_frontmatters`.

- [ ] **Step 4: Run graph adapter guard**

Run:

```bash
rtk uv run pytest tests/test_storage_adapters/test_datapackage.py::test_datapackage_adapter_preserves_geneset_extension_fields -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
rtk git add science/src/science_tool/graph/storage_adapters/datapackage.py science/tests/test_storage_adapters/test_datapackage.py
rtk git commit -m "graph: retain geneset extension fields"
```

---

### Task 6: Update Docs And Mark D1 Implemented

**Files:**
- Modify: `docs/plans/2026-05-26-bio-geneset-type-design.md`
- Modify: `docs/plans/2026-05-26-bio-data-architecture-umbrella-design.md`

- [ ] **Step 1: Update D design status**

In `docs/plans/2026-05-26-bio-geneset-type-design.md`, update status and §8 after implementation:

```markdown
Status: approved; D1 collection type implemented, D2 promoted-member implementation deferred
```

In §8, state that D1 shipped:

```markdown
Pillar D D1 is implemented: `bio.geneset` collections now have a schema profile, collection-row parser,
and `science validate` check for `set_key` uniqueness, row counts, set-size summaries, per-set provenance
row shape, and C-backed identifier-space declarations. D2 promoted members remain deferred until evidence
lines need to cite individual sets as child datasets.
```

- [ ] **Step 2: Update umbrella status**

In `docs/plans/2026-05-26-bio-data-architecture-umbrella-design.md`, update Phase 3a row from "impl not started" to:

```markdown
design ✓; impl: D1 collection type merged; D2 promoted members pending
```

Also update §8 Remaining to say D has D1 merged and B is the next dependency for provenance materialization.

- [ ] **Step 3: Run docs grep**

Run:

```bash
rtk rg -n "D1|bio.geneset|promoted-member|impl not started|Pillar D" docs/plans/2026-05-26-bio-geneset-type-design.md docs/plans/2026-05-26-bio-data-architecture-umbrella-design.md
```

Expected: D1 status is internally consistent; no stale "D impl not started" remains for the collection type.

- [ ] **Step 4: Commit**

```bash
rtk git add docs/plans/2026-05-26-bio-geneset-type-design.md docs/plans/2026-05-26-bio-data-architecture-umbrella-design.md
rtk git commit -m "docs: mark geneset D1 implemented"
```

---

### Task 7: Final Verification

**Files:**
- No edits unless verification finds a real defect.

- [ ] **Step 1: Run focused suite**

Run:

```bash
rtk uv run pytest model/tests/test_bio_extension_geneset.py tests/test_commons_geneset.py tests/validate/test_checks_genesets.py tests/test_storage_adapters/test_datapackage.py -q
```

Expected: PASS.

- [ ] **Step 2: Run affected validate suite**

Run:

```bash
rtk uv run pytest tests/validate -q
```

Expected: PASS.

- [ ] **Step 3: Run full suite**

Run:

```bash
rtk uv run pytest tests/ -q
```

Expected: PASS.

- [ ] **Step 4: Review diff**

Run:

```bash
rtk git status --short
rtk git diff --stat
rtk git diff -- docs/plans/2026-05-26-bio-geneset-type-design.md docs/plans/2026-05-26-bio-data-architecture-umbrella-design.md
```

Expected: only D1-related docs/code/tests changed.

---

## Self-Review

**Spec coverage:** D1 collection profile is Task 1. Row-level `set_key`, members, provenance columns, and per-set override validation are Task 2. `identifier_space` against C2/C3 registry metadata is Task 3. Tolerant resource handling and integration coverage are Task 4. Graph raw-field retention is Task 5. Docs status is Task 6. D2 is explicitly excluded.

**Placeholders:** No `TBD`, open-ended "add tests", or unspecified error handling remains. Each task names files, commands, expected results, and concrete code.

**Type consistency:** The schema, parser, and validate check use the same field names: `member_key_column`, `members_resource`, `n_sets`, `set_size_summary`, `identifier_space`, `set_key`, `member_ids`, `dataset_usage`, `source_pmids`. Validate rule names all use the `geneset.` prefix.

**Known implementation caution:** Do not use JSON Schema `$data`; enforce cross-field summary consistency in Python. Derive the row parser's `source_class`, `derived_kind`, `dataset_usage.role`, and `dataset_usage.overlap` vocabularies from the canonical dataset mixin / `DatasetUsage` model rather than retyping local enums. Do not implement `bio.geneset.member` in this plan. Do not resolve every member identifier to a canonical key in D1; D1 validates the declared identifier space and row shape, while full payload canonicalization can be added when an ingest recipe needs it.

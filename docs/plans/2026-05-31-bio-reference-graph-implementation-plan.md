# Bio Reference Graph RG1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement RG1 from `docs/plans/2026-05-31-bio-reference-graph-design.md`: schemas, parsers, resource lookup, and validation for tiny pinned graph/index/edge fixtures.

**Architecture:** RG1 mirrors D1 gene-set implementation: a schema profile declares the dataset shape, a pure commons parser validates node/edge rows, a resource helper resolves local/commons datapackage resources, and a `science validate` check composes those pieces. RG1 intentionally validates build-derived `nodes.csv` / `edges.csv` projections rather than reconciling them against full RDF.

**Tech Stack:** Python 3.12, Pydantic/jsonschema-backed entity schemas, Frictionless-style datapackage YAML, CSV/JSON parsers from the standard library, pytest, ruff, pyright.

---

## Scope

Implement RG1 only:

- `bio.reference_graph/1.0` schema.
- `bio.reference_graph.member/1.0` schema.
- Pure parser for node-index rows and optional edge rows.
- Resource helper for graph/node/edge resources.
- Validation check for collection shape, resource availability, row contracts, counts, and promoted-member resolution.
- Hermetic tests with tiny fixture CSV/JSONL/RDF paths.

Do not implement:

- Full GO/MONDO/Open Targets recipes.
- RDF triple parsing or graph/index reconciliation.
- Non-molecular identity resolvers.
- Generic virtual-member payload slicing beyond validation of `member_of` keys.
- Dataset influence materialization for graph members. That is RG2.

---

## File Structure

Create:

- `science/model/src/science_model/schemas/extension-bio-reference_graph-1.0.json`
  - Dataset extension schema for graph-shaped reference collections.
- `science/model/src/science_model/schemas/extension-bio-reference_graph-member-1.0.json`
  - Dataset extension schema for promoted graph members.
- `science/model/tests/test_bio_extension_reference_graph.py`
  - Schema-loader and entity-validation tests for both profiles.
- `science/src/science_tool/commons/reference_graph.py`
  - Pure row parser and constants. No filesystem, no commons adapter.
- `science/src/science_tool/commons/reference_graph_resources.py`
  - Datapackage resource lookup and CSV reading for graph/node/edge resources.
- `science/tests/test_commons_reference_graph.py`
  - Pure parser tests.
- `science/tests/validate/test_checks_reference_graphs.py`
  - Resource helper, pure validation, and registered check tests.
- `science/src/science_tool/validate/checks/reference_graphs.py`
  - `science validate` check for reference graph datasets.

Modify:

- `science/src/science_tool/validate/checks/__init__.py`
  - Register `reference_graphs` after `genesets` and before `dataset_influence`.
- `science/src/science_tool/validate/checks/dataset_influence.py`
  - Bump `dataset_influence` check order from 35 to 36 so `reference_graphs` can use a unique order 35.
- `science/tests/validate/test_runner.py`
  - Update the helper list of real canonical checks and add an ordering assertion.
- `docs/plans/2026-05-31-bio-reference-graph-design.md`
  - Mark RG1 implemented after code lands.
- `docs/plans/2026-05-26-bio-data-architecture-umbrella-design.md`
  - Update non-tabular-reference status after code lands.

---

## Task 1: Add Reference Graph Schemas

**Files:**
- Create: `science/model/src/science_model/schemas/extension-bio-reference_graph-1.0.json`
- Create: `science/model/src/science_model/schemas/extension-bio-reference_graph-member-1.0.json`
- Create: `science/model/tests/test_bio_extension_reference_graph.py`

- [ ] **Step 1: Write failing schema tests**

Create `science/model/tests/test_bio_extension_reference_graph.py`:

```python
from __future__ import annotations

import pytest

from science_model.entity_schema.loader import SchemaLoader
from science_model.entity_schema.profile import ProfileComponent
from science_model.entity_schema.validator import EntityValidationError, EntityValidator


def _base_collection(**extra: object) -> dict[str, object]:
    return {
        "schema_profile": "science-entity-base/1.0+dataset/1.0+bio.reference_graph/1.0",
        "id": "dataset:mondo",
        "type": "dataset",
        "title": "MONDO disease ontology reference graph",
        "version": "1.0.0",
        "created": "2026-05-31",
        "updated": "2026-05-31",
        "datapackage": "datapackage.yaml",
        "origin": "external",
        "tier": "use-now",
        "source_class": "reference",
        "access": {"level": "public", "verified": True},
        "graph_resource": "graph",
        "graph_format": "rdf_ntriples",
        "member_key_space": {
            "kind": "curie",
            "prefixes": ["MONDO"],
            "resolution_status": "resolved",
        },
        "node_index_resource": "nodes",
        "member_count": 2,
    } | extra


def _base_member(**extra: object) -> dict[str, object]:
    return {
        "schema_profile": "science-entity-base/1.0+dataset/1.0+bio.reference_graph.member/1.0",
        "id": "dataset:mondo-0005148",
        "type": "dataset",
        "title": "MONDO:0005148",
        "version": "1.0.0",
        "created": "2026-05-31",
        "updated": "2026-05-31",
        "datapackage": "virtual:member-of",
        "origin": "derived",
        "tier": "use-now",
        "source_class": "reference",
        "parent_dataset": "dataset:mondo",
        "derivation": {
            "kind": "member_of",
            "parent_dataset": "dataset:mondo",
            "member_key": "MONDO:0005148",
        },
        "member_kind": "term",
        "label": "multiple myeloma",
        "status": "active",
    } | extra


def test_loader_resolves_reference_graph_schema() -> None:
    schema = SchemaLoader().load(ProfileComponent(name="bio.reference_graph", version="1.0"))
    assert schema["$id"].endswith("extension-bio-reference_graph-1.0.json")


def test_loader_resolves_reference_graph_member_schema() -> None:
    schema = SchemaLoader().load(ProfileComponent(name="bio.reference_graph.member", version="1.0"))
    assert schema["$id"].endswith("extension-bio-reference_graph-member-1.0.json")


def test_minimal_reference_graph_collection_validates() -> None:
    EntityValidator().validate(_base_collection())


def test_reference_graph_requires_node_index_for_rg1() -> None:
    entity = _base_collection()
    del entity["node_index_resource"]
    with pytest.raises(EntityValidationError, match="node_index_resource"):
        EntityValidator().validate(entity)


def test_reference_graph_rejects_unknown_graph_format() -> None:
    with pytest.raises(EntityValidationError, match="graph_format"):
        EntityValidator().validate(_base_collection(graph_format="obo"))


def test_reference_graph_requires_non_empty_prefixes() -> None:
    entity = _base_collection(member_key_space={"kind": "curie", "prefixes": [], "resolution_status": "resolved"})
    with pytest.raises(EntityValidationError, match="prefixes"):
        EntityValidator().validate(entity)


def test_reference_graph_member_validates_without_scalar_member_key_duplicate() -> None:
    EntityValidator().validate(_base_member())


def test_reference_graph_member_rejects_top_level_member_key_duplicate() -> None:
    with pytest.raises(EntityValidationError, match="member_key"):
        EntityValidator().validate(_base_member(member_key="MONDO:0005148"))
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run --frozen pytest science/model/tests/test_bio_extension_reference_graph.py -q
```

Expected: FAIL with `SchemaNotFoundError` for `extension-bio-reference_graph-1.0.json`.

- [ ] **Step 3: Add `bio.reference_graph/1.0` schema**

Create `science/model/src/science_model/schemas/extension-bio-reference_graph-1.0.json`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://schemas.science/extension-bio-reference_graph-1.0.json",
  "title": "science entity bio.reference_graph extension",
  "type": "object",
  "required": [
    "graph_resource",
    "graph_format",
    "member_key_space",
    "node_index_resource",
    "member_count"
  ],
  "properties": {
    "graph_resource": {"type": "string", "minLength": 1},
    "graph_format": {"enum": ["rdf_turtle", "rdf_ntriples", "jsonl_edges"]},
    "member_key_space": {
      "type": "object",
      "required": ["kind", "prefixes", "resolution_status"],
      "properties": {
        "kind": {"enum": ["curie", "iri", "tuple"]},
        "prefixes": {
          "type": "array",
          "minItems": 1,
          "items": {"type": "string", "minLength": 1},
          "uniqueItems": true
        },
        "resolution_status": {"enum": ["resolved", "declared_unresolved"]}
      },
      "additionalProperties": false
    },
    "node_index_resource": {"type": "string", "minLength": 1},
    "edge_resource": {"type": "string", "minLength": 1},
    "member_count": {"type": "integer", "minimum": 1},
    "edge_count": {"type": "integer", "minimum": 0}
  },
  "additionalProperties": true
}
```

- [ ] **Step 4: Add `bio.reference_graph.member/1.0` schema**

Create `science/model/src/science_model/schemas/extension-bio-reference_graph-member-1.0.json`:

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "$id": "https://schemas.science/extension-bio-reference_graph-member-1.0.json",
  "title": "science entity bio.reference_graph.member extension",
  "type": "object",
  "required": ["member_kind", "label", "status"],
  "properties": {
    "member_kind": {"type": "string", "minLength": 1},
    "label": {"type": "string", "minLength": 1},
    "status": {"enum": ["active", "deprecated", "withdrawn"]},
    "replaced_by": {
      "type": "array",
      "items": {"type": "string", "minLength": 1},
      "uniqueItems": true
    }
  },
  "not": {"required": ["member_key"]},
  "additionalProperties": true
}
```

Rationale: `additionalProperties: true` matches existing bio extension style and lets the dataset mixin fields coexist in composed validation. The explicit `not` enforces the design rule that scalar member identity lives in `derivation.member_key`, not in the extension.

- [ ] **Step 5: Run schema tests**

Run:

```bash
uv run --frozen pytest science/model/tests/test_bio_extension_reference_graph.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

Run:

```bash
rtk git add science/model/src/science_model/schemas/extension-bio-reference_graph-1.0.json science/model/src/science_model/schemas/extension-bio-reference_graph-member-1.0.json science/model/tests/test_bio_extension_reference_graph.py
rtk git commit -m "feat(model): add bio reference graph schemas"
```

---

## Task 2: Add Pure Reference Graph Row Parser

**Files:**
- Create: `science/src/science_tool/commons/reference_graph.py`
- Create: `science/tests/test_commons_reference_graph.py`

- [ ] **Step 1: Write failing parser tests**

Create `science/tests/test_commons_reference_graph.py`:

```python
from __future__ import annotations

import pytest

from science_tool.commons.reference_graph import (
    REFERENCE_GRAPH_PROFILE_TOKEN,
    REFERENCE_GRAPH_REQUIRED_NODE_COLUMNS,
    ReferenceGraphCollectionError,
    parse_edge_rows,
    parse_node_index_rows,
)


def test_reference_graph_profile_token() -> None:
    assert REFERENCE_GRAPH_PROFILE_TOKEN == "+bio.reference_graph/"


def test_required_node_columns() -> None:
    assert REFERENCE_GRAPH_REQUIRED_NODE_COLUMNS == frozenset(
        {"member_key", "member_kind", "label", "status", "replaced_by", "dataset_usage"}
    )


def test_parse_valid_node_rows() -> None:
    rows = parse_node_index_rows(
        [
            {
                "member_key": "MONDO:0005148",
                "member_kind": "term",
                "label": "multiple myeloma",
                "status": "active",
                "replaced_by": "",
                "dataset_usage": '[{"ref":"dataset:ordo","role":"upstream","overlap":"partial"}]',
            },
            {
                "member_key": "MONDO:obsolete",
                "member_kind": "term",
                "label": "old label",
                "status": "deprecated",
                "replaced_by": "MONDO:0005148",
                "dataset_usage": "[]",
            },
        ]
    )

    assert rows[0].member_key == "MONDO:0005148"
    assert rows[0].member_kind == "term"
    assert rows[0].status == "active"
    assert rows[0].dataset_usage[0]["role"] == "upstream"
    assert rows[1].replaced_by == ("MONDO:0005148",)


def test_parse_node_rows_counts_deprecated_as_addressable() -> None:
    rows = parse_node_index_rows(
        [
            {
                "member_key": "MONDO:active",
                "member_kind": "term",
                "label": "active",
                "status": "active",
                "replaced_by": "",
                "dataset_usage": "[]",
            },
            {
                "member_key": "MONDO:deprecated",
                "member_kind": "term",
                "label": "deprecated",
                "status": "deprecated",
                "replaced_by": "MONDO:active",
                "dataset_usage": "[]",
            },
        ]
    )

    assert len(rows) == 2
    assert {row.member_key for row in rows} == {"MONDO:active", "MONDO:deprecated"}


def test_duplicate_member_key_errors() -> None:
    with pytest.raises(ReferenceGraphCollectionError, match="row 2: duplicate member_key"):
        parse_node_index_rows(
            [
                {
                    "member_key": "MONDO:1",
                    "member_kind": "term",
                    "label": "one",
                    "status": "active",
                    "replaced_by": "",
                    "dataset_usage": "[]",
                },
                {
                    "member_key": "MONDO:1",
                    "member_kind": "term",
                    "label": "again",
                    "status": "active",
                    "replaced_by": "",
                    "dataset_usage": "[]",
                },
            ]
        )


def test_missing_node_column_errors() -> None:
    with pytest.raises(ReferenceGraphCollectionError, match="missing required columns \\['dataset_usage'\\]"):
        parse_node_index_rows(
            [{"member_key": "MONDO:1", "member_kind": "term", "label": "one", "status": "active", "replaced_by": ""}]
        )


def test_invalid_status_errors() -> None:
    with pytest.raises(ReferenceGraphCollectionError, match="status"):
        parse_node_index_rows(
            [
                {
                    "member_key": "MONDO:1",
                    "member_kind": "term",
                    "label": "one",
                    "status": "obsolete",
                    "replaced_by": "",
                    "dataset_usage": "[]",
                }
            ]
        )


def test_replaced_by_rejects_empty_tokens() -> None:
    with pytest.raises(ReferenceGraphCollectionError, match="replaced_by contains an empty token"):
        parse_node_index_rows(
            [
                {
                    "member_key": "MONDO:1",
                    "member_kind": "term",
                    "label": "one",
                    "status": "deprecated",
                    "replaced_by": "MONDO:2;;MONDO:3",
                    "dataset_usage": "[]",
                }
            ]
        )


def test_dataset_usage_must_be_json_list() -> None:
    with pytest.raises(ReferenceGraphCollectionError, match="dataset_usage must be a JSON list"):
        parse_node_index_rows(
            [
                {
                    "member_key": "MONDO:1",
                    "member_kind": "term",
                    "label": "one",
                    "status": "active",
                    "replaced_by": "",
                    "dataset_usage": '{"ref":"dataset:x"}',
                }
            ]
        )


def test_dataset_usage_rejects_invalid_role() -> None:
    with pytest.raises(ReferenceGraphCollectionError, match="role"):
        parse_node_index_rows(
            [
                {
                    "member_key": "MONDO:1",
                    "member_kind": "term",
                    "label": "one",
                    "status": "active",
                    "replaced_by": "",
                    "dataset_usage": '[{"ref":"dataset:x","role":"made_up"}]',
                }
            ]
        )


def test_parse_valid_edge_rows() -> None:
    rows = parse_edge_rows(
        [
            {
                "subject": "MONDO:0005148",
                "predicate": "is_a",
                "object": "MONDO:0000001",
                "evidence": "",
                "dataset_usage": '[{"ref":"dataset:ordo","role":"upstream"}]',
            }
        ]
    )

    assert rows[0].subject == "MONDO:0005148"
    assert rows[0].predicate == "is_a"
    assert rows[0].object == "MONDO:0000001"
    assert rows[0].dataset_usage[0]["ref"] == "dataset:ordo"


def test_edge_rows_reject_missing_required_columns() -> None:
    with pytest.raises(ReferenceGraphCollectionError, match="missing required columns \\['object'\\]"):
        parse_edge_rows([{"subject": "A", "predicate": "is_a", "evidence": "", "dataset_usage": "[]"}])


def test_edge_rows_allow_blank_optional_dataset_usage() -> None:
    rows = parse_edge_rows(
        [{"subject": "A", "predicate": "is_a", "object": "B", "evidence": "", "dataset_usage": ""}]
    )

    assert rows[0].dataset_usage == ()
```

- [ ] **Step 2: Run parser tests to verify they fail**

Run:

```bash
uv run --frozen pytest science/tests/test_commons_reference_graph.py -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'science_tool.commons.reference_graph'`.

- [ ] **Step 3: Implement parser module**

Create `science/src/science_tool/commons/reference_graph.py`:

```python
"""RG1 parser for bio.reference_graph node and edge projections."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, get_args

from science_model.packages.schema import DatasetUsage

REFERENCE_GRAPH_PROFILE_TOKEN = "+bio.reference_graph/"
REFERENCE_GRAPH_MEMBER_PROFILE_TOKEN = "+bio.reference_graph.member/"
REFERENCE_GRAPH_REQUIRED_NODE_COLUMNS = frozenset(
    {"member_key", "member_kind", "label", "status", "replaced_by", "dataset_usage"}
)
REFERENCE_GRAPH_REQUIRED_EDGE_COLUMNS = frozenset({"subject", "predicate", "object"})
REFERENCE_GRAPH_STATUSES = frozenset({"active", "deprecated", "withdrawn"})
REFERENCE_GRAPH_FORMATS = frozenset({"rdf_turtle", "rdf_ntriples", "jsonl_edges"})
REFERENCE_GRAPH_USAGE_ROLES = frozenset(get_args(DatasetUsage.model_fields["role"].annotation))
REFERENCE_GRAPH_USAGE_OVERLAPS = frozenset(get_args(DatasetUsage.model_fields["overlap"].annotation))


class ReferenceGraphCollectionError(ValueError):
    """A bio.reference_graph projection row violates the RG1 row contract."""


@dataclass(frozen=True, slots=True)
class ReferenceGraphNode:
    member_key: str
    member_kind: str
    label: str
    status: str
    replaced_by: tuple[str, ...]
    dataset_usage: tuple[dict[str, Any], ...]


@dataclass(frozen=True, slots=True)
class ReferenceGraphEdge:
    subject: str
    predicate: str
    object: str
    evidence: str | None
    dataset_usage: tuple[dict[str, Any], ...]


def is_reference_graph_frontmatter(fm: dict[str, Any]) -> bool:
    profile = str(fm.get("schema_profile") or "")
    return (fm.get("kind") or fm.get("type")) == "dataset" and REFERENCE_GRAPH_PROFILE_TOKEN in f"+{profile}"


def is_reference_graph_member_frontmatter(fm: dict[str, Any]) -> bool:
    profile = str(fm.get("schema_profile") or "")
    return (fm.get("kind") or fm.get("type")) == "dataset" and REFERENCE_GRAPH_MEMBER_PROFILE_TOKEN in f"+{profile}"


def _split_semicolon(raw: str, *, field: str, row_number: int) -> tuple[str, ...]:
    text = raw.strip()
    if not text:
        return ()
    parts = tuple(part.strip() for part in raw.split(";"))
    if any(not part for part in parts):
        raise ReferenceGraphCollectionError(f"row {row_number}: {field} contains an empty token")
    return parts


def _dataset_usage_defect(entry: Any) -> str | None:
    if not isinstance(entry, dict):
        return "entry is not an object"
    ref = entry.get("ref")
    if not isinstance(ref, str) or not ref.startswith("dataset:"):
        return "ref must be a 'dataset:' reference"
    role = entry.get("role")
    if role not in REFERENCE_GRAPH_USAGE_ROLES:
        return f"role must be one of {sorted(REFERENCE_GRAPH_USAGE_ROLES)}"
    if "overlap" in entry and entry["overlap"] not in REFERENCE_GRAPH_USAGE_OVERLAPS:
        return f"overlap must be one of {sorted(REFERENCE_GRAPH_USAGE_OVERLAPS)}"
    return None


def _parse_dataset_usage(raw: str, *, row_number: int) -> tuple[dict[str, Any], ...]:
    text = raw.strip()
    if not text:
        return ()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ReferenceGraphCollectionError(
            f"row {row_number}: dataset_usage is not valid JSON: {exc.msg}"
        ) from exc
    if not isinstance(parsed, list):
        raise ReferenceGraphCollectionError(f"row {row_number}: dataset_usage must be a JSON list")
    out: list[dict[str, Any]] = []
    for index, entry in enumerate(parsed):
        defect = _dataset_usage_defect(entry)
        if defect is not None:
            raise ReferenceGraphCollectionError(f"row {row_number}: dataset_usage[{index}] malformed -- {defect}")
        out.append(entry)
    return tuple(out)


def parse_node_index_rows(rows: list[dict[str, Any]]) -> list[ReferenceGraphNode]:
    out: list[ReferenceGraphNode] = []
    seen: set[str] = set()
    for row_number, row in enumerate(rows, start=1):
        missing = [col for col in sorted(REFERENCE_GRAPH_REQUIRED_NODE_COLUMNS) if col not in row]
        if missing:
            raise ReferenceGraphCollectionError(f"row {row_number}: missing required columns {missing}")
        member_key = str(row.get("member_key") or "").strip()
        if not member_key:
            raise ReferenceGraphCollectionError(f"row {row_number}: blank member_key")
        if member_key in seen:
            raise ReferenceGraphCollectionError(f"row {row_number}: duplicate member_key {member_key!r}")
        seen.add(member_key)
        member_kind = str(row.get("member_kind") or "").strip()
        if not member_kind:
            raise ReferenceGraphCollectionError(f"row {row_number}: blank member_kind")
        label = str(row.get("label") or "").strip()
        if not label:
            raise ReferenceGraphCollectionError(f"row {row_number}: blank label")
        status = str(row.get("status") or "").strip()
        if status not in REFERENCE_GRAPH_STATUSES:
            raise ReferenceGraphCollectionError(
                f"row {row_number}: status must be one of {sorted(REFERENCE_GRAPH_STATUSES)}"
            )
        out.append(
            ReferenceGraphNode(
                member_key=member_key,
                member_kind=member_kind,
                label=label,
                status=status,
                replaced_by=_split_semicolon(str(row.get("replaced_by") or ""), field="replaced_by", row_number=row_number),
                dataset_usage=_parse_dataset_usage(str(row.get("dataset_usage") or ""), row_number=row_number),
            )
        )
    return out


def parse_edge_rows(rows: list[dict[str, Any]]) -> list[ReferenceGraphEdge]:
    out: list[ReferenceGraphEdge] = []
    for row_number, row in enumerate(rows, start=1):
        missing = [col for col in sorted(REFERENCE_GRAPH_REQUIRED_EDGE_COLUMNS) if col not in row]
        if missing:
            raise ReferenceGraphCollectionError(f"row {row_number}: missing required columns {missing}")
        subject = str(row.get("subject") or "").strip()
        predicate = str(row.get("predicate") or "").strip()
        object_ = str(row.get("object") or "").strip()
        if not subject:
            raise ReferenceGraphCollectionError(f"row {row_number}: blank subject")
        if not predicate:
            raise ReferenceGraphCollectionError(f"row {row_number}: blank predicate")
        if not object_:
            raise ReferenceGraphCollectionError(f"row {row_number}: blank object")
        evidence = str(row["evidence"]).strip() if row.get("evidence") not in (None, "") else None
        out.append(
            ReferenceGraphEdge(
                subject=subject,
                predicate=predicate,
                object=object_,
                evidence=evidence,
                dataset_usage=_parse_dataset_usage(str(row.get("dataset_usage") or ""), row_number=row_number),
            )
        )
    return out
```

- [ ] **Step 4: Run parser tests**

Run:

```bash
uv run --frozen pytest science/tests/test_commons_reference_graph.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

Run:

```bash
rtk git add science/src/science_tool/commons/reference_graph.py science/tests/test_commons_reference_graph.py
rtk git commit -m "feat(commons): parse reference graph projections"
```

---

## Task 3: Add Reference Graph Resource Helpers

**Files:**
- Create: `science/src/science_tool/commons/reference_graph_resources.py`
- Modify: `science/tests/validate/test_checks_reference_graphs.py`

- [ ] **Step 1: Write failing resource-helper tests**

Create `science/tests/validate/test_checks_reference_graphs.py` with the imports/helpers and first resource tests:

```python
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
import yaml

from science_tool.commons.reference_graph_resources import graph_resource_available, read_edge_rows, read_node_rows
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Result, Severity


_MANIFEST = (
    "name: demo\ncreated: 2026-01-01\nlast_modified: 2026-01-02\nstatus: active\n"
    "summary: demo\nprofile: research\nlayout_version: 1\n"
    "knowledge_profiles:\n  local: knowledge/local\n"
)


def _write_project(root: Path) -> None:
    (root / "science.yaml").write_text(_MANIFEST, encoding="utf-8")
    (root / "knowledge" / "local").mkdir(parents=True)


def _ctx(root: Path) -> ValidateContext:
    return ValidateContext.from_project_root(root, strict=False, verbose=False)


def _reference_graph(**extra: object) -> dict[str, object]:
    return {
        "id": "dataset:mondo",
        "type": "dataset",
        "schema_profile": "science-entity-base/1.0+dataset/1.0+bio.reference_graph/1.0",
        "_path": "data/mondo/datapackage.yaml",
        "source_class": "reference",
        "graph_resource": "graph",
        "graph_format": "rdf_ntriples",
        "member_key_space": {"kind": "curie", "prefixes": ["MONDO"], "resolution_status": "resolved"},
        "node_index_resource": "nodes",
        "edge_resource": "edges",
        "member_count": 2,
        "edge_count": 1,
        **extra,
    }


def _node(**extra: object) -> dict[str, object]:
    return {
        "member_key": "MONDO:0005148",
        "member_kind": "term",
        "label": "multiple myeloma",
        "status": "active",
        "replaced_by": "",
        "dataset_usage": "[]",
        **extra,
    }


def _rules(results: list[Result]) -> list[str]:
    return [r.rule for r in results]


def _write_reference_graph_datapackage(
    root: Path,
    *,
    graph_path: str = "graph.nt",
    nodes_path: str = "nodes.csv",
    edges_path: str | None = "edges.csv",
) -> Path:
    dp_dir = root / "data" / "mondo"
    dp_dir.mkdir(parents=True)
    resources: list[dict[str, str]] = [
        {"name": "graph", "path": graph_path},
        {"name": "nodes", "path": nodes_path},
    ]
    if edges_path is not None:
        resources.append({"name": "edges", "path": edges_path})
    dp_dir.joinpath("datapackage.yaml").write_text(
        yaml.safe_dump(
            {
                "profiles": ["science-pkg-entity-1.0"],
                "id": "dataset:mondo",
                "type": "dataset",
                "title": "MONDO",
                "status": "active",
                "origin": "external",
                "tier": "use-now",
                "schema_profile": "science-entity-base/1.0+dataset/1.0+bio.reference_graph/1.0",
                "source_class": "reference",
                "access": {"level": "public", "verified": True},
                "graph_resource": "graph",
                "graph_format": "rdf_ntriples",
                "member_key_space": {"kind": "curie", "prefixes": ["MONDO"], "resolution_status": "resolved"},
                "node_index_resource": "nodes",
                "edge_resource": "edges" if edges_path is not None else None,
                "member_count": 2,
                "edge_count": 1,
                "resources": resources,
            }
        ),
        encoding="utf-8",
    )
    return dp_dir


def test_reference_graph_resource_helper_reads_local_rows_and_checks_graph_availability(tmp_path: Path) -> None:
    _write_project(tmp_path)
    dp_dir = _write_reference_graph_datapackage(tmp_path)
    dp_dir.joinpath("graph.nt").write_text("<MONDO:0005148> <is_a> <MONDO:0000001> .\n", encoding="utf-8")
    dp_dir.joinpath("nodes.csv").write_text(
        "member_key,member_kind,label,status,replaced_by,dataset_usage\n"
        "MONDO:0005148,term,multiple myeloma,active,,[]\n",
        encoding="utf-8",
    )
    dp_dir.joinpath("edges.csv").write_text(
        "subject,predicate,object,evidence,dataset_usage\nMONDO:0005148,is_a,MONDO:0000001,,[]\n",
        encoding="utf-8",
    )
    fm = _reference_graph(_path="data/mondo/datapackage.yaml")

    assert graph_resource_available(tmp_path, fm) is True
    assert read_node_rows(tmp_path, fm) == [
        {
            "member_key": "MONDO:0005148",
            "member_kind": "term",
            "label": "multiple myeloma",
            "status": "active",
            "replaced_by": "",
            "dataset_usage": "[]",
        }
    ]
    assert read_edge_rows(tmp_path, fm) == [
        {"subject": "MONDO:0005148", "predicate": "is_a", "object": "MONDO:0000001", "evidence": "", "dataset_usage": "[]"}
    ]


def test_reference_graph_resource_helper_rejects_unsafe_resource_path(tmp_path: Path) -> None:
    _write_project(tmp_path)
    _write_reference_graph_datapackage(tmp_path, nodes_path="../outside.csv")

    rows = read_node_rows(tmp_path, _reference_graph(_path="data/mondo/datapackage.yaml"))

    assert isinstance(rows, Exception)
    assert "unsafe" in str(rows).lower() or "outside" in str(rows).lower()


def test_reference_graph_resource_helper_missing_optional_edge_resource_returns_none(tmp_path: Path) -> None:
    _write_project(tmp_path)
    dp_dir = _write_reference_graph_datapackage(tmp_path, edges_path=None)
    dp_dir.joinpath("graph.nt").write_text("<A> <p> <B> .\n", encoding="utf-8")
    dp_dir.joinpath("nodes.csv").write_text(
        "member_key,member_kind,label,status,replaced_by,dataset_usage\nA,term,A,active,,[]\n",
        encoding="utf-8",
    )

    fm = _reference_graph(_path="data/mondo/datapackage.yaml")
    fm.pop("edge_resource")

    assert read_edge_rows(tmp_path, fm) is None
```

- [ ] **Step 2: Run resource-helper tests to verify they fail**

Run:

```bash
uv run --frozen pytest science/tests/validate/test_checks_reference_graphs.py::test_reference_graph_resource_helper_reads_local_rows_and_checks_graph_availability -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'science_tool.commons.reference_graph_resources'`.

- [ ] **Step 3: Implement resource helper**

Create `science/src/science_tool/commons/reference_graph_resources.py`:

```python
"""Resource helpers for bio.reference_graph graph/index/edge artifacts."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Literal

import yaml

from science_tool.commons.datapackage import validate_logical_path
from science_tool.commons.errors import (
    CommonsEntityError,
    CommonsError,
    CommonsRootNotFoundError,
    DataResourceNotFoundError,
)
from science_tool.commons.frontmatter import raw_frontmatter
from science_tool.commons.reference_graph import is_reference_graph_frontmatter
from science_tool.commons.resolver import resolve

ResourceKind = Literal["graph", "node", "edge"]

_RESOURCE_FIELD_BY_KIND: dict[ResourceKind, str] = {
    "graph": "graph_resource",
    "node": "node_index_resource",
    "edge": "edge_resource",
}


def reference_graph_resource_frontmatter(project_root: Path, entity_path: str | Path) -> dict[str, Any] | None:
    path = Path(entity_path)
    source_path = path if path.is_absolute() else project_root / path
    fm = raw_frontmatter(source_path)
    if not is_reference_graph_frontmatter(fm):
        return None
    if source_path.name == "entity.md":
        fm["_path"] = str(source_path.parent / "datapackage.yaml")
    else:
        fm["_path"] = str(path)
    return fm


def resource_path_for_reference_graph(
    project_root: Path,
    fm: dict[str, Any],
    *,
    kind: ResourceKind,
) -> Path | Exception | None:
    rel = fm.get("_path")
    resource_name = fm.get(_RESOURCE_FIELD_BY_KIND[kind])
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
        if resource.get("name") != resource_name:
            continue
        resource_path = resource.get("path")
        if not isinstance(resource_path, str):
            return None
        try:
            logical_path = validate_logical_path(resource_path)
        except CommonsError as exc:
            return exc
        return dp_path.parent / logical_path
    return None


def _read_csv(path: Path) -> list[dict[str, Any]] | Exception:
    try:
        with path.open(encoding="utf-8", newline="") as fh:
            return list(csv.DictReader(fh))
    except (OSError, UnicodeError, csv.Error) as exc:
        return exc


def _resolve_commons_resource_path(fm: dict[str, Any], *, kind: ResourceKind) -> Path | Exception | None:
    dataset_id = fm.get("id")
    resource_name = fm.get(_RESOURCE_FIELD_BY_KIND[kind])
    if not isinstance(dataset_id, str) or not isinstance(resource_name, str):
        return None
    try:
        return resolve(dataset_id, resource_name).path
    except (CommonsRootNotFoundError, CommonsEntityError, DataResourceNotFoundError):
        return None
    except CommonsError as exc:
        return exc


def _resource_path(project_root: Path, fm: dict[str, Any], *, kind: ResourceKind) -> Path | Exception | None:
    path = resource_path_for_reference_graph(project_root, fm, kind=kind)
    if isinstance(path, Exception):
        return path
    if path is not None and path.is_file():
        return path
    commons_path = _resolve_commons_resource_path(fm, kind=kind)
    if isinstance(commons_path, Exception):
        return commons_path
    if commons_path is None:
        return None
    return commons_path


def graph_resource_available(project_root: Path, fm: dict[str, Any]) -> bool | Exception | None:
    path = _resource_path(project_root, fm, kind="graph")
    if isinstance(path, Exception) or path is None:
        return path
    return path.is_file()


def read_node_rows(project_root: Path, fm: dict[str, Any]) -> list[dict[str, Any]] | Exception | None:
    path = _resource_path(project_root, fm, kind="node")
    if isinstance(path, Exception) or path is None:
        return path
    return _read_csv(path)


def read_edge_rows(project_root: Path, fm: dict[str, Any]) -> list[dict[str, Any]] | Exception | None:
    path = _resource_path(project_root, fm, kind="edge")
    if isinstance(path, Exception) or path is None:
        return path
    return _read_csv(path)
```

- [ ] **Step 4: Run resource-helper tests**

Run:

```bash
uv run --frozen pytest science/tests/validate/test_checks_reference_graphs.py -q
```

Expected now: PASS for the three resource-helper tests. If the file also contains later tests added by subsequent tasks, run only the resource-helper tests:

```bash
uv run --frozen pytest \
  science/tests/validate/test_checks_reference_graphs.py::test_reference_graph_resource_helper_reads_local_rows_and_checks_graph_availability \
  science/tests/validate/test_checks_reference_graphs.py::test_reference_graph_resource_helper_rejects_unsafe_resource_path \
  science/tests/validate/test_checks_reference_graphs.py::test_reference_graph_resource_helper_missing_optional_edge_resource_returns_none \
  -q
```

- [ ] **Step 5: Commit**

Run:

```bash
rtk git add science/src/science_tool/commons/reference_graph_resources.py science/tests/validate/test_checks_reference_graphs.py
rtk git commit -m "feat(commons): read reference graph resources"
```

---

## Task 4: Add Pure Reference Graph Validation Core

**Files:**
- Create: `science/src/science_tool/validate/checks/reference_graphs.py`
- Modify: `science/tests/validate/test_checks_reference_graphs.py`

- [ ] **Step 1: Add failing pure validation tests**

Append to `science/tests/validate/test_checks_reference_graphs.py`:

```python
from science_tool.validate.checks.reference_graphs import evaluate_reference_graphs


def test_valid_reference_graph_passes_silently() -> None:
    results = list(
        evaluate_reference_graphs(
            [_reference_graph()],
            graph_available_by_dataset_id={"dataset:mondo": True},
            node_rows_by_dataset_id={"dataset:mondo": [_node(), _node(member_key="MONDO:obsolete", status="deprecated")]},
            edge_rows_by_dataset_id={
                "dataset:mondo": [
                    {"subject": "MONDO:0005148", "predicate": "is_a", "object": "MONDO:0000001", "evidence": "", "dataset_usage": "[]"}
                ]
            },
            member_datasets=[],
        )
    )

    assert results == []


def test_malformed_reference_graph_collection_errors() -> None:
    fm = _reference_graph(graph_format="obo")

    results = list(
        evaluate_reference_graphs(
            [fm],
            graph_available_by_dataset_id={"dataset:mondo": True},
            node_rows_by_dataset_id={"dataset:mondo": [_node()]},
            edge_rows_by_dataset_id={},
            member_datasets=[],
        )
    )

    assert _rules(results) == ["reference-graph.collection-malformed"]
    assert results[0].severity is Severity.ERROR


def test_missing_graph_resource_does_not_suppress_node_validation() -> None:
    results = list(
        evaluate_reference_graphs(
            [_reference_graph()],
            graph_available_by_dataset_id={"dataset:mondo": None},
            node_rows_by_dataset_id={"dataset:mondo": [_node()]},
            edge_rows_by_dataset_id={},
            member_datasets=[],
        )
    )

    assert _rules(results) == [
        "reference-graph.graph-resource-unavailable",
        "reference-graph.member-count-mismatch",
    ]
    assert results[0].severity is Severity.INFO


def test_missing_node_index_is_info_not_silent() -> None:
    results = list(
        evaluate_reference_graphs(
            [_reference_graph()],
            graph_available_by_dataset_id={"dataset:mondo": True},
            node_rows_by_dataset_id={},
            edge_rows_by_dataset_id={},
            member_datasets=[],
        )
    )

    assert _rules(results) == ["reference-graph.node-index-unavailable"]
    assert results[0].severity is Severity.INFO


def test_node_index_malformed_errors() -> None:
    results = list(
        evaluate_reference_graphs(
            [_reference_graph()],
            graph_available_by_dataset_id={"dataset:mondo": True},
            node_rows_by_dataset_id={"dataset:mondo": [_node(status="obsolete")]},
            edge_rows_by_dataset_id={},
            member_datasets=[],
        )
    )

    assert _rules(results) == ["reference-graph.node-index-malformed"]
    assert results[0].severity is Severity.ERROR


def test_member_count_counts_deprecated_rows() -> None:
    results = list(
        evaluate_reference_graphs(
            [_reference_graph(member_count=1)],
            graph_available_by_dataset_id={"dataset:mondo": True},
            node_rows_by_dataset_id={"dataset:mondo": [_node(), _node(member_key="MONDO:obsolete", status="deprecated")]},
            edge_rows_by_dataset_id={},
            member_datasets=[],
        )
    )

    assert _rules(results) == ["reference-graph.member-count-mismatch"]
    assert "has 2 node rows" in results[0].message


def test_edge_count_mismatch_errors_when_edge_resource_declared() -> None:
    results = list(
        evaluate_reference_graphs(
            [_reference_graph(edge_count=2)],
            graph_available_by_dataset_id={"dataset:mondo": True},
            node_rows_by_dataset_id={"dataset:mondo": [_node(), _node(member_key="MONDO:obsolete", status="deprecated")]},
            edge_rows_by_dataset_id={
                "dataset:mondo": [
                    {"subject": "MONDO:0005148", "predicate": "is_a", "object": "MONDO:0000001", "evidence": "", "dataset_usage": "[]"}
                ]
            },
            member_datasets=[],
        )
    )

    assert _rules(results) == ["reference-graph.edge-count-mismatch"]


def test_jsonl_edges_format_is_enum_validated_without_distinct_edge_resource() -> None:
    fm = _reference_graph(graph_format="jsonl_edges", edge_resource=None, edge_count=None)
    fm.pop("edge_resource")
    fm.pop("edge_count")
    results = list(
        evaluate_reference_graphs(
            [fm],
            graph_available_by_dataset_id={"dataset:mondo": True},
            node_rows_by_dataset_id={"dataset:mondo": [_node(), _node(member_key="MONDO:obsolete", status="deprecated")]},
            edge_rows_by_dataset_id={},
            member_datasets=[],
        )
    )

    assert results == []


def test_deprecated_promoted_member_warns_with_replaced_by() -> None:
    member = {
        "id": "dataset:mondo-obsolete",
        "type": "dataset",
        "schema_profile": "science-entity-base/1.0+dataset/1.0+bio.reference_graph.member/1.0",
        "_path": "data/mondo-obsolete/entity.md",
        "derivation": {"kind": "member_of", "parent_dataset": "dataset:mondo", "member_key": "MONDO:obsolete"},
        "member_kind": "term",
        "label": "old label",
        "status": "deprecated",
    }
    results = list(
        evaluate_reference_graphs(
            [_reference_graph()],
            graph_available_by_dataset_id={"dataset:mondo": True},
            node_rows_by_dataset_id={
                "dataset:mondo": [
                    _node(),
                    _node(member_key="MONDO:obsolete", status="deprecated", replaced_by="MONDO:0005148"),
                ]
            },
            edge_rows_by_dataset_id={},
            member_datasets=[member],
        )
    )

    assert _rules(results) == ["reference-graph.member-deprecated"]
    assert results[0].severity is Severity.WARN
    assert "MONDO:0005148" in results[0].message


def test_unresolved_promoted_member_errors() -> None:
    member = {
        "id": "dataset:missing",
        "type": "dataset",
        "schema_profile": "science-entity-base/1.0+dataset/1.0+bio.reference_graph.member/1.0",
        "_path": "data/missing/entity.md",
        "derivation": {"kind": "member_of", "parent_dataset": "dataset:mondo", "member_key": "MONDO:missing"},
        "member_kind": "term",
        "label": "missing",
        "status": "active",
    }
    results = list(
        evaluate_reference_graphs(
            [_reference_graph()],
            graph_available_by_dataset_id={"dataset:mondo": True},
            node_rows_by_dataset_id={"dataset:mondo": [_node(), _node(member_key="MONDO:obsolete", status="deprecated")]},
            edge_rows_by_dataset_id={},
            member_datasets=[member],
        )
    )

    assert _rules(results) == ["reference-graph.member-unresolved"]
    assert results[0].severity is Severity.ERROR
```

- [ ] **Step 2: Run pure validation tests to verify they fail**

Run:

```bash
uv run --frozen pytest science/tests/validate/test_checks_reference_graphs.py::test_valid_reference_graph_passes_silently -q
```

Expected: FAIL with `ModuleNotFoundError` or missing `evaluate_reference_graphs`.

- [ ] **Step 3: Implement pure validation core**

Create `science/src/science_tool/validate/checks/reference_graphs.py`:

```python
"""Reference graph collection checks (RG1)."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any

from science_tool.commons.member import evaluate_key_resolution, parse_member_of, ResolutionState
from science_tool.commons.reference_graph import (
    REFERENCE_GRAPH_FORMATS,
    REFERENCE_GRAPH_MEMBER_PROFILE_TOKEN,
    ReferenceGraphCollectionError,
    ReferenceGraphNode,
    is_reference_graph_frontmatter,
    is_reference_graph_member_frontmatter,
    parse_edge_rows,
    parse_node_index_rows,
)
from science_tool.validate.checks import Check
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Result, Severity


def _result(severity: Severity, path: str | None, message: str, rule: str) -> Result:
    return Result(severity, Path(path) if path else None, None, message, rule, None)


def _is_int(value: object) -> bool:
    return type(value) is int


def _collection_defect(fm: dict[str, Any]) -> str | None:
    graph_resource = fm.get("graph_resource")
    if not isinstance(graph_resource, str) or not graph_resource.strip():
        return "graph_resource must name a Frictionless resource"
    graph_format = fm.get("graph_format")
    if graph_format not in REFERENCE_GRAPH_FORMATS:
        return f"graph_format must be one of {sorted(REFERENCE_GRAPH_FORMATS)}"
    member_key_space = fm.get("member_key_space")
    if not isinstance(member_key_space, dict):
        return "member_key_space must be an object"
    kind = member_key_space.get("kind")
    if kind not in ("curie", "iri", "tuple"):
        return "member_key_space.kind must be curie|iri|tuple"
    prefixes = member_key_space.get("prefixes")
    if not isinstance(prefixes, list) or not prefixes or any(not isinstance(item, str) or not item for item in prefixes):
        return "member_key_space.prefixes must be a non-empty list of strings"
    status = member_key_space.get("resolution_status")
    if status not in ("resolved", "declared_unresolved"):
        return "member_key_space.resolution_status must be resolved|declared_unresolved"
    node_resource = fm.get("node_index_resource")
    if not isinstance(node_resource, str) or not node_resource.strip():
        return "node_index_resource must name a Frictionless resource"
    edge_resource = fm.get("edge_resource")
    if edge_resource is not None and (not isinstance(edge_resource, str) or not edge_resource.strip()):
        return "edge_resource must name a Frictionless resource when declared"
    member_count = fm.get("member_count")
    if not _is_int(member_count) or member_count < 1:
        return "member_count must be a positive integer"
    edge_count = fm.get("edge_count")
    if edge_count is not None and (not _is_int(edge_count) or edge_count < 0):
        return "edge_count must be a non-negative integer"
    return None


def _node_by_key(nodes: list[ReferenceGraphNode]) -> dict[str, ReferenceGraphNode]:
    return {node.member_key: node for node in nodes}


def _reference_graph_member_profile(fm: dict[str, Any]) -> bool:
    profile = str(fm.get("schema_profile") or "")
    return REFERENCE_GRAPH_MEMBER_PROFILE_TOKEN in f"+{profile}"


def evaluate_reference_graphs(
    datasets: Iterable[dict[str, Any]],
    *,
    graph_available_by_dataset_id: dict[str, bool | Exception | None],
    node_rows_by_dataset_id: dict[str, list[dict[str, Any]] | Exception | None],
    edge_rows_by_dataset_id: dict[str, list[dict[str, Any]] | Exception | None],
    member_datasets: Iterable[dict[str, Any]],
) -> Iterator[Result]:
    collections = [fm for fm in datasets if is_reference_graph_frontmatter(fm)]
    nodes_by_collection: dict[str, dict[str, ReferenceGraphNode]] = {}

    for fm in collections:
        ident = str(fm.get("id") or "?")
        path = fm.get("_path")
        defect = _collection_defect(fm)
        if defect is not None:
            yield _result(
                Severity.ERROR,
                path,
                f"{ident}: malformed bio.reference_graph collection -- {defect}",
                "reference-graph.collection-malformed",
            )
            continue
        graph_available = graph_available_by_dataset_id.get(ident)
        if graph_available is None or graph_available is False:
            yield _result(
                Severity.INFO,
                path,
                f"{ident}: graph_resource is unavailable; graph artifact cannot be verified",
                "reference-graph.graph-resource-unavailable",
            )
        elif isinstance(graph_available, Exception):
            yield _result(
                Severity.ERROR,
                path,
                f"{ident}: graph_resource malformed -- {graph_available}",
                "reference-graph.graph-resource-malformed",
            )
        raw_nodes = node_rows_by_dataset_id.get(ident)
        if raw_nodes is None:
            yield _result(
                Severity.INFO,
                path,
                f"{ident}: node_index_resource is unavailable; member resolution cannot be verified",
                "reference-graph.node-index-unavailable",
            )
            continue
        if isinstance(raw_nodes, Exception):
            yield _result(
                Severity.ERROR,
                path,
                f"{ident}: node_index_resource malformed -- {raw_nodes}",
                "reference-graph.node-index-malformed",
            )
            continue
        try:
            nodes = parse_node_index_rows(raw_nodes)
        except ReferenceGraphCollectionError as exc:
            yield _result(
                Severity.ERROR,
                path,
                f"{ident}: node_index_resource malformed -- {exc}",
                "reference-graph.node-index-malformed",
            )
            continue
        if len(nodes) != fm["member_count"]:
            yield _result(
                Severity.ERROR,
                path,
                f"{ident}: member_count={fm['member_count']} but node_index_resource has {len(nodes)} node rows",
                "reference-graph.member-count-mismatch",
            )
            continue
        nodes_by_collection[ident] = _node_by_key(nodes)
        raw_edges = edge_rows_by_dataset_id.get(ident)
        if raw_edges is None:
            if fm.get("edge_resource") is not None:
                yield _result(
                    Severity.INFO,
                    path,
                    f"{ident}: edge_resource is unavailable; edge count cannot be verified",
                    "reference-graph.edge-resource-unavailable",
                )
            continue
        if isinstance(raw_edges, Exception):
            yield _result(
                Severity.ERROR,
                path,
                f"{ident}: edge_resource malformed -- {raw_edges}",
                "reference-graph.edge-resource-malformed",
            )
            continue
        try:
            edges = parse_edge_rows(raw_edges)
        except ReferenceGraphCollectionError as exc:
            yield _result(
                Severity.ERROR,
                path,
                f"{ident}: edge_resource malformed -- {exc}",
                "reference-graph.edge-resource-malformed",
            )
            continue
        if fm.get("edge_count") is not None and len(edges) != fm["edge_count"]:
            yield _result(
                Severity.ERROR,
                path,
                f"{ident}: edge_count={fm['edge_count']} but edge_resource has {len(edges)} rows",
                "reference-graph.edge-count-mismatch",
            )

    for member in member_datasets:
        if not is_reference_graph_member_frontmatter(member):
            continue
        member_id = str(member.get("id") or "?")
        path = member.get("_path")
        member_of = parse_member_of(member)
        if member_of is None:
            yield _result(
                Severity.ERROR,
                path,
                f"{member_id}: bio.reference_graph.member must use derivation.kind=member_of",
                "reference-graph.member-not-member-of",
            )
            continue
        available_nodes = nodes_by_collection.get(member_of.parent_dataset)
        state = evaluate_key_resolution(
            key=member_of.member_key,
            available_keys=set(available_nodes) if available_nodes is not None else None,
            declared_status=None,
        )
        if state is ResolutionState.UNKNOWN:
            yield _result(
                Severity.INFO,
                path,
                f"{member_id}: parent reference graph {member_of.parent_dataset!r} unavailable; member resolution cannot be verified",
                "reference-graph.member-resolution-unknown",
            )
            continue
        if state is ResolutionState.UNRESOLVED:
            yield _result(
                Severity.ERROR,
                path,
                f"{member_id}: member_key {member_of.member_key!r} is absent from {member_of.parent_dataset}",
                "reference-graph.member-unresolved",
            )
            continue
        node = available_nodes[member_of.member_key]
        if node.status in {"deprecated", "withdrawn"}:
            replacement = f"; replaced_by={';'.join(node.replaced_by)}" if node.replaced_by else ""
            yield _result(
                Severity.WARN,
                path,
                f"{member_id}: member_key {member_of.member_key!r} is {node.status}{replacement}",
                "reference-graph.member-deprecated",
            )
```

The `@Check` wrapper and filesystem loading come in Task 5.

- [ ] **Step 4: Run pure validation tests**

Run:

```bash
uv run --frozen pytest science/tests/validate/test_checks_reference_graphs.py -q
```

Expected: PASS for tests currently in the file.

- [ ] **Step 5: Commit**

Run:

```bash
rtk git add science/src/science_tool/validate/checks/reference_graphs.py science/tests/validate/test_checks_reference_graphs.py
rtk git commit -m "feat(validate): evaluate reference graph collections"
```

---

## Task 5: Register `science validate` Reference Graph Check

**Files:**
- Modify: `science/src/science_tool/validate/checks/reference_graphs.py`
- Modify: `science/src/science_tool/validate/checks/__init__.py`
- Modify: `science/tests/validate/test_checks_reference_graphs.py`
- Modify: `science/tests/validate/test_runner.py`

- [ ] **Step 1: Add failing registered-check tests**

Append to `science/tests/validate/test_checks_reference_graphs.py`:

```python
from science_tool.validate.checks.reference_graphs import check_reference_graphs


def test_check_reference_graphs_reads_local_resources(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(tmp_path / "empty-commons"))
    (tmp_path / "empty-commons").mkdir()
    _write_project(tmp_path)
    dp_dir = _write_reference_graph_datapackage(tmp_path)
    dp_dir.joinpath("graph.nt").write_text("<MONDO:0005148> <is_a> <MONDO:0000001> .\n", encoding="utf-8")
    dp_dir.joinpath("nodes.csv").write_text(
        "member_key,member_kind,label,status,replaced_by,dataset_usage\n"
        "MONDO:0005148,term,multiple myeloma,active,,[]\n"
        "MONDO:obsolete,term,old label,deprecated,MONDO:0005148,[]\n",
        encoding="utf-8",
    )
    dp_dir.joinpath("edges.csv").write_text(
        "subject,predicate,object,evidence,dataset_usage\nMONDO:0005148,is_a,MONDO:0000001,,[]\n",
        encoding="utf-8",
    )

    results = list(check_reference_graphs(_ctx(tmp_path)))

    assert results == []


def test_check_reference_graphs_reports_malformed_node_rows(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(tmp_path / "empty-commons"))
    (tmp_path / "empty-commons").mkdir()
    _write_project(tmp_path)
    dp_dir = _write_reference_graph_datapackage(tmp_path)
    dp_dir.joinpath("graph.nt").write_text("<MONDO:0005148> <is_a> <MONDO:0000001> .\n", encoding="utf-8")
    dp_dir.joinpath("nodes.csv").write_text(
        "member_key,member_kind,label,status,replaced_by,dataset_usage\n"
        "MONDO:0005148,term,multiple myeloma,obsolete,,[]\n",
        encoding="utf-8",
    )
    dp_dir.joinpath("edges.csv").write_text(
        "subject,predicate,object,evidence,dataset_usage\nMONDO:0005148,is_a,MONDO:0000001,,[]\n",
        encoding="utf-8",
    )

    results = list(check_reference_graphs(_ctx(tmp_path)))

    assert _rules(results) == ["reference-graph.node-index-malformed"]
    assert results[0].severity is Severity.ERROR
```

Add a registration test to `science/tests/validate/test_runner.py` after `test_canonical_loader_registers_dataset_influence_after_genesets`:

```python
def test_canonical_loader_registers_reference_graphs_between_genesets_and_dataset_influence() -> None:
    import science_tool.validate.checks as checks

    clear_checks_for_tests()
    for module_name in ("genesets", "reference_graphs", "dataset_influence"):
        sys.modules.pop(f"science_tool.validate.checks.{module_name}", None)

    checks._load_canonical_checks()

    ordered = [(entry.section, entry.order, entry.fn.__module__) for entry in checks.CANONICAL_CHECKS]
    genesets_index = next(index for index, entry in enumerate(ordered) if entry[0] == "gene-set collections")
    reference_graphs_index = next(index for index, entry in enumerate(ordered) if entry[0] == "reference graph collections")
    influence_index = next(index for index, entry in enumerate(ordered) if entry[0] == "dataset influence")
    assert genesets_index < reference_graphs_index < influence_index
    assert ordered[genesets_index][1] == 34
    assert ordered[reference_graphs_index][1] == 35
    assert ordered[influence_index][1] == 36
```

Also update the existing `test_canonical_loader_registers_dataset_influence_after_genesets` assertion. Replace:

```python
assert influence_index == genesets_index + 1
```

with:

```python
assert influence_index > genesets_index
```

- [ ] **Step 2: Run registered-check tests to verify they fail**

Run:

```bash
uv run --frozen pytest \
  science/tests/validate/test_checks_reference_graphs.py::test_check_reference_graphs_reads_local_resources \
  science/tests/validate/test_runner.py::test_canonical_loader_registers_reference_graphs_between_genesets_and_dataset_influence \
  -q
```

Expected: FAIL because `check_reference_graphs` is not decorated/implemented and `reference_graphs` is not in `CANONICAL_CHECK_MODULES`.

- [ ] **Step 3: Add registered check**

Modify the imports at the top of `science/src/science_tool/validate/checks/reference_graphs.py` to include:

```python
from science_tool.commons.reference_graph_resources import graph_resource_available, read_edge_rows, read_node_rows
from science_tool.validate._helpers import dataset_frontmatters
```

Append this function to the end of `science/src/science_tool/validate/checks/reference_graphs.py`:

```python
@Check(section="reference graph collections", order=35)
def check_reference_graphs(ctx: ValidateContext) -> Iterator[Result]:
    datasets = dataset_frontmatters(ctx)
    collections = [fm for fm in datasets if is_reference_graph_frontmatter(fm)]
    collection_ids = {str(fm["id"]) for fm in collections if isinstance(fm.get("id"), str) and fm["id"]}
    graph_available_by_dataset_id = {
        str(fm["id"]): graph_resource_available(ctx.project_root, fm)
        for fm in collections
        if isinstance(fm.get("id"), str) and fm["id"]
    }
    node_rows_by_dataset_id = {
        str(fm["id"]): read_node_rows(ctx.project_root, fm)
        for fm in collections
        if isinstance(fm.get("id"), str) and fm["id"]
    }
    edge_rows_by_dataset_id = {
        str(fm["id"]): read_edge_rows(ctx.project_root, fm)
        for fm in collections
        if isinstance(fm.get("id"), str) and fm["id"] and fm.get("edge_resource") is not None
    }
    members = []
    for fm in datasets:
        if not is_reference_graph_member_frontmatter(fm):
            continue
        member_of = parse_member_of(fm)
        if member_of is None or member_of.parent_dataset in collection_ids:
            members.append(fm)
    yield from evaluate_reference_graphs(
        collections,
        graph_available_by_dataset_id=graph_available_by_dataset_id,
        node_rows_by_dataset_id=node_rows_by_dataset_id,
        edge_rows_by_dataset_id=edge_rows_by_dataset_id,
        member_datasets=members,
    )
```

This intentionally validates promoted members only when their parent collection is local to the project. Commons-parent promoted members are a later RG3/RG4 concern once real graph commons artifacts exist. RG1 covers promoted-member resolution at the pure `evaluate_reference_graphs` layer only; RG3 must add an on-disk integration test that proves `dataset_frontmatters` discovers a promoted `bio.reference_graph.member` entity in the chosen filesystem location.

- [ ] **Step 4: Register canonical check module**

Modify `science/src/science_tool/validate/checks/__init__.py`, inserting `"reference_graphs"` after `"genesets"` and before `"dataset_influence"`:

```python
    "variant_identity",
    "genesets",
    "reference_graphs",
    "dataset_influence",
    "prose_lints",
```

- [ ] **Step 5: Update test runner helper**

Modify `_register_real_canonical_checks()` in `science/tests/validate/test_runner.py`, inserting `"reference_graphs"` after `"genesets"`:

```python
        "variant_identity",
        "genesets",
        "reference_graphs",
        "dataset_influence",
        "prose_lints",
```

- [ ] **Step 6: Bump dataset influence check order**

Modify `science/src/science_tool/validate/checks/dataset_influence.py`, changing the decorator:

```python
@Check(section="dataset influence", order=36)
def check_dataset_influence(ctx: ValidateContext) -> Iterator[Result]:
```

- [ ] **Step 7: Run registered-check tests**

Run:

```bash
uv run --frozen pytest \
  science/tests/validate/test_checks_reference_graphs.py \
  science/tests/validate/test_runner.py::test_canonical_loader_registers_dataset_influence_after_genesets \
  science/tests/validate/test_runner.py::test_canonical_loader_registers_reference_graphs_between_genesets_and_dataset_influence \
  -q
```

Expected: PASS.

- [ ] **Step 8: Commit**

Run:

```bash
rtk git add science/src/science_tool/validate/checks/reference_graphs.py science/src/science_tool/validate/checks/__init__.py science/src/science_tool/validate/checks/dataset_influence.py science/tests/validate/test_checks_reference_graphs.py science/tests/validate/test_runner.py
rtk git commit -m "feat(validate): check reference graph datasets"
```

---

## Task 6: Docs, Status, and Final Verification

**Files:**
- Modify: `docs/plans/2026-05-31-bio-reference-graph-design.md`
- Modify: `docs/plans/2026-05-26-bio-data-architecture-umbrella-design.md`

- [ ] **Step 1: Update reference graph design status**

In `docs/plans/2026-05-31-bio-reference-graph-design.md`, change:

```markdown
Status: design for review; implementation plan pending
```

to:

```markdown
Status: RG1 implemented locally; RG2+ pending
```

Then update §9 so the table reads:

```markdown
| RG1 | Schema + parser + validation over tiny fixture graph/index/edge resources; node index required | implemented locally |
| RG2 | Virtual member resolution and B materialization hooks for unpromoted graph members | pending |
| RG3 | Promoted `bio.reference_graph.member` child datasets | pending |
| RG4 | First real commons recipe, likely MONDO or GO, with pinned release artifacts | pending |
| RG5 | Later non-molecular identity resolvers over one or more reference graphs | pending |
```

- [ ] **Step 2: Update umbrella status**

In `docs/plans/2026-05-26-bio-data-architecture-umbrella-design.md`, update the non-tabular-reference open item in §7:

```markdown
8. **Still open (non-tabular references).** Knowledge graphs/ontologies such as GO, MONDO, and Open
   Targets are not handled by the flat `bio.geneset` collection model and still need a distinct
   non-tabular-reference treatment.
```

to:

```markdown
8. **Partly resolved (non-tabular references).** `bio.reference_graph` RG1 is implemented for pinned
   graph-shaped reference datasets with node-index validation. Real GO/MONDO/Open Targets recipes,
   virtual graph-member payload resolution, promoted graph members, and non-molecular identity resolvers
   remain follow-up work.
```

Also update §8 "Remaining — other pillars" to mention `bio.reference_graph` RG1 as implemented and RG2+ pending.

- [ ] **Step 3: Run targeted tests**

Run:

```bash
uv run --frozen pytest \
  science/model/tests/test_bio_extension_reference_graph.py \
  science/tests/test_commons_reference_graph.py \
  science/tests/validate/test_checks_reference_graphs.py \
  science/tests/validate/test_runner.py::test_canonical_loader_registers_dataset_influence_after_genesets \
  science/tests/validate/test_runner.py::test_canonical_loader_registers_reference_graphs_between_genesets_and_dataset_influence \
  -q
```

Expected: PASS.

- [ ] **Step 4: Run lint**

Run:

```bash
uv run --frozen ruff check \
  science/src/science_tool/commons/reference_graph.py \
  science/src/science_tool/commons/reference_graph_resources.py \
  science/src/science_tool/validate/checks/reference_graphs.py \
  science/src/science_tool/validate/checks/dataset_influence.py \
  science/tests/test_commons_reference_graph.py \
  science/tests/validate/test_checks_reference_graphs.py \
  science/model/tests/test_bio_extension_reference_graph.py
```

Expected: `All checks passed!`

- [ ] **Step 5: Run type check**

Run:

```bash
uv run --frozen pyright \
  science/src/science_tool/commons/reference_graph.py \
  science/src/science_tool/commons/reference_graph_resources.py \
  science/src/science_tool/validate/checks/reference_graphs.py \
  science/src/science_tool/validate/checks/dataset_influence.py \
  science/tests/test_commons_reference_graph.py \
  science/tests/validate/test_checks_reference_graphs.py \
  science/model/tests/test_bio_extension_reference_graph.py
```

Expected: `0 errors, 0 warnings, 0 informations`

- [ ] **Step 6: Run whitespace check**

Run:

```bash
rtk git diff --check
```

Expected: no output.

- [ ] **Step 7: Commit docs and verification updates**

Run:

```bash
rtk git add docs/plans/2026-05-31-bio-reference-graph-design.md docs/plans/2026-05-26-bio-data-architecture-umbrella-design.md
rtk git commit -m "docs: update reference graph rg1 status"
```

---

## Self-Review Checklist

- [ ] **Spec coverage:** RG1 schema, parser, validation, required node index, count semantics, graph resource availability without byte reads, graph_format enum validation including `jsonl_edges`, deprecated-member warning, open `member_kind`, and no real public graph ingestion are all covered.
- [ ] **No placeholders:** Search this plan for the placeholder/red-flag phrases listed in the writing-plans skill; none should remain.
- [ ] **Type consistency:** The collection descriptor is always `member_key_space`; scalar member identity is only `derivation.member_key`; node rows use `member_key`.
- [ ] **YAGNI:** RG2/RG3/RG4/RG5 are named but not implemented in RG1.
- [ ] **TDD:** Every code task starts with failing tests, then implementation, then passing tests, then commit.

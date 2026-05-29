# B1 Dataset Influence Provenance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Materialize dataset usage provenance as reified graph nodes, validate authored and transition inputs, and keep `paper.datasets` on an explicit migration path to canonical `dataset_usage`.

**Architecture:** Add one shared usage-record projection module used by graph build and validate checks. Keep validation tolerant for unavailable commons/local resources, but make graph materialization strict whenever it is asked to produce queryable provenance. Do not change belief aggregation or independence scoring in B1.

**Tech Stack:** Python, Pydantic `science_model` entities, JSON Schema profile components, rdflib graph materialization, existing `science_tool.validate` check registry, D1 `science_tool.commons.geneset` parser.

---

## File Structure

- Modify `science/model/src/science_model/schemas/science-entity-base-1.0.json`
  - Declare canonical `dataset_usage` on the base schema so any entity-kind schema documents the field.
- Modify `science/model/src/science_model/schemas/mixin-dataset-1.0.json`
  - Remove the duplicate local `dataset_usage` definition after the base schema owns it.
- Modify `science/model/src/science_model/templates/paper.md`
  - Prefer `dataset_usage: []` and keep `datasets: []` visibly marked as transition input.
- Modify `science/model/tests/test_entity_schema_mixin_dataset.py`
  - Keep dataset validation coverage after moving the schema declaration.
- Modify `science/model/tests/test_entity_schema_mixin_paper.py`
  - Add paper schema coverage for `dataset_usage`.
- Create `science/src/science_tool/commons/geneset_resources.py`
  - Own gene-set collection frontmatter detection and member-resource CSV lookup/reading for both validate and graph materialization.
- Modify `science/src/science_tool/validate/checks/genesets.py`
  - Use the shared gene-set resource helper instead of private copies.
- Modify `science/tests/validate/test_checks_genesets.py`
  - Lock the shared helper behavior through the existing check tests.
- Create `science/src/science_tool/commons/frontmatter.py`
  - Own tolerant YAML/frontmatter reading shared by validate and graph code.
- Modify `science/src/science_tool/validate/_helpers.py`
  - Import shared raw frontmatter reading and add tolerant all-entity frontmatter discovery for checks that cannot rely on strict model loading.
- Create `science/src/science_tool/graph/dataset_usage.py`
  - Define `DatasetUsageRecord`, virtual gene-set member URI encoding, strict usage projection, deterministic usage-node URIs, and graph triple emission helpers.
- Modify `science/src/science_tool/graph/materialize.py`
  - Materialize usage records from authored `dataset_usage`, legacy `paper.datasets`, dataset `derivation.inputs`, and D1 gene-set rows.
- Modify `science/src/science_tool/graph/store/constants.py`
  - Include B1 usage predicates in graph export edge metadata and predicate registry.
- Modify `science/src/science_tool/validate/checks/__init__.py`
  - Register the new check last, immediately after `genesets`.
- Create `science/src/science_tool/validate/checks/dataset_influence.py`
  - Validate B1 malformed/self-reference/legacy/ref-resolution cases with pinned severities.
- Create `science/tests/validate/test_checks_dataset_influence.py`
  - Pure and runner tests for B1 validation.
- Create `science/tests/test_dataset_usage_materialize.py`
  - Focused graph materialization tests for B1 usage nodes.
- Modify parity module lists:
  - `science/scripts/update-validate-snapshots.py`
  - `science/tests/validate/test_formatter_snapshots.py`
  - `science/tests/validate/test_parity_corpus.py`
  - `science/tests/validate/test_parity_canonical_body.py`
- Modify `docs/plans/2026-05-26-bio-dataset-influence-provenance-design.md`
  - Mark B1 implementation plan as drafted/active after the code tasks land.

## Design Decisions Locked For Implementation

- `dataset_usage` is schema-documented on the base entity profile because the runtime `Entity` model already exposes it for every entity kind.
- Graph usage nodes live in `graph/provenance`.
- Usage node URI: `PROJECT_NS["dataset-usage/<sha256>"]`, where `<sha256>` hashes the canonical usage record payload.
- Virtual gene-set member URI: `PROJECT_NS["virtual/geneset-member/<dataset-slug>/<encoded-set-key>"]`.
- Virtual set keys are Unicode NFC normalized, UTF-8 encoded, and percent-encoded with uppercase hex escapes; only RFC 3986 unreserved bytes remain literal.
- Graph materialization fails on malformed usage, dataset self-reference, virtual URI collision, or unavailable members resource for any selected `bio.geneset` collection.
- Validate emits INFO when a referenced dataset cannot be checked because commons/local resources are unavailable, and WARN when discovery is available and the dataset is absent.
- `consumed_by` stale-backlink auditing is not implemented in this B1 plan. It is a separate cost class that requires a derived reverse index.
- Malformed usage reaching graph materialization is blocked by the existing strict entity loader for entity-sourced usage and by `parse_geneset_rows` for row-sourced usage; if an ERROR-class condition still reaches the B1 materializer, it raises rather than skipping.

---

### Task 1: Schema And Template Surface

**Files:**
- Modify: `science/model/src/science_model/schemas/science-entity-base-1.0.json`
- Modify: `science/model/src/science_model/schemas/mixin-dataset-1.0.json`
- Modify: `science/model/src/science_model/templates/paper.md`
- Test: `science/model/tests/test_entity_schema_mixin_paper.py`
- Test: `science/model/tests/test_entity_schema_mixin_dataset.py`

- [ ] **Step 1: Write failing paper/base schema tests**

Add these tests to `science/model/tests/test_entity_schema_mixin_paper.py`:

```python
def test_paper_dataset_usage_validates(base_entity: dict) -> None:
    entity = base_entity | {
        "dataset_usage": [
            {"ref": "dataset:gtex-v8", "role": "analyzed", "overlap": "full"},
            {"ref": "dataset:msigdb-c2", "role": "cited"},
        ]
    }
    EntityValidator().validate(entity)


def test_paper_dataset_usage_bad_role_rejected(base_entity: dict) -> None:
    entity = base_entity | {"dataset_usage": [{"ref": "dataset:x", "role": "consulted"}]}
    with pytest.raises(EntityValidationError, match="dataset_usage"):
        EntityValidator().validate(entity)


def test_base_schema_declares_dataset_usage_once() -> None:
    raw = (_SCHEMAS / "science-entity-base-1.0.json").read_text(encoding="utf-8")
    base_schema = json.loads(raw)
    paper_raw = (_SCHEMAS / "mixin-paper-2.0.json").read_text(encoding="utf-8")
    dataset_raw = (_SCHEMAS / "mixin-dataset-1.0.json").read_text(encoding="utf-8")
    paper_schema = json.loads(paper_raw)
    dataset_schema = json.loads(dataset_raw)

    assert "dataset_usage" in base_schema["properties"]
    assert "dataset_usage" not in paper_schema["properties"]
    assert "dataset_usage" not in dataset_schema["properties"]
```

Add this assertion to `test_mixin_paper_2_0_merge_policy_overrides_base_for_created_updated_status`:

```python
    assert policy["dataset_usage"] == MergePolicy.APPEND
```

Add this test to `science/model/tests/test_entity_schema_mixin_dataset.py`:

```python
def test_dataset_usage_schema_is_owned_by_base_schema() -> None:
    base_raw = (_SCHEMAS / "science-entity-base-1.0.json").read_text(encoding="utf-8")
    dataset_raw = (_SCHEMAS / "mixin-dataset-1.0.json").read_text(encoding="utf-8")
    base_schema = json.loads(base_raw)
    dataset_schema = json.loads(dataset_raw)

    assert "dataset_usage" in base_schema["properties"]
    assert "dataset_usage" not in dataset_schema["properties"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run --frozen pytest science/model/tests/test_entity_schema_mixin_paper.py science/model/tests/test_entity_schema_mixin_dataset.py -q
```

Expected: FAIL because `dataset_usage` is still declared only on `mixin-dataset-1.0.json`, and the paper merge policy has no entry.

- [ ] **Step 3: Move schema declaration to base**

In `science/model/src/science_model/schemas/science-entity-base-1.0.json`, add the property and `$defs` block:

```json
    "dataset_usage": {"$ref": "#/$defs/dataset_usage", "science:merge": "append"},
```

Add this top-level sibling after `properties`:

```json
  "$defs": {
    "dataset_usage": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["ref", "role"],
        "properties": {
          "ref": {"type": "string", "pattern": "^dataset:"},
          "role": {"enum": ["analyzed", "set_definition_source", "validation_source", "cited", "upstream", "training"]},
          "overlap": {"enum": ["full", "partial", "unknown"]}
        }
      }
    }
  }
```

In `science/model/src/science_model/schemas/mixin-dataset-1.0.json`, remove the `dataset_usage` property line and remove the `$defs.dataset_usage` block. Keep `$defs.access` and `$defs.derivation`.

- [ ] **Step 4: Update paper template**

In `science/model/src/science_model/templates/paper.md`, replace:

```yaml
datasets: []
```

with:

```yaml
dataset_usage: []
# Transition input only; prefer dataset_usage above.
datasets: []
```

- [ ] **Step 5: Run schema tests**

Run:

```bash
uv run --frozen pytest science/model/tests/test_entity_schema_mixin_paper.py science/model/tests/test_entity_schema_mixin_dataset.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add science/model/src/science_model/schemas/science-entity-base-1.0.json science/model/src/science_model/schemas/mixin-dataset-1.0.json science/model/src/science_model/templates/paper.md science/model/tests/test_entity_schema_mixin_paper.py science/model/tests/test_entity_schema_mixin_dataset.py
git commit -m "feat: expose dataset usage on base schema"
```

---

### Task 2: Shared Gene-Set Resource Reader

**Files:**
- Create: `science/src/science_tool/commons/geneset_resources.py`
- Modify: `science/src/science_tool/validate/checks/genesets.py`
- Test: `science/tests/validate/test_checks_genesets.py`

- [ ] **Step 1: Write failing helper import test**

Add this test to `science/tests/validate/test_checks_genesets.py`:

```python
def test_geneset_resource_helper_reads_local_rows(tmp_path: Path) -> None:
    from science_tool.commons.geneset_resources import read_member_rows

    _write_project(tmp_path)
    _write_geneset_dataset(
        tmp_path,
        rows="set_key,name,member_ids\nR-HSA-1,Cell cycle,HGNC:1;HGNC:2\n",
    )
    fm = _geneset(_path="data/reactome/datapackage.yaml")

    rows = read_member_rows(tmp_path, fm)

    assert rows == [{"set_key": "R-HSA-1", "name": "Cell cycle", "member_ids": "HGNC:1;HGNC:2"}]
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run --frozen pytest science/tests/validate/test_checks_genesets.py::test_geneset_resource_helper_reads_local_rows -q
```

Expected: FAIL with `ModuleNotFoundError: No module named 'science_tool.commons.geneset_resources'`.

- [ ] **Step 3: Create shared helper**

Create `science/src/science_tool/commons/geneset_resources.py`:

```python
"""Shared resource helpers for bio.geneset collection member tables."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

import yaml

from science_tool.commons.datapackage import validate_logical_path
from science_tool.commons.errors import CommonsError

PROFILE_TOKEN = "+bio.geneset/"


def is_geneset_frontmatter(fm: dict[str, Any]) -> bool:
    profile = str(fm.get("schema_profile") or "")
    return (fm.get("kind") or fm.get("type")) == "dataset" and PROFILE_TOKEN in f"+{profile}"


def resource_path_for_members(project_root: Path, fm: dict[str, Any]) -> Path | Exception | None:
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


def read_member_rows(project_root: Path, fm: dict[str, Any]) -> list[dict[str, Any]] | Exception | None:
    path = resource_path_for_members(project_root, fm)
    if isinstance(path, Exception):
        return path
    if path is None or not path.is_file():
        return None
    try:
        with path.open(encoding="utf-8", newline="") as fh:
            return list(csv.DictReader(fh))
    except (OSError, UnicodeError, csv.Error) as exc:
        return exc
```

- [ ] **Step 4: Switch genesets check to shared helper**

In `science/src/science_tool/validate/checks/genesets.py`:

```python
from science_tool.commons.geneset_resources import (
    is_geneset_frontmatter,
    read_member_rows,
)
```

Change `_is_geneset` to:

```python
def _is_geneset(fm: dict[str, Any]) -> bool:
    return is_geneset_frontmatter(fm)
```

Remove `_resource_path_for_members` and `_read_member_rows`.

Change the runner comprehension to:

```python
    rows_by_dataset_id = {
        str(fm["id"]): read_member_rows(ctx.project_root, fm)
        for fm in genesets
        if isinstance(fm.get("id"), str) and fm["id"]
    }
```

Remove now-unused imports: `csv`, `yaml`, `validate_logical_path`.

- [ ] **Step 5: Run geneset tests**

Run:

```bash
uv run --frozen pytest science/tests/validate/test_checks_genesets.py science/tests/test_commons_geneset.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/commons/geneset_resources.py science/src/science_tool/validate/checks/genesets.py science/tests/validate/test_checks_genesets.py
git commit -m "refactor: share geneset member resource reader"
```

---

### Task 3: Shared Raw Frontmatter And Entity Discovery

**Files:**
- Create: `science/src/science_tool/commons/frontmatter.py`
- Modify: `science/src/science_tool/validate/_helpers.py`
- Test: `science/tests/validate/test_helpers_dataset_discovery.py`

- [ ] **Step 1: Write failing discovery test**

Add this test to `science/tests/validate/test_helpers_dataset_discovery.py`:

```python
def test_entity_frontmatters_discovers_papers_and_datapackage_datasets(tmp_path: Path) -> None:
    from science_tool.validate._helpers import entity_frontmatters

    (tmp_path / "science.yaml").write_text("name: demo\nknowledge_profiles:\n  local: local\n", encoding="utf-8")
    (tmp_path / "doc" / "papers").mkdir(parents=True)
    (tmp_path / "doc" / "papers" / "Adams2025.md").write_text(
        "---\n"
        "id: paper:Adams2025\n"
        "type: paper\n"
        "title: Adams\n"
        "dataset_usage:\n"
        "  - ref: dataset:gtex-v8\n"
        "    role: analyzed\n"
        "---\n",
        encoding="utf-8",
    )
    dp_dir = tmp_path / "data" / "gtex"
    dp_dir.mkdir(parents=True)
    (dp_dir / "datapackage.yaml").write_text(
        "profiles: [science-pkg-entity-1.0]\n"
        "id: dataset:gtex-v8\n"
        "type: dataset\n"
        "title: GTEx\n"
        "origin: external\n"
        "tier: use-now\n"
        "datapackage: datapackage.yaml\n",
        encoding="utf-8",
    )

    rows = entity_frontmatters(_ctx(tmp_path))

    by_id = {row["id"]: row for row in rows}
    assert by_id["paper:Adams2025"]["_path"] == "doc/papers/Adams2025.md"
    assert by_id["dataset:gtex-v8"]["_path"] == "data/gtex/datapackage.yaml"


def test_raw_frontmatter_shared_helper_reads_markdown_and_yaml(tmp_path: Path) -> None:
    from science_tool.commons.frontmatter import raw_frontmatter

    md = tmp_path / "entity.md"
    md.write_text("---\nid: paper:Adams2025\ntype: paper\n---\nBody\n", encoding="utf-8")
    yaml_path = tmp_path / "datapackage.yaml"
    yaml_path.write_text("id: dataset:gtex-v8\ntype: dataset\n", encoding="utf-8")

    assert raw_frontmatter(md)["id"] == "paper:Adams2025"
    assert raw_frontmatter(yaml_path)["id"] == "dataset:gtex-v8"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run --frozen pytest science/tests/validate/test_helpers_dataset_discovery.py -q
```

Expected: FAIL with `ImportError` or `AttributeError` because `entity_frontmatters` and `science_tool.commons.frontmatter` do not exist.

- [ ] **Step 3: Move raw frontmatter reader to commons**

Create `science/src/science_tool/commons/frontmatter.py`:

```python
"""Tolerant frontmatter readers shared by graph and validate code."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml


def raw_frontmatter(path: Path) -> dict[str, Any]:
    """Raw frontmatter for either a fenced markdown entity or a YAML descriptor.

    Reads directly and tolerates malformed input by returning {}. Callers that
    need schema-critical guarantees must enforce those rules themselves.
    """
    try:
        text = path.read_text(encoding="utf-8")
        if path.suffix in (".yaml", ".yml"):
            data = yaml.safe_load(text) or {}
        elif text.startswith("---"):
            end = text.find("\n---", 3)
            data = yaml.safe_load(text[3:end]) if end != -1 else {}
        else:
            data = {}
    except (OSError, UnicodeDecodeError, yaml.YAMLError):
        return {}
    return data if isinstance(data, dict) else {}
```

In `science/src/science_tool/validate/_helpers.py`, import the shared helper and remove the local `raw_frontmatter` function body:

```python
from science_tool.commons.frontmatter import raw_frontmatter
```

- [ ] **Step 4: Implement tolerant entity discovery**

Add to `science/src/science_tool/validate/_helpers.py`:

```python
def entity_frontmatters(ctx: ValidateContext) -> list[dict[str, Any]]:
    """Raw frontmatter for every project entity discovered by tolerant adapters.

    This is for validate checks that must inspect malformed fields without
    strict-loading the closed graph Entity model first.
    """
    out: list[dict[str, Any]] = []
    seen_paths: set[str] = set()
    adapters = (DatapackageAdapter(), MarkdownAdapter())
    for adapter in adapters:
        for ref in adapter.discover(ctx.project_root):
            if ref.path in seen_paths:
                continue
            seen_paths.add(ref.path)
            abs_path = ctx.project_root / ref.path
            if not abs_path.is_file():
                continue
            fm = raw_frontmatter(abs_path)
            kind = fm.get("kind") or fm.get("type")
            if not isinstance(kind, str) or not kind:
                continue
            fm["_path"] = ref.path
            out.append(fm)
    return out
```

- [ ] **Step 5: Run helper tests**

Run:

```bash
uv run --frozen pytest science/tests/validate/test_helpers_dataset_discovery.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/commons/frontmatter.py science/src/science_tool/validate/_helpers.py science/tests/validate/test_helpers_dataset_discovery.py
git commit -m "feat: share raw entity frontmatter discovery"
```

---

### Task 4: Usage Projection Helper

**Files:**
- Create: `science/src/science_tool/graph/dataset_usage.py`
- Test: `science/tests/test_dataset_usage_materialize.py`

- [ ] **Step 1: Write failing pure helper tests**

Create `science/tests/test_dataset_usage_materialize.py`:

```python
from __future__ import annotations

import pytest
from rdflib import URIRef
from science_model.entities import Entity, PaperEntity
from science_model.packages.schema import AccessBlock, DatasetUsage, DerivationBlock

from science_tool.graph.store import PROJECT_NS


def _base_entity_kwargs() -> dict[str, object]:
    return {
        "id": "observation:o1",
        "canonical_id": "observation:o1",
        "kind": "observation",
        "type": "observation",
        "title": "Observation",
        "project": "demo",
        "ontology_terms": [],
        "related": [],
        "source_refs": [],
        "content_preview": "",
        "file_path": "doc/observations/o1.md",
    }


def _paper() -> PaperEntity:
    return PaperEntity(
        id="paper:Adams2025",
        canonical_id="paper:Adams2025",
        kind="paper",
        type="paper",
        title="Adams",
        project="demo",
        ontology_terms=[],
        related=[],
        source_refs=[],
        content_preview="",
        file_path="doc/papers/Adams2025.md",
        datasets=["dataset:gtex-v8", "dataset:encode-v4"],
        dataset_usage=[DatasetUsage(ref="dataset:gtex-v8", role="cited")],
    )


def test_entity_usage_records_are_universal_for_authored_dataset_usage() -> None:
    from science_tool.graph.dataset_usage import usage_records_for_entity

    entity = Entity(
        **_base_entity_kwargs(),
        dataset_usage=[DatasetUsage(ref="dataset:gtex-v8", role="validation_source", overlap="partial")],
    )

    records = usage_records_for_entity(entity)

    assert [(r.consumer_id, r.dataset_ref, r.role, r.overlap, r.source) for r in records] == [
        ("observation:o1", "dataset:gtex-v8", "validation_source", "partial", "authored")
    ]


def test_paper_legacy_datasets_union_without_duplicate() -> None:
    from science_tool.graph.dataset_usage import usage_records_for_entity

    records = usage_records_for_entity(_paper())

    assert [(r.dataset_ref, r.role, r.overlap, r.source) for r in records] == [
        ("dataset:gtex-v8", "cited", "unknown", "authored"),
        ("dataset:encode-v4", "analyzed", "unknown", "paper.datasets"),
    ]


def test_derived_dataset_inputs_project_to_upstream_unknown() -> None:
    from science_tool.graph.dataset_usage import usage_records_for_entity

    entity = Entity(
        id="dataset:derived",
        canonical_id="dataset:derived",
        kind="dataset",
        type="dataset",
        title="Derived",
        project="demo",
        ontology_terms=[],
        related=[],
        source_refs=[],
        content_preview="",
        file_path="data/derived/datapackage.yaml",
        origin="derived",
        derivation=DerivationBlock(
            workflow="workflow:w",
            workflow_run="workflow-run:r",
            git_commit="abc",
            config_snapshot="cfg",
            produced_at="2026-05-29",
            inputs=["dataset:raw"],
        ),
    )

    records = usage_records_for_entity(entity)

    assert [(r.dataset_ref, r.role, r.overlap, r.source) for r in records] == [
        ("dataset:raw", "upstream", "unknown", "derivation.inputs")
    ]


def test_dataset_self_reference_is_materialization_error() -> None:
    from science_tool.graph.dataset_usage import DatasetUsageMaterializationError, usage_records_for_entity

    entity = Entity(
        id="dataset:self",
        canonical_id="dataset:self",
        kind="dataset",
        type="dataset",
        title="Self",
        project="demo",
        ontology_terms=[],
        related=[],
        source_refs=[],
        content_preview="",
        file_path="data/self/datapackage.yaml",
        origin="external",
        access=AccessBlock(level="public", verified=True),
        dataset_usage=[DatasetUsage(ref="dataset:self", role="analyzed")],
    )

    with pytest.raises(DatasetUsageMaterializationError, match="self-referential"):
        usage_records_for_entity(entity)


def test_virtual_geneset_member_uri_uses_canonical_percent_encoding() -> None:
    from science_tool.graph.dataset_usage import virtual_geneset_member_uri

    uri = virtual_geneset_member_uri("dataset:reactome-v89", "A B/é")

    assert uri == URIRef(PROJECT_NS["virtual/geneset-member/reactome-v89/A%20B%2F%C3%A9"])
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run --frozen pytest science/tests/test_dataset_usage_materialize.py -q
```

Expected: FAIL with `ModuleNotFoundError` for `science_tool.graph.dataset_usage`.

- [ ] **Step 3: Implement projection helper**

Create `science/src/science_tool/graph/dataset_usage.py`:

```python
"""Dataset usage projection and graph helpers for Pillar B1."""

from __future__ import annotations

import hashlib
import json
import unicodedata
from dataclasses import dataclass
from typing import Literal

from rdflib import Literal as RDFLiteral, URIRef
from rdflib.namespace import RDF
from science_model.entities import Entity
from science_model.packages.schema import DerivationBlock

from science_tool.graph.store import PROJECT_NS, SCI_NS

UsageSource = Literal["authored", "paper.datasets", "derivation.inputs", "geneset.members_resource"]

_UNRESERVED = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~"


class DatasetUsageMaterializationError(ValueError):
    """A usage record cannot be safely materialized into graph truth."""


@dataclass(frozen=True, slots=True)
class DatasetUsageRecord:
    consumer_id: str
    dataset_ref: str
    role: str
    overlap: str
    source: UsageSource
    source_path: str
    row_key: str = ""

    def payload(self) -> dict[str, str]:
        return {
            "consumer_id": self.consumer_id,
            "dataset_ref": self.dataset_ref,
            "role": self.role,
            "overlap": self.overlap,
            "source": self.source,
            "source_path": self.source_path,
            "row_key": self.row_key,
        }


def usage_records_for_entity(entity: Entity) -> list[DatasetUsageRecord]:
    records: list[DatasetUsageRecord] = []
    explicit_refs: set[str] = set()
    source_path = str(getattr(entity, "file_path", "") or "")

    for usage in getattr(entity, "dataset_usage", []) or []:
        dataset_ref = str(usage.ref)
        _reject_self_reference(entity, dataset_ref)
        explicit_refs.add(dataset_ref)
        records.append(
            DatasetUsageRecord(
                consumer_id=entity.canonical_id,
                dataset_ref=dataset_ref,
                role=str(usage.role),
                overlap=str(usage.overlap or "unknown"),
                source="authored",
                source_path=source_path,
            )
        )

    if entity.kind == "paper":
        for dataset_ref in getattr(entity, "datasets", []) or []:
            if dataset_ref in explicit_refs:
                continue
            records.append(
                DatasetUsageRecord(
                    consumer_id=entity.canonical_id,
                    dataset_ref=str(dataset_ref),
                    role="analyzed",
                    overlap="unknown",
                    source="paper.datasets",
                    source_path=source_path,
                )
            )

    derivation = getattr(entity, "derivation", None)
    if entity.kind == "dataset" and isinstance(derivation, DerivationBlock):
        for dataset_ref in derivation.inputs:
            _reject_self_reference(entity, dataset_ref)
            records.append(
                DatasetUsageRecord(
                    consumer_id=entity.canonical_id,
                    dataset_ref=str(dataset_ref),
                    role="upstream",
                    overlap="unknown",
                    source="derivation.inputs",
                    source_path=source_path,
                )
            )

    return records


def _reject_self_reference(entity: Entity, dataset_ref: str) -> None:
    if entity.kind == "dataset" and dataset_ref == entity.canonical_id:
        raise DatasetUsageMaterializationError(
            f"{entity.canonical_id}: self-referential dataset usage {dataset_ref!r}"
        )


def project_entity_uri(canonical_id: str) -> URIRef:
    kind, slug = canonical_id.split(":", 1)
    return URIRef(PROJECT_NS[f"{kind}/{slug.lower()}"])


def virtual_geneset_member_uri(collection_id: str, set_key: str) -> URIRef:
    if not collection_id.startswith("dataset:"):
        raise DatasetUsageMaterializationError(f"gene-set collection id must be dataset:<slug>, got {collection_id!r}")
    dataset_slug = collection_id.split(":", 1)[1].lower()
    return URIRef(PROJECT_NS[f"virtual/geneset-member/{dataset_slug}/{_encode_path_segment(set_key)}"])


def _encode_path_segment(value: str) -> str:
    normalized = unicodedata.normalize("NFC", value)
    out: list[str] = []
    for byte in normalized.encode("utf-8"):
        if byte in _UNRESERVED:
            out.append(chr(byte))
        else:
            out.append(f"%{byte:02X}")
    return "".join(out)


def usage_node_uri(record: DatasetUsageRecord) -> URIRef:
    payload = json.dumps(record.payload(), sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return URIRef(PROJECT_NS[f"dataset-usage/{digest}"])


def add_usage_record_to_graph(record: DatasetUsageRecord, graph) -> None:
    node = usage_node_uri(record)
    consumer = project_entity_uri(record.consumer_id) if ":" in record.consumer_id else URIRef(record.consumer_id)
    dataset_uri = project_entity_uri(record.dataset_ref)
    graph.add((consumer, SCI_NS.hasDatasetUsage, node))
    graph.add((node, RDF.type, SCI_NS.DatasetUsage))
    graph.add((node, SCI_NS.dataset, dataset_uri))
    graph.add((node, SCI_NS.usageRole, RDFLiteral(record.role)))
    graph.add((node, SCI_NS.usageOverlap, RDFLiteral(record.overlap)))
    graph.add((node, SCI_NS.usageSource, RDFLiteral(record.source)))
```

- [ ] **Step 4: Run helper tests**

Run:

```bash
uv run --frozen pytest science/tests/test_dataset_usage_materialize.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/graph/dataset_usage.py science/tests/test_dataset_usage_materialize.py
git commit -m "feat: project dataset usage records"
```

---

### Task 5: Materialize Entity Usage Nodes

**Files:**
- Modify: `science/src/science_tool/graph/materialize.py`
- Modify: `science/src/science_tool/graph/store/constants.py`
- Test: `science/tests/test_dataset_usage_materialize.py`

- [ ] **Step 1: Add failing graph integration test**

Append to `science/tests/test_dataset_usage_materialize.py`:

```python
from rdflib import Dataset, Literal
from rdflib.namespace import RDF

from science_tool.graph.materialize import materialize_graph
from science_tool.graph.store import SCI_NS


def _write_project(root):
    root.mkdir(parents=True, exist_ok=True)
    (root / "science.yaml").write_text("name: demo\nknowledge_profiles:\n  local: local\n", encoding="utf-8")


def _write_dataset(path, slug, extra):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "profiles: [science-pkg-entity-1.0]\n"
        f"id: dataset:{slug}\n"
        "type: dataset\n"
        f"title: {slug}\n"
        "status: active\n"
        "tier: use-now\n"
        "datapackage: datapackage.yaml\n"
        f"{extra}",
        encoding="utf-8",
    )


def _load_trig(path):
    ds = Dataset()
    ds.parse(source=str(path), format="trig")
    return ds


def test_materialize_graph_emits_entity_usage_nodes(tmp_path):
    _write_project(tmp_path)
    _write_dataset(
        tmp_path / "data" / "gtex" / "datapackage.yaml",
        "gtex-v8",
        "origin: external\n"
        "access:\n"
        "  level: public\n"
        "  verified: true\n",
    )
    _write_dataset(
        tmp_path / "data" / "derived" / "datapackage.yaml",
        "derived",
        "source_class: derived\n"
        "derived_kind: aggregate\n"
        "origin: derived\n"
        "derivation:\n"
        "  workflow: workflow:w\n"
        "  workflow_run: workflow-run:r\n"
        "  git_commit: abc\n"
        "  config_snapshot: cfg\n"
        "  produced_at: '2026-05-29'\n"
        "  inputs:\n"
        "    - dataset:gtex-v8\n",
    )
    paper_dir = tmp_path / "doc" / "papers"
    paper_dir.mkdir(parents=True)
    (paper_dir / "Adams2025.md").write_text(
        "---\n"
        "id: paper:Adams2025\n"
        "type: paper\n"
        "title: Adams\n"
        "status: active\n"
        "created: '2026-05-29'\n"
        "updated: '2026-05-29'\n"
        "dataset_usage:\n"
        "  - ref: dataset:gtex-v8\n"
        "    role: analyzed\n"
        "    overlap: full\n"
        "---\n",
        encoding="utf-8",
    )

    trig = materialize_graph(tmp_path)
    graph = _load_trig(trig).graph(PROJECT_NS["graph/provenance"])

    paper_uri = PROJECT_NS["paper/Adams2025".lower()]
    derived_uri = PROJECT_NS["dataset/derived"]
    gtex_uri = PROJECT_NS["dataset/gtex-v8"]
    paper_nodes = list(graph.objects(paper_uri, SCI_NS.hasDatasetUsage))
    derived_nodes = list(graph.objects(derived_uri, SCI_NS.hasDatasetUsage))

    assert len(paper_nodes) == 1
    assert len(derived_nodes) == 1
    assert (paper_nodes[0], RDF.type, SCI_NS.DatasetUsage) in graph
    assert (paper_nodes[0], SCI_NS.dataset, gtex_uri) in graph
    assert (paper_nodes[0], SCI_NS.usageRole, Literal("analyzed")) in graph
    assert (paper_nodes[0], SCI_NS.usageOverlap, Literal("full")) in graph
    assert (paper_nodes[0], SCI_NS.usageSource, Literal("authored")) in graph
    assert (derived_nodes[0], SCI_NS.dataset, gtex_uri) in graph
    assert (derived_nodes[0], SCI_NS.usageRole, Literal("upstream")) in graph
    assert (derived_nodes[0], SCI_NS.usageOverlap, Literal("unknown")) in graph
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run --frozen pytest science/tests/test_dataset_usage_materialize.py::test_materialize_graph_emits_entity_usage_nodes -q
```

Expected: FAIL because no `sci:hasDatasetUsage` triples are emitted.

- [ ] **Step 3: Wire entity usage into materialize**

In `science/src/science_tool/graph/materialize.py`, add imports:

```python
from science_tool.graph.dataset_usage import add_usage_record_to_graph, usage_records_for_entity
```

After `_add_produced_by_edges(...)` in `_build_dataset_from_sources`, add:

```python
    _add_dataset_usage_edges(sources, provenance=provenance)
```

Add helper:

```python
def _add_dataset_usage_edges(sources: ProjectSources, *, provenance) -> None:
    for entity in sources.entities:
        for record in usage_records_for_entity(entity):
            add_usage_record_to_graph(record, provenance)
```

- [ ] **Step 4: Add graph predicate metadata**

In `science/src/science_tool/graph/store/constants.py`, add these predicates to `GRAPH_EXPORT_EDGE_METADATA_PREDICATES`:

```python
        SCI_NS.hasDatasetUsage,
        SCI_NS.dataset,
        SCI_NS.usageRole,
        SCI_NS.usageOverlap,
        SCI_NS.usageSource,
```

Add these entries to `PREDICATE_REGISTRY`:

```python
    {
        "predicate": "sci:hasDatasetUsage",
        "description": "Links a consumer entity to a reified dataset usage record",
        "layer": "graph/provenance",
    },
    {
        "predicate": "sci:dataset",
        "description": "Dataset referenced by a reified dataset usage record",
        "layer": "graph/provenance",
    },
    {
        "predicate": "sci:usageRole",
        "description": "Role of a dataset in a reified usage record",
        "layer": "graph/provenance",
    },
    {
        "predicate": "sci:usageOverlap",
        "description": "Overlap of a dataset usage record: full, partial, or unknown",
        "layer": "graph/provenance",
    },
    {
        "predicate": "sci:usageSource",
        "description": "Projection source for a reified dataset usage record",
        "layer": "graph/provenance",
    },
```

- [ ] **Step 5: Run graph test**

Run:

```bash
uv run --frozen pytest science/tests/test_dataset_usage_materialize.py::test_materialize_graph_emits_entity_usage_nodes -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/graph/materialize.py science/src/science_tool/graph/store/constants.py science/tests/test_dataset_usage_materialize.py
git commit -m "feat: materialize entity dataset usage nodes"
```

---

### Task 6: Materialize Gene-Set Row Usage Nodes Strictly

**Files:**
- Modify: `science/src/science_tool/graph/dataset_usage.py`
- Modify: `science/src/science_tool/graph/materialize.py`
- Test: `science/tests/test_dataset_usage_materialize.py`

- [ ] **Step 1: Add failing gene-set graph tests**

Append to `science/tests/test_dataset_usage_materialize.py`:

```python
def _write_geneset_collection(root, *, with_members=True):
    dp_dir = root / "data" / "reactome"
    dp_dir.mkdir(parents=True, exist_ok=True)
    (dp_dir / "datapackage.yaml").write_text(
        "profiles: [science-pkg-entity-1.0]\n"
        "id: dataset:reactome-v89\n"
        "type: dataset\n"
        "title: Reactome\n"
        "status: active\n"
        "origin: external\n"
        "tier: use-now\n"
        "datapackage: datapackage.yaml\n"
        "schema_profile: science-entity-base/1.0+dataset/1.0+bio.geneset/1.0\n"
        "source_class: reference\n"
        "access:\n"
        "  level: public\n"
        "  verified: true\n"
        "member_key_column: set_key\n"
        "members_resource: sets\n"
        "n_sets: 1\n"
        "set_size_summary: {min: 2, median: 2, max: 2}\n"
        "identifier_space: {tier: gene, namespace: hgnc_id, resolution_status: declared_unresolved}\n"
        "resources:\n"
        "  - name: sets\n"
        "    path: sets.csv\n",
        encoding="utf-8",
    )
    if with_members:
        (dp_dir / "sets.csv").write_text(
            "set_key,name,member_ids,dataset_usage\n"
            'R-HSA-1,Cell cycle,HGNC:1;HGNC:2,"[{""ref"":""dataset:gtex-v8"",""role"":""set_definition_source"",""overlap"":""full""}]"\n',
            encoding="utf-8",
        )


def test_materialize_graph_emits_geneset_row_usage_nodes(tmp_path):
    _write_project(tmp_path)
    _write_dataset(
        tmp_path / "data" / "gtex" / "datapackage.yaml",
        "gtex-v8",
        "origin: external\n"
        "access:\n"
        "  level: public\n"
        "  verified: true\n",
    )
    _write_geneset_collection(tmp_path)

    trig = materialize_graph(tmp_path)
    graph = _load_trig(trig).graph(PROJECT_NS["graph/provenance"])

    row_uri = PROJECT_NS["virtual/geneset-member/reactome-v89/R-HSA-1"]
    nodes = list(graph.objects(row_uri, SCI_NS.hasDatasetUsage))

    assert len(nodes) == 1
    assert (nodes[0], SCI_NS.dataset, PROJECT_NS["dataset/gtex-v8"]) in graph
    assert (nodes[0], SCI_NS.usageRole, Literal("set_definition_source")) in graph
    assert (nodes[0], SCI_NS.usageOverlap, Literal("full")) in graph
    assert (nodes[0], SCI_NS.usageSource, Literal("geneset.members_resource")) in graph


def test_materialize_graph_requires_geneset_members_resource(tmp_path):
    _write_project(tmp_path)
    _write_geneset_collection(tmp_path, with_members=False)

    with pytest.raises(RuntimeError, match="members_resource"):
        materialize_graph(tmp_path)
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run --frozen pytest science/tests/test_dataset_usage_materialize.py::test_materialize_graph_emits_geneset_row_usage_nodes science/tests/test_dataset_usage_materialize.py::test_materialize_graph_requires_geneset_members_resource -q
```

Expected: FAIL because gene-set rows are not read during graph materialization.

- [ ] **Step 3: Add row usage projection helper**

Add to `science/src/science_tool/graph/dataset_usage.py`:

```python
def usage_records_for_geneset_rows(
    *,
    collection_id: str,
    source_path: str,
    rows,
) -> list[DatasetUsageRecord]:
    records: list[DatasetUsageRecord] = []
    seen_virtual: dict[str, str] = {}
    for row in rows:
        consumer_uri = virtual_geneset_member_uri(collection_id, row.set_key)
        previous = seen_virtual.get(str(consumer_uri))
        if previous is not None and previous != row.set_key:
            raise DatasetUsageMaterializationError(
                f"{collection_id}: set_key {row.set_key!r} collides with {previous!r}"
            )
        seen_virtual[str(consumer_uri)] = row.set_key
        for usage in row.dataset_usage:
            overlap = str(usage.get("overlap") or "unknown")
            records.append(
                DatasetUsageRecord(
                    consumer_id=str(consumer_uri),
                    dataset_ref=str(usage["ref"]),
                    role=str(usage["role"]),
                    overlap=overlap,
                    source="geneset.members_resource",
                    source_path=source_path,
                    row_key=row.set_key,
                )
            )
    return records
```

Update `project_entity_uri` to support virtual URI strings:

```python
def project_entity_uri(canonical_id: str) -> URIRef:
    if canonical_id.startswith("http://") or canonical_id.startswith("https://"):
        return URIRef(canonical_id)
    kind, slug = canonical_id.split(":", 1)
    return URIRef(PROJECT_NS[f"{kind}/{slug.lower()}"])
```

- [ ] **Step 4: Wire row usage into materialize**

In `science/src/science_tool/graph/materialize.py`, add imports:

```python
from science_tool.commons.geneset import GenesetCollectionError, parse_geneset_rows
from science_tool.commons.geneset_resources import is_geneset_frontmatter, read_member_rows
from science_tool.commons.frontmatter import raw_frontmatter
from science_tool.graph.dataset_usage import usage_records_for_geneset_rows
```

Extend `_add_dataset_usage_edges`:

```python
def _add_dataset_usage_edges(sources: ProjectSources, *, provenance) -> None:
    for entity in sources.entities:
        for record in usage_records_for_entity(entity):
            add_usage_record_to_graph(record, provenance)
    for record in _geneset_usage_records(sources):
        add_usage_record_to_graph(record, provenance)
```

Add helper:

```python
def _geneset_usage_records(sources: ProjectSources):
    project_root = Path(sources.project_root)
    for entity in sources.entities:
        if entity.kind != "dataset":
            continue
        fm_path = project_root / entity.file_path
        fm = raw_frontmatter(fm_path)
        if not is_geneset_frontmatter(fm):
            continue
        fm["_path"] = entity.file_path
        raw_rows = read_member_rows(project_root, fm)
        if raw_rows is None:
            raise RuntimeError(f"{entity.canonical_id}: members_resource unavailable for graph materialization")
        if isinstance(raw_rows, Exception):
            raise RuntimeError(f"{entity.canonical_id}: members_resource malformed: {raw_rows}") from raw_rows
        try:
            rows = parse_geneset_rows(raw_rows)
        except GenesetCollectionError as exc:
            raise RuntimeError(f"{entity.canonical_id}: members_resource malformed: {exc}") from exc
        yield from usage_records_for_geneset_rows(
            collection_id=entity.canonical_id,
            source_path=entity.file_path,
            rows=rows,
        )
```

- [ ] **Step 5: Run gene-set graph tests**

Run:

```bash
uv run --frozen pytest science/tests/test_dataset_usage_materialize.py::test_materialize_graph_emits_geneset_row_usage_nodes science/tests/test_dataset_usage_materialize.py::test_materialize_graph_requires_geneset_members_resource -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/graph/dataset_usage.py science/src/science_tool/graph/materialize.py science/tests/test_dataset_usage_materialize.py
git commit -m "feat: materialize geneset row dataset usage"
```

---

### Task 7: Dataset Influence Validate Check Pure Core

**Files:**
- Create: `science/src/science_tool/validate/checks/dataset_influence.py`
- Test: `science/tests/validate/test_checks_dataset_influence.py`

- [ ] **Step 1: Write failing pure tests**

Create `science/tests/validate/test_checks_dataset_influence.py`:

```python
from __future__ import annotations

from pathlib import Path

from science_tool.validate.result import Severity


def _rules(results):
    return [(r.severity, r.rule) for r in results]


def _fm(**extra):
    return {
        "id": "paper:Adams2025",
        "type": "paper",
        "_path": "doc/papers/Adams2025.md",
        **extra,
    }


def test_malformed_dataset_usage_errors() -> None:
    from science_tool.validate.checks.dataset_influence import evaluate_dataset_influence

    results = list(
        evaluate_dataset_influence(
            [_fm(dataset_usage={"ref": "dataset:gtex-v8", "role": "analyzed"})],
            dataset_ref_status={"dataset:gtex-v8": "resolved"},
            row_usage_refs=[],
        )
    )

    assert _rules(results) == [(Severity.ERROR, "dataset-influence.dataset-usage-malformed")]


def test_paper_datasets_invalid_entry_errors() -> None:
    from science_tool.validate.checks.dataset_influence import evaluate_dataset_influence

    results = list(
        evaluate_dataset_influence(
            [_fm(datasets=["paper:Other"])],
            dataset_ref_status={},
            row_usage_refs=[],
        )
    )

    assert _rules(results) == [(Severity.ERROR, "dataset-influence.paper-datasets-invalid")]


def test_legacy_paper_datasets_warns_when_not_equivalent() -> None:
    from science_tool.validate.checks.dataset_influence import evaluate_dataset_influence

    results = list(
        evaluate_dataset_influence(
            [_fm(datasets=["dataset:gtex-v8"])],
            dataset_ref_status={"dataset:gtex-v8": "resolved"},
            row_usage_refs=[],
        )
    )

    assert _rules(results) == [(Severity.WARN, "dataset-influence.paper-datasets-legacy")]


def test_paper_datasets_conflict_warns_and_explicit_wins() -> None:
    from science_tool.validate.checks.dataset_influence import evaluate_dataset_influence

    results = list(
        evaluate_dataset_influence(
            [
                _fm(
                    datasets=["dataset:gtex-v8"],
                    dataset_usage=[{"ref": "dataset:gtex-v8", "role": "cited"}],
                )
            ],
            dataset_ref_status={"dataset:gtex-v8": "resolved"},
            row_usage_refs=[],
        )
    )

    assert _rules(results) == [(Severity.WARN, "dataset-influence.paper-datasets-conflict")]


def test_paper_datasets_analyzed_full_is_refinement_not_conflict() -> None:
    from science_tool.validate.checks.dataset_influence import evaluate_dataset_influence

    results = list(
        evaluate_dataset_influence(
            [
                _fm(
                    datasets=["dataset:gtex-v8"],
                    dataset_usage=[{"ref": "dataset:gtex-v8", "role": "analyzed", "overlap": "full"}],
                )
            ],
            dataset_ref_status={"dataset:gtex-v8": "resolved"},
            row_usage_refs=[],
        )
    )

    assert results == []


def test_dataset_self_reference_errors() -> None:
    from science_tool.validate.checks.dataset_influence import evaluate_dataset_influence

    results = list(
        evaluate_dataset_influence(
            [
                {
                    "id": "dataset:self",
                    "type": "dataset",
                    "_path": "data/self/datapackage.yaml",
                    "dataset_usage": [{"ref": "dataset:self", "role": "analyzed"}],
                }
            ],
            dataset_ref_status={"dataset:self": "resolved"},
            row_usage_refs=[],
        )
    )

    assert _rules(results) == [(Severity.ERROR, "dataset-influence.self-reference")]


def test_unresolved_refs_use_pinned_severities() -> None:
    from science_tool.validate.checks.dataset_influence import evaluate_dataset_influence

    results = list(
        evaluate_dataset_influence(
            [
                _fm(
                    dataset_usage=[
                        {"ref": "dataset:unknown-a", "role": "analyzed"},
                        {"ref": "dataset:unknown-b", "role": "training"},
                    ]
                )
            ],
            dataset_ref_status={
                "dataset:unknown-a": "unavailable",
                "dataset:unknown-b": "missing",
            },
            row_usage_refs=[],
        )
    )

    assert _rules(results) == [
        (Severity.INFO, "dataset-influence.ref-unresolved-unavailable"),
        (Severity.WARN, "dataset-influence.ref-unresolved"),
    ]
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run --frozen pytest science/tests/validate/test_checks_dataset_influence.py -q
```

Expected: FAIL because the check module does not exist.

- [ ] **Step 3: Implement pure check core**

Create `science/src/science_tool/validate/checks/dataset_influence.py`:

```python
"""Dataset influence/provenance checks for Pillar B1."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any, Literal

from science_tool.validate.checks import Check
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Result, Severity

DatasetRefStatus = Literal["resolved", "missing", "unavailable"]
_ROLES = ("analyzed", "set_definition_source", "validation_source", "cited", "upstream", "training")
_OVERLAPS = ("full", "partial", "unknown")


def _result(severity: Severity, path: str | None, message: str, rule: str) -> Result:
    return Result(severity, Path(path) if path else None, None, message, rule, None)


def _usage_defect(entry: Any) -> str | None:
    if not isinstance(entry, dict):
        return "entry is not an object"
    ref = entry.get("ref")
    if not isinstance(ref, str) or not ref.startswith("dataset:"):
        return "ref must be a 'dataset:' reference"
    if entry.get("role") not in _ROLES:
        return f"role must be one of {list(_ROLES)}"
    overlap = entry.get("overlap")
    if overlap is not None and overlap not in _OVERLAPS:
        return f"overlap must be one of {list(_OVERLAPS)}"
    return None


def _iter_usage_entries(fm: dict[str, Any]) -> tuple[list[dict[str, Any]], str | None]:
    usage = fm.get("dataset_usage")
    if usage is None:
        return [], None
    if not isinstance(usage, list):
        return [], f"dataset_usage must be a list, got {type(usage).__name__}"
    entries: list[dict[str, Any]] = []
    for index, entry in enumerate(usage):
        defect = _usage_defect(entry)
        if defect is not None:
            return [], f"dataset_usage[{index}] malformed -- {defect}"
        entries.append(entry)
    return entries, None


def evaluate_dataset_influence(
    frontmatters: Iterable[dict[str, Any]],
    *,
    dataset_ref_status: dict[str, DatasetRefStatus],
    row_usage_refs: Iterable[tuple[str, str, str]],
) -> Iterator[Result]:
    refs_to_check: list[tuple[str, str, str]] = []
    for fm in frontmatters:
        ident = str(fm.get("id") or "?")
        path = fm.get("_path")
        kind = fm.get("kind") or fm.get("type")
        usage_entries, defect = _iter_usage_entries(fm)
        if defect is not None:
            yield _result(
                Severity.ERROR,
                path,
                f"{ident}: {defect}",
                "dataset-influence.dataset-usage-malformed",
            )
            continue

        for entry in usage_entries:
            ref = str(entry["ref"])
            if kind == "dataset" and ref == ident:
                yield _result(
                    Severity.ERROR,
                    path,
                    f"{ident}: dataset_usage must not reference itself",
                    "dataset-influence.self-reference",
                )
                continue
            refs_to_check.append((ref, ident, str(path or "")))

        derivation = fm.get("derivation")
        if kind == "dataset" and isinstance(derivation, dict):
            inputs = derivation.get("inputs")
            if isinstance(inputs, list):
                for ref in inputs:
                    if isinstance(ref, str) and ref == ident:
                        yield _result(
                            Severity.ERROR,
                            path,
                            f"{ident}: derivation.inputs must not reference itself",
                            "dataset-influence.self-reference",
                        )
                    elif isinstance(ref, str) and ref.startswith("dataset:"):
                        refs_to_check.append((ref, ident, str(path or "")))

        if kind == "paper":
            raw_datasets = fm.get("datasets") or []
            if raw_datasets and not isinstance(raw_datasets, list):
                yield _result(
                    Severity.ERROR,
                    path,
                    f"{ident}: datasets must be a list of dataset: refs",
                    "dataset-influence.paper-datasets-invalid",
                )
                continue
            explicit_by_ref = {str(entry["ref"]): entry for entry in usage_entries}
            for ref in raw_datasets:
                if not isinstance(ref, str) or not ref.startswith("dataset:"):
                    yield _result(
                        Severity.ERROR,
                        path,
                        f"{ident}: paper.datasets entry {ref!r} is not a dataset: ref",
                        "dataset-influence.paper-datasets-invalid",
                    )
                    continue
                if ref in explicit_by_ref:
                    entry = explicit_by_ref[ref]
                    if entry.get("role") != "analyzed":
                        yield _result(
                            Severity.WARN,
                            path,
                            f"{ident}: paper.datasets {ref!r} conflicts with explicit dataset_usage; explicit entry materializes",
                            "dataset-influence.paper-datasets-conflict",
                        )
                    continue
                yield _result(
                    Severity.WARN,
                    path,
                    f"{ident}: legacy paper.datasets {ref!r} should migrate to dataset_usage",
                    "dataset-influence.paper-datasets-legacy",
                )
                refs_to_check.append((ref, ident, str(path or "")))

    refs_to_check.extend(row_usage_refs)
    for ref, consumer, path in refs_to_check:
        status = dataset_ref_status.get(ref, "missing")
        if status == "resolved":
            continue
        if status == "unavailable":
            yield _result(
                Severity.INFO,
                path,
                f"{consumer}: dataset ref {ref!r} cannot be checked because registry resources are unavailable",
                "dataset-influence.ref-unresolved-unavailable",
            )
        else:
            yield _result(
                Severity.WARN,
                path,
                f"{consumer}: dataset ref {ref!r} does not resolve to a local or commons dataset",
                "dataset-influence.ref-unresolved",
            )


@Check(section="dataset influence", order=35)
def check_dataset_influence(ctx: ValidateContext) -> Iterator[Result]:
    return iter(())
```

- [ ] **Step 4: Run pure tests**

Run:

```bash
uv run --frozen pytest science/tests/validate/test_checks_dataset_influence.py -q
```

Expected: PASS for the pure tests.

- [ ] **Step 5: Commit**

```bash
git add science/src/science_tool/validate/checks/dataset_influence.py science/tests/validate/test_checks_dataset_influence.py
git commit -m "feat: add dataset influence check core"
```

---

### Task 8: Validate Check Runner And Registration

**Files:**
- Modify: `science/src/science_tool/validate/checks/dataset_influence.py`
- Modify: `science/src/science_tool/validate/checks/__init__.py`
- Modify parity lists:
  - `science/scripts/update-validate-snapshots.py`
  - `science/tests/validate/test_formatter_snapshots.py`
  - `science/tests/validate/test_parity_corpus.py`
  - `science/tests/validate/test_parity_canonical_body.py`
- Test: `science/tests/validate/test_checks_dataset_influence.py`
- Test: `science/tests/validate/test_runner.py`

- [ ] **Step 1: Add failing runner tests**

Append to `science/tests/validate/test_checks_dataset_influence.py`:

```python
import importlib
import pytest

from science_tool.validate.checks import CANONICAL_CHECKS, clear_checks_for_tests
from science_tool.validate.context import ValidateContext


_MANIFEST = "name: demo\nknowledge_profiles:\n  local: local\n"


def _ctx(root: Path) -> ValidateContext:
    return ValidateContext.from_project_root(root, strict=False, verbose=False)


def _write_project(root: Path) -> None:
    (root / "science.yaml").write_text(_MANIFEST, encoding="utf-8")


def test_check_dataset_influence_resolves_local_dataset_ref(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from science_tool.validate.checks.dataset_influence import check_dataset_influence

    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(tmp_path / "empty-commons"))
    _write_project(tmp_path)
    (tmp_path / "doc" / "papers").mkdir(parents=True)
    (tmp_path / "doc" / "papers" / "Adams2025.md").write_text(
        "---\nid: paper:Adams2025\ntype: paper\ntitle: Adams\ndataset_usage:\n"
        "  - ref: dataset:gtex-v8\n    role: analyzed\n---\n",
        encoding="utf-8",
    )
    dp_dir = tmp_path / "data" / "gtex"
    dp_dir.mkdir(parents=True)
    (dp_dir / "datapackage.yaml").write_text(
        "profiles: [science-pkg-entity-1.0]\nid: dataset:gtex-v8\ntype: dataset\ntitle: GTEx\n"
        "origin: external\ntier: use-now\ndatapackage: datapackage.yaml\naccess: {level: public, verified: true}\n",
        encoding="utf-8",
    )

    assert list(check_dataset_influence(_ctx(tmp_path))) == []


def test_check_dataset_influence_unbuilt_commons_ref_infos(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from science_tool.validate.checks.dataset_influence import check_dataset_influence

    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(tmp_path / "missing-commons"))
    _write_project(tmp_path)
    (tmp_path / "doc" / "papers").mkdir(parents=True)
    (tmp_path / "doc" / "papers" / "Adams2025.md").write_text(
        "---\nid: paper:Adams2025\ntype: paper\ntitle: Adams\ndataset_usage:\n"
        "  - ref: dataset:gtex-v8\n    role: analyzed\n---\n",
        encoding="utf-8",
    )

    results = list(check_dataset_influence(_ctx(tmp_path)))

    assert _rules(results) == [(Severity.INFO, "dataset-influence.ref-unresolved-unavailable")]


def test_dataset_influence_registration_after_genesets() -> None:
    clear_checks_for_tests()

    import science_tool.validate.checks.dataset_influence as dataset_influence
    import science_tool.validate.checks.genesets as genesets

    importlib.reload(genesets)
    importlib.reload(dataset_influence)

    ordered = [(entry.section, entry.order, entry.fn.__module__) for entry in CANONICAL_CHECKS]
    genesets_index = next(index for index, entry in enumerate(ordered) if entry[0] == "gene-set collections")
    influence_index = next(index for index, entry in enumerate(ordered) if entry[0] == "dataset influence")
    assert influence_index == genesets_index + 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run --frozen pytest science/tests/validate/test_checks_dataset_influence.py -q
```

Expected: FAIL because the runner returns no results and the canonical loader does not import `dataset_influence`.

- [ ] **Step 3: Implement ref status and row refs in runner**

In `science/src/science_tool/validate/checks/dataset_influence.py`, add imports:

```python
from science_tool.commons.adapter import CommonsEntityAdapter
from science_tool.commons.config import resolve_commons_root
from science_tool.commons.errors import CommonsError
from science_tool.commons.geneset import GenesetCollectionError, parse_geneset_rows
from science_tool.commons.geneset_resources import is_geneset_frontmatter, read_member_rows
from science_tool.validate._helpers import dataset_frontmatters, entity_frontmatters
```

Add helpers:

```python
def _dataset_ref_statuses(ctx: ValidateContext, refs: set[str]) -> dict[str, DatasetRefStatus]:
    local_ids = {
        str(fm["id"])
        for fm in dataset_frontmatters(ctx)
        if isinstance(fm.get("id"), str) and fm["id"]
    }
    root = resolve_commons_root()
    commons_available = root.is_dir()
    adapter = CommonsEntityAdapter(root) if commons_available else None
    out: dict[str, DatasetRefStatus] = {}
    for ref in refs:
        if ref in local_ids:
            out[ref] = "resolved"
            continue
        if adapter is None:
            out[ref] = "unavailable"
            continue
        try:
            record = adapter.load(ref)
        except CommonsError:
            out[ref] = "missing"
            continue
        kind = record.frontmatter.get("kind") or record.frontmatter.get("type")
        out[ref] = "resolved" if kind == "dataset" else "missing"
    return out


def _collect_refs(frontmatters: list[dict[str, Any]], row_usage_refs: list[tuple[str, str, str]]) -> set[str]:
    refs = {ref for ref, _consumer, _path in row_usage_refs}
    for fm in frontmatters:
        usage = fm.get("dataset_usage")
        if isinstance(usage, list):
            for entry in usage:
                if isinstance(entry, dict) and isinstance(entry.get("ref"), str):
                    refs.add(entry["ref"])
        datasets = fm.get("datasets")
        if isinstance(datasets, list):
            refs.update(ref for ref in datasets if isinstance(ref, str) and ref.startswith("dataset:"))
        derivation = fm.get("derivation")
        if isinstance(derivation, dict) and isinstance(derivation.get("inputs"), list):
            refs.update(ref for ref in derivation["inputs"] if isinstance(ref, str) and ref.startswith("dataset:"))
    return refs


def _row_usage_refs(ctx: ValidateContext, frontmatters: list[dict[str, Any]]) -> list[tuple[str, str, str]]:
    refs: list[tuple[str, str, str]] = []
    for fm in frontmatters:
        if not is_geneset_frontmatter(fm):
            continue
        ident = fm.get("id")
        path = str(fm.get("_path") or "")
        if not isinstance(ident, str) or not ident:
            continue
        raw_rows = read_member_rows(ctx.project_root, fm)
        if raw_rows is None or isinstance(raw_rows, Exception):
            continue
        try:
            rows = parse_geneset_rows(raw_rows)
        except GenesetCollectionError:
            continue
        for row in rows:
            for usage in row.dataset_usage:
                refs.append((str(usage["ref"]), f"{ident}#{row.set_key}", path))
    return refs
```

Replace the runner with:

```python
@Check(section="dataset influence", order=35)
def check_dataset_influence(ctx: ValidateContext) -> Iterator[Result]:
    frontmatters = entity_frontmatters(ctx)
    row_refs = _row_usage_refs(ctx, frontmatters)
    statuses = _dataset_ref_statuses(ctx, _collect_refs(frontmatters, row_refs))
    yield from evaluate_dataset_influence(
        frontmatters,
        dataset_ref_status=statuses,
        row_usage_refs=row_refs,
    )
```

- [ ] **Step 4: Register check and parity mirrors**

In `science/src/science_tool/validate/checks/__init__.py`, insert `"dataset_influence"` immediately after `"genesets"` in the import tuple. The check's `@Check(..., order=35)` registration makes it last in the sorted canonical check sequence, immediately after `genesets` at order 34.

In each `CHECK_MODULES` tuple in the parity files, insert `"dataset_influence"` after `"genesets"`:

```python
    "genesets",
    "dataset_influence",
```

- [ ] **Step 5: Run validate tests**

Run:

```bash
uv run --frozen pytest science/tests/validate/test_checks_dataset_influence.py science/tests/validate/test_runner.py science/tests/validate/test_formatter_snapshots.py science/tests/validate/test_parity_corpus.py science/tests/validate/test_parity_canonical_body.py -q
```

Expected: PASS. If snapshot tests fail only because the canonical section list includes the new check, update snapshots with the existing project command:

```bash
uv run --frozen python science/scripts/update-validate-snapshots.py
```

Then rerun the same pytest command and require PASS.

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/validate/checks/dataset_influence.py science/src/science_tool/validate/checks/__init__.py science/scripts/update-validate-snapshots.py science/tests/validate/test_checks_dataset_influence.py science/tests/validate/test_runner.py science/tests/validate/test_formatter_snapshots.py science/tests/validate/test_parity_corpus.py science/tests/validate/test_parity_canonical_body.py science/tests/validate/snapshots/json_default.json science/tests/validate/snapshots/text_default.txt
git commit -m "feat: validate dataset influence provenance"
```

---

### Task 9: Strict Graph Failure Coverage

**Files:**
- Modify: `science/tests/test_dataset_usage_materialize.py`
- Modify: `science/src/science_tool/graph/dataset_usage.py`
- Modify: `science/src/science_tool/graph/materialize.py`

- [ ] **Step 1: Add failing strictness tests**

Append to `science/tests/test_dataset_usage_materialize.py`:

```python
def test_materialize_graph_rejects_dataset_usage_self_reference(tmp_path):
    _write_project(tmp_path)
    _write_dataset(
        tmp_path / "data" / "self" / "datapackage.yaml",
        "self",
        "dataset_usage:\n"
        "  - ref: dataset:self\n"
        "    role: analyzed\n",
    )

    with pytest.raises(ValueError, match="self-referential"):
        materialize_graph(tmp_path)


def test_virtual_member_uri_normalizes_nfc() -> None:
    from science_tool.graph.dataset_usage import virtual_geneset_member_uri

    composed = virtual_geneset_member_uri("dataset:reactome-v89", "é")
    decomposed = virtual_geneset_member_uri("dataset:reactome-v89", "e\u0301")

    assert composed == decomposed
```

- [ ] **Step 2: Run tests**

Run:

```bash
uv run --frozen pytest science/tests/test_dataset_usage_materialize.py::test_materialize_graph_rejects_dataset_usage_self_reference science/tests/test_dataset_usage_materialize.py::test_virtual_member_uri_normalizes_nfc -q
```

Expected: PASS if prior tasks already implemented strictness and NFC normalization. If either fails, fix only the failing helper path:

```python
normalized = unicodedata.normalize("NFC", value)
```

and:

```python
raise DatasetUsageMaterializationError(...)
```

- [ ] **Step 3: Run focused graph suite**

Run:

```bash
uv run --frozen pytest science/tests/test_dataset_usage_materialize.py science/tests/test_graph_materialize.py -q
```

Expected: PASS.

- [ ] **Step 4: Commit**

If Task 9 changed files:

```bash
git add science/tests/test_dataset_usage_materialize.py science/src/science_tool/graph/dataset_usage.py science/src/science_tool/graph/materialize.py
git commit -m "test: cover strict dataset usage materialization"
```

If Task 9 did not change files:

```bash
git status --short
```

Expected: no staged changes from Task 9.

---

### Task 10: Documentation Status And Migration Note

**Files:**
- Modify: `docs/plans/2026-05-26-bio-dataset-influence-provenance-design.md`
- Modify: `docs/plans/2026-05-26-bio-data-architecture-umbrella-design.md`

- [ ] **Step 1: Update design status**

In `docs/plans/2026-05-26-bio-dataset-influence-provenance-design.md`, change the status line to:

```markdown
Status: B1 implemented locally; B-migration and B2 deferred
```

In section 10, change the B1 row status to:

```markdown
| B1 — additive `dataset_usage` transition for papers, usage-node graph materialization, `derivation.inputs` projection, legacy `paper.datasets` warnings, influence-query groundwork | authored-to-graph provenance layer | implemented locally |
```

In section 11, replace the next-step paragraph with:

```markdown
Pillar B1 is implemented as an authored-to-graph provenance layer. The next B work is the
B-migration mechanical conversion from `paper.datasets` to `paper.dataset_usage`, followed by
B2 candidate/committed independence derivation.
```

- [ ] **Step 2: Update umbrella status**

In `docs/plans/2026-05-26-bio-data-architecture-umbrella-design.md`, update the Pillar B row or status note to say B1 is implemented locally and B-migration/B2 remain open.

- [ ] **Step 3: Verify docs have no Dropbox-local paths**

Run:

```bash
rg -n 'Dropbox' docs/plans/2026-05-26-bio-dataset-influence-provenance-design.md docs/plans/2026-05-26-bio-data-architecture-umbrella-design.md
```

Expected: no output.

- [ ] **Step 4: Commit**

```bash
git add docs/plans/2026-05-26-bio-dataset-influence-provenance-design.md docs/plans/2026-05-26-bio-data-architecture-umbrella-design.md
git commit -m "docs: mark B1 dataset influence implemented"
```

---

### Task 11: Full Verification

**Files:**
- No planned code edits.

- [ ] **Step 1: Run focused affected suite**

Run:

```bash
uv run --frozen pytest science/model/tests/test_entity_schema_mixin_paper.py science/model/tests/test_entity_schema_mixin_dataset.py science/tests/test_commons_geneset.py science/tests/validate/test_checks_genesets.py science/tests/validate/test_helpers_dataset_discovery.py science/tests/validate/test_checks_dataset_influence.py science/tests/test_dataset_usage_materialize.py -q
```

Expected: PASS.

- [ ] **Step 2: Run graph and validate regression slice**

Run:

```bash
uv run --frozen pytest science/tests/test_graph_materialize.py science/tests/validate/test_runner.py science/tests/validate/test_formatter_snapshots.py science/tests/validate/test_parity_corpus.py science/tests/validate/test_parity_canonical_body.py -q
```

Expected: PASS.

- [ ] **Step 3: Run full test suite**

Run:

```bash
uv run --frozen pytest science/tests/ science/model/tests/ -q
```

Expected: PASS.

- [ ] **Step 4: Check formatting and diff hygiene**

Run:

```bash
uv run --frozen ruff check science/src/science_tool/graph/dataset_usage.py science/src/science_tool/validate/checks/dataset_influence.py science/src/science_tool/commons/geneset_resources.py science/tests/test_dataset_usage_materialize.py science/tests/validate/test_checks_dataset_influence.py
git diff --check
git status --short
```

Expected:
- `ruff check` exits 0.
- `git diff --check` exits 0.
- `git status --short` is clean after all task commits.

---

## Self-Review Checklist

- Spec coverage:
  - Base/schema exposure: Task 1.
  - Additive `paper.datasets` transition and per-ref union: Tasks 4, 7, 8.
  - Reified usage nodes and graph predicates: Tasks 4, 5.
  - D1 gene-set row usage with strict graph build: Tasks 2, 6, 9.
  - Validate severities: Tasks 7, 8.
  - Self-reference guard: Tasks 4, 7, 9.
  - B2 most-dependent-wins handoff: design doc only; B2 is not implemented in B1.
  - Migration to single system: Task 10 documents the next B-migration phase.
- No B1 task changes `aggregate_belief`, `shared_dataset`, `independence_group`, or `suspect-circular`.
- No permanent compatibility layer is introduced; `paper.datasets` remains named transition input with warning coverage.
- The optional `consumed_by` staleness check is explicitly out of this implementation plan because it requires a reverse usage index and has a separate cost profile.

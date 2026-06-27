# Benchmark Catalog V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add v1 benchmark-capable dataset metadata, validation, query/reporting, commons seed records, and the `/science:catalog-benchmarks` command guide.

**Architecture:** Benchmarks remain an optional `benchmark` block on `dataset:*` entities. `science_model` owns typed parsing and schema validation; `science_tool` owns raw-frontmatter validation and read-only CLI reports; commons stores shared seed dataset entities without adding graph edges or belief scoring in v1.

**Tech Stack:** Python 3.13, Pydantic v2, Click/Rich CLI, JSON Schema, pytest, commons entity registry.

---

## Scope

This plan implements Phase 1 only:

- typed `BenchmarkBlock` and `BenchmarkTask` model support;
- JSON schema support for `benchmark` on dataset mixin records;
- raw-frontmatter validation for benchmark metadata;
- read-only `science benchmark list` with facet summary;
- `/science:catalog-benchmarks` guidance;
- shared commons seed records for the biology/omics stress set.

This plan does not implement graph-aware belief mapping, `science benchmark gaps`, `science benchmark tests`, benchmark outcomes, or proposition/evidence graph updates. Those are Phase 2/3 surfaces in `docs/plans/2026-06-26-benchmark-grounded-model-assessment-design.md`.

## Files

- Modify: `science/model/src/science_model/packages/schema.py`  
  Add Pydantic `BenchmarkTask` and `BenchmarkBlock`.
- Modify: `science/model/src/science_model/entities.py`  
  Add `benchmark: BenchmarkBlock | None` on `Entity`, gated to dataset kind.
- Modify: `science/model/src/science_model/frontmatter.py`  
  Coerce raw YAML `benchmark:` into `BenchmarkBlock`.
- Modify: `science/model/src/science_model/schemas/mixin-dataset-1.0.json`  
  Add optional `benchmark` object schema.
- Modify: `science/model/tests/test_dataset_models.py`  
  Model and parser tests.
- Modify: `science/model/tests/test_entity_schema_mixin_dataset.py`  
  JSON schema tests.
- Create: `science/src/science_tool/validate/checks/benchmark_metadata.py`  
  Raw-frontmatter benchmark validation check.
- Modify: `science/src/science_tool/validate/checks/__init__.py`  
  Register the validation check.
- Create: `science/tests/validate/test_checks_benchmark_metadata.py`  
  Validation check tests.
- Create: `science/src/science_tool/benchmark_catalog.py`  
  Query helpers, filters, and facet summary.
- Modify: `science/src/science_tool/cli.py`  
  Add `science benchmark list`.
- Create: `science/tests/test_benchmark_cli.py`  
  CLI tests.
- Modify: `science/tests/test_commons_inventory.py`  
  Confirm benchmark metadata projects through commons inventory.
- Modify or create in `~/d/science-commons/`: `datasets/<slug>/entity.md` for the seed benchmark records.
- Create: `commands/catalog-benchmarks.md`  
  Agent command guidance for v1 discovery/classification/facet coverage.

## Execution Preflight

- [ ] **Step 1: Create an isolated worktree**

Run from `~/d/science`:

```bash
rtk git worktree add .worktrees/benchmark-catalog-v1 -b benchmark-catalog-v1
cd .worktrees/benchmark-catalog-v1
```

Expected: a clean feature worktree on branch `benchmark-catalog-v1`.

- [ ] **Step 2: Verify the baseline**

```bash
rtk git status --short
rtk uv run --frozen pytest science/model/tests/test_dataset_models.py science/model/tests/test_entity_schema_mixin_dataset.py -q
rtk uv run --frozen pytest science/tests/validate/test_checks_dataset_metadata.py science/tests/test_dataset_prioritize.py science/tests/test_dataset_prioritize_cli.py -q
```

Expected: `git status` prints no changed files; the targeted baseline tests pass.

---

### Task 1: Typed Benchmark Metadata Model

**Files:**
- Modify: `science/model/src/science_model/packages/schema.py`
- Modify: `science/model/src/science_model/entities.py`
- Modify: `science/model/src/science_model/frontmatter.py`
- Test: `science/model/tests/test_dataset_models.py`

- [ ] **Step 1: Write failing model tests**

In `science/model/tests/test_dataset_models.py`, update the import:

```python
from science_model.packages.schema import (
    AccessBlock,
    AccessException,
    BenchmarkBlock,
    BenchmarkTask,
    DatasetUsage,
    DerivationBlock,
    GroundTruth,
)
```

Add these tests after `TestDerivationBlock`:

```python
class TestBenchmarkBlock:
    def test_sparse_facets_only_block_is_valid(self) -> None:
        block = BenchmarkBlock(
            domains=["biology"],
            modalities=["single-cell-rna-seq"],
            signal_types=["perturbation"],
            benchmark_kinds=["perturbation-response"],
            related_beliefs=["hypothesis:h1"],
            limitations=["No held-out task definition yet."],
        )

        assert block.domains == ["biology"]
        assert block.tasks == []

    def test_task_carries_core_evaluation_fields(self) -> None:
        task = BenchmarkTask(
            id="drug-response",
            task_type="response-prediction",
            prediction_target="post-treatment expression signature",
            held_out_unit="compound",
            metric="rank correlation",
            baseline="untreated profile",
            ground_truth=GroundTruth(type="measured-outcome", description="expression state"),
            interpretation_limits=["L1000 landmark genes only."],
            timepoints=["24h"],
            contexts=["A549 cell line"],
        )

        assert task.held_out_unit == "compound"
        assert task.ground_truth is not None
        assert task.timepoints == ["24h"]

    def test_task_id_must_be_slug_like(self) -> None:
        with pytest.raises(ValueError, match="tasks.id"):
            BenchmarkTask(id="Bad Task", task_type="classification")

    def test_duplicate_task_ids_are_rejected(self) -> None:
        with pytest.raises(ValueError, match="duplicate benchmark task id"):
            BenchmarkBlock(
                benchmark_kinds=["perturbation-response"],
                tasks=[
                    BenchmarkTask(id="drug-response", task_type="prediction"),
                    BenchmarkTask(id="drug-response", task_type="ranking"),
                ],
            )
```

Add this parser test near the existing parse tests:

```python
def test_parse_dataset_benchmark_block(tmp_path: Path) -> None:
    md = _write_dataset_md(
        tmp_path,
        "benchmark:",
        "  domains: [biology]",
        "  modalities: [single-cell-rna-seq]",
        "  signal_types: [perturbation]",
        "  benchmark_kinds: [perturbation-response]",
        "  source_datasets: ['GEO:GSE000']",
        "  related_beliefs: [hypothesis:h1]",
        "  limitations:",
        "    - Landmark genes only.",
        "  tasks:",
        "    - id: drug-response",
        "      task_type: response-prediction",
        "      prediction_target: post-treatment expression signature",
        "      held_out_unit: compound",
        "      metric: rank correlation",
        "      baseline: untreated profile",
        "      ground_truth:",
        "        type: measured-outcome",
        "        description: post-perturbation expression state",
        "      intervention: drug dose",
        "      timepoints: ['24h']",
        "      contexts: ['A549 cell line']",
        "      interpretation_limits:",
        "        - L1000 landmark genes only.",
    )

    entity = parse_entity_file(md, project_slug="testproj")

    assert entity.benchmark is not None
    assert entity.benchmark.benchmark_kinds == ["perturbation-response"]
    assert entity.benchmark.limitations == ["Landmark genes only."]
    task = entity.benchmark.tasks[0]
    assert task.id == "drug-response"
    assert task.held_out_unit == "compound"
    assert task.timepoints == ["24h"]
    assert task.ground_truth is not None and task.ground_truth.type == "measured-outcome"
```

- [ ] **Step 2: Run tests and verify they fail**

```bash
rtk uv run --frozen pytest science/model/tests/test_dataset_models.py -q -k "BenchmarkBlock or benchmark_block"
```

Expected: FAIL because `BenchmarkBlock`, `BenchmarkTask`, and `Entity.benchmark` do not exist.

- [ ] **Step 3: Implement Pydantic model types**

In `science/model/src/science_model/packages/schema.py`, add `import re` below the module docstring imports:

```python
import re
```

Add these classes after `DatasetUsage`:

```python
_BENCHMARK_TASK_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,63}$")


class GroundTruth(BaseModel):
    """What a benchmark task treats as ground truth."""

    type: str = ""
    description: str = ""


class BenchmarkTask(BaseModel):
    """A locally named evaluation task inside a dataset benchmark block.

    The required fields to make a task an actual *test* are ``prediction_target``
    (what the model predicts) and ``held_out_unit`` (what is withheld). v1 keeps
    them as free-text; vocabularies promote to enums in a later phase.
    """

    id: str
    task_type: str = ""
    prediction_target: str = ""
    held_out_unit: str = ""
    metric: str = ""
    baseline: str = ""
    ground_truth: GroundTruth | None = None
    interpretation_limits: list[str] = Field(default_factory=list)
    # optional structure-specific fields (free-text v1)
    intervention: str = ""
    timepoints: list[str] = Field(default_factory=list)
    contexts: list[str] = Field(default_factory=list)

    @field_validator("id")
    @classmethod
    def _validate_id(cls, value: str) -> str:
        if not _BENCHMARK_TASK_ID_RE.fullmatch(value):
            raise ValueError("tasks.id must be lowercase kebab-case, 2-64 characters")
        return value


class BenchmarkBlock(BaseModel):
    """Benchmark-capable dataset metadata.

    V1 keeps vocabularies as free-text strings. Later phases can promote stable
    terms to enums once seed records show which facets actually recur.
    """

    domains: list[str] = Field(default_factory=list)
    modalities: list[str] = Field(default_factory=list)
    signal_types: list[str] = Field(default_factory=list)
    benchmark_kinds: list[str] = Field(default_factory=list)
    source_datasets: list[str] = Field(default_factory=list)
    related_beliefs: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    tasks: list[BenchmarkTask] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_unique_task_ids(self) -> "BenchmarkBlock":
        seen: set[str] = set()
        duplicates: set[str] = set()
        for task in self.tasks:
            if task.id in seen:
                duplicates.add(task.id)
            seen.add(task.id)
        if duplicates:
            ordered = ", ".join(sorted(duplicates))
            raise ValueError(f"duplicate benchmark task id: {ordered}")
        return self
```

- [ ] **Step 4: Add benchmark to the entity model**

In `science/model/src/science_model/entities.py`, add `BenchmarkBlock` to the package schema imports:

```python
from science_model.packages.schema import (
    AccessBlock,
    BenchmarkBlock,
    DatasetUsage,
    DerivationBlock,
    MemberOfDerivationBlock,
    WorkflowRecipeDerivationBlock,
)
```

Add this field as the **final field declaration** on `Entity` (append after the
last existing field, not mid-class), so `model_dump` key order is unchanged for
existing entities and snapshot/golden output for non-dataset entities is
unaffected:

```python
    benchmark: BenchmarkBlock | None = None
```

In `Entity._validate_dataset_taxonomy`, add this explicit dataset-only gate
immediately after the existing `if self.kind != "dataset": return self` guard, so
it uses the same string comparison the method already relies on (entities.py:287
— `self.kind` is a plain string, not an `EntityType`):

```python
        # placed after the early `if self.kind != "dataset": return self` guard,
        # so by here self.kind == "dataset"; the inverse guard for non-datasets:
        if self.kind != "dataset" and self.benchmark is not None:
            raise ValueError(f"{self.id}: benchmark metadata is only valid on dataset entities")
```

Note: because the guard sits before the `kind != "dataset"` early return, write
the non-dataset check as its own statement at the top of the method (before that
early return), e.g.:

```python
    def _validate_dataset_taxonomy(self) -> "Entity":
        if self.kind != "dataset":
            if self.benchmark is not None:
                raise ValueError(f"{self.id}: benchmark metadata is only valid on dataset entities")
            return self
        ...  # existing dataset-only checks unchanged
```

- [ ] **Step 5: Coerce frontmatter benchmark blocks**

In `science/model/src/science_model/frontmatter.py`, add `BenchmarkBlock` to the import from `science_model.packages.schema`:

```python
from science_model.packages.schema import (
    AccessBlock,
    AccessException,
    BenchmarkBlock,
    DerivationBlock,
    MemberOfDerivationBlock,
)
```

Add this helper near `_coerce_access`:

```python
def _coerce_benchmark(fm: dict) -> BenchmarkBlock | None:
    raw = fm.get("benchmark")
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ValueError("benchmark must be a mapping")
    return BenchmarkBlock.model_validate(raw)
```

Add this to `entity_kwargs` after `dataset_usage`:

```python
        "benchmark": _coerce_benchmark(fm) if kind == EntityType.DATASET.value else None,
```

Note (M1): on the parse path a `benchmark:` block authored on a non-dataset
entity is silently dropped (coerced to `None`), so the model taxonomy gate added
in Step 4 only fires for direct `Entity(...)` construction. This is acceptable
for v1 — the dataset mixin schema is where authored non-dataset benchmark blocks
get surfaced as a hard schema error — but do not expect the parse path to raise.

- [ ] **Step 6: Run model tests**

```bash
rtk uv run --frozen pytest science/model/tests/test_dataset_models.py -q -k "BenchmarkBlock or benchmark_block"
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
rtk git add science/model/src/science_model/packages/schema.py science/model/src/science_model/entities.py science/model/src/science_model/frontmatter.py science/model/tests/test_dataset_models.py
rtk git commit -m "feat(model): add benchmark metadata block to datasets"
```

---

### Task 2: Dataset Mixin JSON Schema

**Files:**
- Modify: `science/model/src/science_model/schemas/mixin-dataset-1.0.json`
- Test: `science/model/tests/test_entity_schema_mixin_dataset.py`

- [ ] **Step 1: Write failing schema tests**

Add these tests to `science/model/tests/test_entity_schema_mixin_dataset.py` after `test_dataset_class_vocabulary`:

```python
def test_dataset_benchmark_block_validates(base_entity: dict) -> None:
    entity = base_entity | {
        "origin": "external",
        "access": {"level": "public", "verified": True},
        "benchmark": {
            "domains": ["biology"],
            "modalities": ["single-cell-rna-seq"],
            "signal_types": ["perturbation"],
            "benchmark_kinds": ["perturbation-response"],
            "source_datasets": ["GEO:GSE000"],
            "related_beliefs": ["hypothesis:h1"],
            "limitations": ["Small molecule perturbations only."],
            "tasks": [
                {
                    "id": "drug-response",
                    "task_type": "response-prediction",
                    "prediction_target": "post-treatment expression signature",
                    "held_out_unit": "compound",
                    "metric": "auroc",
                    "baseline": "mean-expression",
                    "ground_truth": {"type": "measured-outcome", "description": "expression state"},
                    "interpretation_limits": ["Landmark genes only."],
                    "intervention": "compound dose",
                    "timepoints": ["24h"],
                    "contexts": ["A549 cell line"],
                }
            ],
        },
    }

    EntityValidator().validate(entity)


def test_dataset_benchmark_task_id_pattern_rejected(base_entity: dict) -> None:
    entity = base_entity | {
        "origin": "external",
        "access": {"level": "public", "verified": True},
        "benchmark": {
            "benchmark_kinds": ["perturbation-response"],
            "tasks": [{"id": "Bad Task", "task_type": "response-prediction"}],
        },
    }

    with pytest.raises(EntityValidationError, match="benchmark"):
        EntityValidator().validate(entity)
```

- [ ] **Step 2: Run tests and verify they fail**

```bash
rtk uv run --frozen pytest science/model/tests/test_entity_schema_mixin_dataset.py -q -k "benchmark"
```

Expected: FAIL because `benchmark` is not recognized by the dataset mixin schema.

- [ ] **Step 3: Add the schema property**

In `science/model/src/science_model/schemas/mixin-dataset-1.0.json`, add this property after `derived_kind`:

```json
    "derived_kind": {"enum": ["aggregate", "transform", "model_output"]},
    "benchmark": {"$ref": "#/$defs/benchmark"}
```

Add these definitions inside `$defs`, before `access`:

```json
    "benchmark": {
      "type": "object",
      "properties": {
        "domains": {"type": "array", "items": {"type": "string"}},
        "modalities": {"type": "array", "items": {"type": "string"}},
        "signal_types": {"type": "array", "items": {"type": "string"}},
        "benchmark_kinds": {"type": "array", "items": {"type": "string"}},
        "source_datasets": {"type": "array", "items": {"type": "string"}},
        "related_beliefs": {"type": "array", "items": {"type": "string"}},
        "notes": {"type": "array", "items": {"type": "string"}},
        "limitations": {"type": "array", "items": {"type": "string"}},
        "tasks": {"type": "array", "items": {"$ref": "#/$defs/benchmark_task"}}
      }
    },
    "benchmark_task": {
      "type": "object",
      "required": ["id"],
      "properties": {
        "id": {"type": "string", "pattern": "^[a-z0-9][a-z0-9-]{1,63}$"},
        "task_type": {"type": "string"},
        "prediction_target": {"type": "string"},
        "held_out_unit": {"type": "string"},
        "metric": {"type": "string"},
        "baseline": {"type": "string"},
        "ground_truth": {
          "type": "object",
          "properties": {
            "type": {"type": "string"},
            "description": {"type": "string"}
          }
        },
        "interpretation_limits": {"type": "array", "items": {"type": "string"}},
        "intervention": {"type": "string"},
        "timepoints": {"type": "array", "items": {"type": "string"}},
        "contexts": {"type": "array", "items": {"type": "string"}}
      }
    },
```

Keep `benchmark` without a `science:merge` annotation so commons promotion treats the block as a replace/conflict field. That is intentional for v1: benchmark interpretation should be resolved explicitly when two projects disagree.

- [ ] **Step 4: Run schema tests**

```bash
rtk uv run --frozen pytest science/model/tests/test_entity_schema_mixin_dataset.py -q -k "benchmark or dataset_class"
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
rtk git add science/model/src/science_model/schemas/mixin-dataset-1.0.json science/model/tests/test_entity_schema_mixin_dataset.py
rtk git commit -m "feat(schema): allow benchmark metadata on dataset mixin"
```

---

### Task 3: Benchmark Metadata Validation

**Files:**
- Create: `science/src/science_tool/validate/checks/benchmark_metadata.py`
- Modify: `science/src/science_tool/validate/checks/__init__.py`
- Test: `science/tests/validate/test_checks_benchmark_metadata.py`

- [ ] **Step 1: Write failing validation tests**

Create `science/tests/validate/test_checks_benchmark_metadata.py`:

```python
from __future__ import annotations

from pathlib import Path

from science_tool.validate.result import Severity


def _load_checks_with_benchmark_metadata_fresh() -> None:
    import sys

    import science_tool.validate.checks as checks

    checks.clear_checks_for_tests()
    sys.modules.pop("science_tool.validate.checks.benchmark_metadata", None)
    checks._load_canonical_checks()


def _ds(**kw) -> dict:
    base = {
        "type": "dataset",
        "id": "dataset:x",
        "_path": "entities/datasets/x.md",
        "dataset_class": "deposit",
    }
    base.update(kw)
    return base


def _rules(datasets: list[dict]) -> list[tuple[Severity, str]]:
    from science_tool.validate.checks.benchmark_metadata import evaluate_benchmark_metadata

    return [(r.severity, r.rule) for r in evaluate_benchmark_metadata(datasets)]


def test_dataset_without_benchmark_is_ignored() -> None:
    assert _rules([_ds()]) == []


def test_duplicate_task_ids_are_errors() -> None:
    rules = _rules(
        [
            _ds(
                benchmark={
                    "benchmark_kinds": ["perturbation-response"],
                    "tasks": [
                        {"id": "drug-response", "task_type": "prediction"},
                        {"id": "drug-response", "task_type": "ranking"},
                    ],
                }
            )
        ]
    )

    assert (Severity.ERROR, "benchmark.task-id-duplicate") in rules


def test_invalid_task_id_is_error() -> None:
    rules = _rules([_ds(benchmark={"tasks": [{"id": "Bad Task"}]})])

    assert (Severity.ERROR, "benchmark.task-id-invalid") in rules


def test_task_missing_core_evaluation_fields_warns() -> None:
    rules = _rules(
        [
            _ds(
                benchmark={
                    "benchmark_kinds": ["static-association"],
                    "tasks": [{"id": "classification", "task_type": "classification"}],
                }
            )
        ]
    )

    assert (Severity.WARN, "benchmark.task-sparse") in rules


def test_facets_only_block_without_limitations_warns() -> None:
    rules = _rules([_ds(benchmark={"benchmark_kinds": ["static-association"]})])

    assert (Severity.WARN, "benchmark.facets-lack-task-or-limitation") in rules


def test_perturbation_benchmark_without_intervention_or_context_warns() -> None:
    rules = _rules(
        [
            _ds(
                benchmark={
                    "benchmark_kinds": ["perturbation-response"],
                    "tasks": [{"id": "drug-response", "task_type": "prediction", "metric": "auroc", "baseline": "mean"}],
                }
            )
        ]
    )

    assert (Severity.WARN, "benchmark.perturbation-context-missing") in rules


def test_time_series_benchmark_without_timepoints_warns() -> None:
    rules = _rules(
        [
            _ds(
                benchmark={
                    "benchmark_kinds": ["time-series"],
                    "tasks": [{"id": "trajectory", "task_type": "forecast", "metric": "rmse", "baseline": "last-value"}],
                }
            )
        ]
    )

    assert (Severity.WARN, "benchmark.timepoints-missing") in rules


def test_pointer_benchmark_block_is_info() -> None:
    rules = _rules(
        [
            _ds(
                dataset_class="pointer",
                benchmark={"benchmark_kinds": ["perturbation-response"], "limitations": "Tracked candidate only."},
            )
        ]
    )

    assert (Severity.INFO, "benchmark.pointer-block") in rules


def test_module_is_registered() -> None:
    from science_tool.validate.checks import CANONICAL_CHECKS

    _load_checks_with_benchmark_metadata_fresh()
    assert any(entry.fn.__module__.endswith("benchmark_metadata") for entry in CANONICAL_CHECKS)


def test_benchmark_validation_surfaces_through_runner(tmp_path: Path) -> None:
    from science_tool.validate.runner import run

    _load_checks_with_benchmark_metadata_fresh()
    (tmp_path / "science.yaml").write_text("name: demo\n", encoding="utf-8")
    ds_dir = tmp_path / "entities" / "datasets"
    ds_dir.mkdir(parents=True)
    (ds_dir / "x.md").write_text(
        "---\n"
        "id: dataset:x\n"
        "type: dataset\n"
        "title: X\n"
        "status: active\n"
        "origin: external\n"
        "dataset_class: deposit\n"
        "tier: use-now\n"
        "license: MIT\n"
        "access: {level: public, verified: true, verification_method: retrieved}\n"
        "datapackage: data/x/datapackage.json\n"
        "benchmark:\n"
        "  benchmark_kinds: [static-association]\n"
        "---\n"
        "body\n",
        encoding="utf-8",
    )

    result = run(tmp_path, profile="full")

    assert any(r.rule == "benchmark.facets-lack-task-or-limitation" for r in result.results)
```

- [ ] **Step 2: Run tests and verify they fail**

```bash
rtk uv run --frozen pytest science/tests/validate/test_checks_benchmark_metadata.py -q
```

Expected: FAIL because `science_tool.validate.checks.benchmark_metadata` does not exist.

- [ ] **Step 3: Implement the validation check**

Layering note (S3): the Pydantic model (Task 1) is the SSOT and **hard-raises**
on a malformed `tasks[].id` or duplicate ids (fail-early house style). This
validate check intentionally re-reports the same two conditions as graceful
`ERROR` results because it reads **raw frontmatter** via `dataset_frontmatters`
(matching `dataset_metadata.py`), which is the surface `science validate` uses and
which runs even when a sibling entity fails to parse. The two layers are
complementary, not redundant: the model protects in-process construction; the
check gives a file/line-attributed message in the validate report. Do not move id
validation out of the model.

Create `science/src/science_tool/validate/checks/benchmark_metadata.py`:

```python
"""Benchmark metadata checks for dataset entities."""

from __future__ import annotations

import re
from collections.abc import Iterable, Iterator, Mapping
from pathlib import Path
from typing import Any

from science_tool.datasets.semantics import dataset_class_for
from science_tool.validate._helpers import dataset_frontmatters
from science_tool.validate.checks import Check
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Result, Severity

_TASK_ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,63}$")


def _path(value: object) -> Path | None:
    if isinstance(value, Path):
        return value
    if isinstance(value, str) and value:
        return Path(value)
    return None


def _result(severity: Severity, path: object, message: str, rule: str) -> Result:
    return Result(severity=severity, path=_path(path), line=None, message=message, rule=rule, task=None)


def _nonempty(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def _task_list(value: object) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def evaluate_benchmark_metadata(datasets: Iterable[dict[str, Any]]) -> Iterator[Result]:
    for fm in datasets:
        if (fm.get("kind") or fm.get("type")) != "dataset":
            continue
        benchmark = fm.get("benchmark")
        if benchmark is None:
            continue

        path = fm.get("_path")
        ident = str(fm.get("id") or "?")
        if not isinstance(benchmark, Mapping):
            yield _result(
                Severity.WARN,
                path,
                f"{ident}: benchmark must be a mapping",
                "benchmark.block-malformed",
            )
            continue

        try:
            dataset_class = dataset_class_for(fm)
        except ValueError:
            dataset_class = "deposit"
        if dataset_class == "pointer":
            yield _result(
                Severity.INFO,
                path,
                f"{ident}: pointer dataset carries benchmark metadata; keep limitations explicit",
                "benchmark.pointer-block",
            )

        kinds = _string_list(benchmark.get("benchmark_kinds"))
        tasks = _task_list(benchmark.get("tasks"))

        if kinds and not tasks and not _string_list(benchmark.get("limitations")):
            yield _result(
                Severity.WARN,
                path,
                f"{ident}: benchmark facets have no tasks and no limitations text",
                "benchmark.facets-lack-task-or-limitation",
            )

        seen: set[str] = set()
        for task in tasks:
            task_id = task.get("id")
            if not isinstance(task_id, str) or not _TASK_ID_RE.fullmatch(task_id):
                yield _result(
                    Severity.ERROR,
                    path,
                    f"{ident}: benchmark task id {task_id!r} must be lowercase kebab-case",
                    "benchmark.task-id-invalid",
                )
                continue
            if task_id in seen:
                yield _result(
                    Severity.ERROR,
                    path,
                    f"{ident}: duplicate benchmark task id {task_id!r}",
                    "benchmark.task-id-duplicate",
                )
            seen.add(task_id)

            missing = [
                field
                for field in ("task_type", "prediction_target")
                if not _nonempty(task.get(field))
            ]
            if missing:
                yield _result(
                    Severity.WARN,
                    path,
                    f"{ident}#{task_id}: benchmark task missing {', '.join(missing)}",
                    "benchmark.task-sparse",
                )

        if "perturbation-response" in kinds and not any(
            _nonempty(task.get("intervention")) or _string_list(task.get("contexts"))
            for task in tasks
        ):
            yield _result(
                Severity.WARN,
                path,
                f"{ident}: perturbation-response benchmark lacks task intervention or contexts",
                "benchmark.perturbation-context-missing",
            )

        if "time-series" in kinds and not any(_string_list(task.get("timepoints")) for task in tasks):
            yield _result(
                Severity.WARN,
                path,
                f"{ident}: time-series benchmark lacks task timepoints",
                "benchmark.timepoints-missing",
            )


@Check(section="benchmark metadata", order=33)
def check_benchmark_metadata(ctx: ValidateContext) -> Iterator[Result]:
    yield from evaluate_benchmark_metadata(dataset_frontmatters(ctx))
```

- [ ] **Step 4: Register the check**

In `science/src/science_tool/validate/checks/__init__.py`, add `"benchmark_metadata"` immediately after `"dataset_metadata"`:

```python
    "dataset_metadata",
    "benchmark_metadata",
    "dataset_lineage",
```

- [ ] **Step 5: Run validation tests**

```bash
rtk uv run --frozen pytest science/tests/validate/test_checks_benchmark_metadata.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
rtk git add science/src/science_tool/validate/checks/benchmark_metadata.py science/src/science_tool/validate/checks/__init__.py science/tests/validate/test_checks_benchmark_metadata.py
rtk git commit -m "feat(validate): check benchmark dataset metadata"
```

---

### Task 4: Benchmark Query Helpers and CLI

**Files:**
- Create: `science/src/science_tool/benchmark_catalog.py`
- Modify: `science/src/science_tool/cli.py`
- Test: `science/tests/test_benchmark_cli.py`

- [ ] **Step 1: Write failing CLI tests**

Create `science/tests/test_benchmark_cli.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

from click.testing import CliRunner

from science_tool.cli import main as science_cli


def _write_dataset(root: Path, slug: str, frontmatter: str) -> None:
    path = root / "entities" / "datasets" / f"{slug}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\n{frontmatter}---\nbody\n", encoding="utf-8")


def _invoke(tmp_path: Path, *args: str):
    return CliRunner().invoke(
        science_cli,
        ["benchmark", "list", *args],
        catch_exceptions=False,
        env={"SCIENCE_PROJECT_ROOT": str(tmp_path), "SCIENCE_COMMONS_ROOT": str(tmp_path / "no-commons")},
    )


def test_benchmark_list_json_filters_by_domain_and_kind(tmp_path: Path) -> None:
    _write_dataset(
        tmp_path,
        "sciplex3",
        "id: dataset:sciplex3\n"
        "type: dataset\n"
        "title: Sci-Plex 3\n"
        "dataset_class: deposit\n"
        "benchmark:\n"
        "  domains: [biology]\n"
        "  modalities: [single-cell-rna-seq]\n"
        "  signal_types: [perturbation]\n"
        "  benchmark_kinds: [perturbation-response]\n"
        "  related_beliefs: [hypothesis:h1]\n"
        "  tasks:\n"
        "    - id: drug-response\n"
        "      task_type: response-prediction\n"
        "      metric: auroc\n"
        "      baseline: mean-expression\n",
    )
    _write_dataset(
        tmp_path,
        "gtex",
        "id: dataset:gtex\n"
        "type: dataset\n"
        "title: GTEx\n"
        "dataset_class: deposit\n"
        "benchmark:\n"
        "  domains: [biology]\n"
        "  modalities: [bulk-rna-seq]\n"
        "  signal_types: [cross-sectional]\n"
        "  benchmark_kinds: [static-association]\n"
        "  limitations: tissue expression only\n",
    )

    result = _invoke(tmp_path, "--domain", "biology", "--kind", "perturbation-response", "--format", "json")

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert [row["id"] for row in payload["rows"]] == ["dataset:sciplex3"]
    assert payload["summary"]["benchmark_kinds"]["perturbation-response"] == 1
    assert payload["summary"]["tasks"]["with_tasks"] == 1


def test_benchmark_list_belief_ref_text_is_exact_token_match(tmp_path: Path) -> None:
    _write_dataset(
        tmp_path,
        "match",
        "id: dataset:match\n"
        "type: dataset\n"
        "title: Match\n"
        "dataset_class: deposit\n"
        "benchmark:\n"
        "  domains: [biology]\n"
        "  benchmark_kinds: [static-association]\n"
        "  related_beliefs: ['hypothesis:h1 validates response']\n",
    )
    _write_dataset(
        tmp_path,
        "near",
        "id: dataset:near\n"
        "type: dataset\n"
        "title: Near\n"
        "dataset_class: deposit\n"
        "benchmark:\n"
        "  domains: [biology]\n"
        "  benchmark_kinds: [static-association]\n"
        "  related_beliefs: ['hypothesis:h10 validates response']\n",
    )

    result = _invoke(tmp_path, "--belief-ref-text", "hypothesis:h1", "--format", "json")

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert [row["id"] for row in payload["rows"]] == ["dataset:match"]


def test_benchmark_list_coverage_summary_json(tmp_path: Path) -> None:
    _write_dataset(
        tmp_path,
        "hca",
        "id: dataset:hca\n"
        "type: dataset\n"
        "title: Human Cell Atlas\n"
        "dataset_class: reference\n"
        "benchmark:\n"
        "  domains: [biology]\n"
        "  modalities: [single-cell-rna-seq, spatial]\n"
        "  signal_types: [reference-atlas]\n"
        "  benchmark_kinds: [cross-context-generalization]\n"
        "  limitations: facets only\n",
    )

    result = _invoke(tmp_path, "--coverage-summary", "--format", "json")

    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)
    assert payload["summary"]["dataset_class"]["reference"] == 1
    assert payload["summary"]["modalities"]["spatial"] == 1
    assert payload["summary"]["tasks"]["facets_only"] == 1
```

- [ ] **Step 2: Run tests and verify they fail**

```bash
rtk uv run --frozen pytest science/tests/test_benchmark_cli.py -q
```

Expected: FAIL because the `benchmark` CLI group and helper module do not exist.

- [ ] **Step 3: Implement query helpers**

Create `science/src/science_tool/benchmark_catalog.py`:

```python
"""Read-only benchmark catalog queries over dataset frontmatter."""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import Any

from science_model.frontmatter import parse_frontmatter
from science_tool.datasets.semantics import dataset_class_for

_TOKEN_RE = re.compile(r"[A-Za-z0-9:_-]+")


class CommonsUnavailable(Exception):
    """Raised when benchmark listing cannot read the commons registry."""


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def _tasks(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, dict)]


def _token_match(values: list[str], needle: str) -> bool:
    wanted = needle.casefold()
    for value in values:
        if wanted in {token.casefold() for token in _TOKEN_RE.findall(value)}:
            return True
    return False


def _row(scope: str, fm: dict[str, Any]) -> dict[str, Any] | None:
    benchmark = fm.get("benchmark")
    if not isinstance(benchmark, dict):
        return None
    tasks = _tasks(benchmark.get("tasks"))
    try:
        dataset_class = dataset_class_for(fm)
    except ValueError:
        dataset_class = "deposit"
    return {
        "id": str(fm.get("id") or ""),
        "title": str(fm.get("title") or ""),
        "scope": scope,
        "dataset_class": dataset_class,
        "domains": _string_list(benchmark.get("domains")),
        "modalities": _string_list(benchmark.get("modalities")),
        "signal_types": _string_list(benchmark.get("signal_types")),
        "benchmark_kinds": _string_list(benchmark.get("benchmark_kinds")),
        "source_datasets": _string_list(benchmark.get("source_datasets")),
        "related_beliefs": _string_list(benchmark.get("related_beliefs")),
        "task_count": len(tasks),
        "task_ids": [str(task.get("id")) for task in tasks if isinstance(task.get("id"), str)],
    }


def _local_rows(project_root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted((project_root / "entities" / "datasets").glob("*.md")):
        parsed = parse_frontmatter(path)
        if parsed is None:
            continue
        fm, _body = parsed
        if (fm.get("kind") or fm.get("type")) != "dataset":
            continue
        row = _row("local", fm)
        if row is not None:
            rows.append(row)
    return rows


def _commons_rows() -> list[dict[str, Any]]:
    from science_tool.commons.config import resolve_commons_root
    from science_tool.commons.errors import CommonsRegistryError
    from science_tool.commons.query import CommonsQuery

    try:
        records = CommonsQuery(resolve_commons_root()).find("dataset")
    except (CommonsRegistryError, FileNotFoundError) as exc:
        raise CommonsUnavailable(str(exc)) from exc
    rows: list[dict[str, Any]] = []
    for record in records:
        row = _row("commons", record.frontmatter or {})
        if row is not None:
            rows.append(row)
    return rows


def list_benchmarks(
    project_root: Path,
    *,
    domain: str | None = None,
    kind: str | None = None,
    belief_ref_text: str | None = None,
    include_commons: bool = False,
) -> tuple[list[dict[str, Any]], str | None]:
    rows = _local_rows(project_root)
    notice: str | None = None
    if include_commons:
        try:
            rows.extend(_commons_rows())
        except CommonsUnavailable as exc:
            notice = str(exc)

    filtered = []
    for row in rows:
        if domain is not None and domain not in row["domains"]:
            continue
        if kind is not None and kind not in row["benchmark_kinds"]:
            continue
        if belief_ref_text is not None and not _token_match(row["related_beliefs"], belief_ref_text):
            continue
        filtered.append(row)
    return sorted(filtered, key=lambda r: (r["scope"], r["id"])), notice


def coverage_summary(rows: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    def count_list(field: str) -> dict[str, int]:
        counter: Counter[str] = Counter()
        for row in rows:
            counter.update(row[field])
        return dict(sorted(counter.items()))

    dataset_class = Counter(str(row["dataset_class"]) for row in rows)
    tasks = Counter("with_tasks" if row["task_count"] else "facets_only" for row in rows)
    return {
        "domains": count_list("domains"),
        "modalities": count_list("modalities"),
        "signal_types": count_list("signal_types"),
        "benchmark_kinds": count_list("benchmark_kinds"),
        "dataset_class": dict(sorted(dataset_class.items())),
        "tasks": dict(sorted(tasks.items())),
    }
```

- [ ] **Step 4: Add the CLI group and list command**

In `science/src/science_tool/cli.py`, add this group before the existing `dataset` group:

```python
@main.group("benchmark")
def benchmark_group() -> None:
    """Benchmark-capable dataset catalog commands."""
```

Add this command below the group:

```python
@benchmark_group.command("list")
@click.option("--domain", default=None, help="Filter by benchmark.domains value")
@click.option("--kind", "benchmark_kind", default=None, help="Filter by benchmark.benchmark_kinds value")
@click.option(
    "--belief-ref-text",
    default=None,
    help="Case-insensitive exact-token match against free-text benchmark.related_beliefs strings",
)
@click.option("--commons", "include_commons", is_flag=True, help="Also list commons benchmark datasets")
@click.option("--coverage-summary", is_flag=True, help="Print facet counts instead of benchmark rows")
@click.option("--format", "output_format", default="table", type=click.Choice(["table", "json"]))
@click.option(
    "--project-root",
    default=None,
    type=click.Path(path_type=Path, file_okay=False, dir_okay=True),
    help="Project root (defaults to SCIENCE_PROJECT_ROOT env var or cwd)",
)
def benchmark_list(
    domain: str | None,
    benchmark_kind: str | None,
    belief_ref_text: str | None,
    include_commons: bool,
    coverage_summary: bool,
    output_format: str,
    project_root: Path | None,
) -> None:
    """List benchmark-capable dataset metadata."""
    import json as _json

    from rich.console import Console
    from rich.table import Table

    from science_tool.benchmark_catalog import coverage_summary as summarize_coverage
    from science_tool.benchmark_catalog import list_benchmarks

    root = project_root.resolve() if project_root else _project_root_from_env()
    rows, notice = list_benchmarks(
        root,
        domain=domain,
        kind=benchmark_kind,
        belief_ref_text=belief_ref_text,
        include_commons=include_commons,
    )
    summary = summarize_coverage(rows)

    if notice:
        click.echo(f"notice: commons benchmarks unavailable ({notice})", err=True)

    if output_format == "json":
        click.echo(_json.dumps({"rows": rows, "summary": summary, "commons_notice": notice}, indent=2))
        return

    if coverage_summary:
        table = Table(show_header=True, header_style="bold")
        for col in ("facet", "value", "count"):
            table.add_column(col, overflow="fold", no_wrap=False)
        for facet, values in summary.items():
            for value, count in values.items():
                table.add_row(facet, value, str(count))
        Console(width=200).print(table)
        return

    if not rows:
        click.echo("No matching benchmark dataset entities.")
        return

    table = Table(show_header=True, header_style="bold")
    for col in ("id", "title", "scope", "class", "domains", "modalities", "kinds", "tasks"):
        table.add_column(col, overflow="fold", no_wrap=False)
    for row in rows:
        table.add_row(
            row["id"],
            row["title"],
            row["scope"],
            row["dataset_class"],
            ", ".join(row["domains"]) or "-",
            ", ".join(row["modalities"]) or "-",
            ", ".join(row["benchmark_kinds"]) or "-",
            ", ".join(row["task_ids"]) or "-",
        )
    Console(width=200).print(table)
```

- [ ] **Step 5: Run CLI tests**

```bash
rtk uv run --frozen pytest science/tests/test_benchmark_cli.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
rtk git add science/src/science_tool/benchmark_catalog.py science/src/science_tool/cli.py science/tests/test_benchmark_cli.py
rtk git commit -m "feat(cli): list benchmark-capable datasets"
```

---

### Task 5: Commons Projection and Seed Records

**Files:**
- Modify: `science/tests/test_commons_inventory.py`
- Modify or create in `~/d/science-commons/`: `datasets/sciplex3/entity.md`, `datasets/l1000-cmap/entity.md`, `datasets/dream-perturbation/entity.md`, `datasets/human-cell-atlas/entity.md`, `datasets/cptac-proteogenomics/entity.md`, `datasets/tahoe-100m/entity.md`

- [ ] **Step 1: Add commons inventory regression test**

In `science/tests/test_commons_inventory.py`, add this test after `test_build_commons_inventory_clean_store`:

```python
def test_build_commons_inventory_projects_benchmark_metadata(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = _make_store(tmp_path)
    dataset_dir = root / "datasets" / "benchmark-example"
    dataset_dir.mkdir(parents=True)
    (dataset_dir / "entity.md").write_text(
        "---\n"
        'schema_profile: "science-entity-base/1.0+dataset/1.0"\n'
        'id: "dataset:benchmark-example"\n'
        'type: "dataset"\n'
        'title: "Benchmark Example"\n'
        'version: "1.0.0"\n'
        'status: "active"\n'
        'created: "2026-06-27"\n'
        'updated: "2026-06-27"\n'
        'datapackage: "datapackage.json"\n'
        'origin: "external"\n'
        'dataset_class: "deposit"\n'
        'tier: "use-now"\n'
        "access:\n"
        '  level: "public"\n'
        "  verified: true\n"
        '  verification_method: "retrieved"\n'
        '  source_url: "https://example.org/benchmark"\n'
        "ontology_terms: []\n"
        "tags: []\n"
        "benchmark:\n"
        "  domains: [biology]\n"
        "  modalities: [single-cell-rna-seq]\n"
        "  signal_types: [perturbation]\n"
        "  benchmark_kinds: [perturbation-response]\n"
        "  tasks:\n"
        "    - id: drug-response\n"
        "      task_type: response-prediction\n"
        "      metric: auroc\n"
        "      baseline: mean-expression\n"
        "---\n"
        "body\n",
        encoding="utf-8",
    )
    (dataset_dir / "datapackage.json").write_text('{"resources": []}\n', encoding="utf-8")
    monkeypatch.setenv("SCIENCE_COMMONS_ROOT", str(root))

    payload = build_commons_inventory()

    entity = next(e for e in payload.entities if e.id == "dataset:benchmark-example")
    assert entity.scope == "cross-project"
    assert entity.data["benchmark"]["benchmark_kinds"] == ["perturbation-response"]
```

- [ ] **Step 2: Run commons inventory test**

```bash
rtk uv run --frozen pytest science/tests/test_commons_inventory.py -q -k "benchmark_metadata or clean_store"
```

Expected: PASS. The schema change from Task 2 is sufficient; no inventory code change should be needed because non-promoted frontmatter keys already project into `InventoryEntity.data`.

- [ ] **Step 3: Author seed records in commons**

In the commons repo at `~/d/science-commons`, create or update these records. Use `scope: shared` when a record has a `scope` field; the commons inventory projection will emit `scope: cross-project`.

For `datasets/sciplex3/entity.md`:

```yaml
---
schema_profile: "science-entity-base/1.0+dataset/1.0"
id: "dataset:sciplex3"
type: "dataset"
title: "Sci-Plex 3"
version: "1.0.0"
status: "active"
created: "2026-06-27"
updated: "2026-06-27"
scope: "shared"
origin: "external"
source_class: "observational"
dataset_class: "deposit"
tier: "evaluate-next"
license: "unknown"
access:
  level: "public"
  availability: "available"
  verified: true
  verification_method: "retrieved"
  source_url: "https://www.science.org/doi/10.1126/science.aax6234"
ontology_terms: []
tags: []
benchmark:
  domains: ["biology"]
  modalities: ["single-cell-rna-seq"]
  signal_types: ["perturbation"]
  benchmark_kinds: ["perturbation-response", "cross-context-generalization"]
  source_datasets: []
  related_beliefs: []
  notes:
    - "Seed benchmark-capable dataset for single-cell perturbation response examples."
  limitations:
    - "Verify exact downloadable package location before marking as runnable deposit."
  tasks:
    - id: compound-response
      task_type: "response-prediction"
      prediction_target: "post-treatment single-cell expression signature"
      held_out_unit: "compound"
      metric: "rank correlation"
      baseline: "untreated expression profile"
      ground_truth:
        type: "measured-outcome"
        description: "measured post-perturbation expression state"
      interpretation_limits:
        - "Positive rank correlation against held-out perturbation response is the intended signal."
      intervention: "small-molecule compound and dose"
      contexts: ["cell line", "compound", "dose"]
---
# Sci-Plex 3
```

For `datasets/l1000-cmap/entity.md`:

```yaml
---
schema_profile: "science-entity-base/1.0+dataset/1.0"
id: "dataset:l1000-cmap"
type: "dataset"
title: "LINCS L1000 Connectivity Map"
version: "1.0.0"
status: "active"
created: "2026-06-27"
updated: "2026-06-27"
scope: "shared"
origin: "external"
source_class: "observational"
dataset_class: "deposit"
tier: "evaluate-next"
license: "unknown"
access:
  level: "public"
  availability: "available"
  verified: true
  verification_method: "retrieved"
  source_url: "https://clue.io/"
ontology_terms: []
tags: []
benchmark:
  domains: ["biology"]
  modalities: ["bulk-expression", "landmark-transcriptomics"]
  signal_types: ["perturbation", "cross-context-generalization"]
  benchmark_kinds: ["perturbation-response", "mechanism-discrimination"]
  source_datasets: []
  related_beliefs: []
  notes:
    - "Seed benchmark for perturbational expression signatures and mechanism ranking."
  limitations:
    - "L1000 measures landmark genes and inferred expression rather than full transcriptomes."
  tasks:
    - id: perturbation-signature-retrieval
      task_type: "signature-retrieval"
      prediction_target: "matched perturbation class for a query signature"
      held_out_unit: "perturbagen"
      metric: "connectivity score"
      baseline: "nearest landmark expression signature"
      ground_truth:
        type: "labeled-class"
        description: "known perturbagen class for each signature"
      interpretation_limits:
        - "Query should retrieve the matched perturbation class above baseline."
      intervention: "compound, knockdown, or overexpression"
      contexts: ["cell line", "perturbagen", "dose", "time"]
---
# LINCS L1000 Connectivity Map
```

For `datasets/dream-perturbation/entity.md`:

```yaml
---
schema_profile: "science-entity-base/1.0+dataset/1.0"
id: "dataset:dream-perturbation"
type: "dataset"
title: "DREAM perturbation challenge registry"
version: "1.0.0"
status: "active"
created: "2026-06-27"
updated: "2026-06-27"
scope: "shared"
origin: "external"
source_class: "reference"
dataset_class: "reference"
tier: "track"
license: "unknown"
access:
  level: "public"
  availability: "available"
  verified: true
  verification_method: "landing-confirmed"
  source_url: "https://dreamchallenges.org/"
ontology_terms: []
tags: []
benchmark:
  domains: ["biology"]
  modalities: ["varies"]
  signal_types: ["perturbation"]
  benchmark_kinds: ["perturbation-response", "mechanism-discrimination"]
  source_datasets: []
  related_beliefs: []
  notes:
    - "Reference-class registry for challenge-style perturbation benchmarks."
  limitations:
    - "Registry record only; individual challenge datasets require separate dataset records before runtime use."
---
# DREAM perturbation challenge registry
```

For `datasets/human-cell-atlas/entity.md`:

```yaml
---
schema_profile: "science-entity-base/1.0+dataset/1.0"
id: "dataset:human-cell-atlas"
type: "dataset"
title: "Human Cell Atlas"
version: "1.0.0"
status: "active"
created: "2026-06-27"
updated: "2026-06-27"
scope: "shared"
origin: "external"
source_class: "reference"
dataset_class: "reference"
tier: "track"
license: "unknown"
access:
  level: "public"
  availability: "available"
  verified: true
  verification_method: "landing-confirmed"
  source_url: "https://www.humancellatlas.org/"
ontology_terms: []
tags: []
benchmark:
  domains: ["biology"]
  modalities: ["single-cell-rna-seq", "spatial", "multimodal"]
  signal_types: ["reference-atlas", "cross-context-generalization"]
  benchmark_kinds: ["cross-context-generalization", "static-association"]
  source_datasets: []
  related_beliefs: []
  notes:
    - "Reference atlas seed for cross-context cell state and tissue generalization examples."
  limitations:
    - "Atlas/portal record only; concrete analysis-ready subsets should be separate deposit records."
---
# Human Cell Atlas
```

For `datasets/cptac-proteogenomics/entity.md`:

```yaml
---
schema_profile: "science-entity-base/1.0+dataset/1.0"
id: "dataset:cptac-proteogenomics"
type: "dataset"
title: "CPTAC proteogenomics"
version: "1.0.0"
status: "active"
created: "2026-06-27"
updated: "2026-06-27"
scope: "shared"
origin: "external"
source_class: "observational"
dataset_class: "deposit"
tier: "evaluate-next"
license: "unknown"
access:
  level: "public"
  availability: "available"
  verified: true
  verification_method: "retrieved"
  source_url: "https://proteomic.datacommons.cancer.gov/pdc/"
ontology_terms: []
tags: []
benchmark:
  domains: ["biology", "cancer"]
  modalities: ["proteomics", "bulk-rna-seq", "genomics", "multimodal"]
  signal_types: ["cross-sectional", "multi-omic"]
  benchmark_kinds: ["static-association", "cross-context-generalization"]
  source_datasets: []
  related_beliefs: []
  notes:
    - "Seed benchmark for testing multi-omic model transfer beyond RNA-only datasets."
  limitations:
    - "Cancer cohort context; access and license terms must be checked per study before staging."
  tasks:
    - id: protein-rna-cross-modal
      task_type: "cross-modal-prediction"
      prediction_target: "protein abundance from transcriptomic and genomic features"
      held_out_unit: "tumor sample"
      metric: "spearman-correlation"
      baseline: "gene-wise RNA abundance"
      ground_truth:
        type: "measured-outcome"
        description: "mass-spectrometry protein abundance"
      interpretation_limits:
        - "Protein prediction should exceed the RNA-only baseline."
      contexts: ["tumor type", "assay batch"]
---
# CPTAC proteogenomics
```

For `datasets/tahoe-100m/entity.md`:

```yaml
---
schema_profile: "science-entity-base/1.0+dataset/1.0"
id: "dataset:tahoe-100m"
type: "dataset"
title: "Tahoe-100M perturbation atlas"
version: "1.0.0"
status: "candidate"
created: "2026-06-27"
updated: "2026-06-27"
scope: "shared"
origin: "external"
source_class: "observational"
dataset_class: "pointer"
tier: "track"
license: "unknown"
access:
  level: "public"
  availability: "available"
  verified: true
  verification_method: "metadata-confirmed"
  source_url: "https://www.openproblems.bio/"
ontology_terms: []
tags: []
benchmark:
  domains: ["biology"]
  modalities: ["single-cell-rna-seq"]
  signal_types: ["perturbation"]
  benchmark_kinds: ["perturbation-response", "cross-context-generalization"]
  source_datasets: []
  related_beliefs: []
  notes:
    - "Pointer seed for a large perturbation atlas candidate; useful to test how sparse benchmark metadata behaves before staging."
  limitations:
    - "Tracked candidate only; verify canonical landing page, license, and access package before converting to deposit."
---
# Tahoe-100M perturbation atlas
```

- [ ] **Step 4: Validate commons seed records**

Run from `~/d/science` after setting `SCIENCE_COMMONS_ROOT` to the commons repo:

```bash
SCIENCE_COMMONS_ROOT=~/d/science-commons rtk uv run --frozen science commons validate --type dataset
SCIENCE_COMMONS_ROOT=~/d/science-commons rtk uv run --frozen science commons index rebuild
SCIENCE_COMMONS_ROOT=~/d/science-commons rtk uv run --frozen science benchmark list --commons --domain biology --coverage-summary --format json
```

Expected: commons validation passes (no `dataset.method-class-mismatch`: deposit
seeds use `retrieved`, the reference seeds use `landing-confirmed`, the pointer
uses `metadata-confirmed`); index rebuild succeeds; benchmark list JSON includes
the six seed records in either local or commons scope.

Note: the deposit seeds are verified but carry no local `datapackage`, so an
advisory `dataset.deposit-verified-unstaged` (WARN) is expected and correct — a
catalog seed is access-verified but not staged. It must not be an error and must
not block the commons build.

- [ ] **Step 5: Commit repo regression test**

```bash
rtk git add science/tests/test_commons_inventory.py
rtk git commit -m "test(commons): preserve benchmark metadata in inventory"
```

Commit the commons seed records separately in `~/d/science-commons` with:

```bash
rtk git -C ~/d/science-commons add datasets/sciplex3/entity.md datasets/l1000-cmap/entity.md datasets/dream-perturbation/entity.md datasets/human-cell-atlas/entity.md datasets/cptac-proteogenomics/entity.md datasets/tahoe-100m/entity.md
rtk git -C ~/d/science-commons commit -m "data: seed benchmark-capable omics datasets"
```

---

### Task 6: `/science:catalog-benchmarks` Command Guide

**Files:**
- Create: `commands/catalog-benchmarks.md`
- Test: `science/tests/test_command_docs.py`

- [ ] **Step 1: Create the command guide**

Create `commands/catalog-benchmarks.md`:

```markdown
---
description: Discover, classify, and summarize benchmark-capable datasets without adding belief edges or benchmark outcomes.
---

# Catalog Benchmarks

Catalog benchmark-capable datasets for `$ARGUMENTS`.
If no argument is provided, run the v1 descriptive benchmark loop over the project's active questions, hypotheses, and existing datasets.

## Scope

v1 is descriptive only:

- discover benchmark-capable datasets;
- classify `benchmark.domains`, `benchmark.modalities`, `benchmark.signal_types`, and `benchmark.benchmark_kinds`;
- add sparse `benchmark.tasks[]` only when the task is concrete;
- run `science benchmark list` and the facet coverage summary;
- record limitations when a dataset is facets-only.

Do not create belief-test plans, benchmark outcomes, graph edges, or benchmark gap entities in v1. Those are Phase 2/3.

## Setup

Follow `${CLAUDE_PLUGIN_ROOT}/references/command-preamble.md` with role `research-assistant`.

Read:

1. `${CLAUDE_PLUGIN_ROOT}/skills/data/SKILL.md`
2. `~/d/science/docs/plans/2026-06-26-benchmark-grounded-model-assessment-design.md`
3. `entities/datasets/`, if present
4. `entities/questions/`, `entities/hypotheses/`, and `entities/propositions/`, if present

## Step 1: Inspect Current Benchmark Coverage

Run:

```bash
science benchmark list --format json
science benchmark list --coverage-summary --format json
science benchmark list --commons --coverage-summary --format json
```

Use the JSON `summary` object as the source of truth for facet counts by domain, modality, signal type, benchmark kind, dataset class, and task completeness.

## Step 2: Classify Candidate Benchmarks

For each candidate dataset, decide whether it is:

- `dataset_class: deposit` when the benchmark data can be obtained and staged;
- `dataset_class: reference` when it is a benchmark portal, registry, atlas, or leaderboard used for lookup;
- `dataset_class: pointer` when it is worth tracking but not yet usable as data or lookup.

Do not infer `dataset_class` from `source_class`. A reference genome or reference atlas can be a downloadable deposit; a portal can be reference-only.

Fill the `benchmark` block with sparse, concrete metadata:

```yaml
benchmark:
  domains: ["biology"]
  modalities: ["single-cell-rna-seq"]
  signal_types: ["perturbation"]
  benchmark_kinds: ["perturbation-response"]
  source_datasets: []
  related_beliefs: []
  limitations:
    - "Facets only; no held-out task definition yet."
```

Add `tasks[]` only when the task is concrete — at minimum a `prediction_target`
and a `held_out_unit` (what is predicted and what is withheld), plus `metric` and
`baseline`:

```yaml
tasks:
  - id: "compound-response"
    task_type: "response-prediction"
    prediction_target: "post-treatment expression signature"
    held_out_unit: "compound"
    metric: "rank-correlation"
    baseline: "untreated expression profile"
    ground_truth:
      type: "measured-outcome"
      description: "measured post-perturbation expression state"
    interpretation_limits:
      - "Positive rank correlation against held-out perturbation response is the intended signal."
    intervention: "compound and dose"
    contexts: ["cell line", "compound", "dose"]
```

Task identity is local to the dataset. Render it as `dataset:<slug>#<task-id>` in prose and reports.

## Step 3: Search for Missing Facets

Prefer candidates that add new information relative to the existing summary:

- first proteomics benchmark before another RNA-seq benchmark;
- first perturbation or time-series signal before another static association dataset;
- first multimodal benchmark before another single-modality dataset;
- a reference registry when it makes future concrete deposits discoverable.

Useful biology/omics signal types include perturbation, time-series, longitudinal cohort, proteomics, spatial, single-cell, bulk RNA-seq, and multimodal proteogenomics.

## Step 4: Validate

Run:

```bash
science benchmark list --coverage-summary --format json
science validate --profile commit
```

Resolve benchmark metadata warnings before handing off. A facets-only record should have `limitations`; perturbation records should name `intervention` or `contexts` when they have tasks; time-series records should name `timepoints` when they have tasks.
```

- [ ] **Step 2: Run command doc tests**

```bash
rtk uv run --frozen pytest science/tests/test_command_docs.py -q -k "command"
```

Expected: PASS.

- [ ] **Step 3: Commit**

```bash
rtk git add commands/catalog-benchmarks.md
rtk git commit -m "docs(commands): add catalog-benchmarks guide"
```

---

### Task 7: End-to-End Verification

**Files:**
- Verify all files changed in previous tasks.

- [ ] **Step 1: Run targeted model, validation, CLI, and commons tests**

```bash
rtk uv run --frozen pytest \
  science/model/tests/test_dataset_models.py \
  science/model/tests/test_entity_schema_mixin_dataset.py \
  science/tests/validate/test_checks_benchmark_metadata.py \
  science/tests/test_benchmark_cli.py \
  science/tests/test_commons_inventory.py \
  science/tests/test_command_docs.py \
  -q
```

Expected: PASS.

- [ ] **Step 1b: Run the broader suites that a base-`Entity` field change can ripple into**

Adding `benchmark` to `Entity` (not just `DatasetEntity`) can affect entity
serialization, the kind-descriptor 3-way reconciliation gate, graph
materialization, and snapshot/golden output. Run the full model suite plus the
graph/snapshot surfaces:

```bash
rtk uv run --frozen pytest science/model/tests -q
rtk uv run --frozen pytest science/tests -q -k "reconcil or profile or kind_descriptor or schema_sync"
rtk uv run --frozen pytest science/tests -q -k "materialize or graph or snapshot or golden"
```

Expected: PASS. If a snapshot/golden test changes, confirm the only diff is the
new optional `benchmark` key on dataset entities (and that non-dataset entities
are unchanged because the field defaults to `None` and is excluded when empty);
update the golden intentionally if so.

- [ ] **Step 2: Run formatter and linter**

```bash
rtk uv run --frozen ruff format science/model/src/science_model/packages/schema.py science/model/src/science_model/entities.py science/model/src/science_model/frontmatter.py science/src/science_tool/benchmark_catalog.py science/src/science_tool/validate/checks/benchmark_metadata.py science/src/science_tool/cli.py science/model/tests/test_dataset_models.py science/model/tests/test_entity_schema_mixin_dataset.py science/tests/validate/test_checks_benchmark_metadata.py science/tests/test_benchmark_cli.py science/tests/test_commons_inventory.py
rtk uv run --frozen ruff check science/model/src/science_model/packages/schema.py science/model/src/science_model/entities.py science/model/src/science_model/frontmatter.py science/src/science_tool/benchmark_catalog.py science/src/science_tool/validate/checks/benchmark_metadata.py science/src/science_tool/cli.py science/model/tests/test_dataset_models.py science/model/tests/test_entity_schema_mixin_dataset.py science/tests/validate/test_checks_benchmark_metadata.py science/tests/test_benchmark_cli.py science/tests/test_commons_inventory.py
```

Expected: formatter completes; ruff check passes.

- [ ] **Step 3: Run smoke CLI checks**

```bash
rtk uv run --frozen science benchmark list --format json
rtk uv run --frozen science benchmark list --coverage-summary --format json
rtk uv run --frozen science validate --profile commit
```

Expected: benchmark commands return JSON; commit-profile validation completes without benchmark validation errors introduced by this branch.

- [ ] **Step 4: Inspect git state**

```bash
rtk git status --short
rtk git log --oneline -5
```

Expected: only intentional files are modified or all work is committed; recent commits correspond to the tasks above.

## Self-Review

- Spec coverage: Task 1 implements typed benchmark metadata; Task 2 implements schema validation; Task 3 implements v1 warnings and task identity checks; Task 4 implements read-only benchmark list and facet coverage summary; Task 5 covers commons seed records and projection; Task 6 covers `/science:catalog-benchmarks`; Task 7 verifies the tranche.
- Placeholder scan: This plan contains concrete paths, command invocations, and code snippets. It intentionally excludes Phase 2/3 work rather than leaving it unspecified.
- Type consistency: `BenchmarkBlock`, `BenchmarkTask`, `GroundTruth`, and the task fields `task_type`, `prediction_target`, `held_out_unit`, `metric`, `baseline`, `ground_truth`, `interpretation_limits`, `intervention`, `timepoints`, `contexts` use the same names and shapes across model, schema, validation, CLI rows, and command documentation. List-typed fields (`notes`, `limitations`, `interpretation_limits`, `timepoints`, `contexts`) are arrays in both the Pydantic model and the JSON schema (no string/list drift); `interpretation_threshold` and task-level `notes` are intentionally absent in v1 (the former is a Phase-2 belief-test concept).
- Design conformance: the `BenchmarkTask` shape matches `docs/plans/2026-06-26-benchmark-grounded-model-assessment-design.md`; `source_datasets` is free-text (no `^dataset:` pattern) per the design's "free-text refs to underlying data" intent.

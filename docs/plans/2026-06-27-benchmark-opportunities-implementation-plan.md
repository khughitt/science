# Benchmark Opportunities Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a read-only `science benchmark opportunities` report that matches project entities to benchmark-capable datasets with explainable baseline and relative scores.

**Architecture:** Keep benchmark opportunity logic in a focused `science_tool.benchmark_opportunities` module. Reuse the existing benchmark catalog discovery path, entity policy loader, dataset readiness logic, and CLI output conventions. The CLI layer should only parse options, translate user-facing errors, and render JSON/table output.

**Tech Stack:** Python 3.12, Click, Rich, PyYAML frontmatter parsing through existing Science helpers, pytest, pyright, ruff.

---

## Design References

- `docs/plans/2026-06-27-benchmark-opportunities-design.md`
- `science/src/science_tool/benchmark_catalog.py`
- `science/src/science_tool/entities.py`
- `science/src/science_tool/dataset_prioritize.py`
- `science/src/science_tool/cli.py`
- `science/tests/test_benchmark_cli.py`

## File Structure

- Modify `science/src/science_tool/benchmark_catalog.py`
  - Add a small public benchmark-source loader that returns raw benchmark frontmatter plus scope/fallback id.
  - Keep `science benchmark list` output unchanged.
- Create `science/src/science_tool/benchmark_opportunities.py`
  - Own all project entity loading, tokenization, stoplist/synonym handling, score components, row construction, ordering, and report assembly.
- Modify `science/src/science_tool/cli.py`
  - Add `science benchmark opportunities` under the existing `benchmark` group.
  - Render JSON and table output.
  - Translate `EntityCommandError` into `click.ClickException`.
- Create `science/tests/test_benchmark_opportunities.py`
  - Unit and CLI tests for loader shape, scoring, matching, row granularity, ordering, calibration output, commons degradation, and invalid entity handling.

## Public JSON Contract

The command returns:

```json
{
  "matched_opportunities": [],
  "coverage_gaps": [],
  "available_unmapped_benchmarks": [],
  "unmapped_project_entities": [],
  "calibration": {"enabled": false},
  "commons_notice": null
}
```

Rows are sorted as documented in the design:

- matched opportunities: `relative_score` desc, `baseline_score` desc, `entity_id`, `benchmark_id`, `task_id`
- unmapped benchmarks: `baseline_score` desc, `benchmark_id`
- gaps/entities: stable lexical ordering

---

### Task 1: Benchmark Source Loader

**Files:**
- Modify: `science/src/science_tool/benchmark_catalog.py`
- Create: `science/tests/test_benchmark_opportunities.py`

- [ ] **Step 1: Write failing tests for raw benchmark source loading**

Create `science/tests/test_benchmark_opportunities.py` with these fixtures and tests:

```python
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from click.testing import CliRunner

from science_tool.cli import main as science_cli


def _write_entity(root: Path, kind_dir: str, slug: str, frontmatter: str, body: str = "body") -> None:
    path = root / "entities" / kind_dir / f"{slug}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\n{frontmatter}---\n{body}\n", encoding="utf-8")


def _write_dataset(root: Path, slug: str, frontmatter: str, body: str = "body") -> None:
    _write_entity(root, "datasets", slug, frontmatter, body=body)


def _invoke(tmp_path: Path, *args: str):
    return CliRunner().invoke(
        science_cli,
        ["benchmark", "opportunities", *args],
        catch_exceptions=False,
        env={"SCIENCE_PROJECT_ROOT": str(tmp_path), "SCIENCE_COMMONS_ROOT": str(tmp_path / "no-commons")},
    )


def _write_corrupt_commons_registry(root: Path, frontmatter_json: str = "{not-json") -> None:
    root.mkdir()
    conn = sqlite3.connect(root / "registry.sqlite")
    try:
        conn.executescript(
            """
            CREATE TABLE entities (
                canonical_id TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                slug TEXT NOT NULL,
                title TEXT,
                schema_profile TEXT NOT NULL,
                body_path TEXT NOT NULL,
                datapackage_path TEXT,
                mtime_ns INTEGER NOT NULL,
                frontmatter_json TEXT NOT NULL
            );
            """
        )
        conn.execute(
            "INSERT INTO entities "
            "(canonical_id, type, slug, title, schema_profile, body_path, datapackage_path, mtime_ns, frontmatter_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "dataset:corrupt",
                "dataset",
                "corrupt",
                "Corrupt",
                "dataset/v1",
                "datasets/corrupt/entity.md",
                None,
                0,
                frontmatter_json,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def test_benchmark_sources_preserve_task_details_notes_and_limitations(tmp_path: Path) -> None:
    from science_tool.benchmark_catalog import benchmark_sources

    _write_dataset(
        tmp_path,
        "sciplex3",
        """
id: dataset:sciplex3
type: dataset
title: Sci-Plex 3
dataset_class: pointer
benchmark:
  domains: [biology]
  modalities: [single-cell-rna-seq, perturbation]
  signal_types: [perturbation]
  benchmark_kinds: [perturbation-response]
  notes:
    - Useful perturbation benchmark.
  limitations:
    - No local datapackage staged.
  tasks:
    - id: compound-response
      prediction_target: post-treatment expression
      held_out_unit: compound
      metric: rank-correlation
      baseline: nearest-neighbor
      ground_truth:
        type: measured-outcome
        description: measured expression
""",
    )

    sources, notice = benchmark_sources(tmp_path)

    assert notice is None
    assert len(sources) == 1
    source = sources[0]
    assert source["fallback_id"] == "dataset:sciplex3"
    assert source["scope"] == "local"
    benchmark = source["frontmatter"]["benchmark"]
    assert benchmark["notes"] == ["Useful perturbation benchmark."]
    assert benchmark["limitations"] == ["No local datapackage staged."]
    assert benchmark["tasks"][0]["held_out_unit"] == "compound"
```

- [ ] **Step 2: Run the failing test**

Run:

```bash
rtk uv run --frozen --project science pytest science/tests/test_benchmark_opportunities.py::test_benchmark_sources_preserve_task_details_notes_and_limitations -q
```

Expected: FAIL with `ImportError` or `AttributeError` because `benchmark_sources` does not exist.

- [ ] **Step 3: Add the source loader without changing list rows**

Modify `science/src/science_tool/benchmark_catalog.py`:

```python
class BenchmarkSource(TypedDict):
    frontmatter: Mapping[str, object]
    fallback_id: str
    scope: str


def _source_from_frontmatter(
    fm: Mapping[str, object],
    *,
    fallback_id: str,
    scope: str,
) -> BenchmarkSource | None:
    if (fm.get("kind") or fm.get("type")) != "dataset":
        return None
    if not isinstance(fm.get("benchmark"), Mapping):
        return None
    return {"frontmatter": fm, "fallback_id": fallback_id, "scope": scope}


def _local_sources(project_root: Path) -> list[BenchmarkSource]:
    datasets_dir = project_root / "entities" / "datasets"
    if not datasets_dir.is_dir():
        return []

    sources: list[BenchmarkSource] = []
    for md in sorted(datasets_dir.glob("*.md")):
        parsed = parse_frontmatter(md)
        if parsed is None:
            continue
        fm, _ = parsed
        source = _source_from_frontmatter(fm, fallback_id=f"dataset:{md.stem}", scope="local")
        if source is not None:
            sources.append(source)
    return sources


def _commons_sources() -> list[BenchmarkSource]:
    from science_tool.commons.config import resolve_commons_root
    from science_tool.commons.errors import CommonsError
    from science_tool.commons.query import CommonsQuery

    try:
        records = CommonsQuery(resolve_commons_root()).find("dataset")
    except (CommonsError, FileNotFoundError, ValueError) as exc:
        raise CommonsUnavailable(str(exc)) from exc

    sources: list[BenchmarkSource] = []
    for record in records:
        if not isinstance(record.frontmatter, Mapping):
            msg = f"{record.canonical_id}: frontmatter_json must decode to an object"
            raise CommonsUnavailable(msg)
        source = _source_from_frontmatter(
            record.frontmatter,
            fallback_id=record.canonical_id,
            scope="commons",
        )
        if source is not None:
            sources.append(source)
    return sources


def benchmark_sources(project_root: Path, *, include_commons: bool = False) -> tuple[list[BenchmarkSource], str | None]:
    sources = _local_sources(project_root)
    notice: str | None = None
    if include_commons:
        try:
            sources.extend(_commons_sources())
        except CommonsUnavailable as exc:
            notice = str(exc)
    return sources, notice
```

Then simplify `_local_rows()` and `_commons_rows()` to build rows from these sources:

```python
def _local_rows(project_root: Path) -> list[BenchmarkRow]:
    rows: list[BenchmarkRow] = []
    for source in _local_sources(project_root):
        row = _row_from_frontmatter(
            source["frontmatter"],
            fallback_id=source["fallback_id"],
            scope=source["scope"],
        )
        if row is not None:
            rows.append(row)
    return rows


def _commons_rows() -> list[BenchmarkRow]:
    rows: list[BenchmarkRow] = []
    for source in _commons_sources():
        row = _row_from_frontmatter(
            source["frontmatter"],
            fallback_id=source["fallback_id"],
            scope=source["scope"],
        )
        if row is not None:
            rows.append(row)
    return rows
```

- [ ] **Step 4: Verify source loader and existing benchmark list tests**

Run:

```bash
rtk uv run --frozen --project science pytest science/tests/test_benchmark_opportunities.py::test_benchmark_sources_preserve_task_details_notes_and_limitations science/tests/test_benchmark_cli.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
rtk git add science/src/science_tool/benchmark_catalog.py science/tests/test_benchmark_opportunities.py
rtk git commit -m "feat(benchmark): expose benchmark source rows"
```

---

### Task 2: Opportunity Data Model and Baseline Scoring

**Files:**
- Create: `science/src/science_tool/benchmark_opportunities.py`
- Modify: `science/tests/test_benchmark_opportunities.py`

- [ ] **Step 1: Add failing tests for dataset loading, row granularity, and baseline components**

Append to `science/tests/test_benchmark_opportunities.py`:

```python
def test_load_opportunity_datasets_preserves_facets_only_and_task_rows(tmp_path: Path) -> None:
    from science_tool.benchmark_opportunities import load_opportunity_datasets

    _write_dataset(
        tmp_path,
        "hca-spatial",
        """
id: dataset:hca-spatial
type: dataset
title: HCA Spatial
dataset_class: reference
benchmark:
  domains: [biology]
  modalities: [spatial]
  signal_types: [cross-context-generalization]
  benchmark_kinds: [static-association]
  limitations:
    - Facets only.
""",
    )
    _write_dataset(
        tmp_path,
        "cptac",
        """
id: dataset:cptac
type: dataset
title: CPTAC Proteogenomics
dataset_class: reference
benchmark:
  domains: [biology]
  modalities: [proteomics, multimodal]
  signal_types: [multi-omic]
  benchmark_kinds: [mechanism-discrimination]
  tasks:
    - id: subtype-transfer
      prediction_target: subtype
      held_out_unit: cohort
      metric: auroc
      baseline: clinical-only
      ground_truth:
        type: measured-outcome
        description: curated subtype
""",
    )

    rows, notice = load_opportunity_datasets(tmp_path, include_commons=False)

    assert notice is None
    assert [row.id for row in rows] == ["dataset:cptac", "dataset:hca-spatial"]
    assert rows[0].tasks[0].canonical_task_id == "dataset:cptac#subtype-transfer"
    assert rows[1].tasks == []
    assert rows[1].limitations == ["Facets only."]


def test_baseline_score_is_component_sum_and_credits_perturbation_axes(tmp_path: Path) -> None:
    from science_tool.benchmark_opportunities import baseline_score, load_opportunity_datasets

    _write_dataset(
        tmp_path,
        "sciplex3",
        """
id: dataset:sciplex3
type: dataset
title: Sci-Plex 3
dataset_class: pointer
benchmark:
  domains: [biology]
  modalities: [single-cell-rna-seq, perturbation]
  signal_types: [perturbation, cross-context-generalization]
  benchmark_kinds: [perturbation-response]
  limitations:
    - No local datapackage staged.
  tasks:
    - id: compound-response
      prediction_target: post-treatment expression
      held_out_unit: compound
      metric: rank-correlation
      baseline: nearest-neighbor
      ground_truth:
        type: measured-outcome
        description: measured expression
""",
    )

    dataset = load_opportunity_datasets(tmp_path, include_commons=False)[0][0]
    score = baseline_score(dataset)

    assert score.total == sum(score.components.values())
    assert score.components["task_completeness"] == 30
    assert score.components["signal_value"] > 0
    assert score.components["modality_value"] > 0
    assert score.components["limitations"] == 10
    assert "signal:perturbation" in score.notes
    assert "modality:perturbation" in score.notes
```

- [ ] **Step 2: Run the failing tests**

Run:

```bash
rtk uv run --frozen --project science pytest science/tests/test_benchmark_opportunities.py::test_load_opportunity_datasets_preserves_facets_only_and_task_rows science/tests/test_benchmark_opportunities.py::test_baseline_score_is_component_sum_and_credits_perturbation_axes -q
```

Expected: FAIL because `science_tool.benchmark_opportunities` does not exist.

- [ ] **Step 3: Create `benchmark_opportunities.py` with data contracts and baseline scoring**

Create `science/src/science_tool/benchmark_opportunities.py`:

```python
"""Read-only benchmark opportunity reports."""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from science_tool.benchmark_catalog import benchmark_sources
from science_tool.dataset_prioritize import readiness_weight
from science_tool.datasets.semantics import dataset_class_for

_TOKEN_RE = re.compile(r"[A-Za-z0-9:_-]+")


@dataclass(frozen=True)
class OpportunityTask:
    id: str
    canonical_task_id: str
    task_type: str
    prediction_target: str
    held_out_unit: str
    metric: str
    baseline: str
    ground_truth_type: str
    ground_truth_description: str
    prose: tuple[str, ...]


@dataclass(frozen=True)
class OpportunityDataset:
    id: str
    title: str
    scope: str
    dataset_class: str
    frontmatter: Mapping[str, object]
    domains: tuple[str, ...]
    modalities: tuple[str, ...]
    signal_types: tuple[str, ...]
    benchmark_kinds: tuple[str, ...]
    source_datasets: tuple[str, ...]
    related_beliefs: tuple[str, ...]
    notes: tuple[str, ...]
    limitations: tuple[str, ...]
    tasks: tuple[OpportunityTask, ...]


@dataclass(frozen=True)
class Score:
    total: int
    components: dict[str, int]
    notes: list[str]


def _string_list(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(item.strip() for item in value if isinstance(item, str) and item.strip())


def _task_from_mapping(dataset_id: str, task: Mapping[str, object]) -> OpportunityTask | None:
    task_id = task.get("id")
    if not isinstance(task_id, str) or not task_id.strip():
        return None
    ground_truth = task.get("ground_truth")
    gt_type = ""
    gt_description = ""
    if isinstance(ground_truth, Mapping):
        gt_type = str(ground_truth.get("type") or "")
        gt_description = str(ground_truth.get("description") or "")
    prose = tuple(
        value
        for value in (
            str(task.get("task_type") or ""),
            str(task.get("prediction_target") or ""),
            str(task.get("held_out_unit") or ""),
            str(task.get("metric") or ""),
            str(task.get("baseline") or ""),
            gt_type,
            gt_description,
        )
        if value
    )
    return OpportunityTask(
        id=task_id,
        canonical_task_id=f"{dataset_id}#{task_id}",
        task_type=str(task.get("task_type") or ""),
        prediction_target=str(task.get("prediction_target") or ""),
        held_out_unit=str(task.get("held_out_unit") or ""),
        metric=str(task.get("metric") or ""),
        baseline=str(task.get("baseline") or ""),
        ground_truth_type=gt_type,
        ground_truth_description=gt_description,
        prose=prose,
    )


def _tasks(dataset_id: str, value: object) -> tuple[OpportunityTask, ...]:
    if not isinstance(value, list):
        return ()
    tasks: list[OpportunityTask] = []
    for item in value:
        if isinstance(item, Mapping):
            task = _task_from_mapping(dataset_id, item)
            if task is not None:
                tasks.append(task)
    return tuple(tasks)


def _dataset_class(fm: Mapping[str, object]) -> str:
    try:
        return dataset_class_for(fm)
    except ValueError:
        return "deposit"


def _dataset_from_source(source: Mapping[str, object]) -> OpportunityDataset | None:
    fm = source["frontmatter"]
    if not isinstance(fm, Mapping):
        return None
    benchmark = fm.get("benchmark")
    if not isinstance(benchmark, Mapping):
        return None
    dataset_id = str(fm.get("id") or source["fallback_id"])
    return OpportunityDataset(
        id=dataset_id,
        title=str(fm.get("title") or ""),
        scope=str(source["scope"]),
        dataset_class=_dataset_class(fm),
        frontmatter=fm,
        domains=_string_list(benchmark.get("domains")),
        modalities=_string_list(benchmark.get("modalities")),
        signal_types=_string_list(benchmark.get("signal_types")),
        benchmark_kinds=_string_list(benchmark.get("benchmark_kinds")),
        source_datasets=_string_list(benchmark.get("source_datasets")),
        related_beliefs=_string_list(benchmark.get("related_beliefs")),
        notes=_string_list(benchmark.get("notes")),
        limitations=_string_list(benchmark.get("limitations")),
        tasks=_tasks(dataset_id, benchmark.get("tasks")),
    )


def load_opportunity_datasets(
    project_root: Path,
    *,
    include_commons: bool,
) -> tuple[list[OpportunityDataset], str | None]:
    sources, notice = benchmark_sources(project_root, include_commons=include_commons)
    datasets = [dataset for source in sources if (dataset := _dataset_from_source(source)) is not None]
    return sorted(datasets, key=lambda row: (row.scope, row.id)), notice


def _task_completeness(dataset: OpportunityDataset) -> int:
    if not dataset.tasks:
        return 0
    best = 0
    for task in dataset.tasks:
        points = 0
        points += 6 if task.prediction_target else 0
        points += 6 if task.held_out_unit else 0
        points += 6 if task.metric else 0
        points += 6 if task.baseline else 0
        points += 6 if task.ground_truth_type or task.ground_truth_description else 0
        best = max(best, points)
    return best


_SIGNAL_POINTS = {
    "perturbation": 10,
    "time-series": 10,
    "longitudinal": 8,
    "cross-context-generalization": 7,
    "multi-omic": 7,
}

_MODALITY_POINTS = {
    "proteomics": 7,
    "spatial": 6,
    "multimodal": 6,
    "perturbation": 4,
    "single-cell-rna-seq": 4,
}


def _facet_points(values: tuple[str, ...], weights: Mapping[str, int], cap: int) -> tuple[int, list[str]]:
    total = 0
    notes: list[str] = []
    for value in values:
        points = weights.get(value, 0)
        if points:
            total += points
            notes.append(value)
    return min(total, cap), notes


def baseline_score(dataset: OpportunityDataset) -> Score:
    task = _task_completeness(dataset)
    signal, signal_notes = _facet_points(dataset.signal_types, _SIGNAL_POINTS, 25)
    modality, modality_notes = _facet_points(dataset.modalities, _MODALITY_POINTS, 20)
    readiness_float, readiness_flags = readiness_weight(dict(dataset.frontmatter))
    readiness = round(readiness_float * 15)
    limitations = 10 if dataset.limitations else 0
    components = {
        "task_completeness": task,
        "signal_value": signal,
        "modality_value": modality,
        "readiness": readiness,
        "limitations": limitations,
    }
    notes = [f"signal:{value}" for value in signal_notes]
    notes.extend(f"modality:{value}" for value in modality_notes)
    notes.extend(readiness_flags)
    if limitations:
        notes.append("limitations-present")
    return Score(total=min(sum(components.values()), 100), components=components, notes=notes)
```

- [ ] **Step 4: Verify the new tests pass**

Run:

```bash
rtk uv run --frozen --project science pytest science/tests/test_benchmark_opportunities.py::test_load_opportunity_datasets_preserves_facets_only_and_task_rows science/tests/test_benchmark_opportunities.py::test_baseline_score_is_component_sum_and_credits_perturbation_axes -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
rtk git add science/src/science_tool/benchmark_opportunities.py science/tests/test_benchmark_opportunities.py
rtk git commit -m "feat(benchmark): score benchmark baseline value"
```

---

### Task 3: Project Entity Loading, Token Gates, and Relative Matching

**Files:**
- Modify: `science/src/science_tool/benchmark_opportunities.py`
- Modify: `science/tests/test_benchmark_opportunities.py`

- [ ] **Step 1: Add failing tests for entity loading, controlled facets, and id-token matching**

Append to `science/tests/test_benchmark_opportunities.py`:

```python
def test_opportunity_report_matches_shorthand_related_belief_and_controlled_facets(tmp_path: Path) -> None:
    from science_tool.benchmark_opportunities import opportunity_report

    _write_entity(
        tmp_path,
        "hypotheses",
        "0005-dynamic-homeostasis",
        """
id: hypothesis:0005-dynamic-homeostasis
type: hypothesis
title: Dynamic perturbation recovery
status: active
""",
        body="Proteomics should improve recovery predictions. Prose mentions noisy measured expression.",
    )
    _write_dataset(
        tmp_path,
        "sciplex3",
        """
id: dataset:sciplex3
type: dataset
title: Sci-Plex 3
dataset_class: pointer
benchmark:
  domains: [biology]
  modalities: [single-cell-rna-seq, perturbation]
  signal_types: [perturbation]
  benchmark_kinds: [perturbation-response]
  related_beliefs:
    - h5 predicts response shifts.
  limitations:
    - No local datapackage staged.
  tasks:
    - id: compound-response
      prediction_target: post-treatment expression
      held_out_unit: compound
      metric: rank-correlation
      baseline: nearest-neighbor
      ground_truth:
        type: measured-outcome
        description: measured expression
""",
    )

    payload = opportunity_report(tmp_path, include_commons=False)

    rows = payload["matched_opportunities"]
    assert len(rows) == 1
    assert rows[0]["entity_id"] == "hypothesis:0005-dynamic-homeostasis"
    assert rows[0]["benchmark_id"] == "dataset:sciplex3"
    assert rows[0]["task_id"] == "dataset:sciplex3#compound-response"
    assert "related-belief-id:h5" in rows[0]["match_reasons"]
    assert "facet-token:perturbation" in rows[0]["match_reasons"]
    assert not any("measured" in reason for reason in rows[0]["match_reasons"])


def test_stoplist_blocks_generic_token_only_match(tmp_path: Path) -> None:
    from science_tool.benchmark_opportunities import opportunity_report

    _write_entity(
        tmp_path,
        "hypotheses",
        "0001-model",
        """
id: hypothesis:0001-model
type: hypothesis
title: Model response analysis
status: active
""",
        body="Data and model evidence.",
    )
    _write_dataset(
        tmp_path,
        "generic",
        """
id: dataset:generic
type: dataset
title: Generic
benchmark:
  domains: [biology]
  modalities: [data]
  signal_types: [response]
  benchmark_kinds: [analysis]
""",
    )

    payload = opportunity_report(tmp_path, include_commons=False)

    assert payload["matched_opportunities"] == []
    assert payload["unmapped_project_entities"][0]["entity_id"] == "hypothesis:0001-model"
    assert payload["available_unmapped_benchmarks"][0]["benchmark_id"] == "dataset:generic"


def test_facets_only_rows_use_null_task_and_multitask_diversity_is_deduped(tmp_path: Path) -> None:
    from science_tool.benchmark_opportunities import opportunity_report

    _write_entity(
        tmp_path,
        "hypotheses",
        "0002-spatial",
        """
id: hypothesis:0002-spatial
type: hypothesis
title: Spatial proteomics transfer
status: active
""",
    )
    _write_dataset(
        tmp_path,
        "atlas",
        """
id: dataset:atlas
type: dataset
title: Spatial atlas
benchmark:
  domains: [biology]
  modalities: [spatial, proteomics]
  signal_types: [cross-context-generalization]
  benchmark_kinds: [static-association]
  limitations:
    - Facets only.
""",
    )
    _write_dataset(
        tmp_path,
        "multi-task",
        """
id: dataset:multi-task
type: dataset
title: Spatial proteomics tasks
benchmark:
  domains: [biology]
  modalities: [spatial, proteomics]
  signal_types: [cross-context-generalization]
  benchmark_kinds: [static-association]
  tasks:
    - id: task-a
      prediction_target: subtype
    - id: task-b
      prediction_target: subtype
""",
    )

    payload = opportunity_report(tmp_path, include_commons=False)
    rows = payload["matched_opportunities"]

    atlas = next(row for row in rows if row["benchmark_id"] == "dataset:atlas")
    assert atlas["task_id"] is None
    task_rows = [row for row in rows if row["benchmark_id"] == "dataset:multi-task"]
    assert [row["task_id"] for row in task_rows] == ["dataset:multi-task#task-a", "dataset:multi-task#task-b"]
    diversity_points = [row["score_components"]["relative"]["diversity_added"] for row in task_rows]
    assert diversity_points[0] > 0
    assert diversity_points[1] == 0
```

- [ ] **Step 2: Run failing tests**

Run:

```bash
rtk uv run --frozen --project science pytest science/tests/test_benchmark_opportunities.py::test_opportunity_report_matches_shorthand_related_belief_and_controlled_facets science/tests/test_benchmark_opportunities.py::test_stoplist_blocks_generic_token_only_match science/tests/test_benchmark_opportunities.py::test_facets_only_rows_use_null_task_and_multitask_diversity_is_deduped -q
```

Expected: FAIL because `opportunity_report` is not defined.

- [ ] **Step 3: Add project loading, tokenization, relative scoring, and report assembly**

Append to `science/src/science_tool/benchmark_opportunities.py`:

```python
from science_tool.entities import (
    _SHORTFORM_ENTITY_KINDS,
    _load_markdown_entities,
    _numeric_variants,
    _parse_markdown_file,
)

_ENTITY_KINDS = ("question", "hypothesis", "proposition")
_STOP_TOKENS = {
    "analysis",
    "cell",
    "data",
    "dataset",
    "evidence",
    "model",
    "result",
    "response",
}
_SYNONYMS = {
    "intervention": "perturbation",
    "single-cell": "single-cell-rna-seq",
    "transcriptomics": "rna-seq",
}


@dataclass(frozen=True)
class ProjectBenchmarkEntity:
    id: str
    kind: str
    title: str
    content_preview: str
    frontmatter: Mapping[str, object]
    tokens: frozenset[str]
    id_tokens: frozenset[str]


def _normalize_token(token: str) -> str:
    token = token.lower().strip()
    return _SYNONYMS.get(token, token)


def _tokens_from_text(*values: str, include_stop_tokens: bool = False) -> frozenset[str]:
    tokens: set[str] = set()
    for value in values:
        for raw in _TOKEN_RE.findall(value):
            token = _normalize_token(raw)
            if not include_stop_tokens and token in _STOP_TOKENS:
                continue
            if len(token) < 3 and not re.fullmatch(r"[hq]\d+", token):
                continue
            tokens.add(token)
    return frozenset(tokens)


def _as_string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, str) and item]


def _shortform_for(kind: str) -> str | None:
    for shortform, entity_kind in _SHORTFORM_ENTITY_KINDS.items():
        if entity_kind == kind:
            return shortform
    return None


def _id_tokens(entity_id: str, kind: str, fm: Mapping[str, object]) -> frozenset[str]:
    tokens = {entity_id.lower()}
    local = entity_id.split(":", 1)[1] if ":" in entity_id else entity_id
    tokens.add(local.lower())
    tokens.update(value.lower() for value in _numeric_variants(local))
    shortform = _shortform_for(kind)
    if shortform is not None:
        numeric_prefix = re.match(r"^0*(\d+)(.*)$", local)
        if numeric_prefix is not None:
            number, suffix = numeric_prefix.groups()
            tokens.add(f"{shortform}{number}".lower())
            if suffix:
                tokens.add(f"{shortform}{number}{suffix}".lower())
    for field in ("deprecated_ids", "aliases", "same_as", "source_refs"):
        tokens.update(value.lower() for value in _as_string_list(fm.get(field)))
    return frozenset(tokens)


def load_project_entities(project_root: Path) -> list[ProjectBenchmarkEntity]:
    entities: list[ProjectBenchmarkEntity] = []
    for kind in _ENTITY_KINDS:
        for row in _load_markdown_entities(project_root, kind=kind):
            fm = row["frontmatter"]
            if not isinstance(fm, Mapping):
                continue
            entity_id = str(row["id"])
            title = str(fm.get("title") or "")
            _frontmatter, body = _parse_markdown_file(row["path"])
            content_preview = str(fm.get("content_preview") or body[:200])
            tokens = _tokens_from_text(entity_id, title, content_preview)
            entities.append(
                ProjectBenchmarkEntity(
                    id=entity_id,
                    kind=str(row["kind"]),
                    title=title,
                    content_preview=content_preview,
                    frontmatter=fm,
                    tokens=tokens,
                    id_tokens=_id_tokens(entity_id, kind, fm),
                )
            )
    return sorted(entities, key=lambda entity: entity.id)


def _controlled_facet_tokens(dataset: OpportunityDataset) -> frozenset[str]:
    return _tokens_from_text(
        *dataset.domains,
        *dataset.modalities,
        *dataset.signal_types,
        *dataset.benchmark_kinds,
        include_stop_tokens=False,
    )


def _benchmark_prose_tokens(dataset: OpportunityDataset) -> frozenset[str]:
    task_prose: list[str] = []
    for task in dataset.tasks:
        task_prose.extend(task.prose)
    return _tokens_from_text(*dataset.notes, *dataset.limitations, *task_prose)


def _related_belief_tokens(dataset: OpportunityDataset) -> frozenset[str]:
    return _tokens_from_text(*dataset.related_beliefs, include_stop_tokens=True)


def _kind_signal_points(entity_tokens: frozenset[str], dataset: OpportunityDataset) -> tuple[int, list[str]]:
    rules = {
        "perturbation": ("perturbation-response", 10),
        "dynamic": ("time-series", 8),
        "temporal": ("time-series", 8),
        "spatial": ("static-association", 5),
        "proteomics": ("mechanism-discrimination", 5),
    }
    total = 0
    notes: list[str] = []
    kinds = set(dataset.benchmark_kinds)
    for token, (kind, points) in rules.items():
        if token in entity_tokens and kind in kinds:
            total += points
            notes.append(f"kind-signal:{token}->{kind}")
    return min(total, 20), notes


def _relative_score(
    entity: ProjectBenchmarkEntity,
    dataset: OpportunityDataset,
    task_id: str | None,
    seen_facets: set[tuple[str, str, str]],
) -> Score | None:
    related_tokens = _related_belief_tokens(dataset)
    id_hits = sorted(entity.id_tokens & related_tokens)
    facet_hits = sorted(entity.tokens & _controlled_facet_tokens(dataset))
    if not id_hits and not facet_hits:
        return None

    related_points = 40 if id_hits else 0
    facet_points = min(len(facet_hits) * 8, 25)
    kind_points, kind_notes = _kind_signal_points(entity.tokens, dataset)

    diversity_points = 0
    diversity_notes: list[str] = []
    for value in (*dataset.modalities, *dataset.signal_types):
        key = (entity.id, dataset.id, value)
        if key not in seen_facets:
            seen_facets.add(key)
            if value in {"proteomics", "spatial", "multimodal", "perturbation", "time-series", "cross-context-generalization"}:
                diversity_points += 5
                diversity_notes.append(f"diversity:{value}")
    diversity_points = min(diversity_points, 15)

    readiness_float, _flags = readiness_weight(dict(dataset.frontmatter))
    readiness_penalty = 0 if readiness_float >= 0.5 else -10
    components = {
        "related_belief_id": related_points,
        "facet_overlap": facet_points,
        "kind_signal_fit": kind_points,
        "diversity_added": diversity_points,
        "readiness_penalty": readiness_penalty,
    }
    notes = [f"related-belief-id:{hit}" for hit in id_hits]
    notes.extend(f"facet-token:{hit}" for hit in facet_hits)
    notes.extend(kind_notes)
    notes.extend(diversity_notes)
    total = max(0, min(sum(components.values()), 100))
    return Score(total=total, components=components, notes=notes)


def _row_for(
    entity: ProjectBenchmarkEntity,
    dataset: OpportunityDataset,
    task_id: str | None,
    baseline: Score,
    relative: Score,
) -> dict[str, object]:
    return {
        "entity_id": entity.id,
        "entity_title": entity.title,
        "benchmark_id": dataset.id,
        "benchmark_title": dataset.title,
        "task_id": task_id,
        "match_reasons": relative.notes,
        "benchmark_kinds": list(dataset.benchmark_kinds),
        "signal_types": list(dataset.signal_types),
        "modalities": list(dataset.modalities),
        "baseline_score": baseline.total,
        "relative_score": relative.total,
        "score_components": {"baseline": baseline.components, "relative": relative.components},
        "score_notes": baseline.notes + relative.notes,
    }


def _rows_for_match(
    entity: ProjectBenchmarkEntity,
    dataset: OpportunityDataset,
    seen_facets: set[tuple[str, str, str]],
) -> list[dict[str, object]]:
    baseline = baseline_score(dataset)
    task_ids: list[str | None] = [task.canonical_task_id for task in dataset.tasks] or [None]
    rows: list[dict[str, object]] = []
    for task_id in task_ids:
        relative = _relative_score(entity, dataset, task_id, seen_facets)
        if relative is None:
            continue
        rows.append(_row_for(entity, dataset, task_id, baseline, relative))
    return rows


def _available_unmapped_benchmarks(datasets: list[OpportunityDataset], matched_ids: set[str]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for dataset in datasets:
        if dataset.id in matched_ids:
            continue
        baseline = baseline_score(dataset)
        rows.append(
            {
                "benchmark_id": dataset.id,
                "benchmark_title": dataset.title,
                "baseline_score": baseline.total,
                "unmapped_facets": sorted(set(dataset.modalities + dataset.signal_types)),
            }
        )
    return sorted(rows, key=lambda row: (-int(row["baseline_score"]), str(row["benchmark_id"])))


def _coverage_gaps(entities: list[ProjectBenchmarkEntity], matched_rows: list[dict[str, object]]) -> list[dict[str, object]]:
    matched_by_entity: dict[str, set[str]] = {}
    for row in matched_rows:
        facets = matched_by_entity.setdefault(str(row["entity_id"]), set())
        facets.update(str(value) for value in row["modalities"])
        facets.update(str(value) for value in row["signal_types"])
    gaps: list[dict[str, object]] = []
    for entity in entities:
        entity_tokens = entity.tokens
        missing_modalities = sorted(token for token in ("proteomics", "spatial", "multimodal") if token in entity_tokens and token not in matched_by_entity.get(entity.id, set()))
        missing_signal_types = sorted(token for token in ("perturbation", "time-series", "cross-context-generalization") if token in entity_tokens and token not in matched_by_entity.get(entity.id, set()))
        if missing_modalities or missing_signal_types:
            gaps.append(
                {
                    "entity_id": entity.id,
                    "missing_modalities": missing_modalities,
                    "missing_signal_types": missing_signal_types,
                    "reason": "No matched benchmark has these facets.",
                }
            )
    return sorted(gaps, key=lambda row: (str(row["entity_id"]), ",".join(row["missing_modalities"]), ",".join(row["missing_signal_types"])))


def opportunity_report(
    project_root: Path,
    *,
    include_commons: bool = False,
    entity_id: str | None = None,
    domain: str | None = None,
    calibration_report: bool = False,
) -> dict[str, object]:
    entities = load_project_entities(project_root)
    if entity_id is not None:
        entities = [entity for entity in entities if entity.id == entity_id]
    datasets, notice = load_opportunity_datasets(project_root, include_commons=include_commons)
    if domain is not None:
        datasets = [dataset for dataset in datasets if domain in dataset.domains]

    seen_facets: set[tuple[str, str, str]] = set()
    matched: list[dict[str, object]] = []
    for entity in entities:
        for dataset in datasets:
            matched.extend(_rows_for_match(entity, dataset, seen_facets))
    matched.sort(
        key=lambda row: (
            -int(row["relative_score"]),
            -int(row["baseline_score"]),
            str(row["entity_id"]),
            str(row["benchmark_id"]),
            "" if row["task_id"] is None else str(row["task_id"]),
        )
    )
    matched_entity_ids = {str(row["entity_id"]) for row in matched}
    matched_benchmark_ids = {str(row["benchmark_id"]) for row in matched}
    return {
        "matched_opportunities": matched,
        "coverage_gaps": _coverage_gaps(entities, matched),
        "available_unmapped_benchmarks": _available_unmapped_benchmarks(datasets, matched_benchmark_ids),
        "unmapped_project_entities": [
            {"entity_id": entity.id, "entity_title": entity.title, "observed_tokens": sorted(entity.tokens)}
            for entity in entities
            if entity.id not in matched_entity_ids
        ],
        "calibration": {
            "enabled": calibration_report,
            "stop_tokens": sorted(_STOP_TOKENS) if calibration_report else [],
        },
        "commons_notice": notice,
    }
```

- [ ] **Step 4: Verify relative matching tests pass**

Run:

```bash
rtk uv run --frozen --project science pytest science/tests/test_benchmark_opportunities.py::test_opportunity_report_matches_shorthand_related_belief_and_controlled_facets science/tests/test_benchmark_opportunities.py::test_stoplist_blocks_generic_token_only_match science/tests/test_benchmark_opportunities.py::test_facets_only_rows_use_null_task_and_multitask_diversity_is_deduped -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
rtk git add science/src/science_tool/benchmark_opportunities.py science/tests/test_benchmark_opportunities.py
rtk git commit -m "feat(benchmark): match project entities to benchmark opportunities"
```

---

### Task 4: CLI Integration

**Files:**
- Modify: `science/src/science_tool/cli.py`
- Modify: `science/tests/test_benchmark_opportunities.py`

- [ ] **Step 1: Add failing CLI tests**

Append to `science/tests/test_benchmark_opportunities.py`:

```python
def test_benchmark_opportunities_json_and_calibration_shape(tmp_path: Path) -> None:
    _write_entity(
        tmp_path,
        "hypotheses",
        "0001-perturbation",
        """
id: hypothesis:0001-perturbation
type: hypothesis
title: Perturbation response
status: active
""",
    )
    _write_dataset(
        tmp_path,
        "sciplex3",
        """
id: dataset:sciplex3
type: dataset
title: Sci-Plex 3
benchmark:
  domains: [biology]
  modalities: [single-cell-rna-seq]
  signal_types: [perturbation]
  benchmark_kinds: [perturbation-response]
""",
    )

    result = _invoke(tmp_path, "--format", "json", "--calibration-report")

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["matched_opportunities"][0]["entity_id"] == "hypothesis:0001-perturbation"
    assert payload["calibration"]["enabled"] is True
    assert "stop_tokens" in payload["calibration"]


def test_benchmark_opportunities_table_uses_candidate_language(tmp_path: Path) -> None:
    _write_entity(
        tmp_path,
        "hypotheses",
        "0001-spatial",
        """
id: hypothesis:0001-spatial
type: hypothesis
title: Spatial transfer
status: active
""",
    )
    _write_dataset(
        tmp_path,
        "atlas",
        """
id: dataset:atlas
type: dataset
title: Atlas
benchmark:
  domains: [biology]
  modalities: [spatial]
  signal_types: [cross-context-generalization]
  benchmark_kinds: [static-association]
""",
    )

    result = _invoke(tmp_path)

    assert result.exit_code == 0
    assert "Candidate Opportunities" in result.output
    assert "recommended" not in result.output.lower()
    assert "best" not in result.output.lower()


def test_benchmark_opportunities_invalid_entity_is_click_error(tmp_path: Path) -> None:
    result = _invoke(tmp_path, "--entity", "hypothesis:missing")

    assert result.exit_code == 1
    assert "Entity not found: hypothesis:missing" in result.output


def test_benchmark_opportunities_commons_unavailable_degrades_to_local_rows(tmp_path: Path) -> None:
    _write_entity(
        tmp_path,
        "hypotheses",
        "0001-static",
        """
id: hypothesis:0001-static
type: hypothesis
title: Static biology association
status: active
""",
    )
    _write_dataset(
        tmp_path,
        "local",
        """
id: dataset:local
type: dataset
title: Local
benchmark:
  domains: [biology]
  modalities: [biology]
  benchmark_kinds: [static-association]
""",
    )

    result = _invoke(tmp_path, "--commons", "--format", "json")

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["commons_notice"]
    assert "notice: commons benchmarks unavailable" in result.stderr
```

- [ ] **Step 2: Run failing CLI tests**

Run:

```bash
rtk uv run --frozen --project science pytest science/tests/test_benchmark_opportunities.py::test_benchmark_opportunities_json_and_calibration_shape science/tests/test_benchmark_opportunities.py::test_benchmark_opportunities_table_uses_candidate_language science/tests/test_benchmark_opportunities.py::test_benchmark_opportunities_invalid_entity_is_click_error science/tests/test_benchmark_opportunities.py::test_benchmark_opportunities_commons_unavailable_degrades_to_local_rows -q
```

Expected: FAIL because `benchmark opportunities` is not registered.

- [ ] **Step 3: Add CLI command**

Modify `science/src/science_tool/cli.py` under the existing `@benchmark_group.command("list")` block and before `@main.group("dataset")`:

```python
@benchmark_group.command("opportunities")
@click.option("--domain", default=None, help="Filter benchmark datasets by benchmark domain.")
@click.option("--entity", "entity_ref", default=None, help="Limit report to one project entity reference.")
@click.option("--commons", "include_commons", is_flag=True, help="Also include commons benchmark dataset entities.")
@click.option("--calibration-report", is_flag=True, help="Include token/scoring calibration details.")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["table", "json"]),
    default="table",
    show_default=True,
)
@click.option(
    "--project-root",
    default=None,
    type=click.Path(path_type=Path, file_okay=False, dir_okay=True),
    help="Project root (defaults to SCIENCE_PROJECT_ROOT env var or cwd).",
)
def benchmark_opportunities(
    domain: str | None,
    entity_ref: str | None,
    include_commons: bool,
    calibration_report: bool,
    output_format: str,
    project_root: Path | None,
) -> None:
    """Report candidate benchmark opportunities for project entities."""
    from rich.console import Console
    from rich.table import Table

    from science_tool.benchmark_opportunities import opportunity_report
    from science_tool.entities import EntityCommandError, resolve_entity_ref

    root = project_root.resolve() if project_root else _project_root_from_env()
    entity_id: str | None = None
    if entity_ref is not None:
        try:
            entity_id = resolve_entity_ref(root, entity_ref)
        except EntityCommandError as exc:
            raise click.ClickException(str(exc)) from exc

    payload = opportunity_report(
        root,
        include_commons=include_commons,
        entity_id=entity_id,
        domain=domain,
        calibration_report=calibration_report,
    )

    notice = payload.get("commons_notice")
    if notice:
        click.echo(f"notice: commons benchmarks unavailable ({notice})", err=True)

    if output_format == "json":
        click.echo(json.dumps(payload, indent=2, sort_keys=True))
        return

    console = Console(width=200)
    rows = payload["matched_opportunities"]
    if isinstance(rows, list) and rows:
        table = Table(title="Candidate Opportunities", show_header=True, header_style="bold")
        for col in ("entity", "benchmark", "task", "relative", "baseline", "reasons"):
            table.add_column(col, overflow="fold", no_wrap=False)
        for row in rows:
            task_id = row.get("task_id") or "-"
            reasons = ", ".join(str(item) for item in row.get("match_reasons", []))
            table.add_row(
                str(row.get("entity_id", "")),
                str(row.get("benchmark_id", "")),
                str(task_id),
                str(row.get("relative_score", "")),
                str(row.get("baseline_score", "")),
                reasons,
            )
        console.print(table)
    else:
        click.echo("No candidate benchmark opportunities.")

    if calibration_report:
        calibration = payload.get("calibration")
        table = Table(title="Calibration", show_header=True, header_style="bold")
        table.add_column("field", overflow="fold", no_wrap=False)
        table.add_column("value", overflow="fold", no_wrap=False)
        if isinstance(calibration, dict):
            for key, value in sorted(calibration.items()):
                table.add_row(str(key), json.dumps(value, sort_keys=True))
        console.print(table)
```

- [ ] **Step 4: Verify CLI tests pass**

Run:

```bash
rtk uv run --frozen --project science pytest science/tests/test_benchmark_opportunities.py::test_benchmark_opportunities_json_and_calibration_shape science/tests/test_benchmark_opportunities.py::test_benchmark_opportunities_table_uses_candidate_language science/tests/test_benchmark_opportunities.py::test_benchmark_opportunities_invalid_entity_is_click_error science/tests/test_benchmark_opportunities.py::test_benchmark_opportunities_commons_unavailable_degrades_to_local_rows -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
rtk git add science/src/science_tool/cli.py science/tests/test_benchmark_opportunities.py
rtk git commit -m "feat(cli): report benchmark opportunities"
```

---

### Task 5: Integration Verification and Type Cleanup

**Files:**
- Modify if needed: `science/src/science_tool/benchmark_opportunities.py`
- Modify if needed: `science/src/science_tool/benchmark_catalog.py`
- Modify if needed: `science/src/science_tool/cli.py`
- Modify if needed: `science/tests/test_benchmark_opportunities.py`

- [ ] **Step 1: Run focused benchmark tests**

Run:

```bash
rtk uv run --frozen --project science pytest science/tests/test_benchmark_opportunities.py science/tests/test_benchmark_cli.py -q
```

Expected: PASS.

- [ ] **Step 2: Run pyright on touched modules**

Run:

```bash
rtk uv run --frozen --project science pyright science/src/science_tool/benchmark_catalog.py science/src/science_tool/benchmark_opportunities.py science/src/science_tool/cli.py science/tests/test_benchmark_opportunities.py
```

Expected: 0 errors.

If pyright complains about `Mapping[str, object]` indexing in `benchmark_opportunities.py`, replace the expression with an `isinstance(..., Mapping)` guard and a local variable before indexing. Do not add `type: ignore` for these data-shape checks.

- [ ] **Step 3: Run ruff**

Run:

```bash
rtk uv run --frozen --project science ruff check science/src/science_tool/benchmark_catalog.py science/src/science_tool/benchmark_opportunities.py science/src/science_tool/cli.py science/tests/test_benchmark_opportunities.py
```

Expected: All checks passed.

- [ ] **Step 4: Run CLI smoke commands**

Run:

```bash
rtk uv run --frozen --project science science benchmark opportunities --format json
rtk uv run --frozen --project science science benchmark opportunities --commons --domain biology --calibration-report --format json
```

Expected: both commands exit 0 and emit JSON with the six top-level keys from the public contract. The second command may include `commons_notice` depending on the local commons configuration.

- [ ] **Step 5: Commit verification fixes if any were needed**

If Task 5 required code edits, run:

```bash
rtk git add science/src/science_tool/benchmark_catalog.py science/src/science_tool/benchmark_opportunities.py science/src/science_tool/cli.py science/tests/test_benchmark_opportunities.py
rtk git commit -m "fix(benchmark): tighten opportunity report verification"
```

If Task 5 required no code edits, do not create an empty commit.

---

## Self-Review

Spec coverage:

- Read-only CLI command: Task 4.
- Rich benchmark rows with task fields, notes, limitations, and readiness frontmatter: Tasks 1-2.
- Policy-root entity loading via `_load_markdown_entities(project_root, kind=...)`: Task 3.
- `title + content_preview`, not full `content`: Task 3.
- `related_beliefs` free-text id-token matching: Task 3.
- Stoplist/min-token gating: Task 3.
- Controlled-facet-only `facet_overlap`: Task 3.
- Additive `baseline_score` and `relative_score` components: Tasks 2-3.
- Modality diversity and multi-task dedupe: Task 3.
- Facets-only `task_id: null`: Task 3.
- Calibration output: Task 4.
- Commons degradation: Task 4.
- Invalid `--entity` Click error: Task 4.

Placeholder scan:

- No unresolved marker strings or open-ended implementation steps are intentionally present.
- Every test step includes concrete test code and expected failure/pass behavior.
- Every code step names exact files and concrete functions/classes.

Type consistency:

- `OpportunityDataset`, `OpportunityTask`, `ProjectBenchmarkEntity`, and `Score` are defined before later tasks use them.
- JSON keys match the design contract: `matched_opportunities`, `coverage_gaps`, `available_unmapped_benchmarks`, `unmapped_project_entities`, `calibration`, `commons_notice`.
- CLI option names match the design: `--commons`, `--domain`, `--entity`, `--calibration-report`, `--format`.

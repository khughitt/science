# Benchmark Tests v0 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a read-only `science benchmark tests` report that projects existing benchmark opportunities and gaps into concrete or draft-needed benchmark test-plan rows.

**Architecture:** Implement the report in `science_tool.benchmark_opportunities` so it can reuse the existing private opportunity/gap analysis context, candidate scoring, baseline components, facet normalization, and dataset readiness helpers without creating a second matcher. Add a CLI command under the existing `benchmark` group that renders JSON/table output and mirrors the error/commons behavior of `benchmark gaps`.

**Tech Stack:** Python, Click, Rich, pytest, existing `science_tool` benchmark catalog/opportunity/gap helpers.

---

## File Structure

- Modify `science/src/science_tool/benchmark_opportunities.py`
  - Add typed dicts/literals for benchmark test rows, summaries, and reports.
  - Add pure helpers for task completeness, needs, readiness labels, matched facets, row projection, deduplication, filtering, sorting, and summaries.
  - Add public `benchmark_tests_report(...)`.
- Modify `science/src/science_tool/cli.py`
  - Add `science benchmark tests` command.
  - Resolve `--entity` like `benchmark gaps`.
  - Render JSON/table output.
- Modify `science/tests/test_benchmark_opportunities.py`
  - Add unit tests for report generation, state/filter semantics, scoring passthrough, deduplication, readiness labels, and commons degradation.
- Modify `science/tests/test_benchmark_cli.py`
  - Add CLI JSON/table/error tests for the new command.
- No schema changes.
- No file creation/mutation command behavior.

## Task 1: Core Benchmark Test Report Types And Concrete Opportunity Rows

**Files:**
- Modify: `science/src/science_tool/benchmark_opportunities.py`
- Test: `science/tests/test_benchmark_opportunities.py`

- [ ] **Step 1: Add failing test for concrete rows from matched opportunities**

Append this test near the other opportunity report tests in `science/tests/test_benchmark_opportunities.py`:

```python
def test_benchmark_tests_report_includes_concrete_opportunity_rows(tmp_path: Path) -> None:
    from science_tool.benchmark_opportunities import benchmark_tests_report

    _write_entity(
        tmp_path,
        "hypotheses",
        "0001-perturbation",
        """
id: hypothesis:0001-perturbation
type: hypothesis
title: Perturbation response hypothesis
""",
        body="Drug perturbation should shift single-cell response states.",
    )
    _write_dataset(
        tmp_path,
        "sciplex3",
        """
id: dataset:sciplex3
type: dataset
title: Sci-Plex 3
dataset_class: deposit
local_path: data/sciplex3
benchmark:
  domains: [biology]
  modalities: [single-cell-rna-seq]
  signal_types: [perturbation]
  benchmark_kinds: [perturbation-response]
  limitations:
    - Focused on measured transcriptional response.
  tasks:
    - id: compound-response
      task_type: perturbation response
      prediction_target: post-treatment expression
      held_out_unit: compound
      metric: rank-correlation
      baseline: nearest-neighbor
      ground_truth:
        type: measured-outcome
        description: measured expression after perturbation
""",
    )

    payload = benchmark_tests_report(tmp_path)

    assert payload["commons_notice"] is None
    assert payload["summary"]["test_plan_rows"] == 1
    assert payload["summary"]["concrete_rows"] == 1
    assert payload["summary"]["draft_needed_rows"] == 0
    row = payload["benchmark_tests"][0]
    assert row["entity_id"] == "hypothesis:0001-perturbation"
    assert row["benchmark_id"] == "dataset:sciplex3"
    assert row["task_id"] == "dataset:sciplex3#compound-response"
    assert row["test_plan_state"] == "concrete"
    assert row["task_type"] == "perturbation response"
    assert row["benchmark_kinds"] == ["perturbation-response"]
    assert row["readiness_label"] == "runnable"
    assert row["priority_source"] == "opportunity-relative"
    assert row["priority_score"] == sum(row["score_components"]["source"].values())
    assert row["score_components"]["baseline"]["task_completeness"] == 30
    assert row["matched_facets"] == ["perturbation", "single-cell-rna-seq"]
    assert row["prediction_target"] == "post-treatment expression"
    assert row["held_out_unit"] == "compound"
    assert row["metric"] == "rank-correlation"
    assert row["baseline"] == "nearest-neighbor"
    assert row["ground_truth"] == {
        "type": "measured-outcome",
        "description": "measured expression after perturbation",
    }
    assert row["needs"] == []
```

- [ ] **Step 2: Run the failing test**

Run:

```bash
rtk uv run --frozen --project science pytest science/tests/test_benchmark_opportunities.py::test_benchmark_tests_report_includes_concrete_opportunity_rows -q
```

Expected: FAIL with `ImportError` or `AttributeError` because `benchmark_tests_report` does not exist.

- [ ] **Step 3: Add report types and minimal concrete-row implementation**

In `science/src/science_tool/benchmark_opportunities.py`, add these imports:

```python
from science_tool.dataset_prioritize import readiness_for, readiness_weight
from science_tool.datasets.semantics import runtime_state_for
```

The file already imports `readiness_weight`; change that import line rather than adding a duplicate.

After `BenchmarkGapReport`, add:

```python
TestPlanState = Literal["concrete", "draft-needed"]
PrioritySource = Literal["opportunity-relative", "gap-candidate", "gap-fallback"]
ReadinessLabel = Literal["runnable", "stage-needed", "metadata-only", "blocked"]


class BenchmarkTestScoreComponents(TypedDict):
    source: dict[str, int]
    baseline: dict[str, int]


class BenchmarkTestGroundTruth(TypedDict):
    type: str
    description: str


class BenchmarkTestRow(TypedDict):
    entity_id: str
    entity_title: str
    benchmark_id: str
    benchmark_title: str
    task_id: str | None
    test_plan_state: TestPlanState
    task_type: str
    benchmark_kinds: list[str]
    readiness_label: ReadinessLabel
    priority_score: int
    priority_source: PrioritySource
    score_components: BenchmarkTestScoreComponents
    matched_facets: list[str]
    reason_notes: list[str]
    prediction_target: str
    held_out_unit: str
    metric: str
    baseline: str
    ground_truth: BenchmarkTestGroundTruth
    needs: list[str]


class BenchmarkTestSummary(TypedDict):
    entities_total: int
    test_plan_rows: int
    concrete_rows: int
    draft_needed_rows: int
    entities_with_test_plans: int
    entities_without_test_plans: int
    top_facets: list[FacetCountRow]


class BenchmarkTestReport(TypedDict):
    benchmark_tests: list[BenchmarkTestRow]
    summary: BenchmarkTestSummary
    commons_notice: str | None
```

Add these helpers before `_build_opportunity_report`:

```python
def _task_needs(task: OpportunityTask | None) -> list[str]:
    if task is None:
        return ["prediction-target", "held-out-unit", "metric", "baseline", "ground-truth"]
    needs: list[str] = []
    if not task.prediction_target:
        needs.append("prediction-target")
    if not task.held_out_unit:
        needs.append("held-out-unit")
    if not task.metric:
        needs.append("metric")
    if not task.baseline:
        needs.append("baseline")
    if not (task.ground_truth_type or task.ground_truth_description):
        needs.append("ground-truth")
    return needs


def _test_plan_state(task: OpportunityTask | None) -> TestPlanState:
    return "concrete" if task is not None and not _task_needs(task) else "draft-needed"


def _readiness_label(context: DatasetOpportunityContext, *, has_task: bool) -> ReadinessLabel:
    fm = context.dataset.frontmatter
    runtime_state = runtime_state_for(fm)
    readiness_state = readiness_for(dict(fm)).state
    if runtime_state in {"reference-only", "pointer-only"}:
        return "metadata-only"
    if readiness_state in {"embargoed", "withdrawn", "unknown"} or readiness_state.endswith(", unverified"):
        return "blocked"
    if readiness_state in {
        "derived-via-code",
        "derived-via-member-of",
        "derived-via-workflow-recipe",
        "consumable-via-scope-reduced",
        "consumable-via-substituted",
        "acquiring",
    }:
        return "stage-needed"
    if runtime_state == "runnable" and has_task:
        return "runnable"
    if runtime_state == "unstaged-deposit":
        return "stage-needed"
    if runtime_state == "blocked-access":
        return "blocked"
    if not has_task:
        return "metadata-only"
    return "metadata-only"


def _context_declared_hint_facets(context: DatasetOpportunityContext) -> set[str]:
    return _context_declared_facets(context) & BENCHMARK_GAP_HINT_FACET_SET


def _matched_facets_for_context(context: DatasetOpportunityContext, extra: set[str] | None = None) -> list[str]:
    facets = set(_normalized_values(context.dataset.modalities))
    facets.update(_normalized_values(context.dataset.signal_types))
    if extra:
        facets.update(extra & _context_declared_hint_facets(context))
    return _sorted_facets(facets)


def _ground_truth_payload(task: OpportunityTask | None) -> BenchmarkTestGroundTruth:
    return {
        "type": task.ground_truth_type if task is not None else "",
        "description": task.ground_truth_description if task is not None else "",
    }
```

Add this row builder:

```python
def _benchmark_test_row(
    *,
    entity_id: str,
    entity_title: str,
    context: DatasetOpportunityContext,
    task: OpportunityTask | None,
    priority_score: int,
    priority_source: PrioritySource,
    source_components: Mapping[str, int],
    reason_notes: list[str],
    matched_facets: list[str],
) -> BenchmarkTestRow:
    needs = _task_needs(task)
    return {
        "entity_id": entity_id,
        "entity_title": entity_title,
        "benchmark_id": context.dataset.id,
        "benchmark_title": context.dataset.title,
        "task_id": task.canonical_task_id if task is not None else None,
        "test_plan_state": _test_plan_state(task),
        "task_type": task.task_type if task is not None else "",
        "benchmark_kinds": list(context.dataset.benchmark_kinds),
        "readiness_label": _readiness_label(context, has_task=task is not None),
        "priority_score": priority_score,
        "priority_source": priority_source,
        "score_components": {
            "source": dict(source_components),
            "baseline": dict(context.baseline.components),
        },
        "matched_facets": matched_facets,
        "reason_notes": sorted(set(reason_notes), key=_reason_note_sort_key),
        "prediction_target": task.prediction_target if task is not None else "",
        "held_out_unit": task.held_out_unit if task is not None else "",
        "metric": task.metric if task is not None else "",
        "baseline": task.baseline if task is not None else "",
        "ground_truth": _ground_truth_payload(task),
        "needs": needs,
    }
```

Add these report helpers:

```python
def _rows_for_context_tasks(
    *,
    entity_id: str,
    entity_title: str,
    context: DatasetOpportunityContext,
    priority_score: int,
    priority_source: PrioritySource,
    source_components: Mapping[str, int],
    reason_notes: list[str],
    matched_facets: list[str],
) -> list[BenchmarkTestRow]:
    tasks = context.dataset.tasks
    if not tasks:
        return [
            _benchmark_test_row(
                entity_id=entity_id,
                entity_title=entity_title,
                context=context,
                task=None,
                priority_score=priority_score,
                priority_source=priority_source,
                source_components=source_components,
                reason_notes=[*reason_notes, "draft-needed"],
                matched_facets=matched_facets,
            )
        ]
    return [
        _benchmark_test_row(
            entity_id=entity_id,
            entity_title=entity_title,
            context=context,
            task=task,
            priority_score=priority_score,
            priority_source=priority_source,
            source_components=source_components,
            reason_notes=reason_notes if _test_plan_state(task) == "concrete" else [*reason_notes, "draft-needed"],
            matched_facets=matched_facets,
        )
        for task in tasks
    ]


def _benchmark_test_summary(rows: list[BenchmarkTestRow], *, entities_total: int) -> BenchmarkTestSummary:
    entity_ids = {row["entity_id"] for row in rows}
    facet_counts: Counter[str] = Counter()
    for row in rows:
        facet_counts.update(row["matched_facets"])
    return {
        "entities_total": entities_total,
        "test_plan_rows": len(rows),
        "concrete_rows": sum(1 for row in rows if row["test_plan_state"] == "concrete"),
        "draft_needed_rows": sum(1 for row in rows if row["test_plan_state"] == "draft-needed"),
        "entities_with_test_plans": len(entity_ids),
        "entities_without_test_plans": max(entities_total - len(entity_ids), 0),
        "top_facets": _top_facet_counts(facet_counts, top=10),
    }
```

Add the first version of the public report:

```python
def benchmark_tests_report(
    project_root: Path,
    *,
    include_commons: bool = False,
    entity_id: str | None = None,
    domain: str | None = None,
    facet: str | None = None,
    state: TestPlanState | None = None,
    benchmark_id: str | None = None,
) -> BenchmarkTestReport:
    normalized_facet = _normalized_gap_facet(facet)
    analysis = _opportunity_analysis(
        project_root,
        include_commons=include_commons,
        entity_id=entity_id,
        domain=domain,
        include_prose_tokens=False,
    )
    contexts = {context.dataset.id: context for context in analysis.contexts}
    rows: list[BenchmarkTestRow] = []
    for opportunity in analysis.report["matched_opportunities"]:
        context = contexts.get(opportunity["benchmark_id"])
        if context is None:
            continue
        task_id = opportunity["task_id"]
        tasks = [
            task
            for task in context.dataset.tasks
            if task_id is None or task.canonical_task_id == task_id
        ]
        if not tasks:
            tasks = context.dataset.tasks
        for row in _rows_for_context_tasks(
            entity_id=opportunity["entity_id"],
            entity_title=opportunity["entity_title"],
            context=context,
            priority_score=opportunity["relative_score"],
            priority_source="opportunity-relative",
            source_components=opportunity["score_components"]["relative"],
            reason_notes=opportunity["match_reasons"],
            matched_facets=_matched_facets_for_context(context),
        ):
            if task_id is None or row["task_id"] == task_id:
                rows.append(row)
    rows = _filter_benchmark_test_rows(
        rows,
        normalized_facet=normalized_facet,
        state=state,
        benchmark_id=_normalize_benchmark_filter(benchmark_id),
    )
    rows.sort(key=_benchmark_test_sort_key)
    return {
        "benchmark_tests": rows,
        "summary": _benchmark_test_summary(rows, entities_total=len(analysis.entities)),
        "commons_notice": analysis.report["commons_notice"],
    }
```

Add these filter/sort helpers used above:

```python
def _normalize_benchmark_filter(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    if not stripped:
        return None
    return stripped if stripped.startswith("dataset:") else f"dataset:{stripped}"


def _filter_benchmark_test_rows(
    rows: list[BenchmarkTestRow],
    *,
    normalized_facet: str | None,
    state: TestPlanState | None,
    benchmark_id: str | None,
) -> list[BenchmarkTestRow]:
    filtered = rows
    if normalized_facet is not None:
        filtered = [row for row in filtered if normalized_facet in row["matched_facets"]]
    if state is not None:
        filtered = [row for row in filtered if row["test_plan_state"] == state]
    if benchmark_id is not None:
        filtered = [row for row in filtered if row["benchmark_id"] == benchmark_id]
    return filtered


def _benchmark_test_state_sort_key(state: TestPlanState) -> int:
    return 0 if state == "concrete" else 1


def _benchmark_test_sort_key(row: BenchmarkTestRow) -> tuple[int, int, str, str, str]:
    return (
        _benchmark_test_state_sort_key(row["test_plan_state"]),
        -row["priority_score"],
        row["entity_id"],
        row["benchmark_id"],
        row["task_id"] or "",
    )
```

- [ ] **Step 4: Run the concrete-row test**

Run:

```bash
rtk uv run --frozen --project science pytest science/tests/test_benchmark_opportunities.py::test_benchmark_tests_report_includes_concrete_opportunity_rows -q
```

Expected: PASS.

- [ ] **Step 5: Run ruff on touched Python files**

Run:

```bash
rtk uv run --frozen --project science ruff check science/src/science_tool/benchmark_opportunities.py science/tests/test_benchmark_opportunities.py
```

Expected: `All checks passed!`

- [ ] **Step 6: Commit**

```bash
rtk git add science/src/science_tool/benchmark_opportunities.py science/tests/test_benchmark_opportunities.py
rtk git commit -m "feat(benchmark): add benchmark tests report rows"
```

## Task 2: Draft-Needed Rows, Gap Candidates, Deduplication, And Filters

**Files:**
- Modify: `science/src/science_tool/benchmark_opportunities.py`
- Test: `science/tests/test_benchmark_opportunities.py`

- [ ] **Step 1: Add failing tests for draft-needed rows and filters**

Append:

```python
def test_benchmark_tests_report_includes_draft_needed_gap_candidates(tmp_path: Path) -> None:
    from science_tool.benchmark_opportunities import benchmark_tests_report

    _write_entity(
        tmp_path,
        "hypotheses",
        "0002-spatial",
        """
id: hypothesis:0002-spatial
type: hypothesis
title: Region validation hypothesis
""",
        body="Tumor microenvironment region structure needs validation.",
    )
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

    payload = benchmark_tests_report(tmp_path)

    assert payload["summary"]["test_plan_rows"] == 1
    assert payload["summary"]["draft_needed_rows"] == 1
    row = payload["benchmark_tests"][0]
    assert row["test_plan_state"] == "draft-needed"
    assert row["priority_source"] == "gap-candidate"
    assert row["task_id"] is None
    assert row["readiness_label"] == "metadata-only"
    assert row["matched_facets"] == ["spatial", "cross-context-generalization"]
    assert "entity-hint:spatial" in row["reason_notes"]
    assert row["priority_score"] == min(sum(row["score_components"]["source"].values()), 100)
    assert row["needs"] == ["prediction-target", "held-out-unit", "metric", "baseline", "ground-truth"]


def test_benchmark_tests_report_filters_state_facet_and_benchmark(tmp_path: Path) -> None:
    from science_tool.benchmark_opportunities import benchmark_tests_report

    _write_entity(
        tmp_path,
        "hypotheses",
        "0003-drug",
        """
id: hypothesis:0003-drug
type: hypothesis
title: Drug response hypothesis
""",
        body="Drug compound knockout screen should be tested.",
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
  modalities: [single-cell-rna-seq]
  signal_types: [perturbation]
  benchmark_kinds: [perturbation-response]
  tasks:
    - id: compound-response
      task_type: perturbation response
      prediction_target: expression
      held_out_unit: compound
      metric: rank-correlation
      baseline: nearest-neighbor
      ground_truth:
        type: measured-outcome
        description: expression
""",
    )
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
""",
    )

    by_state = benchmark_tests_report(tmp_path, state="concrete")
    assert [row["benchmark_id"] for row in by_state["benchmark_tests"]] == ["dataset:sciplex3"]

    by_facet = benchmark_tests_report(tmp_path, facet="perturbation")
    assert [row["benchmark_id"] for row in by_facet["benchmark_tests"]] == ["dataset:sciplex3"]

    by_benchmark = benchmark_tests_report(tmp_path, benchmark_id="sciplex3")
    assert [row["benchmark_id"] for row in by_benchmark["benchmark_tests"]] == ["dataset:sciplex3"]


def test_benchmark_tests_report_does_not_project_gap_current_matches_as_rows(tmp_path: Path) -> None:
    from science_tool.benchmark_opportunities import benchmark_tests_report

    _write_entity(
        tmp_path,
        "hypotheses",
        "0004-weak",
        """
id: hypothesis:0004-weak
type: hypothesis
title: Weak spatial hypothesis
""",
        body="Spatial hypothesis.",
    )
    _write_dataset(
        tmp_path,
        "atlas",
        """
id: dataset:atlas
type: dataset
title: Atlas
dataset_class: reference
benchmark:
  domains: [biology]
  modalities: [spatial]
  signal_types: []
  benchmark_kinds: [static-association]
""",
    )

    payload = benchmark_tests_report(tmp_path)

    keys = [(row["entity_id"], row["benchmark_id"], row["task_id"]) for row in payload["benchmark_tests"]]
    assert keys == [("hypothesis:0004-weak", "dataset:atlas", None)]
    row = payload["benchmark_tests"][0]
    assert row["priority_source"] == "opportunity-relative"


def test_benchmark_tests_report_merges_duplicate_rows_by_source_precedence() -> None:
    from science_tool.benchmark_opportunities import _dedupe_benchmark_test_rows

    base = {
        "entity_id": "hypothesis:0005-merge",
        "entity_title": "Merge",
        "benchmark_id": "dataset:merge",
        "benchmark_title": "Merge Benchmark",
        "task_id": None,
        "test_plan_state": "draft-needed",
        "task_type": "",
        "benchmark_kinds": ["static-association"],
        "readiness_label": "metadata-only",
        "priority_score": 10,
        "priority_source": "gap-fallback",
        "score_components": {"source": {"task_readiness": 10}, "baseline": {}},
        "matched_facets": ["spatial"],
        "reason_notes": ["fallback:task-ready"],
        "prediction_target": "",
        "held_out_unit": "",
        "metric": "",
        "baseline": "",
        "ground_truth": {"type": "", "description": ""},
        "needs": ["prediction-target", "held-out-unit", "metric", "baseline", "ground-truth"],
    }
    stronger = {
        **base,
        "priority_score": 25,
        "priority_source": "opportunity-relative",
        "score_components": {"source": {"facet_overlap": 25}, "baseline": {}},
        "matched_facets": ["perturbation"],
        "reason_notes": ["facet-token:perturbation"],
    }

    rows = _dedupe_benchmark_test_rows([base, stronger])

    assert len(rows) == 1
    assert rows[0]["priority_source"] == "opportunity-relative"
    assert rows[0]["priority_score"] == 25
    assert rows[0]["matched_facets"] == ["perturbation", "spatial"]
    assert rows[0]["reason_notes"] == ["facet-token:perturbation", "fallback:task-ready"]
```

- [ ] **Step 2: Run tests to verify failures**

Run:

```bash
rtk uv run --frozen --project science pytest \
  science/tests/test_benchmark_opportunities.py::test_benchmark_tests_report_includes_draft_needed_gap_candidates \
  science/tests/test_benchmark_opportunities.py::test_benchmark_tests_report_filters_state_facet_and_benchmark \
  science/tests/test_benchmark_opportunities.py::test_benchmark_tests_report_does_not_project_gap_current_matches_as_rows \
  science/tests/test_benchmark_opportunities.py::test_benchmark_tests_report_merges_duplicate_rows_by_source_precedence \
  -q
```

Expected: FAIL because gap candidates are not projected yet and filters are incomplete for gap rows.

- [ ] **Step 3: Add gap projection and dedup helpers**

In `benchmark_tests_report`, after building opportunity rows and before filtering, compute a gap report and append gap candidate rows:

```python
    gap_payload = gaps_report(
        project_root,
        include_commons=include_commons,
        entity_id=entity_id,
        domain=domain,
        facet=facet,
    )
    candidate_components = _gap_candidate_components(
        gap_payload,
        entities=analysis.entities,
        contexts=analysis.contexts,
    )
    for gap_row in gap_payload["benchmark_gaps"]:
        entity_title = gap_row["entity_title"]
        entity_id_for_row = gap_row["entity_id"]
        for candidate in gap_row["candidate_benchmarks"]:
            context = contexts.get(candidate["benchmark_id"])
            if context is None:
                continue
            source = "gap-fallback" if _is_fallback_candidate(candidate) else "gap-candidate"
            matched_facets = _matched_facets_for_context(
                context,
                extra=set(candidate["matched_missing_facets"]) | set(candidate["matched_hint_facets"]),
            )
            rows.extend(
                _rows_for_context_tasks(
                    entity_id=entity_id_for_row,
                    entity_title=entity_title,
                    context=context,
                    priority_score=candidate["candidate_score"],
                    priority_source=source,
                    source_components=candidate_components.get(
                        (entity_id_for_row, candidate["benchmark_id"]),
                        {},
                    ),
                    reason_notes=candidate["reason_notes"],
                    matched_facets=matched_facets,
                )
            )
    rows = _dedupe_benchmark_test_rows(rows)
```

Add the helper referenced above:

```python
def _gap_candidate_components(
    gap_payload: BenchmarkGapReport,
    *,
    entities: list[ProjectBenchmarkEntity],
    contexts: list[DatasetOpportunityContext],
) -> dict[tuple[str, str], dict[str, int]]:
    entity_by_id = {entity.id: entity for entity in entities}
    context_by_id = {context.dataset.id: context for context in contexts}
    components: dict[tuple[str, str], dict[str, int]] = {}
    for row in gap_payload["benchmark_gaps"]:
        entity = entity_by_id.get(row["entity_id"])
        if entity is None:
            continue
        hint_facets = set(_entity_facet_hints(entity))
        missing_facets = {_normalize_token(value) for value in row["missing_modalities"] + row["missing_signal_types"]}
        for candidate in row["candidate_benchmarks"]:
            context = context_by_id.get(candidate["benchmark_id"])
            if context is None:
                continue
            score = _candidate_score(context, missing_facets=missing_facets, hint_facets=hint_facets)
            components[(row["entity_id"], candidate["benchmark_id"])] = dict(score.components)
    return components
```

Add dedup helpers:

```python
def _benchmark_test_source_rank(source: PrioritySource) -> int:
    return {
        "opportunity-relative": 0,
        "gap-candidate": 1,
        "gap-fallback": 2,
    }[source]


def _merge_benchmark_test_rows(existing: BenchmarkTestRow, incoming: BenchmarkTestRow) -> BenchmarkTestRow:
    keep, other = (
        (existing, incoming)
        if _benchmark_test_source_rank(existing["priority_source"]) <= _benchmark_test_source_rank(incoming["priority_source"])
        else (incoming, existing)
    )
    return {
        **keep,
        "reason_notes": sorted({*keep["reason_notes"], *other["reason_notes"]}, key=_reason_note_sort_key),
        "matched_facets": _sorted_facets(set(keep["matched_facets"]) | set(other["matched_facets"])),
    }


def _dedupe_benchmark_test_rows(rows: list[BenchmarkTestRow]) -> list[BenchmarkTestRow]:
    by_key: dict[tuple[str, str, str | None], BenchmarkTestRow] = {}
    for row in rows:
        key = (row["entity_id"], row["benchmark_id"], row["task_id"])
        if key in by_key:
            by_key[key] = _merge_benchmark_test_rows(by_key[key], row)
        else:
            by_key[key] = row
    return list(by_key.values())
```

- [ ] **Step 4: Run focused tests**

Run:

```bash
rtk uv run --frozen --project science pytest \
  science/tests/test_benchmark_opportunities.py::test_benchmark_tests_report_includes_draft_needed_gap_candidates \
  science/tests/test_benchmark_opportunities.py::test_benchmark_tests_report_filters_state_facet_and_benchmark \
  science/tests/test_benchmark_opportunities.py::test_benchmark_tests_report_does_not_project_gap_current_matches_as_rows \
  science/tests/test_benchmark_opportunities.py::test_benchmark_tests_report_merges_duplicate_rows_by_source_precedence \
  -q
```

Expected: PASS.

- [ ] **Step 5: Add readiness label coverage test**

Append:

```python
def test_benchmark_tests_report_readiness_labels_cover_runtime_states(tmp_path: Path) -> None:
    from science_tool.benchmark_opportunities import _dataset_context, _readiness_label, load_opportunity_datasets

    cases = [
        ("runnable", "dataset_class: deposit\nlocal_path: data/runnable", True, "runnable"),
        (
            "unstaged",
            "origin: external\ndataset_class: deposit\naccess:\n  level: public\n  availability: available\n  verified: true",
            True,
            "stage-needed",
        ),
        ("derived", "origin: derived\ndataset_class: deposit\nproduced_by: [code-file:builder]", True, "stage-needed"),
        (
            "embargoed",
            "origin: external\ndataset_class: deposit\naccess:\n  level: public\n  availability: embargoed\n  verified: true",
            True,
            "blocked",
        ),
        ("reference", "dataset_class: reference", False, "metadata-only"),
        ("pointer", "dataset_class: pointer", False, "metadata-only"),
        (
            "blocked",
            "origin: external\ndataset_class: deposit\naccess:\n  level: controlled\n  availability: available\n  verified: false",
            True,
            "blocked",
        ),
    ]
    for slug, access_block, has_task, expected in cases:
        tasks = """
  tasks:
    - id: task
      task_type: prediction
      prediction_target: target
      held_out_unit: unit
      metric: auroc
      baseline: baseline
      ground_truth:
        type: label
        description: label
""" if has_task else ""
        _write_dataset(
            tmp_path,
            slug,
            f"""
id: dataset:{slug}
type: dataset
title: {slug}
{access_block}
benchmark:
  domains: [biology]
  modalities: [spatial]
  signal_types: [perturbation]
  benchmark_kinds: [static-association]
{tasks}""",
        )

    datasets, _notice = load_opportunity_datasets(tmp_path, include_commons=False)
    labels = {
        dataset.id: _readiness_label(_dataset_context(dataset, include_prose_tokens=False), has_task=bool(dataset.tasks))
        for dataset in datasets
    }

    assert labels == {
        "dataset:blocked": "blocked",
        "dataset:derived": "stage-needed",
        "dataset:embargoed": "blocked",
        "dataset:pointer": "metadata-only",
        "dataset:reference": "metadata-only",
        "dataset:runnable": "runnable",
        "dataset:unstaged": "stage-needed",
    }
```

- [ ] **Step 6: Run readiness test**

Run:

```bash
rtk uv run --frozen --project science pytest science/tests/test_benchmark_opportunities.py::test_benchmark_tests_report_readiness_labels_cover_runtime_states -q
```

Expected: PASS.

- [ ] **Step 7: Run ruff and focused benchmark tests**

Run:

```bash
rtk uv run --frozen --project science ruff check science/src/science_tool/benchmark_opportunities.py science/tests/test_benchmark_opportunities.py
rtk uv run --frozen --project science pytest science/tests/test_benchmark_opportunities.py -q
```

Expected: ruff passes and benchmark opportunities tests pass.

- [ ] **Step 8: Commit**

```bash
rtk git add science/src/science_tool/benchmark_opportunities.py science/tests/test_benchmark_opportunities.py
rtk git commit -m "feat(benchmark): project benchmark test gaps"
```

## Task 3: CLI Command

**Files:**
- Modify: `science/src/science_tool/cli.py`
- Test: `science/tests/test_benchmark_cli.py`

- [ ] **Step 1: Add CLI helper and JSON/table tests**

In `science/tests/test_benchmark_cli.py`, add:

```python
def _invoke_tests(tmp_path: Path, *args: str):
    return CliRunner().invoke(
        science_cli,
        ["benchmark", "tests", *args],
        catch_exceptions=False,
        env={"SCIENCE_PROJECT_ROOT": str(tmp_path), "SCIENCE_COMMONS_ROOT": str(tmp_path / "no-commons")},
    )
```

Append these tests:

```python
def test_benchmark_tests_cli_json_output(tmp_path: Path) -> None:
    _write_entity(
        tmp_path,
        "hypotheses",
        "0001-perturbation",
        """
id: hypothesis:0001-perturbation
type: hypothesis
title: Perturbation response hypothesis
""",
        body="Drug perturbation should shift response states.",
    )
    _write_dataset(
        tmp_path,
        "sciplex3",
        """
id: dataset:sciplex3
type: dataset
title: Sci-Plex 3
dataset_class: deposit
local_path: data/sciplex3
benchmark:
  domains: [biology]
  modalities: [single-cell-rna-seq]
  signal_types: [perturbation]
  benchmark_kinds: [perturbation-response]
  tasks:
    - id: compound-response
      task_type: perturbation response
      prediction_target: expression
      held_out_unit: compound
      metric: rank-correlation
      baseline: nearest-neighbor
      ground_truth:
        type: measured-outcome
        description: expression
""",
    )

    result = _invoke_tests(tmp_path, "--format", "json")

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["summary"]["concrete_rows"] == 1
    assert payload["benchmark_tests"][0]["test_plan_state"] == "concrete"
    assert payload["benchmark_tests"][0]["priority_source"] == "opportunity-relative"


def test_benchmark_tests_cli_table_output(tmp_path: Path) -> None:
    _write_entity(
        tmp_path,
        "hypotheses",
        "0002-spatial",
        """
id: hypothesis:0002-spatial
type: hypothesis
title: Spatial hypothesis
""",
        body="Microenvironment region needs spatial validation.",
    )
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
""",
    )

    result = _invoke_tests(tmp_path)

    assert result.exit_code == 0
    assert "Benchmark Tests" in result.output
    assert "hypothesis:0002-spatial" in result.output
    assert "draft-needed" in result.output
    assert "dataset:hca-spatial" in result.output
    assert "prediction-target" in result.output


def test_benchmark_tests_cli_filters_and_empty_state(tmp_path: Path) -> None:
    _write_entity(
        tmp_path,
        "hypotheses",
        "0003-drug",
        """
id: hypothesis:0003-drug
type: hypothesis
title: Drug hypothesis
""",
        body="Drug compound knockout screen should be tested.",
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
  modalities: [single-cell-rna-seq]
  signal_types: [perturbation]
  benchmark_kinds: [perturbation-response]
""",
    )

    result = _invoke_tests(tmp_path, "--state", "concrete")

    assert result.exit_code == 0
    assert "No benchmark test plans." in result.output


def test_benchmark_tests_cli_invalid_entity_and_facet_errors(tmp_path: Path) -> None:
    entity_result = _invoke_tests(tmp_path, "--entity", "hypothesis:missing")
    assert entity_result.exit_code != 0
    assert "Entity not found" in entity_result.output

    facet_result = _invoke_tests(tmp_path, "--facet", "not-a-facet")
    assert facet_result.exit_code != 0
    assert "unknown benchmark gap facet" in facet_result.output
```

- [ ] **Step 2: Run CLI tests to verify failure**

Run:

```bash
rtk uv run --frozen --project science pytest \
  science/tests/test_benchmark_cli.py::test_benchmark_tests_cli_json_output \
  science/tests/test_benchmark_cli.py::test_benchmark_tests_cli_table_output \
  science/tests/test_benchmark_cli.py::test_benchmark_tests_cli_filters_and_empty_state \
  science/tests/test_benchmark_cli.py::test_benchmark_tests_cli_invalid_entity_and_facet_errors \
  -q
```

Expected: FAIL because `benchmark tests` command does not exist.

- [ ] **Step 3: Add `science benchmark tests` command**

In `science/src/science_tool/cli.py`, add this command after `benchmark_gap_calibration` and before `benchmark_gaps`:

```python
@benchmark_group.command("tests")
@click.option("--domain", default=None, help="Filter benchmark datasets by benchmark domain.")
@click.option("--entity", "entity_ref", default=None, help="Limit report to one project entity reference.")
@click.option("--facet", default=None, help="Limit test plans to a high-value benchmark facet.")
@click.option("--state", default=None, type=click.Choice(["concrete", "draft-needed"]), help="Filter by test plan state.")
@click.option("--benchmark", "benchmark_ref", default=None, help="Filter by exact benchmark dataset id or slug.")
@click.option("--commons", "include_commons", is_flag=True, help="Also include commons benchmark dataset entities.")
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
def benchmark_tests(
    domain: str | None,
    entity_ref: str | None,
    facet: str | None,
    state: str | None,
    benchmark_ref: str | None,
    include_commons: bool,
    output_format: str,
    project_root: Path | None,
) -> None:
    """Report candidate benchmark test plans for project entities."""
    from rich.console import Console
    from rich.table import Table

    from science_tool.benchmark_opportunities import benchmark_tests_report
    from science_tool.entities import EntityCommandError, resolve_entity_ref

    root = project_root.resolve() if project_root else _project_root_from_env()
    entity_id: str | None = None
    if entity_ref is not None:
        try:
            entity_id = resolve_entity_ref(root, entity_ref)
        except EntityCommandError as exc:
            raise click.ClickException(str(exc)) from exc

    try:
        payload = benchmark_tests_report(
            root,
            include_commons=include_commons,
            entity_id=entity_id,
            domain=domain,
            facet=facet,
            state=state,  # type: ignore[arg-type]
            benchmark_id=benchmark_ref,
        )
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc

    notice = payload["commons_notice"]
    if notice:
        click.echo(f"notice: commons benchmarks unavailable ({notice})", err=True)

    if output_format == "json":
        click.echo(json.dumps(payload, indent=2, sort_keys=True))
        return

    rows = payload["benchmark_tests"]
    if not rows:
        click.echo("No benchmark test plans.")
        return

    table = Table(title="Benchmark Tests", show_header=True, header_style="bold")
    for col in ("entity", "state", "benchmark", "task", "score", "facets", "needs"):
        table.add_column(col, overflow="fold", no_wrap=False)
    for row in rows:
        table.add_row(
            row["entity_id"],
            row["test_plan_state"],
            row["benchmark_id"],
            row["task_id"] or "-",
            str(row["priority_score"]),
            ", ".join(row["matched_facets"]) or "-",
            ", ".join(row["needs"]) or "-",
        )
    Console(width=200).print(table)
```

If ruff rejects the `type: ignore[arg-type]`, replace the call argument with:

```python
            state=cast("Any", state),
```

and add `cast` to the existing imports from `typing`.

- [ ] **Step 4: Run CLI tests**

Run:

```bash
rtk uv run --frozen --project science pytest \
  science/tests/test_benchmark_cli.py::test_benchmark_tests_cli_json_output \
  science/tests/test_benchmark_cli.py::test_benchmark_tests_cli_table_output \
  science/tests/test_benchmark_cli.py::test_benchmark_tests_cli_filters_and_empty_state \
  science/tests/test_benchmark_cli.py::test_benchmark_tests_cli_invalid_entity_and_facet_errors \
  -q
```

Expected: PASS.

- [ ] **Step 5: Add commons notice CLI test**

Append:

```python
def test_benchmark_tests_cli_commons_unavailable_degrades_to_local_rows(tmp_path: Path) -> None:
    _write_entity(
        tmp_path,
        "hypotheses",
        "0004-local",
        """
id: hypothesis:0004-local
type: hypothesis
title: Local hypothesis
""",
        body="Drug response should be tested.",
    )
    _write_dataset(
        tmp_path,
        "local-benchmark",
        """
id: dataset:local-benchmark
type: dataset
title: Local Benchmark
dataset_class: pointer
benchmark:
  domains: [biology]
  modalities: [single-cell-rna-seq]
  signal_types: [perturbation]
  benchmark_kinds: [perturbation-response]
""",
    )

    result = _invoke_tests(tmp_path, "--commons", "--format", "json")

    assert result.exit_code == 0
    assert "notice: commons benchmarks unavailable" in result.stderr
    payload = json.loads(result.output)
    assert payload["commons_notice"] is not None
    assert payload["benchmark_tests"]
```

- [ ] **Step 6: Run CLI benchmark tests**

Run:

```bash
rtk uv run --frozen --project science pytest science/tests/test_benchmark_cli.py -q
```

Expected: PASS.

- [ ] **Step 7: Run ruff on CLI/test files**

Run:

```bash
rtk uv run --frozen --project science ruff check science/src/science_tool/cli.py science/tests/test_benchmark_cli.py
```

Expected: `All checks passed!`

- [ ] **Step 8: Commit**

```bash
rtk git add science/src/science_tool/cli.py science/tests/test_benchmark_cli.py
rtk git commit -m "feat(cli): add benchmark tests report"
```

## Task 4: End-To-End Verification And Real-Project Smoke Test

**Files:**
- Modify: none expected
- Test: existing test files

- [ ] **Step 1: Run focused Python verification**

Run:

```bash
rtk uv run --frozen --project science ruff check \
  science/src/science_tool/benchmark_opportunities.py \
  science/src/science_tool/cli.py \
  science/tests/test_benchmark_opportunities.py \
  science/tests/test_benchmark_cli.py
rtk uv run --frozen --project science pytest \
  science/tests/test_benchmark_opportunities.py \
  science/tests/test_benchmark_cli.py \
  -q
```

Expected: ruff passes and pytest reports all tests in both files passing.

- [ ] **Step 2: Run real-project JSON smoke test**

Run:

```bash
SCIENCE_COMMONS_ROOT=~/d/science-commons rtk uv run --frozen --project science science benchmark tests \
  --project-root ~/d/cancer/cancer-types/multiple-myeloma \
  --commons \
  --format json
```

Expected:
- exit code 0;
- valid JSON;
- top-level keys include `benchmark_tests`, `summary`, and `commons_notice`;
- `benchmark_tests` may be empty if the project has no current benchmark-test
  projections after filters; that is not a smoke-test failure;
- no traceback.

If output is large, rerun with a summarizing Python command instead of pasting the full JSON:

```bash
SCIENCE_COMMONS_ROOT=~/d/science-commons rtk uv run --frozen --project science python -c 'import json; from pathlib import Path; from science_tool.benchmark_opportunities import benchmark_tests_report; p=benchmark_tests_report(Path.home()/"d/cancer/cancer-types/multiple-myeloma", include_commons=True); print(json.dumps({"summary": p["summary"], "first": p["benchmark_tests"][:2], "commons_notice": p["commons_notice"]}, indent=2))'
```

Expected: JSON summary prints without traceback.

- [ ] **Step 3: Run table smoke test**

Run:

```bash
SCIENCE_COMMONS_ROOT=~/d/science-commons rtk uv run --frozen --project science science benchmark tests \
  --project-root ~/d/cancer/cancer-types/multiple-myeloma \
  --commons \
  --state concrete
```

Expected:
- exit code 0;
- either a `Benchmark Tests` table or `No benchmark test plans.`;
- no traceback.

- [ ] **Step 4: Check git status and commit if needed**

Run:

```bash
rtk git status --short
```

Expected: no unstaged implementation changes. If Task 4 required any small fix, commit it with:

```bash
rtk git add science/src/science_tool/benchmark_opportunities.py science/src/science_tool/cli.py science/tests/test_benchmark_opportunities.py science/tests/test_benchmark_cli.py
rtk git commit -m "test(benchmark): verify benchmark tests report"
```

## Self-Review

### Spec Coverage

- Read-only `science benchmark tests`: Task 3.
- Concrete and draft-needed rows: Tasks 1 and 2.
- Projection over existing opportunity/gap analysis: Tasks 1 and 2.
- No second matcher: implementation uses `_opportunity_analysis`, `gaps_report`, existing candidate scoring, and existing context helpers.
- Score passthrough with `priority_source`: Tasks 1 and 2.
- Matched facet projection and `--facet`: Tasks 1 and 2.
- Readiness labels from runtime/readiness APIs: Task 2.
- CLI JSON/table and empty state: Task 3.
- Commons notice behavior: Task 3 and Task 4.
- Real-project smoke validation: Task 4.

### Placeholder Scan

No placeholder markers are intentionally present. All test and implementation steps include concrete code or commands.

### Type Consistency

- `test_plan_state` values are `concrete` and `draft-needed`.
- `priority_source` values are `opportunity-relative`, `gap-candidate`, and `gap-fallback`.
- Row field name is `readiness_label`, not `readiness`.
- `score_components.source` contains only the source score's real component keys; tests assert passthrough by comparing `priority_score` to the applicable source score or component sum for fixtures where no clamp applies.
- `benchmark_id` filter normalizes bare slugs to `dataset:<slug>`.

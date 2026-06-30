# Benchmark Actionability Tuning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make benchmark gap/test reports more actionable by surfacing candidate modes, demoting fallback rows in default ordering, and separating cleaner domain term evidence from project-local/workflow noise.

**Architecture:** Extend the existing `science_tool.benchmark_opportunities` projections without changing the matcher or scoring formulas. Additive JSON fields preserve compatibility; table rendering reads the same row-level fields exposed in JSON. Evidence term categorization is deterministic and local-first.

**Tech Stack:** Python, Click, Rich tables, pytest, existing `science_tool.benchmark_opportunities` report helpers.

---

## File Structure

- Modify `science/src/science_tool/benchmark_opportunities.py`
  - Add `candidate_mode` to `BenchmarkGapRow`.
  - Add shared gap candidate count helper used by `_gap_summary()` and `gap_calibration_summary()`.
  - Add source/readiness counts to `BenchmarkTestSummary`.
  - Update `_benchmark_test_sort_key()` to sort by state, source, readiness, score, ids.
  - Add evidence term category typed dicts and deterministic categorization helpers.
- Modify `science/src/science_tool/cli.py`
  - Render `candidate_mode` in `science benchmark gaps` table output.
  - Compact fallback-only candidate cells.
- Modify `science/tests/test_benchmark_opportunities.py`
  - Add unit coverage for gap summary/mode, benchmark-test sorting/summary, and evidence term categories.
  - Update existing assertions for expanded summary fields where needed.
- Modify `science/tests/test_benchmark_cli.py`
  - Add or update CLI table assertions for candidate mode and compact fallback display.
- No schema changes.
- No commons metadata changes.

## Task 1: Add Gap Candidate Mode And Shared Summary Counts

**Files:**
- Modify: `science/src/science_tool/benchmark_opportunities.py`
- Test: `science/tests/test_benchmark_opportunities.py`

- [ ] **Step 1: Add failing test for row candidate mode and summary counts**

Append this test near `test_gap_calibration_summary_projects_gap_report_metrics` in `science/tests/test_benchmark_opportunities.py`:

```python
def test_gaps_report_summary_includes_actionability_candidate_counts(tmp_path: Path) -> None:
    from science_tool.benchmark_opportunities import gap_calibration_summary, gaps_report

    _write_entity(
        tmp_path,
        "hypotheses",
        "0040-drug-screen",
        """
id: hypothesis:0040-drug-screen
type: hypothesis
title: Drug screen benchmark gap
""",
        body="Drug compound knockout screen should be tested.",
    )
    _write_entity(
        tmp_path,
        "hypotheses",
        "0041-generic",
        """
id: hypothesis:0041-generic
type: hypothesis
title: Generic benchmark gap
""",
        body="Homeostatic recovery remains under-tested.",
    )
    _write_dataset(
        tmp_path,
        "sciplex",
        """
id: dataset:sciplex
type: dataset
title: Sci-Plex
benchmark:
  domains: [biology]
  modalities: [single-cell-rna-seq]
  signal_types: [perturbation]
  benchmark_kinds: [perturbation-response]
  tasks:
    - id: compound-response
      prediction_target: response
      held_out_unit: compound
      metric: rank-correlation
      baseline: nearest-neighbor
      ground_truth:
        type: measured-outcome
        description: measured response
""",
    )
    _write_dataset(
        tmp_path,
        "generic",
        """
id: dataset:generic
type: dataset
title: Generic Benchmark
benchmark:
  domains: [biology]
  modalities: [assay]
  signal_types: [unrelated]
  benchmark_kinds: [static-association]
  tasks:
    - id: ready
      prediction_target: label
      held_out_unit: cohort
      metric: auroc
      baseline: majority-class
      ground_truth:
        type: measured-outcome
        description: label
""",
    )

    report = gaps_report(tmp_path)

    rows = {row["entity_id"]: row for row in report["benchmark_gaps"]}
    assert rows["hypothesis:0040-drug-screen"]["candidate_mode"] == "entity-specific"
    assert rows["hypothesis:0041-generic"]["candidate_mode"] == "fallback-only"
    assert report["summary"]["candidate_rows"] == 3
    assert report["summary"]["entity_specific_candidate_rows"] == 1
    assert report["summary"]["fallback_candidate_rows"] == 2
    assert report["summary"]["fallback_candidate_ratio"] == pytest.approx(2 / 3)
    assert report["summary"]["gap_candidate_mode_counts"] == {
        "entity-specific": 1,
        "fallback-only": 1,
        "none": 0,
    }

    calibration = gap_calibration_summary(report)
    assert calibration["candidate_rows"] == report["summary"]["candidate_rows"]
    assert calibration["entity_specific_candidate_rows"] == report["summary"]["entity_specific_candidate_rows"]
    assert calibration["fallback_candidate_rows"] == report["summary"]["fallback_candidate_rows"]
```

- [ ] **Step 2: Run the failing test**

```bash
rtk uv run --frozen --project science pytest science/tests/test_benchmark_opportunities.py::test_gaps_report_summary_includes_actionability_candidate_counts -q
```

Expected: FAIL with `KeyError: 'candidate_mode'` or missing summary keys.

- [ ] **Step 3: Extend typed dicts**

In `science/src/science_tool/benchmark_opportunities.py`, update `BenchmarkGapRow`:

```python
class BenchmarkGapRow(TypedDict):
    entity_id: str
    entity_title: str
    gap_level: GapLevel
    missing_modalities: list[str]
    missing_signal_types: list[str]
    current_matches: list[GapCurrentMatchRow]
    candidate_benchmarks: list[GapCandidateBenchmarkRow]
    candidate_mode: CandidateMode
    suggested_search_facets: list[str]
    reason: str
```

Move `CandidateMode = Literal["entity-specific", "fallback-only", "none"]` above `BenchmarkGapRow` if needed so the type is defined before use.

Update `BenchmarkGapSummary`:

```python
class BenchmarkGapSummary(TypedDict):
    entities_total: int
    entities_with_gaps: int
    uncovered_entities: int
    weakly_covered_entities: int
    missing_facet_entities: int
    candidate_rows: int
    entity_specific_candidate_rows: int
    fallback_candidate_rows: int
    fallback_candidate_ratio: float
    gap_candidate_mode_counts: dict[CandidateMode, int]
```

- [ ] **Step 4: Add shared candidate counting helper**

Add this helper near `_candidate_mode()`:

```python
class GapCandidateCounts(TypedDict):
    candidate_rows: int
    entity_specific_candidate_rows: int
    fallback_candidate_rows: int
    fallback_candidate_ratio: float
    gap_candidate_mode_counts: dict[CandidateMode, int]


def _gap_candidate_counts(rows: list[BenchmarkGapRow]) -> GapCandidateCounts:
    candidates = [candidate for row in rows for candidate in row["candidate_benchmarks"]]
    entity_specific_candidates = [
        candidate
        for candidate in candidates
        if candidate["matched_missing_facets"] or candidate["matched_hint_facets"]
    ]
    fallback_candidates = [candidate for candidate in candidates if _is_fallback_candidate(candidate)]
    mode_counts: dict[CandidateMode, int] = {
        "entity-specific": 0,
        "fallback-only": 0,
        "none": 0,
    }
    for row in rows:
        mode_counts[row["candidate_mode"]] += 1
    candidate_total = len(candidates)
    return {
        "candidate_rows": candidate_total,
        "entity_specific_candidate_rows": len(entity_specific_candidates),
        "fallback_candidate_rows": len(fallback_candidates),
        "fallback_candidate_ratio": (len(fallback_candidates) / candidate_total) if candidate_total else 0.0,
        "gap_candidate_mode_counts": mode_counts,
    }
```

- [ ] **Step 5: Set `candidate_mode` while building gap rows**

In `gaps_report()`, compute candidates once before constructing the row:

```python
candidates = _candidate_rows(
    current_entity_id,
    analysis.contexts,
    current_matches,
    missing_facets,
    hint_facets,
    candidate_score_index,
)
rows.append(
    {
        "entity_id": current_entity_id,
        "entity_title": titles.get(current_entity_id, current_entity_id),
        "gap_level": gap_level,
        "missing_modalities": missing_modalities,
        "missing_signal_types": missing_signal_types,
        "current_matches": _current_match_rows(current_matches),
        "candidate_benchmarks": candidates,
        "candidate_mode": _candidate_mode(candidates),
        "suggested_search_facets": suggested_facets,
        "reason": reason,
    }
)
```

- [ ] **Step 6: Use shared counts in `_gap_summary()`**

Replace `_gap_summary()` with:

```python
def _gap_summary(rows: list[BenchmarkGapRow], entities_total: int) -> BenchmarkGapSummary:
    counts = _gap_candidate_counts(rows)
    return {
        "entities_total": entities_total,
        "entities_with_gaps": len(rows),
        "uncovered_entities": sum(1 for row in rows if row["gap_level"] == "uncovered"),
        "weakly_covered_entities": sum(1 for row in rows if row["gap_level"] == "weak"),
        "missing_facet_entities": sum(1 for row in rows if row["gap_level"] == "missing-facet"),
        **counts,
    }
```

- [ ] **Step 7: Use shared counts in `gap_calibration_summary()`**

In `gap_calibration_summary()`, replace the local `entity_specific_candidates` and `fallback_candidates` count derivation for scalar fields with `counts = _gap_candidate_counts(rows)`. Keep the local `fallback_candidates` list for benchmark/reason counters:

```python
rows = report["benchmark_gaps"]
candidates = [candidate for row in rows for candidate in row["candidate_benchmarks"]]
counts = _gap_candidate_counts(rows)
fallback_candidates = [candidate for candidate in candidates if _is_fallback_candidate(candidate)]
```

Then set:

```python
"candidate_rows": counts["candidate_rows"],
"entity_specific_candidate_rows": counts["entity_specific_candidate_rows"],
"fallback_candidate_rows": counts["fallback_candidate_rows"],
```

Do not add `fallback_candidate_ratio` to `GapCalibrationSummary` in this task; that summary already has richer fallback diagnostics and the batch aggregate already computes its ratio.

- [ ] **Step 8: Run focused tests**

```bash
rtk uv run --frozen --project science pytest science/tests/test_benchmark_opportunities.py::test_gaps_report_summary_includes_actionability_candidate_counts science/tests/test_benchmark_opportunities.py::test_gap_calibration_summary_projects_gap_report_metrics -q
```

Expected: PASS.

- [ ] **Step 9: Commit**

```bash
rtk git add science/src/science_tool/benchmark_opportunities.py science/tests/test_benchmark_opportunities.py
rtk git commit -m "feat(benchmark): expose gap candidate actionability counts"
```

## Task 2: Make `benchmark gaps` Table Candidate Mode Visible

**Files:**
- Modify: `science/src/science_tool/cli.py`
- Test: `science/tests/test_benchmark_cli.py`

- [ ] **Step 1: Add failing CLI table test**

Append this test near `test_benchmark_gaps_cli_evidence_report_table` in `science/tests/test_benchmark_cli.py`:

```python
def test_benchmark_gaps_cli_table_shows_candidate_mode_and_compacts_fallbacks(tmp_path: Path) -> None:
    _write_entity(
        tmp_path,
        "hypotheses",
        "0004-generic",
        """
id: hypothesis:0004-generic
type: hypothesis
title: Generic fallback benchmark gap
""",
        body="Homeostatic recovery remains under-tested.",
    )
    for slug in ("generic-a", "generic-b", "generic-c"):
        _write_dataset(
            tmp_path,
            slug,
            f"""
id: dataset:{slug}
type: dataset
title: {slug}
benchmark:
  domains: [biology]
  modalities: [assay]
  signal_types: [unrelated]
  benchmark_kinds: [static-association]
  tasks:
    - id: ready
      prediction_target: label
      held_out_unit: cohort
      metric: auroc
      baseline: majority-class
      ground_truth:
        type: measured-outcome
        description: label
""",
        )

    result = _invoke_gaps(tmp_path)

    assert result.exit_code == 0
    assert "fallback-only" in result.output
    assert "+2 fallback" in result.output
```

- [ ] **Step 2: Run the failing CLI test**

```bash
rtk uv run --frozen --project science pytest science/tests/test_benchmark_cli.py::test_benchmark_gaps_cli_table_shows_candidate_mode_and_compacts_fallbacks -q
```

Expected: FAIL because the table does not show `candidate_mode` or compact fallback counts.

- [ ] **Step 3: Add compact candidate formatter**

In `science/src/science_tool/cli.py`, add this helper near the benchmark command helpers:

```python
def _format_gap_candidates_for_table(row: Mapping[str, Any]) -> str:
    candidates = row["candidate_benchmarks"]
    if not candidates:
        return "-"
    if row.get("candidate_mode") == "fallback-only":
        first = candidates[0]["benchmark_id"]
        remainder = len(candidates) - 1
        return first if remainder <= 0 else f"{first} +{remainder} fallback"
    return ", ".join(candidate["benchmark_id"] for candidate in candidates[:3])
```

If `Mapping` or `Any` is not already imported in `cli.py`, add them to the existing `typing` import.

- [ ] **Step 4: Update the gap table columns**

In `benchmark_gaps()`, change:

```python
for col in ("entity", "level", "missing facets", "matches", "candidates", "reason"):
```

to:

```python
for col in ("entity", "level", "mode", "missing facets", "matches", "candidates", "reason"):
```

Change row rendering from:

```python
candidates = ", ".join(candidate["benchmark_id"] for candidate in row["candidate_benchmarks"][:3]) or "-"
table.add_row(
    row["entity_id"],
    row["gap_level"],
    missing,
    str(len(row["current_matches"])),
    candidates,
    row["reason"],
)
```

to:

```python
table.add_row(
    row["entity_id"],
    row["gap_level"],
    row["candidate_mode"],
    missing,
    str(len(row["current_matches"])),
    _format_gap_candidates_for_table(row),
    row["reason"],
)
```

- [ ] **Step 5: Run CLI test**

```bash
rtk uv run --frozen --project science pytest science/tests/test_benchmark_cli.py::test_benchmark_gaps_cli_table_shows_candidate_mode_and_compacts_fallbacks -q
```

Expected: PASS.

- [ ] **Step 6: Run focused benchmark CLI tests**

```bash
rtk uv run --frozen --project science pytest science/tests/test_benchmark_cli.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
rtk git add science/src/science_tool/cli.py science/tests/test_benchmark_cli.py
rtk git commit -m "feat(cli): show benchmark gap candidate modes"
```

## Task 3: Tune Benchmark Test Sorting And Summary

**Files:**
- Modify: `science/src/science_tool/benchmark_opportunities.py`
- Test: `science/tests/test_benchmark_opportunities.py`

- [ ] **Step 1: Add failing test for source/readiness ordering**

Append this test near the existing benchmark tests report sorting/filtering tests:

```python
def test_benchmark_tests_report_sorts_by_state_source_readiness_before_score(tmp_path: Path) -> None:
    from science_tool.benchmark_opportunities import benchmark_tests_report

    _write_entity(
        tmp_path,
        "hypotheses",
        "0042-spatial",
        """
id: hypothesis:0042-spatial
type: hypothesis
title: Spatial perturbation hypothesis
""",
        body="Spatial perturbation response should be benchmarked.",
    )
    _write_entity(
        tmp_path,
        "hypotheses",
        "0043-generic",
        """
id: hypothesis:0043-generic
type: hypothesis
title: Generic fallback benchmark gap
""",
        body="Homeostatic recovery remains under-tested.",
    )
    _write_dataset(
        tmp_path,
        "matched-metadata",
        """
id: dataset:matched-metadata
type: dataset
title: Matched Metadata
dataset_class: pointer
benchmark:
  domains: [biology]
  modalities: [spatial]
  signal_types: [perturbation]
  benchmark_kinds: [perturbation-response]
  tasks:
    - id: matched
      prediction_target: response
      held_out_unit: sample
      metric: auroc
      baseline: majority-class
      ground_truth:
        type: measured-outcome
        description: response
""",
    )
    _write_dataset(
        tmp_path,
        "matched-runnable",
        """
id: dataset:matched-runnable
type: dataset
title: Matched Runnable
dataset_class: deposit
local_path: data/matched-runnable
benchmark:
  domains: [biology]
  modalities: [spatial]
  signal_types: [perturbation]
  benchmark_kinds: [perturbation-response]
  tasks:
    - id: matched
      prediction_target: response
      held_out_unit: sample
      metric: auroc
      baseline: majority-class
      ground_truth:
        type: measured-outcome
        description: response
""",
    )
    _write_dataset(
        tmp_path,
        "fallback-high-score",
        """
id: dataset:fallback-high-score
type: dataset
title: Fallback High Score
dataset_class: deposit
local_path: data/fallback-high-score
benchmark:
  domains: [biology]
  modalities: [proteomics, multimodal]
  signal_types: [time-series]
  benchmark_kinds: [static-association]
  limitations: [well curated]
  tasks:
    - id: fallback
      prediction_target: response
      held_out_unit: sample
      metric: auroc
      baseline: majority-class
      ground_truth:
        type: measured-outcome
        description: response
""",
    )

    rows = benchmark_tests_report(tmp_path)["benchmark_tests"]

    ordered = [(row["benchmark_id"], row["priority_source"], row["readiness_label"]) for row in rows]
    assert ordered[:2] == [
        ("dataset:matched-runnable", "opportunity-relative", "runnable"),
        ("dataset:matched-metadata", "opportunity-relative", "metadata-only"),
    ]
    assert any(row["priority_source"] == "gap-fallback" for row in rows)
    assert all(row["priority_source"] != "gap-fallback" for row in rows[:2])
```

- [ ] **Step 2: Add failing test for source summary counts**

Append:

```python
def test_benchmark_tests_report_summary_counts_sources_and_fallback_ratio(tmp_path: Path) -> None:
    from science_tool.benchmark_opportunities import benchmark_tests_report

    _write_entity(
        tmp_path,
        "hypotheses",
        "0043-generic",
        """
id: hypothesis:0043-generic
type: hypothesis
title: Generic benchmark gap
""",
        body="Homeostatic recovery remains under-tested.",
    )
    _write_dataset(
        tmp_path,
        "generic",
        """
id: dataset:generic
type: dataset
title: Generic Benchmark
dataset_class: deposit
local_path: data/generic
benchmark:
  domains: [biology]
  modalities: [assay]
  signal_types: [unrelated]
  benchmark_kinds: [static-association]
  tasks:
    - id: ready
      prediction_target: label
      held_out_unit: cohort
      metric: auroc
      baseline: majority-class
      ground_truth:
        type: measured-outcome
        description: label
""",
    )

    summary = benchmark_tests_report(tmp_path)["summary"]

    assert summary["source_counts"] == {
        "opportunity-relative": 0,
        "gap-candidate": 0,
        "gap-fallback": 1,
    }
    assert summary["fallback_rows"] == 1
    assert summary["fallback_row_ratio"] == 1.0
```

- [ ] **Step 3: Run failing tests**

```bash
rtk uv run --frozen --project science pytest science/tests/test_benchmark_opportunities.py::test_benchmark_tests_report_sorts_by_state_source_readiness_before_score science/tests/test_benchmark_opportunities.py::test_benchmark_tests_report_summary_counts_sources_and_fallback_ratio -q
```

Expected: FAIL because summary keys and sort ordering are not implemented.

- [ ] **Step 4: Extend `BenchmarkTestSummary`**

In `BenchmarkTestSummary`, add:

```python
source_counts: dict[PrioritySource, int]
fallback_rows: int
fallback_row_ratio: float
```

If `PrioritySource` is defined after `BenchmarkTestSummary`, move `TestPlanState`, `PrioritySource`, and `ReadinessLabel` above `BenchmarkTestSummary`.

- [ ] **Step 5: Update benchmark test summary helper**

In `_benchmark_test_summary()`, add source counts:

```python
source_counts: dict[PrioritySource, int] = {
    "opportunity-relative": 0,
    "gap-candidate": 0,
    "gap-fallback": 0,
}
for row in rows:
    source_counts[row["priority_source"]] += 1
fallback_rows = source_counts["gap-fallback"]
```

Include these fields in the returned dict:

```python
"source_counts": source_counts,
"fallback_rows": fallback_rows,
"fallback_row_ratio": (fallback_rows / len(rows)) if rows else 0.0,
```

- [ ] **Step 6: Add sort key helpers**

Replace `_benchmark_test_sort_key()` with:

```python
def _benchmark_test_source_sort_key(source: PrioritySource) -> int:
    order = {
        "opportunity-relative": 0,
        "gap-candidate": 1,
        "gap-fallback": 2,
    }
    return order[source]


def _benchmark_test_readiness_sort_key(readiness: ReadinessLabel) -> int:
    order = {
        "runnable": 0,
        "stage-needed": 1,
        "metadata-only": 2,
        "blocked": 3,
    }
    return order[readiness]


def _benchmark_test_sort_key(row: BenchmarkTestRow) -> tuple[int, int, int, int, str, str, str]:
    return (
        _benchmark_test_state_sort_key(row["test_plan_state"]),
        _benchmark_test_source_sort_key(row["priority_source"]),
        _benchmark_test_readiness_sort_key(row["readiness_label"]),
        -row["priority_score"],
        row["entity_id"],
        row["benchmark_id"],
        "" if row["task_id"] is None else row["task_id"],
    )
```

- [ ] **Step 7: Run focused tests**

```bash
rtk uv run --frozen --project science pytest science/tests/test_benchmark_opportunities.py::test_benchmark_tests_report_sorts_by_state_source_readiness_before_score science/tests/test_benchmark_opportunities.py::test_benchmark_tests_report_summary_counts_sources_and_fallback_ratio -q
```

Expected: PASS.

- [ ] **Step 8: Run existing filter tests**

```bash
rtk uv run --frozen --project science pytest science/tests/test_benchmark_opportunities.py -k "benchmark_tests_report" -q
```

Expected: PASS. If an existing assertion depends on old score-first ordering, update it only when the new state/source/readiness order explains the change.

- [ ] **Step 9: Commit**

```bash
rtk git add science/src/science_tool/benchmark_opportunities.py science/tests/test_benchmark_opportunities.py
rtk git commit -m "feat(benchmark): sort test plans by actionability"
```

## Task 4: Categorize Evidence Terms Without Changing `lexicon_candidates`

**Files:**
- Modify: `science/src/science_tool/benchmark_opportunities.py`
- Test: `science/tests/test_benchmark_opportunities.py`

- [ ] **Step 1: Add failing evidence categorization test**

Append near evidence report tests:

```python
def test_gaps_report_evidence_report_categorizes_unmapped_terms_without_redefining_lexicon_candidates(tmp_path: Path) -> None:
    from science_tool.benchmark_opportunities import gaps_report

    project_root = tmp_path / "cbioportal-project"
    project_root.mkdir()
    _write_entity(
        project_root,
        "hypotheses",
        "0044-cytogenetic-model",
        """
id: hypothesis:0044-cytogenetic-model
type: hypothesis
title: cBioPortal cytogenetic lesion model
""",
        body="Cytogenetic lesion mutation evidence should be benchmarked against project catalog models.",
    )
    _write_dataset(
        project_root,
        "generic",
        """
id: dataset:generic
type: dataset
title: Generic Benchmark
benchmark:
  domains: [biology]
  modalities: [assay]
  signal_types: [unrelated]
  benchmark_kinds: [static-association]
  tasks:
    - id: ready
      prediction_target: label
      held_out_unit: cohort
      metric: auroc
      baseline: majority-class
      ground_truth:
        type: measured-outcome
        description: label
""",
    )

    evidence = gaps_report(project_root, evidence_report=True)["evidence_report"]

    categories = evidence["term_categories"]
    domain_terms = {row["term"] for row in categories["domain_candidate_terms"]}
    project_terms = {row["term"] for row in categories["project_local_terms"]}
    workflow_terms = {row["term"] for row in categories["workflow_or_modeling_terms"]}
    assert {"cytogenetic", "lesion", "mutation"} <= domain_terms
    assert "cbioportal" in project_terms
    assert {"catalog", "models"} <= workflow_terms
    assert evidence["summary"]["top_domain_candidate_terms"][0]["term"] in domain_terms
    assert evidence["lexicon_candidates"] == evidence["summary"]["top_unmapped_project_terms"]


def test_evidence_workflow_terms_are_not_already_excluded_upstream() -> None:
    from science_tool.benchmark_opportunities import (
        FACET_HINT_TERMS,
        _UNMAPPED_TERM_EXCLUSIONS,
        _WORKFLOW_OR_MODELING_TERMS,
    )

    assert _WORKFLOW_OR_MODELING_TERMS
    assert not (_WORKFLOW_OR_MODELING_TERMS & _UNMAPPED_TERM_EXCLUSIONS)
    assert not (_WORKFLOW_OR_MODELING_TERMS & set(FACET_HINT_TERMS))


def test_term_categories_are_disjoint_and_project_local_uses_leaf_not_ancestors(tmp_path: Path) -> None:
    from science_tool.benchmark_opportunities import _project_local_tokens, _term_categories

    project_root = tmp_path / "cancer" / "cancer-types" / "multiple-myeloma"
    project_root.mkdir(parents=True)
    categories = _term_categories(
        {
            "hypothesis:0001-project": [
                "cancer",
                "multiple",
                "myeloma",
                "project",
                "mutation",
            ]
        },
        project_local_tokens=_project_local_tokens(project_root, []),
    )

    project_terms = {row["term"] for row in categories["project_local_terms"]}
    workflow_terms = {row["term"] for row in categories["workflow_or_modeling_terms"]}
    domain_terms = {row["term"] for row in categories["domain_candidate_terms"]}
    assert {"multiple", "myeloma"} <= project_terms
    assert "project" in workflow_terms
    assert {"cancer", "mutation"} <= domain_terms
    assert not (project_terms & workflow_terms)
    assert not (project_terms & domain_terms)
    assert not (workflow_terms & domain_terms)
```

- [ ] **Step 2: Run the failing test**

```bash
rtk uv run --frozen --project science pytest \
  science/tests/test_benchmark_opportunities.py::test_gaps_report_evidence_report_categorizes_unmapped_terms_without_redefining_lexicon_candidates \
  science/tests/test_benchmark_opportunities.py::test_evidence_workflow_terms_are_not_already_excluded_upstream \
  science/tests/test_benchmark_opportunities.py::test_term_categories_are_disjoint_and_project_local_uses_leaf_not_ancestors \
  -q
```

Expected: FAIL because `term_categories`, `top_domain_candidate_terms`, `_WORKFLOW_OR_MODELING_TERMS`, `_project_local_tokens`, and `_term_categories` do not exist.

- [ ] **Step 3: Extend evidence typed dicts**

Add:

```python
TermCategory = Literal["domain_candidate_terms", "project_local_terms", "workflow_or_modeling_terms", "other_terms"]


class EvidenceTermCategories(TypedDict):
    domain_candidate_terms: list[TermCountRow]
    project_local_terms: list[TermCountRow]
    workflow_or_modeling_terms: list[TermCountRow]
    other_terms: list[TermCountRow]
```

Update `EvidenceSummary`:

```python
class EvidenceSummary(TypedDict):
    entities_total: int
    entities_with_no_facet_hints: int
    entities_with_fallback_only_candidates: int
    top_unmapped_project_terms: list[TermCountRow]
    top_domain_candidate_terms: list[TermCountRow]
```

Update `EvidenceReport`:

```python
class EvidenceReport(TypedDict):
    enabled: bool
    summary: NotRequired[EvidenceSummary]
    entities: NotRequired[dict[str, EvidenceEntityRow]]
    lexicon_candidates: NotRequired[list[TermCountRow]]
    term_categories: NotRequired[EvidenceTermCategories]
```

- [ ] **Step 4: Add structural term helpers**

Add near `_unmapped_high_value_terms()`:

```python
_WORKFLOW_OR_MODELING_TERMS = frozenset(
    {
        "catalog",
        "model",
        "models",
        "project",
    }
)


def _tokens_from_label(value: str) -> set[str]:
    return {
        token
        for token in re.split(r"[^A-Za-z0-9]+", value.lower())
        if token and len(token) > 1
    }


def _project_local_tokens(project_root: Path, entities: list[ProjectBenchmarkEntity]) -> set[str]:
    tokens: set[str] = set()
    tokens.update(_tokens_from_label(project_root.resolve().name))
    for entity in entities:
        tokens.update(entity.id_tokens)
    return tokens
```

Keep `_WORKFLOW_OR_MODELING_TERMS` deliberately short. The test added in Step 1 verifies the initial list is not already excluded by `_UNMAPPED_TERM_EXCLUSIONS` or `FACET_HINT_TERMS`.

- [ ] **Step 5: Add categorization helper**

```python
def _term_rows_for_terms(by_entity: dict[str, list[str]], terms: set[str], *, top: int = 10) -> list[TermCountRow]:
    filtered = {
        entity_id: [term for term in entity_terms if term in terms]
        for entity_id, entity_terms in by_entity.items()
    }
    return _top_unmapped_terms(filtered, top=top)


def _term_categories(
    by_entity: dict[str, list[str]],
    *,
    project_local_tokens: set[str],
    top: int = 10,
) -> EvidenceTermCategories:
    all_terms = {term for terms in by_entity.values() for term in terms}
    project_terms = all_terms & project_local_tokens
    workflow_terms = (all_terms & _WORKFLOW_OR_MODELING_TERMS) - project_terms
    domain_terms = all_terms - project_terms - workflow_terms
    return {
        "domain_candidate_terms": _term_rows_for_terms(by_entity, domain_terms, top=top),
        "project_local_terms": _term_rows_for_terms(by_entity, project_terms, top=top),
        "workflow_or_modeling_terms": _term_rows_for_terms(by_entity, workflow_terms, top=top),
        "other_terms": [],
    }
```

Project-local terms take precedence over workflow/modeling terms if a token ever appears in both sets. This keeps the emitted categories disjoint.

- [ ] **Step 6: Thread `project_root` into evidence report**

Change `_gap_evidence_report()` signature:

```python
def _gap_evidence_report(
    rows: list[BenchmarkGapRow],
    *,
    project_root: Path,
    entities: list[ProjectBenchmarkEntity],
    matched: dict[str, list[OpportunityRow]],
    enabled: bool,
) -> EvidenceReport:
```

In `gaps_report()`, update the call:

```python
"evidence_report": _gap_evidence_report(
    rows,
    project_root=project_root,
    entities=analysis.entities,
    matched=matched,
    enabled=evidence_report,
),
```

- [ ] **Step 7: Reuse row-level candidate mode and return categories**

Inside `_gap_evidence_report()`, replace:

```python
mode = _candidate_mode(row["candidate_benchmarks"])
```

with:

```python
mode = row["candidate_mode"]
```

After `top_terms = _top_unmapped_terms(unmapped_by_entity)`, add:

```python
categories = _term_categories(
    unmapped_by_entity,
    project_local_tokens=_project_local_tokens(project_root, entities),
)
```

Return:

```python
return {
    "enabled": True,
    "summary": {
        "entities_total": len(rows),
        "entities_with_no_facet_hints": no_hints,
        "entities_with_fallback_only_candidates": fallback_only,
        "top_unmapped_project_terms": top_terms,
        "top_domain_candidate_terms": categories["domain_candidate_terms"],
    },
    "entities": evidence_entities,
    "lexicon_candidates": top_terms,
    "term_categories": categories,
}
```

- [ ] **Step 8: Run evidence tests**

```bash
rtk uv run --frozen --project science pytest science/tests/test_benchmark_opportunities.py -k "evidence_report" -q
```

Expected: PASS.

- [ ] **Step 9: Commit**

```bash
rtk git add science/src/science_tool/benchmark_opportunities.py science/tests/test_benchmark_opportunities.py
rtk git commit -m "feat(benchmark): categorize gap evidence terms"
```

## Task 5: Final Verification And Calibration Rerun

**Files:**
- Modify: `docs/audits/benchmark-actionability-calibration-2026-06-30.md` only if measured outcomes need a dated follow-up note. Prefer a new short audit if results materially change.

- [ ] **Step 1: Run focused benchmark tests**

```bash
rtk uv run --frozen --project science pytest science/tests/test_benchmark_opportunities.py science/tests/test_benchmark_cli.py -q
```

Expected: PASS.

- [ ] **Step 2: Run diff check**

```bash
rtk git diff --check
```

Expected: no output.

- [ ] **Step 3: Rerun four-project calibration summary**

```bash
SCIENCE_COMMONS_ROOT=~/d/science-commons rtk uv run --frozen --project science science benchmark gap-calibration \
  --project post-acute-infection=~/d/health/processes/post-acute-infection \
  --project multiple-myeloma=~/d/cancer/cancer-types/multiple-myeloma \
  --project natural-systems=~/d/natural-systems \
  --project cbioportal=~/d/cancer/data-sources/cbioportal \
  --commons \
  --domain biology \
  --format json > /tmp/benchmark-actionability-tuning-gap-calibration.json
```

Expected: command exits 0. The fallback candidate ratio may remain high; the important check is that fallback volume is now visible in default summaries and table modes are clearer.

- [ ] **Step 4: Rerun evidence report on multiple myeloma**

```bash
SCIENCE_COMMONS_ROOT=~/d/science-commons rtk uv run --frozen --project science science benchmark gaps \
  --project-root ~/d/cancer/cancer-types/multiple-myeloma \
  --commons \
  --domain biology \
  --evidence-report \
  --format json > /tmp/benchmark-actionability-tuning-mm-gaps.json
```

Expected: command exits 0. Inspect `/tmp/benchmark-actionability-tuning-mm-gaps.json` and confirm `evidence_report.term_categories.domain_candidate_terms` exists and `evidence_report.lexicon_candidates` still equals `evidence_report.summary.top_unmapped_project_terms`.

- [ ] **Step 5: Inspect table output**

```bash
SCIENCE_COMMONS_ROOT=~/d/science-commons rtk uv run --frozen --project science science benchmark gaps \
  --project-root ~/d/cancer/cancer-types/multiple-myeloma \
  --commons \
  --domain biology | head -80
```

Expected: output includes candidate mode and compact fallback-only candidate cells.

- [ ] **Step 6: Final status**

```bash
rtk git status --short
```

Expected: only intended files modified.

- [ ] **Step 7: Commit any calibration audit follow-up if added**

If a follow-up audit was added:

```bash
rtk git add docs/audits/<new-file>.md
rtk git commit -m "docs(benchmark): record actionability tuning calibration"
```

If no audit was added, skip this step.

## Self-Review Checklist

- Spec coverage:
  - Gap row `candidate_mode`: Task 1.
  - Shared counts helper: Task 1.
  - Gap table mode and fallback compaction: Task 2.
  - Benchmark test state/source/readiness sorting: Task 3.
  - Benchmark test source/fallback summary: Task 3.
  - Evidence term categories and compatible `lexicon_candidates`: Task 4.
  - Four-project calibration rerun: Task 5.
- Placeholder review: no red-flag placeholder steps remain.
- Type consistency:
  - `CandidateMode`, `PrioritySource`, and `ReadinessLabel` names match existing code.
  - `candidate_mode` is a `BenchmarkGapRow` field and is reused by evidence.
  - `term_categories` and `top_domain_candidate_terms` are additive evidence fields.

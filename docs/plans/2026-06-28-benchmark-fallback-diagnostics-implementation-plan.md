# Benchmark Fallback Diagnostics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add read-only fallback reason and concentration diagnostics to benchmark gap calibration summaries.

**Architecture:** Keep matching, scoring, and ranking unchanged. Replace the generic fallback marker with fallback-specific `reason_notes`, then summarize those notes and fallback benchmark shares in existing single-project and batch calibration projections.

**Tech Stack:** Python 3.13, Click, Rich tables, pytest, ruff.

---

## Files

- Modify `science/src/science_tool/benchmark_opportunities.py`
  - Add fallback reason and share typed rows.
  - Add fallback note helpers.
  - Extend `gap_calibration_summary()` and `benchmark_gap_calibration_batch()`.
- Modify `science/src/science_tool/cli.py`
  - Render fallback diagnostics in table output for `benchmark gaps --calibration-summary`.
  - Render fallback diagnostics in table output for `benchmark gap-calibration`.
- Modify `science/tests/test_benchmark_opportunities.py`
  - Add direct tests for fallback note classification, summary diagnostics, and batch aggregate diagnostics.
- Modify `science/tests/test_benchmark_cli.py`
  - Add CLI JSON/table assertions for batch diagnostics.
- Modify `docs/plans/2026-06-28-benchmark-fallback-diagnostics-design.md`
  - Keep the design contract aligned with implementation if review uncovers needed wording changes.

## Task 1: Fallback Reason Notes

- [ ] Add a failing test in `science/tests/test_benchmark_opportunities.py` that builds a generic fallback candidate and asserts `reason_notes` contains `fallback:task-ready` and not `high-baseline-fallback`.
- [ ] Run the focused test and verify it fails on the old marker.
- [ ] Add `_fallback_reason_notes(score: CandidateScore) -> list[str]`.
- [ ] Update `_candidate_rows()` so fallback rows use `_fallback_reason_notes(score)`.
- [ ] Update fallback detection helpers to use `any(note.startswith("fallback:") ...)`.
- [ ] Re-run the focused test and verify it passes.
- [ ] Commit the task.

## Task 2: Single-Project Summary Diagnostics

- [ ] Add a failing direct test that calls `gap_calibration_summary()` and asserts:
  - `top_fallback_reasons`
  - `top_fallback_benchmark_shares`
  - `fallback_concentration_warning`
- [ ] Run the focused test and verify it fails because fields are absent.
- [ ] Add typed rows:
  - `ReasonCountRow`
  - `BenchmarkShareRow`
- [ ] Extend `GapCalibrationSummary`.
- [ ] Implement top fallback reason counts and benchmark shares from fallback rows.
- [ ] Re-run the focused test and verify it passes.
- [ ] Commit the task.

## Task 3: Batch Aggregate Diagnostics

- [ ] Add a failing batch helper test that builds two projects with repeated fallback benchmarks and asserts aggregate fallback reason counts and benchmark shares.
- [ ] Run the focused test and verify it fails because aggregate fields are absent.
- [ ] Extend `GapCalibrationAggregate`.
- [ ] Compute aggregate fallback reason counts and benchmark shares from all gap rows, not truncated per-project top lists.
- [ ] Re-run the focused test and verify it passes.
- [ ] Commit the task.

## Task 4: CLI Rendering

- [ ] Add CLI JSON/table assertions for `science benchmark gap-calibration`.
- [ ] Add table assertions for `science benchmark gaps --calibration-summary`.
- [ ] Run focused tests and verify table assertions fail before rendering changes.
- [ ] Add table rows for:
  - `top_fallback_reasons`
  - `top_fallback_benchmark_shares`
  - `fallback_concentration_warning`
- [ ] Re-run focused tests and verify they pass.
- [ ] Commit the task.

## Task 5: Verification and Real-Project Smoke

- [ ] Run:

```bash
rtk uv run --frozen --project science ruff check science/src/science_tool/benchmark_opportunities.py science/src/science_tool/cli.py science/tests/test_benchmark_opportunities.py science/tests/test_benchmark_cli.py
rtk uv run --frozen --project science pytest science/tests/test_benchmark_opportunities.py science/tests/test_benchmark_cli.py -q
```

- [ ] Run:

```bash
SCIENCE_COMMONS_ROOT=~/d/science-commons rtk uv run --frozen --project science science benchmark gap-calibration \
  --project pai=~/d/health/processes/post-acute-infection \
  --project mm=~/d/cancer/cancer-types/multiple-myeloma \
  --project natural=~/d/natural-systems \
  --project cbioportal=~/d/cancer/data-sources/cbioportal \
  --commons \
  --format json
```

- [ ] Confirm the aggregate JSON includes fallback reason counts, fallback benchmark shares, and a concentration warning value.
- [ ] Commit any final doc correction if needed.


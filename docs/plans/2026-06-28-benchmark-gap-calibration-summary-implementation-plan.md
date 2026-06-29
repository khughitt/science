# Benchmark Gap Calibration Summary Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a read-only calibration summary for `science benchmark gaps` so benchmark-gap quality can be inspected without ad hoc JSON scripts.

**Architecture:** Keep `gaps_report()` as the single source of truth. Add a pure projection helper in `benchmark_opportunities.py` that summarizes an existing `BenchmarkGapReport`, then have the CLI include/render that projection when `--calibration-summary` is requested.

**Tech Stack:** Python 3.13, Click, Rich tables, pytest, ruff.

---

## Files

- Modify `science/src/science_tool/benchmark_opportunities.py`
  - Add `GapCalibrationSummary` typed payload.
  - Add `gap_calibration_summary(report, top=10)`.
- Modify `science/src/science_tool/cli.py`
  - Add `--calibration-summary` to `science benchmark gaps`.
  - Include top-level `calibration_summary` in JSON only when requested.
  - Render a compact table section in table output only when requested.
- Modify `science/tests/test_benchmark_opportunities.py`
  - Add direct helper tests for counts, score stats, top facets, and fallback rankings.
- Modify `science/tests/test_benchmark_cli.py`
  - Add CLI JSON and table coverage.

## Task 1: Summary Helper

- [ ] Write a failing direct test in `science/tests/test_benchmark_opportunities.py` that builds a gap report with one hint-backed candidate and one fallback-only row, then asserts:
  - `gap_rows`
  - `rows_with_suggested_facets`
  - `candidate_rows`
  - `entity_specific_candidate_rows`
  - `fallback_candidate_rows`
  - score min/median/max
  - top suggested facets
  - top matched hint facets
  - top fallback benchmarks
- [ ] Run the focused test and verify it fails because `gap_calibration_summary` does not exist.
- [ ] Implement `GapCalibrationSummary` and `gap_calibration_summary(report, top=10)` as a pure projection over `report["benchmark_gaps"]`.
- [ ] Re-run the focused test and verify it passes.

## Task 2: CLI JSON Contract

- [ ] Write a failing CLI JSON test in `science/tests/test_benchmark_cli.py` for `science benchmark gaps --calibration-summary --format json`.
- [ ] Assert the payload includes `calibration_summary` and does not require `calibration_report` to be enabled.
- [ ] Run the focused test and verify it fails because the option is unknown or the field is absent.
- [ ] Add the CLI option and JSON projection.
- [ ] Re-run the focused test and verify it passes.

## Task 3: CLI Table Contract

- [ ] Write a failing CLI table test in `science/tests/test_benchmark_cli.py` for `science benchmark gaps --calibration-summary`.
- [ ] Assert output includes `Benchmark Gaps` and `Gap Calibration Summary`.
- [ ] Implement the Rich summary table with scalar counts, score range, and compact top-list rows.
- [ ] Re-run the focused test and verify it passes.

## Task 4: Verification

- [ ] Run `rtk uv run --frozen --project science ruff check science/src/science_tool/benchmark_opportunities.py science/src/science_tool/cli.py science/tests/test_benchmark_opportunities.py science/tests/test_benchmark_cli.py`.
- [ ] Run `rtk uv run --frozen --project science pytest science/tests/test_benchmark_opportunities.py science/tests/test_benchmark_cli.py -q`.
- [ ] Commit only the plan, helper, CLI, and tests.

# Benchmark Fallback Selection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Diversify equal-quality benchmark fallback candidates across gap rows and expose fallback selection diagnostics.

**Architecture:** Keep `candidate_score` and entity-specific ranking unchanged. Replace the fallback-only sort with quality-tier rotation keyed by entity id, then summarize `selected:*` reason notes separately from `fallback:*` reason notes.

**Tech Stack:** Python 3.13, Click, Rich tables, pytest, ruff.

---

## Files

- Modify `science/src/science_tool/benchmark_opportunities.py`
  - Add stable rotation helpers.
  - Add fallback selection notes.
  - Add `top_fallback_selection_reasons` to summary and aggregate payloads.
- Modify `science/src/science_tool/cli.py`
  - Render `top_fallback_selection_reasons` in both calibration table surfaces.
- Modify `science/tests/test_benchmark_opportunities.py`
  - Add fallback diversity, quality-tier, summary, and aggregate tests.
- Modify `science/tests/test_benchmark_cli.py`
  - Add batch table assertion for the new diagnostic.

## Task 1: Equal-Quality Fallback Rotation

- [ ] Add a failing test with several generic entities and five equal-quality fallback datasets. Assert at least two entities receive different fallback triples.
- [ ] Run the focused test and verify it fails because the same top three fallback benchmarks are selected for every entity.
- [ ] Implement stable entity-id rotation within equal `(candidate_score, baseline_score)` tiers.
- [ ] Add `selected:*` notes to selected fallback rows.
- [ ] Re-run the focused test and verify it passes.
- [ ] Commit the task.

## Task 2: Preserve Quality Tier Ordering

- [ ] Add a failing test with one higher-quality fallback candidate and several lower-quality fallback candidates. Assert the higher-quality candidate is always selected first.
- [ ] Run the focused test and verify it fails if the rotation can demote the higher-quality tier.
- [ ] Adjust fallback selection so rotation happens only inside equal-quality tiers.
- [ ] Re-run the focused test and verify it passes.
- [ ] Commit the task.

## Task 3: Summary Selection Diagnostics

- [ ] Add failing direct summary assertions for `top_fallback_selection_reasons`.
- [ ] Run the focused test and verify the field is absent.
- [ ] Extend `GapCalibrationSummary` and `GapCalibrationAggregate`.
- [ ] Count `fallback:*` and `selected:*` notes separately.
- [ ] Re-run focused tests and verify they pass.
- [ ] Commit the task.

## Task 4: CLI Rendering

- [ ] Add failing table assertions for `top_fallback_selection_reasons`.
- [ ] Run focused CLI tests and verify they fail because table output omits the field.
- [ ] Render the field in `benchmark gaps --calibration-summary` and `benchmark gap-calibration`.
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

- [ ] Confirm the aggregate JSON includes `top_fallback_selection_reasons` and that fallback benchmark shares are less concentrated when equal-quality alternatives exist.


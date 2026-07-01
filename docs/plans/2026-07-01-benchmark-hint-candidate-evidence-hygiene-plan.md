# Benchmark Hint Candidate Evidence Hygiene Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Route obvious report/prose terms in `science benchmark hint-candidates` to the existing non-domain bucket so they stay visible without looking like benchmark facet candidates.

**Architecture:** Keep `gaps_report(..., evidence_report=True)` as the source of truth. Extend the existing `_WORKFLOW_OR_MODELING_TERMS` classification set and add a focused report-level regression test. Do not change the JSON schema, suppression sets, or facet hint lexicon.

**Tech Stack:** Python, pytest, ruff, existing `science_tool.benchmark_opportunities`.

---

## Files

- Modify: `science/src/science_tool/benchmark_opportunities.py`
  - Add report/prose terms to `_WORKFLOW_OR_MODELING_TERMS`.
- Modify: `science/tests/test_benchmark_opportunities.py`
  - Add a focused report-level regression test.

---

### Task 1: Report/Prose Term Classification

**Files:**
- Modify: `science/src/science_tool/benchmark_opportunities.py`
- Test: `science/tests/test_benchmark_opportunities.py`

- [ ] **Step 1: Add a failing report-level test**

Append this test near the existing hint-candidate report classification tests in `science/tests/test_benchmark_opportunities.py`:

```python
def test_hint_candidates_report_routes_report_prose_terms_to_workflow_category(tmp_path: Path) -> None:
    from science_tool.benchmark_opportunities import benchmark_hint_candidates_report

    _write_entity(
        tmp_path,
        "hypotheses",
        "0080-report-prose",
        """
id: hypothesis:0080-report-prose
type: hypothesis
title: Report prose
""",
        body=(
            "Related details banner demonstrates promoted evidence. "
            "Any current model over baseline should be reviewed."
        ),
    )

    payload = benchmark_hint_candidates_report(tmp_path)
    by_term = {row["term"]: row for row in payload["hint_candidates"]}
    expected_terms = {
        "any",
        "banner",
        "current",
        "demonstrates",
        "details",
        "over",
        "promoted",
        "related",
    }

    assert expected_terms <= set(by_term)
    for term in expected_terms:
        assert by_term[term]["category"] == "workflow-or-modeling"

    domain_terms = {row["term"] for row in payload["hint_candidates"] if row["category"] == "domain-candidate"}
    assert not (expected_terms & domain_terms)
```

- [ ] **Step 2: Run the failing test**

```bash
rtk uv run --frozen --project science pytest \
  science/tests/test_benchmark_opportunities.py::test_hint_candidates_report_routes_report_prose_terms_to_workflow_category \
  -q
```

Expected: FAIL because these terms are currently categorized as `domain-candidate`.

- [ ] **Step 3: Extend `_WORKFLOW_OR_MODELING_TERMS`**

In `science/src/science_tool/benchmark_opportunities.py`, update `_WORKFLOW_OR_MODELING_TERMS` so it includes these terms in sorted order with the existing set:

```python
_WORKFLOW_OR_MODELING_TERMS = frozenset(
    {
        "all",
        "any",
        "banner",
        "beyond",
        "catalog",
        "conjecture",
        "current",
        "demonstrates",
        "details",
        "model",
        "models",
        "organizing",
        "our",
        "over",
        "project",
        "promoted",
        "related",
        "shared",
    }
)
```

Do not add these terms to `_UNMAPPED_TERM_EXCLUSIONS`; they should remain visible in the report.

- [ ] **Step 4: Run focused tests**

```bash
rtk uv run --frozen --project science pytest \
  science/tests/test_benchmark_opportunities.py::test_hint_candidates_report_routes_report_prose_terms_to_workflow_category \
  science/tests/test_benchmark_opportunities.py::test_hint_candidates_report_routes_generic_terms_to_workflow_category \
  science/tests/test_benchmark_opportunities.py::test_evidence_workflow_terms_are_not_already_excluded_upstream \
  -q
```

Expected: PASS.

- [ ] **Step 5: Run all hint-candidate opportunity tests**

```bash
rtk uv run --frozen --project science pytest science/tests/test_benchmark_opportunities.py -k hint_candidates -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
rtk git add science/src/science_tool/benchmark_opportunities.py science/tests/test_benchmark_opportunities.py
rtk git commit -m "fix(benchmark): classify hint report prose terms"
```

---

### Task 2: Verification and Smoke

**Files:**
- No additional code changes expected.

- [ ] **Step 1: Run focused verification**

```bash
rtk uv run --frozen --project science pytest science/tests/test_benchmark_opportunities.py science/tests/test_benchmark_cli.py -q
rtk uv run --frozen --project science ruff check science/src/science_tool/benchmark_opportunities.py science/tests/test_benchmark_opportunities.py
```

Expected: PASS and `All checks passed!`.

- [ ] **Step 2: Run read-only active-project smoke commands**

```bash
rtk uv run --frozen --project science science benchmark hint-candidates --commons --domain biology --project-root ~/d/cancer/cancer-types/multiple-myeloma --format json > /tmp/hint-mm-hygiene.json
rtk uv run --frozen --project science science benchmark hint-candidates --commons --domain biology --project-root ~/d/health/processes/post-acute-infection --format json > /tmp/hint-pais-hygiene.json
rtk uv run --frozen --project science science benchmark hint-candidates --commons --domain biology --project-root ~/d/natural-systems --format json > /tmp/hint-natural-hygiene.json
rtk uv run --frozen --project science science benchmark hint-candidates --commons --domain biology --project-root ~/d/cancer/data-sources/cbioportal --format json > /tmp/hint-cbio-hygiene.json
```

Expected:
- commands exit 0;
- each JSON payload has `review_file: null`;
- `related`, `details`, `banner`, `demonstrates`, `promoted`, `any`, `over`, and `current` are not `domain-candidate` rows when present.

- [ ] **Step 3: Final status check**

```bash
rtk git status --short
```

Expected: clean after commits.

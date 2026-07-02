# MMRF Task Variants Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the existing MMRF CoMMpass recipe report task-specific support and cohort aggregation state without promoting the dataset or changing benchmark command semantics.

**No tool-visible change this slice.** The only artifacts that change are the recipe's `reports/validation.json` and its schema/README. Because `entity.md` is deliberately untouched, `science benchmark tests` continues to show only `progression-risk`; the `overall-survival` candidate is visible **only** inside the recipe's validation report until a later promotion slice edits `entity.md`. Do not expect any change in the benchmark CLI surface from this work.

**Architecture:** Keep endpoint discovery dataset-level and derive per-task support as a diagnostic projection in `reports/validation.json`. Reuse the existing recipe surfaces in `~/d/science-commons/datasets/mmrf-commpass/recipe`; do not create a second recipe, fallback task, or benchmark command path.

**Cohort-mode scope.** The design defines three cohort modes, but this slice only *classifies*, it does not *select*. Manifest uniqueness is still binary, so exactly two states are emitted: `unique-manifest-no-policy-applied` (no duplicates, but no curated patient-level selection rule has been applied) and `unresolved-cohort` (duplicates present). The design's `patient-level-single-sample` and `sample-level-with-patient-outcomes` modes require an actual selection/evaluation policy and are **deferred** — they are documented in the schema as future modes but are not emitted or tested here. Do not label a coincidentally-unique manifest `patient-level-single-sample`; that would claim a selection rule the recipe never applied.

**Tech Stack:** Python 3, pytest, pandas/parquet, GDC JSON fixtures, commons dataset entity frontmatter.

---

## File Structure

This plan is stored in the `science` repo, but implementation edits are in the existing commons recipe.

- Modify: `~/d/science-commons/datasets/mmrf-commpass/recipe/test_mmrf_recipe.py`
  - Add tests for task support, sample field probes, and cohort aggregation diagnostics.
- Modify: `~/d/science-commons/datasets/mmrf-commpass/recipe/fetch_manifest.py`
  - Add task-support derivation, sample-selection field probes, and cohort aggregation diagnostics to `write_dry_run`.
- Modify: `~/d/science-commons/datasets/mmrf-commpass/recipe/manifest.schema.yaml`
  - Document the new validation report fields and keep promotion state as `pointer`.
- Modify: `~/d/science-commons/datasets/mmrf-commpass/recipe/README.md`
  - Explain the task-aware dry-run output and the unresolved-cohort blocker.
- Do not modify: `~/d/science-commons/datasets/mmrf-commpass/entity.md`
  - `dataset_class: pointer` and the single `progression-risk` task remain unchanged in this slice.

## Task 1: Task-Support Diagnostics

**Files:**
- Modify: `~/d/science-commons/datasets/mmrf-commpass/recipe/test_mmrf_recipe.py`
- Modify: `~/d/science-commons/datasets/mmrf-commpass/recipe/fetch_manifest.py`

- [ ] **Step 1: Write failing tests for task-support derivation**

Add this unit test after `test_endpoint_discovery_accepts_progression_and_rejects_survival_only` in `test_mmrf_recipe.py`:

```python
def test_task_support_derives_progression_and_survival_states():
    from fetch_manifest import derive_task_support, discover_endpoint_fields

    progression = discover_endpoint_fields(_load_json("cases_progression.json")["data"]["hits"])
    progression_support = derive_task_support(progression)
    assert progression_support == {
        "progression-risk": {
            "state": "buildable-candidate",
            "reason": "Open GDC metadata has usable progression or recurrence endpoints for manifest cases.",
            "required_fields_present": ["days_to_recurrence", "progression_or_recurrence"],
            "required_fields_missing": [],
        },
        "overall-survival": {
            "state": "blocked-missing-endpoint",
            "reason": "Open GDC metadata lacks overall-survival endpoint fields.",
            "required_fields_present": [],
            "required_fields_missing": ["vital_status", "days_to_death"],
        },
    }

    survival_only = discover_endpoint_fields(_load_json("cases_survival_only.json")["data"]["hits"])
    survival_support = derive_task_support(survival_only)
    assert survival_support["progression-risk"] == {
        "state": "blocked-missing-endpoint",
        "reason": "Open GDC metadata lacks usable progression or recurrence endpoints.",
        "required_fields_present": [],
        "required_fields_missing": ["days_to_recurrence", "progression_or_recurrence"],
    }
    assert survival_support["overall-survival"] == {
        "state": "buildable-candidate",
        "reason": "Open GDC metadata has overall-survival endpoint fields.",
        "required_fields_present": ["vital_status", "days_to_death"],
        "required_fields_missing": [],
    }
```

Then extend the **existing** `test_write_dry_run_refuses_survival_only_for_progression_task` (do not add a second near-duplicate test) so it also asserts the task-aware validation fields. Add the following block immediately after its existing `with pytest.raises(...): write_dry_run(...)` block:

```python
    validation = json.loads((tmp_path / "reports" / "validation.json").read_text(encoding="utf-8"))
    assert validation["endpoint_status"] == "survival-only"
    assert validation["task_support"]["progression-risk"]["state"] == "blocked-missing-endpoint"
    assert validation["task_support"]["progression-risk"]["required_fields_missing"] == [
        "days_to_recurrence",
        "progression_or_recurrence",
    ]
    assert validation["task_support"]["overall-survival"]["state"] == "buildable-candidate"
    assert validation["task_support"]["overall-survival"]["required_fields_present"] == [
        "vital_status",
        "days_to_death",
    ]
    assert validation["promotable"] is False
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run from `~/d/science-commons/datasets/mmrf-commpass/recipe`:

```bash
PYTHONPATH=~/d/science/science/src rtk uv run --frozen --project ~/d/science/science \
  pytest test_mmrf_recipe.py::test_task_support_derives_progression_and_survival_states \
  test_mmrf_recipe.py::test_write_dry_run_refuses_survival_only_for_progression_task -q
```

Expected: FAIL with `ImportError` or `AttributeError` for `derive_task_support`, or `KeyError: 'task_support'`.

- [ ] **Step 3: Implement task-support derivation**

In `fetch_manifest.py`, add these constants after `SURVIVAL_FIELDS`:

```python
PROGRESSION_TASK_ID = "progression-risk"
SURVIVAL_TASK_ID = "overall-survival"
PROGRESSION_REQUIRED_FIELDS = ["days_to_recurrence", "progression_or_recurrence"]
SURVIVAL_REQUIRED_FIELDS = ["vital_status", "days_to_death"]
```

Add this helper after `discover_endpoint_fields`:

```python
def derive_task_support(endpoint_report: Mapping[str, Any]) -> dict[str, dict[str, Any]]:
    progression_present = [field for field in PROGRESSION_REQUIRED_FIELDS if field in endpoint_report["progression_fields"]]
    progression_missing = [field for field in PROGRESSION_REQUIRED_FIELDS if field not in progression_present]
    survival_present = [field for field in SURVIVAL_REQUIRED_FIELDS if field in endpoint_report["survival_fields"]]
    survival_missing = [field for field in SURVIVAL_REQUIRED_FIELDS if field not in survival_present]

    if progression_missing:
        progression_state = "blocked-missing-endpoint"
        progression_reason = "Open GDC metadata lacks usable progression or recurrence endpoints."
    else:
        progression_state = "buildable-candidate"
        progression_reason = "Open GDC metadata has usable progression or recurrence endpoints for manifest cases."

    if survival_missing:
        survival_state = "blocked-missing-endpoint"
        survival_reason = "Open GDC metadata lacks overall-survival endpoint fields."
    else:
        survival_state = "buildable-candidate"
        survival_reason = "Open GDC metadata has overall-survival endpoint fields."

    return {
        PROGRESSION_TASK_ID: {
            "state": progression_state,
            "reason": progression_reason,
            "required_fields_present": progression_present,
            "required_fields_missing": progression_missing,
        },
        SURVIVAL_TASK_ID: {
            "state": survival_state,
            "reason": survival_reason,
            "required_fields_present": survival_present,
            "required_fields_missing": survival_missing,
        },
    }
```

In `write_dry_run`, compute `task_support` immediately after `endpoint_report`:

```python
    task_support = derive_task_support(endpoint_report)
```

Add it to the `validation` dict immediately after `"endpoint_status": endpoint_report["status"],`:

```python
        "task_support": task_support,
```

- [ ] **Step 4: Run the task-support tests to verify they pass**

Run:

```bash
PYTHONPATH=~/d/science/science/src rtk uv run --frozen --project ~/d/science/science \
  pytest test_mmrf_recipe.py::test_task_support_derives_progression_and_survival_states \
  test_mmrf_recipe.py::test_write_dry_run_refuses_survival_only_for_progression_task -q
```

Expected: PASS.

- [ ] **Step 5: Commit Task 1**

```bash
rtk git -C ~/d/science-commons add datasets/mmrf-commpass/recipe/fetch_manifest.py datasets/mmrf-commpass/recipe/test_mmrf_recipe.py
rtk git -C ~/d/science-commons commit -m "feat(dataset): report MMRF task support diagnostics"
```

## Task 2: Cohort Aggregation Diagnostics

**Files:**
- Modify: `~/d/science-commons/datasets/mmrf-commpass/recipe/test_mmrf_recipe.py`
- Modify: `~/d/science-commons/datasets/mmrf-commpass/recipe/fetch_manifest.py`

- [ ] **Step 1: Write failing tests for cohort mode and duplicate diagnostics**

Replace `test_write_dry_run_refuses_manifest_duplicate_case_submitter_id` with:

```python
def test_write_dry_run_reports_unresolved_cohort_for_duplicate_case_submitter_id(tmp_path):
    from fetch_manifest import StaticGdcClient, write_dry_run

    duplicate_manifest = _load_json("files_page.json")
    duplicate_manifest["data"]["hits"][1]["cases"][0]["submitter_id"] = "MMRF_0001"

    client = StaticGdcClient(
        status_payload={
            "data_release": "Data Release 45.0 - December 04, 2025",
            "commit": "fixture",
            "status": "OK",
        },
        file_total=3,
        file_pages=[duplicate_manifest],
        case_pages=[_load_json("cases_progression.json")],
    )

    with pytest.raises(ValueError, match="unresolved cohort; duplicate case_submitter_id: MMRF_0001"):
        write_dry_run(output_dir=tmp_path, client=client)

    validation = json.loads((tmp_path / "reports" / "validation.json").read_text(encoding="utf-8"))
    assert validation["endpoint_status"] == "progression-ready"
    assert validation["progression_outcome_coverage_complete"] is True
    assert validation["buildable_manifest"] is False
    assert validation["cohort_mode"] == "unresolved-cohort"
    assert validation["cohort_aggregation"] == {
        "duplicate_case_submitter_id_count": 1,
        "duplicate_case_submitter_id_values": ["MMRF_0001"],
        "duplicate_sample_submitter_id_count": 0,
        "duplicate_sample_submitter_id_values": [],
        "duplicate_file_id_count": 0,
        "duplicate_file_id_values": [],
        "affected_case_submitter_id_count": 1,
        "selected_policy": None,
        "blocking_reason": "ambiguous-patient-expression-files",
    }
    assert validation["duplicate_manifest_values"] == {
        "case_submitter_id": ["MMRF_0001"],
        "sample_submitter_id": [],
        "file_id": [],
    }
    assert validation["promotable"] is False


def test_write_dry_run_reports_unique_manifest_no_policy_applied(tmp_path):
    from fetch_manifest import StaticGdcClient, write_dry_run

    client = StaticGdcClient(
        status_payload={
            "data_release": "Data Release 45.0 - December 04, 2025",
            "commit": "fixture",
            "status": "OK",
        },
        file_total=3,
        file_pages=[_load_json("files_page.json")],
        case_pages=[_load_json("cases_progression.json")],
    )

    report = write_dry_run(output_dir=tmp_path, client=client)
    validation = json.loads((tmp_path / "reports" / "validation.json").read_text(encoding="utf-8"))
    assert report["promotable"] is True
    # A coincidentally-unique manifest is NOT a curated patient-level selection;
    # no selection policy has been applied, so selected_policy stays null.
    assert validation["cohort_mode"] == "unique-manifest-no-policy-applied"
    assert validation["cohort_aggregation"] == {
        "duplicate_case_submitter_id_count": 0,
        "duplicate_case_submitter_id_values": [],
        "duplicate_sample_submitter_id_count": 0,
        "duplicate_sample_submitter_id_values": [],
        "duplicate_file_id_count": 0,
        "duplicate_file_id_values": [],
        "affected_case_submitter_id_count": 0,
        "selected_policy": None,
        "blocking_reason": None,
    }
```

- [ ] **Step 2: Run the cohort tests to verify they fail**

Run:

```bash
PYTHONPATH=~/d/science/science/src rtk uv run --frozen --project ~/d/science/science \
  pytest test_mmrf_recipe.py::test_write_dry_run_reports_unresolved_cohort_for_duplicate_case_submitter_id \
  test_mmrf_recipe.py::test_write_dry_run_reports_unique_manifest_no_policy_applied -q
```

Expected: FAIL with `KeyError: 'cohort_mode'` or the old duplicate error text.

- [ ] **Step 3: Implement cohort aggregation diagnostics**

In `fetch_manifest.py`, replace `validate_manifest_buildability` with:

```python
def _duplicate_values(rows: list[Mapping[str, Any]], field: str) -> list[str]:
    return sorted(str(value) for value, count in Counter(row.get(field) for row in rows).items() if count > 1)


def _cohort_aggregation_report(rows: list[Mapping[str, Any]], duplicate_values: Mapping[str, list[str]]) -> dict[str, Any]:
    duplicate_case_values = list(duplicate_values["case_submitter_id"])
    duplicate_sample_values = list(duplicate_values["sample_submitter_id"])
    duplicate_file_values = list(duplicate_values["file_id"])
    unresolved = bool(duplicate_case_values or duplicate_sample_values or duplicate_file_values)
    affected_cases = {
        str(row.get("case_submitter_id"))
        for row in rows
        if row.get("case_submitter_id") in duplicate_case_values
        or row.get("sample_submitter_id") in duplicate_sample_values
        or row.get("file_id") in duplicate_file_values
    }
    if unresolved:
        selected_policy = None
        blocking_reason = "ambiguous-patient-expression-files"
    else:
        # A unique manifest is not a curated patient-level selection. No
        # selection policy has been applied, so leave selected_policy null; the
        # `unique-manifest-no-policy-applied` cohort_mode carries the meaning.
        selected_policy = None
        blocking_reason = None

    return {
        "duplicate_case_submitter_id_count": len(duplicate_case_values),
        "duplicate_case_submitter_id_values": duplicate_case_values,
        "duplicate_sample_submitter_id_count": len(duplicate_sample_values),
        "duplicate_sample_submitter_id_values": duplicate_sample_values,
        "duplicate_file_id_count": len(duplicate_file_values),
        "duplicate_file_id_values": duplicate_file_values,
        "affected_case_submitter_id_count": len(affected_cases),
        "selected_policy": selected_policy,
        "blocking_reason": blocking_reason,
    }


def validate_manifest_buildability(rows: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    materialized = list(rows)
    duplicate_values = {field: _duplicate_values(materialized, field) for field in UNIQUE_MANIFEST_IDENTITY_FIELDS}
    buildable_manifest = not any(duplicate_values.values())
    cohort_aggregation = _cohort_aggregation_report(materialized, duplicate_values)
    return {
        "buildable_manifest": buildable_manifest,
        "duplicate_manifest_values": duplicate_values,
        "cohort_mode": "unique-manifest-no-policy-applied" if buildable_manifest else "unresolved-cohort",
        "cohort_aggregation": cohort_aggregation,
    }
```

In the duplicate error block in `write_dry_run`, replace the raised message with:

```python
        raise ValueError(f"Manifest has unresolved cohort; duplicate {'; '.join(duplicate_parts)}")
```

- [ ] **Step 4: Run the cohort tests to verify they pass**

Run:

```bash
PYTHONPATH=~/d/science/science/src rtk uv run --frozen --project ~/d/science/science \
  pytest test_mmrf_recipe.py::test_write_dry_run_reports_unresolved_cohort_for_duplicate_case_submitter_id \
  test_mmrf_recipe.py::test_write_dry_run_reports_unique_manifest_no_policy_applied -q
```

Expected: PASS.

- [ ] **Step 5: Run prior dry-run tests that depend on validation shape**

Run:

```bash
PYTHONPATH=~/d/science/science/src rtk uv run --frozen --project ~/d/science/science \
  pytest test_mmrf_recipe.py::test_write_dry_run_outputs_manifest_query_and_validation \
  test_mmrf_recipe.py::test_write_dry_run_refuses_partial_progression_outcome_coverage \
  test_mmrf_recipe.py::test_write_dry_run_requires_progression_on_manifest_cases -q
```

Expected: PASS.

- [ ] **Step 6: Commit Task 2**

```bash
rtk git -C ~/d/science-commons add datasets/mmrf-commpass/recipe/fetch_manifest.py datasets/mmrf-commpass/recipe/test_mmrf_recipe.py
rtk git -C ~/d/science-commons commit -m "feat(dataset): classify MMRF cohort aggregation state"
```

## Task 3: Sample-Selection Field Probes

**Files:**
- Modify: `~/d/science-commons/datasets/mmrf-commpass/recipe/test_mmrf_recipe.py`
- Modify: `~/d/science-commons/datasets/mmrf-commpass/recipe/fetch_manifest.py`

- [ ] **Step 1: Write failing tests for sample-selection probes**

Add these tests after the cohort aggregation tests:

```python
def test_discover_sample_selection_fields_reports_structured_heuristic_and_absent():
    from fetch_manifest import discover_sample_selection_fields, normalize_file_hit

    rows = [normalize_file_hit(hit) for hit in _load_json("files_page.json")["data"]["hits"]]
    fields = discover_sample_selection_fields(rows)

    # Structured fields the recipe actually queries: real present/count probes.
    assert fields["sample_type"] == {
        "present": True,
        "non_null_count": 3,
        "source": "sample_type",
        "basis": "structured-field",
        "policy_use": "restrict bone marrow tumor samples when sufficient for policy review",
    }
    assert fields["sample_submitter_id"]["basis"] == "structured-field"
    assert fields["sample_submitter_id"]["non_null_count"] == 3

    # CD138 signal IS in the fixture, but only as an id token, never a
    # structured field. Report it honestly as a heuristic, not absent.
    assert fields["cd138_positive"] == {
        "present": True,
        "non_null_count": 3,
        "source": "sample_submitter_id",
        "basis": "id-token-heuristic",
        "policy_use": "CD138-positive signal is only an id-token heuristic; a structured field is required for a first-class selection rule.",
    }

    # Timepoint and treatment line are not in the open GDC fields the recipe
    # queries, so they are marked not-queried — not a live probe that could
    # silently flip to present.
    assert fields["disease_course_timepoint"]["basis"] == "not-queried"
    assert fields["disease_course_timepoint"]["present"] is False
    assert fields["treatment_line"]["basis"] == "not-queried"
    assert fields["treatment_line"]["present"] is False


def test_write_dry_run_includes_sample_selection_fields(tmp_path):
    from fetch_manifest import StaticGdcClient, write_dry_run

    client = StaticGdcClient(
        status_payload={
            "data_release": "Data Release 45.0 - December 04, 2025",
            "commit": "fixture",
            "status": "OK",
        },
        file_total=3,
        file_pages=[_load_json("files_page.json")],
        case_pages=[_load_json("cases_progression.json")],
    )

    write_dry_run(output_dir=tmp_path, client=client)
    validation = json.loads((tmp_path / "reports" / "validation.json").read_text(encoding="utf-8"))
    fields = validation["sample_selection_fields"]
    assert fields["sample_type"]["present"] is True
    assert fields["sample_submitter_id"]["present"] is True
    assert fields["cd138_positive"]["basis"] == "id-token-heuristic"
    assert fields["disease_course_timepoint"]["basis"] == "not-queried"
    assert fields["treatment_line"]["basis"] == "not-queried"
```

- [ ] **Step 2: Run the sample-probe tests to verify they fail**

Run:

```bash
PYTHONPATH=~/d/science/science/src rtk uv run --frozen --project ~/d/science/science \
  pytest test_mmrf_recipe.py::test_discover_sample_selection_fields_reports_structured_heuristic_and_absent \
  test_mmrf_recipe.py::test_write_dry_run_includes_sample_selection_fields -q
```

Expected: FAIL with `ImportError` or `KeyError: 'sample_selection_fields'`.

- [ ] **Step 3: Implement sample-selection field probes**

In `fetch_manifest.py`, add this helper after `validate_manifest_buildability`:

```python
def _non_null_count(rows: Iterable[Mapping[str, Any]], field: str) -> int:
    return sum(1 for row in rows if _has_value(row.get(field)))


def _sample_id_token_count(rows: Iterable[Mapping[str, Any]], token: str) -> int:
    token_lower = token.lower()
    return sum(1 for row in rows if token_lower in str(row.get("sample_submitter_id") or "").lower())


def discover_sample_selection_fields(rows: Iterable[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    """Report which sample-selection signals the open GDC manifest exposes.

    `sample_type` and `sample_submitter_id` are structured fields the recipe
    actually queries, so they are live present/count probes. `cd138_positive`
    is derivable only as an id-token heuristic (the CD138 signal lives inside
    the sample id string, not a structured field). `disease_course_timepoint`
    and `treatment_line` are NOT in the file/case fields the recipe queries, so
    they are reported as `not-queried` rather than a live probe that could
    silently flip to present.
    """
    materialized = list(rows)
    cd138_count = _sample_id_token_count(materialized, "CD138pos")
    return {
        "sample_type": {
            "present": any(_has_value(row.get("sample_type")) for row in materialized),
            "non_null_count": _non_null_count(materialized, "sample_type"),
            "source": "sample_type",
            "basis": "structured-field",
            "policy_use": "restrict bone marrow tumor samples when sufficient for policy review",
        },
        "sample_submitter_id": {
            "present": any(_has_value(row.get("sample_submitter_id")) for row in materialized),
            "non_null_count": _non_null_count(materialized, "sample_submitter_id"),
            "source": "sample_submitter_id",
            "basis": "structured-field",
            "policy_use": "inspect sample id tokens such as BM and CD138pos; not sufficient without review",
        },
        "cd138_positive": {
            "present": cd138_count > 0,
            "non_null_count": cd138_count,
            "source": "sample_submitter_id",
            "basis": "id-token-heuristic",
            "policy_use": "CD138-positive signal is only an id-token heuristic; a structured field is required for a first-class selection rule.",
        },
        "disease_course_timepoint": {
            "present": False,
            "non_null_count": 0,
            "source": None,
            "basis": "not-queried",
            "policy_use": "not exposed by the open GDC file/case fields currently queried; required for a baseline or earliest-timepoint selection rule.",
        },
        "treatment_line": {
            "present": False,
            "non_null_count": 0,
            "source": None,
            "basis": "not-queried",
            "policy_use": "not exposed by the open GDC file/case fields currently queried; required before treatment-line-specific aggregation can be declared.",
        },
    }
```

In `write_dry_run`, compute the fields after `file_rows` are normalized:

```python
    sample_selection_fields = discover_sample_selection_fields(file_rows)
```

Add a `sample_selection_fields` key anywhere in the `validation` dict literal (there is no literal `cohort_aggregation:` line to anchor on — it arrives via `**buildability_report` — so just place this alongside the other reporting keys, e.g. immediately after `"survival_fields": endpoint_report["survival_fields"],`):

```python
        "sample_selection_fields": sample_selection_fields,
```

- [ ] **Step 4: Run the sample-probe tests to verify they pass**

Run:

```bash
PYTHONPATH=~/d/science/science/src rtk uv run --frozen --project ~/d/science/science \
  pytest test_mmrf_recipe.py::test_discover_sample_selection_fields_reports_structured_heuristic_and_absent \
  test_mmrf_recipe.py::test_write_dry_run_includes_sample_selection_fields -q
```

Expected: PASS.

- [ ] **Step 5: Commit Task 3**

```bash
rtk git -C ~/d/science-commons add datasets/mmrf-commpass/recipe/fetch_manifest.py datasets/mmrf-commpass/recipe/test_mmrf_recipe.py
rtk git -C ~/d/science-commons commit -m "feat(dataset): probe MMRF sample selection fields"
```

## Task 4: Schema And Recipe Documentation

**Files:**
- Modify: `~/d/science-commons/datasets/mmrf-commpass/recipe/test_mmrf_recipe.py`
- Modify: `~/d/science-commons/datasets/mmrf-commpass/recipe/manifest.schema.yaml`
- Modify: `~/d/science-commons/datasets/mmrf-commpass/recipe/README.md`

- [ ] **Step 1: Write failing schema/README tests**

Add these tests near the existing recipe metadata tests in `test_mmrf_recipe.py`:

```python
def test_manifest_schema_documents_task_support_and_cohort_fields():
    schema = yaml.safe_load((RECIPE_DIR / "manifest.schema.yaml").read_text(encoding="utf-8"))
    required_fields = schema["validation_report"]["required_fields"]
    assert "task_support" in required_fields
    assert "cohort_mode" in required_fields
    assert "cohort_aggregation" in required_fields
    assert "sample_selection_fields" in required_fields

    fields = schema["validation_report"]["fields"]
    assert fields["task_support"]["tasks"] == ["progression-risk", "overall-survival"]
    # Only the two states this slice can actually emit are advertised. The
    # design's patient-level-single-sample / sample-level-with-patient-outcomes
    # modes require a real selection/evaluation policy and are deferred.
    assert fields["cohort_mode"]["allowed_values"] == [
        "unique-manifest-no-policy-applied",
        "unresolved-cohort",
    ]
    assert fields["cohort_aggregation"]["blocking_reasons"] == [
        "ambiguous-patient-expression-files",
    ]


def test_manifest_schema_drops_fallback_framing_and_lists_survival_candidate():
    schema = yaml.safe_load((RECIPE_DIR / "manifest.schema.yaml").read_text(encoding="utf-8"))
    # overall-survival is a distinct candidate task, not a fallback ground truth.
    assert schema["dataset"]["task"] == "progression-risk"
    assert schema["dataset"]["candidate_tasks"] == ["overall-survival"]
    endpoint_fields = schema["case_manifest"]["endpoint_fields"]
    assert "survival_fallback_report_only" not in endpoint_fields
    assert "survival_report_only" in endpoint_fields


def test_recipe_readme_documents_task_aware_dry_run_without_entity_promotion():
    text = (RECIPE_DIR / "README.md").read_text(encoding="utf-8")
    assert "task_support" in text
    assert "overall-survival" in text
    assert "cohort_mode" in text
    assert "sample_selection_fields" in text
    assert "entity.md remains a pointer" in text
```

- [ ] **Step 2: Run the schema/README tests to verify they fail**

Run:

```bash
PYTHONPATH=~/d/science/science/src rtk uv run --frozen --project ~/d/science/science \
  pytest test_mmrf_recipe.py::test_manifest_schema_documents_task_support_and_cohort_fields \
  test_mmrf_recipe.py::test_manifest_schema_drops_fallback_framing_and_lists_survival_candidate \
  test_mmrf_recipe.py::test_recipe_readme_documents_task_aware_dry_run_without_entity_promotion -q
```

Expected: FAIL with missing keys or missing README strings.

- [ ] **Step 3: Update `manifest.schema.yaml` validation report contract**

In `manifest.schema.yaml`, add these entries to `validation_report.required_fields` after `endpoint_status`:

```yaml
    - task_support
    - cohort_mode
    - cohort_aggregation
    - sample_selection_fields
```

Add these field docs under `validation_report.fields`, immediately after `endpoint_status`:

```yaml
    task_support:
      type: object
      tasks: [progression-risk, overall-survival]
      state_values:
        - blocked-missing-endpoint
        - buildable-candidate
      description: >
        Per-task diagnostic derived from dataset-level endpoint_status and
        observed endpoint fields. This is report metadata, not dataset
        promotion.
    cohort_mode:
      type: string
      allowed_values:
        - unique-manifest-no-policy-applied
        - unresolved-cohort
      deferred_modes:
        - patient-level-single-sample
        - sample-level-with-patient-outcomes
      description: >
        Current manifest aggregation state. This slice only classifies manifest
        uniqueness, so it emits unique-manifest-no-policy-applied (no duplicates,
        but no curated patient-level selection rule applied) or unresolved-cohort
        (duplicates present). The design's patient-level-single-sample and
        sample-level-with-patient-outcomes modes require an actual selection or
        evaluation policy and are deferred; they are not emitted yet.
    cohort_aggregation:
      type: object
      blocking_reasons:
        - ambiguous-patient-expression-files
      description: >
        Duplicate patient/sample/file diagnostics. selected_policy is null until
        a real patient-level selection policy is implemented.
    sample_selection_fields:
      type: object
      description: >
        Report of which sample-selection signals the open GDC manifest exposes.
        Each entry carries a basis: structured-field (a live present/count probe
        of a queried field), id-token-heuristic (derived from the sample id
        string, e.g. CD138 positivity), or not-queried (a field the recipe does
        not currently request from GDC, so it cannot flip to present without a
        query change). Used to scope a future patient-level selection policy.
```

Update `validation_report.refusal_conditions` to include:

```yaml
    - cohort_mode is unresolved-cohort
```

Also clean up two stale/contradictory labels elsewhere in `manifest.schema.yaml` (issue #3 — the design forbids treating overall survival as a fallback):

- In the `dataset:` block, keep `task: progression-risk` (the promoted task) and add a sibling line documenting the report-only candidate:

```yaml
  candidate_tasks: [overall-survival]
  candidate_tasks_note: >
    overall-survival is reported per-task in validation.json as a distinct
    benchmark candidate, never a fallback for progression-risk. It is not added
    to entity.md in this slice.
```

- In `case_manifest.endpoint_fields`, rename the survival key so it no longer implies a fallback, and update the adjacent note:

```yaml
    survival_report_only:
      - demographic.vital_status
      - demographic.days_to_death
```

```yaml
  notes:
    - Survival metadata is reported per-task as a distinct overall-survival candidate; it is not a fallback for progression-risk promotion.
    - Every manifest case_id must resolve to a case record before package build.
```

- [ ] **Step 4: Update `README.md` dry-run output docs**

In the `Dry Run` section, replace the blocker list with:

```markdown
The dry run queries GDC, writes metadata, and then refuses non-promotable
outcomes. It writes the manifest and validation report before raising for these
known blocker states:

- manifest-linked cases missing from the GDC cases response;
- open metadata exposing only overall-survival fields for the current
  `progression-risk` task;
- open metadata missing usable progression fields;
- duplicate or ambiguous patient/sample/file mappings that leave
  `cohort_mode: unresolved-cohort`.

The validation report is task-aware. `endpoint_status` remains dataset-level,
while `task_support` reports whether each candidate task is currently blocked
or buildable from the discovered endpoint fields. `overall-survival` is reported
as a distinct candidate task when survival fields are present; it is not treated
as a fallback ground truth for `progression-risk`.

The report also includes `sample_selection_fields` so a future promotion
review can see which open GDC sample signals are available before declaring a
CD138-positive, baseline, treatment-line, or disease-course selection policy.
Each field records a `basis`: `structured-field` (a real probe of a queried
field), `id-token-heuristic` (derived from the sample id string, e.g. CD138
positivity), or `not-queried` (a field the recipe does not currently request).
`entity.md remains a pointer` until a separate promotion review changes the
dataset class and task metadata.
```

After the dry-run output list, add:

````markdown
`reports/validation.json` now includes:

```text
endpoint_status
task_support
cohort_mode
cohort_aggregation
sample_selection_fields
promotable
```
````

- [ ] **Step 5: Run the schema/README tests to verify they pass**

Run:

```bash
PYTHONPATH=~/d/science/science/src rtk uv run --frozen --project ~/d/science/science \
  pytest test_mmrf_recipe.py::test_manifest_schema_documents_task_support_and_cohort_fields \
  test_mmrf_recipe.py::test_manifest_schema_drops_fallback_framing_and_lists_survival_candidate \
  test_mmrf_recipe.py::test_recipe_readme_documents_task_aware_dry_run_without_entity_promotion -q
```

Expected: PASS.

- [ ] **Step 6: Commit Task 4**

```bash
rtk git -C ~/d/science-commons add datasets/mmrf-commpass/recipe/test_mmrf_recipe.py datasets/mmrf-commpass/recipe/manifest.schema.yaml datasets/mmrf-commpass/recipe/README.md
rtk git -C ~/d/science-commons commit -m "docs(dataset): document MMRF task support diagnostics"
```

## Task 5: Full Verification And Live Dry-Run Calibration

**Files:**
- Verify: `~/d/science-commons/datasets/mmrf-commpass/recipe/*`
- Verify: `~/d/science-commons/datasets/mmrf-commpass/entity.md`

- [ ] **Step 1: Run the full recipe test suite**

Run from `~/d/science-commons/datasets/mmrf-commpass/recipe`:

```bash
PYTHONPATH=~/d/science/science/src rtk uv run --frozen --project ~/d/science/science \
  pytest test_mmrf_recipe.py -q
```

Expected: PASS.

- [ ] **Step 2: Confirm the dataset entity remains a pointer**

Run:

```bash
rtk rg -n "dataset_class:|id: progression-risk|id: overall-survival" ~/d/science-commons/datasets/mmrf-commpass/entity.md
```

Expected output includes `dataset_class: "pointer"` and `id: progression-risk`; it does not include `id: overall-survival`.

- [ ] **Step 3: Run a live dry run into a temporary output directory**

Run:

```bash
mkdir -p /tmp/mmrf-commpass-task-variants
PYTHONPATH=~/d/science/science/src rtk uv run --frozen --project ~/d/science/science \
  python ~/d/science-commons/datasets/mmrf-commpass/recipe/fetch_manifest.py \
  --output-dir /tmp/mmrf-commpass-task-variants
```

Expected: the command may exit nonzero because the current live GDC-open state is not promotable for `progression-risk`. It must still write `/tmp/mmrf-commpass-task-variants/reports/validation.json`.

- [ ] **Step 4: Inspect the live validation fields**

Run:

```bash
PYTHONPATH=~/d/science/science/src rtk uv run --frozen --project ~/d/science/science \
  python -m json.tool /tmp/mmrf-commpass-task-variants/reports/validation.json
```

Expected:

- `endpoint_status` is present.
- `task_support.progression-risk.state` is present.
- `task_support.overall-survival.state` is present.
- `cohort_mode` is present (one of `unique-manifest-no-policy-applied`, `unresolved-cohort`).
- `cohort_aggregation` is present.
- `sample_selection_fields` is present.
- `promotable` is `false` unless GDC now exposes complete progression endpoints and a unique manifest.

- [ ] **Step 5: Run commons validation for the unchanged pointer entity**

Run from `~/d/science-commons`:

```bash
PYTHONPATH=~/d/science/science/src rtk uv run --frozen --project ~/d/science/science \
  science validate --project-root ~/d/science-commons --entity dataset:mmrf-commpass --format json
```

Expected: PASS with no validation errors for `dataset:mmrf-commpass`.

- [ ] **Step 6: Commit verification-driven adjustments if needed**

If Task 5 exposed only docs/test expectation adjustments, commit them with:

```bash
rtk git -C ~/d/science-commons add datasets/mmrf-commpass/recipe
rtk git -C ~/d/science-commons commit -m "test(dataset): calibrate MMRF task diagnostics"
```

If no files changed, do not create an empty commit.

## Self-Review Checklist

- Spec coverage:
  - Task support for `progression-risk` and `overall-survival`: Tasks 1 and 4.
  - Dataset-level `endpoint_status` stays single-valued: Task 1 derives support from the existing endpoint report and does not create task-level endpoint statuses.
  - Cohort aggregation state and duplicate diagnostics: Task 2.
  - Sample-selection fields (structured probes + id-token heuristic + not-queried markers): Task 3.
  - No promotion or entity change: Task 5 explicitly checks `entity.md` remains pointer and lacks `overall-survival`; the Goal states the benchmark CLI surface is unchanged.
  - Documentation/schema contract, incl. dropping "fallback" framing and listing the survival candidate: Task 4.
- Placeholder scan:
  - No placeholder markers or unspecified edge-case instructions.
  - Every code-changing step includes concrete snippets and exact commands.
- Type consistency:
  - `task_support` keys are `progression-risk` and `overall-survival` throughout.
  - `cohort_mode` emits only the two reachable states this slice classifies: `unique-manifest-no-policy-applied`, `unresolved-cohort`. The design's `patient-level-single-sample` and `sample-level-with-patient-outcomes` are deferred (documented, not emitted), so a coincidentally-unique manifest is never mislabeled as a curated selection.
  - `sample_selection_fields` is a validation-report field only; it does not affect promotion. Each entry's `basis` (`structured-field` / `id-token-heuristic` / `not-queried`) makes clear which entries are live probes versus known-absent fields.

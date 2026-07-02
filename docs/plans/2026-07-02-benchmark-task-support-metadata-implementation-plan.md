# Benchmark Task Support Metadata v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add durable task-local benchmark support metadata so `science benchmark tests` and `science benchmark test-triage` can explain supported, candidate-only, and blocked benchmark tasks without reading local recipe artifacts.

**Architecture:** Extend the dataset benchmark task schema with an optional strict `support` block, then make the benchmark report raw-frontmatter path validate and project that block into additive row fields and reason notes. Keep dataset readiness as the access/runtime axis and route support states only in the triage bucket function.

**Tech Stack:** Python 3.12, Pydantic, JSON Schema, Click CLI tests, pytest, science commons dataset frontmatter.

---

## File Structure

- `science/model/src/science_model/packages/schema.py`
  - Add `BenchmarkTaskSupport` and attach it to `BenchmarkTask`.
  - Enforce support state enum, reason code format, `checked_at` date format, and required reason for `candidate` / `blocked`.
- `science/model/src/science_model/schemas/mixin-dataset-1.0.json`
  - Add the matching JSON Schema under `benchmark_task.support`.
- `science/model/tests/test_dataset_models.py`
  - Cover entity parsing for valid support and schema-model failures.
- `science/src/science_tool/benchmark_opportunities.py`
  - Add report-local task support types, strict raw-frontmatter parser, row projection fields, support reason notes, and triage bucket branches.
- `science/tests/test_benchmark_cli.py`
  - Cover JSON row projection, invalid raw support failure, blocked/candidate triage routing, and candidate-not-run-now behavior.
- `science/src/science_tool/validate/checks/benchmark_metadata.py`
  - Add validation diagnostics for malformed task support metadata on raw frontmatter.
- `science/tests/validate/test_checks_benchmark_metadata.py`
  - Cover support reason/state validation diagnostics.
- `~/d/science-commons/datasets/mmrf-commpass/entity.md`
  - Add durable support metadata for `progression-risk`; optionally add explicit `overall-survival` only if the record already has enough task metadata to make it a distinct authored task.

## Task 1: Model and JSON Schema

**Files:**
- Modify: `science/model/src/science_model/packages/schema.py`
- Modify: `science/model/src/science_model/schemas/mixin-dataset-1.0.json`
- Test: `science/model/tests/test_dataset_models.py`

- [ ] **Step 1: Add failing model tests**

Append these tests after `test_parse_dataset_benchmark_block` in `science/model/tests/test_dataset_models.py`:

```python
def test_parse_dataset_benchmark_task_support_block(tmp_path: Path) -> None:
    md = _write_dataset_md(
        tmp_path,
        "benchmark:",
        "  tasks:",
        "    - id: progression-risk",
        "      task_type: survival prediction",
        "      prediction_target: progression or relapse",
        "      held_out_unit: patient",
        "      metric: concordance-index",
        "      baseline: clinical covariates",
        "      ground_truth:",
        "        type: clinical-endpoint",
        "        description: progression-free survival endpoint",
        "      support:",
        "        state: blocked",
        "        reason: open-metadata-missing-progression-endpoint",
        "        checked_at: '2026-07-02'",
        "        evidence:",
        "          - recipe/reports/validation.json#task_support.progression-risk",
        "        notes:",
        "          - Open metadata lacks progression endpoint coverage.",
    )

    entity = parse_entity_file(md, project_slug="testproj")

    task = entity.benchmark.tasks[0]
    assert task.support is not None
    assert task.support.state == "blocked"
    assert task.support.reason == "open-metadata-missing-progression-endpoint"
    assert task.support.checked_at == "2026-07-02"
    assert task.support.evidence == ["recipe/reports/validation.json#task_support.progression-risk"]
    assert task.support.notes == ["Open metadata lacks progression endpoint coverage."]


def test_parse_dataset_benchmark_task_support_unknown_state_raises(tmp_path: Path) -> None:
    md = _write_dataset_md(
        tmp_path,
        "benchmark:",
        "  tasks:",
        "    - id: progression-risk",
        "      support:",
        "        state: blockd",
        "        reason: open-metadata-missing-progression-endpoint",
        "        checked_at: '2026-07-02'",
    )

    with pytest.raises(ValidationError, match="support"):
        parse_entity_file(md, project_slug="testproj")


def test_parse_dataset_benchmark_task_support_candidate_requires_reason(tmp_path: Path) -> None:
    md = _write_dataset_md(
        tmp_path,
        "benchmark:",
        "  tasks:",
        "    - id: overall-survival",
        "      support:",
        "        state: candidate",
        "        checked_at: '2026-07-02'",
    )

    with pytest.raises(ValidationError, match="support.reason is required"):
        parse_entity_file(md, project_slug="testproj")


def test_parse_dataset_benchmark_task_support_reason_must_be_kebab_case(tmp_path: Path) -> None:
    md = _write_dataset_md(
        tmp_path,
        "benchmark:",
        "  tasks:",
        "    - id: progression-risk",
        "      support:",
        "        state: blocked",
        "        reason: Missing Endpoint",
        "        checked_at: '2026-07-02'",
    )

    with pytest.raises(ValidationError, match="support.reason"):
        parse_entity_file(md, project_slug="testproj")
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
uv run --frozen pytest science/model/tests/test_dataset_models.py -k "benchmark_task_support" -v
```

Expected: failures mention extra field `support` or missing `BenchmarkTask.support`.

- [ ] **Step 3: Add model implementation**

In `science/model/src/science_model/packages/schema.py`, add this near `GroundTruth`:

```python
BenchmarkTaskSupportState = Literal["supported", "candidate", "blocked"]
_BENCHMARK_TASK_SUPPORT_REASON_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_BENCHMARK_TASK_SUPPORT_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class BenchmarkTaskSupport(BaseModel):
    """Durable task-local support assessment for benchmark report actionability."""

    state: BenchmarkTaskSupportState
    reason: str = ""
    checked_at: str = ""
    evidence: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    model_config = ConfigDict(extra="forbid")

    @field_validator("reason")
    @classmethod
    def _validate_reason(cls, value: str) -> str:
        if value and _BENCHMARK_TASK_SUPPORT_REASON_RE.fullmatch(value) is None:
            raise ValueError("support.reason must be lowercase kebab-case")
        return value

    @field_validator("checked_at")
    @classmethod
    def _validate_checked_at(cls, value: str) -> str:
        if value and _BENCHMARK_TASK_SUPPORT_DATE_RE.fullmatch(value) is None:
            raise ValueError("support.checked_at must be YYYY-MM-DD")
        return value

    @model_validator(mode="after")
    def _validate_state_requirements(self) -> BenchmarkTaskSupport:
        if self.state in {"candidate", "blocked"} and not self.reason:
            raise ValueError("support.reason is required when support.state is candidate or blocked")
        return self
```

Add `support: BenchmarkTaskSupport | None = None` to `BenchmarkTask`.

If `Literal` or `model_validator` are not already imported in this file, update imports to include them.

- [ ] **Step 4: Add JSON Schema implementation**

In `science/model/src/science_model/schemas/mixin-dataset-1.0.json`, add this property to `$defs.benchmark_task.properties`:

```json
"support": {"$ref": "#/$defs/benchmark_task_support"}
```

Add this sibling definition under `$defs`:

```json
"benchmark_task_support": {
  "type": "object",
  "additionalProperties": false,
  "required": ["state"],
  "properties": {
    "state": {"enum": ["supported", "candidate", "blocked"]},
    "reason": {
      "type": "string",
      "pattern": "^[a-z0-9]+(?:-[a-z0-9]+)*$"
    },
    "checked_at": {
      "type": "string",
      "pattern": "^\\d{4}-\\d{2}-\\d{2}$"
    },
    "evidence": {"type": "array", "items": {"type": "string"}},
    "notes": {"type": "array", "items": {"type": "string"}}
  },
  "allOf": [
    {
      "if": {"properties": {"state": {"enum": ["candidate", "blocked"]}}, "required": ["state"]},
      "then": {"required": ["reason"]}
    }
  ]
}
```

Keep JSON syntax valid by adding commas around the new definition and property as needed.

- [ ] **Step 5: Run model tests and schema smoke**

Run:

```bash
uv run --frozen pytest science/model/tests/test_dataset_models.py -k "benchmark_task_support or benchmark_block" -v
```

Expected: PASS.

Run:

```bash
uv run --frozen pytest science/model/tests/test_dataset_models.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add science/model/src/science_model/packages/schema.py science/model/src/science_model/schemas/mixin-dataset-1.0.json science/model/tests/test_dataset_models.py
git commit -m "feat: add benchmark task support schema"
```

## Task 2: Raw Frontmatter Parser and Benchmark Tests Projection

**Files:**
- Modify: `science/src/science_tool/benchmark_opportunities.py`
- Test: `science/tests/test_benchmark_cli.py`

- [ ] **Step 1: Add failing CLI/report tests**

Add these tests near the existing `test_benchmark_tests_cli_json_output` tests in `science/tests/test_benchmark_cli.py`:

```python
def test_benchmark_tests_cli_projects_task_support_fields(tmp_path: Path) -> None:
    _write_entity(
        tmp_path,
        "hypotheses",
        "0301-progression",
        """
id: hypothesis:0301-progression
type: hypothesis
title: Progression benchmark hypothesis
""",
        body="Progression risk should be benchmarked in multiple myeloma.",
    )
    _write_dataset(
        tmp_path,
        "mmrf-commpass",
        """
id: dataset:mmrf-commpass
type: dataset
title: MMRF CoMMpass
dataset_class: pointer
benchmark:
  domains: [biology]
  modalities: [bulk-rna-seq]
  signal_types: [time-series]
  benchmark_kinds: [survival-prediction]
  tasks:
    - id: progression-risk
      task_type: survival prediction
      prediction_target: progression or relapse
      held_out_unit: patient
      metric: concordance-index
      baseline: clinical covariates
      ground_truth:
        type: clinical-endpoint
        description: progression-free survival endpoint
      support:
        state: blocked
        reason: open-metadata-missing-progression-endpoint
        checked_at: '2026-07-02'
        evidence:
          - recipe/reports/validation.json#task_support.progression-risk
        notes:
          - Open metadata lacks progression endpoint coverage.
""",
    )

    result = _invoke_tests(tmp_path, "--format", "json")

    assert result.exit_code == 0
    payload = json.loads(result.output)
    row = payload["benchmark_tests"][0]
    assert row["benchmark_id"] == "dataset:mmrf-commpass"
    assert row["task_id"] == "dataset:mmrf-commpass#progression-risk"
    assert row["readiness_label"] == "metadata-only"
    assert row["task_support_state"] == "blocked"
    assert row["task_support_reason"] == "open-metadata-missing-progression-endpoint"
    assert row["task_support_checked_at"] == "2026-07-02"
    assert row["task_support_evidence"] == ["recipe/reports/validation.json#task_support.progression-risk"]
    assert row["task_support_notes"] == ["Open metadata lacks progression endpoint coverage."]
    assert "task-support:blocked:open-metadata-missing-progression-endpoint" in row["reason_notes"]
    assert "task-support:blocked:open-metadata-missing-progression-endpoint" not in row["needs"]


def test_benchmark_tests_cli_rejects_invalid_task_support_state(tmp_path: Path) -> None:
    _write_entity(
        tmp_path,
        "hypotheses",
        "0302-progression",
        """
id: hypothesis:0302-progression
type: hypothesis
title: Progression benchmark hypothesis
""",
        body="Progression risk should be benchmarked.",
    )
    _write_dataset(
        tmp_path,
        "bad-support",
        """
id: dataset:bad-support
type: dataset
title: Bad Support
dataset_class: pointer
benchmark:
  domains: [biology]
  modalities: [bulk-rna-seq]
  signal_types: [time-series]
  benchmark_kinds: [survival-prediction]
  tasks:
    - id: progression-risk
      prediction_target: progression or relapse
      held_out_unit: patient
      metric: concordance-index
      baseline: clinical covariates
      ground_truth:
        type: clinical-endpoint
        description: progression endpoint
      support:
        state: blockd
        reason: open-metadata-missing-progression-endpoint
""",
    )

    result = _invoke_tests(tmp_path, "--format", "json")

    assert result.exit_code != 0
    assert "benchmark task support state" in result.output
    assert "blockd" in result.output
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
uv run --frozen pytest science/tests/test_benchmark_cli.py -k "task_support" -v
```

Expected: the projection test fails because support fields are missing, and the invalid state test fails because invalid support is silently ignored or not surfaced.

- [ ] **Step 3: Add report-local support types**

In `science/src/science_tool/benchmark_opportunities.py`, add these definitions near `OpportunityTask`:

```python
TaskSupportState = Literal["supported", "candidate", "blocked"]


@dataclass(frozen=True)
class OpportunityTaskSupport:
    state: TaskSupportState
    reason: str
    checked_at: str
    evidence: list[str]
    notes: list[str]
```

Add `support: OpportunityTaskSupport | None` to `OpportunityTask`.

Add these fields to `BenchmarkTestRow`:

```python
    task_support_state: str
    task_support_reason: str
    task_support_checked_at: str
    task_support_evidence: list[str]
    task_support_notes: list[str]
```

- [ ] **Step 4: Add strict raw support parser**

Add these helpers before `_task_from_mapping`:

```python
_TASK_SUPPORT_STATES: set[str] = {"supported", "candidate", "blocked"}
_TASK_SUPPORT_REASON_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_TASK_SUPPORT_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _task_support_from_mapping(dataset_id: str, task_id: str, value: object) -> OpportunityTaskSupport | None:
    if value is None:
        return None
    if not isinstance(value, Mapping):
        raise ValueError(f"{dataset_id}#{task_id}: benchmark task support must be a mapping")

    state = value.get("state")
    if not isinstance(state, str) or state not in _TASK_SUPPORT_STATES:
        raise ValueError(f"{dataset_id}#{task_id}: benchmark task support state {state!r} is invalid")

    reason = str(value.get("reason") or "")
    if state in {"candidate", "blocked"} and not reason:
        raise ValueError(f"{dataset_id}#{task_id}: benchmark task support reason is required for {state}")
    if reason and _TASK_SUPPORT_REASON_RE.fullmatch(reason) is None:
        raise ValueError(f"{dataset_id}#{task_id}: benchmark task support reason must be lowercase kebab-case")

    checked_at = str(value.get("checked_at") or "")
    if checked_at and _TASK_SUPPORT_DATE_RE.fullmatch(checked_at) is None:
        raise ValueError(f"{dataset_id}#{task_id}: benchmark task support checked_at must be YYYY-MM-DD")

    return OpportunityTaskSupport(
        state=cast("TaskSupportState", state),
        reason=reason,
        checked_at=checked_at,
        evidence=_string_list(value.get("evidence")),
        notes=_string_list(value.get("notes")),
    )
```

If `re` or `cast` are not already imported, add them to the imports.

- [ ] **Step 5: Thread support through tasks and rows**

In `_task_from_mapping`, after validating `task_id`, call:

```python
    support = _task_support_from_mapping(dataset_id, task_id, task.get("support"))
```

Pass `support=support` into the `OpportunityTask(...)` constructor.

Add this helper near `_ground_truth_payload`:

```python
def _task_support_reason_notes(task: OpportunityTask | None) -> list[str]:
    if task is None or task.support is None or not task.support.reason:
        return []
    if task.support.state == "blocked":
        return [f"task-support:blocked:{task.support.reason}"]
    if task.support.state == "candidate":
        return [f"task-support:candidate:{task.support.reason}"]
    return []
```

In `_benchmark_test_row`, before sorting reason notes, combine authored notes:

```python
    reason_notes.extend(_task_support_reason_notes(task))
```

Add these fields to the returned row:

```python
        "task_support_state": task.support.state if task is not None and task.support is not None else "",
        "task_support_reason": task.support.reason if task is not None and task.support is not None else "",
        "task_support_checked_at": task.support.checked_at if task is not None and task.support is not None else "",
        "task_support_evidence": list(task.support.evidence) if task is not None and task.support is not None else [],
        "task_support_notes": list(task.support.notes) if task is not None and task.support is not None else [],
```

Do not add support reason notes to `_task_needs`; `needs` remains only missing test-plan metadata.

- [ ] **Step 6: Run focused tests**

Run:

```bash
uv run --frozen pytest science/tests/test_benchmark_cli.py -k "task_support" -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add science/src/science_tool/benchmark_opportunities.py science/tests/test_benchmark_cli.py
git commit -m "feat: project benchmark task support in reports"
```

## Task 3: Triage Routing for Blocked and Candidate Support

**Files:**
- Modify: `science/src/science_tool/benchmark_opportunities.py`
- Test: `science/tests/test_benchmark_cli.py`

- [ ] **Step 1: Add failing triage tests**

Add these tests near the existing benchmark test triage tests in `science/tests/test_benchmark_cli.py`:

```python
def test_benchmark_test_triage_routes_blocked_task_support_to_blocked_bucket(tmp_path: Path) -> None:
    _write_entity(
        tmp_path,
        "hypotheses",
        "0303-progression",
        """
id: hypothesis:0303-progression
type: hypothesis
title: Progression benchmark hypothesis
""",
        body="Progression risk should be benchmarked with survival data.",
    )
    _write_dataset(
        tmp_path,
        "blocked-progress",
        """
id: dataset:blocked-progress
type: dataset
title: Blocked Progression
dataset_class: deposit
local_path: data/blocked-progress
benchmark:
  domains: [biology]
  modalities: [bulk-rna-seq]
  signal_types: [time-series]
  benchmark_kinds: [survival-prediction]
  tasks:
    - id: progression-risk
      task_type: survival prediction
      prediction_target: progression or relapse
      held_out_unit: patient
      metric: concordance-index
      baseline: clinical covariates
      ground_truth:
        type: clinical-endpoint
        description: progression endpoint
      support:
        state: blocked
        reason: open-metadata-missing-progression-endpoint
        checked_at: '2026-07-02'
""",
    )

    result = _invoke_test_triage(tmp_path, "--format", "json")

    assert result.exit_code == 0
    payload = json.loads(result.output)
    row = payload["buckets"]["blocked-or-reference"][0]
    assert row["benchmark_id"] == "dataset:blocked-progress"
    assert row["readiness_label"] == "runnable"
    assert row["task_support_state"] == "blocked"
    assert "task-support:blocked:open-metadata-missing-progression-endpoint" in row["reason_notes"]
    assert payload["summary"]["bucket_counts"]["run-now"] == 0


def test_benchmark_test_triage_candidate_support_does_not_enter_run_now(tmp_path: Path) -> None:
    _write_entity(
        tmp_path,
        "hypotheses",
        "0304-survival",
        """
id: hypothesis:0304-survival
type: hypothesis
title: Survival benchmark hypothesis
""",
        body="Overall survival should be benchmarked with expression data.",
    )
    _write_dataset(
        tmp_path,
        "candidate-survival",
        """
id: dataset:candidate-survival
type: dataset
title: Candidate Survival
dataset_class: deposit
local_path: data/candidate-survival
benchmark:
  domains: [biology]
  modalities: [bulk-rna-seq]
  signal_types: [time-series]
  benchmark_kinds: [survival-prediction]
  tasks:
    - id: overall-survival
      task_type: survival prediction
      prediction_target: overall survival
      held_out_unit: patient
      metric: concordance-index
      baseline: clinical covariates
      ground_truth:
        type: clinical-endpoint
        description: overall survival endpoint
      support:
        state: candidate
        reason: open-metadata-survival-endpoint-present
        checked_at: '2026-07-02'
""",
    )

    result = _invoke_test_triage(tmp_path, "--format", "json")

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["summary"]["bucket_counts"]["run-now"] == 0
    row = payload["buckets"]["metadata-needed"][0]
    assert row["benchmark_id"] == "dataset:candidate-survival"
    assert row["readiness_label"] == "runnable"
    assert row["test_plan_state"] == "concrete"
    assert row["task_support_state"] == "candidate"
    assert "task-support:candidate:open-metadata-survival-endpoint-present" in row["reason_notes"]
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
uv run --frozen pytest science/tests/test_benchmark_cli.py -k "triage and support" -v
```

Expected: the blocked row initially appears in `run-now`, and the candidate concrete runnable row initially appears in `run-now`.

- [ ] **Step 3: Implement support-state triage branches**

Modify `_benchmark_test_triage_bucket` in `science/src/science_tool/benchmark_opportunities.py` so the support state is checked after fallback and before the current readiness/test-plan rules:

```python
def _benchmark_test_triage_bucket(row: BenchmarkTestRow) -> BenchmarkTestTriageBucket:
    if row["priority_source"] == "gap-fallback":
        return "fallback-diagnostic"

    if row["task_support_state"] == "blocked":
        return "blocked-or-reference"

    if row["task_support_state"] == "candidate":
        if row["readiness_label"] == "stage-needed":
            return "stage-next"
        if row["readiness_label"] == "runnable":
            return "metadata-needed"
        return "blocked-or-reference"

    if row["test_plan_state"] == "concrete" and row["readiness_label"] == "runnable":
        return "run-now"
    if row["readiness_label"] == "stage-needed":
        return "stage-next"
    if row["test_plan_state"] == "draft-needed" and row["readiness_label"] != "blocked":
        return "metadata-needed"
    if row["readiness_label"] in {"metadata-only", "blocked"}:
        return "blocked-or-reference"
    raise ValueError(f"unable to classify benchmark test row: {row['entity_id']} {row['benchmark_id']}")
```

This preserves `readiness_label` as dataset access/runtime state.

- [ ] **Step 4: Run focused triage tests**

Run:

```bash
uv run --frozen pytest science/tests/test_benchmark_cli.py -k "triage and support" -v
```

Expected: PASS.

- [ ] **Step 5: Run broader benchmark CLI tests**

Run:

```bash
uv run --frozen pytest science/tests/test_benchmark_cli.py -k "benchmark_tests or benchmark_test_triage" -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/benchmark_opportunities.py science/tests/test_benchmark_cli.py
git commit -m "feat: route benchmark task support in triage"
```

## Task 4: Benchmark Metadata Validation

**Files:**
- Modify: `science/src/science_tool/validate/checks/benchmark_metadata.py`
- Test: `science/tests/validate/test_checks_benchmark_metadata.py`

- [ ] **Step 1: Add failing validation tests**

Add these tests after the existing task id tests in `science/tests/validate/test_checks_benchmark_metadata.py`:

```python
def test_task_support_invalid_state_is_error() -> None:
    results = _results(
        [
            _ds(
                benchmark={
                    "tasks": [
                        {
                            "id": "progression-risk",
                            "support": {
                                "state": "blockd",
                                "reason": "open-metadata-missing-progression-endpoint",
                            },
                        }
                    ]
                }
            )
        ]
    )

    assert any(
        result.severity is Severity.ERROR
        and result.rule == "benchmark.task-support-state-invalid"
        and "blockd" in result.message
        for result in results
    )


def test_task_support_candidate_and_blocked_require_reason() -> None:
    rules = _rules(
        [
            _ds(
                benchmark={
                    "tasks": [
                        {"id": "overall-survival", "support": {"state": "candidate"}},
                        {"id": "progression-risk", "support": {"state": "blocked"}},
                    ]
                }
            )
        ]
    )

    assert rules.count((Severity.ERROR, "benchmark.task-support-reason-required")) == 2


def test_task_support_reason_must_be_lowercase_kebab_case() -> None:
    results = _results(
        [
            _ds(
                benchmark={
                    "tasks": [
                        {
                            "id": "progression-risk",
                            "support": {
                                "state": "blocked",
                                "reason": "Missing Endpoint",
                            },
                        }
                    ]
                }
            )
        ]
    )

    assert any(
        result.severity is Severity.ERROR
        and result.rule == "benchmark.task-support-reason-invalid"
        and "lowercase kebab-case" in result.message
        for result in results
    )


def test_task_support_checked_at_must_be_iso_date() -> None:
    rules = _rules(
        [
            _ds(
                benchmark={
                    "tasks": [
                        {
                            "id": "progression-risk",
                            "support": {
                                "state": "blocked",
                                "reason": "open-metadata-missing-progression-endpoint",
                                "checked_at": "07/02/2026",
                            },
                        }
                    ]
                }
            )
        ]
    )

    assert (Severity.ERROR, "benchmark.task-support-checked-at-invalid") in rules
```

- [ ] **Step 2: Run tests and verify they fail**

Run:

```bash
uv run --frozen pytest science/tests/validate/test_checks_benchmark_metadata.py -k "task_support" -v
```

Expected: FAIL because the new validation rules do not exist.

- [ ] **Step 3: Add validation helpers**

In `science/src/science_tool/validate/checks/benchmark_metadata.py`, add module constants near `_TASK_ID_RE`:

```python
_TASK_SUPPORT_STATES = {"supported", "candidate", "blocked"}
_TASK_SUPPORT_REASON_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_TASK_SUPPORT_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
```

Add this helper after `_task_mappings`:

```python
def _task_support_mapping(task: Mapping[str, Any]) -> Mapping[str, Any] | None:
    support = task.get("support")
    if support is None:
        return None
    if isinstance(support, Mapping):
        return support
    return {}
```

- [ ] **Step 4: Add validation rules**

Inside `for task in valid_tasks:`, before the sparse task warning, add:

```python
            support = _task_support_mapping(task)
            if support is not None:
                state = support.get("state")
                task_id = task["id"]
                if not isinstance(state, str) or state not in _TASK_SUPPORT_STATES:
                    yield _result(
                        Severity.ERROR,
                        path,
                        f"{ident}: benchmark task {task_id!r} support state {state!r} is invalid",
                        "benchmark.task-support-state-invalid",
                    )
                    continue

                reason = support.get("reason")
                has_reason = _nonempty_str(reason)
                if state in {"candidate", "blocked"} and not has_reason:
                    yield _result(
                        Severity.ERROR,
                        path,
                        f"{ident}: benchmark task {task_id!r} support reason is required for state {state!r}",
                        "benchmark.task-support-reason-required",
                    )
                if has_reason and _TASK_SUPPORT_REASON_RE.fullmatch(str(reason)) is None:
                    yield _result(
                        Severity.ERROR,
                        path,
                        f"{ident}: benchmark task {task_id!r} support reason must be lowercase kebab-case",
                        "benchmark.task-support-reason-invalid",
                    )

                checked_at = support.get("checked_at")
                if _nonempty_str(checked_at) and _TASK_SUPPORT_DATE_RE.fullmatch(str(checked_at)) is None:
                    yield _result(
                        Severity.ERROR,
                        path,
                        f"{ident}: benchmark task {task_id!r} support checked_at must be YYYY-MM-DD",
                        "benchmark.task-support-checked-at-invalid",
                    )
```

This intentionally treats a non-mapping `support` as an invalid state diagnostic rather than ignoring it.

- [ ] **Step 5: Run validation tests**

Run:

```bash
uv run --frozen pytest science/tests/validate/test_checks_benchmark_metadata.py -k "task_support or benchmark_metadata" -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add science/src/science_tool/validate/checks/benchmark_metadata.py science/tests/validate/test_checks_benchmark_metadata.py
git commit -m "feat: validate benchmark task support metadata"
```

## Task 5: MMRF Commons Metadata

**Files:**
- Modify: `~/d/science-commons/datasets/mmrf-commpass/entity.md`

- [ ] **Step 1: Inspect current MMRF entity and commons status**

Run:

```bash
rtk git -C ~/d/science-commons status --short
```

Expected: either clean or only unrelated known changes. Do not edit if the target file has unexpected uncommitted changes.

Run:

```bash
rtk sed -n '1,220p' ~/d/science-commons/datasets/mmrf-commpass/entity.md
```

Expected: the entity has `dataset_class: pointer` and a `benchmark.tasks` entry for `progression-risk`.

- [ ] **Step 2: Edit `progression-risk` support metadata**

Under the `progression-risk` task in `~/d/science-commons/datasets/mmrf-commpass/entity.md`, add:

```yaml
      support:
        state: blocked
        reason: open-metadata-missing-progression-endpoint
        checked_at: "2026-07-02"
        evidence:
          - recipe/reports/validation.json#task_support.progression-risk
        notes:
          - Open GDC metadata currently exposes survival endpoints but not usable progression or relapse endpoints for this task.
```

Keep `dataset_class: pointer`; do not add a staged `datapackage` or access artifact in this slice.

- [ ] **Step 3: Add `overall-survival` only if the entity already has clear task text**

If the existing entity description already discusses overall survival as a distinct benchmark, add a second task:

```yaml
    - id: overall-survival
      task_type: survival prediction
      prediction_target: overall survival
      held_out_unit: patient
      metric: concordance-index
      baseline: clinical covariates
      ground_truth:
        type: clinical-endpoint
        description: overall survival endpoint from open clinical metadata
      support:
        state: candidate
        reason: open-metadata-survival-endpoint-present
        checked_at: "2026-07-02"
        evidence:
          - recipe/reports/validation.json#task_support.overall-survival
        notes:
          - This is a distinct survival task and does not satisfy progression-risk.
```

If the existing entity does not already describe overall survival, do not add this task in this plan. Leave the task for a future authored metadata update.

- [ ] **Step 4: Validate commons entity with local science command**

Run from the science repo worktree:

```bash
uv run --frozen science validate --project-root ~/d/science-commons --format json
```

Expected: command exits 0 or reports only pre-existing unrelated validation findings. There must be no `benchmark.task-support-*` errors for `dataset:mmrf-commpass`.

- [ ] **Step 5: Commit commons metadata**

Run:

```bash
rtk git -C ~/d/science-commons add datasets/mmrf-commpass/entity.md
rtk git -C ~/d/science-commons commit -m "docs: add mmrf benchmark task support metadata"
```

Expected: a commons commit is created. Do not include generated recipe artifacts or staged data.

## Task 6: Integration Verification and Calibration Smoke

**Files:**
- No expected source edits.

- [ ] **Step 1: Run focused test suites**

Run:

```bash
uv run --frozen pytest science/model/tests/test_dataset_models.py science/tests/test_benchmark_cli.py science/tests/validate/test_checks_benchmark_metadata.py -k "benchmark_task_support or task_support or benchmark_tests or benchmark_test_triage or benchmark_metadata" -v
```

Expected: PASS.

- [ ] **Step 2: Run lint/type checks for touched Python files**

Run:

```bash
uv run --frozen ruff check science/model/src/science_model/packages/schema.py science/src/science_tool/benchmark_opportunities.py science/src/science_tool/validate/checks/benchmark_metadata.py science/model/tests/test_dataset_models.py science/tests/test_benchmark_cli.py science/tests/validate/test_checks_benchmark_metadata.py
```

Expected: PASS.

- [ ] **Step 3: Inspect MMRF benchmark tests JSON**

Run:

```bash
uv run --frozen science benchmark tests --project-root ~/d/cancer/cancer-types/multiple-myeloma --commons --benchmark mmrf-commpass --format json
```

Expected:
- Rows for `dataset:mmrf-commpass#progression-risk` include `task_support_state: "blocked"`.
- Rows preserve dataset-level `readiness_label` rather than replacing it with task support.
- `reason_notes` includes `task-support:blocked:open-metadata-missing-progression-endpoint`.

- [ ] **Step 4: Inspect MMRF benchmark triage JSON**

Run:

```bash
uv run --frozen science benchmark test-triage --project-root ~/d/cancer/cancer-types/multiple-myeloma --commons --benchmark mmrf-commpass --format json
```

Expected:
- Non-fallback `progression-risk` rows appear under `blocked-or-reference`.
- They include structured task-support fields and the support reason note.
- Candidate `overall-survival` rows, if authored in Task 5, do not appear under `run-now`.

- [ ] **Step 5: Commit science repo changes**

Run:

```bash
git status --short
```

Expected: only intentional science repo files are changed; unrelated untracked files such as `docs/plans/2026-07-02-bio-identity-adoption-layer-*.md` remain uncommitted unless explicitly requested.

Run:

```bash
git add science/model/src/science_model/packages/schema.py science/model/src/science_model/schemas/mixin-dataset-1.0.json science/model/tests/test_dataset_models.py science/src/science_tool/benchmark_opportunities.py science/src/science_tool/validate/checks/benchmark_metadata.py science/tests/test_benchmark_cli.py science/tests/validate/test_checks_benchmark_metadata.py
git commit -m "feat: add benchmark task support reporting"
```

Expected: if earlier task commits were already made, this final commit may have nothing to commit. Do not amend earlier commits unless the branch workflow requires squashing.

## Self-Review

- **Spec coverage:** The plan covers the schema, raw report parser, additive report fields, triage behavior, validation diagnostics, and MMRF metadata application. It explicitly keeps `readiness_label` as dataset readiness and avoids reading local recipe artifacts.
- **Placeholder scan:** The plan contains no placeholder steps, no open-ended "handle errors" step, and no unnamed test instructions. Task 5 has an explicit branch for `overall-survival`: add it only when the existing entity already describes it; otherwise leave it out.
- **Type consistency:** `OpportunityTaskSupport`, `task_support_*` row keys, and triage support-state checks use the same state values: `supported`, `candidate`, and `blocked`.

## Execution Handoff

Plan complete and saved to `docs/plans/2026-07-02-benchmark-task-support-metadata-implementation-plan.md`.

Two execution options:

1. **Subagent-Driven (recommended)** - dispatch a fresh subagent per task, review between tasks, fast iteration.
2. **Inline Execution** - execute tasks in this session using executing-plans, batch execution with checkpoints.

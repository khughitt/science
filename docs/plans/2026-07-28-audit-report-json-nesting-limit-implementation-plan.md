# Audit Report JSON Nesting Limit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make pathological audit-report JSON nesting fail with the same parse error on every supported Python version.

**Architecture:** Keep the standard JSON decoder and existing exception wrapping. After a successful decode, traverse dictionaries and lists iteratively, counting the top-level container as depth one and rejecting depth greater than 100 before top-level type or Pydantic validation.

**Tech Stack:** Python 3.13/3.14, standard-library `json`, Pydantic, pytest.

## Global Constraints

- Preserve the existing 8 MiB report-size limit and `IngestError("could not parse ...")` error category.
- `MAX_REPORT_NESTING = 100`; the top-level JSON container has depth one.
- The depth check must be iterative and must inspect dictionary values and list elements.
- Do not add a custom JSON decoder, lexical pre-scan, compatibility layer, or dependency.

---

### Task 1: Enforce the report nesting boundary

**Files:**
- Modify: `science/src/science_tool/findings/ingest.py:57-160`
- Test: `science/tests/test_findings_ingest.py:1467-1483`

**Interfaces:**
- Consumes: parsed JSON values returned by `json.loads(text)`.
- Produces: `MAX_REPORT_NESTING: int = 100` and `_require_bounded_json_nesting(value: object, path: Path) -> None`.

- [ ] **Step 1: Write the failing cross-version and boundary tests**

Retain the 10,000-array regression input and add an independent literal oracle,
helpers, and exact-boundary tests:

```python
EXPECTED_MAX_REPORT_NESTING = 100


def _nested_list(depth: int) -> object:
    value: object = 0
    for _ in range(depth):
        value = [value]
    return value


def _report_with_metric_nesting(depth: int) -> dict:
    report = _report(
        metrics={
            "dataset_anomalies": {
                "nested": _nested_list(depth),
            }
        }
    )
    return report.model_dump(mode="json")


def test_load_report_wraps_a_deep_nesting_parse_error(tmp_path):
    path = tmp_path / "report.json"
    path.write_text(("[" * 10000) + "0" + ("]" * 10000), encoding="utf-8")

    with pytest.raises(IngestError, match="could not parse.*excessive nesting"):
        load_report(tmp_path, path)


def test_load_report_accepts_the_maximum_json_nesting(tmp_path):
    path = tmp_path / "report.json"
    # root object + metrics object + producer object consume three levels.
    path.write_text(
        json.dumps(_report_with_metric_nesting(EXPECTED_MAX_REPORT_NESTING - 3)),
        encoding="utf-8",
    )

    assert load_report(tmp_path, path).schema_version == 2


def test_load_report_refuses_one_level_beyond_maximum_json_nesting(tmp_path):
    path = tmp_path / "report.json"
    path.write_text(
        json.dumps(_report_with_metric_nesting(EXPECTED_MAX_REPORT_NESTING - 2)),
        encoding="utf-8",
    )

    with pytest.raises(IngestError, match="could not parse.*excessive nesting"):
        load_report(tmp_path, path)
```

- [ ] **Step 2: Run the tests on Python 3.14 and verify red**

Run:

```bash
(cd science && uv run --frozen pytest -q \
  tests/test_findings_ingest.py::test_load_report_wraps_a_deep_nesting_parse_error \
  tests/test_findings_ingest.py::test_load_report_accepts_the_maximum_json_nesting \
  tests/test_findings_ingest.py::test_load_report_refuses_one_level_beyond_maximum_json_nesting)
```

Expected: the deep input reports `is not a JSON object`; the one-level-beyond test does not raise. The exact-limit control passes.

- [ ] **Step 3: Implement the iterative depth check**

Add beside `MAX_REPORT_BYTES`:

```python
MAX_REPORT_NESTING = 100
```

Add before `load_report`:

```python
def _require_bounded_json_nesting(value: object, path: Path) -> None:
    stack: list[tuple[object, int]] = [(value, 0)]
    while stack:
        current, parent_depth = stack.pop()
        if isinstance(current, dict):
            children = current.values()
        elif isinstance(current, list):
            children = current
        else:
            continue

        depth = parent_depth + 1
        if depth > MAX_REPORT_NESTING:
            raise IngestError(
                f"could not parse {path}: excessive nesting exceeds "
                f"{MAX_REPORT_NESTING}"
            )
        stack.extend((child, depth) for child in children)
```

Call it immediately after the decoder exception block and before the top-level dictionary check:

```python
    _require_bounded_json_nesting(raw, path)
    if not isinstance(raw, dict):
```

Update the decoder comment so it says `RecursionError` is decoder-version-dependent and the explicit post-decode check enforces the portable limit.

- [ ] **Step 4: Run the focused tests and verify green**

Run the Step 2 command.

Expected: 3 passed on Python 3.14.

Run the same selection with the preserved Python 3.13 environment:

```bash
(cd science && \
  TMPDIR=/var/tmp/schema-closure-final-pytest \
  SCIENCE_TEST_TMPDIR=/var/tmp/schema-closure-final-pytest \
  ../.worktrees/schema-closure-tranche/science/.venv/bin/python -m pytest -q \
  tests/test_findings_ingest.py::test_load_report_wraps_a_deep_nesting_parse_error \
  tests/test_findings_ingest.py::test_load_report_accepts_the_maximum_json_nesting \
  tests/test_findings_ingest.py::test_load_report_refuses_one_level_beyond_maximum_json_nesting)
```

Expected: 3 passed on Python 3.13.

- [ ] **Step 5: Run package verification**

Run sequentially:

```bash
(cd science/model && uv run --frozen pytest -q)
(cd science && uv run --frozen pytest -q)
(cd science && uv run ruff check)
(cd science && uv run pyright)
git diff --check
```

Expected: all commands exit zero. Use `/var/tmp/schema-closure-final-pytest` for the CLI/tool suite so the managed sandbox's synthetic `/tmp/.git` does not contaminate boundary tests.

- [ ] **Step 6: Commit**

```bash
git add \
  science/src/science_tool/findings/ingest.py \
  science/tests/test_findings_ingest.py
git commit -m "fix(findings): enforce a portable JSON nesting limit"
```

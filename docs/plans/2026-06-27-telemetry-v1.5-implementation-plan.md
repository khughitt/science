# Telemetry v1.5 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add validation-summary telemetry and feedback triage telemetry context while preserving correct Click exit semantics.

**Architecture:** Keep storage and aggregation in `science_tool.telemetry`, use `science_tool.validate.cli` as the boundary that converts `RunResult` into a validation-summary event, and keep feedback triage enrichment in `science_tool.feedback` with CLI wiring in `science_tool.cli`. Telemetry remains local, aggregate-only, and best-effort.

**Tech Stack:** Python 3.13, Click, pytest/CliRunner, JSONL telemetry files, existing `emit_query_rows` output conventions.

---

## File Structure

- Modify `science/src/science_tool/cli.py`
  - Restore non-zero Click exit behavior in `TelemetryGroup.main`.
  - Add `--with-telemetry` to `feedback triage` and render telemetry columns/JSON.
- Modify `science/src/science_tool/telemetry.py`
  - Add validation summary event helper functions.
  - Add recent telemetry filtering and triage summary helpers.
- Modify `science/src/science_tool/validate/cli.py`
  - Append a `validation_summary` event after `run()` returns and before `ctx.exit(1)`.
- Modify `science/src/science_tool/feedback.py`
  - Add functions that attach telemetry summaries to existing triage rows/groups.
- Modify `science/tests/test_telemetry.py`
  - Unit tests for validation-summary event creation and telemetry triage summaries.
- Modify `science/tests/test_telemetry_cli.py`
  - Regression test for non-zero exit preservation under telemetry instrumentation.
- Modify `science/tests/validate/test_validate_cli.py`
  - CLI tests that validation-summary events are emitted for pass/warn/fail and omit raw rows.
- Modify `science/tests/test_feedback_cli.py`
  - CLI tests for `feedback triage --with-telemetry` JSON/table output.

## Task 1: Restore Click Exit Semantics

**Files:**
- Modify: `science/src/science_tool/cli.py`
- Test: `science/tests/test_telemetry_cli.py`
- Existing regression coverage: `science/tests/validate/test_validate_cli.py`

- [ ] **Step 1: Write a focused failing telemetry regression test**

Add this test to `science/tests/test_telemetry_cli.py`:

```python
def test_telemetry_group_preserves_nonzero_ctx_exit(tmp_path: Path) -> None:
    telemetry_dir = tmp_path / "telemetry"
    result = CliRunner().invoke(
        main,
        ["validate", "--project-root", str(tmp_path)],
        env={"SCIENCE_TELEMETRY_DIR": str(telemetry_dir)},
    )

    assert result.exit_code != 0
    assert "science.yaml not found" in result.output
```

- [ ] **Step 2: Run red check**

Run:

```bash
SCIENCE_TEST_TMPDIR=/tmp/science-pytest-tmp rtk uv run --frozen pytest tests/test_telemetry_cli.py::test_telemetry_group_preserves_nonzero_ctx_exit -q
```

Expected: FAIL with `assert 0 != 0`.

- [ ] **Step 3: Implement the exit-code fix**

In `TelemetryGroup.main`, capture the return from the existing `super().main(*args, standalone_mode=False, **kwargs)` call. If it is a non-zero integer, preserve normal Click process semantics:

```python
result = super().main(*args, standalone_mode=False, **kwargs)
if isinstance(result, int) and result != 0 and standalone_mode:
    raise SystemExit(result)
return result
```

When `standalone_mode` is false, return the integer unchanged so programmatic callers keep Click's non-standalone behavior.

- [ ] **Step 4: Run regression and existing validate tests**

Run:

```bash
SCIENCE_TEST_TMPDIR=/tmp/science-pytest-tmp rtk uv run --frozen pytest tests/test_telemetry_cli.py::test_telemetry_group_preserves_nonzero_ctx_exit tests/validate/test_validate_cli.py::test_validate_exits_nonzero_when_errors_exist tests/validate/test_validate_cli.py::test_fail_on_ghost_files_exits_nonzero -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
rtk git add science/src/science_tool/cli.py science/tests/test_telemetry_cli.py
rtk git commit -m "fix(telemetry): preserve click exit codes"
```

## Task 2: Validation Summary Event Model

**Files:**
- Modify: `science/src/science_tool/telemetry.py`
- Test: `science/tests/test_telemetry.py`

- [ ] **Step 1: Write failing unit tests for validation-summary helpers**

Add tests that construct simple validation-like records and expect:

```python
event = new_validation_summary_event(
    command="validate",
    profile="full",
    strict=False,
    fail_on=None,
    errors=1,
    warnings=2,
    infos=3,
    gated=True,
    rule_ids=["demo.error", "demo.warn", "demo.warn", None],
)
```

The test should assert:

```python
assert event["surface"] == "validation"
assert event["event_type"] == "validation_summary"
assert event["status"] == "fail"
assert event["counts"] == {"error": 1, "warn": 2, "info": 3}
assert event["top_checks"] == [{"check": "demo.warn", "count": 2}, {"check": "demo.error", "count": 1}]
assert "path" not in event
assert "message" not in event
```

Also add separate tests for `status == "warn"` and `status == "pass"`.

- [ ] **Step 2: Run red check**

Run:

```bash
SCIENCE_TEST_TMPDIR=/tmp/science-pytest-tmp rtk uv run --frozen pytest tests/test_telemetry.py -q
```

Expected: FAIL because `new_validation_summary_event` does not exist.

- [ ] **Step 3: Implement validation-summary helpers**

Add to `science/src/science_tool/telemetry.py`:

```python
def new_validation_summary_event(
    *,
    command: str,
    profile: str,
    strict: bool,
    fail_on: str | None,
    errors: int,
    warnings: int,
    infos: int,
    gated: bool,
    rule_ids: Sequence[str | None],
) -> dict[str, object]:
    event = new_event(event_type="validation_summary", command=command, argv=())
    event["surface"] = "validation"
    event["profile"] = profile
    event["strict"] = strict
    event["fail_on"] = fail_on
    event["status"] = _validation_status(errors=errors, warnings=warnings, gated=gated)
    event["counts"] = {"error": errors, "warn": warnings, "info": infos}
    event["top_checks"] = _top_checks(rule_ids)
    return event
```

Use deterministic sorting in `_top_checks`: count descending, then rule ID ascending.

- [ ] **Step 4: Run unit tests**

Run:

```bash
SCIENCE_TEST_TMPDIR=/tmp/science-pytest-tmp rtk uv run --frozen pytest tests/test_telemetry.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
rtk git add science/src/science_tool/telemetry.py science/tests/test_telemetry.py
rtk git commit -m "feat(telemetry): model validation summary events"
```

## Task 3: Emit Validation Summary Events from `science validate`

**Files:**
- Modify: `science/src/science_tool/validate/cli.py`
- Test: `science/tests/validate/test_validate_cli.py`

- [ ] **Step 1: Write failing CLI tests for validation telemetry**

Add tests to `science/tests/validate/test_validate_cli.py`:

```python
from science_tool.telemetry import read_events
```

Test fail case:

```python
def test_validate_records_failure_summary_telemetry(tmp_path: Path) -> None:
    @Check(section="demo", order=10)
    def demo_check(ctx: ValidateContext) -> list[Result]:
        return [Result(Severity.ERROR, Path("secret/path.md"), 9, "private message", "demo.error", None)]

    telemetry_dir = tmp_path / "telemetry"
    result = CliRunner().invoke(
        main,
        ["validate", "--format", "json", "--project-root", str(_project(tmp_path / "project"))],
        env={"SCIENCE_TELEMETRY_DIR": str(telemetry_dir)},
    )

    assert result.exit_code == 1
    events = [event for event in read_events(telemetry_dir) if event.get("event_type") == "validation_summary"]
    assert len(events) == 1
    event = events[0]
    assert event["status"] == "fail"
    assert event["counts"] == {"error": 1, "warn": 0, "info": 0}
    assert event["top_checks"] == [{"check": "demo.error", "count": 1}]
    assert "secret/path.md" not in json.dumps(event)
    assert "private message" not in json.dumps(event)
```

Add one warning-only test expecting `status == "warn"` and one clean test expecting `status == "pass"`.

- [ ] **Step 2: Run red check**

Run:

```bash
SCIENCE_TEST_TMPDIR=/tmp/science-pytest-tmp rtk uv run --frozen pytest tests/validate/test_validate_cli.py::test_validate_records_failure_summary_telemetry -q
```

Expected: FAIL because no `validation_summary` event is recorded.

- [ ] **Step 3: Implement event emission in validate CLI**

In `science/src/science_tool/validate/cli.py`, after the validate command assigns the `run()` return value to `result` and before output/exit, call a small helper:

```python
def _record_validation_summary(
    *,
    result: RunResult,
    profile: str,
    strict: bool,
    fail_on: str | None,
) -> None:
    from science_tool.telemetry import append_event, get_telemetry_dir, new_validation_summary_event, telemetry_enabled

    if not telemetry_enabled():
        return
    event = new_validation_summary_event(
        command="validate",
        profile=profile,
        strict=strict,
        fail_on=fail_on,
        errors=result.errors,
        warnings=result.warnings,
        infos=result.infos,
        gated=bool(result.gated),
        rule_ids=[item.rule for item in result.results],
    )
    append_event(get_telemetry_dir(), event)
```

Use the user-provided `fail_on` value for the event; do not store project root.

- [ ] **Step 4: Run validate telemetry tests**

Run:

```bash
SCIENCE_TEST_TMPDIR=/tmp/science-pytest-tmp rtk uv run --frozen pytest tests/validate/test_validate_cli.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
rtk git add science/src/science_tool/validate/cli.py science/tests/validate/test_validate_cli.py
rtk git commit -m "feat(validate): record summary telemetry"
```

## Task 4: Feedback Triage Telemetry Summaries

**Files:**
- Modify: `science/src/science_tool/telemetry.py`
- Modify: `science/src/science_tool/feedback.py`
- Modify: `science/src/science_tool/cli.py`
- Test: `science/tests/test_telemetry.py`
- Test: `science/tests/test_feedback_cli.py`

- [ ] **Step 1: Write failing unit tests for triage telemetry aggregation**

In `science/tests/test_telemetry.py`, add a test for:

```python
summary = summarize_recent_for_feedback_target(
    events,
    target="command:validate",
    today=date(2026, 6, 27),
    since_days=14,
)
```

Use events containing:
- one `command_error` for `validate`;
- two `validation_summary` events for `validate`, one `warn`, one `fail`;
- one unrelated `feedback list` event.

Assert:

```python
assert summary["recent_events"] == 3
assert summary["command_errors"] == {"NoSuchOption": 1}
assert summary["commands"] == {"validate": 1}
assert summary["validation"]["runs"] == 2
assert summary["validation"]["statuses"] == {"fail": 1, "warn": 1}
assert summary["validation"]["top_checks"] == {"demo.warn": 2, "demo.error": 1}
```

- [ ] **Step 2: Run red unit check**

Run:

```bash
SCIENCE_TEST_TMPDIR=/tmp/science-pytest-tmp rtk uv run --frozen pytest tests/test_telemetry.py -q
```

Expected: FAIL because `summarize_recent_for_feedback_target` does not exist.

- [ ] **Step 3: Implement telemetry triage aggregation**

In `science/src/science_tool/telemetry.py`, add:

```python
def summarize_recent_for_feedback_target(
    events: Sequence[Mapping[str, object]],
    *,
    target: str,
    today: date | None = None,
    since_days: int = 14,
) -> dict[str, object]:
    cutoff = (today or date.today()) - timedelta(days=since_days)
    matching = [
        event for event in events
        if _event_date(event) is not None
        and _event_date(event) >= cutoff
        and _feedback_target_matches_event(target, event)
    ]
    return _summarize_feedback_events(matching)
```

Rules:
- include events newer than or equal to `today - since_days`;
- for `command:<name>`, include command events where first command token equals `<name>` or command equals `<name>`;
- for `command:validate`, include `validation_summary` events whose command is `validate`;
- for non-command targets, include all recent events but do not infer a command match;
- return empty counters when nothing matches.

Also add `format_feedback_telemetry(summary: Mapping[str, object]) -> str` returning `no recent telemetry` or compact text like `validate: 2 runs, 1 fail, 1 warn`.

- [ ] **Step 4: Add feedback/CLI wiring tests**

In `science/tests/test_feedback_cli.py`, add:

```python
def test_triage_cluster_json_can_include_telemetry_context(runner: CliRunner, tmp_path: Path) -> None:
    telemetry_dir = tmp_path / "telemetry"
    feedback_dir = tmp_path / "feedback"
    append_event(
        telemetry_dir,
        {
            "event_id": "v1",
            "timestamp": "2026-06-27T10:00:00-04:00",
            "event_type": "validation_summary",
            "surface": "validation",
            "command": "validate",
            "status": "warn",
            "counts": {"error": 0, "warn": 1, "info": 0},
            "top_checks": [{"check": "demo.warn", "count": 1}],
        },
    )
    runner.invoke(
        main,
        ["feedback", "add", "--target", "command:validate", "--summary", "Validation warnings are recurring"],
        env={"SCIENCE_FEEDBACK_DIR": str(feedback_dir), "SCIENCE_TELEMETRY_DIR": str(telemetry_dir)},
    )

    result = runner.invoke(
        main,
        ["feedback", "triage", "--cluster", "--with-telemetry", "--format", "json"],
        env={"SCIENCE_FEEDBACK_DIR": str(feedback_dir), "SCIENCE_TELEMETRY_DIR": str(telemetry_dir)},
    )

    payload = json.loads(result.output)
    assert payload["rows"][0]["telemetry"]["validation"]["runs"] == 1
```

Add one table test expecting the output to include `validate:` when `--with-telemetry` is used.

- [ ] **Step 5: Implement feedback triage enrichment**

In `science/src/science_tool/feedback.py`, add:

```python
def attach_telemetry_to_triage_rows(
    rows: list[dict[str, object]],
    *,
    events: list[dict[str, object]],
    since_days: int | None,
) -> list[dict[str, object]]:
    enriched: list[dict[str, object]] = []
    window = since_days if since_days is not None else 14
    for row in rows:
        copied = dict(row)
        copied["telemetry"] = summarize_recent_for_feedback_target(
            events,
            target=str(row.get("target") or ""),
            since_days=window,
        )
        enriched.append(copied)
    return enriched
```

This should copy each row and add `telemetry`.

In `science/src/science_tool/cli.py`, add:

```python
@click.option("--with-telemetry", is_flag=True, help="Include recent local telemetry context.")
```

to `feedback_triage`. When set:
- read local telemetry events;
- enrich cluster JSON rows before `emit_query_rows`;
- add a `("telemetry_text", "Telemetry")` column for table output and populate it with `format_feedback_telemetry(row["telemetry"])`.

- [ ] **Step 6: Run feedback triage tests**

Run:

```bash
SCIENCE_TEST_TMPDIR=/tmp/science-pytest-tmp rtk uv run --frozen pytest tests/test_telemetry.py tests/test_feedback_cli.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
rtk git add science/src/science_tool/telemetry.py science/src/science_tool/feedback.py science/src/science_tool/cli.py science/tests/test_telemetry.py science/tests/test_feedback_cli.py
rtk git commit -m "feat(feedback): show telemetry in triage"
```

## Task 5: Focused Verification

**Files:**
- All touched files.

- [ ] **Step 1: Run focused pytest suite**

Run:

```bash
SCIENCE_TEST_TMPDIR=/tmp/science-pytest-tmp rtk uv run --frozen pytest tests/test_telemetry.py tests/test_telemetry_cli.py tests/test_feedback.py tests/test_feedback_cli.py tests/validate/test_validate_cli.py -q
```

Expected: PASS.

- [ ] **Step 2: Run type and lint checks**

Run:

```bash
rtk uv run --frozen pyright src/science_tool/telemetry.py src/science_tool/validate/cli.py tests/test_telemetry.py tests/test_telemetry_cli.py tests/validate/test_validate_cli.py tests/test_feedback_cli.py
```

Expected: `0 errors, 0 warnings, 0 informations`.

Run:

```bash
rtk uv run --frozen ruff check src/science_tool/telemetry.py src/science_tool/cli.py src/science_tool/validate/cli.py src/science_tool/feedback.py tests/test_telemetry.py tests/test_telemetry_cli.py tests/validate/test_validate_cli.py tests/test_feedback_cli.py
```

Expected: `All checks passed!`

- [ ] **Step 3: Run CLI smoke test**

Run:

```bash
SCIENCE_TELEMETRY_DIR=/tmp/science-telemetry-v15-smoke rtk uv run --frozen science validate --format json --project-root .
```

Expected: exits non-zero if this repo root is not a Science project, or exits according to validation results; do not treat non-zero as failure by itself. Then run:

```bash
SCIENCE_TELEMETRY_DIR=/tmp/science-telemetry-v15-smoke rtk uv run --frozen science telemetry report --format json
```

Expected: report includes `validation_summary` if the first command reached validation `run()`, and otherwise at least preserves a `command_error`.

- [ ] **Step 4: Commit any final docs/polish**

If no files changed after verification, skip this commit. Otherwise:

```bash
rtk git add docs/plans/2026-06-26-feedback-telemetry-adaptation-design.md docs/plans/2026-06-27-telemetry-v1.5-design.md
rtk git commit -m "docs(telemetry): update v1.5 notes"
```

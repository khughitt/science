# Telemetry Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the smallest useful local-first telemetry core for Science CLI usage and reporting.

**Architecture:** Add a focused `science_tool.telemetry` module that owns event models, redaction, JSONL storage, aggregation, and pruning. Register a top-level `science telemetry` command group in `science_tool.cli`, and use Click result callbacks plus a custom command group to capture command finishes and parse/runtime failures without editing every command.

**Tech Stack:** Python 3.13, Click, Pydantic-adjacent stdlib dataclasses/dicts, JSONL files under the Science config directory, pytest, CliRunner.

---

## File Structure

- Create `science/src/science_tool/telemetry.py`
  - Owns event creation, argument shape redaction, JSONL storage, report aggregation, export, and pruning.
- Modify `science/src/science_tool/cli.py`
  - Adds `TelemetryGroup` for parse/runtime error capture.
  - Adds `@main.result_callback()` for successful command completion capture.
  - Adds top-level `science telemetry status|report|export|prune` commands.
- Create `science/tests/test_telemetry.py`
  - Unit tests for redaction, JSONL read/write, reports, export, and prune.
- Create `science/tests/test_telemetry_cli.py`
  - CLI tests for successful invocation capture, parse-error capture, status/report/export/prune behavior, and opt-out.

## Task 1: Telemetry Storage and Redaction

**Files:**
- Create: `science/src/science_tool/telemetry.py`
- Test: `science/tests/test_telemetry.py`

- [ ] **Step 1: Write failing tests for argument redaction and event storage**

Add tests that expect:
- safe entity refs like `dataset:sciplex3` are preserved;
- option names are preserved;
- paths, URLs, and arbitrary text values are redacted;
- events append to monthly JSONL files;
- malformed JSONL rows are skipped when reading.

Run: `SCIENCE_TEST_TMPDIR=/tmp/science-pytest-tmp rtk uv run --frozen pytest tests/test_telemetry.py -q`
Expected: FAIL because `science_tool.telemetry` does not exist.

- [ ] **Step 2: Implement minimal storage/redaction module**

Implement:
- `get_telemetry_dir()`
- `redact_argv(argv: Sequence[str]) -> list[str]`
- `append_event(telemetry_dir: Path, event: Mapping[str, object]) -> Path | None`
- `read_events(telemetry_dir: Path) -> list[dict[str, object]]`
- `new_event(...) -> dict[str, object]`

Telemetry writes are best-effort: storage failures return `None` and do not raise.

- [ ] **Step 3: Run storage/redaction tests**

Run: `SCIENCE_TEST_TMPDIR=/tmp/science-pytest-tmp rtk uv run --frozen pytest tests/test_telemetry.py -q`
Expected: PASS.

- [ ] **Step 4: Commit**

Commit message: `feat(telemetry): add local event journal`

## Task 2: Telemetry Reporting, Export, and Prune

**Files:**
- Modify: `science/src/science_tool/telemetry.py`
- Test: `science/tests/test_telemetry.py`

- [ ] **Step 1: Write failing tests for summary reports and maintenance**

Add tests that expect:
- `summarize_events()` counts total events, commands, error classes, and exit codes;
- `export_events_jsonl()` emits newline-delimited sorted JSON;
- `prune_events()` removes events before a cutoff date and keeps newer events.

Run: `SCIENCE_TEST_TMPDIR=/tmp/science-pytest-tmp rtk uv run --frozen pytest tests/test_telemetry.py -q`
Expected: FAIL because reporting functions do not exist.

- [ ] **Step 2: Implement reporting helpers**

Implement:
- `summarize_events(events: Sequence[Mapping[str, object]]) -> dict[str, object]`
- `export_events_jsonl(events: Sequence[Mapping[str, object]]) -> str`
- `prune_events(telemetry_dir: Path, before: date) -> int`

Keep output deterministic by sorting events by timestamp then event_id.

- [ ] **Step 3: Run telemetry unit tests**

Run: `SCIENCE_TEST_TMPDIR=/tmp/science-pytest-tmp rtk uv run --frozen pytest tests/test_telemetry.py -q`
Expected: PASS.

- [ ] **Step 4: Commit**

Commit message: `feat(telemetry): report and prune local events`

## Task 3: CLI Instrumentation and Commands

**Files:**
- Modify: `science/src/science_tool/cli.py`
- Test: `science/tests/test_telemetry_cli.py`

- [ ] **Step 1: Write failing CLI tests**

Add tests that expect:
- `science feedback list --format json` records one `command_finish` event;
- `science feedback list --bad-option` records one `command_error` event with `error_class: NoSuchOption`;
- `SCIENCE_TELEMETRY_ENABLED=0` disables event writing;
- `science telemetry status --format json` reports the telemetry directory and event count;
- `science telemetry report --format json` reports command/error counts;
- `science telemetry export --format jsonl` prints JSONL;
- `science telemetry prune --before YYYY-MM-DD` removes old events.

Run: `SCIENCE_TEST_TMPDIR=/tmp/science-pytest-tmp rtk uv run --frozen pytest tests/test_telemetry_cli.py -q`
Expected: FAIL because CLI instrumentation and telemetry commands do not exist.

- [ ] **Step 2: Implement CLI integration**

Implement:
- `TelemetryGroup(click.Group)` with `main()` override that catches `click.ClickException`/`click.Abort`, records `command_error`, then re-raises.
- Change `@click.group()` to use `cls=TelemetryGroup`.
- `@main.result_callback()` to record `command_finish` after successful command execution.
- `science telemetry status|report|export|prune` command group.

Use `SCIENCE_TELEMETRY_DIR` for testable storage and `SCIENCE_TELEMETRY_ENABLED=0|false|no` as the local opt-out.

- [ ] **Step 3: Run CLI tests**

Run: `SCIENCE_TEST_TMPDIR=/tmp/science-pytest-tmp rtk uv run --frozen pytest tests/test_telemetry_cli.py -q`
Expected: PASS.

- [ ] **Step 4: Commit**

Commit message: `feat(cli): record local telemetry events`

## Task 4: Documentation and Full Focused Verification

**Files:**
- Modify: `commands/catalog-benchmarks.md` only if command-doc coverage requires it.
- Modify: `docs/plans/2026-06-26-feedback-telemetry-adaptation-design.md` if the implemented v1 contract needs a revision note.

- [ ] **Step 1: Run focused test suite**

Run:
`SCIENCE_TEST_TMPDIR=/tmp/science-pytest-tmp rtk uv run --frozen pytest tests/test_telemetry.py tests/test_telemetry_cli.py tests/test_feedback.py tests/test_feedback_cli.py -q`

Expected: PASS.

- [ ] **Step 2: Run type/lint checks**

Run:
`rtk uv run --frozen pyright src/science_tool/telemetry.py tests/test_telemetry.py tests/test_telemetry_cli.py`

Run:
`rtk uv run --frozen ruff check src/science_tool/telemetry.py src/science_tool/cli.py tests/test_telemetry.py tests/test_telemetry_cli.py`

Expected: PASS.

- [ ] **Step 3: Smoke test real CLI telemetry**

Run:
`SCIENCE_TELEMETRY_DIR=/tmp/science-telemetry-smoke rtk uv run --frozen science feedback list --format json`

Run:
`SCIENCE_TELEMETRY_DIR=/tmp/science-telemetry-smoke rtk uv run --frozen science telemetry report --format json`

Expected: report includes at least one `command_finish` event.

- [ ] **Step 4: Commit remaining docs or polish**

Commit message: `docs(telemetry): record v1 implementation scope`

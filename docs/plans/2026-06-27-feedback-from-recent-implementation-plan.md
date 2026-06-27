# Feedback From Recent Telemetry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add `science feedback add --from-recent` so users can create explicit feedback entries from recent redacted local telemetry.

**Architecture:** `science_tool.telemetry` provides deterministic recent-event selection and feedback defaults. The Click command consumes those helpers and still writes ordinary `FeedbackEntry` YAML records through the existing feedback persistence path.

**Tech Stack:** Python, Click, Pydantic feedback models, pytest `CliRunner`, local JSONL telemetry.

---

### Task 1: Telemetry Selection Helpers

**Files:**
- Modify: `science/src/science_tool/telemetry.py`
- Test: `science/tests/test_telemetry.py`

- [ ] Add failing tests for `feedback_context_from_recent_event`.
- [ ] Verify those tests fail because the helper does not exist.
- [ ] Implement:
  - `feedback_context_from_recent_event(events, index=1, today=None, since_days=14)`
  - `TelemetryFeedbackContext` dataclass with `event`, `target`, `category`, `detail`
  - eligible event filtering for command errors, nonzero exits, and warn/fail validation summaries
  - newest-first ordering by timestamp and event id
- [ ] Run `rtk uv run --frozen pytest tests/test_telemetry.py -q`.
- [ ] Commit telemetry helper changes.

### Task 2: Feedback CLI Integration

**Files:**
- Modify: `science/src/science_tool/cli.py`
- Test: `science/tests/test_feedback_cli.py`

- [ ] Add failing CLI tests for `science feedback add --from-recent`.
- [ ] Verify the tests fail because the option does not exist.
- [ ] Add `--from-recent` to `feedback add` as an optional 1-based integer flag value.
- [ ] When present, load local telemetry and use the helper defaults:
  - missing `--target` uses telemetry target
  - missing `--category` uses telemetry category
  - `--detail` appends the telemetry detail block
- [ ] Preserve duplicate detection and normal feedback YAML output.
- [ ] Run `rtk uv run --frozen pytest tests/test_feedback_cli.py tests/test_telemetry.py -q`.
- [ ] Commit CLI integration.

### Task 3: Verification and Cleanup

**Files:**
- Verify only unless tests require small corrections.

- [ ] Run focused pytest:
  `rtk uv run --frozen pytest tests/test_telemetry.py tests/test_telemetry_cli.py tests/test_feedback.py tests/test_feedback_cli.py -q`
- [ ] Run pyright:
  `rtk uv run --frozen pyright src/science_tool/telemetry.py src/science_tool/cli.py tests/test_telemetry.py tests/test_feedback_cli.py`
- [ ] Run ruff:
  `rtk uv run --frozen ruff check src/science_tool/telemetry.py src/science_tool/cli.py tests/test_telemetry.py tests/test_feedback_cli.py`
- [ ] Smoke test with a temporary telemetry directory.
- [ ] Commit any verification fixes.

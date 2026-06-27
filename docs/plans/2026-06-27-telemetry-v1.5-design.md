---
id: "plan:2026-06-27-telemetry-v1.5-design"
type: "plan"
title: "Telemetry v1.5: validation summaries and feedback triage context"
status: "proposed"
created: "2026-06-27"
updated: "2026-06-27"
related:
  - "plan:2026-06-26-feedback-telemetry-adaptation-design"
---

# Telemetry v1.5: validation summaries and feedback triage context

## Purpose

Telemetry v1 shipped a local JSONL event journal, command finish/error capture,
basic reports, export, prune, and local opt-out. It can say which commands ran
and which Click-level errors occurred, but it still cannot answer the more useful
question: "What project checks keep failing or warning, and how should that
inform feedback triage?"

Telemetry v1.5 adds the smallest useful bridge from operational events to
maintainer action:

- preserve correct Click exit semantics after telemetry instrumentation;
- record aggregate validation-summary events for `science validate`;
- show recent telemetry context in `science feedback triage --with-telemetry`.

It deliberately defers `science feedback add --from-recent` until triage context
has proved which recent telemetry is worth attaching to feedback entries.

## Current bug to fix first

The v1 root `TelemetryGroup` invokes Click with `standalone_mode=False` so it can
record parse/runtime errors. That changes the behavior of commands that call
`ctx.exit(1)`: Click returns the integer exit code instead of raising
`SystemExit`. In `CliRunner`, those commands then appear to exit with code 0 even
though they printed failure output. Existing `science validate` tests catch this.

v1.5 must restore normal Click semantics:

- successful commands still record `command_finish` with `exit_code: 0`;
- commands that call `ctx.exit(N)` must surface process exit code `N`;
- validation commands that exit 1 should record a validation summary with failure
  status, not silently look successful;
- telemetry write failures must remain best-effort and never change command
  results.

## Validation summary event

`science validate` should append one aggregate event after `run()` returns and
before it exits:

```yaml
schema_version: 1
surface: "validation"
event_type: "validation_summary"
source: "science"
command: "validate"
profile: "full"
strict: false
fail_on: "ghost-files"   # or null
status: "pass|warn|fail"
counts:
  error: 0
  warn: 7
  info: 2
top_checks:
  - check: "dataset.license-missing"
    count: 3
  - check: "entity-conformance"
    count: 2
```

The event is aggregate-only. It must not store raw validation rows, file paths,
line numbers, messages, stderr, or project content. `top_checks` counts rule IDs
only and omits missing/empty rule values. A result is:

- `fail` when `result.errors > 0` or `result.gated` is non-empty;
- `warn` when there are warnings but no failure;
- `pass` otherwise.

This event complements, rather than replaces, the existing `command_finish` /
`command_error` event. A failing validation run should still preserve its real
exit code.

## Feedback triage with telemetry

Add `--with-telemetry` to `science feedback triage`. The option is read-only and
local-only. It joins feedback clusters or target groups with recent telemetry
summaries from the local journal.

For v1.5, "relevant" means:

- feedback targets of the form `command:<name>` match telemetry command names
  whose first token equals `<name>` or whose command string equals `<name>`;
- `command:validate` also includes `validation_summary` events for `validate`;
- non-command targets get a general recent telemetry summary, but no inferred
  command mapping.

JSON output adds a `telemetry` object per triage row:

```json
{
  "recent_events": 4,
  "command_errors": {"NoSuchOption": 1},
  "commands": {"validate": 3},
  "validation": {
    "runs": 3,
    "statuses": {"warn": 2, "fail": 1},
    "top_checks": {"dataset.license-missing": 2}
  }
}
```

Table output adds a compact `Telemetry` column such as:

```text
validate: 3 runs, 1 fail, 2 warn
```

or `no recent telemetry`.

The existing `--since N` option should filter feedback entries as it does today.
For telemetry context, v1.5 should use the same `N`-day window when provided and
otherwise default to the last 14 days. This keeps triage from being dominated by
stale local command history.

## Deferred

The following remain out of scope for this tranche:

- `science feedback add --from-recent`;
- validation-summary capture for non-`science validate` validation-like commands
  such as `graph validate` or commons validation;
- skill note events;
- remote upload or automatic export;
- raw validation row capture.

## Testing strategy

Tests should lock down the public behavior:

- root CLI instrumentation preserves non-zero exit codes from `ctx.exit`;
- failing `science validate` records a `validation_summary` with status `fail`;
- warning-only validation records status `warn`;
- clean validation records status `pass`;
- validation events omit raw paths/messages and include only counts and rule IDs;
- `feedback triage --with-telemetry --format json` includes telemetry objects;
- table triage includes a compact telemetry column;
- telemetry remains disabled when `SCIENCE_TELEMETRY_ENABLED=0`.

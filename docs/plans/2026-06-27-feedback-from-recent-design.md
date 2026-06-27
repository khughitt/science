# Feedback From Recent Telemetry Design

## Status
Accepted for implementation.

## Context
Telemetry v1 and v1.5 made Science record local-first command context and validation summaries. The next friction point is feedback capture: after a command fails, the user still has to remember the command shape, target, and useful details when creating `science feedback` entries.

This tranche keeps feedback user-authored and explicit. Telemetry is only a local context source that can pre-fill safe fields and add redacted detail.

## Goals
- Add `science feedback add --from-recent` as the smallest useful bridge from local telemetry to feedback.
- Reduce feedback capture friction after command failures and validation warnings or failures.
- Preserve local-first behavior, redaction, and explicit user intent.
- Keep the feedback YAML schema unchanged.

## Non-Goals
- No automatic feedback creation.
- No raw command argument capture beyond existing redacted `argv_shape`.
- No interactive picker in v1; selection is deterministic by index.
- No remote telemetry export or upload.

## CLI Contract
`science feedback add --from-recent INDEX --summary TEXT [--target TARGET] [--category CATEGORY] [--detail TEXT] [--project PROJECT] [--related ID]...`

Selection uses recent telemetry events sorted newest-first. `INDEX` is 1-based and defaults to `1`, so `--from-recent` selects the newest eligible event.

Eligible events are:
- `command_error`
- `command_finish` events with nonzero `exit_code`
- `validation_summary` events with `status` of `warn` or `fail`

The selected event provides defaults:
- `target`: `command:<first command token>` unless `--target` is provided.
- `category`: `friction` for command errors or nonzero exits, `gap` for validation summaries unless `--category` is provided.
- `detail`: appended with a redacted telemetry context block. User-provided `--detail` remains first.

If no eligible event exists, the command fails with a `ClickException` that tells the user no recent telemetry is available.

## Telemetry Context Block
The detail block must be aggregate and redacted:

```text
Telemetry context:
- event: <event_id>
- timestamp: <timestamp>
- command: <command>
- argv: <redacted argv_shape>
- exit_code: <exit_code>
- error_class: <error_class>
- validation_status: <status>
- validation_counts: error=<n>, warn=<n>, info=<n>
- top_checks: check.one=2, check.two=1
```

Fields with no value are omitted. The block never includes raw paths, raw URLs, or raw validation messages.

## Module Boundaries
- `science_tool.telemetry` owns selection, summarization, and context rendering for telemetry events.
- `science_tool.cli.feedback_add` owns Click options, duplicate handling, and normal feedback entry creation.
- `science_tool.feedback` remains the feedback persistence and triage layer.

## Testing
- Unit tests cover eligible event filtering, newest-first ordering, target/category defaults, and redacted context rendering.
- CLI tests cover creating feedback from a recent command error and validation summary.
- CLI tests cover out-of-range/no telemetry failure without writing feedback.

## Future Work
- `science feedback recent` or an interactive picker can be added later if users need a preview workflow.
- `science feedback scaffold-test --from-recent` can reuse the same telemetry selection helper after this contract is stable.

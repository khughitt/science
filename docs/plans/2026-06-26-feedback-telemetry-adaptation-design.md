---
id: "plan:2026-06-26-feedback-telemetry-adaptation-design"
type: "plan"
title: "Feedback, telemetry, and adaptation for Science"
status: "proposed"
created: "2026-06-26"
updated: "2026-06-26"
related:
  - "plan:2026-03-25-feedback-system-design"
---

# Feedback, telemetry, and adaptation for Science

## Implementation note (2026-06-27)

The first shipped tranche is intentionally smaller than the full design:

- local JSONL event journal;
- conservative command-argument shape redaction;
- automatic CLI `command_finish` and Click parse/runtime `command_error`
  capture;
- `science telemetry status`, `report`, `export`, and `prune`;
- local opt-out through `SCIENCE_TELEMETRY_ENABLED=0|false|no|off`.

It does not yet implement `feedback add --from-recent`,
`feedback triage --with-telemetry`, validation-summary events, skill note
helpers, or explicit export/report workflows beyond local JSONL output.

## Purpose

Science already collects explicit feedback through `science feedback add`, but
explicit feedback catches only what an agent notices and chooses to report. It
misses silent friction: mistyped commands, repeated validation failures,
abandoned workflows, stale guidance that causes retries, and commands that work
only after undocumented recovery steps.

This design adds a local-first telemetry and adaptation layer. The goal is not
central analytics. The goal is to help Science understand which commands, skills,
schemas, and workflows are helping or failing in real project use, then turn that
evidence into better feedback triage, documentation, tests, and command design.

## Goals

- Keep telemetry local by default. No automatic network upload.
- Capture operational signals that explicit feedback misses.
- Reduce friction in filing feedback by linking feedback entries to recent
  command and validation context.
- Give maintainers reports that answer "what is not working?" without reading
  every project history manually.
- Preserve enough structure to compare usage patterns across projects when a
  user explicitly exports local telemetry.

## Non-goals

- No remote telemetry service.
- No personally identifying user tracking.
- No raw free-text command argument capture by default.
- No attempt to judge scientific truth directly from telemetry. Telemetry
  measures tool behavior and workflow outcomes, not whether a claim is true.
- No replacement for feedback entries. Telemetry gives context; feedback remains
  the human-readable issue record.

## Current state

The current feedback system stores one YAML file per entry under
`~/.config/science/feedback/` and exposes:

- `science feedback add`
- `science feedback list`
- `science feedback update`
- `science feedback triage`
- `science feedback scaffold-test`
- `science feedback report`

This is enough for structured issue capture and manual triage. The missing layer
is event context: what command was being run, which invocation failed, whether
the agent retried, what validation warnings appeared repeatedly, and how long an
entry stayed open before it was addressed.

## Design overview

Add a local event journal plus report and export commands:

```text
~/.config/science/
  feedback/
    fb-YYYY-MM-DD-NNN.yaml
  telemetry/
    events-YYYY-MM.jsonl
```

Each event is an append-only JSON object. Commands emit small, structured
records at important boundaries: invocation, parse failure, command completion,
validation summary, feedback creation/update, and selected recovery actions.

The feedback CLI consumes this journal in two ways:

1. `science feedback triage --with-telemetry` shows relevant event context for
   each feedback cluster.
2. `science feedback add --from-recent` can attach recent failed commands,
   validation summaries, or retries to the feedback detail.

Telemetry has its own commands:

```bash
science telemetry report
science telemetry export --format jsonl --redact default
science telemetry status
science telemetry prune --before 2026-01-01
```

## Event model

### Base fields

Every event has:

```yaml
schema_version: 1
event_id: "tel-2026-06-26T14-22-31.123456-abcdef"
timestamp: "2026-06-26T14:22:31.123456-04:00"
project: "pan-disease"
project_root_hash: "sha256:..."
cwd_kind: "project-root|subdir|outside-project"
surface: "cli|skill|feedback|validation|graph|dataset"
event_type: "command_start|command_finish|command_error|feedback_add|feedback_update|validation_summary|recovery"
source: "science"
```

Project root is hashed so reports can group per project without exposing a full
local path. The human project name is already recorded in feedback entries and
is useful enough to keep, but exact absolute paths are not stored.

### Command events

Command attempts record normalized command shape, not raw sensitive values:

```yaml
surface: "cli"
event_type: "command_finish"
command: "dataset verify-access"
argv_shape:
  - "dataset"
  - "verify-access"
  - "<ref>"
  - "--level"
  - "<choice:public>"
  - "--method"
  - "<choice:retrieved>"
  - "--license"
  - "<value:redacted>"
exit_code: 0
duration_ms: 438
warnings_count: 1
```

Argument redaction is conservative:

- Keep option names.
- Keep enum values and booleans.
- Redact free text, paths, URLs, tokens, notes, titles, and arbitrary strings.
- Preserve typed entity refs only when they match safe local forms like
  `dataset:<slug>`, `question:<slug>`, or `task:<id>`.

### Error events

Parse and runtime failures are first-class because they reveal UX friction:

```yaml
event_type: "command_error"
command: "feedback report"
error_class: "NoSuchOption"
error_message_template: "No such option: {option}"
error_fields:
  option: "--format"
exit_code: 2
```

Messages are templated where possible. The exact stderr text is not stored by
default because it may include paths or user-provided values.

### Validation and graph events

Validation and graph build commands emit summaries, not every row:

```yaml
event_type: "validation_summary"
command: "validate"
status: "warn"
counts:
  error: 0
  warn: 7
top_checks:
  - check: "dataset.license-missing"
    count: 3
  - check: "entity-conformance"
    count: 2
```

This lets reports answer questions such as "which validation checks recur after
which commands?" without copying project content.

### Skill and command-doc events

Science cannot reliably observe every agent skill invocation unless the agent
routes through Science. The v1 design records only observable events:

- Generated Science Codex skills can optionally call `science telemetry note`
  at start and finish.
- Command docs can mention the same helper for high-value workflows.
- Direct CLI commands require no manual note because Click instrumentation can
  capture them.

`science telemetry note` accepts structured fields:

```bash
science telemetry note \
  --surface skill \
  --name science-catalog-datasets \
  --phase start
```

## Storage

Use monthly JSONL files under `~/.config/science/telemetry/`.

Reasons:

- Append-only writes are simple and robust.
- Monthly sharding prevents one unbounded file.
- JSONL is easy to inspect, filter, and export.
- It does not add a database dependency.

Writes are best-effort and must never break the primary command. If telemetry
cannot be written, Science should emit at most a debug-level log, not a user
warning.

## Configuration

Telemetry defaults to local enabled:

```yaml
telemetry:
  enabled: true
  capture: local
  redact: default
  retention_days: 180
```

Configuration can live in the global Science config. Per-project config can
disable telemetry for a sensitive project:

```yaml
telemetry:
  enabled: false
```

Environment overrides:

- `SCIENCE_TELEMETRY=0` disables capture.
- `SCIENCE_TELEMETRY_DIR=/path` redirects local storage for tests or audits.
- `SCIENCE_TELEMETRY_REDACT=strict|default|none` controls local capture detail.

`none` is only for local debugging and should never be used by default export.

## Commands

### `science telemetry status`

Shows whether telemetry is enabled, where local events are stored, current
redaction mode, retention, and event count by month.

### `science telemetry report`

Produces a human-readable local report. Initial report sections:

- Command attempts by command and outcome.
- Most common parse errors and invalid options.
- Commands with high failure or retry ratios.
- Validation checks that recur after specific commands.
- Feedback clusters with telemetry context.
- Feedback time-to-address and still-open age.
- Commands frequently followed by `science feedback add`.

Report flags:

```bash
science telemetry report --since 30d
science telemetry report --project pan-disease
science telemetry report --target command:catalog-datasets
science telemetry report --format table|json|markdown
```

### `science telemetry export`

Writes a local export file. It never uploads.

```bash
science telemetry export \
  --since 90d \
  --format jsonl \
  --redact default \
  --out telemetry-export.jsonl
```

Redaction modes:

- `strict`: drops argv shapes, refs, and message templates; keeps aggregate
  counts and command names.
- `default`: keeps safe command shape and templated errors.
- `none`: local-only full event body; refuse unless `--i-understand-local-only`
  is also passed.

### `science feedback triage --with-telemetry`

Adds context under each target group:

```text
## command:catalog-datasets
  11 open entries, 3 projects
  telemetry:
    42 runs in 30d, 19 warnings, 6 parse errors
    common validation after command: dataset.license-missing, dataset_verified_but_unstageable
    common next command: feedback add, validate
```

### `science feedback add --from-recent`

Shows recent local command failures and validation summaries, then appends a
short sanitized context block to `detail`. In non-interactive environments,
`--from-recent N` attaches the last N relevant events.

This reduces feedback friction because the author no longer has to manually
copy command context into the feedback detail.

## Adaptation loop

Telemetry should feed concrete maintenance actions:

1. **Detect friction.** Reports identify high-failure command surfaces, repeated
   invalid options, recurring validation checks, and workflows that often end in
   feedback.
2. **Create or enrich feedback.** Maintainers convert report clusters into
   feedback entries, or attach telemetry context to existing ones.
3. **Implement fixes.** Fixes remain normal code/docs work with tests.
   `science feedback scaffold-test <id>` can turn an entry into a deliberately
   failing pytest scaffold plus the suggested existing test target.
4. **Close the loop.** `feedback update --status addressed` records the
   resolution. Later telemetry reports should show lower recurrence or fewer
   failures for the same surface.

This explicitly separates observation from adaptation. Telemetry never edits
commands or skills by itself.

## Privacy and safety

- Local-first by default.
- No automatic upload.
- No raw free-text args by default.
- No absolute paths by default.
- No environment variables captured.
- No stdout/stderr capture except templated error classes and aggregate counts.
- Exports are explicit local files.
- Strict redaction is available for sharing.
- Sensitive projects can disable telemetry locally.

## Implementation approach

### Phase 1: event journal and CLI instrumentation

- Add `science_tool.telemetry` with event model, redaction, writer, reader, and
  local config helpers.
- Instrument top-level Click command invocation and error handling.
- Add `science telemetry status`, `report`, and `export`.
- Add tests with `SCIENCE_TELEMETRY_DIR` pointing at a temp directory.

### Phase 2: feedback integration

- Add `feedback triage --with-telemetry`.
- Add `feedback add --from-recent`.
- Include feedback lifecycle metrics in telemetry reports.

### Phase 3: workflow-specific summaries

- Add validation summary events.
- Add dataset/graph summary events.
- Add optional `telemetry note` for generated skills and command docs.

## Testing strategy

- Unit tests for redaction: free text, URLs, paths, and arbitrary strings must
  not survive default redaction.
- Unit tests for event append/read over monthly JSONL files.
- CLI tests for parse-error capture using invalid options.
- CLI tests proving telemetry write failures do not fail the primary command.
- Report tests over synthetic events.
- Feedback integration tests for `--with-telemetry` and `--from-recent`.

## Open decisions

1. Whether local telemetry should be enabled immediately on upgrade or require a
   one-time notice. The design chooses enabled local capture, but the CLI should
   make this visible through `science telemetry status`.
2. Whether generated Codex skills should call `science telemetry note` by
   default. This is useful, but it adds ceremony to every skill. Phase 3 should
   pilot it only for high-value workflows such as `catalog-datasets`,
   `plan-analysis`, `plan-pipeline`, and `pre-register`.
3. How long retention should be. The initial proposal is 180 days because it
   covers multi-month project arcs without unbounded storage.

## Success criteria

- A maintainer can answer "which Science commands are causing the most local
  friction this month?" with one command.
- A feedback entry can be created with sanitized recent context in one command.
- Exported telemetry can be shared without exposing project paths, URLs, notes,
  titles, or arbitrary arguments under default redaction.
- Addressed feedback can be checked against later telemetry to see whether the
  same failure pattern declined.

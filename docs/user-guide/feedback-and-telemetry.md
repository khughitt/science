# Feedback And Telemetry

Science has two related maintenance surfaces:

- `science feedback ...` stores explicit feedback entries that humans and
  agents can triage, update, report, and turn into regression-test scaffolds.
- `science telemetry ...` stores local, redacted operational events that help
  explain recent failures and recurring friction.

Telemetry does not replace feedback. Telemetry provides context; feedback is the
durable work queue and decision record.

## Storage And Privacy

Feedback entries are YAML files under the feedback directory. By default this is
the Science config directory's `feedback/` subdirectory; set
`SCIENCE_FEEDBACK_DIR` to use another location.

Telemetry events are monthly JSONL files under the telemetry directory. By
default this is the Science config directory's `telemetry/` subdirectory; set
`SCIENCE_TELEMETRY_DIR` to use another location.

Telemetry is local-first. Science does not upload telemetry automatically.
Writes are best effort and must not break the primary command. Set
`SCIENCE_TELEMETRY_ENABLED=0`, `false`, `no`, or `off` to disable telemetry
writes.

Telemetry stores command shape, not raw command contents. Argument redaction:

- preserves command tokens and safe Science refs such as `dataset:<slug>`
- redacts URLs as `<url:redacted>`
- redacts paths as `<path:redacted>`
- redacts known sensitive option values such as `--path`, `--source`, `--url`,
  `--note`, `--summary`, and `--title`
- stores generic scalar values as `<value>`

Validation telemetry is aggregate-only. It records counts and top check IDs, not
raw validation paths or messages.

## Telemetry Events

Telemetry events use `schema_version: 1` and include:

- `event_id`
- `timestamp`
- `surface`
- `event_type`
- `source`
- `argv_shape`

Command events also include `command`, and may include `exit_code`,
`error_class`, and `error_message_template`.

The current event types are:

| Event type | Meaning |
|---|---|
| `command_finish` | A CLI command completed successfully. |
| `command_error` | A CLI command failed before normal completion. |
| `validation_summary` | `science validate` recorded aggregate pass, warn, or fail data. |

`validation_summary` events have `surface: validation`, `command: validate`,
`profile`, `strict`, `fail_on`, `status`, `counts`, and `top_checks`.
Validation status is `fail` when errors exist or the gate is tripped, `warn`
when warnings exist without failure, and `pass` otherwise.

## Telemetry Commands

Use:

```bash
science telemetry status [--format table|json]
science telemetry report [--errors] [--limit N] [--format table|json]
science telemetry export --format jsonl
science telemetry prune --before YYYY-MM-DD [--format table|json]
```

`status` reports whether telemetry is enabled, the telemetry directory, and the
event count.

`report` summarizes event types, commands, error classes, and exit codes. With
`--errors`, it also shows recent command failures using redacted `argv_shape`.

`export` prints deterministic JSONL for local inspection or explicit sharing.

`prune` removes events before the supplied date.

## Feedback Entries

Use:

```bash
science feedback add --target <target> --summary <text> [--category <category>] [--concern <concern>]
science feedback list [--status open|all|...] [--target <glob>] [--concern <glob>] [--format table|json]
science feedback update <id> [--status <status> --resolution <text>] [--concern <concern>]
science feedback triage [--cluster] [--with-telemetry] [--since N] [--format table|json]
science feedback report [--status <status>] [--project <name>] [--concern <glob>]
science feedback scaffold-test <id> [--dry-run] [--force]
```

Feedback categories are `friction`, `gap`, `guidance`, `suggestion`, and
`positive`. Feedback statuses are `open`, `addressed`, `deferred`, and
`wontfix`. Setting a terminal status requires a resolution.

Feedback concern is a controlled taxonomy:

| Concern | Use |
|---|---|
| `tooling` | Default. Command behavior, CLI ergonomics, docs, generated artifacts, or framework implementation. |
| `methodology:statistics` | Assumptions, inference validity, finite-sample behavior, model choice, or statistical checks. |
| `methodology:qa` | Data or quality checks that should have caught an issue. |
| `methodology:design` | Study or analysis design mismatches with the question or data constraints. |
| `methodology:data-fitness` | Dataset suitability, preprocessing, provenance, or representativeness. |
| `methodology:reasoning` | Interpretation, causal reasoning, epistemic over-claiming, or confounding. |

Unknown concern values are rejected. Legacy feedback YAML without a concern
loads as `tooling`.

Concern is part of feedback identity. Two entries with the same target and
similar summary but different concerns remain distinct; recurrence is not
merged across concerns. Triage groups by `(concern, target)`, clustered triage
keeps concern in the cluster key, and reports group by concern and then target.

## Feedback From Recent Telemetry

Use:

```bash
science feedback add --from-recent [N] --summary <text>
```

`--from-recent` selects an eligible event from the last 14 days. The optional
`N` is a one-based index into newest-first eligible events. Without `N`, Science
uses the newest eligible event.

Eligible events are:

- `command_error`
- `command_finish` with a non-zero exit code
- `validation_summary` with status `warn` or `fail`

The selected event supplies default feedback context:

- command failures use `category: friction`
- validation summaries use `category: gap`
- target is `command:<first-command-token>`
- detail receives a redacted `Telemetry context:` block

Explicit `--target`, `--category`, and `--detail` values override or prepend to
the telemetry-derived defaults.

## Triage With Telemetry

Use:

```bash
science feedback triage --with-telemetry
science feedback triage --cluster --with-telemetry --format json
```

Telemetry matching is local and target-based. For `command:<name>` targets,
Science matches events whose full command equals `<name>` or whose first command
token is `<name>`. For other target forms, the current implementation treats
local telemetry as relevant context.

The default window is 14 days. `--since N` changes that window for clustered
triage and for telemetry summaries.

Telemetry summaries include recent event count, command errors, command counts,
validation run counts, validation statuses, and aggregate top checks. Table
output renders a compact summary such as `validate: 2 runs, 1 fail, 1 warn`.

## Methodology Reflection

Use `/science:post-mortem` or the `science-post-mortem` Codex skill after an
analysis failed or behaved unexpectedly. Keep the project-specific incident in
the project, and only file generalized methodology lessons as feedback.

Methodology feedback should target the surface that should change, such as a
skill, command, template, or validation check. Use the most specific
`methodology:*` concern that describes the lesson.

`commands/interpret-results.md` points to the post-mortem workflow when an
assumption was violated or an outcome contradicts a pre-registered expectation.

## Deferred Scope

There is no `science telemetry note` command today. Generated skills and command
docs do not emit custom note events. Telemetry report does not yet include
feedback lifecycle metrics such as time-to-address or commands frequently
followed by feedback creation.

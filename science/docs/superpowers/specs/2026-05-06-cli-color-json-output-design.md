# CLI Color and JSON Output Design

**Date:** 2026-05-06
**Status:** Approved design
**Scope:** Centralize Science CLI terminal styles, add an explicit global color
policy, and define a consistent JSON-output convention for agent-facing CLI use.

## Decision

Add centralized terminal styling in `science_tool.styles` and make color output an
explicit root-level policy:

```text
science --color=never|auto|always ...
```

The default is `never`. Human users who want color can opt in with
`--color=auto` or `--color=always`, including through shell aliases. Agent-facing
commands and documentation should prefer JSON output where available.

The default is intentionally stricter than the common CLI default of `auto`.
`auto` protects ordinary stdout capture, but some agent harnesses allocate a PTY
while still parsing output programmatically. Those harnesses can receive ANSI
sequences from auto-coloring tools. Defaulting to `never` keeps the base command
agent-safe even in PTY-backed execution, while still leaving humans a single
alias away from colored output.

For machine-readable output, `--format json` is the canonical convention for
read/query/report commands. Existing `--json` flags can remain as compatibility
or convenience aliases, but new broad CLI work should prefer `--format`.

## Context

The CLI is used by both humans and agents. Humans benefit from color for scanning
task state and entity references. Agents benefit from deterministic, markup-free
output and generally prefer JSON over Rich tables or unstructured prose.

Current color and Rich usage is uneven:

- `science_tool.tasks_display` renders a colored Rich task table, including task
  status, type, priority, and a created-date age gradient.
- `science_tool.output` and `science_tool.verdict.cli` build Rich tables with
  color disabled through `force_terminal=False` and `color_system=None`.
- The `health` command builds Rich tables directly and uses Rich markup such as
  `[cyan]science tasks archive[/cyan]`.
- `science_tool.dag.render` uses fixed Graphviz colors for rendered DAG artifacts.
  This is artifact styling, not terminal styling, and should remain separate.
- `science_tool.project_artifacts.data.validate.sh` contains ANSI shell colors for
  a managed validation script. This can be revisited later, but it should not
  block the Python CLI terminal-style work.

A sweep of `~/d/natural-systems/tasks/active.md` found these related-field entity
kind counts:

```text
93  task
72  question
39  hypothesis
36  meta
32  discussion
31  interpretation
24  plan
10  concept
6   report
4   spec
1   topic
```

These counts are one project sample, not a universal distribution. They should
seed the initial semantic style map because they reflect real heavy CLI use. The
map should also cover known core registry kinds so other projects and future
output have stable defaults.

## Goals

1. Disable terminal color by default for agent-safe output.
2. Provide one global color policy that all Python CLI output can consult.
3. Centralize semantic styles instead of scattering Rich style strings across CLI
   modules.
4. Style common entity references consistently across commands that render
   human-readable output.
5. Preserve JSON output as the preferred agent-facing path.
6. Define a CLI convention for JSON support that can be applied incrementally.

## Non-Goals

- Do not make JSON the default CLI output globally.
- Do not require every mutating command to support JSON in the first
  implementation slice.
- Do not fold Graphviz DAG artifact colors into the terminal style registry.
- Do not introduce compatibility layers beyond preserving existing `--json` flags
  where they already exist.
- Do not rename components or add a `Unified` prefix.

## Color Policy

The root `science` command should accept:

```text
--color=never|auto|always
```

Policy behavior:

- `never`: no ANSI color or Rich terminal markup in CLI output.
- `auto`: color only when stdout is an interactive terminal and Rich supports the
  terminal.
- `always`: force ANSI color for terminal output.

The default is `never`.

Implementation should store the selected policy in Click context so nested
command groups can access it without adding a `--color` option to every command.
Commands outside the main `cli.py` module, such as DAG, verdict, aspects, or
project artifacts commands, should access the same context helper.

Environment variable precedence:

1. An explicit `--color` value wins.
2. If `--color` is omitted and `NO_COLOR` is set to a non-empty value, use
   `never`.
3. If `--color` is omitted, `NO_COLOR` is unset, and `FORCE_COLOR` is set to a
   non-empty value other than `0`, use `always`.
4. Otherwise use the default effective policy, `never`.

If both `NO_COLOR` and `FORCE_COLOR` are set and `--color` is omitted,
`NO_COLOR` wins. This matches the fail-closed default for agent-safe output.

## Style Registry

Add `science_tool.styles` with a small public surface:

- A `ColorPolicy` enum or literal type.
- A `get_console()` helper that returns a Rich `Console` configured from the
  active policy and cached for the current Click invocation. Avoid a module-level
  singleton because tests and nested CLI invocations need independent policy
  state.
- Semantic style constants or helpers for:
  - entity kind
  - entity ID prefix versus local part
  - task status
  - task priority
  - task type/aspect
  - dates and recency
  - muted/detail text
  - warnings, errors, and success messages
- A helper to render typed references such as
  `question:q104-rigor-conditional-claims`.

The style registry should fail early for invalid explicit policies. Unknown
entity kinds should use a muted fallback style rather than inventing ad hoc
colors at call sites.

Typed-reference styling should visually distinguish the entity kind prefix from
the local part when color is enabled. The exact palette can be chosen during
implementation, but the convention is stable: kind prefixes carry the entity-kind
style, local parts use a lighter or less-emphasized variant, and `--color=never`
renders the original plain reference string.

Initial entity-kind styles should tune the common kinds from the natural-systems
sweep:

- `task`
- `question`
- `hypothesis`
- `discussion`
- `interpretation`
- `plan`
- `concept`
- `report`
- `spec`
- `topic`
- `meta`

The registry should also define stable fallback styles for other core registry
kinds such as `proposition`, `observation`, `finding`, `story`, `theme`,
`mechanism`, `dataset`, `paper`, `workflow`, and `workflow-run`.

## Terminal Rendering

The first implementation should update the current style hot spots:

- `tasks_display.render_tasks_table`
- `output.emit_query_rows`
- `verdict.cli` rollup table rendering
- `health` command table and next-step rendering

`tasks list` should retain its useful status, priority, and recency cues when
color is enabled, but produce plain table text with no ANSI sequences when color
is disabled.

`tasks show` currently emits plain markdown with `click.echo(render_task(task))`,
not Rich-rendered markdown. The initial implementation should keep that shape and
should not add color there. A later colorized `tasks show` path would need to use
the style registry and preserve the no-color default.

## JSON Output Convention

Use `--format table|json` as the canonical output option for read/query/report
commands. `OUTPUT_FORMATS = ("table", "json")` already exists and should remain
the central constant for that convention.

Commands that already follow this convention include many `entity`, `graph`,
`inquiry`, `datasets`, `tasks list`, `feedback list`, `project index`, and
`health` paths.

Some commands currently use `--json`, including DAG commands and selected
artifact/package commands. The long-term policy is permanent dual spelling for
existing commands that already expose `--json`: `--format json` is canonical for
new and broadly touched read/query/report commands, while `--json` remains a
supported convenience spelling where it exists. There is no planned deprecation
or version-boundary removal for `--json`.

Agent-facing command docs, skills, and AGENTS instructions should prefer
`--format json` where available. Existing docs already frequently use JSON
output for graph, health, tasks, inquiry, curate, and big-picture commands.

## JSON Coverage Strategy

Prioritize JSON support in this order:

1. Read/query/report commands that return structured records.
2. Validation/audit commands that return findings and summary counts.
3. Mutating commands that return useful created/updated IDs, paths, warnings, or
   result summaries.
4. Commands that primarily stream progress, write files, or invoke external
   tools only when there is a clear structured result to report.

The color implementation does not need to make every command JSON-capable. It
should leave the codebase in a state where future JSON additions follow one
clear convention.

## Error Handling

JSON output should continue to use normal non-zero exit behavior for command
errors. The initial design does not require JSON-encoded errors globally, because
that would change Click exception behavior across the whole CLI.

Human-readable warnings should avoid color unless the active color policy allows
it. New JSON additions should include warnings in the JSON payload, usually as a
top-level `warnings` list. Commands with a single natural result object may use
`{"result": ..., "warnings": [...]}`; row-oriented commands may keep their
existing `{"format": "json", "rows": ..., "meta": ...}` shape and add
`"warnings": [...]` when needed. Existing JSON commands do not need to be
reshaped solely for this change, but newly touched JSON paths should avoid
emitting warnings only on stderr when stdout is intended to be parsed as JSON.

## Testing

Add focused tests for the implementation slice:

1. Root `--color` accepts only `never`, `auto`, and `always`.
2. Default CLI output from a colorized command contains no ANSI escape sequences.
3. `--color=auto` with non-TTY output produces no ANSI escape sequences.
4. `--color=always` enables ANSI style output for at least one representative
   command, such as `tasks list`.
5. `--color=never` suppresses Rich markup and ANSI output from `health`.
6. `NO_COLOR` and `FORCE_COLOR` affect the policy only when `--color` is omitted.
7. JSON output from commands touched by the style work remains unchanged in
   structure and contains no ANSI escape sequences.
8. Entity-reference style helpers render unknown kinds without raising.

Existing tests for DAG Graphviz colors should not be rewritten for terminal
style policy.

## Rollout

Implement in stages:

1. Add `science_tool.styles`, root color option plumbing, and tests for the
   policy helper.
2. Migrate current Rich terminal rendering to the shared console/style helpers.
3. Add entity-reference styling where human output already prints related refs.
4. Add `--format json` aliases to high-value `--json`-only read/report commands
   when touched.
5. Update agent-facing docs to prefer JSON forms for commands used by agents.

This keeps the first code change small enough to verify while making the
terminal and JSON conventions explicit.

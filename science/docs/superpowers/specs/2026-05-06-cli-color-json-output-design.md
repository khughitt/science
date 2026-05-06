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

These common kinds should be covered by the initial semantic style map. The map
should also cover known core registry kinds so future output has stable defaults.

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

## Style Registry

Add `science_tool.styles` with a small public surface:

- A `ColorPolicy` enum or literal type.
- A `make_console()` helper that returns a Rich `Console` configured from the
  active policy.
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

`tasks show` currently emits markdown. The initial implementation can keep that
shape. If color is added there, it should only happen through the style registry
and should preserve a no-color default.

## JSON Output Convention

Use `--format table|json` as the canonical output option for read/query/report
commands. `OUTPUT_FORMATS = ("table", "json")` already exists and should remain
the central constant for that convention.

Commands that already follow this convention include many `entity`, `graph`,
`inquiry`, `datasets`, `tasks list`, `feedback list`, `project index`, and
`health` paths.

Some commands currently use `--json`, including DAG commands and selected
artifact/package commands. These can remain supported. When those commands are
touched, they may add `--format json` as the canonical spelling while preserving
`--json` as an alias if doing so does not create ambiguous Click behavior.

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
it. JSON paths should put warnings in structured fields where the command already
has a payload shape; otherwise warnings may remain on stderr.

## Testing

Add focused tests for the implementation slice:

1. Root `--color` accepts only `never`, `auto`, and `always`.
2. Default CLI output from a colorized command contains no ANSI escape sequences.
3. `--color=always` enables ANSI style output for at least one representative
   command, such as `tasks list`.
4. `--color=never` suppresses Rich markup and ANSI output from `health`.
5. JSON output from commands touched by the style work remains unchanged in
   structure and contains no ANSI escape sequences.
6. Entity-reference style helpers render unknown kinds without raising.

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

# CLI Behavior Convention

Science commands should make their scope, write target, and automation contract
obvious from help text, docs, and command output. This convention defines the
baseline behavior for new commands and the preferred target when existing command
families are cleaned up.

## Command Scope

Commands should state which project or store they operate on:

- Use `--project-root PATH` for commands that operate on a Science project root.
- Use `--root PATH` only for narrow scanner-style commands or existing commands
  that already expose it.
- Use domain-specific names when the target is not a project root, for example
  `--commons-root`, `--runs-dir`, `--report-dir`, or `--out`.
- Do not silently fall back to a different project when a caller supplied an
  explicit path. Fail early with a clear error.

Existing commands are not required to rename flags immediately. New commands
should prefer the names above unless the command family already has a stronger
local convention.

## Write Classes

Every command family should be understandable in terms of write class:

| Write class | Contract |
|---|---|
| Read-only | Prints diagnostics, summaries, candidate plans, or reports without modifying project files. |
| Source-write | Writes source-authored records that should be reviewed and committed. |
| Generated-write | Writes derived files that can be rebuilt from source records. |
| External-write | Writes outside the current project, such as a global registry or commons store. |
| Mixed | Contains subcommands with different write classes; subcommand help must clarify the target. |

When a command writes files, output should name the files or directories it
changed. When it does not write files, help text or terminal output should make
read-only behavior explicit when ambiguity is likely.

## Output Formats

Use output formats consistently:

- `--format json` is for automation and should emit machine-readable JSON only
  on stdout.
- `--format table` is for human terminal review.
- `--format text` is for prose or summary output that is not naturally tabular.
- Legacy `--json` flags may remain, but new multi-format commands should prefer
  `--format`.
- Diagnostics intended for humans during a JSON run should go to stderr or be
  represented structurally in the JSON payload.

If a command can be used in scripts, prefer stable field names in JSON and avoid
embedding presentation-only strings as the only source of status.

## Report-Then-Apply

Commands that perform broad, risky, or hard-to-review changes should separate
planning from mutation:

1. Default to a read-only report when feasible.
2. Require `--apply`, `--write`, or a similarly explicit flag for mutation.
3. Print enough detail in the report for a reviewer to understand what will
   change.
4. After applying, print what changed and any follow-up validation command.

Use `--apply` when the command applies a prepared or computed plan. Use `--write`
when the command writes direct output such as a generated file. Use `--fix` only
for conservative repairs with narrow, documented behavior.

Examples of the pattern:

- `science entities archive` reports first and relocates files with `--apply`.
- `science entities consolidate scaffold/apply` splits decision creation from
  member relocation.
- `science data audit --fix` is intentionally narrow and documented as a
  conservative fixer.

## Migration And Exploratory Labels

Migration-only commands should say what old state they migrate and what current
surface replaces it. Exploratory commands should say why their writes are not
the normal durable path.

Use these labels consistently in docs and help text:

| Label | Use |
|---|---|
| Migration-only | For commands that move legacy project state into the current model. |
| Legacy | For compatibility surfaces that should not be used for new workflows. |
| Exploratory | For commands useful in experiments or manual diagnostics but not normal durable authoring. |

For example, `science data-package` is a legacy migration surface, while
`science graph add ...` is exploratory graph surgery. Durable project knowledge
should normally be authored through source files and then materialized with
`science graph build`.

## Error Handling

Prefer fail-early behavior:

- Invalid enum values should be rejected by the CLI parser or explicit
  validation.
- Missing required files should raise a command error rather than silently
  producing an empty report.
- Ambiguous write targets should require a clearer flag or argument.
- If a command detects stale derived state, it should say which rebuild command
  refreshes that state.

Avoid silent fallbacks that make a command appear successful while using a
different project root, graph, registry, or data source than the caller intended.

## Documentation Requirements

New command families or substantial command changes should update the nearest
durable docs:

- User-facing workflow semantics belong in `docs/user-guide/`.
- Cross-command behavior rules belong in `docs/conventions/`.
- Repeatable maintenance recipes belong in `docs/process/`.
- Temporary implementation details belong in plans/specs until promoted.

When a command is migration-only, legacy, exploratory, or external-write, the
docs should say so close to the first mention of the command.

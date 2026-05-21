# `science validate`

`science validate` is the canonical CLI validator for a Science project. The
managed `validate.sh` project artifact is now a small shell shim that delegates
to this command.

## Synopsis

```bash
science validate [--verbose] [--strict] [--format text|json] [--fail-on TIER] [--project-root PATH]
```

Run from a project root:

```bash
science validate
science validate --format json
science validate --strict --verbose
science validate --project-root ~/d/example-project
```

## Flags

| Flag | Meaning |
|---|---|
| `--verbose` | Enables verbose context for checks that support it. |
| `--strict` | Enables strict advisory checks. Strict mode may add warnings, but warnings still do not fail the command (unless their rule is gated by `--fail-on`/`code_gate`). |
| `--format text|json` | Selects terminal text output or machine-readable JSON output. Default: `text`. |
| `--fail-on TIER` | Exit `1` when any finding gated at `TIER` (or a lower tier) is present. Tiers (cumulative): `report` (default, never blocks), `ghost-files`, `decision-bearing-orphans`, `hygiene`. Overrides `code_gate` in `science.yaml`. |
| `--project-root PATH` | Validates the selected Science project root instead of the current working directory. |

The root CLI also accepts the shared `--color never|auto|always` option before
the command, for example `science --color never validate`.

## Exit Codes

Validation exits `0` when there are no `error` results **and** no findings are gated by the active `--fail-on` tier (or `code_gate` in `science.yaml`). Warnings alone do not fail the command — including warnings under `--strict` — **unless** their rule is gated. It exits `1` when one or more `error` results are present, or when a gated finding is present. Invocation errors (such as an invalid project root) use Click's normal non-zero behavior; an unknown gate tier in `code_gate` is reported as a clean error.

## Severity Model

Results use three severities:

| Severity | Meaning | Exit impact |
|---|---|---|
| `error` | A blocking validation failure. | Causes exit code `1`. |
| `warn` | A non-blocking issue that should be reviewed. | Does not fail the command — unless its rule is gated by `--fail-on`/`code_gate`. |
| `info` | A diagnostic or advisory note. | Does not fail the command. |

`--strict` enables strict advisory warnings; it does not promote `warn` results to `error`.

## Code-file registration & the `--fail-on` gate ladder

### Code-file discovery

The code-files check walks every `code_roots` declaration resolved from `science.yaml` (defaulting to the profile's code directory) and inspects each discovered file for a `# science:code … # science:end` metadata block. All findings are `warn` severity — `validate` is report-only by default; only an active gate makes them fail.

### Code-file rules

| Rule | Meaning |
|---|---|
| `code.ghost` | An in-scope code file with no `# science:code … # science:end` block. |
| `code.malformed-block` | A block is present but unterminated, non-mapping, or contains invalid YAML. |
| `code.metadata-gap` | A valid block whose `status` field is missing or not one of `exploratory`, `workflow-owned`, `library`, or `retired`; or whose `task_ids` is present but not a list. |
| `code.unresolved-task` | A `task_ids` entry that resolves to no task in `tasks/`. |
| `code.uncommitted` | A valid block whose file has no committed content date (untracked or never committed), so commit-based freshness checks would not see it. |
| `code.unreadable` | A discovered file that could not be read (deleted or renamed mid-run, or a permission/IO error). This rule is ungated; it surfaces an anomaly without ever blocking a run. |

### The `--fail-on` gate ladder

The gate ladder uses four ordered, cumulative tiers. Each tier includes all rules from lower tiers:

| Tier | Rules included |
|---|---|
| `report` | _(default)_ No rules are gated; `validate` is always report-only. |
| `ghost-files` | `code.ghost` |
| `decision-bearing-orphans` | `code.ghost` + rules for files whose metadata ties them to decisions but with no committed record (arriving in a follow-up; the tier name ships now so the grammar is stable). |
| `hygiene` | All `code.*` rules except `code.unreadable`. |

Set the active tier with `--fail-on TIER` on the command line, or with `code_gate: TIER` in `science.yaml`. The `--fail-on` flag overrides `code_gate`. Supplying an unknown tier name is a clean error.

## JSON Output Schema

`--format json` emits a single JSON object:

```json
{
  "summary": {"errors": 0, "warnings": 1, "infos": 0},
  "results": [
    {
      "severity": "warn",
      "path": "doc/example.md",
      "line": 12,
      "message": "example warning",
      "rule": "example.rule",
      "task": "task:t001"
    }
  ]
}
```

Top-level fields:

| Field | Type | Meaning |
|---|---|---|
| `summary.errors` | integer | Number of `error` results. |
| `summary.warnings` | integer | Number of `warn` results. |
| `summary.infos` | integer | Number of `info` results. |
| `results` | array | Ordered validation results. |

Each result is the serialized `Result.to_dict()` shape:

| Field | Type | Meaning |
|---|---|---|
| `severity` | `"error"`, `"warn"`, or `"info"` | Result severity. |
| `path` | string or null | Project-relative path when the result belongs to a file. |
| `line` | integer or null | One-based line number when available. |
| `message` | string | Human-readable validation message. |
| `rule` | string or null | Stable rule identifier when available. |
| `task` | string or null | Related task reference when available. |

## Environment Variables

| Variable | Meaning |
|---|---|
| `NO_COLOR` | Disables terminal color output through the shared Science CLI color policy. |
| `SCIENCE_VALIDATE_DISABLE_SIDECAR=1` | For `science validate`, disables both Python sidecar discovery and deprecated legacy `validate.local.sh` discovery. |

`FORCE_COLOR` and the root `--color` option are handled by the shared Science
CLI styling layer.

## Discovery

`validate.sh` is the managed project artifact shim that delegates to `science validate`.
Use `science validate` directly when you need structured output or a
project-root-selectable CLI entrypoint; use `validate.sh` when a project or tool
expects the managed artifact path.

`validate_local.py` is imported by default when it exists in the project root.
If `SCIENCE_VALIDATE_DISABLE_SIDECAR` is set to `1`, `science validate` skips Python sidecar discovery and deprecated legacy `validate.local.sh` discovery, including legacy sidecar deprecation warnings.
Because `validate.sh` delegates to `science validate`, this environment variable affects validation reached through the shim as well.
Python sidecars register hooks with `science_tool.validate.hook()` for `pre_validation`, `extra_checks`, or `post_validation`.

# `science validate`

`science validate` is the additive Python CLI validator for a Science project.
During Phase 1, the managed bash `validate.sh` remains the canonical validator
for project validation; use this command when you need structured output,
Python sidecar hooks, or a project-root-selectable CLI entrypoint.

## Synopsis

```bash
science validate [--verbose] [--strict] [--format text|json] [--project-root PATH]
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
| `--strict` | Enables strict advisory checks. Strict mode may add warnings, but warnings still do not fail the command. |
| `--format text|json` | Selects terminal text output or machine-readable JSON output. Default: `text`. |
| `--project-root PATH` | Validates the selected Science project root instead of the current working directory. |

The root CLI also accepts the shared `--color never|auto|always` option before
the command, for example `science --color never validate`.

## Exit Codes

Validation exits `0` when there are no `error` results. Warnings alone do not fail the command, including warnings emitted under `--strict`.

Validation exits `1` when one or more `error` results are present. Invocation
errors, such as an invalid project root, use Click's normal non-zero command
error behavior.

## Severity Model

Results use three severities:

| Severity | Meaning | Exit impact |
|---|---|---|
| `error` | A blocking validation failure. | Causes exit code `1`. |
| `warn` | A non-blocking issue that should be reviewed. | Does not fail the command. |
| `info` | A diagnostic or advisory note. | Does not fail the command. |

`--strict` enables strict advisory warnings; it does not promote `warn` results to `error`.

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
| `SCIENCE_VALIDATE_DISABLE_SIDECAR=1` | Skips `validate_local.py` discovery. |

`FORCE_COLOR` and the root `--color` option are handled by the shared Science
CLI styling layer.

## Discovery

`validate.sh` remains the managed bash canonical validator during Phase 1.
`science validate` is additive and should not be treated as a replacement for
the managed script until the migration plan says otherwise.

`validate_local.py` is imported by default when it exists in the project root.
If `SCIENCE_VALIDATE_DISABLE_SIDECAR` is set to `1`, Python sidecar discovery is skipped.
Python sidecars register hooks with `science_tool.validate.hook()` for `pre_validation`, `extra_checks`, or `post_validation`.

# CLI Flag Drift Audit

**Date:** 2026-07-01

**Scope:** Read-only audit of registered Click options across the `science` CLI,
focused on the conventions in
[`../../conventions/cli-behavior.md`](../../conventions/cli-behavior.md).

## Method

The inventory was generated from the registered Click command tree, not by
grepping docs. It walks `science_tool.cli:main`, records every `click.Option`,
and groups long flags by command path.

The current CLI exposes 921 option declarations and 265 unique long flags. The
most common long flags are `--format` (114), `--project-root` (63), `--path`
(53), `--status` (31), `--root` (29), `--json` (22), and `--apply` (20).

## Summary

The CLI is more consistent than the raw size suggests: most machine-readable
commands use `--format`, and many risky mutations already follow report-then-apply
semantics. The main drift is in target-path naming and historical JSON aliases.
This should be cleaned up gradually through docs/help text, aliases, and tests,
not by breaking existing command names.

## Target And Path Flags

| Flag | Count | Current use | Recommended action |
|---|---:|---|---|
| `--project-root` | 63 | Main project-root selector for many newer commands. | Keep as canonical for new project-scoped commands. |
| `--path` | 53 | Mostly graph path, dataset path, or explicit output/input path depending on family. | Keep only when the target is not the project root; help text must name the target. |
| `--root` | 29 | Common in scanner-style and annotation commands. | Accept for scanner-style commands; avoid for new project-scoped commands unless local family convention is strong. |
| `--project` | 16 | Mixed use: project root in some older commands, project name/filter/spec in others. | Highest ambiguity. Do not expand; clarify help text before any aliasing. |
| `--output` | 15 | Output file or directory. | Keep for explicit output paths; prefer `--out` only where already established. |
| `--out` | 5 | Short output path flag in package/export/scaffold commands. | Keep existing; prefer one spelling within a command family. |
| `--repo-root` | 2 | Repo-level root for advisory audits/walk generation. | Keep for repo root when distinct from project root. |
| `--runs-dir` | 1 | Workflow-run entity directory. | Good domain-specific name. |
| `--report-dir` | 1 | QA report destination directory. | Good domain-specific name. |
| `--commons-root` | 0 | Named in the convention as a future domain-specific target. | Use if future commands need explicit commons root selection. |

### Finding FD1: `--project` Is Ambiguous

`--project` currently means different things in different command families:
project root in older DAG/data/entity commands, named registered project in
commons commands, feedback project filter, and benchmark project specs.

This is the clearest real drift. Existing commands should not be renamed
opportunistically, but new commands should avoid `--project` unless the value is
a project identifier rather than a filesystem root.

**Recommended cleanup:** audit the 16 `--project` users and split them into:

- filesystem root candidates for a future `--project-root` alias;
- project id/name filters that should keep `--project`;
- multi-project specs that need local documentation.

### Finding FD2: `--path` Is Broad But Usually Local

`--path` appears 53 times. Most uses are not project roots; they select graph
files, dataset paths, explicit entity paths, or command-specific artifacts. That
is acceptable, but it makes help text important.

**Recommended cleanup:** do not rename `--path` broadly. Instead, add tests or
review checks for ambiguous help text when new `--path` options are introduced.

## Output Format Flags

| Flag | Count | Current use | Recommended action |
|---|---:|---|---|
| `--format` | 114 | Primary multi-format selector. | Canonical for new commands with more than one output mode. |
| `--json` | 22 | Legacy/convenience boolean JSON switch. | Keep as compatibility alias where present; avoid for new multi-format commands. |

### Finding FD3: `--json` Is Common Enough To Preserve As Alias

Twenty-two commands still expose `--json`. Some command families already expose
both `--format` and `--json` and document `--json` as a convenience alias. That
is the right transition shape.

**Recommended cleanup:** when touching a `--json`-only command that naturally has
multiple output modes, add `--format` and keep `--json` as an alias. Do not remove
`--json` in the same change.

## Mutation Gates

| Flag | Count | Current use | Recommended action |
|---|---:|---|---|
| `--apply` | 20 | Primary report-then-apply mutation gate. | Canonical for applying computed plans. |
| `--force` | 9 | Override safety checks or overwrite files. | Keep rare; pair with clear help and sometimes `--yes`. |
| `--check` | 6 | Mixed: CI gate, read-only status, health/prose check selector. | Clarify help; avoid for mutation semantics. |
| `--write` | 5 | Write generated output or direct safe patch. | Use for direct file output, not broad plan application. |
| `--dry-run` | 5 | Explicit preview mode. | Good when default behavior writes, or when command family already uses the term. |
| `--fix` | 3 | Narrow conservative repairs. | Keep only for documented narrow repairs. |
| `--yes` | 1 | Confirmation paired with force. | Good for high-risk overwrite workflows. |

### Finding FD4: Mutation Gates Are Mostly Healthy

The broad pattern already matches the convention: risky broad changes generally
use `--apply`, direct writes use `--write`, conservative repair commands use
`--fix`, and some commands expose explicit `--dry-run`.

The risk is semantic drift in smaller flags:

- `--check` can mean "run only selected checks", "CI fixpoint check", or "include
  current status".
- `--write` can mean generated output or an in-place patch.
- `--force` can mean overwrite, bypass a safety warning, or allow unresolved
  blockers.

**Recommended cleanup:** do not normalize these mechanically. Instead, improve
help text and add focused tests when a command's meaning is unclear.

## Command Family Notes

### Annotation

`science annotate` uses repeated `--root` and `--format` options across many
subcommands. This is internally consistent, but it diverges from the newer
project-root convention.

**Recommendation:** keep the family-local convention for now. If the annotation
CLI is later reorganized, consider a family-level root option or `--project-root`
alias in a single coordinated change.

### DAG

`science dag` uses `--project` for filesystem project roots and retains `--json`
aliases beside `--format` for some commands.

**Recommendation:** document as older family-local convention. If touched,
prefer adding `--project-root` aliases while preserving `--project`.

### Commons

`science commons` uses several `--json` flags and `--project` for named
registered project overlays rather than filesystem roots.

**Recommendation:** keep `--project` here because it is identifier-like, not a
path. If multi-format output grows, add `--format` while preserving `--json`.

### Graph

`science graph` uses `--path` extensively for graph file paths and
`--project-root` for source-aware graph operations.

**Recommendation:** this distinction is useful. Do not collapse it.

## Low-Risk Follow-Ups

1. Add a small CLI metadata test that prevents new project-root selectors from
   using `--project` unless explicitly allowlisted.
   **Status:** Added in `science/tests/test_cli_surface_contract.py`.
2. Add a test or lint for new commands that expose `--json` without `--format`,
   with an allowlist for legacy/convenience aliases.
   **Status:** Added in `science/tests/test_cli_surface_contract.py`.
3. Improve help text for the 16 `--project` users before adding aliases.
   **Status:** Addressed by `science/tests/test_cli_surface_contract.py` and
   help-text updates for the previously blank or ambiguous `--project` options.
4. Add `--project-root` aliases for older filesystem-root commands only when the
   command family is already being touched.
5. Keep command renames out of the first cleanup slice. The first implementation
   should be additive and compatibility-preserving.

## Disposition

This audit completes backlog item B4. The next implementation choice should be
between:

- a small metadata guard for future command additions; or
- a focused code simplification slice that extracts one command family from
  `science/src/science_tool/cli.py` without changing behavior.

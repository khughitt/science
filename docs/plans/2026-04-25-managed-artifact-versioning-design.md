# Managed Artifact Versioning

**Date:** 2026-04-25
**Status:** Draft
**Author:** keith.hughitt@gmail.com

## Motivation

Science projects receive framework behavior in two different ways:

1. Some artifacts are resolved centrally at runtime, such as commands, skills,
   and framework templates.
2. Some artifacts are copied into each project, such as `validate.sh`.

Runtime-resolved artifacts update naturally when the Science framework changes.
Copied artifacts do not. They can drift until a project starts enforcing old
rules, missing new checks, or producing confusing validation output.

The immediate example is `mm30/validate.sh`: it is older than the canonical
`science/scripts/validate.sh`, so it lacks newer behavior around `.env`
loading, `science-tool` availability, hypothesis `phase:` validation, and graph
audit handling. This is not a project-specific mistake; it is a lifecycle gap
for copied Science artifacts.

Science also has broader versioning concerns. `science.yaml`, project docs,
tasks, graph sources, generated graphs, package schemas, templates, skills, and
commands all evolve over time. A single "update everything" command would be
unsafe because many of those files are project-owned research state, not
replaceable framework files. The versioning model needs to distinguish artifact
ownership before it automates anything.

## Goal

Add a small, explicit managed-artifact versioning system that can detect and
update copied framework artifacts without touching project-owned research state.

The first managed artifact is `validate.sh`. The design must leave room for
future copied artifacts, but v1 should only automate artifacts with clear
framework ownership and safe replacement semantics.

## Non-Goals

- Do not add a blanket project auto-updater.
- Do not rewrite project-owned docs, tasks, hypotheses, entities, datasets, or
  `science.yaml` as part of copied-artifact updates.
- Do not copy commands, skills, or framework templates into projects merely to
  version them.
- Do not add legacy compatibility layers for old validator behavior.
- Do not silently overwrite locally modified managed artifacts.

## Artifact Taxonomy

### 1. Runtime-Resolved Framework Artifacts

These artifacts live in the Science framework and are resolved at runtime.
Projects should not copy them unless they are creating local overrides.

Examples:

- `commands/*.md`
- `skills/**`
- `codex-skills/**`
- `templates/*.md`
- ontology extractor scripts and framework references used by commands

Versioning behavior:

- No per-project version check is needed.
- Updates come from updating the installed Science framework.
- Project-local `.ai/prompts/` and `.ai/templates/` remain overrides, not
  managed copies. They are project-owned and should not be overwritten.

### 2. Copied Managed Framework Artifacts

These artifacts are framework-owned but intentionally copied into projects
because they need to be runnable from the project root or visible to non-plugin
tools.

Initial v1 artifact:

- `validate.sh`

Potential future artifacts:

- small bootstrap scripts that are copied into projects
- generated wrapper scripts whose canonical content is owned by Science

Versioning behavior:

- Each managed copy includes a machine-readable artifact header.
- `science-tool` can check whether the copy matches the canonical artifact.
- `science-tool` can update the copy when it is unchanged or safely
  replaceable.
- If the project copy has local edits, the tool reports `locally_modified` and
  refuses to overwrite unless an explicit force flag is used.

### 3. Project-Owned Migratable Artifacts

These are owned by the project, but their schema or conventions can evolve.

Examples:

- `science.yaml`
- `AGENTS.md`
- `CLAUDE.md`
- `pyproject.toml`
- `.env`
- project-local `.ai/**` overrides
- `knowledge/sources/**`
- `specs/**`
- `doc/**`
- `tasks/**`

Versioning behavior:

- These use schema/layout migration commands, not copied-artifact replacement.
- `layout_version` in `science.yaml` remains the project layout/schema signal.
- Migration commands should be explicit, previewable, and scoped to a named
  migration.
- The managed-artifact checker may warn that a project layout is old, but it
  must not rewrite project-owned files.

### 4. Generated Or Derived Artifacts

These are rebuilt from project-owned inputs or framework code.

Examples:

- `knowledge/graph.trig`
- graph revision metadata
- DAG render outputs such as `*-auto.dot`, `*-auto.png`, numbered DOT files
- research package outputs
- generated visualization notebooks copied during graph build

Versioning behavior:

- These use rebuild, diff, freshness, or drift checks.
- They are not managed copied artifacts.
- If their generation code changes, the project should run the relevant
  regenerate command, not update a copied file by version.

### 5. External Dependencies And Tool Packages

These are versioned by the language/package ecosystem.

Examples:

- `science-tool`
- `science-model`
- `uv.lock`
- Python package dependencies
- third-party ontology releases

Versioning behavior:

- Use `uv` and normal package lock/update semantics.
- The project artifact checker may report the active `science-tool` version or
  path, but should not update dependencies itself.

## Managed Artifact Header

Each copied managed artifact should carry a small header near the top of the
file:

```bash
# science-managed-artifact: validate.sh
# science-managed-version: 2026.04.25
# science-managed-source-sha256: <canonical-content-hash>
```

Rules:

- The hash covers the canonical artifact body after exact managed-content
  normalization: convert `\r\n` and `\r` to `\n`, then elide the value of the
  `science-managed-source-sha256` line.
- No other normalization is performed. Trailing whitespace, byte order marks,
  and all non-hash header content remain significant.
- The artifact name must match a known artifact in the `science-tool` artifact
  registry.
- Absence of the header means `untracked`, not automatically outdated.

The date-like version is intentionally simple. It is an artifact contract
version, not the package version. If a file changes twice in a day, append a
suffix such as `2026.04.25.2`.

## Canonical Artifact Registry

`science-tool` owns a small internal registry of managed artifacts.

For each artifact, the registry records:

- artifact name
- destination path relative to project root
- canonical source content
- version
- source hash
- previous managed hashes, when older versions are still recognized
- file mode, when relevant
- replacement policy

For v1:

```yaml
artifacts:
  - name: validate.sh
    destination: validate.sh
    mode: "0755"
    comment_prefix: "#"
    replacement_policy: managed-copy
```

The canonical `validate.sh` source should be available to `science-tool` as
package data. `scripts/validate.sh` remains the framework-visible source used by
Claude plugin commands, but tests must ensure the packaged artifact and
`scripts/validate.sh` stay hash-equivalent under `managed_content_hash`.
v1 uses `#` comment headers. `ArtifactDefinition.comment_prefix` exists so a
future managed artifact can declare a different comment marker deliberately
rather than relying on shell-script assumptions.

Direct bootstrap copying is supported. If a command copies
`${CLAUDE_PLUGIN_ROOT}/scripts/validate.sh` into a project before
`science-tool` is available, the file may contain the literal sentinel hash line
from the canonical source. Because the managed hash elides the hash-line value,
that direct copy still checks as `current` once `science-tool` is installed.

### Bumping A Managed Artifact

When changing a canonical managed artifact, maintainers must preserve the
outdated path for existing projects:

1. Before editing, compute the old canonical `managed_content_hash`.
2. Edit the canonical artifact and bump `science-managed-version`.
3. Add the old hash to the artifact definition's `previous_hashes`.
4. Copy or regenerate the packaged artifact data.
5. Run the packaged-vs-root hash-equivalence test.
6. Run a check against at least one downstream project that still has the old
   copy and verify it reports `outdated`, not `locally_modified`.

This manual checklist is v1. A future helper command,
`science-tool project artifacts release validate.sh`, can automate the old-hash
capture from git history if the process becomes repetitive.

## CLI Design

Add a `science-tool project artifacts` command group.

### Check

```bash
science-tool project artifacts check --project-root .
science-tool project artifacts check --project-root . --format json
science-tool project artifacts check --project-root . --strict
```

For each known artifact, report:

- `missing`: destination file does not exist
- `current`: file matches the canonical content/version
- `outdated`: file has a recognized managed header and content hash matching a
  previous known managed version
- `locally_modified`: file has a recognized managed header but content does
  not match the current canonical hash or any previous known managed hash
- `untracked`: file exists at the destination but lacks a managed header

Table output should include artifact name, status, expected version, current
version, and destination path. JSON output should be stable for commands and
future status checks.

By default, `check` exits `0` after reporting statuses. With `--strict`, it
exits non-zero when any artifact is not `current`. This makes the command usable
from CI, pre-commit hooks, or a future `validate.sh` staleness check without
making interactive checks noisy.

### Update

```bash
science-tool project artifacts update validate.sh --project-root .
science-tool project artifacts update --all --project-root .
science-tool project artifacts update validate.sh --project-root . --force --yes
```

Update behavior:

- `missing`: write the canonical artifact.
- `current`: no-op.
- `outdated`: replace with canonical artifact.
- `locally_modified`: refuse unless `--force --yes` is passed.
- `untracked`: refuse unless `--force --yes` is passed.

The command prints the old status and final status for each selected artifact.
It should fail early if both an artifact name and `--all` are omitted.

Before overwriting any existing non-current file, `update` writes a backup next
to the destination, using `<filename>.pre-update.bak` and a numeric suffix if
that backup path already exists. This applies to forced overwrites and to normal
`outdated` replacement.
Project creation/import guidance should add `*.pre-update*.bak` to `.gitignore`
so backup files appear only when a user deliberately force-adds them.

`update` must refuse to write outside a Science project root unless
`--no-project-check` is passed. A Science project root is a directory containing
`science.yaml`. The escape hatch exists for early bootstrap and tests, but normal
project commands should create or update `science.yaml` before installing copied
managed artifacts.

For `--all`, update should attempt every selected artifact and report
per-artifact status. It should return non-zero overall if any artifact failed,
instead of stopping at the first failure and hiding the remaining statuses.

### Diff

```bash
science-tool project artifacts diff validate.sh --project-root .
```

Diff behavior:

- Show a unified diff between the project copy and canonical content.
- For missing files, report that no project copy exists.
- For current files, report that no differences exist.

This keeps the update path explicit and reviewable.

## Integration Points

### `validate.sh`

The validator should gain the managed-artifact header and be distributed through
the artifact registry. New project creation and import should copy the managed
artifact, not perform ad hoc file copying without version metadata.

Validation should not self-update. Running `bash validate.sh` may report that it
is outdated if the checker is available, but it must not mutate project files.
The mutation path belongs to `science-tool project artifacts update`.

### `create-project` And `import-project`

The command docs should stop saying "copy `scripts/validate.sh`" as a bare file
operation. They should instruct agents to install the managed artifact:

```bash
science-tool project artifacts update validate.sh --project-root .
```

For bootstrap cases where `science-tool` is not installed yet, commands may copy
the framework artifact directly, but the copied file must include the managed
header so future checks work.

### `status`, `health`, And `next-steps`

These commands can mention stale managed artifacts, but they should not update
them automatically.

Recommended behavior:

- `science-tool health` includes managed artifact status.
- `/science:status` may summarize "1 managed artifact outdated:
  `validate.sh`".
- `/science:next-steps` may recommend running the update command when artifacts
  are stale.

v1 implements `science-tool health` integration directly. Slash-command
docs can consume that health output in a follow-up; they must not gain a second
independent artifact classifier.

## Artifact Impact Matrix

| Artifact class | Examples | Managed by version check? | Update mechanism |
|---|---|---:|---|
| Runtime-resolved framework | `commands/`, `skills/`, `templates/`, `codex-skills/` | No | Update Science framework |
| Copied managed framework | `validate.sh` | Yes | `science-tool project artifacts update` |
| Project manifest/schema | `science.yaml`, `layout_version` | No | Explicit migrations |
| Agent guides | `AGENTS.md`, `CLAUDE.md` | No in v1 | Import/migration guidance only |
| Project AI overrides | `.ai/prompts/`, `.ai/templates/` | No | Project-owned edits |
| Research/source docs | `doc/`, `specs/`, `tasks/` | No | Project-owned edits/migrations |
| Knowledge sources | `knowledge/sources/**` | No | Entity/schema migrations |
| Generated graph | `knowledge/graph.trig` | No | Rebuild/update graph |
| DAG generated outputs | DOT/PNG/reference outputs | No | DAG render/number/audit commands |
| Packages/dependencies | `science-tool`, `science-model`, `uv.lock` | No | `uv` dependency management |

## Migration Strategy

1. Add the artifact registry with only `validate.sh`.
2. Add check, diff, and update CLI commands.
3. Add headers to the canonical validator and to newly copied validators.
4. Update `create-project` and `import-project` docs.
5. Update project health/status surfaces to report stale managed artifacts.
6. Use `mm30` as the first real downstream update test.

Existing projects without a header will show `untracked` for `validate.sh`.
That is intentional. The first update requires explicit user action because an
untracked root script might contain local project logic.

## Risks

### Risk: managed headers make shell scripts noisy

The header is three comment lines near the top of the file. Shell ignores it,
and the operational benefit outweighs the small visual cost.

### Risk: projects have intentionally customized validators

The checker reports these as `untracked` or `locally_modified` and refuses to
overwrite without `--force --yes`. Even then, it writes a `.pre-update.bak`
backup before replacement. The project can keep the custom file if it wants.

### Risk: canonical artifact duplication

If `scripts/validate.sh` and packaged `science-tool` artifact data diverge, the
updater becomes another source of drift. Add a test that compares them. If this
continues to be awkward, move the canonical source fully into package data and
generate `scripts/validate.sh` from it.

Tracked follow-up: make `scripts/validate.sh` a committed generated artifact
from the package-data source, with a regeneration command or build hook. That
would make the packaged copy the single source of truth while preserving the
plugin-visible script path.

### Risk: artifact versioning expands too broadly

The taxonomy is the guardrail. Only framework-owned copied files with safe
replacement semantics belong in the managed-artifact registry. Everything else
uses migrations, rebuilds, or package management.

## Follow-Up Work

- Track a follow-up to make `scripts/validate.sh` a generated committed artifact
  from the packaged canonical validator. v1 accepts two checked-in copies with a
  hash-equivalence test; the follow-up removes that duplication once the managed
  artifact mechanism has proven stable.

## Open Decisions

### Should `validate.sh` self-report staleness?

Recommendation: defer. Start with explicit `project artifacts check` and
project health integration. Self-reporting requires the script to locate
`science-tool` and compare itself on every validation run, which may add noise
and failure modes to the validator.

### Should `AGENTS.md` become a managed artifact?

Recommendation: no for v1. It contains project-specific operational guidance
and should be treated as project-owned. Future import tooling can lint for
recommended sections, but replacement semantics are unsafe.

### Should templates copied into `.ai/templates/` be managed?

Recommendation: no. `.ai/templates/` means "project override." If a project
chooses to fork a framework template there, it owns the fork.

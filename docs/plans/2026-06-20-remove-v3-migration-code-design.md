# Remove One-Shot v2→v3 Migration Code & Docs

## Status

Proposed.

## Context

All managed Science projects have completed the v2→v3 layout/identity
migration. The one-shot migration code, its CLI commands, tests, and the
migration guides remain in the tree. They no longer have a job to do, and they
make the codebase and docs harder to read: a contributor cannot easily tell
which "migration" code is dead one-shot tooling and which is live
infrastructure.

The word "migration" currently spans three unrelated things:

1. **One-shot v2→v3 migrators** — tooling that exists only to move a pre-v3
   project to v3. Dead now that every project is v3.
2. **Generic managed-artifact update runner** (`project_artifacts/migrations/`
   + `project_artifacts/update.py`) — runs `project_action` steps when a managed
   file such as `validate.sh` gets a new canonical version. Ongoing
   infrastructure; nothing to do with v3.
3. **Identity/reference audit utilities** (`graph/migrate.py`'s
   `audit_project_sources` / `AuditRow` / `_audit_*`, and
   `entity_migrations.audit_identifiers`) — read-only audits that
   `science validate`, `health`, `materialize`, and `freshness` depend on at
   runtime.

Only category 1 is dead. Categories 2 and 3 stay.

## Decision

Remove the one-shot v2→v3 migration modules, their CLI commands, their tests,
and the migration guide docs. Keep the generic managed-artifact update runner
and all audit utilities. Where a module mixes one-shot migration with live
audit code (`graph/migrate.py`, `entity_migrations.py`), split surgically and
keep the file.

Clean break: no compatibility shims, no retired-command stubs. Removed CLI
commands disappear entirely.

This is a single branch (`remove-v3-migration-code`) merged into `main`.

Leave `graph/migrate.py` named as-is this pass even though it becomes
predominantly an audit module; a rename is deferred to avoid churn.

## Scope

### A. Remove outright

Module + its CLI command (in `cli.py` unless noted) + its tests:

| Module | CLI command removed | Tests removed |
|---|---|---|
| `science/src/science_tool/entity_layout_migration.py` | `science entities migrate` | `test_entity_layout_migration.py`, `test_migrate_local_kinds_integration.py` |
| `science/src/science_tool/datapackage_migrate.py` | datapackage migrate command | `test_data_package_migrate.py`, `test_data_package_migrate_e2e.py` |
| `science/src/science_tool/peers_migrate.py` | `science peers migrate` (in `peers_cli.py`) | `test_peers_migrate.py` |
| `science/src/science_tool/refs_migrate.py` | refs migrate command (in `refs_cli.py`) | `test_refs_migrate_cli.py`, `test_refs_migrate_paper.py` |
| `science/src/science_tool/tasks_id_migration.py` | tasks id migrate command | `test_tasks_id_migration.py` |
| `science/src/science_tool/graph/paper_dataset_migration.py` | command in `cli.py` | `test_paper_dataset_migration.py` |
| `science/src/science_tool/graph/project_model_migration.py` | command in `cli.py` | `test_project_model_migration.py` |
| `science/src/science_tool/graph/tags_migration.py` | command in `cli.py` | `test_tags_migration.py` |
| `science/src/science_tool/aspects/migrate.py` | aspects migrate command (in `aspects/cli.py` / `big_picture/cli.py`) | `test_aspects_migrate.py` |
| `scripts/migrate_downstream_conventions.py` (repo top-level) | — | — |

Also remove:

- `science/tests/test_layered_claim_migration.py` (tests the layered-claim
  migration removed in section B).
- `science/tests/test_graph_migrate.py` — verify it only exercises removed CLI
  migration commands; if it also covers audit behavior, move those cases to an
  audit test instead of deleting them.
- `science/tests/_fixtures/migration_add_phase.py` — remove only if used solely
  by removed tests; otherwise keep.

Before deleting each module, confirm its only non-test importers are the CLI
command being removed and other removed modules. `paper_dataset_migration` is
referenced by `validate/checks/dataset_influence.py`; confirm that reference is
to a still-needed symbol or update the check. (Suspected import-time-only;
verify during implementation.)

### B. Surgical split — `graph/migrate.py` (keep the file)

`audit_project_sources`, `AuditRow`, and the `_audit_*` helpers are imported by
`entities.py`, `graph/health.py`, `graph/materialize.py`, and
`graph/freshness.py`. These stay.

Remove only the one-shot layered-claim migration surface:

- `build_layered_claim_migration_report`
- `write_migration_report`
- `_merge_entities` and any helpers used only by the above
- the `cli.py` command (imported at `cli.py:42`) that calls them

Keep `LayeredClaimMigrationRow` only if still referenced by retained code;
otherwise remove it with the report builder.

### C. Surgical split — `entity_migrations.py` (keep the file)

- Keep `audit_identifiers` (ongoing identity audit).
- Remove `migrate_identifiers`, its private rewrite helper(s), and the
  `science entities migrate-identifiers` command (`cli.py:281`).
- Trim `test_entity_migrations.py` to the `audit_identifiers` cases only.

### D. Keep entirely (generic infrastructure, not v3)

- `project_artifacts/migrations/` (`__init__.py`, `bash.py`, `python.py`,
  `transaction.py`) — the managed-artifact migration runner.
- `project_artifacts/update.py`.
- Tests: `test_update_with_migration.py`, `test_update_no_migration.py`,
  `test_migration_runner.py`, `test_migration_bash.py`, `test_migration_python.py`.
- `graph/aggregate_retire.py` + `test_aggregate_retire_curie_migration.py`
  (live aggregate-triage).
- `test_graph_migrate_identity_audit.py` (tests the retained audit path).

### E. Docs

Delete:

- `docs/entity-layout-migration-guide.md`
- `docs/migration/` (all 7 files:
  `2026-05-19-validate-local-sh-porting-guide.md`,
  `2026-05-26-assembly-identity.md`, `2026-05-27-gene-crosswalk-identity.md`,
  `2026-05-27-protein-crosswalk-identity.md`, `managed-artifacts-template.md`,
  and any others present)
- `docs/audits/2026-06-06-layout-v3-migration-readiness-audit.md`

Leave `archive/**` and `docs/plans/**` untouched — they are the historical
record of past work. No current (non-archive, non-plan) doc links these files,
so no link fixup is required. Confirm with a final grep.

Before deleting `docs/migration/managed-artifacts-template.md`, confirm it is a
migration artifact and not a template the live managed-artifact update flow
consumes.

## Non-Goals

- Renaming `graph/migrate.py` to `graph/audit.py` (deferred).
- Touching `archive/**` or `docs/plans/**`.
- Removing or changing the managed-artifact update runner or any audit code.
- Adding retired-command stubs or deprecation messages.

## Risks & Mitigations

- **Mixed-module over-deletion** (`graph/migrate.py`, `entity_migrations.py`):
  mitigated by enumerating importers before editing and running the full test
  suite after.
- **Dangling CLI registration** after a module is removed: mitigated by a
  `science --help` smoke check across affected command groups.
- **A "migration" module is actually a live dependency** (e.g.
  `paper_dataset_migration` referenced by a validate check): mitigated by the
  per-module importer check in section A before deletion.

## Validation

```bash
# No references to any removed module remain in source:
rg "entity_layout_migration|datapackage_migrate|peers_migrate|refs_migrate|\
tasks_id_migration|paper_dataset_migration|project_model_migration|\
tags_migration|aspects\.migrate|migrate_identifiers|\
build_layered_claim_migration_report" science/src

# No current docs link the removed guides (archive/plans excluded):
rg "entity-layout-migration-guide|docs/migration/" \
  --glob '!archive/**' --glob '!docs/plans/**'

# Full suite green, no import errors:
uv run --frozen pytest science/tests

# CLI loads with no dangling registrations:
science --help
science entities --help
science peers --help

# Audit path still works end to end on a real project:
science validate
science graph build
```

## Alternatives Considered

- **Remove everything named "migration."** Rejected: would delete the
  managed-artifact update runner and break `science` managed-artifact updates.
- **Docs-only removal.** Rejected: leaves the dead one-shot code and CLI
  commands, which is the main source of confusion.
- **Retired-command stubs.** Rejected: compatibility layers are against project
  convention and preserve dead entry points.

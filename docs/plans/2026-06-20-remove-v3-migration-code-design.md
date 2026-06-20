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
code (`graph/migrate.py`, `entity_migrations.py`, `graph/paper_dataset_migration.py`),
split surgically: keep/relocate the live part, remove only the one-shot apply
code. Update retained legacy-shape guards to hard-error instead of pointing at
removed commands.

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
| `science/src/science_tool/graph/project_model_migration.py` | command in `cli.py` | `test_project_model_migration.py` |
| `science/src/science_tool/graph/tags_migration.py` | command in `cli.py` | `test_tags_migration.py` |
| `science/src/science_tool/aspects/migrate.py` | aspects migrate command (in `aspects/cli.py` / `big_picture/cli.py`) | `test_aspects_migrate.py` |
| `scripts/migrate_downstream_conventions.py` (repo top-level) | — | — |

Also remove:

- `science/tests/test_graph_migrate.py` — verify it only exercises removed CLI
  migration commands (project-id rewrite / `migrate-identifiers`); if it also
  covers retained audit or layered-claim-report behavior, move those cases to an
  audit test instead of deleting them.
- `science/tests/_fixtures/migration_add_phase.py` — remove only if used solely
  by removed tests; otherwise keep.
- Migration cases inside broader CLI suites that the per-module tests don't
  cover: `test_peers_cli.py` (the `test_peers_migrate*` cases, ~lines 583-786),
  `test_entities_cli.py` (the `entities migrate` / `migrate-identifiers` cases,
  ~line 459), and `test_aspects_cli.py` (`test_migrate_*`, ~lines 20-40). Remove
  these cases; keep the rest of each suite.

`test_layered_claim_migration.py` is **retained** (it covers the live
layered-claim report — see section B).

Before deleting each module, confirm its only non-test importers are the CLI
command being removed and other removed modules. (`graph/paper_dataset_migration.py`
is intentionally absent from this table — it has a live importer and is handled
by the surgical split in section B.)

### B. Surgical splits — keep the file, remove only one-shot apply code

#### `graph/migrate.py`

Most of this module is **live**, not one-shot:

- `audit_project_sources` / `AuditRow` / `_audit_*` — imported by `entities.py`,
  `graph/health.py`, `graph/materialize.py`, `graph/freshness.py`. **Keep.**
- `build_layered_claim_migration_report`, `write_migration_report`,
  `LayeredClaimMigrationReport` (and `LayeredClaimMigrationRow`) — back the live
  `layered_claim_migration` health check (`health.py:25,1755`) and the status
  display (`cli.py:4441+`). Despite the "migration" name this is ongoing
  claim-layer adoption reporting. **Keep.**

Remove only the one-shot **project-id rewrite (apply)** surface, which exists to
rename identifiers in a pre-v3 project and is tied to the removed
`science entities migrate-identifiers` command:

- `rewrite_project_ids_in_sources`
- `preview_project_id_rewrites`
- `write_local_sources`
- `_merge_entities` and helpers used only by the above

The implementation plan must confirm per-symbol (via importer analysis) that
each removed function is reachable only from the removed CLI command and other
removed code; anything also used by `audit_*` or the layered-claim report stays.

#### `graph/paper_dataset_migration.py`

`is_paper_dataset_role_conflict` is a live validation predicate used by
`validate/checks/dataset_influence.py`. Move/inline that predicate into the
validation layer (the check module or a `validate/_helpers`-style home), update
the import, then delete the one-shot planner (`plan_paper_dataset_migration`)
and the rest of the module, its CLI command, and `test_paper_dataset_migration.py`
(retaining or relocating any test coverage for the moved predicate).

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
- `test_layered_claim_migration.py` (tests the retained, live layered-claim
  report from section B).

### E. Docs

`docs/migration/` contains **5** files, not all of which are v3 migration.
Verified: only the files below have no live references in retained source.

Delete (no live references; one-shot v3 layout/identity migration):

- `docs/entity-layout-migration-guide.md`
- `docs/migration/2026-05-26-assembly-identity.md`
- `docs/migration/2026-05-27-gene-crosswalk-identity.md`
- `docs/migration/2026-05-27-protein-crosswalk-identity.md`
- `docs/audits/2026-06-06-layout-v3-migration-readiness-audit.md`

Keep (referenced by retained code / belong to kept infrastructure):

- `docs/migration/2026-05-19-validate-local-sh-porting-guide.md` — referenced by
  `validate/runner.py:30` (`_LEGACY_SIDECAR_PORTING_GUIDE`, a live validation
  error) and by `project_artifacts/registry.yaml` managed-artifact steps. Tied
  to the kept managed-artifact/validate flow, not v3 layout migration.
- `docs/migration/managed-artifacts-template.md` — managed-artifact authoring
  template for the kept managed-artifact system, not a v3 migration guide.

So `docs/migration/` is trimmed, not removed.

Leave `archive/**` and `docs/plans/**` untouched — they are the historical
record. No current (non-archive, non-plan) doc links the deleted files, so no
doc link fixup is required (confirm with the final grep).

### F. Update legacy-shape guard messages (hard errors, no recovery doc)

Several retained guards currently tell the user to run a now-removed migrator.
Per the scope decision, replace each with a hard error stating the legacy shape
is unsupported by this Science version (which requires v3) — no command
reference and no recovery doc. Sites:

- `project_config.py:131` — removed `science.yaml` fields → drop the
  "Run `science peers migrate`" sentence.
- `validate/checks/manifest.py:34` — `layout_version` < 3 message.
- `graph/materialize.py:374` and `:458` — unmigrated data-package messages.
- `graph/health.py:1614` — unmigrated data-package message.
- `cli.py:522` — "(`science entities migrate`) first." in the entities flow.

Keep the guards' detection and severity; only the remediation text changes.
Update any test that asserts the old message text.

## Non-Goals

- Renaming `graph/migrate.py` to `graph/audit.py` (deferred).
- Touching `archive/**` or `docs/plans/**`.
- Removing or changing the managed-artifact update runner or any audit code.
- Adding retired-command stubs or deprecation messages.

## Risks & Mitigations

- **"migration"-named code that is actually live** (the layered-claim health
  report; the `paper_dataset` role-conflict predicate; the validate-sidecar
  porting guide): mitigated by the per-symbol/per-file importer checks in
  sections A, B, and E — name alone never decides removal.
- **Mixed-module over-deletion** (`graph/migrate.py`, `entity_migrations.py`):
  mitigated by enumerating importers before editing and running the full test
  suite after.
- **Dangling CLI registration** after a module is removed: mitigated by a
  `science --help` smoke check across affected command groups.

## Validation

```bash
# No references to any removed module remain in source:
rg "entity_layout_migration|datapackage_migrate|peers_migrate|refs_migrate|\
tasks_id_migration|project_model_migration|tags_migration|aspects\.migrate|\
migrate_identifiers|rewrite_project_ids_in_sources|plan_paper_dataset_migration" \
  science/src
# (NOTE: build_layered_claim_migration_report and audit_project_sources are
#  KEPT — they must still resolve.)

# No retained source still tells users to run a removed command:
rg "science peers migrate|science entities migrate|migrate-identifiers|\
data-package migrate|aspects migrate" science/src

# Only the deleted guides are gone; the porting guide + template remain:
rg "entity-layout-migration-guide|assembly-identity|crosswalk-identity|\
layout-v3-migration-readiness-audit" --glob '!archive/**' --glob '!docs/plans/**'

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

# Remove-v3 Migration Code Supersession

The `remove-v3-migration-code` plan is no longer a valid active
implementation plan. It mixed completed cleanup of truly retired one-shot
migrators with proposed removals of migration-named surfaces that are still
live, documented, and tested.

## Completed Cleanup

The identifier rewrite cleanup and several old one-shot migrators were removed.
The current tree keeps `entity_migrations.audit_identifiers`, graph source
audits, layered-claim migration reporting, and the managed-artifact migration
runner as live infrastructure. These surfaces are not dead merely because they
use migration terminology.

## Intentionally Live Migration Surfaces

`science entities migrate` remains the v2-to-v3 entity layout migration surface.
It supports legacy `doc/` and `specs/` entity migrations, local-kind migration,
overlay relocation into `overlays/`, post-move audit checks, and the guarded
`layout_version: 3` bump. The current contract is documented in
`docs/user-guide/project-layout.md` and the entity-layout checkpoint.

`science graph migrate-paper-datasets` remains the transition surface from
legacy paper `datasets` frontmatter to canonical `dataset_usage`. It is
documented in `docs/user-guide/entities.md`; validation still uses the
paper-dataset role-conflict predicate to compare legacy and canonical entries.

Other migration-named code that remains live includes `graph migrate-addresses`,
managed-artifact project migrations, aggregate-retirement migration paths, and
layered-claim migration reporting. Do not remove code solely because it contains
the word "migration"; decide from current importers, CLI surface, docs, and
tests.

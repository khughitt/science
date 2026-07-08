# Remove-v3 Migration Code Supersession

The `remove-v3-migration-code` plan is no longer a valid active
implementation plan. It mixed completed cleanup of truly retired one-shot
migrators with proposed removals of migration-named surfaces that were still
live, documented, and tested at the time of this checkpoint.

Current status, 2026-07-08: the v2 entity-layout migration surface has since
been retired by `6147e473` (`refactor: remove v2 entity layout support`).
`science entities --help` no longer lists a `migrate` subcommand, and
`science/src/science_tool/entity_layout_migration.py` is absent. Treat the
`science entities migrate` notes below as historical context for why it was not
removed by this superseded plan, not as a current command contract.

## Completed Cleanup

The identifier rewrite cleanup and several old one-shot migrators were removed.
The current tree keeps `entity_migrations.audit_identifiers`, graph source
audits, layered-claim migration reporting, and the managed-artifact migration
runner as live infrastructure. These surfaces are not dead merely because they
use migration terminology.

## Historical And Live Migration Surfaces

Historically, `science entities migrate` was the v2-to-v3 entity layout
migration surface. It supported legacy `doc/` and `specs/` entity migrations,
local-kind migration, overlay relocation into `overlays/`, post-move audit
checks, and the guarded `layout_version: 3` bump. The historical contract is
preserved in the entity-layout checkpoint.

Historically, `science graph migrate-paper-datasets` was the transition surface
from legacy paper `datasets` frontmatter to canonical `dataset_usage`. It has
also since been retired; current validation fails `paper.datasets` with
forward-path guidance to use `dataset_usage` entries.

Other migration-named code that remains live includes `graph migrate-addresses`,
managed-artifact project migrations, aggregate-retirement migration paths, and
layered-claim migration reporting. Do not remove code solely because it contains
the word "migration"; decide from current importers, CLI surface, docs, and
tests.

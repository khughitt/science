# Legacy Support Scrub Audit

Date: 2026-07-04

## Purpose

Science should have one current way to represent each concept. The remaining
legacy readers and authoring paths cannot be deleted safely until the registered
project repositories no longer contain data that needs those readers.

The cleanup therefore runs per legacy surface:

0. If no migrator exists for the surface, build one first (TDD). Three surfaces
   below have no existing migrator: `type:`→`kind:`, scalar `access:`, and
   `article:`→`paper:`.
1. Detect the surface across registered projects.
2. Migrate all project data for that surface.
3. Re-run the precheck until it reports zero hits, and confirm each migrated
   project still builds (`science validate` / `graph materialize`) — sentinel
   absence alone does not prove a project still loads.
4. Delete the reader, fallback, migration command, and authoring guidance for
   that surface.
5. Verify both the toolkit and the registered project trees.

Do not remove a migrator before it has made its surface precheck green.

## Scope Rules

In scope:

- Old project data representations still loadable by the toolkit.
- Authoring templates, commands, and skills that still emit old representations.
- Migration-only commands and validators whose only purpose is transition support.
- Reader fallbacks that silently normalize old project files into current models.

Out of scope:

- Current lifecycle states such as task `retired`, claim `superseded`, and
  reference-graph `deprecated`.
- Biological or registry lifecycle metadata such as deprecated gene/protein rows.
- Current benchmark fallback concepts such as `gap-fallback` and
  `fallback-diagnostic`.
- Live `article` entity support. Only `article:<bibkey>` as a legacy alias for
  `paper:<bibkey>` is in scope.
- Current `profiles` model concepts. Only the bare `profiles:` config key used
  as a fallback for missing `knowledge_profiles:` is in scope.

## Inventory Base

Use existing project registry infrastructure instead of building a new registry
reader:

- `science/src/science_tool/registry/config.py` loads registered projects.
- `science/src/science_tool/registry/sync.py` already iterates registered
  projects safely and skips non-project directories.
- `scripts/audit_downstream_project_inventory.py` already scans one project for
  several downstream legacy indicators.

The multi-project precheck should deduplicate projects by resolved path because
the registry currently includes a `.worktrees/` duplicate. The per-project scan
must also exclude nested `.worktrees/` and `.git/` directories so a project's own
worktrees do not double-count entity files or sentinels.

## Coverage Universe

The safety model deletes each reader once its precheck is green, so the scanned
set must provably cover the at-risk set. The registry lists **22 projects**, but
**23 `science.yaml` files exist on disk** under Dropbox (excluding worktrees) —
at least one repository is outside the registered-project list and therefore
invisible to a registry-only precheck. `~/d/science-commons` is the known
special case: it is not an ordinary research project, but it is an in-scope
shared canonical entity repository for reusable records such as datasets and
paper summaries. The legacy-surface inventory must scan commons as a shared
repository and migrate affected commons files before deleting any reader. Before
trusting any zero-hit gate, filesystem-sweep for `science.yaml` outside the
registered set and, for each hit, register it, include it as a shared repository,
migrate it under this campaign, or record an explicit exclusion with rationale.
Removing a migrator is a one-way door — a project archived, off-machine, or
reactivated later can no longer be migrated.

## Execution Environment

- Run migrations with `PYTHONPATH=src:model/src`. Work happens in the
  `.worktrees/remove-legacy-support` worktree, but `science_model` is
  editable-installed from `main`; without the explicit path the stale main copy
  shadows worktree edits and migrations silently run old code.
- Each project migration is a commit in a separate, Dropbox-synced git repo whose
  branch/HEAD can drift mid-session. Verify branch and HEAD in each project repo
  before committing, and path-scope any stashes.
- Commons migrations are commits in `~/d/science-commons`. Treat it with the
  same branch/HEAD hygiene as registered projects even though it is included as a
  shared repository rather than an ordinary research project.

## Migration Command Retention Decision

After a surface reaches a zero-hit precheck and every migrated project still
builds, delete that surface's migration command along with the silent reader
fallback. Retaining the command would keep an endorsed way to carry legacy state
forward, which conflicts with the goal of one current representation. The escape
hatch for an off-machine or later-reactivated project is the recorded migration
commit plus git history, not a permanent legacy migration surface.

## Status 2026-07-05

Merged to `main`:

- Multi-project inventory and coverage sweep.
- v2-to-v3 entity layout migration and reader cleanup.
- Aggregate-manifest retirement, including downstream project migrations,
  zero-hit inventory gate, and toolkit reader/migrator/test removal.

Current refreshed inventory:

- Zero findings for retired DAG `.edges.yaml`, article prefix aliases, aggregate manifests,
  annotation marker aliases,
  entity-layout roots, `type:` frontmatter, scalar `access:`, active legacy
  data-package entities, bare `profiles:`, and removed `science.yaml` fields.

Completed in `refactor/strict-frontmatter-cleanup`:

- Remove the last `kind`/`type` dual-read in
  `science/src/science_tool/graph/commons_sources.py`.
- Remove scalar `access:` coercion in
  `science/model/src/science_model/frontmatter.py`.
- Remove adjacent strict-frontmatter fallbacks in workbench-apply existing
  target validation, curation inventory classification, and graph health access
  checks.

Completed in `refactor/article-prefix-alias-retirement`:

- Migrated all registered/shared `article:<bibkey>` reference aliases to
  `paper:<bibkey>` in affected project repos.
- Removed toolkit `article:` to `paper:` canonicalization, the dedicated health
  sentinel, and the short-lived migration command/module after the zero-hit
  inventory gate.

Completed in `refactor/retired-edges-yaml-retirement`:

- Migrated/committed all registered/shared `*.edges.yaml` project data found by
  the inventory gate.
- Removed active retired-edge reader, migration, archive/schema, CLI, and
  command-guidance support after the zero-hit inventory gate.

Completed in `refactor/marker-alias-retirement`:

- Migrated/committed all registered `[NEEDS CITATION]` markers to
  `[MISSING_CITATION]`.
- Removed active marker alias normalization, the marker migrator CLI, and
  command/skill guidance after the zero-hit inventory gate.

## Findings Table

| Surface | Project precheck signal | Current migration tool | Reader / authoring support to remove after green precheck | Notes |
| --- | --- | --- | --- | --- |
| v2-to-v3 entity layout | Entity markdown under `doc/` or `specs/`; toolkit scanners reading `doc`, `specs`, and `entities` together | `science/src/science_tool/entity_layout_migration.py` and related commands | `_SCAN_DIRS=("doc","specs","entities")` plumbing in `science/src/science_tool/refs.py`, `markers.py`, `prose_lint.py`, validation checks, graph health, materialize preflight, commons promotion helpers | Largest dependency cluster. Remove migrator last for this surface. |
| `type:` frontmatter | Entity frontmatter with `type:` instead of `kind:`; templates and commands that still author `type:` | Complete; no new migrator needed because inventory was already zero | Complete; active `kind`/`type` dual reads removed from commons translation, workbench apply, and curation inventory | Current inventory reports zero `type:` frontmatter findings. |
| Flat scalar `access:` | Frontmatter with `access: public` or another scalar value | Complete; no new migrator needed because inventory was already zero | Complete; scalar coercion removed from frontmatter parsing and graph health | Current inventory reports zero scalar `access:` findings. |
| `article:<bibkey>` prefix alias | Structured/project refs containing `article:<bibkey>` where the intended target is a literature record | Complete; short-lived scoped rewriter committed in history and removed after migration | Complete; literature-prefix alias checks, canonicalization paths, health sentinel, and migrator removed | Live `article` entity kind and BibTeX `@article` support remain. |
| Retired DAG `.edges.yaml` | Complete; current inventory reports zero `retired_edges_yaml` findings | Complete; migration commits exist in affected project repos | Complete; retired-edge readers, schemas, CLI commands, warnings, validation adapters, and command guidance removed | cBioPortal build passes; protein-landscape and multiple-myeloma still have unrelated pre-existing project validation/build blockers recorded during the slice. |
| Aggregate manifests | `knowledge/sources/<local>/entities.yaml`, `terms.yaml`, and `doc/<plural>/<plural>.{json,yaml}` aggregate owners | Complete; migration commits exist in affected project repos | Complete; aggregate readers, migrators, command paths, validators, and tests removed | Merged 2026-07-05; current inventory reports zero aggregate-manifest findings. |
| Legacy data-package entities | Complete; current inventory reports zero `legacy_data_package_entity` findings | Complete; no project migration was needed because inventory was already zero | Complete; materialize preflight, graph-health sentinel, `data-package` CLI group, promote helper, and docs removed | Runtime Frictionless datapackage descriptors remain current. |
| Other one-shot graph migrations | Complete for active one-shot commands; current inventory reports zero retired paper `datasets` findings and targeted precheck reported zero `migrate-addresses` flips | Complete; paper dataset migrations committed in affected project repos, address migration had no downstream hits | Complete for `graph migrate-addresses` and `graph migrate-paper-datasets`; `graph/migrate.py` remains as an audit helper, not a one-shot migrator | Retired commands removed 2026-07-06. Protein-landscape and science/meta still have unrelated pre-existing validation blockers recorded during the slice. |
| `science_qa` table mode | Complete; targeted downstream/code scan reports no active table-mode usage outside the retired tests/docs | No project migration was needed because inventory was already zero | Complete; `science_qa run --table`, the CLI legacy branch, and public `run_qa(config, table)` mode removed | This was a single confirmed item, not a cluster. |
| Annotation marker alias | Complete; current inventory reports zero `legacy_marker_alias` findings | Complete; direct downstream edits committed in affected project repos | Complete; marker alias normalization, marker migrator CLI, and marker docs removed | `[MISSING_CITATION]` remains canonical. |
| Bare `profiles:` config fallback | Complete; current inventory reports zero bare `profiles:` science.yaml findings | Complete; no project migration was needed because inventory was already zero | Complete; graph source loading and local kind registration now reject bare top-level `profiles:` instead of falling back to it | Do not flag current model/profile concepts or entity/datapackage frontmatter `profiles`. |
| Removed science.yaml fields | `parent:` or `children:` in project config | Direct config edit if found | `science/src/science_tool/project_config.py:_reject_legacy_fields` | Enforcement-only shim. Remove near the end after confirming zero downstream hits. |
| Command and skill guidance | Commands/skills instruct agents to read or author legacy paths or template fallbacks | Documentation edits after the relevant data migrator exists | `commands/*.md`, `skills/**/*.md`, `templates/*.md`, mirrored `science_model/templates/*` | Update early enough to stop new legacy data, but avoid deleting migration instructions before migrations run. |

## Precheck Sentinels

The downstream scanner should report counts by project and surface for:

- Entity markdown under `doc/` and `specs/`.
- Frontmatter `type:` fields on entity markdown.
- Scalar `access:` values.
- `article:<bibkey>` refs in structured sources and markdown frontmatter fields.
- `*.edges.yaml`.
- Aggregate manifest files.
- Active `doc/data-packages/*.md` data-package entities.
- Top-level `profiles:` in `science.yaml` when `knowledge_profiles:` is absent.
- `validate.local.sh`.
- `[NEEDS CITATION]`.
- `parent:` and `children:` in `science.yaml`.
- Known one-shot graph migration inputs.
- `science_qa` legacy table-mode use, if discoverable from project scripts or docs.

The scanner must avoid broad string matches that would false-positive on current
features: `profiles` as a model concept, `deprecated_ids`, task `retired`,
claim `superseded`, benchmark fallback concepts, and live `article` entities.

## Execution Order

1. Complete: build the multi-project inventory wrapper and produce the first
   table.
2. Complete: migrate and gate v2-to-v3 entity layout.
3. Complete: finish strict `kind:` reader cleanup now that `type:` data hits
   are zero.
4. Complete: remove scalar `access:` coercion now that scalar data hits are
   zero.
5. Complete: migrate and gate `article:<bibkey>` aliases.
6. Complete in current worktree: migrate and gate retired DAG `.edges.yaml`.
7. Complete: migrate and gate aggregate manifests.
8. Complete: reconfirm and retire legacy data-package entities.
9. Reconfirm and, if needed, migrate the remaining one-shot graph migrations.
10. Complete: migrate and gate marker aliases, `science_qa` table mode, and bare `profiles:` config fallback.
11. Remove enforcement-only shims after zero-hit confirmation.
12. Run final toolkit and downstream verification.

Each surface should end with a checked-in precheck report showing zero project
hits before deleting the corresponding reader.

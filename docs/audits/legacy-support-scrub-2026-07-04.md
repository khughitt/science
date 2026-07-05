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

- `article_prefix_alias`: 39 findings.
- `retired_edges_yaml`: 4 findings.
- `legacy_marker_alias`: 4 findings.
- Zero findings for aggregate manifests, entity-layout roots, `type:`
  frontmatter, scalar `access:`, active legacy data-package entities, bare
  `profiles:`, and removed `science.yaml` fields.

Remaining code-only cleanup before the next data-bearing migration:

- Remove the last `kind`/`type` dual-read in
  `science/src/science_tool/graph/commons_sources.py`.
- Remove scalar `access:` coercion in
  `science/model/src/science_model/frontmatter.py`.

## Findings Table

| Surface | Project precheck signal | Current migration tool | Reader / authoring support to remove after green precheck | Notes |
| --- | --- | --- | --- | --- |
| v2-to-v3 entity layout | Entity markdown under `doc/` or `specs/`; toolkit scanners reading `doc`, `specs`, and `entities` together | `science/src/science_tool/entity_layout_migration.py` and related commands | `_SCAN_DIRS=("doc","specs","entities")` plumbing in `science/src/science_tool/refs.py`, `markers.py`, `prose_lint.py`, validation checks, graph health, materialize preflight, commons promotion helpers | Largest dependency cluster. Remove migrator last for this surface. |
| `type:` frontmatter | Entity frontmatter with `type:` instead of `kind:`; templates and commands that still author `type:` | **MUST BUILD** — no `type:`→`kind:` rewriter exists; build a field-order-preserving, idempotent frontmatter migrator (TDD) before migrating data | All `fm.get("kind") or fm.get("type")` dual reads; templates and command docs that author `type:` | Sharp sequencing constraint: templates must emit `kind:` before the reader shim is removed. |
| Flat scalar `access:` | Frontmatter with `access: public` or another scalar value | **MUST BUILD** — no scalar-`access:` migrator exists; build one that emits a block with `verified: false` (matches current `_coerce_access` — a scalar was never verified) | `science/model/src/science_model/frontmatter.py` scalar coercion and health/reporting shims | Run after entity layout so paths are canonical. |
| `article:<bibkey>` prefix alias | Structured/project refs containing `article:<bibkey>` where the intended target is a literature record | **MUST BUILD** — no `article:`→`paper:` rewriter exists (`add_article` is unrelated entity creation); build one scoped to the alias prefix only | Literature-prefix alias checks and canonicalization paths | Do not remove the live `article` entity kind or BibTeX `@article` support. |
| Retired DAG `.edges.yaml` | Any `*.edges.yaml` file in project DAG areas | `science dag retired-edge-migration-plan`, `science dag scaffold-retired-edge-workbench`, and related retired-edge tools | `science/src/science_tool/dag/` retired-edge readers, schemas, CLI commands, warnings, and validation adapters | Keep migration commands until every registered project has zero edge YAML files. |
| Aggregate manifests | `knowledge/sources/<local>/entities.yaml`, `terms.yaml`, and `doc/<plural>/<plural>.{json,yaml}` aggregate owners | Complete; migration commits exist in affected project repos | Complete; aggregate readers, migrators, command paths, validators, and tests removed | Merged 2026-07-05; current inventory reports zero aggregate-manifest findings. |
| Legacy data-package entities | `doc/data-packages/*.md` with active `type: data-package` | `data-package` CLI group and dataset/research-package promotion helpers | `science/src/science_tool/graph/materialize.py:_preflight_migration`, `science/src/science_tool/cli.py` `data-package` group, promote helpers, docs | Precheck must look at project data, not only toolkit code. |
| Other one-shot graph migrations | Inputs still requiring `graph migrate-addresses`, `graph migrate-paper-datasets`, `graph/migrate.py`, or materialize migration flags | Existing one-shot commands and flags | One-shot commands and flags after data is clean | Treat each one-shot as a separate surface if its precheck is nonzero. |
| `science_qa` table mode | QA invocation using `--config qa.yaml --table T` | Add or document datapackage-mode migration if any downstream usage remains | `science/qa/src/science_qa/cli.py` legacy branch and `run_qa` mode if unused | This is a single confirmed item, not a cluster. |
| Annotation marker alias | `[NEEDS CITATION]` markers | `science markers migrate --write` | `science/src/science_tool/markers.py` `LEGACY_ALIASES` and marker docs | Keep `[MISSING_CITATION]` canonical. |
| Bare `profiles:` config fallback | `science.yaml` has top-level `profiles:` without `knowledge_profiles:` | Config-key migration to `knowledge_profiles:` | `science/src/science_tool/graph/sources.py` fallback from `profiles` to `knowledge_profiles` | Do not flag current model/profile concepts. |
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
3. Next: finish strict `kind:` reader cleanup now that `type:` data hits are
   zero.
4. Next: remove scalar `access:` coercion now that scalar data hits are zero.
5. Migrate and gate `article:<bibkey>` aliases.
6. Migrate and gate retired DAG `.edges.yaml`.
7. Complete: migrate and gate aggregate manifests.
8. Reconfirm and, if needed, migrate legacy data-package entities.
9. Reconfirm and, if needed, migrate the remaining one-shot graph migrations.
10. Migrate and gate small aliases and CLI compatibility modes.
11. Remove enforcement-only shims after zero-hit confirmation.
12. Run final toolkit and downstream verification.

Each surface should end with a checked-in precheck report showing zero project
hits before deleting the corresponding reader.

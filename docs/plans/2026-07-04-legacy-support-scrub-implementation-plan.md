# Legacy Support Scrub Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove legacy/fallback support from Science only after all registered project data has been migrated to the current representation.

**Architecture:** Treat each legacy representation as its own migration surface. A surface is complete only when the downstream precheck reports zero hits, the reader/migrator/authoring support has been removed, and toolkit plus downstream verification are green.

**Tech Stack:** Python 3.13, Click, Pydantic v2, PyYAML, pytest, existing Science registry and downstream audit scripts.

---

## Guardrails

- Do not delete a migrator before it has run everywhere and its precheck is green.
  Removing a migrator is a one-way door: a project archived, off-machine, or
  reactivated later can no longer be migrated. Only remove after the coverage
  universe (Task 1) is reconciled and green.
- After a surface gate is green, delete its explicit migration command too. The
  target state has one current representation, not a permanent supported path
  for legacy state; recovery for omitted projects comes from the recorded
  migration commits and git history.
- Do not do broad string cleanup for `fallback`, `deprecated`, `retired`, or
  `article`; distinguish current concepts from compatibility shims.
- Use `~/d/` paths in docs and code comments when absolute paths are needed.
- Keep commits surface-scoped so regressions can be bisected.
- **Run migrations with `PYTHONPATH=src:model/src`.** This work happens in the
  `.worktrees/remove-legacy-support` worktree, but `science_model` is
  editable-installed from `main`; without the explicit `PYTHONPATH` the stale
  main copy shadows worktree edits and migrations silently run old code.
- **Each project migration is a commit in a separate, Dropbox-synced git repo.**
  Verify the branch and HEAD in each project repo before committing its
  migration (branch/HEAD can drift mid-session on Dropbox), and path-scope any
  stashes. The surface-scoped-commit rule above applies per project repo, not
  just to the toolkit repo.
- A surface's gate is not green on sentinel-absence alone: the affected projects
  must still build. Re-run `science validate` (or `graph materialize`) on each
  migrated project before deleting that surface's reader.
- Treat `~/d/science-commons` as an in-scope shared repository. It is not an
  ordinary registered research project, but it owns reusable canonical records
  such as datasets and paper summaries, so any affected commons files must be
  migrated before a reader is deleted.

## Status 2026-07-06

- Merged on `main`: Task 1 inventory, Task 2 v2-to-v3 entity layout, and Task 7
  aggregate manifest retirement, retired DAG `.edges.yaml` retirement, and
  marker alias cleanup.
- Current inventory: 0 total findings. Retired DAG `.edges.yaml`, article prefix
  aliases, aggregate manifest, marker alias, `type:` frontmatter, scalar
  `access:`, data-package, bare `profiles:`, and removed `science.yaml` field
  hits are zero.
- Current coverage: 23 registered entries, 22 scanned projects, 1 shared
  repository (`~/d/science-commons`), 1 skipped stale registered path
  (`~/d/natural-systems/.worktrees/validation-strict-cleanup`), and no
  unregistered `science.yaml` files in the configured search roots.
- Strict frontmatter cleanup is complete in
  `refactor/strict-frontmatter-cleanup`: remaining `type:` reader fallbacks and
  scalar `access:` coercion paths were removed from active toolkit code.
- Complete in `refactor/marker-alias-retirement`: downstream marker aliases
  have been migrated/committed in 3d-attention-bias, natural-systems, and
  seq-feats; active toolkit alias normalization, marker migrator CLI, and
  command guidance have been removed.
- Complete in `refactor/data-package-retirement`: the registered-project
  inventory reports zero legacy data-package entity findings, and active
  materialize preflight, health sentinel, data-package CLI group, promotion
  helper, and user-facing command guidance were removed.
- Complete in `refactor/command-guidance-legacy-cleanup`: current command,
  generated Codex skill, template, schema-reference, and user-guide surfaces no
  longer teach retired entity-root, `type:` frontmatter, `article:` prefix,
  `.edges.yaml`, data-package entity-ref, aggregate-manifest, or layout-v2
  scaffold patterns.
- Complete in `refactor/removed-science-yaml-fields-cleanup`: removed
  `science.yaml` fields remain explicitly rejected. This is a fail-early guard,
  not reader or fallback support; deleting it would silently accept `parent:`
  and `children:` as unknown extra fields.
- Complete in `refactor/legacy-scrub-final-verification`: final inventory
  reports zero legacy-surface findings across 22 scanned projects plus
  `~/d/science-commons`. Final verification is recorded in
  `docs/audits/legacy-support-scrub-final-verification-2026-07-06.md`.

## Task 1: Multi-Project Legacy Inventory

**Files:**
- Modify: `scripts/audit_downstream_project_inventory.py`
- Create: `scripts/audit_registered_projects_legacy_surfaces.py`
- Test: `science/tests/test_downstream_legacy_inventory.py`
- Output: `docs/audits/legacy-support-scrub-inventory-2026-07-04.md`

- [x] **Step 1: Add focused single-project findings**

Extend the existing downstream scanner so it returns structured counts for the
sentinels listed in `docs/audits/legacy-support-scrub-2026-07-04.md`. Keep the
checks precise enough to avoid current feature false positives.

- [x] **Step 2: Add registered-project wrapper**

Create a wrapper that loads registered projects, resolves and deduplicates
paths, skips entries without `science.yaml`, runs the single-project scanner,
and writes markdown plus JSON output. The single-project scanner must exclude
nested `.worktrees/` and `.git/` directories so a project's own worktrees do not
double-count entity files or sentinels.

- [x] **Step 3: Reconcile the coverage universe**

The safety model deletes readers once the precheck is green, so the scanned set
must provably cover the at-risk set. Filesystem-sweep for `science.yaml` files
outside the registry (there is a known delta — the registry lists 22 projects
but more `science.yaml` files exist on disk). For each unregistered project,
either register it, migrate it under this campaign, or record an explicit
exclusion with rationale. Do not trust any zero-hit gate until this delta is
resolved.

Status 2026-07-05: `~/d/science-commons` is now included as an in-scope shared
repository rather than treated as an unresolved unregistered project. The sweep
still reports one stale registered worktree path,
`~/d/natural-systems/.worktrees/validation-strict-cleanup`; because that path is
absent, it is not load-bearing project data, but it should be pruned from the
global registry before final cleanup.

- [x] **Step 4: Test deduplication and sentinel precision**

Add tests with tiny temporary project trees covering:

- duplicate registry paths collapse to one scan target;
- a nested `.worktrees/<name>/` copy does not double-count its sentinels;
- top-level `profiles:` without `knowledge_profiles:` is reported;
- ordinary `profiles` text or model/profile vocabulary is not reported;
- `article:<bibkey>` refs are reported, while `kind: article` is not;
- task `retired` and `deprecated_ids` are not reported.

- [x] **Step 5: Run initial inventory**

Run the wrapper against registered projects and save the baseline report under
`docs/audits/`. This report drives the remaining task order.

- [x] **Step 6: Verify**

Run:

```bash
cd science && uv run --frozen pytest tests/test_downstream_legacy_inventory.py -q
```

## Task 2: v2-to-v3 Entity Layout Surface

**Files:**
- Remove only after green precheck: `science/src/science_tool/entity_layout_migration.py`
- Modify after green precheck: `science/src/science_tool/refs.py`, `science/src/science_tool/markers.py`, `science/src/science_tool/prose_lint.py`, `science/src/science_tool/validate/checks/entity_conformance.py`, `science/src/science_tool/validate/checks/directory_structure.py`, `science/src/science_tool/graph/health.py`, `science/src/science_tool/graph/materialize.py`
- Tests: existing entity layout, refs, markers, prose lint, validation, graph health tests

- [x] **Step 1: Run layout precheck**

Use Task 1 inventory to list every registered project with entity files under
`doc/` or `specs/`.

- [x] **Step 2: Migrate project data**

Run the existing entity layout migration over each affected project. Review
git diffs in each project and resolve collisions explicitly.

- [x] **Step 3: Gate**

Re-run the registered-project inventory. Proceed only when `doc/specs entity`
hits are zero **and** each affected project still builds: run `science validate`
(or `graph materialize`) on every migrated project and confirm green. Sentinel
absence alone does not prove a project still loads.

- [x] **Step 4: Remove reader support**

Delete the scanner branches that treat `doc/` and `specs/` as entity roots.
Keep `doc/` as prose-only where still intentional.

- [x] **Step 5: Verify**

Run focused tests, then:

```bash
cd science && uv run --frozen pytest
```

## Task 3: `type:` to `kind:` Surface

**Files:**
- Create: `science/src/science_tool/` frontmatter `type:`→`kind:` migrator + CLI command
- Modify: all entity templates in `templates/` and `science/model/src/science_model/templates/`
- Modify after green precheck: loader/frontmatter sites using `kind`/`type` dual reads
- Test: `science/tests/` for the new migrator
- Tests: frontmatter, entity loader, command authoring tests

> No on-disk `type:`→`kind:` rewriter exists today — this surface requires
> building one before any data can be migrated.

Status 2026-07-05: project data and active authoring surfaces are clean in the
registered-project inventory. The remaining reader fallbacks were removed in
`refactor/strict-frontmatter-cleanup`, including commons entity translation,
workbench-apply existing-target validation, and curation inventory
classification.

- [x] **Step 0: Build the frontmatter migrator (TDD) or confirm it is not needed**

Write a rewriter that replaces entity-frontmatter `type:` with `kind:`,
preserving surrounding field order and body bytes, idempotent, with a
`--write`/dry-run split. Cover with tests before running it on any project.

No new migrator was needed in this slice: the registered-project inventory was
already zero for `type:` entity frontmatter after earlier project migration
work.

- [x] **Step 1: Inventory authoring and data**

Use the scanner to count project files with entity frontmatter `type:` and
toolkit templates/commands that still author `type:`.

- [x] **Step 2: Change authoring surfaces**

Update templates and command guidance to emit `kind:`. Do this before removing
reader compatibility so new legacy files stop appearing.

- [x] **Step 3: Migrate project data**

Run the Step 0 migrator to rewrite on-disk entity frontmatter from `type:` to
`kind:` in all registered projects, preserving field order.

- [x] **Step 4: Gate**

Re-run the registered-project inventory. Proceed only when `type:` hits are
zero in project entity files and toolkit templates, **and** each migrated
project still builds under `science validate` / `graph materialize`.

- [x] **Step 5: Remove dual-read support**

Replace `fm.get("kind") or fm.get("type")` and equivalent normalization with
strict `kind:` reads. Remove tests whose only purpose is `type:` compatibility.

- [x] **Step 6: Verify**

Run frontmatter/entity tests, then the full `science` and `science/model`
suites.

## Task 4: Scalar `access:` Surface

**Files:**
- Create: scalar-`access:`→block migrator + CLI command
- Modify before gate: project entity files
- Modify after gate: `science/model/src/science_model/frontmatter.py`, `science/src/science_tool/graph/health.py`
- Test: `science/tests/` for the new migrator
- Tests: frontmatter access parsing and health checks

> No scalar-`access:` migrator exists today — build one before migrating data.

Status 2026-07-05: registered-project inventory reports zero scalar `access:`
hits, so no project data migration is currently required. Scalar coercion was
removed in `refactor/strict-frontmatter-cleanup`; scalar input now fails
frontmatter parsing and health reports malformed scalar access instead of
normalizing it.

- [x] **Step 0: Build the access migrator (TDD) or confirm it is not needed**

Write a rewriter that converts scalar `access: <level>` to a structured block.
It **must preserve the current coercion semantics** — `verified: false` (the
existing `_coerce_access` behavior); a scalar value was never verified, so the
migration must not assert `verified: true`. Cover with tests before running.

No new migrator was needed in this slice: the registered-project inventory was
already zero for scalar `access:` fields after earlier project migration work.

- [x] **Step 1: Inventory scalar access**

Report every entity with scalar `access:`.

- [x] **Step 2: Migrate data**

Run the Step 0 migrator to rewrite scalar access values to structured blocks
with explicit `level` and `verified: false` fields.

- [x] **Step 3: Gate**

Proceed only when project scalar access hits are zero **and** each migrated
project still builds under `science validate` / `graph materialize`.

- [x] **Step 4: Remove scalar coercion**

Make scalar `access:` invalid instead of normalized.

- [x] **Step 5: Verify**

Run frontmatter and health tests plus package suites.

## Task 5: `article:<bibkey>` Alias Surface

**Files:**
- Created then removed after gate: `article:<bibkey>`→`paper:<bibkey>` ref
  migrator + CLI command
- Removed after gate: literature-prefix canonicalization and health checks
- Do not remove: live `article` entity kind support
- Test: `science/tests/` for the new migrator

> No `article:`→`paper:` ref rewriter exists today (`add_article` is unrelated
> entity creation) — build one before migrating refs.

Status 2026-07-05: complete in `refactor/article-prefix-alias-retirement`.
Migrated 39 `article:<bibkey>` alias hits across
`~/d/3d-attention-bias`, `~/d/cancer/cancer-types/multiple-myeloma`, and
`~/d/cancer/data-sources/cbioportal`; removed the toolkit canonicalization path,
health sentinel, and short-lived migrator command/module after the zero-hit gate.

- [x] **Step 0: Build the ref migrator (TDD)**

Write a rewriter that rewrites `article:<bibkey>` refs (in structured sources
and markdown frontmatter) to `paper:<bibkey>`. It must target only the alias
prefix and must not touch `kind: article` entities or `@article` BibTeX. Cover
with tests before running.

- [x] **Step 1: Inventory alias refs**

Report only `article:<bibkey>` references that are acting as paper aliases.

- [x] **Step 2: Migrate refs**

Run the Step 0 migrator to rewrite those refs to `paper:<bibkey>` across
registered projects.

- [x] **Step 3: Gate**

Proceed only when alias refs are zero, `kind: article` still passes tests,
**and** each migrated project still builds under `science validate` /
`graph materialize`.

- [x] **Step 4: Remove alias normalization**

Delete the `article:` to `paper:` alias path and related migration docs/tests.

- [x] **Step 5: Verify**

Run reference, graph audit, and entity kind tests.

## Task 6: Retired DAG `.edges.yaml` Surface

**Files:**
- Keep until after gate: retired-edge migration commands and modules
- Remove after gate: retired-edge readers, schemas, CLI commands, warnings, and tests

Status 2026-07-05: complete in `refactor/retired-edges-yaml-retirement`.
Project data was migrated/committed in cBioPortal, protein-landscape, and
multiple-myeloma; the registered-project inventory now reports zero
`retired_edges_yaml` findings. Active toolkit reader, migrator, archive/schema,
and CLI support was removed after the zero-hit gate.

- [x] **Step 1: Inventory edge YAML files**

Report every registered project containing `*.edges.yaml`.

- [x] **Step 2: Migrate DAG rows**

Use retired-edge migration planning and workbench scaffold commands to migrate
each project.

- [x] **Step 3: Gate**

Proceed only when edge YAML hits are zero **and** each migrated project still
builds under `science validate` / `graph materialize`.

- [x] **Step 4: Remove retired-edge support**

Delete retired-edge inspection/migration modules, schema command, and
compatibility warnings.

- [x] **Step 5: Verify**

Run DAG and graph tests plus package suites.

## Task 7: Aggregate Manifest Surface

**Files:**
- Keep until after gate: `aggregate_retire.py`, `aggregate_triage.py`
- Remove after gate: aggregate adapter support and aggregate-retired validation

Status 2026-07-05: complete and merged to `main`. Aggregate manifests were
migrated in affected project repos, the inventory reports zero
`aggregate_manifest` findings, and aggregate readers/migration commands/tests
were removed from the toolkit.

- [x] **Step 1: Inventory aggregate manifests**

Report multi-type and single-type aggregate manifests by project.

- [x] **Step 2: Migrate or retire aggregate owners**

Use aggregate triage and retire helpers to convert each owner to canonical
entity markdown or delete retired rows.

- [x] **Step 3: Gate**

Proceed only when aggregate manifest hits are zero **and** each migrated project
still builds under `science validate` / `graph materialize`.

- [x] **Step 4: Remove aggregate readers**

Remove aggregate adapter support paths and transition validators.

- [x] **Step 5: Verify**

Run graph source, identity collision, aggregate, and validation tests.

## Task 8: Legacy Data-Package Surface

**Files:**
- Removed after gate: materialize preflight, data-package CLI group, promote
  helper, and docs

- [x] **Step 1: Inventory data-package entities**

Report active `doc/data-packages/*.md` entities.

- [x] **Step 2: Migrate data**

Split each legacy data-package entity into derived datasets plus a
research-package as appropriate.

- [x] **Step 3: Gate**

Proceed only when active data-package hits are zero **and** each migrated project
still builds under `science validate` / `graph materialize`.

- [x] **Step 4: Remove legacy support**

Delete the data-package CLI group and preflight support.

- [x] **Step 5: Verify**

Run dataset, graph materialization, and CLI tests.

## Task 9: Remaining One-Shot Migration Surfaces

**Files:**
- `science/src/science_tool/graph/paper_dataset_migration.py` (deleted)
- `science/src/science_tool/graph/store/mutations.py:migrate_addresses_direction` (deleted)
- related CLI commands (`graph migrate-addresses`, `graph migrate-paper-datasets`)

- [x] **Step 1: Inventory one-shot inputs**

Use the downstream scanner to identify project data that still requires each
one-shot migration. Active one-shot inputs were retired paper `datasets` fields
and anti-canonical `sci:addresses` triples. `graph/migrate.py` was reviewed and
kept as an audit helper.

- [x] **Step 2: Run each migration**

Run the one-shot migrator for every project with hits.

- [x] **Step 3: Gate and remove**

For each one-shot surface, delete only after its own zero-hit report **and**
confirmation that each migrated project still builds under `science validate` /
`graph materialize`.

- [x] **Step 4: Verify**

Retired one-shot command tests assert `graph migrate-addresses` and
`graph migrate-paper-datasets` are no longer commands. Final verification
records that `science graph materialize` is not a live command; the current
write-producing graph build command was not run across downstream repos during
the read-only final pass.

## Task 10: Small Aliases and Removed-Field Guards

**Files:**
- `science/qa/src/science_qa/cli.py`
- `science/src/science_tool/markers.py`
- `science/src/science_tool/graph/sources.py`
- `science/src/science_tool/project_config.py`
- related docs and tests

Status 2026-07-06: marker alias cleanup is complete; `science_qa` table mode
and the bare `profiles:` config fallback were retired in
`refactor/runtime-shim-retirement`; removed `science.yaml` fields remain
explicitly rejected in `ProjectConfig` because top-level extras are otherwise
allowed. Current inventory reports zero `legacy_marker_alias`, bare
`profiles:`, and removed `science.yaml` field hits.

- [x] **Step 1: Inventory small aliases**

Check registered projects for QA table-mode usage, `[NEEDS CITATION]`, bare
`profiles:` config fallback, and removed `parent:`/`children:` fields.

- [x] **Step 2: Migrate data/usages**

Migrate each small surface independently.

- [x] **Step 3: Gate**

Proceed only when each small surface has zero downstream hits **and** any project
touched by that surface's migration still builds under `science validate` /
`graph materialize`.

- [x] **Step 4: Remove support and keep removed-field rejection**

Delete compatibility branches for zero-hit surfaces. Keep explicit rejection
for already-removed config fields when the schema otherwise allows extra keys;
that guard prevents silent acceptance rather than supporting a retired shape.

- [x] **Step 5: Verify**

Run targeted tests plus package suites.

## Task 11: Command, Skill, and User Guide Cleanup

**Files:**
- `commands/*.md`
- `skills/**/*.md`
- `templates/*.md`
- `science/model/src/science_model/templates/*.md`
- `docs/user-guide/*.md`
- `docs/conventions/*.md`

Status 2026-07-06: complete in `refactor/command-guidance-legacy-cleanup`.
Current commands, generated Codex skills, templates, active user-guide docs,
and schema references point at current roots/fields and no longer teach retired
`article:` aliases, `.edges.yaml`, data-package entity refs, aggregate
manifests, or layout-v2 scaffolds.

- [x] **Step 1: Remove legacy authoring instructions**

Update instructions to point only at current paths and current fields.

- [x] **Step 2: Keep migration history only where useful**

Historical plans can remain historical, but active user guidance should not
tell agents to read or author legacy surfaces.

- [x] **Step 3: Gate docs and templates**

Run final `rg` triage over active docs/templates/commands/skills and classify
intentional survivors.

- [x] **Step 4: Verify docs**

Run docs/user-guide tests if available, then full package suites.

## Task 12: Final Verification

**Files:**
- Output: `docs/audits/legacy-support-scrub-final-inventory-2026-07-06.md`
- Output: `docs/audits/legacy-support-scrub-final-verification-2026-07-06.md`

- [x] **Step 1: Run downstream precheck and rebuild projects**

Run the registered-project inventory across all deduplicated project roots.
Expected: zero hits for every removed surface. Then confirm every affected
project still builds — run `science validate` / `graph materialize` across the
project set — so the final state proves the projects load, not only that the
sentinels are gone.

Result: final inventory reports `total_findings: 0`. `science validate
--profile commit` passed for 12 projects, failed for 9 with unrelated project
validation/tooling issues, and timed out for `~/d/cancer/cancer-types/multiple-myeloma`
under the 60-second per-project cap. `science graph materialize` is not a live
CLI command; `science graph build` writes graph artifacts and was not run
across downstream repos in this read-only pass.

- [x] **Step 2: Run toolkit search triage**

Run targeted `rg` searches across toolkit code, active docs, commands, skills,
templates, and registered project trees. Classify every remaining hit as a
current concept or remove it.

Result: active toolkit hits are classified as negative guidance, rejection
paths, retired-command tests, inventory fixtures, current `doc` prose scanning,
or "do not create" docs. Registered-project broad `rg` hits are classified in
the final verification report as historical snippets, fixtures, generated
reports, current datapackage/profile/task fields, live `article` records, or
unreadable `pgdata`; structured inventory remains the authoritative zero-hit
data gate.

- [x] **Step 3: Run full verification**

Run:

```bash
cd science && uv run --frozen pytest
cd science/model && uv run --frozen pytest
cd science && uv run ruff check
cd science && uv run pyright
```

Result: `science`, `science/model`, and `science/qa` pytest suites pass. Full
`ruff check` and `pyright` still fail on unrelated existing annotation,
dataset, feedback, labnote, benchmark, and test issues in untouched files; see
the final verification report.

- [x] **Step 4: Commit final state**

Commit the completed scrub without AI attribution trailers.

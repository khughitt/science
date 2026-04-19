# Manuscript + Paper Terminology Rename

**Date:** 2026-04-19
**Status:** Draft

## Motivation

Science's entity-prefix vocabulary has a terminology collision. Two distinct concepts currently share overlapping names:

- **Authoring** (user's own publication in progress): `templates/paper.md`, entity prefix `paper:<id>`, with `status: outline | draft | revision | final`.
- **External literature** (a paper the user has read and summarized): `templates/paper-summary.md`, entity prefix `article:<bibkey>`.

Meanwhile, the `doc/papers/` directory convention in real projects (mm30, natural-systems) holds external-literature files — entities with `id: article:...` despite living under a directory named `papers`. The directory name, filename, and entity prefix all disagree.

This creates three downstream problems:

1. New users see `paper.md` and `paper-summary.md` and cannot tell which is which without reading content.
2. The knowledge-gaps spec (2026-04-19) needs to distinguish user manuscripts from external papers in coverage metrics; with the current vocabulary, `paper:<bibkey>` is ambiguous.
3. Future features that want to surface "manuscripts in progress" as a first-class concept have no clean entity-prefix to target.

Normalizing vocabulary now — before knowledge-gaps consumes `paper:` as its external-literature prefix — removes the collision cheaply. Both real projects are already using `article:` consistently for external lit, so the rename is mechanical on project-side and touches only one template file on framework-side.

## Goal

Normalize Science's literature vocabulary to two clean, non-overlapping entity prefixes:

- `manuscript:<id>` — user's own publication-in-progress.
- `paper:<bibkey>` — external literature the user has read and summarized.

After the rename, template filenames, directory conventions, and entity prefixes all agree:

- `templates/manuscript.md` → `manuscript:<id>` → user-authored publication drafts.
- `templates/paper.md` → `paper:<bibkey>` → entries in `doc/papers/`.

## Scope

### In scope

- Rename `templates/paper.md` → `templates/manuscript.md`. Update its frontmatter `id:` line from `paper:<paper_id>` to `manuscript:<manuscript_id>`.
- Rename `templates/paper-summary.md` → `templates/paper.md`. Update its frontmatter `id:` line from `article:<bibtex_key>` to `paper:<bibtex_key>`.
- New CLI subcommand `science-tool refs migrate-paper` that rewrites `article:<X>` to `paper:<X>` across an existing project's markdown files (frontmatter `id:`, `related:` lists, `source_refs:`, prose mentions). Dry-run default, `--apply` to write.
- Update all `commands/*.md` and `references/*.md` that mention `article:<X>` as an example entity ID. Flat find-and-replace of the prefix.
- Cosmetic updates to `science-tool/src/science_tool/cli.py` user-facing strings that say "article" where they should now say "paper".
- Transition-window dual-prefix acceptance: downstream consumers (resolver, validator, knowledge-gaps module, graph materialization) continue to accept `article:<X>` as a valid external-paper entity ID alongside `paper:<X>` for one release cycle.
- Unit tests: migration tool correctness, idempotency, transition-window dual-acceptance.

### Out of scope

- **Directory renames.** `doc/papers/` and `doc/background/papers/` already align with the new vocabulary; no change.
- **`paper-fetch` subcommand rename.** Reads correctly under the new vocabulary.
- **`cite:<bibkey>` source-ref prefix.** Bibtex-citation-style, orthogonal to entity prefixes. Unchanged.
- **Migrating the historic `paper:` authoring prefix.** Neither tracked project has instantiated `templates/paper.md`, so no existing entities with `id: paper:<id>` need rewriting. The authoring rename is framework-only.
- **Deprecation of the transition-window fallback.** Removed in a follow-on release once all tracked projects confirm migration; this spec does not commit to the removal schedule.

## Entity-Prefix Mapping

| Before | After | Notes |
|---|---|---|
| `paper:<id>` (authoring) | `manuscript:<id>` | Framework-only; no existing project entities to migrate. |
| `article:<bibkey>` (external lit) | `paper:<bibkey>` | Project-wide rename via `science-tool refs migrate-paper`. |
| `cite:<bibkey>` (bibtex ref) | unchanged | Separate concept; no change. |

## Template Changes

### `templates/paper.md` → `templates/manuscript.md`

Rename the file. Update the frontmatter block:

```yaml
# before
---
id: "paper:{{paper_id}}"
type: "paper"
...
```

```yaml
# after
---
id: "manuscript:{{manuscript_id}}"
type: "manuscript"
...
```

The rest of the template (Abstract, Outline sections, stories list) is unchanged. Placeholder name `{{paper_id}}` becomes `{{manuscript_id}}` for consistency.

### `templates/paper-summary.md` → `templates/paper.md`

Rename the file (after `paper.md` → `manuscript.md` completes, so no filename conflict). Update frontmatter:

```yaml
# before
---
id: "article:{{bibtex_key}}"
type: "article"
...
```

```yaml
# after
---
id: "paper:{{bibtex_key}}"
type: "paper"
...
```

All other fields (`source_refs`, `related`, `ontology_terms`, `datasets`, etc.) unchanged.

## Migration Tool

### CLI: `science-tool refs migrate-paper`

Invocation:

```
science-tool refs migrate-paper [--apply] [--project-root <path>]
```

Behavior:

1. Walk every markdown file under `project_root`'s canonical content directories: `doc/`, `specs/`, `tasks/`, `knowledge/`, `core/`, `papers/` (if present).
2. For each file, apply two text rewrites:
   - YAML frontmatter `id:` fields of the form `id: article:<X>` or `id: "article:<X>"` → `id: paper:<X>` (or `id: "paper:<X>"`).
   - Any other occurrence of `article:<X>` in markdown body or YAML values → `paper:<X>`. The regex is anchored on the literal prefix `article:` followed by a valid entity-ID character class.
3. Without `--apply`: print a diff-summary — per-file count of matches — and exit 0 without writing.
4. With `--apply`: rewrite files in place. Preserve all other formatting (indentation, whitespace). Exit 0 on success with a summary: "Rewrote N `id:` fields and M `related:` references in K files."

Idempotency: if a project has no remaining `article:` references, the command exits 0 with "No `article:` references found; project is migrated." Re-running on a migrated project is a no-op.

No project-side migration is needed for the authoring rename, because tracked projects have no `paper:<id>` authoring entities. The migration tool focuses solely on the external-literature rename.

### Module layout

- `science-tool/src/science_tool/refs/__init__.py`
- `science-tool/src/science_tool/refs/migrate_paper.py` — pure-function core.
- `science-tool/src/science_tool/refs/cli.py` — click subgroup registering the `refs` command group and `migrate-paper` subcommand.
- Wire `refs_group` into `science-tool/src/science_tool/cli.py` near other subcommand groups (`aspects_group`, `big_picture_group`).

### Rewrite rules (precise)

The migration applies these rewrites, case-sensitively:

- `id: article:` → `id: paper:`
- `id: "article:` → `id: "paper:`
- `- article:` → `- paper:` (for list-item entries in `related:`, `source_refs:`, etc.)
- `[article:` → `[paper:` (for inline-list entries like `related: [article:X]`)
- `"article:` → `"paper:` (for double-quoted values inside YAML lists)
- `'article:` → `'paper:` (for single-quoted values)
- Word-boundary: `\barticle:(?=[A-Za-z0-9])` → `paper:` (for prose mentions)

The prose-match rule uses a word boundary to avoid accidental rewrites of substrings like `particle:` that happen to contain `article:`. Entity-ID character class is `[A-Za-z0-9_-.]`.

## Transition-Window Dual-Prefix Acceptance

Downstream consumers that resolve entity IDs MUST accept both `article:<bibkey>` and `paper:<bibkey>` as the external-literature prefix during the transition window. Affected code:

- `science_tool.big_picture.resolver._load_entities` and related scanning — already scans by filename, not prefix; no change.
- `science_tool.big_picture.validator._collect_project_ids` — harvests IDs from frontmatter; accepts whatever prefix the entity declares. No change needed.
- `science_tool.big_picture.validator.REFERENCE_PATTERN` — currently matches `interpretation|task|question|hypothesis`. Extend to also match `paper|article` (both accepted).
- `science_tool.big_picture.knowledge_gaps` (not yet shipped) — its coverage rule counts both prefixes per the knowledge-gaps spec.
- Any future graph-materialization code that handles external-paper entities — accepts both prefixes for one release cycle.

The dual-acceptance behaves as if `article:<bibkey>` and `paper:<bibkey>` are aliases. A reference from one entity to the other resolves correctly regardless of prefix orientation.

Deprecation: the dual-acceptance is removed in a follow-on release (one-line change in each consumer) once all tracked projects confirm migration. This spec does not commit to a specific removal date.

## Documentation Updates

All in the same PR as the rename:

- `commands/search-literature.md` — mentions `doc/papers/` (no rename needed) but any example `article:<X>` IDs become `paper:<X>`.
- `commands/research-papers.md` — same.
- `commands/bias-audit.md`, `commands/compare-hypotheses.md`, `commands/next-steps.md`, `commands/research-topic.md` — check for `article:` mentions, rewrite.
- `references/role-prompts/research-assistant.md` — mentions `doc/background/papers/`; check for `article:` references, rewrite.
- `references/project-structure.md` — update if it mentions either prefix.
- Any `templates/*.md` with example `article:<X>` references in body — rewrite to `paper:<X>`.

## Python CLI Updates

`science-tool/src/science_tool/cli.py`:

- Line ~1004: `click.echo(f"Added article: {uri}")` → `click.echo(f"Added paper: {uri}")`.
- Line ~1493 help text: `"Evidence source (e.g. paper:doi_...)"` — already correct under new vocabulary; no change.
- Line ~965 help text: `"Provenance source reference (paper:doi_... or file path)"` — already correct; no change.

Search `cli.py` for additional `article` occurrences and rewrite to `paper` where they refer to the entity concept rather than grammar (e.g., "an article" in a docstring).

## Testing

### Unit tests: migration tool

In `science-tool/tests/test_refs_migrate_paper.py`:

- `test_migrate_rewrites_id_field` — single file with `id: article:Smith2024` becomes `id: paper:Smith2024`.
- `test_migrate_rewrites_related_list_inline` — `related: [article:Smith2024, article:Jones2023]` becomes `related: [paper:Smith2024, paper:Jones2023]`.
- `test_migrate_rewrites_related_list_multiline` — multi-line YAML list-item form rewritten.
- `test_migrate_rewrites_prose_mentions` — "see article:Smith2024" in body becomes "see paper:Smith2024".
- `test_migrate_preserves_particle_substrings` — prose containing "particle:" is NOT rewritten.
- `test_migrate_preserves_cite_prefix` — `source_refs: [cite:Smith2024]` unchanged.
- `test_migrate_dry_run_does_not_write` — confirm file contents unchanged without `--apply`.
- `test_migrate_idempotent` — applying twice yields no second-round rewrites.
- `test_migrate_counts_are_accurate` — report matches actual rewrite count.

### Unit tests: transition-window acceptance

In `science-tool/tests/test_big_picture_validator.py`:

- `test_reference_pattern_accepts_paper_prefix` — extend existing reference-pattern test to confirm both `paper:` and `article:` entity IDs resolve.

### Integration tests

- `test_refs_cli_dry_run` — `science-tool refs migrate-paper --project-root <fixture>` emits the summary without writing.
- `test_refs_cli_apply` — `--apply` rewrites a fixture project correctly; re-running is a no-op.

### Fixture

Extend the existing `science-tool/tests/fixtures/big_picture/minimal_project/` or add a dedicated fixture under `science-tool/tests/fixtures/refs/legacy_project/`:

- A question file with `related: [article:Smith2024]`.
- A paper file at `doc/papers/Smith2024.md` with `id: article:Smith2024`.
- A topic with `related: [article:Smith2024, article:Jones2023]`.
- A prose mention of `article:Smith2024` in an interpretation body.

## Sequencing with Other Specs

1. **This spec lands first.** Template renames + `science-tool refs migrate-paper` CLI + transition-window dual-acceptance in consumers that already exist.
2. **User runs migration** on tracked projects (mm30, natural-systems) — one-time manual step:
   ```
   uv run science-tool refs migrate-paper --project-root .
   uv run science-tool refs migrate-paper --project-root . --apply
   ```
3. **Knowledge-gaps spec lands next.** Its coverage metric uses `paper:` as canonical; the dual-acceptance defined here covers any projects not yet migrated.
4. **Dual-acceptance removal** (separate follow-on spec) once all tracked projects confirm migration.

## Relationship to Existing Specs

- **Knowledge-gaps spec (2026-04-19-knowledge-gaps-design.md)**: consumes this rename. The knowledge-gaps module's coverage metric uses `paper:<bibkey>` as canonical and treats `article:<bibkey>` as a transition-window alias.
- **Big-picture spec (2026-04-18-project-big-picture-design.md)**: affected only through the validator's `REFERENCE_PATTERN` extension. No semantic change.
- **Entity-aspects spec (2026-04-19-entity-aspects-design.md)**: independent. Aspect vocabulary does not reference `article:` or `paper:` prefixes.

## Out of Scope / Follow-on Work

- **Removal of dual-prefix acceptance**: a follow-on spec removes the `article:` fallback one release cycle after this spec's migration tool ships. Requires confirming all tracked projects are migrated before removing.
- **Manuscript authoring workflow features**: any features that use the new `manuscript:` prefix (e.g., `/science:draft-section`, `/science:manuscripts list`) are separate specs, not part of this rename.
- **Cross-project migration auditing**: a tool that inspects external projects and reports migration status (e.g., `science-tool refs audit`). Not needed for v1 — the migration tool itself reports unmigrated references.
- **Renaming `doc/background/papers/` → `doc/papers/`**: some projects use the longer path; harmonization is cosmetic and can wait.

## Open Decisions (resolve during implementation)

- **Migration tool directory scan**: v1 walks `doc/`, `specs/`, `tasks/`, `knowledge/`, `core/`, `papers/`. If a project uses a non-standard directory with `article:` entities, the user is responsible for adding it to the scan — or we add a `--include <path>` flag in a follow-up.
- **Encoding/whitespace preservation**: rewrites use text-level regex substitution on UTF-8 input. Preserves line endings and indentation. Does not reformat YAML. If a project has non-UTF-8 files, migration logs a warning and skips the file.
- **Partial-rewrite safety**: if a file contains both `article:` references and the new migration tool crashes mid-write, the partial state is recoverable via git. The tool does not implement transactional rollback.

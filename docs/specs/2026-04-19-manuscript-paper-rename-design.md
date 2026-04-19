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
- Update command docs that name the old template paths (`commands/research-papers.md`, `commands/search-literature.md`, any command docs that mention `paper-summary.md`) so agent workflows point at the renamed files in the same release.
- Update all `commands/*.md` and `references/*.md` that mention `article:<X>` as an example entity ID. Flat find-and-replace of the prefix.
- Cosmetic updates to `science-tool/src/science_tool/cli.py` user-facing strings that say "article" where they should now say "paper".
- Transition-window dual-prefix acceptance: downstream consumers that compare or count external-literature entity IDs continue to accept `article:<X>` as a valid legacy spelling alongside `paper:<X>` for one release cycle.
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

### Canonical bibkey extraction

Both the migration tool and downstream consumers (e.g., knowledge-gaps dedup) must agree on how bibkey is extracted from an entity ID. Rule:

- The bibkey is the full substring after the first `:` in the entity ID.
- Comparison is case-sensitive, byte-for-byte. No normalization (no lowercasing, no stripping suffixes like `Smith2024a` → `Smith2024`).
- Example: `paper:Smith2024` and `cite:Smith2024` share bibkey `Smith2024` and dedup as one paper. `paper:smith2024` does NOT dedup with `paper:Smith2024`.
- Entity IDs that do not parse as `<prefix>:<bibkey>` are not external-literature entities and are skipped for bibkey dedup.

This rule is authoritative across specs — the knowledge-gaps spec references it by name rather than restating it.

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

The rest of the template (Abstract, Outline sections, stories list) is unchanged. Placeholder name `{{paper_id}}` becomes `{{manuscript_id}}` for consistency. Convention for `manuscript_id`: a short kebab-case slug (e.g., `2026-reanalysis`, `vesicle-review`). No schema is enforced — matches how other entity IDs in Science are chosen by authors.

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
science-tool refs migrate-paper [--apply] [--project-root <path>] [--force] [--verbose]
```

Behavior:

1. Walk every markdown file under the project's canonical markdown roots. Implementation should reuse the same project-root/path-discovery conventions already used by `science_tool.refs.check_refs` and other project scanners rather than introducing a second hard-coded notion of project layout. At minimum, v1 scans `doc/`, `specs/`, `tasks/`, `core/`, `knowledge/`, and top-level project markdown files such as `RESEARCH_PLAN.md` when present.
2. For each file, apply these text rewrites:
   - YAML frontmatter `id:` fields of the form `id: article:<X>` or `id: "article:<X>"` → `id: paper:<X>` (or `id: "paper:<X>"`).
   - YAML frontmatter `type:` fields of the form `type: article`, `type: "article"`, or `type: 'article'` → `type: paper` (matching quote style preserved). Scoped to frontmatter only: prose `type: article` inside body text is left alone.
   - Any other occurrence of `article:<X>` in markdown body or YAML values → `paper:<X>`. The regex is anchored on the literal prefix `article:` followed by a valid entity-ID character class.
3. Before `--apply`: verify the project git working tree is clean by shelling out to `git status --porcelain` (run in `--project-root`). If non-empty, refuse to proceed unless `--force` is passed. Rationale: the migration produces a wide mechanical rewrite; mixing it with unrelated uncommitted work muddies the audit trail.
4. Without `--apply`: emit a unified diff (`difflib.unified_diff`) of every pending rewrite followed by a trailing per-file match-count summary, then exit 0 without writing. By default, cap diff output at the first 200 lines plus `"... N more files with changes"`; `--verbose` removes the cap. Users review the diff, then re-run with `--apply`.
5. With `--apply`: rewrite files in place using temp-file + atomic replace per file. Preserve all other formatting (indentation, whitespace, line endings). Exit 0 on success with a summary: `"Rewrote N legacy paper references in K files. Run `science-tool refs check-refs` to verify."`

Idempotency: if a project has no remaining `article:` references, the command exits 0 with "No `article:` references found; project is migrated." Re-running on a migrated project is a no-op.

No project-side migration is needed for the authoring rename, because tracked projects have no `paper:<id>` authoring entities. The migration tool focuses solely on the external-literature rename.

### Module layout

`science_tool/refs.py` already exists as a module, so this feature MUST NOT introduce a conflicting `science_tool/refs/` package.

Recommended layout:

- `science-tool/src/science_tool/refs_migrate.py` — pure-function core for scanning and rewriting legacy `article:` IDs.
- `science-tool/src/science_tool/cli.py` — add a small `@main.group()` named `refs`, then register a `migrate-paper` subcommand there.

Alternative acceptable layout:

- `science-tool/src/science_tool/refs_cli.py` — click group only.
- `science-tool/src/science_tool/refs_migrate.py` — pure-function core.

Constraint: no new package named `science_tool.refs`.

### Rewrite rules (precise)

The migration applies these rewrites, case-sensitively:

- `id: article:` → `id: paper:`
- `id: "article:` → `id: "paper:`
- `- article:` → `- paper:` (for list-item entries in `related:`, `source_refs:`, etc.)
- `[article:` → `[paper:` (for inline-list entries like `related: [article:X]`)
- `"article:` → `"paper:` (for double-quoted values inside YAML lists)
- `'article:` → `'paper:` (for single-quoted values)
- Word-boundary: `\barticle:(?=[A-Za-z0-9])` → `paper:` (for prose mentions)

Additionally, the migration rewrites the frontmatter `type:` field (scoped by a top-of-file YAML-block scanner — first `---` to second `---` only):

- `^type: article\s*$` → `type: paper`
- `^type: "article"\s*$` → `type: "paper"`
- `^type: 'article'\s*$` → `type: 'paper'`

The prose-match rule uses a word boundary to avoid accidental rewrites of substrings like `particle:` that happen to contain `article:`. Entity-ID character class is `[A-Za-z0-9_\-.]`.

## Transition-Window Dual-Prefix Acceptance

Downstream consumers that compare or count external-literature entity IDs MUST treat `article:<bibkey>` as a legacy spelling of canonical `paper:<bibkey>` during the transition window.

Implementation rule: normalize at comparison boundaries rather than attempting global alias objects. Concretely, any code that asks "is this an external-paper entity?" or deduplicates/counts external-paper IDs should canonicalize `article:<bibkey>` → `paper:<bibkey>` before comparison.

Affected code:

- `science_tool.big_picture.resolver._load_entities` and related scanning — already scans by filename, not prefix; no change.
- `science_tool.big_picture.knowledge_gaps` (not yet shipped) — its coverage rule counts both prefixes per the knowledge-gaps spec.
- Any future graph-materialization or synthesis code that handles external-paper entities — canonicalizes legacy `article:` spellings for one release cycle.

Non-goal for this spec: extending the big-picture validator to parse paper refs in generated synthesis text. Current synthesis outputs do not directly emit `paper:` IDs, so validator changes are not required for this rename alone. If a later feature emits `paper:` references in synthesized markdown, that feature must update both `REFERENCE_PATTERN` and `_collect_project_ids` together.

Deprecation: the dual-acceptance is removed in a follow-on release (one-line change in each consumer) once all tracked projects confirm migration. This spec does not commit to a specific removal date.

## Documentation Updates

All in the same PR as the rename:

- `commands/research-papers.md` and `commands/search-literature.md` — template path references must move from `paper-summary.md` to `paper.md`; any mention of authoring template `paper.md` becomes `manuscript.md`.
- `commands/search-literature.md` — mentions `doc/papers/` (no rename needed) but any example `article:<X>` IDs become `paper:<X>`.
- `commands/research-papers.md` — same.
- `commands/bias-audit.md`, `commands/compare-hypotheses.md`, `commands/next-steps.md`, `commands/research-topic.md` — check for `article:` mentions, rewrite.
- `references/role-prompts/research-assistant.md` — mentions `doc/background/papers/`; check for `article:` references, rewrite.
- `references/project-structure.md` — update if it mentions either prefix.
- `docs/specs/2026-03-02-agent-capabilities-design.md` and any other spec docs that reference `templates/paper-summary.md` or `templates/paper.md` by filename — update to the new names so historical design docs do not point implementers at deleted templates.
- Any `templates/*.md` with example `article:<X>` references in body — rewrite to `paper:<X>`.
- Grep `science-tool/src/` for hardcoded template path strings (`"paper-summary.md"`, `"paper.md"`) to catch any code that resolves templates dynamically rather than by entity type. Known call sites: template-loader helpers in `cli.py` and any `templates/` path-join helpers. Rewrite filename literals and add a one-line rename comment where it aids future reviewers.

## Python CLI Updates

`science-tool/src/science_tool/cli.py`:

- Line ~1004: `click.echo(f"Added article: {uri}")` → `click.echo(f"Added paper: {uri}")`.
- Line ~1493 help text: `"Evidence source (e.g. paper:doi_...)"` — already correct under new vocabulary; no change.
- Line ~965 help text: `"Provenance source reference (paper:doi_... or file path)"` — already correct; no change.

Search `cli.py` for additional `article` occurrences and rewrite to `paper` where they refer to the entity concept rather than grammar (e.g., "an article" in a docstring).

### Other Python sources (test audit)

Beyond `cli.py`, nine test modules currently contain `article:` string literals (as of 2026-04-19):

- `science-tool/tests/test_paper_model.py`
- `science-tool/tests/test_graph_cli.py`
- `science-tool/tests/test_inquiry_cli.py`
- `science-tool/tests/test_cross_impact.py`
- `science-tool/tests/test_layered_claim_migration.py`
- `science-tool/tests/test_graph_export.py`
- `science-tool/tests/test_causal.py`
- `science-tool/tests/test_project_model_migration.py`
- `science-tool/tests/test_causal_cli.py`

Triage each match against this rule:

- **Assertion on current entity-prefix output (canonical `paper:`)**: rewrite `article:` → `paper:`.
- **Regression fixture intentionally exercising the legacy prefix via the transition-window alias path**: keep as `article:` and add a one-line `# deliberate: legacy alias` comment so readers know it's intentional.
- **Dead fixture with no assertion on the prefix**: rewrite mechanically.

This audit is an explicit step in the implementation plan and is NOT a side effect of `science-tool refs migrate-paper` (which touches markdown only).

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

In `science-tool/tests/test_refs_migrate_paper.py` or a small dedicated normalization test module:

- `test_external_paper_prefix_normalization_accepts_article_and_paper` — canonicalization helper maps both `article:Smith2024` and `paper:Smith2024` to the same canonical key.
- `test_external_paper_prefix_normalization_preserves_non_paper_ids` — `question:q01`, `cite:Smith2024`, `manuscript:m01` are unchanged.

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
   uv run science-tool refs migrate-paper --project-root .               # dry-run, review diff
   uv run science-tool refs migrate-paper --project-root . --apply       # perform rewrite
   uv run science-tool refs check-refs --project-root .                  # verify no dangling refs
   ```
   The `check-refs` step catches any mid-migration half-states (e.g., an `article:` reference that the regex missed because the entity ID used an unusual character) before the change is committed.
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

- **Migration tool directory scan**: v1 uses existing project markdown discovery conventions rather than a fresh hard-coded path list. If a real project still proves to house `article:` IDs outside those roots, add `--include <path>` in a follow-up rather than baking speculative roots into v1.
- **Encoding/whitespace preservation**: rewrites use text-level regex substitution on UTF-8 input. Preserves line endings and indentation. Does not reformat YAML. If a project has non-UTF-8 files, migration logs a warning and skips the file.
- **Partial-rewrite safety**: per-file writes are atomic, but the overall migration is not transactional across the whole project. If the command stops halfway through, rerunning it is safe and git still provides recovery.

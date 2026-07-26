# Context-budget Slice 3 — task storage split — design

**Status:** design approved (2026-07-26), ready for an implementation plan.
**Parent design:** [`2026-07-24-agent-context-budget-program-design.md`](2026-07-24-agent-context-budget-program-design.md) §"Slice 3 — task storage". Slices 1 and 2 have landed on local main; Slice 3's gate (1 & 2) is satisfied.

## Goal

Replace the single aggregated `tasks/active.md` with one file per open task —
`tasks/active/tNNN-slug.md`, YAML frontmatter + markdown body, mirroring the
`entities/` convention — so each open task is a small (~1,800 char) file that is
cheap to read, cheap to re-inject on compaction, and complete rather than
silently truncated at the host's file-read cap. `active.md` is removed outright
(no dual-read compatibility layer). Closed tasks stay as monthly ledgers under
`tasks/done/YYYY-MM.md`; `tasks/archive.md` (historical prose aliases) is
unchanged.

## Why split rather than shrink

The host restores previously-read files on every compaction; a file just under
the read cap (~87,500 chars) is the most expensive thing to have read, and a
file over it is downgraded to a path-only stub (useless). `tasks/active.md` in
the largest adopting project is ~391k chars — over the cap, so it reads as a
silently truncated *oldest-first* prefix. Per-task files sit far below the
expensive band and are individually complete. Trimming `active.md` toward the
cap would move it *into* the expensive band; splitting avoids the band entirely.

## Decisions (approved)

1. **Format = YAML frontmatter + body**, mirroring `entities/`. Not the lighter
   "keep the `## [tNNN]` DSL block per file" option — the toolkit gets one
   record convention across `entities/` and `tasks/`.
2. **Migration reach = ship the migrator + migrate `science/meta` in-slice
   only.** The other five repos carrying `tasks/active.md`
   (natural-systems, protein-landscape, 3d-attention-bias, seq-feats, cats) are
   migrated later by running the command in each, on that repo's own branch —
   respecting per-repo (Dropbox) branch volatility and avoiding a cross-repo
   transaction. The roster is DERIVED from the sibling set at run time, never
   hard-coded.

## Design

### 1. File format & (de)serialization

`tasks/active/tNNN-slug.md`:

```
---
id: t042
title: Wire --since filter
type: feature
priority: P1
status: active
aspects: [software-development]
related: [hypothesis:h003]
blocked-by: []
group: ""
parent: ""
created: 2026-07-20
completed: null
---

Description body in markdown. Dated journal notes are appended in the body,
exactly as today (`_format_note` / `_append_note_to_description`).
```

- Frontmatter carries the full authored `science_model.Task` field set
  (`id, project, title, type, aspects, priority, status, blocked_by, related,
  parent, group, artifacts, findings, created, completed`). This is a superset
  of what the current `## [tNNN]` DSL emits (the DSL drops
  `project`/`artifacts`/`findings`); migration is therefore lossless w.r.t.
  what `active.md` stores and additionally admits fields the model already has.
- New functions in `tasks.py`: `parse_task_file(path) -> Task` (frontmatter via
  `markdown_utils.frontmatter_span`, body → `description`) and
  `render_task_file(task) -> str` (canonical frontmatter renderer + body). A
  per-file round-trip verifier mirrors the existing `_verify_round_trip`:
  `parse_task_file` of `render_task_file(task)` must equal `task`.
- Slug derivation reuses `entities.derive_slug(title)` (lowercase, hyphenate,
  word-boundary truncate). `id` is the stable identity; the slug is cosmetic. A
  title change on `tasks edit` re-derives the slug and renames the file (old file
  removed, new written, same `id`).

### 2. Read/write path centralization

The lever for the ~14 readers is to centralize on one read entry point.

- `_read_active(tasks_dir)` → parse every `tasks/active/*.md` (sorted by id) into
  `list[Task]`, replacing `parse_tasks(tasks_dir / "active.md")`.
- New `write_task_file(tasks_dir, task)` and `delete_task_file(tasks_dir, task)`
  operating on the per-task path (derived from id+slug; locate existing file by
  `tNNN-*.md` glob so a stale slug is found and replaced).
- Rewrite every mutator to per-file: `add_task`, `append_task_note` (edit),
  `tasks edit` field updates, `complete_task`/`retire_task`/`defer`/`block`/
  `unblock`, and `_move_task_to_done` (write the done ledger, delete the active
  per-task file — same atomicity guarantee as today).
- `next_task_id` scans `tasks/active/*.md` + `tasks/done/*.md` for the max id.
  `known_task_ids`, `find_task_location`, `_task_search_paths` updated to the
  per-file layout. The `_task_allocation_lock` stays — it still serializes id
  allocation and creation across concurrent processes.
- The remaining direct readers that don't go through the helpers —
  `big_picture/validator.py`, `curate/inventory.py`, `dag/refs.py`,
  `graph/health_checks/legacy_task_type.py`,
  `graph/health_checks/lingering_tags.py`, `refs.py`,
  `validate/checks/cross_references.py`, `validate/checks/project_readme.py`,
  `validate/checks/tasks.py`, `validate/_helpers.py`, `tasks_archive.py`,
  `correspondence/probe.py` — are each pointed at the centralized read
  (`_read_active` / `_task_search_paths` / `known_task_ids`) rather than
  `tasks_dir / "active.md"` directly. Where a check specifically asserts
  something about the *file*, it is re-expressed against the directory.

### 3. Migrator

`science tasks migrate-storage [--apply | --resume]`, adapting the transactional
pattern of `datasets/capability_migration.py`:

- **Plan (dry-run default):** parse `tasks/active.md`; compute the target
  per-task file for each task; report what would be written. Refuse if
  `tasks/active/` already exists and is non-empty (already migrated), or if
  `tasks/active.md` is absent (nothing to do).
- **Apply (`--apply`):** journal the pre-image (hash of `active.md`) + the full
  post-images (each per-task file path + content); write all per-task files;
  then **delete `tasks/active.md` LAST and confirm it is gone**; then clear the
  journal. Deleting `active.md` is the terminal marker (the analogue of the
  capability migrator's "pin set last").
- **Resume (`--resume`):** finish an interrupted apply from the journal — write
  any missing per-task files, delete `active.md`, clear the journal. Never
  re-plans; refuses if the source changed under it.
- Journal at `.science/task-storage-migration.journal` (mirrors the capability
  migrator's location idiom).
- Migrate `science/meta` in-slice as the worked example (verify its branch
  first — the meta project is in-repo, so this is a normal commit here).

### 4. Storage adapter & docs

- `graph/storage_adapters/task.py`: `discover()` already `rglob`s
  `tasks/**/*.md` (skipping `archive.md`), so it will find per-task files; update
  `load_raw` / the parse call to use `parse_task_file` for files under
  `tasks/active/` while continuing to parse `tasks/done/*.md` ledgers with the
  existing DSL parser. (Done ledgers keep the `## [tNNN]` block format.)
- Docs: update the descriptions that treat `active.md` as an aggregate — the
  `big-picture.md:68` "If `tasks/active.md` is a single aggregated file" note,
  `create-graph.md:48` Canonical Inputs list, the `templates/agents-md.md` /
  `templates/core-overview.md` store pointers, and the `create-project` scaffold
  section — to describe `tasks/active/` one-file-per-task. This is bounded
  description maintenance and does NOT reopen the Slice-2 read-directive rules
  (those docs still point agents at `science tasks list`, not at reading files);
  the content guard `test_no_raw_task_file_reads_in_docs.py` allow-list is
  updated for any changed legit line.

## Non-goals

- Splitting `tasks/done/YYYY-MM.md`: closed tasks are an append-only ledger, not
  worked documents; splitting natural-systems' 4 files into ~700 buys no read
  benefit, and Slice 2 already gives `done/` a bounded query surface
  (`tasks list --status done --since`).
- Migrating the other five repos in this slice (decision 2).
- Any dual-read / compatibility layer for `active.md`.
- Changing `tasks/archive.md` (historical prose aliases).

## Risks

- **Blast radius: ~14 readers.** Mitigated by centralizing on `_read_active` /
  the search-path helpers; the few checks that assert file-level facts are
  re-expressed against the directory and covered by their existing tests.
- **Migration interrupted mid-write.** Mitigated by the journal + delete-last +
  `--resume`, per the capability-migrator pattern.
- **Round-trip fidelity.** A per-file round-trip verifier + a migration test
  that the parsed per-task set equals the parsed `active.md` set (same tasks,
  same fields) guards against a lossy conversion.
- **`meta` branch volatility.** `science/meta` is in-repo (this worktree), so its
  migration commits land here; still verify the branch before committing.

## Testing

- `parse_task_file`/`render_task_file` round-trip (all fields, empty optionals,
  journal-note bodies, unicode titles).
- Slug derivation + rename-on-title-change (file renamed, id stable, no orphan).
- Read path: `_read_active` over a `tasks/active/` dir returns the same task set
  a DSL `active.md` would have.
- Every mutator (`add`/`edit`/`note`/`done`/`defer`/`retire`/`block`/`unblock`/
  `archive`) writes/updates/deletes the correct per-task file and leaves the
  round-trip clean.
- Migrator: dry-run report; apply produces per-task files matching the source
  task set and removes `active.md`; refuse on already-migrated / absent source;
  `--resume` finishes an interrupted journal; source-changed-under-migration
  refusal.
- Adapter: graph build over a split `tasks/active/` yields the same task nodes.
- The full validate/health/refs/curate/big-picture readers work over the split
  layout (their existing tests, re-pointed fixtures).
- `science/meta` migrates clean and its `science tasks list` is unchanged
  post-migration.

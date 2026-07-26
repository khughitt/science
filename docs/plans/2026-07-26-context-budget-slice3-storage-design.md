# Context-budget Slice 3 — task storage split — design

**Status:** design approved (2026-07-26), ready for an implementation plan.
**Parent design:** [`2026-07-24-agent-context-budget-program-design.md`](2026-07-24-agent-context-budget-program-design.md) §"Slice 3 — task storage". Slices 1 and 2 have landed on local main; Slice 3's gate (1 & 2) is satisfied.

## Goal

Replace the single aggregated `tasks/active.md` with one file per open task —
`tasks/active/tNNN-slug.md`, YAML frontmatter + markdown body, mirroring the
`entities/` convention — so each open task is a small (~1,800 char) file that is
cheap to read, cheap to re-inject on compaction, and complete rather than
silently truncated at the host's file-read cap. `active.md` is removed outright
(no dual-read compatibility layer). `active/` holds **open** tasks only; any
terminal (`done`/`retired`) tasks still sitting in `active.md` must be archived
(`science tasks archive --apply`) before the split — the migrator refuses
otherwise (see §3). Closed tasks stay as monthly ledgers under
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
blocked_by: []
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
- **Frontmatter keys use the model field names verbatim, with underscores** —
  `blocked_by`, not the DSL's `blocked-by`. The DSL's hyphenated keys
  (`blocked-by`) are converted to underscores on migration; `render_task_file`
  emits underscores. `parse_task_file` **rejects unknown frontmatter keys**
  (fail early, no silent drop) so a stray `blocked-by` or typo surfaces instead
  of yielding a silently empty list. (Rationale: pydantic would otherwise ignore
  `blocked-by` and produce an empty `blocked_by`.)

### 1a. Storage identity invariants

These hold for every `tasks/active/*.md` file and are enforced on read, on
mutation, and by the migrator (see §3):

- **Canonical id.** `id` matches the repo's existing canonical pattern
  `_TASK_ID_PATTERN = r"t[0-9]{3,}"` (tasks.py:49) — reuse that constant, do NOT
  introduce a looser `t\d+` (which would admit `t1`, `t01`, or Unicode digits).
  `parse_task_file` refuses a non-canonical id rather than materializing it.
- **Filename ↔ frontmatter agreement.** The filename's `tNNN` prefix equals the
  frontmatter `id`. A mismatch is an error, not a silent reconciliation.
- **Unique ids across `tasks/active/`.** No two active files share an `id`. On
  read this is a hard error (the current aggregate parser silently accepted
  duplicate `## [tNNN]` blocks; the split makes uniqueness structural and
  checked).
- **Exactly one file per id on mutation.** `write_task_file` / `delete_task_file`
  locate the existing file by a `tNNN-*.md` glob and require **exactly one**
  match (zero for a fresh `add`); 2+ matches is an error, never an
  overwrite-one-arbitrarily.
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
  `unblock`, and `_move_task_to_done`.
- **`_move_task_to_done` is idempotent-recoverable.** In the split world it must
  write the done ledger AND delete the active per-task file — two steps that can
  crash between (leaving both an active copy and a ledger copy; a naive retry
  would append a duplicate ledger entry). Define the recovery contract: before
  appending, check whether the done ledger already contains this `id`. If it
  does and the ledger entry is **byte-exact** to what we would write → treat the
  ledger write as already-done and proceed to delete the active file (idempotent
  replay). If it contains a **different** entry for that id → REFUSE (conflict,
  no silent overwrite). Otherwise append, then delete the active file. Order is
  ledger-write-first, active-delete-last, so a crash-then-retry converges. Add a
  crash-between-write-and-delete test.
- **Archived tasks keep the ledger path.** `append_task_note` and `tasks edit`
  today locate a task via `find_task_location`, which can resolve into a
  `tasks/done/YYYY-MM.md` ledger (`tasks.py:512`, `:676`). When the located task
  lives in a done ledger, the mutation continues to rewrite that monthly ledger
  in place (DSL block) — it does NOT create or rename a `tasks/active/` file.
  The title→filename rename rule applies ONLY to active per-task files. This
  path is covered by tests.
- **`tasks_cli.py` direct-`active.md` callers are in scope** and re-pointed at
  the centralized read: `tasks fix-blockers` (`tasks_cli.py:314`), the
  `tasks list` legacy-blocker warning pass (`tasks_cli.py:673`,
  `parse_tasks_for_cli`), and `tasks summary` (`tasks_cli.py:885`,
  `parse_tasks`). Without this, post-migration `summary` reports zero and
  `fix-blockers` becomes a no-op. `parse_tasks_for_cli` gains a directory-aware
  form (or is called over the per-file read) so its warning surface is preserved.
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

- **`active/` holds OPEN tasks only — terminal tasks are refused, not split.**
  `tasks/active.md` can legitimately still contain `done`/`retired` tasks that
  have not been archived yet (e.g. `meta/tasks/active.md` currently holds `t089`
  and `t093`, both `done`). Splitting those into `active/` would contradict the
  "one file per *open* task" goal. The migrator therefore **refuses if any
  source task has a terminal status**, directing the user to run
  `science tasks archive --apply` first (the existing, tested machinery that
  routes terminal tasks — including undated ones — into `done/YYYY-MM.md`). The
  migrator does NOT re-implement archiving. The worked example is
  `tasks archive --apply` **then** `migrate-storage --apply` on `science/meta`.
  The migration equality invariant is thus over OPEN tasks: after archiving, the
  migrated `active/` set equals the (now open-only) `active.md` set.
- **Plan (dry-run default):** parse `tasks/active.md`; compute the target
  per-task file for each task; report what would be written. Refuse if
  `tasks/active/` already exists and is non-empty (already migrated), or if
  `tasks/active.md` is absent (nothing to do), or if **any source task is
  terminal** (see above). **Collision & identity checks (all must pass before
  any write):** every source task has a canonical `t[0-9]{3,}` id; **source ids
  are unique** (the aggregate parser accepts duplicate `## [tNNN]` blocks — a
  duplicate id is a hard refusal, listing the offenders); the computed **target
  paths are unique** (two tasks cannot resolve to the same `tNNN-slug.md`; since
  the path is `id`-prefixed, unique ids give unique paths, but this is asserted,
  not assumed); and no target path already exists.
- **Apply (`--apply`):** runs under the `_task_allocation_lock` for the whole
  operation (no concurrent writer). Journal the pre-image (hash of `active.md`) +
  the full post-images (each per-task file path + content); write all per-task
  files; **re-confirm `active.md` still hashes to the journalled pre-image**
  (refuse + retain journal if it changed under us); then **delete `tasks/active.md`
  LAST and confirm it is gone**; then clear the journal. Deleting `active.md` is
  the terminal marker (the analogue of the capability migrator's "pin set last").
- **Resume (`--resume`):** finish an interrupted apply from the journal, never
  re-planning. **First check the source:** if `tasks/active.md` is still present,
  its current hash MUST equal the journalled pre-image; if it changed (an edit
  after the interruption), **REFUSE and retain the journal** — the migration plan
  is stale and resuming would discard the edit. If `active.md` is absent, that is
  the post-delete completion case (below). Then, for **each** journalled
  post-image, classify the target's current state and act — the crux of a safe
  resume while `active.md` may still be the only complete copy:
  - **absent** → write it from the journal's post-image.
  - **present and byte-exact to the post-image** (hash match) → accept, no write.
  - **present but different** → **REFUSE and retain the journal** (a file changed
    under the migration; never overwrite and never delete the source).
  Only once the source-hash check passes (or `active.md` is already gone) AND
  every post-image is present-and-exact does resume delete `active.md` (if still
  present) and clear the journal. This makes resume idempotent and covers the
  **crash-after-`active.md`-deleted-but-before-journal-clear** case: `active.md`
  absent + all post-images exact ⇒ just clear the journal.
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
- Frontmatter contract: `blocked_by` (underscore) round-trips; an unknown key
  (e.g. `blocked-by` or a typo) is REJECTED, not silently dropped.
- Storage identity: non-canonical id rejected — specifically test the short/
  non-ASCII cases the loose `t\d+` would have admitted (`t1`, `t01`, Unicode
  digits) are all rejected by `t[0-9]{3,}`; filename/frontmatter-id mismatch
  rejected; two active files with the same id → read error; a mutation finding
  2+ `tNNN-*.md` matches → error (no arbitrary overwrite).
- Active→done idempotency: crash-between-ledger-write-and-active-delete leaves an
  exact ledger copy → retry deletes the active file without a duplicate append; a
  conflicting ledger copy for the same id → refusal.
- Slug derivation + rename-on-title-change (file renamed, id stable, no orphan).
- Read path: `_read_active` over a `tasks/active/` dir returns the same task set
  a DSL `active.md` would have.
- Every mutator (`add`/`edit`/`note`/`done`/`defer`/`retire`/`block`/`unblock`/
  `archive`) writes/updates/deletes the correct per-task file and leaves the
  round-trip clean.
- Archived-task edit/note: a `tasks edit`/`tasks note` on a task living in
  `done/YYYY-MM.md` rewrites that ledger in place and creates NO `tasks/active/`
  file.
- `tasks_cli` re-points: post-migration `tasks summary` reports the real counts,
  the `tasks list` warning pass still surfaces legacy-blocker warnings, and
  `tasks fix-blockers` still repairs.
- Migrator: dry-run report; **duplicate source id → refusal (offenders listed);
  colliding/existing target path → refusal; any terminal source task → refusal
  pointing at `tasks archive --apply`**; apply produces per-task files matching
  the source OPEN-task set and removes `active.md`; refuse on already-migrated /
  absent source.
- Migrator source-hash safety: apply re-confirms `active.md` matches the
  pre-image before deleting (refuse if changed); resume refuses if a still-present
  `active.md` no longer matches the journalled pre-image (an interruption-time
  edit is preserved, not discarded).
- Migrator resume states: absent post-image → written; present-exact → accepted;
  **present-different → refusal with journal retained**; crash-after-delete
  (`active.md` gone + all post-images exact) → journal cleared, success.
- Worked example: `science/meta` migrates via `tasks archive --apply` then
  `migrate-storage --apply`; `t089`/`t093` land in a `done/` ledger (not
  `active/`), and post-migration `science tasks list` is unchanged.
- Adapter: graph build over a split `tasks/active/` yields the same task nodes.
- The full validate/health/refs/curate/big-picture readers work over the split
  layout (their existing tests, re-pointed fixtures).
- `science/meta` migrates clean and its `science tasks list` is unchanged
  post-migration.

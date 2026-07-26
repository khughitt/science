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
terminal (`done`/`retired`) tasks still sitting in `active.md` are routed to the
monthly done ledger **by the migrator itself, in the same transaction** (see §3)
— there is no separate archive-first step, because the shipped toolkit's
`tasks archive` reads the split layout and can no longer read a legacy
`active.md`. Closed tasks stay as monthly ledgers under `tasks/done/YYYY-MM.md`;
`tasks/archive.md` (historical prose aliases) is unchanged.

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
- **Strict YAML: reject duplicate and merge keys.** `markdown_utils.frontmatter_span`
  parses with plain `yaml.safe_load` (`markdown_utils.py:222`), which is
  **last-wins on duplicate keys** and expands YAML merge keys (`<<`) — both of
  which would bypass the unknown-key check and silently pick one of two conflicting
  values. `parse_task_file` therefore does NOT trust `frontmatter_span`'s dict
  alone: it composes the frontmatter YAML node and rejects duplicate keys and
  merge keys **before** model construction, reusing the strict recursive checker
  already written for run records
  (`graph/autonomous_runs._reject_duplicate_and_merge_keys`,
  `autonomous_runs.py:24`). A frontmatter block with `priority:` twice, or a `<<`
  merge, is an error, not a last-wins silent pick.
- **Required persisted keys.** `parse_task_file` enforces a required-key set
  **before** model construction: `id`, `title`, `status`, `priority`, `aspects`,
  `created`. `Task` defaults these (`priority="P2"`, `status="proposed"`,
  `aspects=[]`, `created=date.today()` — model `tasks.py:30-39`), so a
  hand-edited or foreign file missing `created` would otherwise silently acquire
  *today's* date and one missing `status` would silently become `proposed`.
  Missing any required key is an error naming the key and file, not a default.
  The remaining fields (`type`, `project`, `related`, `parent`, `group`,
  `blocked_by`, `artifacts`, `findings`, `completed`) may be absent and take
  their model defaults. `render_task_file` always emits the full field set, so
  every migrator- or toolkit-written file round-trips with all required keys
  present; the required-key check only bites files edited by hand.

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
- **Two predicates: nominal identity vs replay equivalence.** `(id, created)` is
  NOT sufficient to prove two records are the same task — unrelated tasks
  routinely share a creation date (the archive fixture already exhibits this:
  a source `t002`/`2026-03-01`/"Done in March" and a ledger `t002`/`2026-03-01`/
  "Already archived" differ only in title/body —
  `test_tasks_archive.py:39,264`). Accepting them as equivalent would delete the
  source. So the design uses two separate predicates:
  - **Nominal identity = `id` equality.** This is what "the same task id" means
    for uniqueness (§1a) and for locating a task. It does NOT license a
    skip/delete.
  - **Migration / archive dedup = STRUCTURAL equality (all `Task` fields
    equal).** `plan_ledger_appends` (§3) treats a terminal task already present
    in a ledger as already-archived **only if the two records are fully equal**;
    an `id` match with *any* differing field is a **conflict → REFUSE**, never a
    silent skip. This tightens the existing `apply_archive`, which today skips a
    destination-local duplicate id regardless of content
    (`tasks_archive.py:248`; `test_apply_skips_duplicate_id_in_destination`
    asserts that silent skip) — a latent silent-data-drop. The plan therefore
    **changes `apply_archive`'s duplicate handling to structural-equality-or-
    conflict and updates that test** (a conscious behavior change, aligned with
    "fail early / no silent fallbacks").
  - **Move-recovery equivalence (`_move_task_to_done`, §2) = same `id`, ledger
    status terminal, and equality on every *transition-stable* field** — i.e.
    all fields except `status`, `completed`, and `description` — with the ledger
    `description` being the active `description` optionally followed by the
    completion/retire suffix (prefix match). Only `completed` and that suffix may
    differ (they are what the completing transition itself adds, and a next-day
    retry changes `completed`). Any transition-stable field differing → conflict
    → REFUSE. This is looser than structural equality (a retry legitimately
    changes `completed`/suffix) but far stronger than `(id, created)`.
- Slug derivation reuses `entities.derive_slug(title)` (lowercase, hyphenate,
  word-boundary truncate). `id` is the stable identity; the slug is cosmetic. A
  title change on `tasks edit` re-derives the slug and renames the file (old file
  removed, new written, same `id`).

### 1b. Storage-state gate (fail loudly on non-split layouts)

With `active.md` removed from every read path, a project that has NOT yet been
migrated (or crashed mid-migration) would otherwise read as **zero tasks** and
`add` would allocate an id blind to the legacy file's ids, colliding on the next
migration. That silent-empty is the exact failure the "fail early" rule forbids.
So a single classifier gates every normal command:

`_tasks_storage_state(tasks_dir) -> StorageState`:

The journal's presence (not the layout) is the authority on whether a migration
is in flight — a half-written `active/` beside `active.md` with **no** journal is
NOT a resumable migration:

- **EMPTY** — no `active.md`, no `active/`, no journal (fresh project). Treated as
  a writable split: readers return `[]`, `add` creates `active/`.
- **SPLIT** — `active/` present, no `active.md`, no journal. The normal operating
  state.
- **LEGACY** — `active.md` present, `active/` absent, no journal. Pre-migration.
- **MIGRATING** — the migration journal (`.science/task-storage-migration.journal`)
  exists (whatever the layout). An interrupted apply/resume.
- **CONFLICT** — both `active.md` and `active/` present but **no journal**. Not a
  migration state — `active/` was created outside the migrator (e.g. a partial
  hand copy). Unsafe to auto-resume (no journal to replay) and unsafe to
  `--apply` (a non-empty `active/` would be clobbered).

`_read_active` and every mutator call `_require_split(tasks_dir)` first:

- EMPTY / SPLIT → proceed.
- LEGACY → raise an actionable error: *"tasks/active.md predates the storage
  split; run `science tasks migrate-storage --apply`."* No allocation, no read
  of a stale layout.
- MIGRATING → raise: *"an interrupted storage migration is in progress; run
  `science tasks migrate-storage --resume`."*
- CONFLICT → raise: *"both tasks/active.md and tasks/active/ exist with no
  migration journal; inspect and remove one by hand — this is not an
  auto-resumable migration."*

**`migrate-storage` mode validity is defined by state** (it is the only
gate-exempt command): `--apply` is valid **only in LEGACY** (refuses in
EMPTY/SPLIT = nothing to do, MIGRATING = use `--resume`, CONFLICT = manual);
`--resume` is valid **only in MIGRATING** (refuses elsewhere — in particular it
does NOT run in CONFLICT, since there is no journal to finish). Because `add` is
blocked in LEGACY, `next_task_id` never allocates against a half-seen id space —
the collision path finding 1 (round 3) describes cannot occur.

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
  append the done ledger AND delete the active per-task file — two steps that can
  crash between (leaving both an active copy and a ledger copy; a naive retry
  would append a duplicate ledger entry). The recovery predicate must NOT be
  byte-exactness: completion derives `completed` and the destination month from
  `date.today()` and may append a supplied note (`tasks.py:599,605,601`), so a
  retry the next day — or without the identical note — would neither reproduce
  the prior block nor search the same month, and byte-exact matching would refuse
  a legitimate replay. Instead: **search every `tasks/done/*.md` ledger** (not
  just the current month) for this `id`, and apply the §1a **move-recovery
  equivalence** predicate (same id, terminal ledger status, all transition-stable
  fields equal, description prefix-match). **Exactly one** occurrence that
  satisfies it → the ledger append already succeeded on a prior attempt; skip the
  append and just delete the active file (idempotent replay). An `id` occurrence
  that FAILS the predicate (a transition-stable field differs), or **more than
  one** occurrence of the id → REFUSE (no silent overwrite).
  Otherwise append to this month's ledger, then delete the active file. Order is
  ledger-append-first, active-delete-last, and the operation runs while the
  caller holds the allocation lock (`_move_task_to_done` requires-held, never
  re-acquires — see the lock bullet), so a crash-then-retry converges without
  duplicating.
  Add a crash-between-append-and-delete test *and* a next-day-retry test (retry
  clock advanced past a month boundary → still no duplicate).
- **A crash-duplicate is inert to ordinary mutators — active+done duplication is
  a hard error for normal lookup.** Between the ledger-append and the active
  delete, the same `id` exists in both an `active/` file and a `done/` ledger.
  Today `find_task_location` merely *warns* and picks the active copy
  (`tasks.py:457-459`), so `edit`/`note`/`defer`/`block`/`unblock` would silently
  mutate the active copy while the terminal ledger copy diverges. Instead, the
  shared per-id lookup used by **all non-recovery mutators** (`edit`, `note`,
  `defer`, `block`, `unblock`) RAISES when an id resolves in both an active file
  and a done ledger — *"task tNNN exists in both tasks/active/ and a done ledger
  (interrupted completion); re-run `science tasks done`/`retire` to reconcile."*
  Only `complete_task`/`retire_task`'s recovery path (`_read_active` +
  `_move_task_to_done`, which does the move-recovery reconcile above) may resolve
  the duplicate; it does not go through this guard. `defer`/`block`/`unblock`
  today read only `active.md` (`tasks.py:612,652,666`) and so must gain the
  cross-layer check for the id they mutate.
- **`tasks edit` cannot terminalize an active task in place.** `edit_task`
  today assigns `status` and rewrites the task's current location
  (`tasks.py:697,707`); it only blocks the *inverse* (archived → non-closed).
  In the split world, letting `edit --status done|retired` set a terminal status
  and rewrite the file **in `active/`** would leave a terminal task in `active/`,
  violating "active holds open tasks only." So an `edit` that would move an
  **active** task to a terminal status is **REFUSED**, with the message to use
  `science tasks done` / `science tasks retire` (the blessed paths that route
  through the `_move_task_to_done` transaction). `edit` continues to handle all
  non-terminal transitions and the existing archived-task rules.
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
  per-file layout.
- **One lock discipline — acquire once at the top, require-held inside.** Today
  only `add_task` acquires `_task_allocation_lock` (`tasks.py:548`), which is
  enough when the sole race is duplicate id allocation. The split adds multi-step
  read-modify-write mutations (append-ledger-then-delete-active;
  rename-on-title-change) whose atomicity matters, and the migrator's "no
  concurrent writer" guarantee is only real if **every** writer takes the same
  lock. But the lock must be acquired *exactly once per operation*:
  `_task_allocation_lock` opens the sentinel afresh and takes `flock(LOCK_EX)`
  (`tasks.py:349`), and on Linux a second `flock(LOCK_EX)` via a distinct open
  file description **deadlocks in the same process** — so a top-level
  `complete_task` that holds the lock and calls `_move_task_to_done` which
  re-acquires would hang. The contract:
  - **Top-level operations acquire the lock once:** `add_task`,
    `append_task_note`, `edit_task`, `complete_task`, `retire_task`,
    `defer_task`, `block_task`, `unblock_task`, `tasks fix-blockers` apply
    (`tasks_cli.py:372`), and `tasks archive` (its plan **and** apply/revalidation
    share **one** lock window — `tasks_cli.py:444`/`:419`).
  - **Internal helpers require the lock already held, and never re-acquire:**
    `_move_task_to_done`, `write_task_file`/`delete_task_file`, the exported
    `write_task_location` (used by note/edit — `tasks.py:463`), and
    `apply_archive` (invoked by the `tasks archive` command that already holds the
    lock). Every one of these is either made a private require-held helper or
    documents/asserts "lock must be held by caller" (a `lock_held` guard, or
    restructuring so the lock always wraps the top-level), rather than opening the
    sentinel again. The require-held set is exhaustive: **no writer** of an
    `active/` file or a `done/` ledger acquires the lock itself.
  - **The migrator's apply and resume each acquire the lock once** for the whole
    operation.
  - **Interactive `fix-blockers` does NOT hold the lock across its prompt loop.**
    Holding an exclusive `flock` while blocked on `click.prompt` for human input
    (`tasks_cli.py:352-368`) would stall every other task writer indefinitely.
    Instead: read the active set and record its hash **without** holding the lock;
    run the interactive loop; then acquire the lock and do an **optimistic
    source-hash recheck** — re-read the active set and confirm it still hashes to
    what was read before prompting; if it changed under the user, **abort the
    write** with a "tasks changed under you; re-run fix-blockers" message rather
    than clobbering the concurrent write. The write itself (per-file updates)
    happens inside that second lock window.
  Read-only paths (`_read_active`, checks) do not take it. This is a
  Global-Constraint-level invariant for the plan: a mutator that does not hold
  the lock — or an internal helper that re-acquires it — is a defect.
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

- **`active/` holds OPEN tasks only — terminal tasks are routed to the done
  ledger in the same transaction (NOT refused, NOT split).** `tasks/active.md`
  can legitimately still contain `done`/`retired` tasks that have not been
  archived yet (e.g. `meta/tasks/active.md` currently holds `t089` and `t093`,
  both `done`). An earlier revision had the migrator *refuse* and tell the user
  to run `science tasks archive --apply` first — but the shipped toolkit repoints
  `tasks archive` at the split `active/` layout (§2), so on a still-legacy
  project `tasks archive` reads an empty `active/` and cannot touch the terminal
  tasks in `active.md`: that instruction is unrunnable. Instead the migrator
  **partitions the parsed `active.md` into open and terminal tasks and, in the
  same transaction, writes open → `tasks/active/tNNN-slug.md` and appends
  terminal → `tasks/done/YYYY-MM.md`**. It does NOT re-implement archiving, but it
  cannot call `apply_archive` either: that function *writes* (and rewrites
  `active.md`) and skips a destination-local duplicate id silently regardless of
  content (`tasks_archive.py:213,248,265`), whereas the migrator needs a **pure**
  computation of the ledger post-images to journal *before* any write. So the fix
  is a small **extraction**: a pure helper — call it
  `plan_ledger_appends(terminal_tasks, done_ledgers, *, today) -> (postimages, conflicts)`
  — that computes each destination's full post-image (month via
  `_destination_for`, `today` passed explicitly and journalled) and returns
  conflicts instead of silently skipping. Both `apply_archive` (its
  transaction owner writes the result + rewrites `active.md`) and the migrator
  (journals the post-images, then writes) call this one helper. The equality
  invariant splits accordingly: after migration the `active/` set equals the
  source's OPEN tasks and every terminal source task appears once in a `done/`
  ledger.
- **Terminal dedup is store-wide, not destination-local.** An undated terminal
  task may already have been appended to an *earlier* month's ledger before a
  crash, while a later migration computes *this* month's file — a
  destination-only check would then duplicate it. `plan_ledger_appends` therefore
  indexes **every** `tasks/done/*.md` by id first: a terminal source task whose
  id already appears exactly once and is **structurally equal** (all `Task`
  fields — §1a migration/archive dedup predicate) is treated as already-archived
  (no new append); an id present with any differing field, or an id appearing in
  more than one ledger, is a conflict → refuse.
- **Plan (dry-run default):** parse `tasks/active.md`; partition into open and
  terminal tasks; compute the target per-task file for each open task and the
  done-ledger destination for each terminal task (via
  `tasks_archive._destination_for`, passing an **explicit `today`** so the month
  choice for undated terminals is fixed once and journalled — never re-derived on
  resume); report what would be written. Refuse if `tasks/active/` already exists
  and is non-empty (already migrated) or if `tasks/active.md` is absent (nothing
  to do). **Collision & identity checks (all must pass before any write):** every
  source task has a canonical `t[0-9]{3,}` id; **source ids are unique** (the
  aggregate parser accepts duplicate `## [tNNN]` blocks — a duplicate id is a
  hard refusal, listing the offenders); the computed open **target paths are
  unique** (two tasks cannot resolve to the same `tNNN-slug.md`; since the path
  is `id`-prefixed, unique ids give unique paths, but this is asserted, not
  assumed); no open target path already exists; and the **store-wide** terminal
  dedup (`plan_ledger_appends` over all `done/*.md`) reports no conflicts.
- **Apply (`--apply`):** runs under the `_task_allocation_lock` for the whole
  operation (no concurrent writer — see the lock-discipline invariant in §2).
  Journal the pre-image (hash of `active.md`) + the full post-images — **both the
  per-task `active/` files AND the resulting done-ledger contents** (each target
  path + full post-image content, so terminal routing replays deterministically);
  write all per-task files; append/rewrite the done ledgers to their journalled
  post-images; **re-confirm `active.md` still hashes to the journalled pre-image**
  (refuse + retain journal if it changed under us); then **delete `tasks/active.md`
  LAST and confirm it is gone**; then clear the journal. Deleting `active.md` is
  the terminal marker (the analogue of the capability migrator's "pin set last").
- **Resume (`--resume`):** runs under the `_task_allocation_lock` (same as apply),
  finishing an interrupted apply from the journal, never re-planning. Because the
  journal holds full post-images for both `active/` files and done ledgers, the
  classification below covers every journalled target uniformly. **First check the
  source:** if `tasks/active.md` is still present,
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
  first — the meta project is in-repo, so this is a normal commit here). A single
  `migrate-storage --apply` routes its open tasks into `active/` and its terminal
  `t089`/`t093` into a `done/` ledger — no separate archive step.

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
  that the parsed `active/` set equals the source's OPEN tasks and each terminal
  source task appears once in a `done/` ledger (same tasks, same fields) guards
  against a lossy conversion.
- **`meta` branch volatility.** `science/meta` is in-repo (this worktree), so its
  migration commits land here; still verify the branch before committing.

## Testing

- `parse_task_file`/`render_task_file` round-trip (all fields, empty optionals,
  journal-note bodies, unicode titles).
- Frontmatter contract: `blocked_by` (underscore) round-trips; an unknown key
  (e.g. `blocked-by` or a typo) is REJECTED, not silently dropped.
- Strict YAML: a frontmatter block with a duplicate key (e.g. `priority:` twice)
  is REJECTED (not last-wins); a YAML merge key (`<<`) is REJECTED (not expanded
  past the unknown-key check).
- Required persisted keys: a file missing `created` (or `status`/`priority`/
  `aspects`/`id`/`title`) is REJECTED naming the key — it does NOT silently
  acquire `date.today()` / `proposed` / `P2`; a file with all required keys and
  the optional ones absent parses with model defaults.
- Storage-state gate: on a LEGACY project (`active.md` present, no `active/`)
  every normal command — `tasks list`, `add`, `edit`, `summary`, `fix-blockers`
  — FAILS with the migrate-storage instruction rather than reading zero tasks or
  allocating a colliding id; on a MIGRATING project (journal present) they FAIL
  with the resume instruction; on a CONFLICT project (both layouts, **no**
  journal) they FAIL with the manual-inspection message (NOT the resume
  message); on EMPTY/SPLIT they proceed.
- Migrate-storage mode validity by state: `--apply` refuses in EMPTY/SPLIT/
  MIGRATING/CONFLICT and runs only in LEGACY; `--resume` refuses in
  EMPTY/SPLIT/LEGACY/CONFLICT and runs only in MIGRATING.
- Storage identity: non-canonical id rejected — specifically test the short/
  non-ASCII cases the loose `t\d+` would have admitted (`t1`, `t01`, Unicode
  digits) are all rejected by `t[0-9]{3,}`; filename/frontmatter-id mismatch
  rejected; two active files with the same id → read error; a mutation finding
  2+ `tNNN-*.md` matches → error (no arbitrary overwrite).
- Active→done idempotency: crash-between-ledger-append-and-active-delete leaves a
  ledger copy → retry deletes the active file without a duplicate append; a
  **next-day retry with the clock advanced past a month boundary** still finds
  the id in the prior month's ledger and does not duplicate; a ledger occurrence
  that FAILS the move-recovery predicate (a transition-stable field differs — a
  same-`id`/same-`created` but different-`title` task), or the id present in two
  ledgers, → refusal.
- Crash-duplicate inertness: with the same id in both `active/` and a done
  ledger, `edit`/`note`/`defer`/`block`/`unblock` all RAISE the reconcile message
  (no mutation of the active copy); `complete`/`retire` reconcile via the
  move-recovery path and remove the active copy.
- Predicate separation: `(id, created)` alone does NOT accept — the archive
  fixture's `t002`/`2026-03-01`/"Done in March" vs ledger "Already archived" is a
  CONFLICT (migration/archive dedup), and `apply_archive` refactored onto
  `plan_ledger_appends` now REFUSES it instead of silently skipping
  (`test_apply_skips_duplicate_id_in_destination` updated to assert the refusal).
- `edit --status done|retired` on an **active** task is REFUSED with the
  use-`done`/`retire` message (no terminal task left in `active/`); a
  non-terminal `edit --status` still succeeds in place; the existing
  archived→non-closed refusal is unchanged.
- Lock discipline: `complete_task`/`retire_task` complete without deadlock (the
  top-level acquires once; `_move_task_to_done` runs lock-held and does not
  re-acquire); a mutator invoked while another holds the lock serializes rather
  than corrupting; `tasks archive` runs its plan and apply under one lock window;
  no `active/`/`done/` writer (`write_task_location`, `apply_archive`, per-file
  helpers) acquires the lock itself.
- `fix-blockers` optimistic recheck: the prompt loop runs without the lock; a
  concurrent write that changes the active set between the pre-prompt read and the
  post-prompt write aborts the write with the re-run message (no clobber); an
  unchanged set writes normally.
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
  colliding/existing open target path → refusal**; apply produces per-task files
  matching the source OPEN-task set, appends terminal source tasks to their
  `done/` ledger, and removes `active.md`; refuse on already-migrated / absent
  source.
- Migrator terminal routing: a source with mixed open + terminal tasks routes
  open → `active/` and terminal → `done/YYYY-MM.md` in one apply (no separate
  archive step); undated terminals use the explicit migration `today` and land
  in the same month on a resume (deterministic post-image, no drift).
- `plan_ledger_appends` (pure helper): computes destination post-images without
  writing; a terminal task already present in **any** `done/*.md` and
  **structurally equal** yields no new append (store-wide dedup); an id present
  with any differing field, or an id in two ledgers, is reported as a conflict
  (not silently skipped); `apply_archive` refactored onto the helper preserves its
  idempotent no-op on a byte-identical re-run (existing idempotency test stays
  green) while the differing-content case now refuses.
- Store-wide migrator dedup: an undated terminal source task already appended to
  *last* month's ledger, with the migration computing *this* month, is NOT
  duplicated — the plan refuses or accepts the existing occurrence per the
  predicate, and apply writes no second copy.
- Migrator lock: apply and resume both run under `_task_allocation_lock`; a
  concurrent mutator is serialized behind them (no interleaved write).
- Migrator source-hash safety: apply re-confirms `active.md` matches the
  pre-image before deleting (refuse if changed); resume refuses if a still-present
  `active.md` no longer matches the journalled pre-image (an interruption-time
  edit is preserved, not discarded).
- Migrator resume states (over both `active/` and done-ledger post-images):
  absent post-image → written; present-exact → accepted; **present-different →
  refusal with journal retained**; crash-after-delete (`active.md` gone + all
  post-images exact) → journal cleared, success.
- Worked example: `science/meta` migrates with a single `migrate-storage
  --apply`; `t089`/`t093` land in a `done/` ledger (not `active/`), and
  post-migration `science tasks list` is unchanged.
- Adapter: graph build over a split `tasks/active/` yields the same task nodes.
- The full validate/health/refs/curate/big-picture readers work over the split
  layout (their existing tests, re-pointed fixtures).
- `science/meta` migrates clean and its `science tasks list` is unchanged
  post-migration.

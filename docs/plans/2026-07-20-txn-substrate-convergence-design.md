# Transaction substrate convergence — design

**Date:** 2026-07-20 (rev 5)
**Status:** Approved for implementation planning
**Scope:** convergence **and** durability foundation — this PR is the durable-batch prerequisite
**Package:** `science` (`src/science_tool/plan_common.py`, `entity_import.py`, `entity_reservation.py`, `reference_rewrite.py`, tests)

> **Rev 5 (2026-07-20).** A fourth review found one Critical + one High architecture contradiction in
> rev 4. Fixes: staged directory publication uses **no-clobber** `renameat2(RENAME_NOREPLACE)` (a bare
> `os.replace` removes and thus clobbers a concurrent empty directory — F1); the substrate PR
> **requires unique `rel_path`s** per transition set, so one capture-time snapshot maps to exactly one
> occurrence — chained occurrences (`A→B`, `B→C`), which would need `previous.post == next.pre`
> validation and an occurrence-vs-snapshot split, are deferred to the durable-batch design (F2). With
> these, all remaining findings are implementation-level (TDD, not prose audit).
>
> **Rev 4 (2026-07-20).** A third review found four Critical + two High protocol issues in rev 3. All
> verified. Fixes: forward-create callbacks fire at the **existence-changing** linearization point —
> the `O_EXCL` open / the publish rename — not after later fallible work (F1); absent-preimage restore
> dispatches `rmdir` vs `unlink` by type, so `created-dir` rollback works (F2); the `link + unlink`
> move fallback makes the destination durable *before* unlinking the source (F3); restore defines
> entry-time staging-survivor reconciliation, making "second pass converges" implementable (F4);
> `CREATE_OR_VERIFY`'s existing-blob fast path is separated from its staging precondition (F5); the
> impossible "unmarked-but-mutated" test is replaced with per-primitive fault injection, and `mark`
> is monotonic (F6).
>
> **Rev 3** — restored the `neither`-halts row, tracker-as-rollback-input, no-clobber
> `CREATE_OR_VERIFY`, two-seam move fallback, durable named seam APIs, all-type restartable restore,
> syscall-based write-surface audit. **Rev 2** — import transition schema, ownership tracker,
> no-follow capture, restartable restore, `atomic_write_bytes`, write-surface harness; scope
> decision **full**.

## Why

`plan_common.py` is already a filesystem-level two-phase transaction — `StateFingerprint` /
`PathTransition` / `snapshot_paths` / `rollback_transitions` / `staged_write` /
`assert_same_surface` — and `archive_plan.py` and `supersede_plan.py` are wired to it end to end.
Four gaps block a durable, cross-process batch layer on top of it:

1. **Snapshot capture is not coherent.** `snapshot_paths` calls `fingerprint(p)` then `p.read_bytes()`
   as two separate reads. A concurrent writer between them yields a snapshot whose recorded hash does
   not describe its retained bytes. Adopter corpora live in Dropbox-synced trees whose sync daemon is
   a live writer no advisory lock excludes, so this is not theoretical.
2. **Import is on a private substrate.** `entity_import.py` carries its own `_FileState` /
   `_TreeSnapshot` / `_snapshot` / `_restore` with `restrict=written` ownership, rather than
   `PathTransition` / `snapshot_paths` / `rollback_transitions`. Archive and supersede were migrated;
   import was not. A batch layer spanning all three families inherits the split unless it is closed.
3. **There is no durable arbitrary-bytes primitive.** `staged_write` takes a text postimage and a
   staging token; a journal and a content-addressed blob store need a general `atomic_write_bytes`.
4. **Restore is not restartable.** `_materialize` (`plan_common.py:304`) does `_remove_live(path)`
   then `os.open(..., O_TRUNC)` and writes in place, with **no parent-directory fsync**. A kill
   mid-restore leaves the path matching neither `pre` nor `post`; the action table then sends the
   *next* recovery straight to `RollbackHalt` — on exactly the recovery path the ownership model
   exists to serve. This is a durability bug in shipped code, independent of the batch layer.

This design converges the substrate onto one coherent, ownership-aware, restartable foundation. It
changes **no family mutator's public function signature**, but it **does change the saved-plan wire
schema** for import (saved plans are public API — see Piece 3).

## Scope

In scope: coherent capture, ownership-typed rollback, import migration (incl. wire schema),
restartable durable restore, `atomic_write_bytes`, and acceptance-time true-write-surface tests.

Out of scope (own later plans): the git-commit layer (temp index, `commit-tree`, CAS ref update,
lineage); the durable-batch layer (write-ahead journal, blob store, batch lock, state machine,
`recover()`, halt/discharge); natural-systems integration. The write-ahead intent and runtime
post-state/partition verification of the settled Task-12 contract belong to the durable-batch layer;
this PR provides the observation primitives and the acceptance harness that layer reuses, plus the
restartable restore that makes `MAY_HAVE_WRITTEN` recovery viable.

---

## Piece 1 — coherent snapshot capture

**Goal.** Bind a regular file's type, mode, hash, and retained bytes to one opened file descriptor,
so no concurrent writer can wedge an inconsistent snapshot; and do it without silently changing the
current `lstat`-based, symlink-aware semantics.

**Algorithm (per path).**

- `fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)`. `O_NOFOLLOW` fails on a symlink at `path`, so a
  regular-file capture never silently follows a link a concurrent writer swapped in. A symlink target
  is fingerprinted from `os.lstat`, exactly as today — no fd, no bytes.
- `st = os.fstat(fd)`; confirm `stat.S_ISREG(st.st_mode)` before reading. Derive type and mode from
  `st`; `read()` the bytes once from that same fd; derive both `content_sha256` and retained
  `PathSnapshot.content` from that single buffer. "One `read_bytes()`" is insufficient — it does not
  bind the metadata to the same opened object. The fd is the unit of coherence.
- Absent / dir / symlink targets keep today's behavior (no retained bytes).

**Drift gate (named API, not `snapshot_paths` alone).**

```python
def capture_and_verify(
    transitions: Sequence[PathTransition], project_root: Path,
) -> dict[Path, PathSnapshot]:
    """Capture a coherent snapshot of every transition's path AND verify each
    derived fingerprint equals that transition's expected `pre`. A mismatch
    raises PreconditionRefused (the world changed between planning and capture).
    Requires unique rel_paths (see Piece 2): one snapshot maps to one occurrence,
    so this single-snapshot comparison is well defined."""
```

**Unique `rel_path`s are a precondition (F2).** One snapshot per path is what makes this comparison
coherent; a chained pair (`A→B` then `B→C`) would fail the second check against the initial `A`
snapshot. `capture_and_verify` first asserts the transition set has no repeated `rel_path` and raises
`BoundaryError` otherwise.

`PreconditionRefused` is a **clean refusal**, not `RollbackHalt`: nothing has mutated yet, so there
is nothing to roll back. This does **not** replace the per-write recheck. Each mutator must still
recheck `pre` immediately before its own write boundary, because a Dropbox write can land after
capture (`apply_reference_rewrite` already does this per referrer). Capture-time verification and
write-boundary recheck are two guards at two instants.

**Touches.** `fingerprint`, `snapshot_paths`, `PathSnapshot`, new `capture_and_verify`,
new `PreconditionRefused` in `plan_common.py`.

---

## Piece 2 — ownership as typed execution state

`PathTransition` stays pure *planned* state. What execution established is recorded separately.

```python
class MutationOwnership(str, Enum):
    NOT_WRITTEN = "not-written"            # this transaction never changed this occurrence
    MAY_HAVE_WRITTEN = "may-have-written"  # completion unknown (crash / conservative default)
    WRITTEN = "written"                    # this transaction performed its identity-changing mutation
```

**`WRITTEN` means "this transaction performed its existence/identity-changing mutation on this
occurrence" — not "the occurrence reached `post`."** The action table separates ownership (did we
touch it) from live state (`pre` / `post` / `neither`). A created file whose content write then
failed is `WRITTEN` + `neither` → halt, which is correct: we *did* bring the path into existence and
must own it. This is why the mark fires at the existence-changing point (Piece 4), not after later
byte writes.

**Totality is over transition occurrences, keyed by index.** In *this* substrate PR each `rel_path`
appears at most once (validated — F2), so an occurrence is a path here; the index keying is what keeps
the model forward-compatible with the durable-batch layer, where a batch may touch one `rel_path` in
two sequential transitions (`A→B`, `B→C`). Supporting those chains is **deferred**: it additionally
requires validating `previous.post == next.pre` and separating the initial rollback snapshot from
per-occurrence preconditions — neither of which this PR's single-snapshot `capture_and_verify` does.
The mutable authority is a **tracker built from the authoritative transition sequence**:

```python
class OwnershipTracker:
    def __init__(self, transitions: Sequence[PathTransition]) -> None:
        # every occurrence starts NOT_WRITTEN; the tracker owns the canonical order
    def mark(self, index: int, ownership: MutationOwnership) -> None:
        # MONOTONIC: NOT_WRITTEN -> {MAY_HAVE_WRITTEN, WRITTEN} and MAY_HAVE_WRITTEN -> WRITTEN only.
        # A downgrade (e.g. WRITTEN -> NOT_WRITTEN) is a programming error and raises.
    def as_executions(self) -> tuple[TransitionExecution, ...]: ...  # frozen readout, inspection only

@dataclass(frozen=True)
class TransitionExecution:      # a frozen SNAPSHOT of tracker state; a readout, NOT a rollback input
    transition: PathTransition
    ownership: MutationOwnership
```

**`rollback_transitions` takes the `OwnershipTracker` itself, never a tuple (rev-3 F2).** A tuple
readout can be sliced or reconstructed, so the tracker is the only object that guarantees rollback
sees every occurrence exactly once. `as_executions()` is a frozen readout for tests/inspection, not
an accepted rollback input. `mark` is monotonic (F6): ownership only escalates, so a double-fire or
an out-of-order mark cannot silently disown a mutated path.

**Rollback action table (the spec):**

| Ownership | Live state | Action |
| --- | --- | --- |
| `NOT_WRITTEN` | anything | Leave untouched |
| `MAY_HAVE_WRITTEN` | matches `pre` | Skip (already restored / never written) |
| `MAY_HAVE_WRITTEN` | matches `post` | Restore (re-drivable; see Piece 5) |
| `MAY_HAVE_WRITTEN` | neither | `RollbackHalt` |
| `WRITTEN` | matches `pre` | Skip (already restored) |
| `WRITTEN` | matches `post` | Restore (re-drivable; see Piece 5) |
| `WRITTEN` | neither | `RollbackHalt` |

**Why `neither` always halts (rev-3 F1).** Restartable restore (Piece 5) publishes by atomic rename,
so an interrupted restore leaves the live target matching **`post`** (before the rename) or **`pre`**
(after it) — never `neither`. A live `neither` is therefore not our half-finished restore; it is a
concurrent modification, corruption, or an unattributed partial, and re-driving would clobber another
writer. Restartability makes the **`matches post → restore`** rows safe to run again (an idempotent
staged rename), nothing more. Consistent with the `import-dst` hard-halt rule (Piece 4).

**Who supplies what.** Import: a referrer rejected by its pre-write recheck stays `NOT_WRITTEN`
(preserving another writer's edit — the `restrict=written` guarantee, now typed); a landed write
becomes `WRITTEN` at its seam. Cross-process recovery (later layer): every WAL-covered path is
`MAY_HAVE_WRITTEN`.

---

## Piece 3 — import transition schema (wire change)

Import currently carries **no transitions**; the acceptance expression (Piece 7) has no authoritative
import surface without them. Add two roles and persist a transition set on both import plans.

**New `PathTransition.role` members:** `import-dst` (exclusive create of the rendered destination),
`import-src` (delete of the source). Referrer rewrites reuse `entity-rewrite`; created ancestor
directories reuse `created-dir`.

```
role: Literal["entity-rewrite", "archive-src", "archive-dst", "archive-index",
              "created-dir", "import-dst", "import-src"]
```

- `import-dst`: `pre` absent, `post` an existing file whose `content_sha256` == sha256(rendered_text)
  **and whose `mode` is the exact creation mode `0o644`** (a `StateFingerprint` file post requires an
  exact mode — rev-3 F5 — so the create forces that mode via `fchmod`, not umask-dependent);
  `postimage` = rendered_text.
- `import-src`: `pre` an existing file (the source), `post` absent; no postimage.
- `created-dir`: `pre` absent, `post` a dir with exact mode — one transition per missing ancestor of
  the destination, innermost last (mirrors `_missing_ancestor_dirs`).

**Wire-schema change (public API).** `ImportPlan` and `CohortImportPlan` gain a
`transitions: list[PathTransition]` field, derived at preview time. `CohortImportPlan.schema_version`
bumps `1 → 2`; `parse_cohort_import_plan` rejects a v1 plan with a clear "re-run the preview" error
(no silent upgrade). `ImportPlan` has no version field today; it gains `schema_version: int = 1` so
the same guard applies going forward. Function signatures (`plan_import`, `apply_import`, etc.) are
unchanged.

---

## Piece 4 — mutation seams and durable, callback-bearing APIs

Import performs **no rename**. Each seam is a *durable* operation that fires `on_commit` at its
**existence/identity-changing linearization point — before any later fallible work** (F1). Today's
sites are not durable: `claim_number_in_dir` uses a plain `open(path, "x")` (umask mode, no fsync),
`mkdir(parents=True)` cannot report each ancestor, and `apply_reference_rewrite` records `written`
only *after* `_atomic_replace_text` returns, with no parent fsync. Rev 4 names the replacements and
fixes each callback point:

| Seam | New durable API | Linearization / `on_commit` | Marks |
| --- | --- | --- | --- |
| exclusive dest create | `create_exclusive(path, text, mode, *, on_commit)` — `O_EXCL` open → **`on_commit`** → write → `fchmod` exact → `fsync` file → `fsync` parent | **immediately after the `O_EXCL` open**, before write/chmod/fsync (F1) | `import-dst` |
| each ancestor mkdir | `mkdir_durable(path, mode, *, on_commit)` — mkdir *staging* dir → `chmod` exact → **`renameat2(staging, path, RENAME_NOREPLACE)`** → **`on_commit`** → `fsync` parent | after the no-clobber publish rename (rev-4 F1) | that `created-dir` |
| source unlink | `unlink_durable(path, *, on_commit)` — `unlink` → **`on_commit`** → `fsync` parent | after `unlink` returns | `import-src` |
| each referrer replace | `apply_reference_rewrite` uses a durable replace (`fsync` file → `os.replace` → **`on_commit`** → `fsync` parent) firing per edit | after each `os.replace` | that `entity-rewrite` |

**Why the create marks at the open (F1).** The live file exists the instant `O_EXCL` open succeeds.
If the callback waited until after write/chmod/fsync, a failure there would leave a file on disk
recorded `NOT_WRITTEN` → rollback "leaves it untouched" → an orphaned partial we created but disown.
Marking at the open makes a mid-write failure `WRITTEN` + `neither` → the accepted `import-dst`
hard-halt (owner-approved scope): a create left in the third state is refused, not auto-restored.

**Why the mkdir stages, and publishes no-clobber (rev-4 F1, rev-5 F1).** A direct `mkdir` then
`chmod` on the live path has a window where the dir exists with the wrong mode — `WRITTEN` + `neither`
→ an unacknowledged forward hard-halt. Staging the dir, setting its mode, then publishing by rename
removes that window. But the publish must be `renameat2(RENAME_NOREPLACE)`, **not** `os.replace`:
`rename(2)` removes an empty destination directory, so a bare `os.replace` would clobber an empty
ancestor a concurrent writer created after the precheck — the same no-clobber invariant already held
for moves and blobs. On `EEXIST` the occurrence stays `NOT_WRITTEN`, the attributable staging dir is
removed, and the operation raises `PreconditionRefused` (re-preview) — consistent with the drift-gate
philosophy. Directory publication therefore requires `renameat2` (Linux); there is no `link`-based
fallback for directories, so a platform without it cannot create ancestors transactionally and the
substrate refuses early rather than degrade the invariant.

**`on_commit` contract** (every durable primitive above, plus `staged_write`, `atomic_write_bytes`,
the move primitive): fires **exactly once**, at the existence/identity-changing linearization point,
**before any fallible durability work**; **performs no I/O and must not raise**; calls
`tracker.mark(index, WRITTEN)` and nothing else.

**The no-clobber move primitive (archive/supersede only) — two seams, ordered for durability (F3).**

```python
def move_no_clobber(src, dst, *, on_commit_dst=None, on_commit_src=None) -> None:
    """renameat2(RENAME_NOREPLACE): atomic. On success: mark dst, mark src,
       fsync(dst parent), fsync(src parent).
    Fallback (no renameat2): the destination link must be durable BEFORE the
    source is removed, or power loss can keep the deletion without the link:
        O_EXCL link(src, dst) -> on_commit_dst -> fsync(dst parent)
        -> unlink(src)        -> on_commit_src -> fsync(src parent)
    Never overwrites an existing dst."""
```

---

## Piece 5 — restartable, durable restore (all preimage types)

Replace in-place `_materialize` with staged publication so restore is interruptible anywhere and
re-runnable, for **every** `StateFingerprint` type — files, dirs, **and symlinks** (`_capture` at
`entity_import.py:532` preserves symlinks, so restore must too — rev-3 F6). Each present type builds
the object at a same-directory staging path, then publishes with one atomic rename:

- **File preimage:** `atomic_write_bytes(target, content, mode=RESTORE, file_mode=pre.mode, …)` —
  staging write → fsync → `os.replace` → parent fsync.
- **Dir preimage:** `mkdir(staging)` → `chmod(staging, pre.mode)` → `os.replace(staging, target)` →
  parent fsync (mode set on the staging dir before the rename — no live `mkdir → chmod` window).
- **Symlink preimage:** `os.symlink(pre.symlink_target, staging)` → `os.replace(staging, target)` →
  parent fsync.
- **Absent preimage (delete) — dispatch by type (F2):** the live/`post` object may be a directory
  (a `created-dir` transition is `pre=absent`, `post=dir`, and `unlink` raises on a directory). Use
  the `_remove_live` dispatch: `rmdir` for a directory, `unlink` for a file/symlink, then parent
  fsync. Idempotent under re-drive.

A kill before the rename leaves a staging object and a live target still matching `post`; a kill
after leaves the target matching `pre`. Neither leaves `neither` — which is why Piece 2's `neither`
row halts.

**Entry-time staging-survivor reconciliation (F4).** The staging path is stable
(`staging_path_for(target, token)`), and an `O_EXCL` re-create fails on a survivor exactly as
`staged_write` does today (`plan_common.py:200`). So restore begins by reconciling any survivor,
classified with `classify_staging` and the target/preimage fingerprints:

- **complete, attributable** file/dir/symlink staging → publish it (finish the rename), then mark;
- **attributable file prefix** → remove and recreate the staging (safe: it is our own `O_EXCL` prefix
  and the target still matches `target_pre`);
- **staging directory with wrong mode** → finish staging (chmod to `pre.mode`) before publication;
- **foreign / unattributable** survivor (not our prefix, or target changed under us) → `RollbackHalt`
  and preserve it as evidence.

This is what makes "a second rollback pass converges" implementable rather than aspirational.
Directory-entry mutations gain the parent-dir fsync they lack today.

---

## Piece 6 — `atomic_write_bytes`

Sibling to `staged_write` (which stays text-postimage + attribution-aware). Serves three consumers
with **distinct publication semantics**:

```python
def atomic_write_bytes(
    path: Path, data: bytes, *,
    mode: WriteMode,                       # REPLACE | CREATE_OR_VERIFY | RESTORE
    file_mode: int | None = None,
    token: str,                            # stable staging token (attribution)
    target_pre: StateFingerprint,          # expected live state before the staged publish
    on_commit: Callable[[], None] | None = None,
) -> None: ...
```

- **`REPLACE`** (journal): stage → fsync → `os.replace` (overwrites the prior journal). `file_mode`
  preserves an existing regular file's mode; required on first create. `target_pre` is the current
  journal fingerprint (or absent on first write).
- **`CREATE_OR_VERIFY`** (content-addressed blob), no-clobber (rev-3 F3), with `target_pre` semantics
  made truthful (F5):
  1. **Existing-blob fast path, before any staging or precondition:** if `path` already exists, read
     it and compare — **equal → idempotent success (no write); different → `BlobMismatch`.**
  2. Otherwise stage the bytes under `token` with the precondition `target_pre == absent`, then
     publish with `renameat2(RENAME_NOREPLACE)` (or `O_EXCL link`); never `os.replace`.
  3. **Racing-creator cleanup:** if publication fails because the destination appeared meanwhile,
     re-read it and compare (equal → success, different → `BlobMismatch`), then remove our staging.
     So `target_pre == absent` describes the *staging-publish path only*; the fast path handles the
     already-present case ahead of it.
- **`RESTORE`** (Piece 5): atomic replace setting the **preimage's exact mode even when it differs
  from the live postimage's mode**. `target_pre` is the transition's `post` fingerprint.
- **Common:** fsync file → publish → parent-dir fsync; `on_commit` per contract; the `token` names a
  stable `staging_path_for` target and (outside the fast path) `target_pre` gates survivor
  attribution exactly as `staged_write` does; reject a dir or symlink at `path`.

---

## Piece 7 — acceptance-time true-write-surface tests

> **Revision (rev-6, pending re-review).** This section replaces the earlier `strace`/`ptrace`-centric
> mechanism with an **in-process os-mutation-interposition shim** as the primary, always-on instrument,
> demoting external syscall tracing to an opt-in bypass guard. Rationale below. The *intent* is
> unchanged from the settled Task-12 contract — observe actual mutations, not a before/after map alone
> — and the shim is the "equivalent syscall-audit shim" the prior text already admitted. Flagged for
> re-review before implementation.

Settled Task-12 contract: actual-write observation is an **acceptance-time invariant**, not a
mutator-reported receipt. A mutator returns an `ApplyOutcome` (applied/skipped/repairs), never
evidence of its own scope.

A before/after map is insufficient (rev-1 F7): it cannot see a path created **and removed** during a
successful run — e.g. `claim_number_in_dir`'s `.NNNN.reserving` sentinel, or a staging `.tmp`. And
"paths opened for write" is also insufficient (rev-2 F7): it misses `rename`, `unlink`, `mkdir`,
`rmdir`, `chmod`, and `symlink`. Ground truth is the set of **filesystem-mutating operations**, not
the persistent delta.

**Why not strace every run (rev-6).** `strace`/`ptrace` is Linux-only, needs `CAP_SYS_PTRACE`
(absent in most CI sandboxes and nested containers), and depends on parsing trace output — brittle
exactly where a durable invariant is wanted. This convergence makes the substrate the **single
choke point** for filesystem effects, which enables a portable, deterministic instrument instead.

**Primary instrument — in-process mutation interposition (always-on, portable).** A fixture wraps the
mutating `os` calls the substrate uses (`rename`, `replace`, `unlink`, `mkdir`, `rmdir`, `symlink`,
`chmod`, `link`, and `open` with `O_CREAT`/`O_TRUNC`) **and** the module's own `_rename_noreplace`
(which reaches `renameat2` via `ctypes`, bypassing `os`), recording `(op, path)` for each. Because the
wrap is at the `os`-module / helper level, it captures every mutation whether it flows through a
substrate primitive **or** a raw call that bypasses one — so it is both the surface invariant and the
bypass detector, with no ptrace dependency.

- **Persistent post-state equivalence** — run each pinned mutator (`apply_archive_plan`,
  `apply_supersede_plan`, `apply_import`, `apply_cohort_import`) in a temp project; assert
  `observed_persistent_changes == {t.rel_path for t in transitions if t.pre != t.post}` over full
  before/after maps (bytes, type, mode, symlink target, dir existence).
- **Transient mutation surface** — from the interposition log, assert every recorded mutating op
  targets either a declared transition path or a declared scratch shape (a reserving sentinel or a
  `staging_path_for` token), and that no scratch path survives a clean run.
- **Kill-boundary scratch-survivor characterization** — with `_fault`-style injection at each seam
  and at the parent-dir fsync, assert each survivor is an attributable prefix/sentinel and classify
  it (`absent` / `prefix` / `complete`), never an unattributable file.

**Bypass guard — external syscall audit (opt-in, best-effort).** The one failure the in-process shim
cannot see is a mutation issued through a *fresh* `ctypes`/C-extension syscall a future change adds
without routing it through `os` or `_rename_noreplace`. An optional `strace`/`ptrace` job asserts no
mutating syscall occurred outside the interposition-recorded set; it runs where ptrace is available
and **skips** elsewhere — degrading only this secondary guard, never the primary invariant.

**Forward payoff.** The interposition log is the same shape the v6 durable-batch layer needs: its
write-ahead journal records *intended* effects, the substrate records *actual* effects, and `recover()`
reconciles them. The effect seam is substrate the batch layer builds on, not test-only scaffolding.

---

## Load-bearing tests

1. **Post-linearization failure (rev-1 F4).** Inject failure into the parent-dir `fsync` after the
   linearization point; assert ownership is already `WRITTEN`, restore succeeds, no path is wrongly
   skipped.
2. **Restartable restore + survivor reconciliation, all types (F4/rev-3 F6).** Kill restore
   mid-publish for a file, a dir, and a symlink preimage; on re-drive assert the staging survivor is
   reconciled (complete→published, prefix→recreated, wrong-mode-dir→finished, foreign→halt) and the
   pass converges. Assert an injected `neither` live state **halts**, never re-drives (rev-3 F1).
3. **Contended-unwritten (import port).** A referrer changed by another writer and rejected by the
   pre-write recheck stays `NOT_WRITTEN`; rollback leaves it untouched.
4. **Coherent-capture race (rev-1 F5).** Single-fd capture; `O_NOFOLLOW` rejects a swapped-in
   symlink; non-regular target takes no bytes. A transition set with a repeated `rel_path` raises
   `BoundaryError` at `capture_and_verify` (F2).
4a. **Concurrent-dir no-clobber (rev-5 F1).** With an empty ancestor dir created by another writer
   after the precheck, `mkdir_durable`'s `renameat2(RENAME_NOREPLACE)` publish leaves the occurrence
   `NOT_WRITTEN`, removes the staging dir, and raises `PreconditionRefused` — the concurrent dir is
   not clobbered.
5. **Mark-at-linearization + monotonicity (F6).** Per primitive (`create_exclusive`, `mkdir_durable`,
   `unlink_durable`, durable replace, `move_no_clobber`), inject a fault at the parent-dir fsync
   (after the linearization point) and assert the occurrence is already `WRITTEN`; assert `mark`
   rejects a downgrade (`WRITTEN → NOT_WRITTEN`). (The impossible rev-3 "unmarked-but-mutated"
   assertion is retired — a tracker cannot infer an unreported mutation.)
6. **Move fallback split + ordering (F3/rev-3 F4).** With `renameat2` unavailable, kill between the
   `link` and the `unlink`; assert dst is `WRITTEN`, src is `NOT_WRITTEN`, dst-parent was fsync'd
   before the unlink, and the tracker reflects both.
7. **Import wire schema (rev-1/rev-3).** A v1 `CohortImportPlan` is rejected with a re-preview error;
   a round-tripped v2 plan carries the exact `import-dst`/`import-src`/`created-dir`/`entity-rewrite`
   set with exact modes; `move_no_clobber` refuses an existing dst.
8. **`atomic_write_bytes` modes (F5/rev-3 F3/F6).** `REPLACE` preserves/first-sets mode;
   `CREATE_OR_VERIFY` takes the existing-blob fast path (equal→ok, differ→`BlobMismatch`), never
   `os.replace`s, and on a lost publication race verifies then cleans up its staging; `RESTORE` sets
   a differing preimage mode; unsupported target type rejected.
9. **True-write-surface (rev-2 F7, rev-6).** In-process interposition-shim persistent equivalence for
   all four families; every recorded mutating op is attributable to a declared transition or scratch
   shape; transient sentinel/staging gone on clean run; kill-boundary survivors classified. The
   external syscall-audit bypass guard is opt-in and skips where ptrace is unavailable.

## Deliverable boundary

This PR lands Pieces 1–7 with tests. No family mutator's public function signature changes; the
import saved-plan wire schema does change (versioned, no silent upgrade). No git dependency is added
to any filesystem-only command. It leaves import, archive, and supersede on one coherent, ownership-
aware, restartable substrate — the genuine precondition for the durable-batch layer.

# Transaction substrate convergence — design

**Date:** 2026-07-20
**Status:** Approved for implementation planning
**Package:** `science` (`src/science_tool/plan_common.py`, `entity_import.py`, tests)

## Why

`plan_common.py` is already a complete filesystem-level two-phase transaction —
`StateFingerprint` / `PathTransition` / `snapshot_paths` / `rollback_transitions` /
`staged_write` / `assert_same_surface` — and `archive_plan.py` and `supersede_plan.py` are
wired to it end to end. Three gaps block building a durable, cross-process batch layer on top
of it:

1. **Snapshot capture is not coherent.** `snapshot_paths` calls `fingerprint(p)` and then
   `p.read_bytes()` as two separate reads. A concurrent writer between them yields a snapshot
   whose recorded hash does not describe its retained bytes, so rollback can restore content
   that never matched the fingerprint it claims. Under this ecosystem's conditions this is not
   theoretical: adopter corpora live in Dropbox-synced trees whose sync daemon is a live writer
   no advisory lock excludes.
2. **Import is on a private substrate.** `entity_import.py` carries its own `_FileState` /
   `_TreeSnapshot` / `_snapshot` / `_restore` with `restrict=written` ownership semantics,
   rather than `PathTransition` / `snapshot_paths` / `rollback_transitions`. Archive and
   supersede were migrated; import was not. Any batch layer spanning all three families
   inherits the split unless it is closed here.
3. **There is no durable arbitrary-bytes primitive.** `staged_write` takes a text postimage and
   a staging token; a journal or content-addressed blob store needs a general
   `atomic_write_bytes`.

This design converges the substrate so the durable-batch layer (a separate plan) can be built
without a second dialect of the same vocabulary. It changes no family mutator's public API.

## Scope

In scope: coherent capture, ownership-typed rollback, import migration, `atomic_write_bytes`,
and acceptance-time observed-surface tests.

Out of scope (own plans): the git-commit layer (temp index, `commit-tree`, CAS ref update,
lineage), the durable-batch layer (write-ahead journal, blob store, batch lock, state machine,
recovery, halt/discharge), and any natural-systems integration. The write-ahead intent and
runtime post-state/partition verification named in the settled Task-12 contract belong to that
durable-batch layer; this substrate only provides the observation primitives and the
acceptance-time test harness it will reuse.

## Piece 1 — coherent snapshot capture

**Goal.** Bind a regular file's type, mode, hash, and retained bytes to one opened file
descriptor, so no concurrent writer can wedge an inconsistent snapshot.

**Contract.**

- Open the path once. Derive type and mode from `os.fstat` on that fd; read the bytes once from
  that same fd; derive both the fingerprint's `content_sha256` and the retained
  `PathSnapshot.content` from that single in-memory buffer. "One `read_bytes()`" is *not*
  sufficient — it does not bind the metadata to the same opened object. The fd is the unit of
  coherence.
- Non-regular targets (absent, dir, symlink) keep today's behavior: no retained bytes.
- **Capture is also a pre-mutation drift guard, but does not replace the per-write recheck.**
  After capture, verify each derived fingerprint against its transition's expected `pre`. A
  mismatch is a **clean precondition refusal** (the world changed between planning and capture),
  *not* a `RollbackHalt` — nothing has been mutated yet, so there is nothing to roll back. Each
  mutator must *still* recheck `pre` immediately before its own write boundary, because a
  Dropbox write can land after capture and before the write. Capture-time verification and
  write-boundary recheck are two guards at two instants, not one replacing the other.

**Touches.** `fingerprint`, `snapshot_paths`, `PathSnapshot` in `plan_common.py`.

## Piece 2 — ownership as typed execution state

`PathTransition` stays pure *planned* state. What execution actually established is recorded
separately, as a total typed map.

```python
class MutationOwnership(str, Enum):
    NOT_WRITTEN = "not-written"        # this transaction never wrote this path
    MAY_HAVE_WRITTEN = "may-have-written"  # completion unknown (crash / conservative default)
    WRITTEN = "written"               # landed in the live filesystem
```

**Totality is over transition occurrences, not paths.** A later batch abstraction may touch the
same `rel_path` in two sequential transitions, so keying solely by `rel_path` is wrong. Pair
each transition with its ownership:

```python
@dataclass(frozen=True)
class TransitionExecution:
    transition: PathTransition
    ownership: MutationOwnership
```

`rollback_transitions` accepts a sequence of `TransitionExecution` (or, for backward
compatibility, a bare `list[PathTransition]` treated as all `MAY_HAVE_WRITTEN`, preserving
today's behavior exactly). The execution list must cover every supplied transition occurrence
exactly — missing or extra entries fail early, so an incomplete rollback can never report
success by omission.

**Rollback action table (the spec):**

| Ownership | Live state | Action |
| --- | --- | --- |
| `NOT_WRITTEN` | anything | Leave untouched |
| `MAY_HAVE_WRITTEN` | matches `pre` | Skip |
| `MAY_HAVE_WRITTEN` | matches `post` | Restore snapshot |
| `MAY_HAVE_WRITTEN` | neither | `RollbackHalt` |
| `WRITTEN` | matches `pre` | Skip (already restored) |
| `WRITTEN` | matches `post` | Restore snapshot |
| `WRITTEN` | neither | `RollbackHalt` |

**Who supplies what:**

- **Import.** A referrer rejected by its pre-write recheck stays `NOT_WRITTEN`, so another
  writer's concurrent edit to that referrer is silently preserved — this is exactly the
  `restrict=written` behavior `_restore` documents today, now expressed as typed evidence
  rather than a set membership skip. A path whose write landed becomes `WRITTEN`.
- **Cross-process recovery** (durable-batch layer, later): every path covered by a durable
  write-ahead intent is `MAY_HAVE_WRITTEN`, because process death erased exact completion
  knowledge. The action table then does the right thing per live state.

**`PathTransition` is unchanged.** Ownership is the merge point: planned state in the
transition, established state in the execution record.

## Piece 3 — `atomic_write_bytes`

A durable arbitrary-bytes primitive, sibling to `staged_write` (not a generalization of it —
`staged_write` is text-postimage + staging-token + attribution-aware and must stay that shape).

```python
def atomic_write_bytes(
    path: Path, data: bytes, *, mode: int | None = None,
    on_commit: Callable[[], None] | None = None,
) -> None:
    ...
```

- fsync file → `os.replace` → parent-dir fsync, same durable shape as `staged_write`.
- **Mode semantics, explicit:** if `path` is an existing regular file, preserve its mode
  (`mode` must be None or equal). If it is a new file, `mode` is required and specifies a secure
  creation mode (journal/blob files are created private). Reject unsupported target types (a dir
  or symlink at `path` is an error, never overwritten).
- `on_commit` per the callback contract below.

## The `on_commit` callback contract

Both `staged_write` and the no-clobber move primitive (piece 2's import path) take
`on_commit: Callable[[], None] | None`. Contract:

- Fires **exactly once**, immediately after the mutation's linearization point
  (`os.replace` / `rename` / `unlink` returns) and **before any fallible durability work**
  (the parent-directory fsync).
- **Performs no I/O and must not raise.** It updates an in-memory ownership tracker and nothing
  more.
- For a rename (source → dest), the single callback marks **both** the source and destination
  transitions `WRITTEN`.
- `WRITTEN` means *landed in the live filesystem*, **not** *parent-directory fsync completed*.

This is load-bearing. In today's `staged_write` (`plan_common.py:225-231`) the sequence is
`os.replace(staging, target)` then `os.open(parent)` + `os.fsync(dir_fd)`. A failure in that
dir-fsync unwinds into `except Exception` and re-raises — but the target is already written. A
caller that marks `WRITTEN` on *return* records `NOT_WRITTEN` for a path that is mutated on
disk. The callback fires in the one-statement gap between the replace and the parent fsync, so
ownership is correct on exactly that error path.

## Piece 4 — acceptance-time observed-surface tests

The settled Task-12 contract: actual-write observation is an **acceptance-time invariant**, not
a mutator-reported runtime receipt. A mutator returns an `ApplyOutcome` (applied/skipped/repairs),
never evidence of its own filesystem scope; the safety authority observes independently.

Harness: run each pinned mutator (`apply_archive_plan`, `apply_supersede_plan`,
`apply_import` / `apply_cohort_import`) in a temporary project; snapshot a complete filesystem
map before and after; assert

```python
observed_changes == {t.rel_path for t in transitions if t.pre != t.post}
```

The map includes, per path: bytes, type, mode, symlink target, and directory existence.

## Load-bearing tests

1. **Post-linearization failure (new, load-bearing).** Inject failure into the parent-directory
   `fsync` *after* `os.replace` / `rename` has landed. Assert: (a) ownership for that transition
   is already `WRITTEN` (the callback fired); (b) rollback restores the snapshot correctly; and
   (c) no path is incorrectly skipped. This is the test that proves the callback closes the
   ownership-loss error path.
2. **Contended-unwritten (retain / port from import).** A referrer changed by another writer,
   which this transaction's pre-write recheck rejected, stays `NOT_WRITTEN`; rollback leaves it
   untouched, preserving the other writer's state. This is import's `restrict=written` guarantee
   re-expressed on the typed model.
3. **Coherent-capture race.** Concurrent modification between the two reads of the old
   `snapshot_paths` must be impossible by construction; a regression test pins the single-fd
   capture.
4. **Ownership totality.** A `TransitionExecution` list missing or duplicating a transition
   occurrence fails early, before any rollback action runs.
5. **Observed-surface equivalence** (piece 4) for all three families.
6. **`atomic_write_bytes` mode semantics** — preserve-existing, require-on-create,
   reject-unsupported-type.

## Deliverable boundary

This PR lands pieces 1–4 with tests, changing no family mutator's public signature and adding no
git dependency to any filesystem-only command. It leaves import, archive, and supersede running
on one shared, coherent, ownership-aware substrate — the precondition for the durable-batch
layer.

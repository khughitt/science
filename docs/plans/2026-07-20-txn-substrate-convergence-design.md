# Transaction substrate convergence — design

**Date:** 2026-07-20 (rev 3)
**Status:** Approved for implementation planning
**Scope:** convergence **and** durability foundation — this PR is the durable-batch prerequisite
**Package:** `science` (`src/science_tool/plan_common.py`, `entity_import.py`, `entity_reservation.py`, `reference_rewrite.py`, tests)

> **Rev 3 (2026-07-20).** A second review found four Critical + three High issues in rev 2. All
> verified against shipped code. Fixes: the `MAY_HAVE_WRITTEN + neither` row halts again — restartable
> staging makes the *`post`* row re-runnable, not the *neither* row auto-recoverable (F1); rollback
> takes the tracker itself, so totality cannot be sliced away (F2); `CREATE_OR_VERIFY` publishes
> no-clobber and errors on a content mismatch (F3); the `link + unlink` move fallback marks its two
> occurrences at two seams (F4); durable, callback-bearing creation/mkdir/unlink/replace APIs with
> exact mode are named (F5); restore is restartable for file **and** dir **and** symlink preimages
> (F6); the write-surface fixture captures mutation syscalls, not just opens (F7).
>
> **Rev 2 (2026-07-20).** First review (7 findings) — added the import transition schema, ownership
> tracker, no-follow capture + drift gate, restartable restore, `atomic_write_bytes`, and the
> true-write-surface harness. Scope decision: **full** (fix restore durability here).

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
    raises PreconditionRefused (the world changed between planning and capture)."""
```

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
    NOT_WRITTEN = "not-written"            # this transaction never wrote this occurrence
    MAY_HAVE_WRITTEN = "may-have-written"  # completion unknown (crash / conservative default)
    WRITTEN = "written"                    # landed in the live filesystem
```

**Totality is over transition occurrences, not paths** — a later batch may touch the same `rel_path`
in two sequential transitions. The mutable authority is a **tracker built from the authoritative
transition sequence**:

```python
class OwnershipTracker:
    def __init__(self, transitions: Sequence[PathTransition]) -> None:
        # every occurrence starts NOT_WRITTEN; the tracker owns the canonical order
    def mark(self, index: int, ownership: MutationOwnership) -> None: ...  # from on_commit seams
    def as_executions(self) -> tuple[TransitionExecution, ...]: ...  # frozen readout, inspection only

@dataclass(frozen=True)
class TransitionExecution:      # a frozen SNAPSHOT of tracker state; a readout, NOT a rollback input
    transition: PathTransition
    ownership: MutationOwnership
```

**`rollback_transitions` takes the `OwnershipTracker` itself, never a tuple (F2).** A tuple readout
can be sliced, duplicated, or reconstructed, so a caller could hand rollback a short list and the
promised missing/extra check would be impossible. The tracker *is* the authoritative sequence; it
alone guarantees rollback sees every occurrence exactly once. `as_executions()` remains a frozen
readout for tests and inspection, but is not accepted as a rollback input. The frozen/"mutate"
contradiction of rev 1 is resolved: the tracker mutates via `mark(index, …)`; `TransitionExecution`
is immutable. **The bare-list compatibility branch is removed**; the three in-repo callers
(`apply_archive_plan`, `apply_supersede_plan`, `apply_import`) migrate explicitly to build and pass a
tracker.

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

**Why `neither` always halts (F1).** Restartable restore (Piece 5) publishes by atomic rename, so an
interrupted restore leaves the live target matching **either `post`** (before the rename) **or `pre`**
(after it) — never `neither`. Therefore a live `neither` is not our half-finished restore; it is a
concurrent modification, corruption, or an unattributed partial write, and re-driving would clobber
another writer. What restartability buys is that the **`matches post → restore`** rows are safe to run
again: re-driving repeats an idempotent staged rename. This is consistent with the `import-dst`
hard-halt rule (Piece 4): a create left in `neither` is likewise a refused third state, not an
auto-restore.

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
  exact mode — F5 — so the create must force that mode via `fchmod`, matching its
  `claim_number_in_dir` peers, not leave it umask-dependent); `postimage` = rendered_text.
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

Import performs **no rename**. Each seam is a *durable* operation (F5) that fires `on_commit` at its
linearization point. Today's sites are not durable: `claim_number_in_dir` uses a plain `open(path,
"x")` (umask mode, no fsync), `mkdir(parents=True)` cannot report each ancestor, and
`apply_reference_rewrite` records `written` only *after* `_atomic_replace_text` returns, with no
parent fsync. Rev 3 names the replacements:

| Seam | New durable API | Linearization / `on_commit` | Marks |
| --- | --- | --- | --- |
| exclusive dest create | `create_exclusive(path, text, mode, *, on_commit)` — `O_EXCL` create → write → `fchmod` exact → `fsync` file → `on_commit` → `fsync` parent | after file is complete on disk, before parent fsync | `import-dst` |
| each ancestor mkdir | `mkdir_durable(path, mode, *, on_commit)` — one call per ancestor (no `parents=True`) → `chmod` exact → `on_commit` → `fsync` parent | after `mkdir` returns | that `created-dir` |
| source unlink | `unlink_durable(path, *, on_commit)` — `unlink` → `on_commit` → `fsync` parent | after `unlink` returns | `import-src` |
| each referrer replace | `apply_reference_rewrite` uses a durable replace (`fsync` file → `os.replace` → `on_commit` → `fsync` parent) firing per edit | after each `os.replace` returns | that `entity-rewrite` |

**`on_commit` contract** (parameter on every durable primitive above, plus `staged_write`,
`atomic_write_bytes`, and the move primitive):

- Fires **exactly once**, immediately after the mutation's linearization point and **before any
  fallible durability work** (the parent-dir fsync).
- **Performs no I/O and must not raise.** It calls `tracker.mark(index, WRITTEN)` and nothing else.
- `WRITTEN` means *landed in the live filesystem*, **not** *parent-dir fsync completed*. This is
  load-bearing: a parent-dir fsync that fails after the linearization point unwinds and re-raises
  with the mutation already on disk; marking on *return* would record `NOT_WRITTEN` for a mutated
  path. Firing in the gap keeps ownership correct on that error path.

**The no-clobber move primitive (archive/supersede only) has two commit seams (F4).** `os.rename`
overwrites a destination that appears after a precheck, so:

```python
def move_no_clobber(src, dst, *, on_commit_dst=None, on_commit_src=None) -> None:
    """renameat2(RENAME_NOREPLACE): atomic; on success fire BOTH callbacks.
    Fallback: O_EXCL link(src, dst) -> fire on_commit_dst -> unlink(src) ->
    fire on_commit_src. Two linearization points, two seams: if link lands but
    unlink fails, dst is WRITTEN and src is not, and the tracker reflects exactly
    that. Never overwrites an existing dst. fsync both parents."""
```

A single callback cannot record the fallback's split truth; `renameat2` fires both because its rename
is atomic.

**Import dest-create remains a hard-halt seam, not restartable** (owner-approved scope call). A
SIGKILL mid-`create_exclusive`-write leaves a file that is neither `pre` (absent) nor `post` (full);
`claim_number_in_dir` already refuses this third state on recovery. The durable-batch layer routes an
`import-dst` in the neither state to operator discharge, not auto-restore. Restartability applies to
*restore* (Piece 5), where we own both the preimage bytes and the staging.

---

## Piece 5 — restartable, durable restore (all preimage types)

Replace in-place `_materialize` with staged publication so restore is interruptible anywhere and
re-runnable, for **every** `StateFingerprint` type the substrate can represent — files, dirs, **and
symlinks** (`_capture` at `entity_import.py:532` preserves symlinks, so restore must too — F6). Every
type builds the object at a same-directory staging path, then publishes with one atomic rename:

- **File preimage:** `atomic_write_bytes(target, content, mode=RESTORE, file_mode=pre.mode, …)` —
  staging write → fsync → `os.replace` → parent fsync.
- **Dir preimage:** `mkdir(staging)` → `chmod(staging, pre.mode)` → `os.replace(staging, target)` →
  parent fsync. The mode is set on the *staging* dir before the rename, so there is no
  `mkdir → chmod` window on the live target (rev 2's split bug — F6).
- **Symlink preimage:** `os.symlink(pre.symlink_target, staging)` → `os.replace(staging, target)` →
  parent fsync.
- **Absent preimage (delete):** `unlink` → parent fsync; idempotent under re-drive.

A kill before the rename leaves a staging object plus a live target still matching `post`; re-drive
repeats the rename. A kill after the rename leaves the target matching `pre`; re-drive is a no-op.
Neither leaves the target in `neither` — which is why Piece 2's `neither` row can safely halt.
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
    target_pre: StateFingerprint,          # expected live state (attribution / no-clobber)
    on_commit: Callable[[], None] | None = None,
) -> None: ...
```

- **`REPLACE`** (journal): stage → fsync → `os.replace` (overwrites the prior journal). `file_mode`
  preserves an existing regular file's mode; required on first create.
- **`CREATE_OR_VERIFY`** (content-addressed blob): **no-clobber publish (F3).** Stage the bytes, then
  publish with `renameat2(RENAME_NOREPLACE)` (or `O_EXCL link`); never `os.replace`. On the
  destination-exists case, read the existing blob and compare: **equal bytes → idempotent success
  (no write); different bytes → `BlobMismatch`** (a content-addressed path holding different content
  is a hash collision or corruption, a real error — "errors never" was wrong). `target_pre` must be
  absent for this mode.
- **`RESTORE`** (Piece 5): atomic replace setting the **preimage's exact mode even when it differs
  from the live postimage's mode** — rev 1's "preserve existing mode" would block restoring a file
  whose mode changed.
- **Common:** fsync file → publish → parent-dir fsync; `on_commit` per contract; the `token` names a
  stable `staging_path_for` target and `target_pre` gates survivor attribution exactly as
  `staged_write` does — a mid-write death leaves an `O_EXCL`-created attributable prefix, cleaned only
  when it is our prefix *and* the target still matches `target_pre`; reject a dir or symlink at
  `path`.

---

## Piece 7 — acceptance-time true-write-surface tests

Settled Task-12 contract: actual-write observation is an **acceptance-time invariant**, not a
mutator-reported receipt. A mutator returns an `ApplyOutcome` (applied/skipped/repairs), never
evidence of its own scope.

A before/after map is insufficient (rev-1 F7): it cannot see a path created **and removed** during a
successful run — e.g. `claim_number_in_dir`'s `.NNNN.reserving` sentinel, or a staging `.tmp`. And
"paths opened for write" is also insufficient (rev-2 F7): it misses `rename`, `unlink`, `mkdir`,
`rmdir`, `chmod`, and `symlink`. The fixture therefore captures **filesystem mutation syscalls**
(via an `strace`/`ptrace`-based audit or an equivalent syscall-audit shim), with open-for-write as
only one event class:

- **Persistent post-state equivalence** — run each pinned mutator (`apply_archive_plan`,
  `apply_supersede_plan`, `apply_import`, `apply_cohort_import`) in a temp project; assert
  `observed_persistent_changes == {t.rel_path for t in transitions if t.pre != t.post}` over full
  before/after maps (bytes, type, mode, symlink target, dir existence).
- **Transient mutation surface** — from the syscall audit, assert every mutating syscall targets
  either a declared transition path or a declared scratch shape (a reserving sentinel or a
  `staging_path_for` token), and that no scratch path survives a clean run.
- **Kill-boundary scratch-survivor characterization** — with `_fault`-style injection at each seam
  and at the parent-dir fsync, assert each survivor is an attributable prefix/sentinel and classify
  it (`absent` / `prefix` / `complete`), never an unattributable file.

---

## Load-bearing tests

1. **Post-linearization failure (F4/rev1).** Inject failure into the parent-dir `fsync` after the
   linearization point; assert ownership is already `WRITTEN`, restore succeeds, no path is wrongly
   skipped.
2. **Restartable restore, all types (F6).** Kill restore mid-publish for a file, a dir, and a symlink
   preimage; assert the target still matches `post` (staging left behind, target intact) and a second
   rollback pass converges. Assert an injected `neither` live state **halts**, never re-drives (F1).
3. **Contended-unwritten (import port).** A referrer changed by another writer and rejected by the
   pre-write recheck stays `NOT_WRITTEN`; rollback leaves it untouched.
4. **Coherent-capture race (rev1 F5).** Single-fd capture; `O_NOFOLLOW` rejects a swapped-in symlink;
   non-regular target takes no bytes.
5. **Ownership totality (F2).** `rollback_transitions` accepts only an `OwnershipTracker`; a tracker
   with an unmarked-but-mutated occurrence, or an out-of-range `mark`, fails early. A sliced
   `as_executions()` tuple is not an accepted input (type-level).
6. **Move fallback split (F4).** With `renameat2` unavailable, kill between `link` and `unlink`;
   assert `import`/archive dst is `WRITTEN`, src is `NOT_WRITTEN`, and the tracker reflects both.
7. **Import wire schema (F1/F3/rev1).** A v1 `CohortImportPlan` is rejected with a re-preview error;
   a round-tripped v2 plan carries the exact `import-dst`/`import-src`/`created-dir`/`entity-rewrite`
   set with exact modes; `move_no_clobber` refuses an existing dst.
8. **`atomic_write_bytes` modes (F3/F6).** `REPLACE` preserves/first-sets mode; `CREATE_OR_VERIFY`
   no-ops on identical bytes, **raises `BlobMismatch` on differing bytes**, and never `os.replace`s;
   `RESTORE` sets a differing preimage mode; unsupported target type rejected.
9. **True-write-surface (F7).** Syscall-audit persistent equivalence for all four families; every
   mutating syscall is attributable; transient sentinel/staging gone on clean run; kill-boundary
   survivors classified.

## Deliverable boundary

This PR lands Pieces 1–7 with tests. No family mutator's public function signature changes; the
import saved-plan wire schema does change (versioned, no silent upgrade). No git dependency is added
to any filesystem-only command. It leaves import, archive, and supersede on one coherent, ownership-
aware, restartable substrate — the genuine precondition for the durable-batch layer.

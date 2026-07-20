# Transaction substrate convergence — design

**Date:** 2026-07-20 (rev 2)
**Status:** Approved for implementation planning
**Scope:** convergence **and** durability foundation — this PR is the durable-batch prerequisite
**Package:** `science` (`src/science_tool/plan_common.py`, `entity_import.py`, `reference_rewrite.py`, tests)

> **Rev 2 (2026-07-20).** A seven-finding adversarial review of rev 1 found the import migration and
> the restore substrate underspecified. All seven were verified against the shipped code. Rev 2 adds
> the import transition schema (F1/F3), an ownership tracker that can enforce totality (F2), a
> no-follow capture algorithm and named drift-gate API (F5), restartable durable restore (F4),
> a fully specified `atomic_write_bytes` (F6), and a true-write-surface acceptance harness with
> kill-boundary characterization (F7). Scope decision: **full** — restore durability is fixed here,
> because it is a latent correctness bug in the shipped `_materialize` and the ownership model's
> recovery payoff is otherwise dead on arrival.

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
transition sequence**, which is what makes the missing/extra check possible (F2): the tracker *is*
the original sequence, so an omission is structurally impossible and an out-of-range mark fails early.

```python
class OwnershipTracker:
    def __init__(self, transitions: Sequence[PathTransition]) -> None:
        # every occurrence starts NOT_WRITTEN; the tracker owns the canonical order
    def mark_written(self, index: int) -> None: ...          # called from on_commit
    def as_executions(self) -> tuple[TransitionExecution, ...]: ...  # frozen readout

@dataclass(frozen=True)
class TransitionExecution:      # a frozen SNAPSHOT of tracker state; never mutated in place
    transition: PathTransition
    ownership: MutationOwnership
```

The frozen/"flip" contradiction of rev 1 is resolved: the **tracker** is mutable and keyed by
occurrence index; `TransitionExecution` is an immutable readout. `rollback_transitions` takes the
tracker's authoritative sequence plus its ownership vector (equivalently, `as_executions()`), never a
bare list. **The bare-list compatibility branch is removed**; the three in-repo callers
(`apply_archive_plan`, `apply_supersede_plan`, `apply_import`) migrate explicitly.

**Rollback action table (the spec):**

| Ownership | Live state | Action |
| --- | --- | --- |
| `NOT_WRITTEN` | anything | Leave untouched |
| `MAY_HAVE_WRITTEN` | matches `pre` | Skip |
| `MAY_HAVE_WRITTEN` | matches `post` | Restore snapshot |
| `MAY_HAVE_WRITTEN` | neither | *(with restartable restore, Piece 5)* re-drive restore; else `RollbackHalt` |
| `WRITTEN` | matches `pre` | Skip (already restored) |
| `WRITTEN` | matches `post` | Restore snapshot |
| `WRITTEN` | neither | `RollbackHalt` |

The one row rev 1 could not honor — `MAY_HAVE_WRITTEN` + neither — is what Piece 5 fixes: a restore
interrupted partway leaves a staging file, not a corrupt target, so re-driving completes it.

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

- `import-dst`: `pre` absent, `post` an existing file whose `content_sha256` == sha256(rendered_text);
  `postimage` = rendered_text. (Same staged-role validator shape as archive-dst.)
- `import-src`: `pre` an existing file (the source), `post` absent; no postimage.
- `created-dir`: `pre` absent, `post` a dir — one per missing ancestor of the destination, innermost
  last (mirrors `_missing_ancestor_dirs`).

**Wire-schema change (public API).** `ImportPlan` and `CohortImportPlan` gain a
`transitions: list[PathTransition]` field, derived at preview time. `CohortImportPlan.schema_version`
bumps `1 → 2`; `parse_cohort_import_plan` rejects a v1 plan with a clear "re-run the preview" error
(no silent upgrade). `ImportPlan` has no version field today; it gains `schema_version: int = 1` so
the same guard applies going forward. Function signatures (`plan_import`, `apply_import`, etc.) are
unchanged.

---

## Piece 4 — mutation seams and the `on_commit` contract

Import performs **no rename**. Its seams, each of which marks its transition(s) `WRITTEN`:

| Seam | Site | Marks |
| --- | --- | --- |
| exclusive dest create | `claim_number_in_dir` `open(path, "x")` returns | `import-dst` |
| each ancestor mkdir | `os.mkdir` returns | that `created-dir` |
| source unlink | `source.unlink()` returns | `import-src` |
| each referrer replace | `apply_reference_rewrite` per-edit `os.replace` returns | that `entity-rewrite` |

**`on_commit` contract** (parameter on `staged_write`, `atomic_write_bytes`, and the move primitive):

- Fires **exactly once**, immediately after the mutation's linearization point
  (`os.replace` / `rename` / `unlink` returns) and **before any fallible durability work** (the
  parent-dir fsync).
- **Performs no I/O and must not raise.** It updates the in-memory tracker and nothing else.
- `WRITTEN` means *landed in the live filesystem*, **not** *parent-dir fsync completed*.

Load-bearing (F4): in today's `staged_write`, `os.replace` is followed by `os.fsync(dir_fd)`, which
can fail after the replace already succeeded, unwind into `except Exception`, and re-raise — with the
target already written. A caller marking `WRITTEN` on *return* records `NOT_WRITTEN` for a mutated
path. The callback fires in the gap between replace and parent fsync, so ownership is correct on that
error path.

**The no-clobber move primitive is archive/supersede-scoped, not import's,** and needs an explicit
algorithm because bare `os.rename` on POSIX overwrites a destination that appears after a precheck.
Definition:

```python
def move_no_clobber(src: Path, dst: Path, *, on_commit=None) -> None:
    """renameat2(RENAME_NOREPLACE) where available; else O_EXCL link(src,dst)
    + unlink(src). Never overwrites an existing dst. fsync both parents."""
```

**Import dest-create is a create, not a staged replace**, so a SIGKILL mid-`open("x")`-write leaves a
partial that is neither `pre` (absent) nor `post` (full). `claim_number_in_dir` already refuses this
"third state" on recovery rather than silently trusting it. Rev 2 keeps that refusal explicit and
documents it as a known non-restartable seam *for the create*; the durable-batch layer's recovery
treats an `import-dst` in the neither state as a hard halt requiring operator discharge, not an
auto-restore. (Restartability applies to *restore* — Piece 5 — where we control both preimage bytes
and staging.)

---

## Piece 5 — restartable, durable restore

Replace in-place `_materialize` with attributed same-directory staging, so restore is interruptible
anywhere and re-runnable:

- **File preimage:** write bytes to a same-directory staging path (`staging_path_for(target, token)`,
  `O_EXCL`), fsync the file, `os.replace` onto the target, fsync the parent dir. This is
  `atomic_write_bytes` with the preimage as `data` and the preimage's exact mode (Piece 6). A kill
  mid-restore leaves a staging file plus an unchanged target — the target still matches `post`, so
  re-driving simply repeats the staged replace. Never a corrupt target.
- **Absent preimage (delete):** `unlink` then parent-dir fsync; idempotent under re-drive.
- **Dir preimage:** `mkdir` + exact-mode `chmod` then parent-dir fsync; `exist_ok` re-drive-safe.
- **Directory-entry mutations gain the parent-dir fsync** they lack today.

This is what upgrades the `MAY_HAVE_WRITTEN` + neither row from `RollbackHalt` to "re-drive restore":
recovery re-runs the same staged materialization and converges.

---

## Piece 6 — `atomic_write_bytes`

Sibling to `staged_write` (which stays text-postimage + attribution-aware). Serves three consumers
with **distinct overwrite semantics**, so the mode is explicit:

```python
def atomic_write_bytes(
    path: Path, data: bytes, *,
    mode: WriteMode,                       # REPLACE | CREATE_OR_VERIFY | RESTORE
    file_mode: int | None = None,
    on_commit: Callable[[], None] | None = None,
) -> None: ...
```

- **`REPLACE`** (journal): unconditional atomic replace. `file_mode` preserves an existing regular
  file's mode; required on first create.
- **`CREATE_OR_VERIFY`** (content-addressed blob): if `path` exists, read it and verify its bytes
  equal `data` (hash identity) — no write, no error; else atomic create. Never an unconditional
  overwrite of a blob.
- **`RESTORE`** (Piece 5): atomic replace that sets the **preimage's exact mode even when it differs
  from the live postimage's mode** — rev 1's "preserve existing mode" rule would have prevented
  restoring a file whose mode changed.
- **Common:** fsync file → `os.replace` → parent-dir fsync; `on_commit` per contract; a temp survivor
  from a mid-write death is an `O_EXCL`-created, attributable byte-prefix and is cleaned only when
  both it is our prefix and the target is unchanged (the `staged_write` attribution rule); reject a
  dir or symlink at `path`.

---

## Piece 7 — acceptance-time true-write-surface tests

Settled Task-12 contract: actual-write observation is an **acceptance-time invariant**, not a
mutator-reported receipt. A mutator returns an `ApplyOutcome` (applied/skipped/repairs), never
evidence of its own scope.

A before/after map is insufficient (F7): it cannot see a path created **and removed** during a
successful run — e.g. `claim_number_in_dir`'s `.NNNN.reserving` sentinel, or a staging `.tmp`. So the
harness observes the **true write surface**, not just persistent post-state:

- **Persistent post-state equivalence** — run each pinned mutator (`apply_archive_plan`,
  `apply_supersede_plan`, `apply_import`, `apply_cohort_import`) in a temp project; assert
  `observed_persistent_changes == {t.rel_path for t in transitions if t.pre != t.post}` over full
  before/after maps (bytes, type, mode, symlink target, dir existence).
- **Transient scratch surface** — via a filesystem watch / audit fixture, record every path opened
  for write during the run. Assert every transient path is a declared scratch shape (a reserving
  sentinel or a `staging_path_for` token) and none survives a clean run.
- **Kill-boundary scratch-survivor characterization** — with `_fault`-style injection at each seam
  and at the parent-dir fsync, assert each survivor is an attributable prefix/sentinel and classify
  it (`absent` / `prefix` / `complete`), never an unattributable file.

---

## Load-bearing tests

1. **Post-linearization failure (F4).** Inject failure into the parent-dir `fsync` after
   `os.replace`/`rename` lands; assert ownership is already `WRITTEN`, restore succeeds, no path is
   wrongly skipped.
2. **Restartable restore (F4/Piece 5).** Kill restore mid-materialize; assert the target still
   matches `post` (staging left behind, target intact) and a second rollback pass converges.
3. **Contended-unwritten (import port).** A referrer changed by another writer and rejected by the
   pre-write recheck stays `NOT_WRITTEN`; rollback leaves it untouched.
4. **Coherent-capture race (F5).** Single-fd capture; `O_NOFOLLOW` rejects a swapped-in symlink;
   non-regular target takes no bytes.
5. **Ownership totality (F2).** A tracker readout missing or duplicating an occurrence fails early;
   an out-of-range `mark_written` raises.
6. **Import wire schema (F1/F3).** A v1 `CohortImportPlan` is rejected with a re-preview error;
   a round-tripped v2 plan carries the exact `import-dst`/`import-src`/`created-dir`/`entity-rewrite`
   transition set; `move_no_clobber` refuses an existing dst.
7. **`atomic_write_bytes` modes (F6).** `REPLACE` preserves/first-sets mode; `CREATE_OR_VERIFY`
   no-ops on identical bytes and errors never; `RESTORE` sets a differing preimage mode; unsupported
   target type rejected.
8. **True-write-surface (F7).** Persistent equivalence for all four families; transient sentinel/
   staging observed and gone on clean run; kill-boundary survivors classified.

## Deliverable boundary

This PR lands Pieces 1–7 with tests. No family mutator's public function signature changes; the
import saved-plan wire schema does change (versioned, no silent upgrade). No git dependency is added
to any filesystem-only command. It leaves import, archive, and supersede on one coherent, ownership-
aware, restartable substrate — the genuine precondition for the durable-batch layer.

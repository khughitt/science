# Transaction substrate convergence — implementation plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Converge import/archive/supersede onto one coherent, ownership-aware, restartable
filesystem-transaction substrate in `science`, fixing the shipped snapshot-capture race and the
non-restartable restore, so a later durable-batch layer can be built without a second dialect.

**Architecture:** Extend `plan_common.py`'s two-phase transaction with: single-fd coherent capture +
a drift gate; a typed `OwnershipTracker`; a general durable `atomic_write_bytes`; staged, no-clobber,
restartable restore; durable callback-bearing mutation primitives; import transitions + wire schema;
and a syscall-audited acceptance harness. No family mutator's public *function* signature changes;
the import *saved-plan wire schema* does change (versioned, no silent upgrade).

**Tech Stack:** Python 3.13, Pydantic v2, pytest. Package root `science/` (run everything from there).
Design doc: [`2026-07-20-txn-substrate-convergence-design.md`](2026-07-20-txn-substrate-convergence-design.md).

## Global Constraints

Every task's requirements implicitly include these (verbatim from the design):

- **`WRITTEN` = "this transaction performed its existence/identity-changing mutation on this
  occurrence"** — not "reached `post`". `on_commit` fires **exactly once**, at that linearization
  point, **before any fallible durability work** (the parent-dir fsync); it performs **no I/O and must
  not raise**; it calls `tracker.mark(index, WRITTEN)` and nothing else.
- **`mark` is monotonic:** `NOT_WRITTEN → {MAY_HAVE_WRITTEN, WRITTEN}` and `MAY_HAVE_WRITTEN →
  WRITTEN` only. A downgrade raises.
- **`rollback_transitions` takes the `OwnershipTracker`**, never a bare list or a sliced tuple.
- **`MAY_HAVE_WRITTEN`/`WRITTEN` + live `neither` → `RollbackHalt`.** Restartable restore makes only
  the `matches post → restore` rows re-drivable.
- **No-clobber publication everywhere:** moves, blobs, and staged directories publish with
  `renameat2(RENAME_NOREPLACE)` (files/blobs may fall back to `O_EXCL link`; directories may not).
  Never `os.replace` where another writer's object could be silently removed.
- **Unique `rel_path`s per transition set** in this PR; chained occurrences are deferred.
- **Durability order:** file fsync → publish → parent-dir fsync; for `link+unlink`, the destination
  is made durable before the source is unlinked.
- **`import-dst` is a hard-halt seam** (mid-create third state is refused, never auto-restored);
  restartability applies to *restore*, not forward creates.
- **Fail early; no legacy/compat layers** (project rule). The bare-list `rollback_transitions` path
  is removed, not aliased.
- Commands run from `science/`: `uv run --frozen pytest`, `uv run ruff check`, `uv run pyright`.

---

## File structure

- `src/science_tool/plan_common.py` — coherent capture, `capture_and_verify`, `PreconditionRefused`,
  `MutationOwnership`/`TransitionExecution`/`OwnershipTracker`, `atomic_write_bytes`/`WriteMode`,
  staged restartable restore, `move_no_clobber`, durable seam primitives, `renameat2` binding.
- `src/science_tool/entity_reservation.py` — `claim_number_in_dir` uses `create_exclusive`.
- `src/science_tool/reference_rewrite.py` — durable per-edit replace + `on_commit`.
- `src/science_tool/entity_import.py` — import transitions, wire schema, tracker-based apply/rollback.
- `src/science_tool/archive_plan.py`, `supersede_plan.py` — tracker-based rollback.
- `tests/` — new: `test_txn_capture.py`, `test_atomic_write_bytes.py`, `test_txn_restore.py`,
  `test_ownership_tracker.py`, `test_move_no_clobber.py`, `test_durable_seams.py`,
  `test_write_surface_acceptance.py`; extended: `test_plan_common.py`, `test_entity_import.py`,
  `test_cohort_import.py`, `test_archive_plan.py`, `test_supersede_plan.py`.

Ordering (dependency): P1 capture → P6 `atomic_write_bytes` → P5 restore → P2 ownership → P4 seams +
archive/supersede wiring → P3 import migration → P7 acceptance harness.

---

## Task 1: Coherent single-fd capture + no-follow

**Files:**
- Modify: `src/science_tool/plan_common.py` (`fingerprint`, `snapshot_paths`, add `_capture_fd`)
- Test: `tests/test_txn_capture.py` (new)

**Interfaces:**
- Produces: `snapshot_paths(paths) -> dict[Path, PathSnapshot]` (unchanged signature, coherent
  internals); `fingerprint(path) -> StateFingerprint` (unchanged signature); regular-file capture
  binds fp + bytes to one fd.
- Consumes: existing `StateFingerprint`, `PathSnapshot`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_txn_capture.py
import os, stat
from pathlib import Path
import pytest
from science_tool.plan_common import snapshot_paths, fingerprint, UnsupportedPathType

def test_snapshot_hash_matches_retained_bytes(tmp_path):
    p = tmp_path / "f.md"; p.write_text("hello")
    snap = snapshot_paths([p])[p]
    import hashlib
    assert snap.fp.content_sha256 == hashlib.sha256(snap.content).hexdigest()

def test_capture_does_not_follow_symlink(tmp_path):
    real = tmp_path / "real.md"; real.write_text("x")
    link = tmp_path / "link.md"; link.symlink_to(real)
    fp = fingerprint(link)
    assert fp.type == "symlink" and fp.symlink_target == str(real)
    assert snapshot_paths([link])[link].content is None

def test_non_regular_rejected(tmp_path):
    fifo = tmp_path / "fifo"; os.mkfifo(fifo)
    with pytest.raises(UnsupportedPathType):
        fingerprint(fifo)
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run --frozen pytest tests/test_txn_capture.py -v`
Expected: FAIL (coherence test may pass incidentally today; symlink/non-regular already work — the
value is the regression pin once internals change in Step 3).

- [ ] **Step 3: Refactor capture to one fd**

Introduce a helper that opens a regular file once (`O_RDONLY | O_NOFOLLOW`), `fstat`s it, reads bytes,
and returns `(StateFingerprint, bytes)` from that single buffer. `fingerprint` keeps using `lstat`
for type dispatch (symlink/dir/absent unchanged); for a regular file it delegates to the helper.
`snapshot_paths` calls the helper for regular files instead of `fingerprint(p)` + `p.read_bytes()`:

```python
def _capture_regular_fd(path: Path) -> tuple[StateFingerprint, bytes]:
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode):
            raise UnsupportedPathType(f"not a regular file: {path}")
        data = b""
        while chunk := os.read(fd, 1 << 20):
            data += chunk
    finally:
        os.close(fd)
    fp = StateFingerprint(existed=True, type="file",
                          content_sha256=hashlib.sha256(data).hexdigest(),
                          mode=stat.S_IMODE(st.st_mode), symlink_target=None)
    return fp, data

def snapshot_paths(paths: list[Path]) -> dict[Path, PathSnapshot]:
    snap: dict[Path, PathSnapshot] = {}
    for p in paths:
        base = fingerprint(p)
        if base.existed and base.type == "file":
            fp, content = _capture_regular_fd(p)
            snap[p] = PathSnapshot(fp=fp, content=content)
        else:
            snap[p] = PathSnapshot(fp=base, content=None)
    return snap
```

(There is still a lstat-then-open gap; the write-boundary recheck and `capture_and_verify` — Task 2 —
close the plan-to-apply window. The fd binds the *bytes* to the *mode+hash* of one opened object,
which is the coherence guarantee.)

- [ ] **Step 4: Run to verify pass**

Run: `uv run --frozen pytest tests/test_txn_capture.py tests/test_plan_common.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/science_tool/plan_common.py tests/test_txn_capture.py
git commit -m "feat(txn): single-fd coherent snapshot capture"
```

---

## Task 2: `capture_and_verify` drift gate + unique-path guard

**Files:**
- Modify: `src/science_tool/plan_common.py` (add `capture_and_verify`, `PreconditionRefused`)
- Test: `tests/test_txn_capture.py`

**Interfaces:**
- Produces: `capture_and_verify(transitions: Sequence[PathTransition], project_root: Path) ->
  dict[Path, PathSnapshot]`; `class PreconditionRefused(RuntimeError)`.
- Consumes: `snapshot_paths`, `resolve_within`, `PathTransition`, `matches`.

- [ ] **Step 1: Write the failing test**

```python
def test_capture_and_verify_refuses_on_pre_mismatch(tmp_path):
    from science_tool.plan_common import capture_and_verify, PreconditionRefused, PathTransition, StateFingerprint
    f = tmp_path / "a.md"; f.write_text("current")
    stale_pre = StateFingerprint(existed=True, type="file",
        content_sha256=hashlib.sha256(b"stale").hexdigest(), mode=0o644, symlink_target=None)
    post = StateFingerprint(existed=False, type=None, content_sha256=None, mode=None, symlink_target=None)
    t = PathTransition(role="import-src", rel_path="a.md", pre=stale_pre, post=post)
    with pytest.raises(PreconditionRefused):
        capture_and_verify([t], tmp_path)

def test_capture_and_verify_rejects_repeated_rel_path(tmp_path):
    from science_tool.plan_common import capture_and_verify, PathTransition, StateFingerprint, BoundaryError
    absent = StateFingerprint(existed=False, type=None, content_sha256=None, mode=None, symlink_target=None)
    dirpost = StateFingerprint(existed=True, type="dir", content_sha256=None, mode=0o755, symlink_target=None)
    t1 = PathTransition(role="created-dir", rel_path="d", pre=absent, post=dirpost)
    t2 = PathTransition(role="created-dir", rel_path="d", pre=absent, post=dirpost)
    with pytest.raises(BoundaryError):
        capture_and_verify([t1, t2], tmp_path)
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run --frozen pytest tests/test_txn_capture.py -k capture_and_verify -v`
Expected: FAIL (`capture_and_verify` undefined).

- [ ] **Step 3: Implement**

```python
class PreconditionRefused(RuntimeError):
    """Live state diverged from a transition's expected `pre` at capture time. Clean refusal —
    nothing mutated yet, so NOT a RollbackHalt."""

def capture_and_verify(transitions, project_root):
    rels = [t.rel_path for t in transitions]
    if len(set(rels)) != len(rels):
        raise BoundaryError("transition set has a repeated rel_path (unsupported in this PR)")
    paths = [resolve_within(project_root, t.rel_path) for t in transitions]
    snap = snapshot_paths(paths)
    for t, p in zip(transitions, paths):
        if snap[p].fp != t.pre:
            raise PreconditionRefused(f"{t.rel_path}: live state != expected pre; re-run the preview")
    return snap
```

Use the module's existing `BoundaryError` (or add one if absent, matching the project's error style).

- [ ] **Step 4: Run to verify pass**

Run: `uv run --frozen pytest tests/test_txn_capture.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/science_tool/plan_common.py tests/test_txn_capture.py
git commit -m "feat(txn): capture_and_verify drift gate + unique-rel_path guard"
```

---

## Task 3: `atomic_write_bytes` — REPLACE mode

**Files:**
- Modify: `src/science_tool/plan_common.py` (add `WriteMode`, `atomic_write_bytes`)
- Test: `tests/test_atomic_write_bytes.py` (new)

**Interfaces:**
- Produces: `class WriteMode(str, Enum): REPLACE, CREATE_OR_VERIFY, RESTORE`;
  `atomic_write_bytes(path, data, *, mode, file_mode=None, token, target_pre, on_commit=None) -> None`.
- Consumes: `staging_path_for`, `StateFingerprint`, `matches`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_atomic_write_bytes.py
import os, stat, pytest
from science_tool.plan_common import atomic_write_bytes, WriteMode, fingerprint

def _pre(path): return fingerprint(path)

def test_replace_first_create_sets_mode(tmp_path):
    p = tmp_path / "journal"
    atomic_write_bytes(p, b"v1", mode=WriteMode.REPLACE, file_mode=0o600,
                       token="t0", target_pre=_pre(p))
    assert p.read_bytes() == b"v1"
    assert stat.S_IMODE(p.stat().st_mode) == 0o600

def test_replace_overwrites_and_fires_on_commit(tmp_path):
    p = tmp_path / "journal"; p.write_bytes(b"v1"); os.chmod(p, 0o600)
    fired = []
    atomic_write_bytes(p, b"v2", mode=WriteMode.REPLACE, file_mode=0o600,
                       token="t1", target_pre=_pre(p), on_commit=lambda: fired.append(1))
    assert p.read_bytes() == b"v2" and fired == [1]

def test_reject_dir_target(tmp_path):
    d = tmp_path / "d"; d.mkdir()
    with pytest.raises(Exception):
        atomic_write_bytes(d, b"x", mode=WriteMode.REPLACE, file_mode=0o644, token="t", target_pre=_pre(d))
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run --frozen pytest tests/test_atomic_write_bytes.py -v`
Expected: FAIL (`atomic_write_bytes` undefined).

- [ ] **Step 3: Implement REPLACE (leave other modes raising `NotImplementedError` for now)**

```python
class WriteMode(str, Enum):
    REPLACE = "replace"
    CREATE_OR_VERIFY = "create-or-verify"
    RESTORE = "restore"

def atomic_write_bytes(path, data, *, mode, file_mode=None, token, target_pre, on_commit=None):
    if path.is_symlink() or (path.exists() and path.is_dir()):
        raise StagingError(f"atomic_write_bytes target is not a regular file: {path}")
    if mode is WriteMode.CREATE_OR_VERIFY:
        raise NotImplementedError  # Task 4
    if mode is WriteMode.RESTORE and file_mode is None:
        raise StagingError("RESTORE requires file_mode")
    resolved_mode = file_mode if file_mode is not None else (
        stat.S_IMODE(path.stat().st_mode) if path.exists() else None)
    if resolved_mode is None:
        raise StagingError("REPLACE first-create requires file_mode")
    staging = staging_path_for(path, token)
    fd = os.open(staging, os.O_WRONLY | os.O_CREAT | os.O_EXCL, resolved_mode)
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(data); fh.flush()
            os.fchmod(fh.fileno(), resolved_mode); os.fsync(fh.fileno())
        os.replace(staging, path)          # REPLACE/RESTORE linearization point
        if on_commit is not None: on_commit()
        dfd = os.open(path.parent, os.O_RDONLY)
        try: os.fsync(dfd)
        finally: os.close(dfd)
    except Exception:
        if staging.exists() and data.startswith(staging.read_bytes()) and matches(target_pre, path):
            staging.unlink()
        raise
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run --frozen pytest tests/test_atomic_write_bytes.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/science_tool/plan_common.py tests/test_atomic_write_bytes.py
git commit -m "feat(txn): atomic_write_bytes REPLACE mode"
```

---

## Task 4: `atomic_write_bytes` — CREATE_OR_VERIFY (no-clobber blob)

**Files:**
- Modify: `src/science_tool/plan_common.py`; add `renameat2` binding + `BlobMismatch`
- Test: `tests/test_atomic_write_bytes.py`

**Interfaces:**
- Produces: `class BlobMismatch(RuntimeError)`; `_rename_noreplace(src: Path, dst: Path) -> None`
  (raises `FileExistsError` if dst exists — `renameat2(RENAME_NOREPLACE)` via `ctypes`, `O_EXCL link`
  fallback for files).
- Consumes: Task 3 scaffolding.

- [ ] **Step 1: Write the failing test**

```python
def test_create_or_verify_idempotent_equal(tmp_path):
    from science_tool.plan_common import atomic_write_bytes, WriteMode, fingerprint
    p = tmp_path / "ab"; p.write_bytes(b"blob")
    atomic_write_bytes(p, b"blob", mode=WriteMode.CREATE_OR_VERIFY, token="t",
                       target_pre=fingerprint(tmp_path / "nonexist"))  # ignored on fast path
    assert p.read_bytes() == b"blob"

def test_create_or_verify_mismatch_raises(tmp_path):
    from science_tool.plan_common import atomic_write_bytes, WriteMode, BlobMismatch, fingerprint
    p = tmp_path / "ab"; p.write_bytes(b"other")
    with pytest.raises(BlobMismatch):
        atomic_write_bytes(p, b"blob", mode=WriteMode.CREATE_OR_VERIFY, token="t",
                           target_pre=fingerprint(p))

def test_create_or_verify_creates_when_absent(tmp_path):
    from science_tool.plan_common import atomic_write_bytes, WriteMode, fingerprint
    p = tmp_path / "ab"
    atomic_write_bytes(p, b"blob", mode=WriteMode.CREATE_OR_VERIFY, token="t",
                       target_pre=fingerprint(p))
    assert p.read_bytes() == b"blob"
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run --frozen pytest tests/test_atomic_write_bytes.py -k create_or_verify -v`
Expected: FAIL (`NotImplementedError`).

- [ ] **Step 3: Implement `_rename_noreplace` + CREATE_OR_VERIFY**

```python
import ctypes
_AT_FDCWD = -100
_RENAME_NOREPLACE = 1 << 0
def _rename_noreplace(src: Path, dst: Path) -> None:
    libc = ctypes.CDLL("libc.so.6", use_errno=True)
    res = libc.renameat2(_AT_FDCWD, os.fsencode(src), _AT_FDCWD, os.fsencode(dst), _RENAME_NOREPLACE)
    if res != 0:
        err = ctypes.get_errno()
        if err == errno.EEXIST: raise FileExistsError(dst)
        if err == errno.ENOSYS:      # kernel without renameat2: O_EXCL link fallback (files only)
            os.link(src, dst); os.unlink(src); return
        raise OSError(err, os.strerror(err), str(dst))

class BlobMismatch(RuntimeError): ...
```

In `atomic_write_bytes`, replace the CREATE_OR_VERIFY `NotImplementedError` with: (1) fast path —
if `path.exists()`, compare bytes → return on equal, `BlobMismatch` on differ; (2) else stage under
`token`, fsync, `_rename_noreplace(staging, path)`; on `FileExistsError`, re-read and compare (equal
→ success, differ → `BlobMismatch`) and unlink the staging; fire `on_commit` after a successful
publish; fsync parent.

- [ ] **Step 4: Run to verify pass**

Run: `uv run --frozen pytest tests/test_atomic_write_bytes.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/science_tool/plan_common.py tests/test_atomic_write_bytes.py
git commit -m "feat(txn): atomic_write_bytes CREATE_OR_VERIFY + renameat2 no-clobber"
```

---

## Task 5: `atomic_write_bytes` — RESTORE mode

**Files:**
- Modify: `src/science_tool/plan_common.py`
- Test: `tests/test_atomic_write_bytes.py`

**Interfaces:**
- Produces: RESTORE branch of `atomic_write_bytes` — atomic replace that sets the preimage's exact
  mode even when it differs from the live file's mode.

- [ ] **Step 1: Write the failing test**

```python
def test_restore_sets_differing_mode(tmp_path):
    import stat
    from science_tool.plan_common import atomic_write_bytes, WriteMode, fingerprint
    p = tmp_path / "f"; p.write_bytes(b"new"); os.chmod(p, 0o600)
    atomic_write_bytes(p, b"old", mode=WriteMode.RESTORE, file_mode=0o644,
                       token="t", target_pre=fingerprint(p))
    assert p.read_bytes() == b"old" and stat.S_IMODE(p.stat().st_mode) == 0o644
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run --frozen pytest tests/test_atomic_write_bytes.py -k restore -v`
Expected: FAIL if the Task 3 `resolved_mode` logic preferred the live mode. (RESTORE must use
`file_mode` unconditionally.)

- [ ] **Step 3: Ensure RESTORE uses `file_mode` exactly**

In the mode-resolution block, when `mode is WriteMode.RESTORE`, `resolved_mode = file_mode` always
(never the live file's mode). The REPLACE branch keeps its preserve-existing rule.

- [ ] **Step 4: Run to verify pass**

Run: `uv run --frozen pytest tests/test_atomic_write_bytes.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/science_tool/plan_common.py tests/test_atomic_write_bytes.py
git commit -m "feat(txn): atomic_write_bytes RESTORE (exact preimage mode)"
```

---

## Task 6: Staged restartable `_materialize` (file/dir/symlink + absent dispatch)

**Files:**
- Modify: `src/science_tool/plan_common.py` (`_materialize`, `_remove_live`)
- Test: `tests/test_txn_restore.py` (new)

**Interfaces:**
- Produces: `_materialize(path, snap, *, token)` — staged publication per type; absent preimage
  dispatches `rmdir` (dir) vs `unlink` (file/symlink) then parent fsync.
- Consumes: `atomic_write_bytes` (RESTORE), `_rename_noreplace`, `staging_path_for`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_txn_restore.py
import os, stat, pytest
from science_tool.plan_common import _materialize, snapshot_paths, PathSnapshot, StateFingerprint

def _snap_of(path): return snapshot_paths([path])[path]

def test_restore_file(tmp_path):
    p = tmp_path / "f"; p.write_text("old"); os.chmod(p, 0o644)
    snap = _snap_of(p); p.write_text("new")
    _materialize(p, snap, token="t")
    assert p.read_text() == "old"

def test_restore_symlink(tmp_path):
    real = tmp_path / "r"; real.write_text("x")
    link = tmp_path / "l"; link.symlink_to(real)
    snap = _snap_of(link); link.unlink(); link.write_text("clobbered-into-file")
    _materialize(link, snap, token="t")
    assert link.is_symlink() and os.readlink(link) == str(real)

def test_restore_absent_over_created_dir(tmp_path):
    d = tmp_path / "made"; 
    absent = StateFingerprint(existed=False, type=None, content_sha256=None, mode=None, symlink_target=None)
    d.mkdir()
    _materialize(d, PathSnapshot(fp=absent, content=None), token="t")
    assert not d.exists()   # rmdir, not unlink (which would raise)
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run --frozen pytest tests/test_txn_restore.py -v`
Expected: FAIL (`_materialize` signature has no `token`; absent path uses `unlink` and raises on dir).

- [ ] **Step 3: Reimplement `_materialize` with staged publication**

```python
def _materialize(path, snap, *, token):
    fp = snap.fp
    if not fp.existed:
        _remove_live(path)                 # already dispatches rmdir vs unlink by lstat
        _fsync_parent(path); return
    if fp.type == "file":
        atomic_write_bytes(path, snap.content or b"", mode=WriteMode.RESTORE,
                           file_mode=fp.mode, token=token, target_pre=fingerprint(path))
        return                              # atomic_write_bytes fsyncs parent
    staging = staging_path_for(path, token)
    if fp.type == "dir":
        staging.mkdir(); os.chmod(staging, fp.mode)
    else:                                   # symlink
        os.symlink(fp.symlink_target, staging)
    _rename_noreplace_or_replace_for_restore(staging, path)   # restore may publish over an existing target
    _fsync_parent(path)
```

For restore specifically the target may legitimately exist (matches `post`); restore *replaces* it,
so directory/symlink publication here uses `os.replace(staging, path)` **after** confirming the live
target still matches `post` (the reconciliation entry — Task 7 — owns the survivor/no-clobber
concerns). Add `_fsync_parent(path)` helper (open parent `O_RDONLY`, fsync, close). Keep
`_remove_live`'s existing `rmdir`/`unlink` dispatch.

- [ ] **Step 4: Run to verify pass**

Run: `uv run --frozen pytest tests/test_txn_restore.py tests/test_plan_common.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/science_tool/plan_common.py tests/test_txn_restore.py
git commit -m "feat(txn): staged restartable _materialize for all preimage types"
```

---

## Task 7: Entry-time staging-survivor reconciliation

**Files:**
- Modify: `src/science_tool/plan_common.py` (add `reconcile_restore_staging`; call it in restore path)
- Test: `tests/test_txn_restore.py`

**Interfaces:**
- Produces: `reconcile_restore_staging(path, snap, *, token) -> None` — consumes a survivor per the
  design table (complete→publish, file-prefix→recreate, wrong-mode-dir→finish, foreign→halt).
- Consumes: `classify_staging`, `matches`.

- [ ] **Step 1: Write the failing test**

```python
def test_reconcile_completes_survivor_then_converges(tmp_path):
    from science_tool.plan_common import _materialize, snapshot_paths, staging_path_for
    p = tmp_path / "f"; p.write_text("old")
    snap = snapshot_paths([p])[p]; p.write_text("new")
    # simulate a kill AFTER staging written but BEFORE publish:
    staging = staging_path_for(p, "t"); staging.write_bytes(b"old")
    _materialize(p, snap, token="t")   # must consume the complete survivor, not O_EXCL-fail
    assert p.read_text() == "old" and not staging.exists()

def test_reconcile_halts_on_foreign_survivor(tmp_path):
    from science_tool.plan_common import _materialize, snapshot_paths, staging_path_for, RollbackHalt
    p = tmp_path / "f"; p.write_text("old")
    snap = snapshot_paths([p])[p]; p.write_text("new")
    staging_path_for(p, "t").write_bytes(b"unrelated-not-a-prefix")
    with pytest.raises(RollbackHalt):
        _materialize(p, snap, token="t")
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run --frozen pytest tests/test_txn_restore.py -k reconcile -v`
Expected: FAIL (staging survivor makes `atomic_write_bytes`' `O_EXCL` raise `StagingError`).

- [ ] **Step 3: Implement reconciliation and call it first in `_materialize`**

`reconcile_restore_staging` inspects `staging_path_for(path, token)`: if absent → return; for a file
preimage use `classify_staging(staging, snap.content)` → `complete` → publish (`os.replace`) + parent
fsync; `prefix` and our own → unlink (recreate downstream); non-prefix/foreign → `RollbackHalt`. For
dir/symlink survivors: a complete, attributable staging object → publish; wrong-mode staging dir →
`chmod` to `fp.mode` then publish; unattributable → `RollbackHalt`. `_materialize` calls it before
building fresh staging.

- [ ] **Step 4: Run to verify pass**

Run: `uv run --frozen pytest tests/test_txn_restore.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/science_tool/plan_common.py tests/test_txn_restore.py
git commit -m "feat(txn): restart-safe restore via staging-survivor reconciliation"
```

---

## Task 8: `OwnershipTracker` + typed execution state

**Files:**
- Modify: `src/science_tool/plan_common.py` (add `MutationOwnership`, `TransitionExecution`,
  `OwnershipTracker`)
- Test: `tests/test_ownership_tracker.py` (new)

**Interfaces:**
- Produces: `MutationOwnership(str, Enum)`; `@dataclass(frozen=True) TransitionExecution`;
  `OwnershipTracker(transitions)` with `.mark(index, ownership)` (monotonic) and
  `.as_executions() -> tuple[TransitionExecution, ...]`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ownership_tracker.py
import pytest
from science_tool.plan_common import OwnershipTracker, MutationOwnership as O, PathTransition, StateFingerprint

def _t(rel):
    a = StateFingerprint(existed=False, type=None, content_sha256=None, mode=None, symlink_target=None)
    d = StateFingerprint(existed=True, type="dir", content_sha256=None, mode=0o755, symlink_target=None)
    return PathTransition(role="created-dir", rel_path=rel, pre=a, post=d)

def test_starts_not_written_and_marks_monotonically():
    tr = OwnershipTracker([_t("a"), _t("b")])
    assert [e.ownership for e in tr.as_executions()] == [O.NOT_WRITTEN, O.NOT_WRITTEN]
    tr.mark(0, O.WRITTEN)
    assert tr.as_executions()[0].ownership is O.WRITTEN

def test_downgrade_raises():
    tr = OwnershipTracker([_t("a")]); tr.mark(0, O.WRITTEN)
    with pytest.raises(Exception):
        tr.mark(0, O.NOT_WRITTEN)

def test_out_of_range_raises():
    tr = OwnershipTracker([_t("a")])
    with pytest.raises(Exception):
        tr.mark(5, O.WRITTEN)
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run --frozen pytest tests/test_ownership_tracker.py -v`
Expected: FAIL (undefined).

- [ ] **Step 3: Implement**

```python
class MutationOwnership(str, Enum):
    NOT_WRITTEN = "not-written"; MAY_HAVE_WRITTEN = "may-have-written"; WRITTEN = "written"

_RANK = {MutationOwnership.NOT_WRITTEN: 0, MutationOwnership.MAY_HAVE_WRITTEN: 1, MutationOwnership.WRITTEN: 2}

@dataclass(frozen=True)
class TransitionExecution:
    transition: PathTransition
    ownership: MutationOwnership

class OwnershipTracker:
    def __init__(self, transitions):
        self._transitions = tuple(transitions)
        self._own = [MutationOwnership.NOT_WRITTEN] * len(self._transitions)
    def mark(self, index, ownership):
        if not 0 <= index < len(self._own): raise IndexError(index)
        if _RANK[ownership] < _RANK[self._own[index]]:
            raise ValueError(f"ownership downgrade at {index}: {self._own[index]} -> {ownership}")
        self._own[index] = ownership
    def as_executions(self):
        return tuple(TransitionExecution(t, o) for t, o in zip(self._transitions, self._own))
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run --frozen pytest tests/test_ownership_tracker.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/science_tool/plan_common.py tests/test_ownership_tracker.py
git commit -m "feat(txn): OwnershipTracker with monotonic mark"
```

---

## Task 9: Tracker-based `rollback_transitions` + action table

**Files:**
- Modify: `src/science_tool/plan_common.py` (`rollback_transitions` takes `OwnershipTracker`)
- Test: `tests/test_ownership_tracker.py`, `tests/test_plan_common.py`

**Interfaces:**
- Produces: `rollback_transitions(tracker: OwnershipTracker, project_root: Path, snapshot) -> None`
  implementing the seven-row action table.
- Consumes: `OwnershipTracker`, `_materialize`, `matches`, `RollbackHalt`.

- [ ] **Step 1: Write the failing test** (action-table rows: NOT_WRITTEN skip; WRITTEN+post restore;
  MAY_HAVE_WRITTEN+neither halt; WRITTEN+pre skip). Assert `rollback_transitions` rejects a bare list.

```python
def test_rollback_neither_halts(tmp_path):
    from science_tool.plan_common import (OwnershipTracker, MutationOwnership as O, rollback_transitions,
        snapshot_paths, RollbackHalt, PathTransition, StateFingerprint, resolve_within)
    f = tmp_path / "x.md"; f.write_text("pre")
    pre = snapshot_paths([f])[f].fp
    post = StateFingerprint(existed=True, type="file",
        content_sha256=__import__("hashlib").sha256(b"post").hexdigest(), mode=0o644, symlink_target=None)
    t = PathTransition(role="entity-rewrite", rel_path="x.md", pre=pre, post=post, postimage="post")
    tr = OwnershipTracker([t]); tr.mark(0, O.WRITTEN)
    f.write_text("SOMETHING ELSE")  # neither pre nor post
    with pytest.raises(RollbackHalt):
        rollback_transitions(tr, tmp_path, snapshot_paths([f]))

def test_rollback_rejects_bare_list(tmp_path):
    from science_tool.plan_common import rollback_transitions
    with pytest.raises(TypeError):
        rollback_transitions([], tmp_path, {})
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run --frozen pytest tests/test_ownership_tracker.py -k rollback -v`
Expected: FAIL.

- [ ] **Step 3: Implement the action table over the tracker**

Iterate `reversed(tracker.as_executions())` with original indices; per the seven rows: `NOT_WRITTEN`
→ continue; live `matches(pre)` → continue; live `matches(post)` → `_materialize(path, snap, token=…)`;
else `RollbackHalt`. Reject a non-`OwnershipTracker` first arg with `TypeError`. Derive a per-path
restore token deterministically (e.g. `f"restore-{index}"`).

- [ ] **Step 4: Run to verify pass**

Run: `uv run --frozen pytest tests/test_ownership_tracker.py tests/test_plan_common.py -v`
Expected: PASS (existing plan_common rollback tests may need migration to build a tracker — do so).

- [ ] **Step 5: Commit**

```bash
git add src/science_tool/plan_common.py tests/test_ownership_tracker.py tests/test_plan_common.py
git commit -m "feat(txn): tracker-based rollback_transitions with action table"
```

---

## Task 10: `move_no_clobber` (two seams, durability ordering)

**Files:**
- Modify: `src/science_tool/plan_common.py` (add `move_no_clobber`)
- Test: `tests/test_move_no_clobber.py` (new)

**Interfaces:**
- Produces: `move_no_clobber(src, dst, *, on_commit_dst=None, on_commit_src=None) -> None`.
- Consumes: `_rename_noreplace`, `_fsync_parent`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_move_no_clobber.py
import pytest
from science_tool.plan_common import move_no_clobber

def test_refuses_existing_dst(tmp_path):
    s = tmp_path / "s"; s.write_text("x"); d = tmp_path / "d"; d.write_text("keep")
    with pytest.raises(FileExistsError):
        move_no_clobber(s, d)
    assert d.read_text() == "keep" and s.exists()

def test_moves_and_fires_both_seams(tmp_path):
    s = tmp_path / "s"; s.write_text("x"); d = tmp_path / "d"
    seen = []
    move_no_clobber(s, d, on_commit_dst=lambda: seen.append("dst"), on_commit_src=lambda: seen.append("src"))
    assert d.read_text() == "x" and not s.exists() and "dst" in seen and "src" in seen
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run --frozen pytest tests/test_move_no_clobber.py -v`
Expected: FAIL (undefined).

- [ ] **Step 3: Implement**

renameat2 path: `_rename_noreplace(src, dst)`; on success fire both callbacks, fsync both parents.
When `_rename_noreplace` falls back to `link`+`unlink` internally, that ordering is wrong for two
seams — so implement `move_no_clobber` to do the fallback itself when needed:
`O_EXCL link(src,dst)` → `on_commit_dst` → `_fsync_parent(dst)` → `unlink(src)` → `on_commit_src` →
`_fsync_parent(src)`. Detect `renameat2` availability once (module-level probe) to choose the path;
the atomic path fires both callbacks after the single rename.

- [ ] **Step 4: Run to verify pass**

Run: `uv run --frozen pytest tests/test_move_no_clobber.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/science_tool/plan_common.py tests/test_move_no_clobber.py
git commit -m "feat(txn): move_no_clobber with ordered two-seam durability"
```

---

## Task 11: Durable seam primitives (`create_exclusive`, `mkdir_durable`, `unlink_durable`, durable replace)

**Files:**
- Modify: `src/science_tool/plan_common.py`
- Test: `tests/test_durable_seams.py` (new)

**Interfaces:**
- Produces: `create_exclusive(path, text, mode, *, on_commit=None)`;
  `mkdir_durable(path, mode, *, token, on_commit=None)`;
  `unlink_durable(path, *, on_commit=None)`;
  `durable_replace_text(path, postimage, mode, token, *, target_pre, on_commit=None)`.
- Consumes: `_rename_noreplace`, `atomic_write_bytes`, `_fsync_parent`, `PreconditionRefused`.

- [ ] **Step 1: Write the failing test** — mark-at-linearization for each primitive, no-clobber dir.

```python
# tests/test_durable_seams.py
import os, stat, pytest
from science_tool.plan_common import (create_exclusive, mkdir_durable, unlink_durable, PreconditionRefused)

def test_create_exclusive_marks_at_open(tmp_path):
    p = tmp_path / "e.md"; fired = []
    create_exclusive(p, "body", 0o644, on_commit=lambda: fired.append(1))
    assert p.read_text() == "body" and stat.S_IMODE(p.stat().st_mode) == 0o644 and fired == [1]
    with pytest.raises(FileExistsError):
        create_exclusive(p, "again", 0o644)

def test_mkdir_durable_no_clobber(tmp_path):
    d = tmp_path / "anc"; d.mkdir()   # concurrent creator got here first
    with pytest.raises(PreconditionRefused):
        mkdir_durable(d, 0o755, token="t")

def test_unlink_durable_marks(tmp_path):
    p = tmp_path / "s.md"; p.write_text("x"); fired = []
    unlink_durable(p, on_commit=lambda: fired.append(1))
    assert not p.exists() and fired == [1]
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run --frozen pytest tests/test_durable_seams.py -v`
Expected: FAIL (undefined).

- [ ] **Step 3: Implement**

- `create_exclusive`: `fd = os.open(path, O_WRONLY|O_CREAT|O_EXCL, mode)` → **`on_commit()`** → write
  → `fchmod` exact → fsync file → fsync parent. (Callback right after the exclusive open — Global
  Constraints.)
- `mkdir_durable`: mkdir staging (`staging_path_for(path, token)` dir) → `chmod` exact →
  `_rename_noreplace(staging, path)`; on `FileExistsError` → remove staging, `raise PreconditionRefused`;
  else `on_commit()` → fsync parent.
- `unlink_durable`: `os.unlink(path)` → `on_commit()` → fsync parent.
- `durable_replace_text`: thin wrapper over `atomic_write_bytes(..., mode=REPLACE, ...)` recheck of
  `target_pre` at the boundary, firing `on_commit` at the replace.

- [ ] **Step 4: Run to verify pass**

Run: `uv run --frozen pytest tests/test_durable_seams.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/science_tool/plan_common.py tests/test_durable_seams.py
git commit -m "feat(txn): durable callback-bearing seam primitives"
```

---

## Task 12: Wire archive + supersede rollback to the tracker

**Files:**
- Modify: `src/science_tool/archive_plan.py` (`apply_archive_plan`), `supersede_plan.py`
  (`apply_supersede_plan`)
- Test: `tests/test_archive_plan.py`, `tests/test_supersede_plan.py` (extend)

**Interfaces:**
- Consumes: `OwnershipTracker`, tracker-based `rollback_transitions`, `capture_and_verify`.
- Produces: unchanged public `apply_*` signatures; internal rollback now tracker-driven.

- [ ] **Step 1: Write/extend the failing test** — an injected apply failure rolls back via the tracker
  and leaves the tree at pre-state; a `neither` referrer halts. (Reuse each module's existing
  rollback test harness, swapping the assertion to go through the tracker path.)

- [ ] **Step 2: Run to verify it fails**

Run: `uv run --frozen pytest tests/test_archive_plan.py tests/test_supersede_plan.py -v`
Expected: FAIL (apply still calls the removed bare-list `rollback_transitions`).

- [ ] **Step 3: Migrate both apply functions**

Build an `OwnershipTracker` from the plan's transition list; pass `on_commit=lambda i=i:
tracker.mark(i, WRITTEN)` into each staged write / `move_no_clobber` seam; on failure call
`rollback_transitions(tracker, project_root, snapshot)`. Replace `snapshot_paths` at the apply
entry with `capture_and_verify(transitions, project_root)` so pre-drift is a clean
`PreconditionRefused`.

- [ ] **Step 4: Run to verify pass**

Run: `uv run --frozen pytest tests/test_archive_plan.py tests/test_supersede_plan.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/science_tool/archive_plan.py src/science_tool/supersede_plan.py tests/test_archive_plan.py tests/test_supersede_plan.py
git commit -m "refactor(txn): archive+supersede rollback via OwnershipTracker"
```

---

## Task 13: Import `PathTransition` roles + validators

**Files:**
- Modify: `src/science_tool/plan_common.py` (`PathTransition.role`, `_STAGED_ROLES`, `_coherent`)
- Test: `tests/test_plan_common.py`

**Interfaces:**
- Produces: roles `import-dst`, `import-src`; `import-dst` in `_STAGED_ROLES` (postimage + hash);
  `import-dst` pre absent; `import-src` post absent.

- [ ] **Step 1: Write the failing test**

```python
def test_import_dst_requires_matching_postimage(tmp_path):
    from science_tool.plan_common import PathTransition, StateFingerprint
    import hashlib
    text = "# Title\n"
    post = StateFingerprint(existed=True, type="file",
        content_sha256=hashlib.sha256(text.encode()).hexdigest(), mode=0o644, symlink_target=None)
    absent = StateFingerprint(existed=False, type=None, content_sha256=None, mode=None, symlink_target=None)
    PathTransition(role="import-dst", rel_path="entities/x.md", pre=absent, post=post, postimage=text)
    with pytest.raises(Exception):
        PathTransition(role="import-dst", rel_path="entities/x.md", pre=post, post=post, postimage=text)  # pre not absent

def test_import_src_post_absent(tmp_path):
    from science_tool.plan_common import PathTransition, StateFingerprint
    pre = StateFingerprint(existed=True, type="file",
        content_sha256="0"*64, mode=0o644, symlink_target=None)
    absent = StateFingerprint(existed=False, type=None, content_sha256=None, mode=None, symlink_target=None)
    PathTransition(role="import-src", rel_path="loose.md", pre=pre, post=absent)
    with pytest.raises(Exception):
        PathTransition(role="import-src", rel_path="loose.md", pre=pre, post=pre)
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run --frozen pytest tests/test_plan_common.py -k import_ -v`
Expected: FAIL (unknown role).

- [ ] **Step 3: Extend the model**

Add `"import-dst", "import-src"` to the `role` Literal; add `"import-dst"` to `_STAGED_ROLES`;
extend the pre-absent set to `{"archive-dst", "created-dir", "import-dst"}`; extend the post-absent
check to `role in {"archive-src", "import-src"}`.

- [ ] **Step 4: Run to verify pass**

Run: `uv run --frozen pytest tests/test_plan_common.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/science_tool/plan_common.py tests/test_plan_common.py
git commit -m "feat(import): import-dst/import-src PathTransition roles"
```

---

## Task 14: Import plan wire schema (transitions + versioning)

**Files:**
- Modify: `src/science_tool/entity_import.py` (`ImportPlan`, `CohortImportPlan`, `plan_import`,
  `plan_cohort_import`, `parse_*`)
- Test: `tests/test_entity_import.py`, `tests/test_cohort_import.py`

**Interfaces:**
- Produces: `ImportPlan.transitions: list[PathTransition]`, `ImportPlan.schema_version: int = 1`;
  `CohortImportPlan.transitions`, `schema_version` bumped `1 → 2`; `parse_cohort_import_plan` rejects
  v1.
- Consumes: `PathTransition`, `_missing_ancestor_dirs`, roles from Task 13.

Existing tests this version bump will break (update them in this task, don't loosen them):
`test_cohort_plan_defaults_and_discriminator` and `test_parse_cohort_round_trips` in
`tests/test_cohort_import.py` assert `schema_version == 1` — bump their expectations to `2`.
Reuse the module's real fixtures: `_project(tmp_path)`, `_loose(root, rel, text)`, `_valid_plan(root)`.

- [ ] **Step 1: Write the failing test**

```python
def test_cohort_v1_plan_rejected(tmp_path):
    from science_tool.entity_import import parse_cohort_import_plan
    import json
    v1 = json.dumps({"plan_type": "cohort-import", "schema_version": 1, "project_root": str(tmp_path),
                     "kind": "paper", "members": [], "ref_report": {}, "warnings": []}).encode()
    with pytest.raises(Exception):
        parse_cohort_import_plan(v1)

def test_plan_import_derives_transitions(tmp_path):
    from science_tool.entity_import import plan_import
    import hashlib
    root = _project(tmp_path)                       # existing fixture in test_cohort_import.py
    src = _loose(root, "loose.md", "# Title\n\nbody\n")
    plan = plan_import(root, src.relative_to(root).as_posix(), kind="paper")
    by_role = {t.role: t for t in plan.transitions}
    dst = by_role["import-dst"]
    assert dst.post.mode == 0o644
    assert dst.post.content_sha256 == hashlib.sha256(plan.rendered_text.encode()).hexdigest()
    assert by_role["import-src"].post.existed is False
    # a created-dir transition appears only if the destination needs a missing ancestor;
    # assert its post.type == "dir" when present.
    for t in plan.transitions:
        if t.role == "created-dir":
            assert t.post.type == "dir"
```

(`plan_import`'s exact keyword args — `kind`, `number`, `title` — match the shipped signature; adjust
the call to the real one. This is one of the three fixture-dependent fill-ins flagged in self-review.)

- [ ] **Step 2: Run to verify it fails**

Run: `uv run --frozen pytest tests/test_cohort_import.py -k v1 tests/test_entity_import.py -k transitions -v`
Expected: FAIL.

- [ ] **Step 3: Implement**

Add `transitions` + `schema_version` fields. In `plan_import`/`plan_cohort_import`, derive the
transition set at preview time: `import-dst` (`pre` absent, `post` file with `mode=0o644` and
`content_sha256 == sha256(rendered_text)`, `postimage=rendered_text`), `import-src` (`pre` = source
fingerprint, `post` absent), `created-dir` per `_missing_ancestor_dirs`, and `entity-rewrite` per
`ref_report` edit. Bump `CohortImportPlan.schema_version` default to `2`; in `parse_cohort_import_plan`
raise a clear "re-run the preview" error unless `schema_version == 2`.

- [ ] **Step 4: Run to verify pass**

Run: `uv run --frozen pytest tests/test_cohort_import.py tests/test_entity_import.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/science_tool/entity_import.py tests/test_cohort_import.py tests/test_entity_import.py
git commit -m "feat(import): persist transitions + version the saved-plan wire schema"
```

---

## Task 15: Migrate import apply onto tracker + durable seams

**Files:**
- Modify: `src/science_tool/entity_import.py` (`apply_import`, `apply_cohort_import`),
  `src/science_tool/entity_reservation.py` (`claim_number_in_dir` → `create_exclusive`),
  `src/science_tool/reference_rewrite.py` (durable per-edit replace + `on_commit`)
- Test: `tests/test_entity_import.py`, `tests/test_cohort_import.py`

**Interfaces:**
- Consumes: `OwnershipTracker`, durable seam primitives (Task 11), `capture_and_verify`, tracker-based
  `rollback_transitions`.
- Produces: unchanged public `apply_import`/`apply_cohort_import` signatures; ownership-driven rollback
  preserving `restrict=written` (rejected referrers stay `NOT_WRITTEN`).

- [ ] **Step 1: Write the failing test** — port the contended-unwritten guarantee: a referrer changed
  by another writer and rejected by the per-write recheck stays untouched after rollback; the
  `import-dst` mid-create third state hard-halts. Use the existing pre-migration import rollback test
  in `tests/test_entity_import.py` as the behavioral oracle — the port must preserve its assertions,
  now driven through the tracker. Reuse `_project`/`_loose`. (Second of the three fixture-dependent
  fill-ins: the exact monkeypatch that makes one referrer's per-write recheck reject depends on the
  existing test's mechanism — mirror it.)

- [ ] **Step 2: Run to verify it fails**

Run: `uv run --frozen pytest tests/test_entity_import.py tests/test_cohort_import.py -v`
Expected: FAIL.

- [ ] **Step 3: Migrate apply**

Replace `_snapshot`/`_restore`/`mutated`-set bookkeeping with: `capture_and_verify(plan.transitions,
project_root)`; an `OwnershipTracker(plan.transitions)`; seams wired to `tracker.mark`
(`create_exclusive` for `import-dst`, `mkdir_durable` per `created-dir`, `unlink_durable` for
`import-src`, durable per-edit replace for `entity-rewrite`); on failure
`rollback_transitions(tracker, project_root, snapshot)`. `claim_number_in_dir` calls
`create_exclusive` (marking `import-dst` at the exclusive open — the hard-halt seam). A referrer whose
per-write recheck rejects it is never marked, so it stays `NOT_WRITTEN` and rollback leaves it. Retire
`_FileState`/`_TreeSnapshot`/`_snapshot`/`_restore` once no caller remains.

- [ ] **Step 4: Run to verify pass**

Run: `uv run --frozen pytest tests/test_entity_import.py tests/test_cohort_import.py tests/test_entity_import_cli.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/science_tool/entity_import.py src/science_tool/entity_reservation.py src/science_tool/reference_rewrite.py tests/
git commit -m "refactor(import): apply on shared tracker substrate; retire private snapshot"
```

---

## Task 16: Acceptance harness — true-write-surface across all four families

**Files:**
- Create: `tests/test_write_surface_acceptance.py`; a syscall-audit fixture helper (e.g.
  `tests/_fs_audit.py`)
- Test: the harness itself (marked to run in default suite; the syscall audit must degrade to a
  skip if the environment lacks `strace`/ptrace permission, never a false pass).

**Interfaces:**
- Consumes: `apply_archive_plan`, `apply_supersede_plan`, `apply_import`, `apply_cohort_import`;
  each plan's `transitions`.

- [ ] **Step 1: Write the harness + tests**

A fixture runs a callable under a filesystem-mutation audit (strace `-e trace=%file` or a ptrace
shim), returning the set of mutating syscalls with their target paths. Three assertions per family:
(a) `observed_persistent_changes == {t.rel_path for t in transitions if t.pre != t.post}` over a full
before/after tree map (bytes, type, mode, symlink, dir existence); (b) every mutating syscall targets
a declared transition path or a declared scratch shape (`.NNNN.reserving` sentinel, `*.tmp` token),
and no scratch survives a clean run; (c) with `_fault` injection at each seam and the parent-dir
fsync, each survivor is attributable and classifiable.

```python
def test_import_persistent_surface_equals_transitions(tmp_path):
    from science_tool.entity_import import plan_import, apply_import
    root = _project(tmp_path)                       # existing fixture pattern from test_cohort_import.py
    src = _loose(root, "loose.md", "# Title\n\nbody\n")
    plan = plan_import(root, src.relative_to(root).as_posix(), kind="paper")
    before = _tree_map(root)
    apply_import(root, plan)
    observed = _diff(before, _tree_map(root))
    assert observed == {t.rel_path for t in plan.transitions if t.pre != t.post}
```

(Third fixture-dependent fill-in: `_tree_map`/`_diff` are new helpers this task defines; `_project`/
`_loose` are copied from `test_cohort_import.py` or promoted to a shared conftest.)

- [ ] **Step 2: Run to verify it fails**

Run: `uv run --frozen pytest tests/test_write_surface_acceptance.py -v`
Expected: FAIL until the fixture + `_tree_map`/`_diff` helpers exist.

- [ ] **Step 3: Implement the fixture and helpers**

`_tree_map` walks the project (excluding `.git`) recording per-path (type, mode, sha256|symlink
target|dir). The audit fixture wraps the mutator call; if syscall tracing is unavailable it `skip`s
the transient/kill-boundary assertions but still runs the persistent-surface assertion (which needs
no tracing) — a missing tracer must never read as a pass of the stronger claims.

- [ ] **Step 4: Run to verify pass**

Run: `uv run --frozen pytest tests/test_write_surface_acceptance.py -v`
Expected: PASS (persistent-surface always; transient/kill assertions PASS or SKIP by environment).

- [ ] **Step 5: Commit**

```bash
git add tests/test_write_surface_acceptance.py tests/_fs_audit.py
git commit -m "test(txn): acceptance-time true-write-surface harness (all four families)"
```

---

## Final verification (after all tasks)

Run from `science/`:

```bash
uv run --frozen pytest
uv run ruff check
uv run pyright
```

Expected: full suite green; ruff clean; pyright clean over the three source trees. Then run the
opt-in markers touched by this work:

```bash
uv run --frozen pytest -m snapshot
uv run --frozen pytest -m real_projects
```

Refresh any formatter/registry snapshot that legitimately changed (e.g. a new `PathTransition` role
in a serialized fixture), never by loosening an assertion.

## Self-review checklist (run before handing off)

- **Spec coverage:** Pieces 1–7 each map to tasks — P1→T1-2, P6→T3-5, P5→T6-7, P2→T8-9, P4→T10-12,
  P3→T13-15, P7→T16. Every design load-bearing test (1–9) has a home (T1-2, T3-5, T6-7, T9, T10-11,
  T14-15, T16).
- **Type consistency:** `OwnershipTracker`, `TransitionExecution`, `MutationOwnership`, `WriteMode`,
  `PreconditionRefused`, `BlobMismatch`, `move_no_clobber`, `create_exclusive`, `mkdir_durable`,
  `unlink_durable`, `atomic_write_bytes`, `capture_and_verify` are spelled identically across tasks.
- **No placeholders:** every code step carries real code; three tasks (T14 plan-derive, T15
  contended-referrer, T16 scaffold) leave `...` in *test scaffolding* that depends on the project
  fixture — the implementer fills these against the real `_scaffold` helpers, and the surrounding
  assertions are concrete. Flag these three to the executor as the only fill-in points.

## Execution handoff

Plan complete and saved to
`docs/plans/2026-07-20-txn-substrate-convergence-implementation.md`. Two execution options:

1. **Subagent-Driven (recommended)** — a fresh implementer subagent per task, task review between
   tasks, broad whole-branch review at the end. Best fit here: the tasks are mostly independent and
   the substrate is safety-critical, so per-task review earns its cost.
2. **Inline Execution** — execute tasks in this session with checkpoints.

Which approach?

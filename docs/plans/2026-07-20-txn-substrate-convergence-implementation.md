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
- **Restore authority is the transition's frozen `post`, never a fresh `fingerprint(path)`.** The
  expected-live fingerprint (`transition.post`) is threaded from `rollback_transitions` through
  `_materialize` and `reconcile_restore_staging` and passed **unchanged** as `atomic_write_bytes`'s
  `target_pre`. Restore must never re-read the live file and adopt it as its own precondition — that
  would re-authorize a concurrent writer's content.
- **No-clobber publication everywhere:** moves, blobs, and staged directories publish through the one
  `_publish_no_clobber` primitive — `renameat2(RENAME_NOREPLACE)` when the kernel has it, else an
  ordered `O_EXCL link → fsync(dst parent) → unlink(src) → fsync(src parent)` fallback (files/blobs
  only; directories have no link fallback and require `renameat2`). Never `os.replace` where another
  writer's object could be silently removed. Restore *publish-over-post* is the sole exception: it may
  `os.replace` only after confirming the live target still matches `expected_live`.
- **Unique `rel_path`s per transition set** in this PR; chained occurrences are deferred.
- **Restore staging tokens are transaction-unique:** rollback derives each path's token as
  `f"{op_token}-restore-{index}"` from a per-operation token, never a bare `restore-{index}`.
- **Durability order:** file fsync → publish → parent-dir fsync; the ordered link fallback makes the
  destination durable (fsync dst parent) **before** the source is unlinked.
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

The load-bearing red is a coherence test with an **injected writer between the two reads** — it must
fail on today's `snapshot_paths` (`fingerprint(p)` reads+hashes, then `p.read_bytes()` reads again)
and pass once capture binds hash and bytes to one fd.

```python
# tests/test_txn_capture.py
import hashlib, os, stat
from pathlib import Path
import pytest
from science_tool import plan_common
from science_tool.plan_common import snapshot_paths, fingerprint, UnsupportedPathType

def test_capture_is_coherent_under_interleaved_writer(tmp_path, monkeypatch):
    """A writer that changes the file BETWEEN the fingerprint read and the bytes read must not
    produce a snapshot whose recorded hash disagrees with its retained bytes. On the shipped
    two-read implementation the hash describes the old bytes and `content` holds the new bytes;
    single-fd capture closes the gap."""
    p = tmp_path / "f.md"; p.write_text("original")
    real_read_bytes = Path.read_bytes
    calls = {"n": 0}

    def racing_read_bytes(self):
        data = real_read_bytes(self)
        if self == p and calls["n"] == 0:      # right after the FIRST read (fingerprint's)
            calls["n"] = 1
            fd = os.open(p, os.O_WRONLY | os.O_TRUNC)
            try:
                os.write(fd, b"tampered-longer-content")
            finally:
                os.close(fd)
        return data

    # If capture still does two Path.read_bytes calls, the second returns the tampered bytes while
    # the hash came from the first -> incoherent. One fd + one os.read cannot be split this way.
    monkeypatch.setattr(Path, "read_bytes", racing_read_bytes)
    snap = snapshot_paths([p])[p]
    assert snap.fp.content_sha256 == hashlib.sha256(snap.content).hexdigest()

def test_snapshot_hash_matches_retained_bytes(tmp_path):
    p = tmp_path / "f.md"; p.write_text("hello")
    snap = snapshot_paths([p])[p]
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
Expected: FAIL on `test_capture_is_coherent_under_interleaved_writer` (shipped two-read capture is
incoherent under the injected writer). The symlink/non-regular tests already pass and serve as
regression pins across the Step 3 refactor.

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

These tests use only roles that already exist on today's `PathTransition` (`entity-rewrite`,
`created-dir`) so Task 2 does not depend on Task 13's new roles. `import hashlib` at module top.

```python
def test_capture_and_verify_refuses_on_pre_mismatch(tmp_path):
    from science_tool.plan_common import (capture_and_verify, PreconditionRefused,
                                          PathTransition, StateFingerprint)
    body = "# Title\n"
    f = tmp_path / "a.md"; f.write_text("current")     # live bytes != stale_pre
    stale_pre = StateFingerprint(existed=True, type="file",
        content_sha256=hashlib.sha256(b"stale").hexdigest(), mode=0o644, symlink_target=None)
    post = StateFingerprint(existed=True, type="file",
        content_sha256=hashlib.sha256(body.encode()).hexdigest(), mode=0o644, symlink_target=None)
    t = PathTransition(role="entity-rewrite", rel_path="a.md", pre=stale_pre, post=post, postimage=body)
    with pytest.raises(PreconditionRefused):
        capture_and_verify([t], tmp_path)

def test_capture_and_verify_rejects_repeated_rel_path(tmp_path):
    from science_tool.plan_common import (capture_and_verify, PathTransition,
                                          StateFingerprint, BoundaryError)
    absent = StateFingerprint(existed=False, type=None, content_sha256=None, mode=None, symlink_target=None)
    dirpost = StateFingerprint(existed=True, type="dir", content_sha256=None, mode=0o755, symlink_target=None)
    t1 = PathTransition(role="created-dir", rel_path="d", pre=absent, post=dirpost)
    t2 = PathTransition(role="created-dir", rel_path="d", pre=absent, post=dirpost)
    with pytest.raises(BoundaryError):
        capture_and_verify([t1, t2], tmp_path)
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run --frozen pytest tests/test_txn_capture.py -k capture_and_verify -v`
Expected: FAIL (`capture_and_verify` and `BoundaryError` undefined — `ImportError`).

- [ ] **Step 3: Implement**

`BoundaryError` does **not** exist in `plan_common.py` today (grep-confirmed). Add it as a new
module-level exception beside `PathEscape`/`StagingError`, then `capture_and_verify`:

```python
class BoundaryError(RuntimeError):
    """A transition set violates a structural precondition of the substrate (e.g. a repeated
    rel_path this PR does not support). Raised at capture time, before any mutation."""

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
    if mode is not WriteMode.REPLACE:
        raise NotImplementedError(f"{mode} added in a later task")   # CREATE_OR_VERIFY=T4, RESTORE=T5
    # REPLACE: preserve the live file's mode on overwrite; require file_mode only on first create.
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
        os.replace(staging, path)          # REPLACE linearization point
        if on_commit is not None: on_commit()
        _fsync_parent(path)
    except Exception:
        if staging.exists() and data.startswith(staging.read_bytes()) and matches(target_pre, path):
            staging.unlink()
        raise
```

Define the shared `_fsync_parent` helper here (Task 3 is its first user); Tasks 4–15 reuse it:

```python
def _fsync_parent(path):
    dfd = os.open(path.parent, os.O_RDONLY)
    try:
        os.fsync(dfd)
    finally:
        os.close(dfd)
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
- Produces:
  - `_renameat2_available: bool` — module-level probe (does libc expose `renameat2` and does it not
    return `ENOSYS`).
  - `_rename_noreplace(src: Path, dst: Path) -> None` — **atomic no-clobber rename only.** Raises
    `FileExistsError` if dst exists; raises `NoAtomicRename` (a private sentinel) if the kernel lacks
    `renameat2`. It performs **no** link fallback — capability detection is separated from the ordered
    fallback (fixes the unfsynced `link→unlink` durability gap).
  - `_publish_no_clobber(src: Path, dst: Path, *, on_commit=None) -> None` — publishes a regular file
    with no-clobber semantics and correct durability, for the **blob** shape where `src` is a staging
    file in `dst`'s own directory (one seam, one parent to fsync): atomic `_rename_noreplace` when
    available (fire `on_commit`, fsync dst parent); else ordered fallback `O_EXCL link(src,dst)` →
    `on_commit()` → `fsync(dst parent)` → `unlink(src)` → `fsync(src parent)`. `move_no_clobber`
    (Task 10) shares the `_rename_noreplace`/`NoAtomicRename` probe but has its own ordered fallback
    because a move crosses two directories and carries two seams.
  - `class BlobMismatch(RuntimeError)`.
- Consumes: Task 3 scaffolding, `_fsync_parent` (Task 3).

- [ ] **Step 1: Write the failing test**

CREATE_OR_VERIFY must create with an explicit `file_mode` (a fresh blob has no live mode to inherit —
this is why Task 3 rejects first-create without one).

```python
def test_create_or_verify_idempotent_equal(tmp_path):
    from science_tool.plan_common import atomic_write_bytes, WriteMode, fingerprint
    p = tmp_path / "ab"; p.write_bytes(b"blob")
    atomic_write_bytes(p, b"blob", mode=WriteMode.CREATE_OR_VERIFY, file_mode=0o444, token="t",
                       target_pre=fingerprint(p))              # equal -> idempotent success
    assert p.read_bytes() == b"blob"

def test_create_or_verify_mismatch_raises(tmp_path):
    from science_tool.plan_common import atomic_write_bytes, WriteMode, BlobMismatch, fingerprint
    p = tmp_path / "ab"; p.write_bytes(b"other")
    with pytest.raises(BlobMismatch):
        atomic_write_bytes(p, b"blob", mode=WriteMode.CREATE_OR_VERIFY, file_mode=0o444, token="t",
                           target_pre=fingerprint(p))

def test_create_or_verify_creates_when_absent(tmp_path):
    import stat
    from science_tool.plan_common import atomic_write_bytes, WriteMode, fingerprint
    p = tmp_path / "ab"
    atomic_write_bytes(p, b"blob", mode=WriteMode.CREATE_OR_VERIFY, file_mode=0o444, token="t",
                       target_pre=fingerprint(p))
    assert p.read_bytes() == b"blob" and stat.S_IMODE(p.stat().st_mode) == 0o444

def test_create_or_verify_requires_file_mode(tmp_path):
    from science_tool.plan_common import atomic_write_bytes, WriteMode, StagingError, fingerprint
    p = tmp_path / "ab"
    with pytest.raises(StagingError):
        atomic_write_bytes(p, b"blob", mode=WriteMode.CREATE_OR_VERIFY, token="t",
                           target_pre=fingerprint(p))
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run --frozen pytest tests/test_atomic_write_bytes.py -k create_or_verify -v`
Expected: FAIL (`NotImplementedError`).

- [ ] **Step 3: Implement `_rename_noreplace`, `_publish_no_clobber`, and CREATE_OR_VERIFY**

```python
import ctypes, errno

class NoAtomicRename(RuntimeError):
    """renameat2(RENAME_NOREPLACE) is unavailable on this kernel; callers use the ordered fallback."""

_AT_FDCWD = -100
_RENAME_NOREPLACE = 1 << 0

def _rename_noreplace(src: Path, dst: Path) -> None:
    """ATOMIC no-clobber rename. No fallback here — capability detection only."""
    libc = ctypes.CDLL("libc.so.6", use_errno=True)
    res = libc.renameat2(_AT_FDCWD, os.fsencode(src), _AT_FDCWD, os.fsencode(dst), _RENAME_NOREPLACE)
    if res != 0:
        err = ctypes.get_errno()
        if err == errno.EEXIST:
            raise FileExistsError(dst)
        if err == errno.ENOSYS:
            raise NoAtomicRename(str(dst))
        raise OSError(err, os.strerror(err), str(dst))

def _publish_no_clobber(src: Path, dst: Path, *, on_commit=None) -> None:
    """No-clobber publish of a regular file with correct durability ordering. Used by blobs and moves.
    Directories have no link fallback and must go through _rename_noreplace directly (Task 11)."""
    try:
        _rename_noreplace(src, dst)              # atomic path: single linearization point
        if on_commit is not None:
            on_commit()
        _fsync_parent(dst)
        return
    except NoAtomicRename:
        pass
    # Ordered fallback: make dst durable BEFORE unlinking src (Global Constraint).
    try:
        os.link(src, dst)                        # fails EEXIST if dst present -> no-clobber preserved
    except FileExistsError:
        raise
    if on_commit is not None:                    # linearization point = the link that creates dst
        on_commit()
    _fsync_parent(dst)
    os.unlink(src)
    _fsync_parent(src)

class BlobMismatch(RuntimeError): ...
```

In `atomic_write_bytes`, replace the CREATE_OR_VERIFY `NotImplementedError` branch with:

```python
    if mode is WriteMode.CREATE_OR_VERIFY:
        if file_mode is None:
            raise StagingError("CREATE_OR_VERIFY requires file_mode (a fresh blob has no live mode)")
        if path.exists():                                    # fast path
            if path.read_bytes() == data:
                return                                       # idempotent
            raise BlobMismatch(f"blob at {path} differs from intended content")
        staging = staging_path_for(path, token)
        fd = os.open(staging, os.O_WRONLY | os.O_CREAT | os.O_EXCL, file_mode)
        with os.fdopen(fd, "wb") as fh:
            fh.write(data); fh.flush()
            os.fchmod(fh.fileno(), file_mode); os.fsync(fh.fileno())
        try:
            _publish_no_clobber(staging, path, on_commit=on_commit)
        except FileExistsError:                              # lost the race; verify equality
            survivor = path.read_bytes(); staging.unlink()
            if survivor != data:
                raise BlobMismatch(f"blob at {path} differs (concurrent create)")
        return
```

(The REPLACE branch from Task 3 is unchanged; add this branch above it, after the symlink/dir guard.)

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
  mode **unconditionally**, even when it differs from the live file's mode (REPLACE preserves the live
  mode; RESTORE forces `file_mode`). `file_mode` is required.

- [ ] **Step 1: Write the failing test**

```python
def test_restore_forces_preimage_mode_where_replace_would_preserve(tmp_path):
    import stat
    from science_tool.plan_common import atomic_write_bytes, WriteMode, StagingError, fingerprint
    p = tmp_path / "f"; p.write_bytes(b"new"); os.chmod(p, 0o600)   # live mode 0o600
    # REPLACE without file_mode preserves the live 0o600 ...
    atomic_write_bytes(p, b"mid", mode=WriteMode.REPLACE, token="t0", target_pre=fingerprint(p))
    assert stat.S_IMODE(p.stat().st_mode) == 0o600
    # ... RESTORE forces the preimage's 0o644 even though the live file is 0o600.
    atomic_write_bytes(p, b"old", mode=WriteMode.RESTORE, file_mode=0o644,
                       token="t1", target_pre=fingerprint(p))
    assert p.read_bytes() == b"old" and stat.S_IMODE(p.stat().st_mode) == 0o644

def test_restore_requires_file_mode(tmp_path):
    from science_tool.plan_common import atomic_write_bytes, WriteMode, StagingError, fingerprint
    p = tmp_path / "f"; p.write_bytes(b"new")
    with pytest.raises(StagingError):
        atomic_write_bytes(p, b"old", mode=WriteMode.RESTORE, token="t", target_pre=fingerprint(p))
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run --frozen pytest tests/test_atomic_write_bytes.py -k restore -v`
Expected: FAIL — after Task 3, RESTORE raises `NotImplementedError`.

- [ ] **Step 3: Implement the RESTORE branch**

Add above the REPLACE branch (and remove RESTORE from the `mode is not WriteMode.REPLACE` guard):

```python
    if mode is WriteMode.RESTORE:
        if file_mode is None:
            raise StagingError("RESTORE requires file_mode (the preimage's exact mode)")
        staging = staging_path_for(path, token)
        fd = os.open(staging, os.O_WRONLY | os.O_CREAT | os.O_EXCL, file_mode)
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(data); fh.flush()
                os.fchmod(fh.fileno(), file_mode); os.fsync(fh.fileno())  # force exact preimage mode
            os.replace(staging, path)          # restore publish-over-post (target legitimately exists)
            if on_commit is not None: on_commit()
            _fsync_parent(path)
        except Exception:
            if staging.exists() and data.startswith(staging.read_bytes()) and matches(target_pre, path):
                staging.unlink()
            raise
        return
```

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
- Produces: `_materialize(path, snap, *, token, expected_live: StateFingerprint)` — staged publication
  per type. `expected_live` is the state rollback already verified the live path holds (the
  transition's `post`); `_materialize` guards on it and **never re-reads** the live file to derive its
  own precondition. Absent preimage dispatches `rmdir` (dir) vs `unlink` (file/symlink) then parent
  fsync.
- Consumes: `atomic_write_bytes` (RESTORE), `_rename_noreplace`, `staging_path_for`, `_fsync_parent`
  (Task 3), `matches`, `RollbackHalt`.

- [ ] **Step 1: Write the failing test**

The caller (rollback, or these tests) passes the verified post state as `expected_live`; a live path
that diverges from it halts instead of being clobbered.

```python
# tests/test_txn_restore.py
import os, stat, pytest
from science_tool.plan_common import (_materialize, snapshot_paths, fingerprint, PathSnapshot,
                                      StateFingerprint, RollbackHalt)

def _snap_of(path): return snapshot_paths([path])[path]

def test_restore_file(tmp_path):
    p = tmp_path / "f"; p.write_text("old"); os.chmod(p, 0o644)
    snap = _snap_of(p); p.write_text("new")
    _materialize(p, snap, token="t", expected_live=fingerprint(p))   # expected_live = the "new" post
    assert p.read_text() == "old"

def test_restore_symlink(tmp_path):
    real = tmp_path / "r"; real.write_text("x")
    link = tmp_path / "l"; link.symlink_to(real)
    snap = _snap_of(link); link.unlink(); link.write_text("clobbered-into-file")
    _materialize(link, snap, token="t", expected_live=fingerprint(link))
    assert link.is_symlink() and os.readlink(link) == str(real)

def test_restore_absent_over_created_dir(tmp_path):
    d = tmp_path / "made"
    absent = StateFingerprint(existed=False, type=None, content_sha256=None, mode=None, symlink_target=None)
    d.mkdir()
    _materialize(d, PathSnapshot(fp=absent, content=None), token="t", expected_live=fingerprint(d))
    assert not d.exists()   # rmdir, not unlink (which would raise)

def test_restore_halts_when_live_diverged_from_expected(tmp_path):
    p = tmp_path / "f"; p.write_text("old")
    snap = _snap_of(p)
    diverged = fingerprint(p)          # captures the "old" state as the (wrong) expectation
    p.write_text("someone-else-wrote-this")
    with pytest.raises(RollbackHalt):
        _materialize(p, snap, token="t", expected_live=diverged)   # live != expected -> refuse
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run --frozen pytest tests/test_txn_restore.py -v`
Expected: FAIL (`_materialize` has no `token`/`expected_live`; absent path uses `unlink` and raises on
a dir; no divergence guard).

- [ ] **Step 3: Reimplement `_materialize` with staged publication + expected-live guard**

```python
def _materialize(path, snap, *, token, expected_live):   # _fsync_parent defined in Task 3
    # Guard on the state rollback verified, NOT on a fresh read of the live file.
    if not matches(expected_live, path):
        raise RollbackHalt(f"{path}: live state diverged from expected post before restore")
    fp = snap.fp
    if not fp.existed:
        _remove_live(path)                 # dispatches rmdir vs unlink by lstat
        _fsync_parent(path); return
    if fp.type == "file":
        atomic_write_bytes(path, snap.content or b"", mode=WriteMode.RESTORE,
                           file_mode=fp.mode, token=token, target_pre=expected_live)
        return                              # atomic_write_bytes fsyncs parent
    # dir / symlink: build staging, then remove the verified post object and rename staging in.
    staging = staging_path_for(path, token)
    if fp.type == "dir":
        staging.mkdir(); os.chmod(staging, fp.mode)
    else:                                   # symlink
        os.symlink(fp.symlink_target, staging)
    _remove_live(path)                      # post object was just verified above
    _rename_noreplace(staging, path)        # dst now absent -> atomic no-clobber (dirs have no link fallback)
    _fsync_parent(path)
```

The remove→rename window for dir/symlink is covered on restart by Task 7's reconciliation (a surviving
staging object + an absent/post live target is republished, not O_EXCL-failed). Keep `_remove_live`'s
existing `rmdir`/`unlink` dispatch.

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
- Produces: `reconcile_restore_staging(path, snap, *, token, expected_live: StateFingerprint) -> bool`
  — consumes a survivor per the design table (complete→publish, file-prefix→recreate,
  wrong-mode-dir→finish, foreign→halt). Returns `True` when it published a complete survivor (restore
  is done — caller returns early), `False` when it only discarded a partial (caller proceeds to build
  fresh staging). Needs `expected_live` to decide publish-vs-halt: a complete survivor is only
  published when the live target still matches `expected_live`.
- Consumes: `classify_staging` (extended to accept bytes), `matches`, `RollbackHalt`.

Extend `classify_staging` to accept the restore preimage as **bytes** (its current signature is
`postimage: str` and it `.encode()`s internally; restore compares against `snap.content: bytes`).
Change the signature to `postimage: str | bytes` and normalize once:
`want = postimage.encode("utf-8") if isinstance(postimage, str) else postimage`. Existing str callers
are unaffected.

- [ ] **Step 1: Write the failing test**

```python
def test_reconcile_completes_survivor_then_converges(tmp_path):
    from science_tool.plan_common import _materialize, snapshot_paths, fingerprint, staging_path_for
    p = tmp_path / "f"; p.write_text("old")
    snap = snapshot_paths([p])[p]; p.write_text("new"); live = fingerprint(p)
    # simulate a kill AFTER staging written but BEFORE publish:
    staging = staging_path_for(p, "t"); staging.write_bytes(b"old")
    _materialize(p, snap, token="t", expected_live=live)   # consume the complete survivor, not O_EXCL-fail
    assert p.read_text() == "old" and not staging.exists()

def test_reconcile_halts_on_foreign_survivor(tmp_path):
    from science_tool.plan_common import (_materialize, snapshot_paths, fingerprint,
                                          staging_path_for, RollbackHalt)
    p = tmp_path / "f"; p.write_text("old")
    snap = snapshot_paths([p])[p]; p.write_text("new"); live = fingerprint(p)
    staging_path_for(p, "t").write_bytes(b"unrelated-not-a-prefix")
    with pytest.raises(RollbackHalt):
        _materialize(p, snap, token="t", expected_live=live)

def test_classify_staging_accepts_bytes(tmp_path):
    from science_tool.plan_common import classify_staging, staging_path_for
    p = tmp_path / "f"; s = staging_path_for(p, "t"); s.write_bytes(b"abc")
    assert classify_staging(s, b"abc") == "complete"
    assert classify_staging(s, b"abcdef") == "prefix"
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run --frozen pytest tests/test_txn_restore.py -k "reconcile or classify" -v`
Expected: FAIL (staging survivor makes the fresh `os.symlink`/`mkdir`/`O_EXCL` raise `FileExistsError`;
`classify_staging` rejects bytes).

- [ ] **Step 3: Implement reconciliation and call it first in `_materialize`**

```python
def reconcile_restore_staging(path, snap, *, token, expected_live) -> bool:
    staging = staging_path_for(path, token)
    if not staging.exists():
        return False
    fp = snap.fp
    if fp.existed and fp.type == "file":
        kind = classify_staging(staging, snap.content or b"")   # raises StagingError on foreign bytes
        if kind == "complete":
            if not matches(expected_live, path):
                raise RollbackHalt(f"{path}: live diverged; refusing to publish restore survivor")
            os.replace(staging, path); _fsync_parent(path)
            return True
        staging.unlink()                         # "prefix"/"absent": our own partial -> discard, recreate
        return False
    # dir / symlink survivor
    if fp.existed and fp.type == "dir" and staging.is_dir() and not staging.is_symlink():
        os.chmod(staging, fp.mode)               # finish a wrong-mode staging dir
    elif fp.existed and fp.type == "symlink" and staging.is_symlink() \
            and os.readlink(staging) == fp.symlink_target:
        pass                                     # attributable complete symlink
    else:
        raise RollbackHalt(f"{path}: unattributable restore staging survivor: {staging}")
    if not matches(expected_live, path):
        raise RollbackHalt(f"{path}: live diverged; refusing to publish restore survivor")
    _remove_live(path); _rename_noreplace(staging, path); _fsync_parent(path)
    return True
```

Then make it the first statement of `_materialize`, returning early when it converged:

```python
def _materialize(path, snap, *, token, expected_live):
    if reconcile_restore_staging(path, snap, token=token, expected_live=expected_live):
        return                                   # a complete survivor was published
    if not matches(expected_live, path):
        raise RollbackHalt(f"{path}: live state diverged from expected post before restore")
    ...                                          # (rest of Task 6 body unchanged)
```

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
- Produces: `rollback_transitions(tracker: OwnershipTracker, project_root: Path, snapshot, *,
  token: str) -> None` implementing the seven-row action table. `token` is the per-operation token;
  each path's restore staging token is `f"{token}-restore-{index}"` (transaction-unique — Global
  Constraint). Passes `expected_live=t.post` into `_materialize`.
- Consumes: `OwnershipTracker`, `_materialize`, `matches`, `RollbackHalt`.

- [ ] **Step 1: Write the failing test** (action-table rows: NOT_WRITTEN skip; WRITTEN+post restore;
  MAY_HAVE_WRITTEN+neither halt; WRITTEN+pre skip). Assert `rollback_transitions` rejects a bare list.

```python
def test_rollback_neither_halts(tmp_path):
    import hashlib
    from science_tool.plan_common import (OwnershipTracker, MutationOwnership as O, rollback_transitions,
        snapshot_paths, RollbackHalt, PathTransition, StateFingerprint)
    f = tmp_path / "x.md"; f.write_text("pre")
    pre = snapshot_paths([f])[f].fp
    post = StateFingerprint(existed=True, type="file",
        content_sha256=hashlib.sha256(b"post").hexdigest(), mode=0o644, symlink_target=None)
    t = PathTransition(role="entity-rewrite", rel_path="x.md", pre=pre, post=post, postimage="post")
    tr = OwnershipTracker([t]); tr.mark(0, O.WRITTEN)
    f.write_text("SOMETHING ELSE")  # neither pre nor post
    with pytest.raises(RollbackHalt):
        rollback_transitions(tr, tmp_path, snapshot_paths([f]), token="op")

def test_rollback_written_post_restores(tmp_path):
    import hashlib
    from science_tool.plan_common import (OwnershipTracker, MutationOwnership as O, rollback_transitions,
        snapshot_paths, PathTransition, StateFingerprint)
    f = tmp_path / "x.md"; f.write_text("pre")
    snap = snapshot_paths([f]); pre = snap[f].fp
    post_text = "post"
    post = StateFingerprint(existed=True, type="file",
        content_sha256=hashlib.sha256(post_text.encode()).hexdigest(), mode=0o644, symlink_target=None)
    t = PathTransition(role="entity-rewrite", rel_path="x.md", pre=pre, post=post, postimage=post_text)
    tr = OwnershipTracker([t]); tr.mark(0, O.WRITTEN)
    f.write_text(post_text)                       # live == post: reversible
    rollback_transitions(tr, tmp_path, snap, token="op")
    assert f.read_text() == "pre"

def test_rollback_rejects_bare_list(tmp_path):
    from science_tool.plan_common import rollback_transitions
    with pytest.raises(TypeError):
        rollback_transitions([], tmp_path, {}, token="op")
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run --frozen pytest tests/test_ownership_tracker.py -k rollback -v`
Expected: FAIL.

- [ ] **Step 3: Implement the action table over the tracker**

```python
def rollback_transitions(tracker, project_root, snapshot, *, token):
    if not isinstance(tracker, OwnershipTracker):
        raise TypeError("rollback_transitions requires an OwnershipTracker, not a bare list")
    execs = list(tracker.as_executions())
    for index in range(len(execs) - 1, -1, -1):        # reverse: dirs after their moved-in contents
        ex = execs[index]; t = ex.transition
        if ex.ownership is MutationOwnership.NOT_WRITTEN:
            continue
        path = resolve_within(project_root, t.rel_path)
        if matches(t.pre, path):
            continue                                   # already at pre (never written / already reverted)
        if not matches(t.post, path):
            raise RollbackHalt(
                f"{t.rel_path}: live matches neither pre nor post; concurrent change — refusing")
        snap = snapshot.get(path)
        if snap is None:
            raise RollbackHalt(f"no snapshot captured for {t.rel_path}; refusing to reconstruct")
        _materialize(path, snap, token=f"{token}-restore-{index}", expected_live=t.post)
```

The bare-list rejection is the first line; the seven rows are the `NOT_WRITTEN`/`pre`/`post`/`neither`
branches. `_materialize`'s own `expected_live` guard is the second line of defense against a live
change racing between the `matches(t.post, path)` check here and the restore.

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
- Produces: `move_no_clobber(src, dst, *, on_commit_dst=None, on_commit_src=None,
  _force_fallback: bool = False) -> None`. `_force_fallback` is a TEST-ONLY seam forcing the ordered
  link path even where `renameat2` exists, so the fallback's ordering is exercised on any kernel.
- Consumes: `_rename_noreplace`, `NoAtomicRename`, `_fsync_parent`.

- [ ] **Step 1: Write the failing test** — refusal; both seams on the atomic path; **and the ordered
  fallback path with its ordering** (dst durable before src unlinked).

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
    assert d.read_text() == "x" and not s.exists() and seen == ["dst", "src"]

def test_fallback_orders_dst_commit_before_src_unlink(tmp_path):
    s = tmp_path / "s"; s.write_text("x"); d = tmp_path / "d"
    order = []
    def dst(): order.append(("dst-commit", d.exists(), s.exists()))
    def src(): order.append(("src-commit", d.exists(), s.exists()))
    move_no_clobber(s, d, on_commit_dst=dst, on_commit_src=src, _force_fallback=True)
    # dst exists at dst-commit; src still present at dst-commit, gone by src-commit
    assert order == [("dst-commit", True, True), ("src-commit", True, False)]
    assert d.read_text() == "x" and not s.exists()

def test_fallback_refuses_existing_dst(tmp_path):
    s = tmp_path / "s"; s.write_text("x"); d = tmp_path / "d"; d.write_text("keep")
    with pytest.raises(FileExistsError):
        move_no_clobber(s, d, _force_fallback=True)
    assert d.read_text() == "keep" and s.exists()
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run --frozen pytest tests/test_move_no_clobber.py -v`
Expected: FAIL (undefined).

- [ ] **Step 3: Implement**

```python
def move_no_clobber(src, dst, *, on_commit_dst=None, on_commit_src=None, _force_fallback=False):
    if not _force_fallback:
        try:
            _rename_noreplace(src, dst)              # atomic: dst created and src removed in one step
            if on_commit_dst is not None: on_commit_dst()
            if on_commit_src is not None: on_commit_src()
            _fsync_parent(dst); _fsync_parent(src)
            return
        except NoAtomicRename:
            pass
    # Ordered fallback: dst made durable BEFORE src is unlinked.
    os.link(src, dst)                                # FileExistsError if dst present -> no-clobber
    if on_commit_dst is not None: on_commit_dst()
    _fsync_parent(dst)
    os.unlink(src)
    if on_commit_src is not None: on_commit_src()
    _fsync_parent(src)
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run --frozen pytest tests/test_move_no_clobber.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/science_tool/plan_common.py tests/test_move_no_clobber.py
git commit -m "feat(txn): move_no_clobber with ordered two-seam durability"
```

---

## Task 11: `staged_write` gains `on_commit`; durable seam primitives

**Files:**
- Modify: `src/science_tool/plan_common.py`
- Test: `tests/test_durable_seams.py` (new), `tests/test_plan_common.py` (staged_write on_commit)

**Interfaces:**
- Produces:
  - `staged_write(..., on_commit=None)` — the existing signature gains an `on_commit` callback fired
    at the `os.replace` linearization point, **before** the fallible parent-dir fsync. (Archive and
    supersede call `staged_write` directly, so ownership marking must live here — not only in the new
    primitives.)
  - `create_exclusive(path, text, mode, *, on_commit=None, _fault=None)`;
    `mkdir_durable(path, mode, *, token, on_commit=None, _fault=None)`;
    `unlink_durable(path, *, on_commit=None, _fault=None)`;
    `durable_replace_text(path, postimage, mode, token, *, target_pre, on_commit=None)`.
  - `_fault` is the same TEST-ONLY `Callable[[str], None]` seam pattern as `staged_write`'s: a test
    raises from it to simulate a kill at a labeled boundary.
- Consumes: `_rename_noreplace`, `NoAtomicRename`, `atomic_write_bytes`, `_fsync_parent`,
  `PreconditionRefused`.

- [ ] **Step 1: Write the failing test** — mark-at-linearization for each primitive, no-clobber dir,
  and the load-bearing case: **on_commit fires (ownership recorded) even when durability fails right
  after the linearization point.**

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

def test_create_exclusive_marks_before_a_failing_fsync(tmp_path):
    """The linearization point is the O_EXCL open; a failure in the LATER durability work must still
    leave ownership marked WRITTEN (the file exists) — proving on_commit fired before fallible I/O."""
    p = tmp_path / "e.md"; fired = []
    class _Kill(BaseException): ...
    def fault(label):
        if label == "post-linearization":
            raise _Kill()
    with pytest.raises(_Kill):
        create_exclusive(p, "body", 0o644, on_commit=lambda: fired.append(1), _fault=fault)
    assert fired == [1]          # marked despite the kill
    assert p.exists()            # the identity change happened

def test_mkdir_durable_no_clobber(tmp_path):
    d = tmp_path / "anc"; d.mkdir()   # concurrent creator got here first
    with pytest.raises(PreconditionRefused):
        mkdir_durable(d, 0o755, token="t")

def test_unlink_durable_marks(tmp_path):
    p = tmp_path / "s.md"; p.write_text("x"); fired = []
    unlink_durable(p, on_commit=lambda: fired.append(1))
    assert not p.exists() and fired == [1]
```

And in `tests/test_plan_common.py`, that `staged_write` fires `on_commit`:

```python
def test_staged_write_fires_on_commit_at_replace(tmp_path):
    from science_tool.plan_common import staged_write, fingerprint
    p = tmp_path / "idx.jsonl"; fired = []
    staged_write(p, "line\n", 0o644, "tok", target_pre=fingerprint(p),
                 on_commit=lambda: fired.append(1))
    assert p.read_text() == "line\n" and fired == [1]
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run --frozen pytest tests/test_durable_seams.py tests/test_plan_common.py -k "durable or staged_write" -v`
Expected: FAIL (undefined; `staged_write` has no `on_commit`).

- [ ] **Step 3: Implement**

- `staged_write`: add `on_commit=None`; after `os.replace(staging, target)` and before the parent-dir
  fsync, `if on_commit is not None: on_commit()`. (The `os.replace` is the linearization point; the
  dir fsync is the fallible durability work that must follow the mark.)
- `create_exclusive`: `fd = os.open(path, O_WRONLY|O_CREAT|O_EXCL, mode)` → **`on_commit()`** →
  `_fault("post-linearization")` → write → `fchmod` exact → fsync file → fsync parent. (Callback right
  after the exclusive open — Global Constraints.)
- `mkdir_durable`: mkdir staging (`staging_path_for(path, token)` dir) → `chmod` exact →
  `_rename_noreplace(staging, path)`; on `FileExistsError` → remove staging, `raise PreconditionRefused`;
  else `on_commit()` → `_fault("post-linearization")` → fsync parent. (Dirs have no link fallback; a
  `NoAtomicRename` here is a hard environment error, not a fallback.)
- `unlink_durable`: `os.unlink(path)` → `on_commit()` → `_fault("post-linearization")` → fsync parent.
- `durable_replace_text`: thin wrapper over `atomic_write_bytes(..., mode=REPLACE, on_commit=...)`
  passing `target_pre` through; `on_commit` fires at the replace.

- [ ] **Step 4: Run to verify pass**

Run: `uv run --frozen pytest tests/test_durable_seams.py tests/test_plan_common.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/science_tool/plan_common.py tests/test_durable_seams.py tests/test_plan_common.py
git commit -m "feat(txn): staged_write on_commit + durable callback-bearing seam primitives"
```

---

## Task 12: Wire archive + supersede rollback to the tracker

**Files:**
- Modify: `src/science_tool/archive_plan.py` (`apply_archive_plan`), `supersede_plan.py`
  (`apply_supersede_plan`)
- Test: `tests/test_archive_plan.py`, `tests/test_supersede_plan.py` (extend)

**Interfaces:**
- Consumes: `OwnershipTracker`, `MutationOwnership`, tracker-based `rollback_transitions`,
  `capture_and_verify`, `move_no_clobber`, `mkdir_durable`, `staged_write(..., on_commit=...)`.
- Produces: unchanged public `apply_*` signatures; internal rollback now tracker-driven; `created-dir`
  transitions are made through `mkdir_durable` and marked, so rollback reverts created ancestors.

- [ ] **Step 1: Write/extend the failing test** — an injected apply failure rolls back via the tracker
  and leaves the tree at pre-state, **including any created ancestor directory** (the finding-4 case).
  This mirrors the existing `test_kill_after_index_replacement_...` harness but raises a catchable
  `RuntimeError` (so the `except Exception` rollback path runs) instead of the `_Kill` BaseException.

```python
def test_apply_archive_rolls_back_to_pre_state_including_created_dirs(tmp_path: Path) -> None:
    _superseded(tmp_path)
    # Force a fresh ancestor: archive into a kind whose _archive/<kind>/ dir does not exist yet,
    # so the plan carries a created-dir transition. _superseded seeds a 'superseded' interpretation;
    # its archive dst is entities/_archive/interpretations/ -> a created-dir.
    plan = plan_archive(tmp_path, selection=ArchiveStatusSweep(kind="all_by_status",
                        statuses=["superseded"]), now="2026-07-18T00:00:00Z")
    created = [t for t in plan.transitions if t.role == "created-dir"]
    assert created, "test fixture must exercise at least one created-dir"
    before = _tree(tmp_path)                                   # _tree helper already in this test module

    def fault(label: str) -> None:
        if label == "index-written":
            raise RuntimeError("boom after index")             # catchable -> triggers rollback

    with pytest.raises(ArchiveApplyError):
        apply_archive_plan(tmp_path, plan, staging_token="tok", _fault=fault)

    assert _tree(tmp_path) == before                            # every move, index, AND created dir reverted
    for t in created:
        assert not (tmp_path / t.rel_path).exists()             # created ancestor removed on rollback
```

(If `test_archive_plan.py` has no `_tree` helper, add the same walk used in `test_entity_import.py`'s
`_tree`: per-path `(type, mode, sha256|symlink target|dir)`, excluding `.git` and `*.tmp`.)

- [ ] **Step 2: Run to verify it fails**

Run: `uv run --frozen pytest tests/test_archive_plan.py tests/test_supersede_plan.py -v`
Expected: FAIL (apply still calls the removed bare-list `rollback_transitions`; created dirs are bare
`mkdir` and never marked, so a created ancestor is left behind).

- [ ] **Step 3: Migrate both apply functions**

In `apply_archive_plan` (and the parallel structure in `apply_supersede_plan`):

1. Replace the `snapshot_paths(...)` + separate `matches(t.pre, ...)` pre-check loop with
   `snap = capture_and_verify(all_t, project_root)` (unique-guard + pre-drift → `PreconditionRefused`).
   Keep the abs-path map for the seams.
2. `tracker = OwnershipTracker(all_t)`; build `idx = {id(t): i for i, t in enumerate(all_t)}`.
3. `created-dir`: replace bare `mkdir`+`chmod` with
   `mkdir_durable(d, t.post.mode, token=staging_token, on_commit=lambda i=idx[id(t)]: tracker.mark(i, WRITTEN))`.
4. moves: replace `os.rename(src, dst)` + `_fsync_dir` with
   `move_no_clobber(src, dst, on_commit_dst=lambda i=idx[id(dst_t)]: tracker.mark(i, WRITTEN),
   on_commit_src=lambda i=idx[id(src_t)]: tracker.mark(i, WRITTEN))` (map each move to its
   `archive-dst`/`archive-src` transitions). Keep the `EXDEV` guard by catching it around the call.
5. index: `staged_write(..., on_commit=lambda i=idx[id(plan.index)]: tracker.mark(i, WRITTEN))`.
6. on failure: `rollback_transitions(tracker, project_root, snap, token=staging_token)`.

`WRITTEN` is `MutationOwnership.WRITTEN`.

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

- [ ] **Step 1: Write the failing test** — the behavioral oracles already in `tests/test_entity_import.py`
  are the contract the migration must preserve; they exercise partial-rewrite rollback (a referrer
  written before the failure is restored, one never reached stays untouched — `_tree == before` proves
  both), created-dir removal, mode restoration, and the sentinel/third-state guarantee. The migration
  keeps every one green **through the tracker path**. These exist verbatim (do not rewrite them —
  running them green after Step 3 is the gate):
  - `test_rollback_restores_whole_tree_after_partial_rewrite` — the contended/untouched-referrer oracle.
  - `test_rollback_removes_a_kind_directory_it_created`
  - `test_rollback_restores_a_non_default_mode`
  - `test_rollback_leaves_no_sentinel_either` — the `import-dst` mid-create third state hard-halt.
  - `test_import_rolls_back_when_the_audit_fails`

  Add one new test asserting the migration routes through `OwnershipTracker` (the bare-list path is
  gone) and that a partial failure still converges to pre-state:

```python
def test_apply_import_rolls_back_via_tracker_after_partial_rewrite(tmp_path: Path,
                                                                   monkeypatch: pytest.MonkeyPatch) -> None:
    from science_tool import entity_import as mod
    from science_tool.entity_import import apply_import
    root = _project(tmp_path)
    source = _loose(root, "doc/plans/x.md")
    for n in (1, 2, 3):
        (root / "entities" / "plans" / f"000{n}-ref.md").write_text(
            f"---\nid: plan:000{n}-ref\nkind: plan\ntitle: R{n}\nstatus: active\n"
            "related:\n- doc/plans/x.md\n---\n\nbody\n", encoding="utf-8")
    plan = plan_import(root, source, kind="plan", title="T1")
    before = _tree(root)
    real = mod.apply_reference_rewrite
    def _partial(*a: object, **k: object) -> object:
        real(*a, **k); raise RuntimeError("exploded after writing some referrers")
    monkeypatch.setattr(mod, "apply_reference_rewrite", _partial)
    with pytest.raises(RuntimeError, match="exploded"):
        apply_import(root, plan)
    assert _tree(root) == before
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run --frozen pytest tests/test_entity_import.py tests/test_cohort_import.py -v`
Expected: FAIL.

- [ ] **Step 3: Migrate apply**

Replace `_snapshot`/`_restore`/`mutated`-set bookkeeping with: `capture_and_verify(plan.transitions,
project_root)`; an `OwnershipTracker(plan.transitions)`; seams wired to `tracker.mark` (via each
primitive's `on_commit`: `create_exclusive` for `import-dst`, `mkdir_durable` per `created-dir`,
`unlink_durable` for `import-src`, `durable_replace_text` for `entity-rewrite`); on failure
`rollback_transitions(tracker, project_root, snapshot, token=staging_token)` (choose one per-apply
`staging_token`). `claim_number_in_dir` calls
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

## Task 16: Acceptance harness — observed persistent surface across all four families

**Files:**
- Create: `tests/test_write_surface_acceptance.py`; a shared tree-map helper (`tests/_fs_map.py`)
- Modify: `tests/conftest.py` (promote `_project`/`_loose` to shared fixtures, or import from the
  helper) — the four families' fixtures already live in `test_cohort_import.py`/`test_archive_plan.py`.

**Interfaces:**
- Consumes: `apply_archive_plan`, `apply_supersede_plan`, `apply_import`, `apply_cohort_import`;
  each plan's `transitions`.

**Design decision (revised):** the settled contract (audit §5) is a **before/after filesystem-map
comparison**, not syscall tracing. A tree map needs no `strace`/ptrace and therefore always runs in
CI — there is no skip path that could let the invariant silently no-op. Transient/scratch behavior is
characterized by the existing in-process `_fault` seams (also always runs), not by tracing syscalls of
an in-process callable (which is not possible without a subprocess). Syscall auditing is explicitly
out of scope for this PR.

- [ ] **Step 1: Write the harness + tests**

Two assertions per family, both always-on:
(a) **persistent surface** — `_diff(before, after) == {t.rel_path for t in transitions if t.pre != t.post}`
over a full tree map (type, mode, sha256 | symlink target | dir existence);
(b) **no scratch survives a clean run** — after a successful apply, no `*.tmp` token file and no
`.NNNN.reserving` sentinel remain anywhere under the project.

```python
# tests/test_write_surface_acceptance.py
from tests._fs_map import tree_map, diff_map, no_scratch_survivors

def test_import_persistent_surface_equals_transitions(tmp_path):
    from science_tool.entity_import import plan_import, apply_import
    root = _project(tmp_path)                        # shared fixture (see Files)
    src = _loose(root, "doc/plans/x.md", "# Title\n\nbody\n")
    plan = plan_import(root, src, kind="plan", title="Title")   # real plan_import signature
    before = tree_map(root)
    apply_import(root, plan)
    observed = diff_map(before, tree_map(root))
    assert observed == {t.rel_path for t in plan.transitions if t.pre != t.post}
    assert no_scratch_survivors(root)
```

Repeat the same two assertions for `apply_archive_plan`, `apply_supersede_plan`, and
`apply_cohort_import`, each built with that family's existing fixture (`_superseded`/`plan_archive`,
the supersede fixture, `_valid_plan`/`apply_cohort_import`). A fault-boundary characterization test
per family reuses each apply's `_fault` seam and asserts every survivor is a declared scratch shape:

```python
def test_archive_fault_survivors_are_declared_scratch(tmp_path):
    from science_tool.archive_plan import plan_archive, apply_archive_plan, ArchiveApplyError
    _superseded(tmp_path)
    plan = plan_archive(tmp_path, selection=ArchiveStatusSweep(kind="all_by_status",
                        statuses=["superseded"]), now="2026-07-18T00:00:00Z")
    class _Kill(BaseException): ...
    def fault(label):
        if label == "index-written": raise _Kill()
    with pytest.raises(_Kill):
        apply_archive_plan(tmp_path, plan, staging_token="tok", _fault=fault)
    # any surviving scratch is an attributable *.tmp for a declared staged target — never foreign debris
    for p in tmp_path.rglob("*.tmp"):
        assert any(p.name.startswith(Path(t.rel_path).name) for t in plan.transitions)
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run --frozen pytest tests/test_write_surface_acceptance.py -v`
Expected: FAIL until `tests/_fs_map.py` (`tree_map`/`diff_map`/`no_scratch_survivors`) exists.

- [ ] **Step 3: Implement the helper**

`tree_map(root)` walks the project excluding `.git`, returning `{rel_path: signature}` where signature
is `("file", mode, sha256)`, `("symlink", target)`, or `("dir", mode)`. `diff_map(before, after)`
returns the set of `rel_path`s whose signature changed, was added, or was removed. `no_scratch_survivors`
returns `True` iff no `*.tmp` and no `.*.reserving` path exists under root. All pure-Python; no tracing.

- [ ] **Step 4: Run to verify pass**

Run: `uv run --frozen pytest tests/test_write_surface_acceptance.py -v`
Expected: PASS — every assertion runs unconditionally (no environment-gated skips).

- [ ] **Step 5: Commit**

```bash
git add tests/test_write_surface_acceptance.py tests/_fs_map.py tests/conftest.py
git commit -m "test(txn): acceptance-time observed-surface harness (all four families)"
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
  `PreconditionRefused`, `BlobMismatch`, `BoundaryError`, `NoAtomicRename`, `move_no_clobber`,
  `_publish_no_clobber`, `create_exclusive`, `mkdir_durable`, `unlink_durable`, `durable_replace_text`,
  `atomic_write_bytes`, `capture_and_verify`, `reconcile_restore_staging`, `_materialize` (now
  `*, token, expected_live`), `rollback_transitions` (now `*, token`) are spelled identically across
  tasks and carry a single signature each.
- **No placeholders:** every code step carries real, runnable code and every test is concrete.
  The three formerly-prose steps (T12/T15 rollback tests, T16 harness) now contain full test bodies
  built on the repo's real fixtures (`_project`, `_loose`, `_valid_plan`, `_superseded`, `plan_import`,
  `plan_archive`) and real oracle test names verified present in `test_entity_import.py` /
  `test_archive_plan.py`. The only implementer-supplied code is the `tree_map`/`diff_map` helper body
  in T16, which is fully specified in prose (T16 Step 3). No `_scaffold`, no `...` in production code.
- **Every review finding closed:** F1 restore-authority (expected_live threaded T6/T7/T9 + Global
  Constraint); F2 red/green (T1 injected race, T2 existing roles + `import hashlib` + `BoundaryError`,
  T3 REPLACE-only, T4 `file_mode`, T5 real RESTORE red); F3 link durability (`_publish_no_clobber` /
  move fallback, dst durable before src unlink); F4 created-dir ownership + `staged_write.on_commit`
  (T11/T12); F5 restore interfaces (concrete `reconcile_restore_staging`/`_materialize`, `classify_staging`
  bytes, per-op token); F6 load-bearing tests (T10 fallback-ordering, T11 post-linearization fault,
  T12/T15 concrete, T16 always-on tree-map, strace dropped).

## Execution handoff

Plan complete and saved to
`docs/plans/2026-07-20-txn-substrate-convergence-implementation.md`. Two execution options:

1. **Subagent-Driven (recommended)** — a fresh implementer subagent per task, task review between
   tasks, broad whole-branch review at the end. Best fit here: the tasks are mostly independent and
   the substrate is safety-critical, so per-task review earns its cost.
2. **Inline Execution** — execute tasks in this session with checkpoints.

Which approach?

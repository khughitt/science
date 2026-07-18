from __future__ import annotations

import hashlib
import hmac
import os
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Callable, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class UnsupportedPathType(RuntimeError):
    pass


class StateFingerprint(BaseModel):
    model_config = ConfigDict(extra="forbid")
    existed: bool
    type: Literal["file", "dir", "symlink"] | None
    content_sha256: str | None
    mode: int | None
    symlink_target: str | None

    @model_validator(mode="after")
    def _coherent(self) -> StateFingerprint:
        if not self.existed:
            if any(v is not None for v in
                   (self.type, self.content_sha256, self.mode, self.symlink_target)):
                raise ValueError("absent fingerprint must carry all attributes None")
            return self
        if self.type is None:
            raise ValueError("present fingerprint requires a type")
        if self.mode is None:
            raise ValueError("present fingerprint requires a mode")
        if self.type == "file":
            if self.content_sha256 is None or self.symlink_target is not None:
                raise ValueError("file fingerprint needs content_sha256 and no symlink_target")
        elif self.type == "dir":
            if self.content_sha256 is not None or self.symlink_target is not None:
                raise ValueError("dir fingerprint carries neither content nor symlink_target")
        else:  # symlink
            if self.symlink_target is None or self.content_sha256 is not None:
                raise ValueError("symlink fingerprint needs symlink_target and no content_sha256")
        return self


def fingerprint(path: Path) -> StateFingerprint:
    try:
        st = os.lstat(path)
    except FileNotFoundError:
        return StateFingerprint(existed=False, type=None, content_sha256=None,
                                mode=None, symlink_target=None)
    mode = stat.S_IMODE(st.st_mode)
    if stat.S_ISLNK(st.st_mode):
        return StateFingerprint(existed=True, type="symlink", content_sha256=None,
                                mode=mode, symlink_target=os.readlink(path))
    if stat.S_ISDIR(st.st_mode):
        return StateFingerprint(existed=True, type="dir", content_sha256=None,
                                mode=mode, symlink_target=None)
    if not stat.S_ISREG(st.st_mode):
        # A FIFO, socket, or device: fail early -- read_bytes() on a FIFO blocks forever,
        # and none of these are things this transaction machinery ever legitimately touches.
        raise UnsupportedPathType(
            f"unsupported filesystem object at {path}: not a regular file, directory, or symlink"
        )
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    return StateFingerprint(existed=True, type="file", content_sha256=sha,
                            mode=mode, symlink_target=None)


def matches(fp: StateFingerprint, path: Path) -> bool:
    return fingerprint(path) == fp


_STAGED_ROLES = {"entity-rewrite", "archive-index"}


class PathTransition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    role: Literal["entity-rewrite", "archive-src", "archive-dst", "archive-index", "created-dir"]
    rel_path: str
    pre: StateFingerprint
    post: StateFingerprint
    postimage: str | None = None

    @model_validator(mode="after")
    def _coherent(self) -> "PathTransition":
        if self.role in _STAGED_ROLES:
            if self.postimage is None:
                raise ValueError(f"{self.role} requires a postimage")
            if not (self.post.existed and self.post.type == "file"):
                raise ValueError(f"{self.role} post must be an existing file")
            want = hashlib.sha256(self.postimage.encode("utf-8")).hexdigest()
            if self.post.content_sha256 != want:
                raise ValueError("post.content_sha256 does not match sha256(postimage)")
        else:
            if self.postimage is not None:
                raise ValueError(f"{self.role} must not carry a postimage")
        if self.role == "archive-src" and self.post.existed:
            raise ValueError("archive-src post must be absent (the source is moved away)")
        if self.role in {"archive-dst", "created-dir"} and self.pre.existed:
            raise ValueError(f"{self.role} pre must be absent (it is created)")
        if self.role == "created-dir" and self.post.type != "dir":
            raise ValueError("created-dir post must be a directory")
        return self


def _canonical_nonempty(values: list[str]) -> list[str]:
    if not values:
        raise ValueError("explicit selection list must be non-empty")
    if len(set(values)) != len(values):
        raise ValueError("explicit selection list must be unique")
    if list(values) != sorted(values):
        raise ValueError("explicit selection list must be canonically (sorted) ordered")
    return values


class ArchiveStatusSweep(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["all_by_status"]
    statuses: list[str]

    @field_validator("statuses")
    @classmethod
    def _v(cls, v: list[str]) -> list[str]:
        return _canonical_nonempty(v)


class ExplicitArchiveIds(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["explicit_ids"]
    ids: list[str]
    allowed_statuses: list[str]

    @field_validator("ids", "allowed_statuses")
    @classmethod
    def _v(cls, v: list[str]) -> list[str]:
        return _canonical_nonempty(v)


class AllSupersessionMembers(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["all"]


class ExplicitSupersessionIds(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["explicit_ids"]
    ids: list[str]

    @field_validator("ids")
    @classmethod
    def _v(cls, v: list[str]) -> list[str]:
        return _canonical_nonempty(v)


ArchiveSelection = Annotated[ArchiveStatusSweep | ExplicitArchiveIds, Field(discriminator="kind")]
SupersedeSelection = Annotated[AllSupersessionMembers | ExplicitSupersessionIds, Field(discriminator="kind")]


class EnvelopeError(RuntimeError):
    pass


def read_plan_bytes(path: Path) -> bytes:
    """Read the plan file EXACTLY once; callers hash and parse this same buffer."""
    return path.read_bytes()


def plan_sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def verify_envelope(raw: bytes, expected_sha256: str) -> None:
    actual = plan_sha256(raw)
    if not hmac.compare_digest(actual, expected_sha256):  # constant-time; hashlib has no compare_digest
        raise EnvelopeError(
            "plan bytes do not match --expected-plan-sha256 (approval envelope); "
            "the saved plan was not the one approved"
        )


class StagingError(RuntimeError):
    pass


def staging_path_for(target: Path, token: str) -> Path:
    return target.with_name(f"{target.name}.{token}.tmp")


def staged_write(target: Path, postimage: str, mode: int, token: str, *,
                 target_pre: "StateFingerprint",
                 _fault: Callable[[str], None] | None = None) -> None:
    # `_fault` is a TEST-ONLY seam: a test raises a `BaseException` from it to simulate a process
    # kill mid-staging. Because it is a BaseException, the `except Exception` cleanup below does NOT
    # run — the partial `.tmp` survives, exactly as an uncaught SIGKILL would leave it, so the kill
    # test can assert the survivor is an attributable byte-prefix of the postimage (design §3.4).
    staging = staging_path_for(target, token)
    data = postimage.encode("utf-8")
    try:
        fd = os.open(staging, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    except FileExistsError as exc:
        raise StagingError(f"staging path already exists: {staging}") from exc
    try:
        with os.fdopen(fd, "wb") as fh:
            if _fault is not None and len(data) > 1:
                # TEST SEAM: land a STRICT, non-empty prefix on disk (flushed + fsync'd), then simulate
                # a kill BEFORE the rest is written. A BaseException from `_fault` unwinds the `with`
                # (flushing an already-empty buffer), so the survivor is exactly the prefix — a genuine
                # partial, shorter than `data`, never the complete file. If `_fault` does NOT raise, the
                # remaining bytes are written, so the primitive is never left corrupt by a no-op seam.
                half = len(data) // 2
                fh.write(data[:half])
                fh.flush()
                os.fsync(fh.fileno())
                _fault("mid-write")
                fh.write(data[half:])
            else:
                fh.write(data)
            fh.flush()
            os.fchmod(fh.fileno(), mode)  # O_EXCL creation mode is umask-masked; force exact bits
            os.fsync(fh.fileno())         # ...and fsync AFTER the mode is set, on the same fd
        os.replace(staging, target)
        dir_fd = os.open(target.parent, os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    except Exception:
        # Attribution-aware cleanup (design §3.3/§3.4): remove a survivor ONLY when BOTH hold —
        # (1) it is our own O_EXCL-created partial (a byte-prefix of the intended postimage), AND
        # (2) the persistent target is still attributable to this op (unchanged from `target_pre`).
        # A non-prefix survivor, or a target a concurrent writer changed, is interference: refuse to
        # delete our staged bytes and surface the anomaly rather than erase recovery evidence. (A kill
        # via `_fault` is a BaseException and skips this handler entirely, so the partial .tmp is
        # preserved for classification.)
        if staging.exists():
            survivor = staging.read_bytes()
            if not data.startswith(survivor):
                raise StagingError(
                    f"staging survivor is not an attributable prefix, not removing: {staging}")
            if not matches(target_pre, target):
                raise StagingError(
                    f"target changed concurrently during staging; preserving survivor as evidence: {staging}")
            staging.unlink()  # our own partial (or complete) write AND target still ours; safe to remove
        raise


def classify_staging(staging: Path, postimage: str) -> Literal["absent", "prefix", "complete"]:
    if not staging.exists():
        return "absent"
    data = staging.read_bytes()
    want = postimage.encode("utf-8")
    if data == want:
        return "complete"
    if want.startswith(data):
        return "prefix"
    raise StagingError(f"staging survivor is not a prefix of the postimage: {staging}")


class RollbackHalt(RuntimeError):
    pass


class PathEscape(RuntimeError):
    pass


class SurfaceMismatch(RuntimeError):
    pass


@dataclass(frozen=True)
class PathSnapshot:
    fp: StateFingerprint
    content: bytes | None  # regular-file bytes only; None for absent/dir/symlink


def snapshot_paths(paths: list[Path]) -> dict[Path, PathSnapshot]:
    """Capture COMPLETE pre-state: existence, type, mode, symlink target, and (for regular
    files) the bytes. `bytes | None` alone conflated absent with directory and dropped mode
    and symlink identity, so rollback could not faithfully reconstruct the tree."""
    snap: dict[Path, PathSnapshot] = {}
    for p in paths:
        fp = fingerprint(p)
        content = p.read_bytes() if fp.existed and fp.type == "file" else None
        snap[p] = PathSnapshot(fp=fp, content=content)
    return snap


def _remove_live(path: Path) -> None:
    try:
        st = os.lstat(path)
    except FileNotFoundError:
        return
    if stat.S_ISDIR(st.st_mode):
        os.rmdir(path)  # created dirs are empty by the time we reverse-process them
    else:
        os.unlink(path)


def _materialize(path: Path, snap: PathSnapshot) -> None:
    _remove_live(path)
    fp = snap.fp
    if not fp.existed:
        return
    if fp.type == "file":
        assert fp.mode is not None  # a present file fingerprint always carries its exact mode
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, fp.mode)
        with os.fdopen(fd, "wb") as fh:
            fh.write(snap.content or b"")
            fh.flush()
            os.fchmod(fh.fileno(), fp.mode)  # exact bits, incl. 0o000 — an `or 0o644` fallback corrupts mode 0
            os.fsync(fh.fileno())
    elif fp.type == "dir":
        assert fp.mode is not None  # a present dir fingerprint always carries its exact mode
        path.mkdir(parents=False, exist_ok=True)
        os.chmod(path, fp.mode)  # exact bits, incl. 0o000 — no `or 0o755` fallback
    else:  # symlink
        os.symlink(fp.symlink_target, path)


def rollback_transitions(
    transitions: list[PathTransition], project_root: Path, snapshot: dict[Path, PathSnapshot]
) -> None:
    for t in reversed(transitions):  # dirs removed only after their moved-in contents revert
        path = resolve_within(project_root, t.rel_path)
        if matches(t.pre, path):
            continue  # never got written, or already reverted
        if not matches(t.post, path):
            raise RollbackHalt(
                f"live state of {t.rel_path} matches neither pre nor post; "
                "a concurrent change occurred — refusing to clobber"
            )
        snap = snapshot.get(path)
        if snap is None:
            # No captured pre-state for a path we are asked to revert -> reconstructing from `pre`
            # alone would write an EMPTY file when bytes are unavailable. That is data loss, so halt.
            raise RollbackHalt(f"no snapshot captured for {t.rel_path}; refusing to reconstruct")
        _materialize(path, snap)


def resolve_within(project_root: Path, rel_path: str) -> Path:
    """Resolve rel_path under project_root, refusing absolute paths, `..` escape, non-canonical
    spellings, AND symlink-ancestor escape. Called for EVERY declared path before filesystem
    access. Lexical checks alone are not enough: if `entities/` were a symlink pointing outside
    the project, a lexically-clean `entities/x.md` would still write out of the corpus — so we
    `.resolve()` the candidate (following symlinks in the existing ancestor chain) and confirm the
    physical target is contained, exactly as the import boundary does (`entity_import.py:486`)."""
    if (
        rel_path == ""
        or Path(rel_path).is_absolute()
        or rel_path != os.path.normpath(rel_path)
        or rel_path.split("/", 1)[0] == ".."
    ):
        raise PathEscape(f"non-canonical or escaping rel_path: {rel_path!r}")
    root = project_root.resolve()
    candidate = (root / rel_path).resolve()  # follows symlinks in the existing prefix
    if candidate != root and not candidate.is_relative_to(root):
        raise PathEscape(f"rel_path escapes project root (symlink or traversal): {rel_path!r}")
    return candidate


def _surface_key(t: PathTransition) -> tuple[str, str, str, str, str | None]:
    return (t.role, t.rel_path, t.pre.model_dump_json(), t.post.model_dump_json(), t.postimage)


def assert_same_surface(
    declared: list[PathTransition], expected: list[PathTransition]
) -> None:
    if sorted(map(_surface_key, declared)) != sorted(map(_surface_key, expected)):
        raise SurfaceMismatch(
            "declared transition surface differs from the freshly derived surface"
        )


def assert_staging_unique(project_root: Path, staged_targets: list[Path], token: str) -> None:
    root = project_root.resolve()
    staging = [staging_path_for(t, token) for t in staged_targets]
    if len(set(staging)) != len(staging):
        raise StagingError("staging path collision among staged writes")
    for s in staging:
        normalized = Path(os.path.normpath(s))
        if root not in normalized.parents:
            raise StagingError(f"staging path escapes project root: {s}")

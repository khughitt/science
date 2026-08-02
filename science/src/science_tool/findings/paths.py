"""Anchored filesystem primitives -- the only way this package touches disk.

The organising idea: **a validated pathname is not a validated file.** Walking the
components of `doc/audits/cases/x.md` and then calling `open()` on that string
resolves every component a SECOND time, and anything swapped in between is what
actually gets opened. So the walk here does not return a name to be re-resolved; it
returns a *directory descriptor*, and every subsequent read, write, listing, lock,
and rename happens through it with `dir_fd=`. The kernel then operates inside the
directory the walk verified, whatever that pathname now refers to.

Seven concrete failures this shape prevents, each reproduced before being written down:

1. **Partial symlink checks.** `path.is_symlink()` on a leaf says nothing about
   `doc/` or `doc/audits/`. `_walk_dirs` opens EVERY component `O_NOFOLLOW`.
2. **Deciding absence before walking.** `lstat` on a full pathname follows every
   component but the last, so a symlinked `doc/audits` whose target lacks `cases/`
   raises `FileNotFoundError` -- and a caller reading that as "no cases" reports
   clean about a store that was redirected. Absence is decided ONLY by the walk.
3. **Mutating before validating.** `Path.mkdir(parents=True)` follows links and
   creates directories in the target before any check runs. `_walk_dirs(create=True)`
   makes one component at a time and stops AT a link having created nothing beyond it.
4. **`O_TRUNC` through a hard link.** `O_NOFOLLOW` says nothing about hard links: a
   planted `.ingest.lock` or predictable temp name that is a second link to a real
   file gets that file truncated. Temp files are created `O_EXCL`; the lock is opened
   WITHOUT `O_TRUNC` and then `fstat`ed. Neither ever truncates anything.
5. **Blocking and non-file objects.** A FIFO planted under a report or case name makes
   a plain `O_RDONLY` hang forever. Reads use `O_NONBLOCK` and then require
   `S_ISREG`, so a FIFO, device, or directory is refused rather than waited on.
6. **An anchored name that is not a name.** `openat` resolves its argument relative to
   the descriptor, so `../outside.txt` walks straight back out and the anchoring
   guarantee evaporates. Every `*_at` operation puts its argument through
   `_leaf_name` first.
7. **Resolving and reopening the project root.** A root pathname can be replaced by a
   different real directory after `resolve()` but before `open()`. Root capture starts
   from a held `/` descriptor and opens every lexical component exactly once with
   `O_NOFOLLOW`; later swaps cannot redirect the captured descriptor.
"""

from __future__ import annotations

import os
import stat
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Literal


class PathSafetyError(ValueError):
    """A path escapes the project, passes through a link, or is not a regular file."""


class PathExistsError(PathSafetyError):
    """An exclusive create found an entry already there.

    Distinct so a caller can retry on THIS and only this. `except PathSafetyError`
    around an exclusive create would also swallow a symlinked or unreachable
    directory and "recover" from it by deleting a name.
    """


def _leaf_name(name: str) -> str:
    """One entry INSIDE the anchored directory -- never a path.

    `openat` resolves its name relative to the descriptor, so `../outside.txt` walks
    straight back out. A `*_at` primitive that accepted separators would not be
    anchored at all: its "inside the anchored directory" guarantee would be a comment
    rather than a property.
    """
    if not name or name in (".", ".."):
        raise PathSafetyError(f"{name!r} does not name an entry")
    if "/" in name or "\\" in name or "\0" in name:
        raise PathSafetyError(
            f"{name!r} must name ONE entry inside the anchored directory, not a path"
        )
    return name


def _dir_segments(rel_dir: str) -> list[str]:
    """The validated components of a project-relative DIRECTORY path.

    `..` is REFUSED, never collapsed: collapsing `a/../b` lexically answers a question
    about the filesystem (what is `a`?) with string arithmetic. The empty string is
    legal here and names the project root itself.
    """
    candidate = rel_dir.replace("\\", "/")
    if candidate.startswith("/"):
        raise PathSafetyError(f"path must be project-relative, got {rel_dir!r}")
    parts = [s for s in candidate.split("/") if s not in ("", ".")]
    if any(segment == ".." for segment in parts):
        raise PathSafetyError(f"path contains a `..` segment: {rel_dir!r}")
    return parts


def _segments(rel_path: str) -> list[str]:
    """As `_dir_segments`, but the path must name something."""
    parts = _dir_segments(rel_path)
    if not parts:
        raise PathSafetyError(f"path names no file, got {rel_path!r}")
    return parts


def _absolute_project_root(project_root: Path) -> Path:
    """Return a normalized absolute spelling without touching the filesystem."""
    spelling = os.fspath(project_root)
    if "\0" in spelling:
        raise PathSafetyError("project root must be NUL-free")
    if ".." in project_root.parts:
        raise PathSafetyError(
            f"project root contains a `..` segment: {project_root}"
        )
    try:
        root = project_root if project_root.is_absolute() else Path.cwd() / project_root
    except OSError as exc:
        raise PathSafetyError(f"could not resolve project root {project_root}: {exc}") from exc
    if root.anchor != os.sep:
        raise PathSafetyError(
            f"project root must have the single POSIX root anchor {os.sep!r}: {root}"
        )
    return root


def _open_project_root(project_root: Path) -> tuple[Path, int]:
    """Capture the absolute lexical root through one descriptor-anchored walk."""
    root = _absolute_project_root(project_root)
    try:
        descriptor = open_dir_anchored(root)
    except PathSafetyError as exc:
        raise PathSafetyError(f"could not open project root {root}: {exc}") from exc
    return root, descriptor


def open_dir_anchored(directory: Path, *, create: bool = False) -> int:
    """Open an absolute directory one component at a time, following no link.

    Makes no containment claim. With ``create=True``, each missing component is made inside the
    already-captured parent, so creation stops at a link without mutating its target.
    """
    if not directory.is_absolute():
        raise PathSafetyError(f"{directory} must be absolute to be anchored")
    if ".." in directory.parts:
        raise PathSafetyError(f"{directory} contains a `..` segment")
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    try:
        parent_fd = os.open(os.sep, flags)
    except OSError as exc:
        raise PathSafetyError(f"could not open the filesystem root: {exc}") from exc

    walked = Path(os.sep)
    try:
        for segment in directory.parts[1:]:
            walked = walked / segment
            name = _leaf_name(segment)
            if create:
                try:
                    os.mkdir(name, mode=0o755, dir_fd=parent_fd)
                except FileExistsError:
                    pass
                except OSError as exc:
                    raise PathSafetyError(f"could not create {walked}: {exc}") from exc
            try:
                child_fd = os.open(name, flags, dir_fd=parent_fd)
            except OSError as exc:
                raise PathSafetyError(
                    f"{directory} has a missing, inaccessible, symlink, or "
                    f"non-directory component at {walked}: {exc}"
                ) from exc
            os.close(parent_fd)
            parent_fd = child_fd
    except BaseException:
        os.close(parent_fd)
        raise
    return parent_fd


def _walk_dirs_with_root(
    project_root: Path,
    segments: list[str],
    *,
    create: bool,
) -> tuple[Path, int]:
    """Capture once, then return the lexical root and walked directory descriptor.

    Raises `FileNotFoundError` when a component is genuinely absent and
    `PathSafetyError` when one is a link or not a directory. Callers MUST tell these
    apart: the first may legitimately mean "nothing stored yet", the second never does.

    A project root that cannot be opened is a `PathSafetyError`, deliberately NOT a
    `FileNotFoundError`: "the project does not exist" must never be reachable through
    the same branch as "the project has no cases yet".
    """
    root, parent_fd = _open_project_root(project_root)
    walked = root
    try:
        for segment in segments:
            walked = walked / segment
            if create:
                try:
                    os.mkdir(segment, mode=0o755, dir_fd=parent_fd)
                except FileExistsError:
                    pass  # may be a real directory -- the reopen below decides
                except OSError as exc:
                    raise PathSafetyError(f"could not create {walked}: {exc}") from exc
            try:
                child_fd = os.open(
                    segment,
                    os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                    dir_fd=parent_fd,
                )
            except FileNotFoundError:
                raise  # genuine absence -- NOT a safety failure, and not conflated
            except OSError as exc:
                raise PathSafetyError(
                    f"{walked} is a symlink or not a directory; every component of "
                    f"{'/'.join(segments)!r} must be a real directory inside the "
                    f"project ({exc})"
                ) from exc
            os.close(parent_fd)
            parent_fd = child_fd
    except BaseException:
        os.close(parent_fd)
        raise
    return root, parent_fd


def _walk_dirs(project_root: Path, segments: list[str], *, create: bool) -> int:
    """Open the directory one component at a time and return its descriptor."""
    _root, descriptor = _walk_dirs_with_root(
        project_root,
        segments,
        create=create,
    )
    return descriptor


@contextmanager
def open_dir_inside(
    project_root: Path, rel_dir: str, *, create: bool = False
) -> Iterator[int]:
    """Yield a descriptor for `rel_dir`, held open for the whole operation."""
    descriptor = _walk_dirs(project_root, _dir_segments(rel_dir), create=create)
    try:
        yield descriptor
    finally:
        active = sys.exception()
        try:
            os.close(descriptor)
        except OSError as exc:
            message = f"could not close directory descriptor for {rel_dir!r}: {exc}"
            if active is None:
                raise PathSafetyError(message) from exc
            BaseException.add_note(active, message)


@contextmanager
def open_dir_inside_if_present(
    project_root: Path, rel_dir: str
) -> Iterator[int | None]:
    """As `open_dir_inside`, but yields `None` when the directory is GENUINELY absent.

    ONE walk answers both questions. A separate `exists()` helper followed by an open
    is two walks of the same name, and the name can refer to two different real
    directories across them -- reopening the exact gap the descriptor exists to close.
    That is why there is no `dir_exists_inside`: presence and access are the same
    question, so they get one answer.

    `None` means a component was genuinely missing. A link or non-directory at any
    component raises instead, because "redirected" is not "empty".
    """
    try:
        descriptor = _walk_dirs(project_root, _dir_segments(rel_dir), create=False)
    except FileNotFoundError:
        yield None
        return
    try:
        yield descriptor
    finally:
        os.close(descriptor)


def mkdir_inside(project_root: Path, rel_dir: str) -> Path:
    """Create every component of `rel_dir`, never traversing or creating a link."""
    segments = _dir_segments(rel_dir)
    root, descriptor = _walk_dirs_with_root(project_root, segments, create=True)
    os.close(descriptor)
    return root.joinpath(*segments)


def resolve_inside(project_root: Path, rel_path: str) -> Path:
    """Validate a path's components and return the name. **Check-only.**

    Used where a path is being *judged* rather than opened -- the `PathSubject` and
    `LocationEvidence` entries of an incoming report. It must NOT be used to obtain a
    name for a subsequent read or write: that is precisely the check/use gap the
    directory descriptors above exist to close. The leaf need not exist.
    """
    segments = _segments(rel_path)
    try:
        root, parent_fd = _walk_dirs_with_root(
            project_root,
            segments[:-1],
            create=False,
        )
    except FileNotFoundError as exc:
        raise PathSafetyError(
            f"a parent of {rel_path!r} does not exist inside the project"
        ) from exc
    try:
        leaf = _leaf_name(segments[-1])
        try:
            leaf_stat = os.lstat(leaf, dir_fd=parent_fd)
        except FileNotFoundError:
            pass  # a genuinely absent leaf is safe to name
        except OSError as exc:
            raise PathSafetyError(f"could not inspect {rel_path!r}: {exc}") from exc
        else:
            if stat.S_ISLNK(leaf_stat.st_mode):
                raise PathSafetyError(
                    f"{root.joinpath(*segments)} is a symlink; every component of "
                    f"{rel_path!r} must be a real entry inside the project"
                )
    finally:
        os.close(parent_fd)
    return root.joinpath(*segments)


def project_relative(project_root: Path, path: Path) -> str:
    """The project-relative spelling of an absolute-or-relative `path`, or refuse.

    `path` is NOT resolved: resolving would follow the very links this refuses, and a
    symlinked report would silently be read as its target.
    """
    root = _absolute_project_root(project_root)
    candidate = path if path.is_absolute() else (project_root / path)
    if ".." in candidate.parts:
        raise PathSafetyError(f"path contains a `..` segment: {path}")
    try:
        normalized = candidate if candidate.is_absolute() else Path.cwd() / candidate
    except OSError as exc:
        raise PathSafetyError(f"could not make {path} absolute: {exc}") from exc
    try:
        return normalized.relative_to(root).as_posix()
    except ValueError as exc:
        raise PathSafetyError(
            f"{path} is outside the project root {project_root}"
        ) from exc


def exists_at(dir_fd: int, name: str) -> bool:
    """Is there an entry under this name inside the anchored directory?

    `lstat`, not `stat`: a DANGLING link is present under its own name, and treating
    it as absent would write straight through it.

    Anchored and leaf-validated like every other `*_at` primitive. A caller asking
    `exists_at(fd, "../elsewhere.md")` would otherwise be answered about a file
    outside the directory it holds -- and then, on `False`, write inside it.
    """
    try:
        os.lstat(_leaf_name(name), dir_fd=dir_fd)
    except FileNotFoundError:
        return False
    except OSError as exc:
        raise PathSafetyError(f"could not stat {name!r}: {exc}") from exc
    return True


def list_names_at(dir_fd: int) -> tuple[str, ...]:
    """List one anchored directory without resolving its pathname again."""
    try:
        return tuple(sorted(os.listdir(dir_fd)))
    except OSError as exc:
        raise PathSafetyError(f"could not list anchored directory: {exc}") from exc


EntryType = Literal["directory", "regular", "other"]


def entry_type_at(dir_fd: int, name: str) -> EntryType:
    """Classify one anchored entry without following a symlink.

    Symlinks are never a usable entry type for trusted ingestion: a directory
    link redirects traversal and a leaf link redirects the read. Both fail loud.
    """
    name = _leaf_name(name)
    try:
        info = os.stat(name, dir_fd=dir_fd, follow_symlinks=False)
    except OSError as exc:
        raise PathSafetyError(f"could not inspect {name!r}: {exc}") from exc
    if stat.S_ISLNK(info.st_mode):
        raise PathSafetyError(f"{name!r} is a symlink; refusing anchored traversal")
    if stat.S_ISDIR(info.st_mode):
        return "directory"
    if stat.S_ISREG(info.st_mode):
        return "regular"
    return "other"


@contextmanager
def open_child_dir_at_if_present(
    parent_fd: int,
    name: str,
) -> Iterator[int | None]:
    """Open one child directory relative to an already-verified parent.

    `None` means the name is genuinely absent. A symlink or non-directory is a
    safety failure, not an empty directory.
    """
    name = _leaf_name(name)
    try:
        descriptor = os.open(
            name,
            os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
            dir_fd=parent_fd,
        )
    except FileNotFoundError:
        yield None
        return
    except OSError as exc:
        raise PathSafetyError(
            f"{name!r} is a symlink or not a directory inside the anchored "
            f"parent: {exc}"
        ) from exc
    try:
        yield descriptor
    finally:
        os.close(descriptor)


def read_regular_file_at(dir_fd: int, name: str, max_bytes: int) -> str:
    """Read one regular file inside an ALREADY-ANCHORED directory.

    `O_NONBLOCK` so a planted FIFO cannot hang the open; `S_ISREG` so a FIFO, device,
    or directory is refused rather than read; and the `fstat` is of THIS descriptor,
    so the object that was type-checked and sized is the object that is read.

    Decoding failures are raised as `PathSafetyError` rather than `UnicodeDecodeError`
    so that malformed bytes stay inside this module's declared error channel.
    """
    name = _leaf_name(name)
    try:
        descriptor = os.open(
            name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=dir_fd
        )
    except OSError as exc:
        # ELOOP is what O_NOFOLLOW raises on a symlinked final component.
        raise PathSafetyError(
            f"could not open {name!r} without following a symlink: {exc}"
        ) from exc
    try:
        return read_regular_fd(descriptor, max_bytes)
    except PathSafetyError as exc:
        raise PathSafetyError(f"could not read {name!r}: {exc}") from exc
    finally:
        os.close(descriptor)


def open_record_at(dir_fd: int, name: str) -> int:
    """Open one existing regular file for reading and appending.

    One descriptor pins identity across a count and its later append. ``O_NOFOLLOW`` rejects a
    symlink, the regular-file check rejects blocking objects, and a one-link requirement rejects a
    hard link whose other name the caller does not own.
    """
    name = _leaf_name(name)
    try:
        descriptor = os.open(
            name,
            os.O_RDWR | os.O_APPEND | os.O_NOFOLLOW | os.O_NONBLOCK,
            dir_fd=dir_fd,
        )
    except OSError as exc:
        raise PathSafetyError(f"could not open record {name!r}: {exc}") from exc
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode):
            raise PathSafetyError(f"{name!r} is not a regular file; refusing to use it as a record")
        if info.st_nlink != 1:
            raise PathSafetyError(
                f"{name!r} has {info.st_nlink} links; a hard-linked record lets whoever planted "
                "the link choose where these bytes also land"
            )
    except BaseException:
        os.close(descriptor)
        raise
    return descriptor


def read_regular_fd(descriptor: int, max_bytes: int) -> str:
    """Read an already-open regular file from offset zero without moving its offset."""
    info = os.fstat(descriptor)
    if not stat.S_ISREG(info.st_mode):
        raise PathSafetyError("descriptor is not a regular file; refusing to read it")
    if info.st_size > max_bytes:
        raise PathSafetyError(f"{info.st_size} bytes exceeds {max_bytes}")
    data = bytearray()
    while len(data) <= max_bytes:
        chunk = os.pread(descriptor, max_bytes + 1 - len(data), len(data))
        if not chunk:
            break
        data.extend(chunk)
    if len(data) > max_bytes:
        raise PathSafetyError(f"record exceeds {max_bytes} bytes")
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PathSafetyError(f"record is not valid UTF-8: {exc}") from exc


def write_all(descriptor: int, payload: bytes) -> None:
    """Write every byte or raise if the descriptor stops making progress."""
    view = memoryview(payload)
    while view:
        try:
            written = os.write(descriptor, view)
        except OSError as exc:
            raise PathSafetyError(f"could not write {len(view)} remaining bytes: {exc}") from exc
        if written == 0:
            raise PathSafetyError("write made no progress")
        view = view[written:]


def create_regular_file_at(dir_fd: int, name: str) -> int:
    """Create a file that must NOT already exist, inside an anchored directory.

    `O_EXCL`, never `O_TRUNC`. The temp-file name is predictable, and a planted HARD
    LINK under it is not a symlink -- `O_NOFOLLOW` is silent about hard links -- so an
    `O_TRUNC` open would empty the file's other name. With `O_EXCL` the open simply
    fails unless this call created the entry itself.

    An existing entry raises `PathExistsError` specifically, so a caller may retry on
    that alone without also "recovering" from a redirected directory.
    """
    name = _leaf_name(name)
    try:
        return os.open(
            name,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o644,
            dir_fd=dir_fd,
        )
    except FileExistsError as exc:
        raise PathExistsError(f"{name!r} already exists") from exc
    except OSError as exc:
        raise PathSafetyError(f"could not create {name!r}: {exc}") from exc


def open_lock_at(dir_fd: int, name: str) -> int:
    """Open (creating if absent) a lock file, WITHOUT truncating it.

    A lock file's contents are irrelevant, which is exactly why truncating one is
    indefensible: if the name is a hard link to something that matters, `O_TRUNC`
    destroys that for no benefit whatsoever. The `fstat` then refuses anything that
    is not a regular file, so a planted FIFO cannot stand in for the lock.

    `st_nlink` must be exactly 1. Not truncating prevents the data loss, but a
    hard-linked lock is still a lock on somebody else's inode: whoever planted the
    link chooses what this project's ingestion serializes against, and can hold that
    `flock` to stall it or watch it. A lock the project does not solely own is not
    this project's lock.
    """
    name = _leaf_name(name)
    try:
        descriptor = os.open(
            name,
            os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK,
            0o644,
            dir_fd=dir_fd,
        )
    except OSError as exc:
        raise PathSafetyError(f"could not open lock {name!r}: {exc}") from exc
    try:
        try:
            info = os.fstat(descriptor)
        except OSError as exc:
            raise PathSafetyError(f"could not inspect lock {name!r}: {exc}") from exc
        if not stat.S_ISREG(info.st_mode):
            raise PathSafetyError(f"lock {name!r} is not a regular file")
        if info.st_nlink != 1:
            raise PathSafetyError(
                f"lock {name!r} has {info.st_nlink} links; a hard-linked lock lets "
                "whoever planted it choose the inode this project serializes on"
            )
    except BaseException as error:
        try:
            os.close(descriptor)
        except OSError as exc:
            BaseException.add_note(
                error, f"could not close lock {name!r} after validation failed: {exc}"
            )
        raise
    return descriptor


def unlink_at(dir_fd: int, name: str) -> None:
    """Remove one name. Never follows a link and never truncates anything."""
    try:
        os.unlink(_leaf_name(name), dir_fd=dir_fd)
    except FileNotFoundError:
        pass
    except OSError as exc:
        raise PathSafetyError(f"could not remove {name!r}: {exc}") from exc


def replace_at(dir_fd: int, source: str, target: str) -> None:
    """Atomically commit `source` over `target`, both inside the anchored directory."""
    try:
        os.replace(
            _leaf_name(source), _leaf_name(target), src_dir_fd=dir_fd, dst_dir_fd=dir_fd
        )
    except OSError as exc:
        raise PathSafetyError(
            f"could not commit {source!r} to {target!r}: {exc}"
        ) from exc


def read_inside_bounded(project_root: Path, path: Path, max_bytes: int) -> str:
    """Read a caller-supplied path: relativize, anchor the parent, then read."""
    relative = project_relative(project_root, path)
    parent, _, name = relative.rpartition("/")
    if not name:
        raise PathSafetyError(f"{path} names no file")
    with open_dir_inside(project_root, parent) as dir_fd:
        return read_regular_file_at(dir_fd, name, max_bytes)

"""Every git subprocess call the boundary tooling makes.

SOURCE UNIVERSE (design: "govern what is shareable, diagnose whatever bites"):

* Rule-text inspection (`governed_ignore_files`, `unmanaged_rules`) sees only
  TRACKED, in-worktree `.gitignore` files. `.git/info/exclude` is per-clone and
  `core.excludesFile` is machine-wide; a finding against either could not be
  fixed in the repository or seen by anyone else.
* Effect inspection (`visible_paths`, `tracked_ignored`) uses git's FULL
  effective resolution, including both of those, because it asks what actually
  happened. Such a hit is reported with its source path and never rewritten.

`git check-ignore` is NOT the reachability oracle: without `--no-index` it
reports a tracked path as un-ignored regardless of the rules, so it answers
"do the patterns match?" rather than "will git surface this file?".
`visible_paths` answers the second, and agrees with `git add .`.

All output framing is NUL-delimited: newlines are legal in git paths.
"""

from __future__ import annotations

import os
import stat
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from science_tool.boundary.config import strip_git_trailing_spaces


@dataclass(frozen=True)
class IgnoreHit:
    path: str
    source: str
    line: int
    pattern: str


@dataclass(frozen=True)
class IgnoreRule:
    source: str
    line: int
    pattern: str


@dataclass(frozen=True)
class _IndexEntry:
    mode: str
    object_name: str
    stage: str
    path: str


class BoundaryGitError(Exception):
    """A git invocation failed in a way that must not be read as 'clean'."""


def _nearest_git_marker(project_root: Path) -> Path | None:
    """Find a `.git` marker at or above the project root without following it."""
    current = project_root
    while True:
        marker = current / ".git"
        try:
            os.lstat(marker)
        except FileNotFoundError:
            pass
        except OSError as exc:
            raise BoundaryGitError(f"cannot inspect Git repository marker {marker}: {exc}") from exc
        else:
            return marker
        if current.parent == current:
            return None
        current = current.parent


def is_git_worktree(project_root: Path) -> bool:
    """Discover Git from `project_root`, distinguishing absence from corruption."""
    proc = subprocess.run(
        ["git", "-C", str(project_root), "rev-parse", "--is-inside-work-tree"],
        capture_output=True,
        check=False,
        env={**os.environ, "LC_ALL": "C"},
    )
    if proc.returncode == 0:
        answer = proc.stdout.decode("utf-8", "replace").strip()
        if answer == "true":
            return True
        raise BoundaryGitError(
            f"Git repository discovery from {project_root} returned unexpected worktree state {answer!r}"
        )

    detail = proc.stderr.decode("utf-8", "replace").strip()
    marker = _nearest_git_marker(project_root)
    if marker is not None:
        raise BoundaryGitError(
            f"Git repository discovery from {project_root} failed with marker {marker}: "
            f"git rev-parse exited {proc.returncode}: {detail}"
        )
    if proc.returncode == 128 and detail.startswith("fatal: not a git repository"):
        return False
    raise BoundaryGitError(
        f"Git repository discovery from {project_root} failed (git rev-parse exited {proc.returncode}): {detail}"
    )


def read_ignore_file(path: Path) -> str:
    """Read a regular ignore file through an identity-checked no-follow handle."""
    try:
        metadata = os.lstat(path)
    except FileNotFoundError:
        raise
    except OSError as exc:
        raise BoundaryGitError(f"cannot inspect ignore file {path}: {exc}") from exc
    if stat.S_ISLNK(metadata.st_mode):
        raise BoundaryGitError(f"cannot read ignore file {path}: source is a symlink")
    if not stat.S_ISREG(metadata.st_mode):
        raise BoundaryGitError(f"cannot read ignore file {path}: source is not a regular file")
    if not hasattr(os, "O_NOFOLLOW"):
        raise BoundaryGitError(f"cannot read ignore file {path}: platform lacks O_NOFOLLOW")

    try:
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    except OSError as exc:
        raise BoundaryGitError(f"cannot read ignore file {path} without following symlinks: {exc}") from exc
    try:
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode) or (opened.st_dev, opened.st_ino) != (metadata.st_dev, metadata.st_ino):
            raise BoundaryGitError(f"cannot read ignore file {path}: source changed during safe read")
        with os.fdopen(descriptor, "rb") as stream:
            descriptor = -1
            return stream.read().decode("utf-8", "surrogateescape")
    except OSError as exc:
        raise BoundaryGitError(f"cannot read ignore file {path}: {exc}") from exc
    finally:
        if descriptor != -1:
            os.close(descriptor)


def write_ignore_file(path: Path, text: str) -> None:
    """Write text produced by `read_ignore_file` without losing raw bytes."""
    path.write_bytes(text.encode("utf-8", "surrogateescape"))


def _physical_lines(text: str) -> list[str]:
    """Git physical lines: LF-delimited, with a terminal CR removed."""
    return [line[:-1] if line.endswith("\r") else line for line in text.split("\n")]


def _git(
    project_root: Path,
    *args: str,
    stdin: bytes | None = None,
    ok: tuple[int, ...] = (0,),
) -> bytes:
    """Run git, accepting ONLY documented return codes.

    Fails closed: 'not a git repository', a malformed invocation, or any other
    git failure must never be silently reported as an empty (clean) result.
    `check-ignore` documents 1 as "nothing matched", which is a success here.
    """
    proc = subprocess.run(
        ["git", "-C", str(project_root), *args],
        input=stdin,
        capture_output=True,
        check=False,
    )
    if proc.returncode not in ok:
        detail = proc.stderr.decode("utf-8", "replace").strip()
        raise BoundaryGitError(f"git {' '.join(args)} failed ({proc.returncode}): {detail}")
    return proc.stdout


def _git_plain(*args: str) -> None:
    """A git call with no project root -- scratch `init` and `config`.

    Same fail-closed contract as `_git`: a scratch repo that silently failed to
    initialise would make every conflict check report clean.
    """
    proc = subprocess.run(["git", *args], capture_output=True, check=False)
    if proc.returncode != 0:
        detail = proc.stderr.decode("utf-8", "replace").strip()
        raise BoundaryGitError(f"git {' '.join(args)} failed ({proc.returncode}): {detail}")


def _read_governed(project_root: Path, rel: str) -> str:
    """Read a governed `.gitignore` without following any symlink component."""
    descriptor = _open_governed(project_root, rel, missing_ok=False)
    assert descriptor is not None
    try:
        with os.fdopen(descriptor, "rb") as stream:
            return stream.read().decode("utf-8", "surrogateescape")
    except OSError as exc:
        raise BoundaryGitError(f"cannot read governed ignore file {rel}: {exc}") from exc


def _open_governed(project_root: Path, rel: str, *, missing_ok: bool) -> int | None:
    """Open a regular governed source without following symlinks.

    Missing paths and symlink components mean the indexed source is not active
    in the worktree. Other inspection failures are errors, never "not present".
    Returning an open descriptor closes the stat/open race for the final file.
    """
    parts = Path(rel).parts
    directory_flags = os.O_RDONLY | os.O_DIRECTORY
    nofollow = os.O_NOFOLLOW
    try:
        directory_fd = os.open(project_root, directory_flags)
    except OSError as exc:
        raise BoundaryGitError(f"cannot inspect governed ignore file {rel}: {exc}") from exc

    try:
        for part in parts[:-1]:
            try:
                metadata = os.stat(part, dir_fd=directory_fd, follow_symlinks=False)
            except FileNotFoundError:
                if missing_ok:
                    return None
                raise BoundaryGitError(f"cannot read governed ignore file {rel}: path disappeared")
            except OSError as exc:
                raise BoundaryGitError(f"cannot inspect governed ignore file {rel}: {exc}") from exc
            if stat.S_ISLNK(metadata.st_mode):
                if missing_ok:
                    return None
                raise BoundaryGitError(f"cannot read governed ignore file {rel}: parent is a symlink")
            if not stat.S_ISDIR(metadata.st_mode):
                raise BoundaryGitError(f"cannot inspect governed ignore file {rel}: parent is not a directory")
            try:
                child_fd = os.open(
                    part,
                    directory_flags | nofollow,
                    dir_fd=directory_fd,
                )
            except FileNotFoundError:
                if missing_ok:
                    return None
                raise BoundaryGitError(f"cannot read governed ignore file {rel}: path disappeared")
            except OSError as exc:
                raise BoundaryGitError(f"cannot inspect governed ignore file {rel}: {exc}") from exc
            os.close(directory_fd)
            directory_fd = child_fd

        name = parts[-1]
        try:
            metadata = os.stat(name, dir_fd=directory_fd, follow_symlinks=False)
        except FileNotFoundError:
            if missing_ok:
                return None
            raise BoundaryGitError(f"cannot read governed ignore file {rel}: path disappeared")
        except OSError as exc:
            raise BoundaryGitError(f"cannot inspect governed ignore file {rel}: {exc}") from exc
        if stat.S_ISLNK(metadata.st_mode):
            if missing_ok:
                return None
            raise BoundaryGitError(f"cannot read governed ignore file {rel}: source is a symlink")
        if not stat.S_ISREG(metadata.st_mode):
            raise BoundaryGitError(f"cannot inspect governed ignore file {rel}: source is not a regular file")
        try:
            return os.open(name, os.O_RDONLY | nofollow, dir_fd=directory_fd)
        except FileNotFoundError:
            if missing_ok:
                return None
            raise BoundaryGitError(f"cannot read governed ignore file {rel}: path disappeared")
        except OSError as exc:
            raise BoundaryGitError(f"cannot read governed ignore file {rel}: {exc}") from exc
    finally:
        os.close(directory_fd)


def _ignore_case(project_root: Path) -> str | None:
    """The project's effective `core.ignoreCase`, or None if unset."""
    raw = _git(
        project_root,
        "config",
        "-z",
        "--type=bool",
        "--get",
        "core.ignoreCase",
        ok=(0, 1),
    )
    value = _scalar_z(raw, label="git config core.ignoreCase output")
    if value not in {None, "true", "false"}:
        raise BoundaryGitError(f"git config returned invalid normalized core.ignoreCase value {value!r}")
    return value


def git_ignores_case(project_root: Path) -> bool:
    """Whether this worktree applies case-insensitive Git path semantics."""
    return _ignore_case(project_root) == "true"


def _split_z(payload: bytes) -> list[str]:
    """Decode a NUL-framed stream, rejecting truncation and empty records."""
    if not payload:
        return []
    if not payload.endswith(b"\0"):
        raise BoundaryGitError("malformed NUL-delimited git output: missing terminal NUL")
    chunks = payload[:-1].split(b"\0")
    if any(not chunk for chunk in chunks):
        raise BoundaryGitError("malformed NUL-delimited git output: empty field")
    return [chunk.decode("utf-8", "surrogateescape") for chunk in chunks]


def _scalar_z(payload: bytes, *, label: str) -> str | None:
    """Parse an optional scalar from a strict NUL-framed Git query."""
    values = _split_z(payload)
    if len(values) > 1:
        raise BoundaryGitError(f"{label} returned multiple values")
    return values[0] if values else None


def _index_entries(project_root: Path, *paths: str) -> list[_IndexEntry]:
    args = ["ls-files", "--stage", "-z"]
    if paths:
        args.extend(("--", *paths))
    entries: list[_IndexEntry] = []
    for record in _split_z(_git(project_root, *args)):
        header, separator, path = record.partition("\t")
        fields = header.split(" ")
        if not separator or len(fields) != 3:
            raise BoundaryGitError("malformed git ls-files --stage record")
        mode, object_name, stage = fields
        entries.append(
            _IndexEntry(
                mode=mode,
                object_name=object_name,
                stage=stage,
                path=path,
            )
        )
    return entries


def _intent_to_add_paths(project_root: Path) -> set[str]:
    """Paths Git omits from a tree because they are only intent-to-add."""
    common = ("diff", "--cached", "--name-only", "-z", "--no-renames")
    visible = set(
        _split_z(
            _git(
                project_root,
                *common,
                "--ita-visible-in-index",
                "--",
            )
        )
    )
    durable = set(
        _split_z(
            _git(
                project_root,
                *common,
                "--ita-invisible-in-index",
                "--",
            )
        )
    )
    return visible - durable


def _check_ignore_records(payload: bytes) -> list[tuple[str, int, str, str]]:
    """Parse exact four-field `check-ignore -v -z` records."""
    fields = _split_z(payload)
    if len(fields) % 4:
        raise BoundaryGitError("malformed git check-ignore output: expected four fields per record")
    records: list[tuple[str, int, str, str]] = []
    for index in range(0, len(fields), 4):
        line = fields[index + 1]
        try:
            number = int(line)
        except ValueError as exc:
            raise BoundaryGitError(f"git check-ignore returned invalid line number {line!r}") from exc
        if number < 1:
            raise BoundaryGitError(f"git check-ignore returned invalid line number {line!r}")
        records.append((fields[index], number, fields[index + 2], fields[index + 3]))
    return records


def visible_paths(project_root: Path) -> set[str]:
    """Paths git will surface: tracked, plus untracked-and-not-ignored."""
    return set(
        _split_z(
            _git(
                project_root,
                "ls-files",
                "-z",
                "--cached",
                "--others",
                "--exclude-standard",
            )
        )
    )


def indexed_paths(project_root: Path) -> list[str]:
    """Sorted repository-relative paths present in Git's index."""
    return sorted(set(_split_z(_git(project_root, "ls-files", "-z"))))


def indexed_regular_blob(project_root: Path, path: str) -> bytes | None:
    """Return a path's sole stage-0 regular blob, or None if it is nondurable.

    Intent-to-add records carry Git's empty placeholder blob. Callers that
    require committed content must compare the returned bytes with that content;
    for a nonempty managed boundary this excludes intent-to-add without parsing
    the unstable `ls-files --debug` flag format.
    """
    entries = _index_entries(project_root, path)
    if len(entries) != 1:
        return None
    entry = entries[0]
    if entry.path != path or entry.stage != "0" or entry.mode not in {"100644", "100755"}:
        return None
    return _git(project_root, "cat-file", "blob", entry.object_name)


def tracked_ignored(project_root: Path) -> list[IgnoreHit]:
    """Tracked files that nonetheless match an ignore rule."""
    tracked = _git(project_root, "ls-files", "-z")
    tracked_paths = _split_z(tracked)
    if not tracked_paths:
        return []
    tracked_stdin = "\0".join(tracked_paths).encode("utf-8", "surrogateescape") + b"\0"
    raw = _git(
        project_root,
        "check-ignore",
        "--no-index",
        "--stdin",
        "-z",
        "-v",
        stdin=tracked_stdin,
        ok=(0, 1),
    )
    hits: list[IgnoreHit] = []
    for source, line, pattern, path in _check_ignore_records(raw):
        if pattern.startswith("!"):
            continue
        hits.append(
            IgnoreHit(
                path=path,
                source=source,
                line=line,
                pattern=pattern,
            )
        )
    return sorted(hits, key=lambda hit: hit.path)


def governed_ignore_files(project_root: Path) -> list[str]:
    """Stage-0 regular, present `.gitignore` files actually in effect."""
    by_path: dict[str, list[_IndexEntry]] = {}
    for entry in _index_entries(project_root):
        if entry.path == ".gitignore" or entry.path.endswith("/.gitignore"):
            by_path.setdefault(entry.path, []).append(entry)
    intent_to_add = _intent_to_add_paths(project_root) if by_path else set()
    governed: list[str] = []
    for path, entries in by_path.items():
        if (
            path in intent_to_add
            or len(entries) != 1
            or entries[0].stage != "0"
            or entries[0].mode not in {"100644", "100755"}
        ):
            continue
        descriptor = _open_governed(project_root, path, missing_ok=True)
        if descriptor is None:
            continue
        os.close(descriptor)
        governed.append(path)
    return sorted(governed)


def unmanaged_rules(project_root: Path) -> list[IgnoreRule]:
    """Every hand-written rule in governed files, excluding the managed block."""
    from science_tool.boundary.generate import managed_block_line_numbers

    rules: list[IgnoreRule] = []
    for rel in governed_ignore_files(project_root):
        text = _read_governed(project_root, rel)
        managed_lines = managed_block_line_numbers(text) if rel == ".gitignore" else frozenset()
        for number, raw in enumerate(_physical_lines(text), start=1):
            line = strip_git_trailing_spaces(raw)
            if number in managed_lines or not line or line.startswith("#"):
                continue
            rules.append(IgnoreRule(source=rel, line=number, pattern=line))
    return sorted(rules, key=lambda rule: (rule.source, rule.line))


def matching_unmanaged_rules(
    project_root: Path,
    paths: list[str],
) -> dict[str, list[IgnoreRule]]:
    """Return every unmanaged rule matching each path, including negations.

    A scratch repository isolates unmanaged rules from the managed block. Each
    round then peels the winning unmanaged rules away so earlier shadowed rules
    can surface. Git remains the pattern-matching engine throughout.
    """
    from science_tool.boundary.generate import managed_block_line_numbers

    if not paths:
        return {}
    governed = governed_ignore_files(project_root)
    if not governed:
        return {}

    initially_blanked: dict[str, set[int]] = {}
    sources: dict[str, list[str]] = {}
    for rel in governed:
        text = _read_governed(project_root, rel)
        lines = _physical_lines(text)
        sources[rel] = lines
        managed = set(managed_block_line_numbers(text)) if rel == ".gitignore" else set()
        initially_blanked[rel] = managed

    matches: dict[str, list[IgnoreRule]] = {}
    unique_paths = list(dict.fromkeys(paths))
    blanked_by_path = {
        path: {source: set(lines) for source, lines in initially_blanked.items()} for path in unique_paths
    }

    with tempfile.TemporaryDirectory() as tmp:
        scratch = Path(tmp) / "scratch"
        scratch.mkdir()
        _git_plain("init", "-q", "--template=", str(scratch))
        scratch_exclude = scratch / ".git" / "info" / "exclude"
        scratch_exclude.parent.mkdir(parents=True, exist_ok=True)
        write_ignore_file(scratch_exclude, "")
        empty = Path(tmp) / "empty-excludes"
        empty.write_text("")
        _git_plain("-C", str(scratch), "config", "core.excludesFile", str(empty))
        case = _ignore_case(project_root)
        if case is not None:
            _git_plain("-C", str(scratch), "config", "core.ignoreCase", case)

        active = unique_paths
        while active:
            groups: dict[tuple[tuple[str, tuple[int, ...]], ...], list[str]] = {}
            for path in active:
                state = tuple((source, tuple(sorted(lines))) for source, lines in sorted(blanked_by_path[path].items()))
                groups.setdefault(state, []).append(path)

            next_active: list[str] = []
            for group in groups.values():
                group_paths = set(group)
                group_blanked = blanked_by_path[group[0]]
                for rel, lines in sources.items():
                    rendered = [
                        "" if number in group_blanked[rel] else raw for number, raw in enumerate(lines, start=1)
                    ]
                    target = scratch / rel
                    target.parent.mkdir(parents=True, exist_ok=True)
                    write_ignore_file(target, "\n".join(rendered))

                payload = "\0".join(group).encode("utf-8", "surrogateescape") + b"\0"
                raw_out = _git(
                    scratch,
                    "check-ignore",
                    "--no-index",
                    "--stdin",
                    "-z",
                    "-v",
                    stdin=payload,
                    ok=(0, 1),
                )
                reported: set[str] = set()
                for source, number, pattern, path in _check_ignore_records(raw_out):
                    if path not in group_paths:
                        raise BoundaryGitError(f"git check-ignore returned unexpected path {path!r}")
                    if path in reported:
                        raise BoundaryGitError(f"git check-ignore returned duplicate path {path!r}")
                    reported.add(path)
                    if source not in sources:
                        raise BoundaryGitError(f"git check-ignore returned unexpected ignore source {source!r}")
                    if number < 1 or number > len(sources[source]):
                        raise BoundaryGitError(f"git check-ignore returned out-of-range line {number} for {source}")
                    if number in blanked_by_path[path][source]:
                        raise BoundaryGitError(f"git check-ignore returned an already-peeled rule {source}:{number}")
                    matches.setdefault(path, []).append(IgnoreRule(source=source, line=number, pattern=pattern))
                    blanked_by_path[path][source].add(number)
                    next_active.append(path)
            active = next_active

    for hits in matches.values():
        hits.sort(key=lambda rule: (rule.source, rule.line))
    return matches

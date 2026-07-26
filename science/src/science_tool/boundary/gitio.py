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


class BoundaryGitError(Exception):
    """A git invocation failed in a way that must not be read as 'clean'."""


def read_ignore_file(path: Path) -> str:
    """Read arbitrary rule bytes without universal-newline translation."""
    return path.read_bytes().decode("utf-8", "surrogateescape")


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
    """Read a governed `.gitignore`, failing closed, tolerating raw bytes."""
    try:
        return read_ignore_file(project_root / rel)
    except OSError as exc:
        raise BoundaryGitError(f"cannot read governed ignore file {rel}: {exc}") from exc


def _ignore_case(project_root: Path) -> str | None:
    """The project's effective `core.ignoreCase`, or None if unset."""
    raw = _git(project_root, "config", "--get", "core.ignoreCase", ok=(0, 1)).decode().strip()
    return raw or None


def _split_z(payload: bytes) -> list[str]:
    return [chunk.decode("utf-8", "surrogateescape") for chunk in payload.split(b"\0") if chunk]


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


def tracked_ignored(project_root: Path) -> list[IgnoreHit]:
    """Tracked files that nonetheless match an ignore rule."""
    tracked = _git(project_root, "ls-files", "-z")
    if not tracked:
        return []
    raw = _git(
        project_root,
        "check-ignore",
        "--no-index",
        "--stdin",
        "-z",
        "-v",
        stdin=tracked,
        ok=(0, 1),
    )
    fields = raw.split(b"\0")
    hits: list[IgnoreHit] = []
    for i in range(0, len(fields) - 3, 4):
        source, line, pattern, path = (
            field.decode("utf-8", "surrogateescape") for field in fields[i : i + 4]
        )
        if not path or pattern.startswith("!"):
            continue
        hits.append(
            IgnoreHit(
                path=path,
                source=source,
                line=int(line or 0),
                pattern=pattern,
            )
        )
    return sorted(hits, key=lambda hit: hit.path)


def governed_ignore_files(project_root: Path) -> list[str]:
    """Tracked, present, non-symlink `.gitignore` files actually in effect."""
    tracked = _split_z(_git(project_root, "ls-files", "-z"))
    named = (path for path in tracked if path == ".gitignore" or path.endswith("/.gitignore"))
    return sorted(
        path
        for path in named
        if (project_root / path).is_file() and not (project_root / path).is_symlink()
    )


def unmanaged_rules(project_root: Path) -> list[IgnoreRule]:
    """Every hand-written rule in governed files, excluding the managed block."""
    from science_tool.boundary.generate import (
        MANAGED_BEGIN,
        MANAGED_END,
        extract_managed_block,
    )

    rules: list[IgnoreRule] = []
    for rel in governed_ignore_files(project_root):
        text = _read_governed(project_root, rel)
        extract_managed_block(text)
        inside = False
        for number, raw in enumerate(_physical_lines(text), start=1):
            line = strip_git_trailing_spaces(raw)
            if MANAGED_BEGIN in raw:
                inside = True
                continue
            if MANAGED_END in raw:
                inside = False
                continue
            if inside or not line or line.startswith("#"):
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
    from science_tool.boundary.generate import (
        MANAGED_BEGIN,
        MANAGED_END,
        extract_managed_block,
    )

    if not paths:
        return {}
    governed = governed_ignore_files(project_root)
    if not governed:
        return {}

    blanked: dict[str, set[int]] = {}
    sources: dict[str, list[str]] = {}
    for rel in governed:
        text = _read_governed(project_root, rel)
        extract_managed_block(text)
        lines = _physical_lines(text)
        sources[rel] = lines
        managed: set[int] = set()
        inside = False
        for number, raw in enumerate(lines, start=1):
            if MANAGED_BEGIN in raw:
                inside = True
                managed.add(number)
                continue
            if MANAGED_END in raw:
                inside = False
                managed.add(number)
                continue
            if inside:
                managed.add(number)
        blanked[rel] = managed

    matches: dict[str, list[IgnoreRule]] = {}
    payload = "\0".join(paths).encode("utf-8", "surrogateescape") + b"\0"

    with tempfile.TemporaryDirectory() as tmp:
        scratch = Path(tmp) / "scratch"
        scratch.mkdir()
        _git_plain("init", "-q", str(scratch))
        empty = Path(tmp) / "empty-excludes"
        empty.write_text("")
        _git_plain("-C", str(scratch), "config", "core.excludesFile", str(empty))
        case = _ignore_case(project_root)
        if case is not None:
            _git_plain("-C", str(scratch), "config", "core.ignoreCase", case)

        while True:
            for rel, lines in sources.items():
                rendered = [
                    "" if number in blanked[rel] else raw
                    for number, raw in enumerate(lines, start=1)
                ]
                target = scratch / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                write_ignore_file(target, "\n".join(rendered))

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
            fields = raw_out.split(b"\0")
            newly: set[tuple[str, int]] = set()
            for i in range(0, len(fields) - 3, 4):
                source, line, pattern, path = (
                    field.decode("utf-8", "surrogateescape")
                    for field in fields[i : i + 4]
                )
                if not path or source not in blanked:
                    continue
                number = int(line or 0)
                if number in blanked[source]:
                    continue
                matches.setdefault(path, []).append(
                    IgnoreRule(source=source, line=number, pattern=pattern)
                )
                newly.add((source, number))
            if not newly:
                break
            for source, number in newly:
                blanked[source].add(number)

    for hits in matches.values():
        hits.sort(key=lambda rule: (rule.source, rule.line))
    return matches

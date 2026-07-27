"""A pre-registration must freeze its vehicle by CONTENT, not by path.

fb-2026-07-11-024 (natural-systems t830). `pre-registration:0026` locked its
vehicle as `pipeline/graph-analysis/data/graph-export.json, exported 2026-04-30,
244 models`. That path was in `.gitignore`, so the "frozen" vehicle was an
untracked build product whose content was a pure function of the working tree.
Executing the registered refresh re-ran the pipeline's first rule, regenerating
the vehicle from a catalogue that had since drifted 244 -> 248 models and
destroying the registered export irrecoverably. The 248-cohort observed
secondaries were then computed AND SEEN, making a downstream cohort decision
post-observation. Nine rounds of adversarial review did not catch it, because
nobody asked whether the named file was durable.

Freezing by path rather than by content is the flaw. Durability is mechanically
checkable, so it is checked here rather than left to review.

`data/` gets no exemption. It is gitignored by design in the standard layout,
which is precisely why it cannot by itself freeze anything: a vehicle living
there must be declared as a content-addressed dataset entity instead.
"""

from __future__ import annotations

import hashlib
import re
import subprocess
from collections.abc import Iterator
from pathlib import Path, PurePosixPath
from typing import Any

from science_tool.entities import resolve_path_policy
from science_tool.validate.checks import Check
from science_tool.validate.context import ValidateContext
from science_tool.validate.prereg_frozen import frozen_because
from science_tool.validate.result import Result, Severity

# Data-gated mode commits the decision rule before any vehicle is admissible,
# so it legitimately names none. The template section is the declaration.
_DATA_GATED_MARKER = "## Vehicle-Admissibility Gate"

_RULE_PROSE = "prereg.prose-path-nondurable"

_HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
# Captures the delimiter run so a fence is closed only by its OWN character, at
# least as long -- a `~~~` line inside a ``` block is content, not the closer.
# Indentation is capped at three spaces per CommonMark: at four it is an indented
# code block, so a 4-space ``` inside an open fence is CONTENT. An unbounded
# `^[ \t]*` closes on it and exposes the rest of the block.
_FENCE_LINE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
_INLINE_CODE = re.compile(r"`([^`\n]+)`")
# The exact grammar behind the design's 16-finding corpus survey. Anchored at
# both ends: a span containing a command, flag, argument or prose fails as a
# whole, so path-shaped arguments are never mined out of a command example. The
# closed class also excludes URLs, since `:` is not in it. It requires a `/`,
# but that is NOT sufficient to keep root-level paths out of scope -- see
# `_normalize`.
_PATH_GRAMMAR = re.compile(r"^[A-Za-z0-9_.][A-Za-z0-9_./+-]*/[A-Za-z0-9_./+-]*$")


def _result(severity: Severity, relative: str, message: str, rule: str) -> Result:
    return Result(severity, Path(relative), None, message, rule, None)


def _git_ok(root: Path, *args: str) -> bool:
    """True when git exits 0. Used for the two boolean queries below."""
    completed = subprocess.run(["git", *args], cwd=root, capture_output=True)
    return completed.returncode == 0


def _git_query(root: Path, *args: str) -> bool | None:
    """git's answer, or None when git did not answer at all.

    `_git_ok` above collapses every non-zero exit into False, which is right
    for its two callers because they act only on a positive. It is WRONG for a
    rule whose finding asserts that git demonstrably will not preserve a path:
    `check-ignore` and `ls-files --error-unmatch` both exit 128 on failure (an
    out-of-worktree path, a broken repository), and reading that as "no" would
    manufacture findings out of errors.
    """
    completed = subprocess.run(["git", *args], cwd=root, capture_output=True)
    if completed.returncode == 0:
        return True
    if completed.returncode == 1:
        return False
    return None


def _is_ignored(root: Path, relative: str) -> bool:
    return _git_ok(root, "check-ignore", "-q", "--", relative)


def _is_tracked(root: Path, relative: str) -> bool:
    return _git_ok(root, "ls-files", "--error-unmatch", "--", relative)


def _vehicle_entries(frontmatter: dict[str, Any]) -> list[Any]:
    declared = frontmatter.get("vehicles")
    if declared is None:
        return []
    if not isinstance(declared, list):
        return [declared]
    return declared


def _strip_fenced_blocks(body: str) -> str:
    """Blank every line inside a fenced code block, delimiters included.

    Tracks the OPENING delimiter, because CommonMark closes a fence only with a
    run of the SAME character, at least as long, followed by nothing but
    whitespace. Two distinct mistakes both end a block early and expose every
    path in its remainder: toggling on a `~~~` line inside a ``` block, and
    closing on ```` ```not-a-close ````. The trailing-text rule applies only
    when a block is already open -- an OPENING fence may carry an info string,
    so ```` ```python ```` must still open.
    """
    lines: list[str] = []
    opener: str | None = None
    for line in body.splitlines():
        match = _FENCE_LINE.match(line)
        if match is not None:
            marker = match.group(1)
            if opener is None:
                opener = marker
                continue
            if (
                marker[0] == opener[0]
                and len(marker) >= len(opener)
                and not line[match.end(1) :].strip()
            ):
                opener = None
                continue
            # Neither an opener nor a valid closer: content inside the block.
        lines.append("" if opener is not None else line)
    return "\n".join(lines)


def _normalize(token: str) -> str | None:
    """A slash-containing, lexically repo-relative path, or None.

    Normalization is delegated to `PurePosixPath` rather than done with string
    surgery, because the ad-hoc version is wrong in three ways that all look
    fine in isolation: stripping one leading `./` leaves `././input.parquet` as
    `./input.parquet`, turns `.//etc/passwd` into the ABSOLUTE `/etc/passwd`
    -- breaking this function's own contract -- and `rstrip('/')` leaves
    `build/./` as `build/.`. `PurePosixPath` collapses `.` segments and
    redundant separators, and knows that a leading `//` is POSIX-absolute.

    Three rejections then apply, and none is redundant:

    * absolute -- `PurePosixPath.is_absolute()` covers `/x` and `//x`.
    * `..` -- load-bearing, since `.` is in the grammar's leading character
      class, so `../secrets/x` matches the grammar and is stopped only here.
    * no `/` after normalization -- the design puts root-level paths out of
      scope, and the GRAMMAR CANNOT ENFORCE THAT: `./input.parquet` contains a
      `/` when it is matched and denotes a root-level path once normalized.
    """
    candidate = token.strip()
    if not candidate:
        return None
    pure = PurePosixPath(candidate)
    if pure.is_absolute():
        return None
    parts = [part for part in pure.parts if part != "."]
    if not parts or any(part == ".." for part in parts):
        return None
    normalized = "/".join(parts)
    if "/" not in normalized:
        return None
    return normalized


def _candidate_paths(body: str) -> list[str]:
    """Normalized repo-relative paths this document names in prose.

    HTML comments are stripped BEFORE fences: a comment may contain a fence
    marker, and opening on it would desynchronise the fence state and swallow
    the rest of the document.
    """
    text = _strip_fenced_blocks(_HTML_COMMENT.sub("", body))
    found: list[str] = []
    seen: set[str] = set()
    for span in _INLINE_CODE.findall(text):
        stripped = span.strip()
        if not _PATH_GRAMMAR.match(stripped):
            continue
        candidate = _normalize(stripped)
        if candidate is None or candidate in seen:
            continue
        seen.add(candidate)
        found.append(candidate)
    return found


@Check(section="discussion documents...", order=13)
def check_prereg_vehicles(ctx: ValidateContext) -> Iterator[Result]:
    entities_root = ctx.project_root / resolve_path_policy("pre-registration").root
    if not entities_root.is_dir():
        return
    is_repo = (ctx.project_root / ".git").exists()

    for path in sorted(entities_root.glob("*.md")):
        if not path.is_file():
            continue
        frontmatter = ctx.frontmatter(path)
        if str(frontmatter.get("kind", "")) != "pre-registration":
            continue
        relative = path.relative_to(ctx.project_root).as_posix()
        entries = _vehicle_entries(frontmatter)

        if not entries:
            freeze_reason = frozen_because(frontmatter)
            if freeze_reason is not None and _DATA_GATED_MARKER not in ctx.body(path):
                yield _result(
                    Severity.WARN,
                    relative,
                    f"{relative} is frozen ({freeze_reason}) but declares no 'vehicles:'. A "
                    f"pre-registration that names its data only in prose is frozen by path, not by "
                    f"content: declare each vehicle as 'path' + 'sha256', or state the "
                    f"'{_DATA_GATED_MARKER} (data-gated mode)' section if no vehicle is admissible yet.",
                    "prereg.vehicle-undeclared",
                )
            continue

        if not is_repo:
            yield _result(
                Severity.WARN,
                relative,
                f"{relative} declares vehicles but {ctx.project_root} is not a git repository, so "
                f"their durability cannot be verified.",
                "prereg.vehicle-unverifiable",
            )
            continue

        for entry in entries:
            yield from _check_vehicle(ctx, relative, entry)


def _check_vehicle(ctx: ValidateContext, relative: str, entry: Any) -> Iterator[Result]:
    """Report the FIRST way this vehicle fails to be frozen, if any.

    The conditions are ordered by how fundamental they are: an unresolvable or
    non-durable path makes its recorded hash moot, so reporting the hash as well
    would be noise.
    """
    if not isinstance(entry, dict) or not entry.get("path"):
        yield _result(
            Severity.ERROR,
            relative,
            f"{relative} has a 'vehicles:' entry with no 'path': {entry!r}.",
            "prereg.vehicle-uncontent-addressed",
        )
        return

    declared_path = str(entry["path"])
    digest = entry.get("sha256")
    if not digest:
        yield _result(
            Severity.ERROR,
            relative,
            f"{relative} freezes vehicle {declared_path!r} by path alone. Record its 'sha256:' — a "
            f"path names where the data was, not which data it was.",
            "prereg.vehicle-uncontent-addressed",
        )
        return

    target = ctx.project_root / declared_path
    if not target.is_file():
        yield _result(
            Severity.ERROR,
            relative,
            f"{relative} freezes vehicle {declared_path!r}, which does not exist.",
            "prereg.vehicle-missing",
        )
        return

    if _is_ignored(ctx.project_root, declared_path):
        yield _result(
            Severity.ERROR,
            relative,
            f"{relative} freezes vehicle {declared_path!r}, which is gitignored. An ignored file is "
            f"a local build product, not a frozen record: regenerating it destroys the registered "
            f"content irrecoverably. Commit it, or declare it as a content-addressed dataset entity.",
            "prereg.vehicle-gitignored",
        )
        return

    if not _is_tracked(ctx.project_root, declared_path):
        yield _result(
            Severity.ERROR,
            relative,
            f"{relative} freezes vehicle {declared_path!r}, which is not tracked by git. An "
            f"uncommitted file cannot be recovered once overwritten.",
            "prereg.vehicle-untracked",
        )
        return

    actual = hashlib.sha256(target.read_bytes()).hexdigest()
    if actual != str(digest):
        yield _result(
            Severity.ERROR,
            relative,
            f"{relative} freezes vehicle {declared_path!r} at sha256 {str(digest)[:12]}…, but the "
            f"file on disk is {actual[:12]}…. The registered content is gone even though the path "
            f"still resolves.",
            "prereg.vehicle-hash-drift",
        )

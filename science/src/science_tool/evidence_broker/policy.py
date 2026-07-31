"""Whether a request may be answered. Nothing here runs git.

Keeping the decision out of the serving module is what makes design §7's agreement table
possible: the `read` denial and the `search` exclusion are independent implementations of one
policy, and they can only be tested against each other while both are pure functions.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import StrEnum

from science_model.audit.subjects import SubjectError, normalize_project_path
from science_model.evidence_broker import SurfacePolicy


class EvidenceOp(StrEnum):
    READ = "read"
    SEARCH = "search"
    HISTORY = "history"


@dataclass(frozen=True)
class EvidenceRequest:
    """One question about the pinned tree.

    `target` is a PATH for `READ` and `HISTORY` and a PATTERN for `SEARCH`. Search is the one
    operation that never names a path, which is why its `pathspec` is separate and optional and
    why its target is never put through a path normalizer.
    """

    op: EvidenceOp
    target: str
    pathspec: str | None = None


@dataclass(frozen=True)
class Denial:
    """Two strings, for two audiences.

    `reason` is categorised and stays parent-side, for the audit. `notice` is what the requester
    sees and comes from the policy, never from this module: a specific reason confirms that the
    denied thing exists, which a blinding study cannot afford.
    """

    reason: str
    notice: str


@dataclass(frozen=True)
class Authorization:
    """The verdict AND the spelling git must use.

    Returning only a verdict is what let an earlier draft authorize one path and read another:
    `a\\b` normalizes to `a/b` and is judged as that, while git reads a file literally named
    `a\\b`. Handing the normalized value back makes the authorized spelling the only spelling
    available downstream, which is stronger than asking every caller to normalize again.
    """

    denial: Denial | None
    path: str | None = None


def _denied_by_prefix(path: str, prefix: str) -> bool:
    """Component-boundary matching. `private` denies `private` and `private/x`, not `privateer`."""
    return path == prefix or path.startswith(f"{prefix}/")


def _judge_path(raw: str, policy: SurfacePolicy) -> Authorization:
    try:
        path = normalize_project_path(raw)
    except SubjectError as exc:
        # Containment BEFORE any prefix: a prefix check alone is walked around with `..`.
        # Reported as malformed rather than denied because they are different facts -- one is
        # the requester's own error and correctable, the other is the study's boundary.
        return Authorization(denial=Denial(reason="path-malformed", notice=str(exc)))
    if any(_denied_by_prefix(path, prefix) for prefix in policy.deny_prefixes):
        return Authorization(denial=Denial(reason="path-denied", notice=policy.notice))
    return Authorization(denial=None, path=path)


def _judge_pattern(pattern: str) -> Authorization:
    """ARGV validity only, judged by the same function `subprocess` uses.

    Whether the regex compiles is git's answer to give, and an EMPTY pattern is NOT refused here:
    an empty ERE is valid and matches every line, which is a legitimate request measured to exit
    0 with every file listed. Refusing it would deny a real query on a guess about intent.

    What genuinely cannot cross the argv boundary halts the run instead of being refused, which
    is the wrong disposition for the requester's own input (§6 calls it retryable). Two cases,
    both measured: a NUL raises `ValueError`, and a lone high surrogate such as `\\ud800` raises
    `UnicodeEncodeError` -- a `ValueError` subclass, so `run_git` catches it and re-raises
    `GitError` either way.

    `os.fsencode` is the test rather than `str.encode("utf-8")` because it is exactly what
    `subprocess` applies on POSIX: it uses `surrogateescape`, so `\\udcff` round-trips to a byte
    and IS accepted by git. Encoding as strict UTF-8 would refuse that as well -- correct-looking,
    and wrong, because it would deny a pattern the instrument can actually run.
    """
    if "\0" in pattern:
        return Authorization(
            denial=Denial(
                reason="pattern-malformed", notice="search pattern contains a NUL character"
            )
        )
    try:
        os.fsencode(pattern)
    except (UnicodeEncodeError, ValueError) as exc:
        return Authorization(
            denial=Denial(reason="pattern-malformed", notice=f"search pattern is not encodable: {exc}")
        )
    return Authorization(denial=None)


def authorize(request: EvidenceRequest, policy: SurfacePolicy) -> Authorization:
    """Judge one request. Happens before any join, any pathspec build, and any git call.

    `Authorization.path` is populated for the operations that name a path and is `None` for a
    search, whose target is a pattern. A search's optional pathspec IS a path and is judged and
    normalized like any other.
    """
    if request.op is not EvidenceOp.SEARCH:
        return _judge_path(request.target, policy)
    pattern = _judge_pattern(request.target)
    if pattern.denial is not None:
        return pattern
    if request.pathspec is None:
        return Authorization(denial=None)
    return _judge_path(request.pathspec, policy)


def literal_pathspec(path: str) -> str:
    """A caller-supplied path as a pathspec git cannot expand.

    MEASURED against git 2.55: with a deny prefix `private`, the history target `priv*` is under
    no prefix as text and passes authorization -- and as a bare pathspec git expands it onto
    `private/x.txt`, so `log` and `grep` both report the denied tree. `:(literal)priv*` matches
    nothing. Without this, every deny prefix is walked around by a glob, which is the policy
    bypass `exclude_pathspecs` exists to prevent on the other side of the same call.
    """
    return f":(top,literal){path}"


def exclude_pathspecs(policy: SurfacePolicy) -> tuple[str, ...]:
    """The deny prefixes as pathspecs every search carries, whether or not one was supplied.

    `literal` disables wildmatch. Measured against git 2.55 (design §3.2), the bare `:(exclude)`
    spelling does not leak denied material -- git also tries a literal prefix match -- it
    OVER-excludes: `:(exclude)notes/a[b].md` also removes the innocent sibling `notes/ab.md`,
    which the policy never denied and which `read` serves without objection. The exclusion set
    would then be a function of glob syntax rather than of the policy text, and "I searched and
    found nothing" would go false for reasons invisible in the policy.

    `top` anchors to the repository root so the exclusion does not drift with the caller's own
    pathspec.
    """
    return tuple(f":(top,literal,exclude){prefix}" for prefix in policy.deny_prefixes)

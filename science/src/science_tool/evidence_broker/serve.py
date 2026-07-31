"""What bytes a request is answered with. Policy is decided elsewhere.

Determinism is the whole product: two honest replays of one request against one commit must
produce identical bytes, because §5.3 refuses a review on disagreement. That needs three things
at once -- the commit pin, the canonical argv below, and the environment `run_git` pins -- and
losing any one of them silently converts an honest run into a refused one.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from science_model.evidence_broker import SurfacePolicy

from science_tool.autonomy.git import run_git
from science_tool.evidence_broker.policy import (
    Denial,
    EvidenceOp,
    EvidenceRequest,
    authorize,
    exclude_pathspecs,
    literal_pathspec,
)


class ServeError(RuntimeError):
    """git said something this module has not been shown how to read.

    Halts the run. A broker that guessed at unfamiliar output would turn an instrument failure
    into evidence, which is the one thing a record of what an agent was shown may not do.
    """


class Outcome(StrEnum):
    SERVED = "served"
    MISS_ABSENT = "miss-absent"
    MISS_NO_MATCH = "miss-no-match"
    MISS_NO_COMMITS = "miss-no-commits"
    REFUSED = "refused"


#: Defined-miss markers. They are part of the served bytes so the hash covers the ANSWER and not
#: merely its absence, and they are fixed strings because replay compares bytes.
MISS_MARKERS: dict[Outcome, bytes] = {
    Outcome.MISS_ABSENT: b"science-evidence: path absent at commit\n",
    Outcome.MISS_NO_MATCH: b"science-evidence: pattern matched nothing\n",
    Outcome.MISS_NO_COMMITS: b"science-evidence: no commits for this query\n",
}


def _absent_sentences(commit: str, path: str) -> tuple[bytes, ...]:
    """The two spellings git gives one fact, FULLY INTERPOLATED.

    Which one appears depends on whether the path is in the working tree, which the actor owns,
    so both must classify the same way. They are built with the path and commit in hand and
    compared whole, rather than searched for as substrings: a committed directory named
    `does not exist in` makes `cat-file blob` fail with
    `fatal: git cat-file <c>:does not exist in: bad file`, which CONTAINS the shorter marker.
    A substring test therefore serves a present tree as an absent path -- measured, git 2.55.
    A filename cannot make the whole sentence match while naming a different path.
    """
    return (
        f"fatal: path '{path}' does not exist in '{commit}'".encode(),
        f"fatal: path '{path}' exists on disk, but not in '{commit}'".encode(),
    )


def _malformed_pattern_prefix(pattern: str) -> bytes:
    """The fixed prefix git gives an argv-rejected pattern, FULLY INTERPOLATED.

    MEASURED, git 2.55: every pattern `-e` cannot compile fails with
    `fatal: -e option, '<pattern>': ` followed by a message that varies with what is wrong --
    `Invalid regular expression`, `Trailing backslash`, `Invalid preceding regular expression`,
    `Unmatched ( or \\(`, and doubtless others this module has not been shown. The PREFIX naming
    this pattern does not vary, so anchoring there is the same discipline `_absent_sentences`
    uses for `read`: comparing an interpolated value rather than a keyword that could appear in
    stderr for an unrelated reason.
    """
    return f"fatal: -e option, '{pattern}': ".encode()


#: `grep` renders through config unless argv says otherwise; `-E` is passed explicitly so
#: `grep.patternType` cannot decide what the caller's pattern MEANS.
_GREP_ARGV: tuple[str, ...] = (
    "grep",
    "-n",
    "-z",
    "-E",
    "--no-color",
    "--no-column",
    "--no-recurse-submodules",
)

#: `log.showSignature=false` is already in `run_git`'s `_HARDENING` -- it EXECUTES, so it is
#: neutralized there rather than pinned here. What argv owns is rendering.
_LOG_ARGV: tuple[str, ...] = (
    "log",
    "--pretty=format:%H %aI",
    "--no-decorate",
    "--no-notes",
    "--no-abbrev-commit",
)


@dataclass(frozen=True)
class Served:
    outcome: Outcome
    payload: bytes
    denial: Denial | None = None


def _miss(outcome: Outcome) -> Served:
    return Served(outcome=outcome, payload=MISS_MARKERS[outcome])


def verify_commit(repo_root: Path, commit: str) -> str:
    """Resolve `commit` to a full object name, or halt.

    RUNS ONCE BEFORE ANY REQUEST, and the ordering is load-bearing. For a well-formed but
    nonexistent commit git reports `path 'x' exists on disk, but not in '<commit>'` -- the same
    sentence it emits for a path added after the pinned commit. Miss classification is sound only
    once the revision is known good, so a broker that verified lazily would answer "absent at
    commit" for every path in a bogus revision.
    """
    completed = run_git(repo_root, "rev-parse", "--verify", "--end-of-options", f"{commit}^{{commit}}")
    if completed.returncode != 0:
        raise ServeError(
            f"{commit!r} does not name a commit in {repo_root}: "
            f"{completed.stderr.decode('utf-8', 'replace').strip()}"
        )
    return completed.stdout.decode("utf-8").strip()


def _serve_read(repo_root: Path, commit: str, target: str) -> Served:
    """Object TYPE first, then the blob. Two calls, because one cannot answer both questions.

    Asking `cat-file blob` alone conflates "not there" with "there but not a file": both exit
    128, and the tree's error text embeds git's own miss sentence. `-t` answers `tree` at exit 0,
    which removes the ambiguous case entirely rather than parsing around it.
    """
    typed = run_git(repo_root, "cat-file", "-t", f"{commit}:{target}")
    if typed.returncode != 0:
        if typed.stderr.strip() in _absent_sentences(commit, target):
            return _miss(Outcome.MISS_ABSENT)
        raise ServeError(
            f"read of {target!r} at {commit} could not be classified: "
            f"{typed.stderr.decode('utf-8', 'replace').strip()}"
        )
    kind = typed.stdout.strip()
    if kind != b"blob":
        # A tree, or a submodule's commit. The path IS at the commit; it simply is not a file,
        # and `git show` would answer it with a directory listing at exit 0 -- FULL coverage
        # over a listing nobody can cite honestly.
        raise ServeError(
            f"read of {target!r} at {commit} names a {kind.decode('ascii', 'replace')}, not a file"
        )
    completed = run_git(repo_root, "cat-file", "blob", f"{commit}:{target}")
    if completed.returncode != 0:
        raise ServeError(
            f"read of {target!r} at {commit} typed as a blob and then failed: "
            f"{completed.stderr.decode('utf-8', 'replace').strip()}"
        )
    return Served(outcome=Outcome.SERVED, payload=completed.stdout)


def _serve_search(
    repo_root: Path, commit: str, pattern: str, policy: SurfacePolicy, pathspec: str | None
) -> Served:
    # A PATTERN, not a request: the helper is given the two values it may use, so there is no
    # `request.target` in reach for it to mistake for a path.
    #
    # `literal_pathspec` on the caller's own path, for the same reason the exclusions carry it:
    # a bare `priv*` is under no deny prefix as text and expands onto `private/x.txt`.
    pathspecs = [*exclude_pathspecs(policy)]
    if pathspec is not None:
        pathspecs.insert(0, literal_pathspec(pathspec))
    completed = run_git(repo_root, *_GREP_ARGV, "-e", pattern, commit, "--", *pathspecs)
    if completed.returncode == 0:
        return Served(outcome=Outcome.SERVED, payload=completed.stdout)
    if completed.returncode == 1:
        return _miss(Outcome.MISS_NO_MATCH)
    stderr = completed.stderr
    if stderr.startswith(_malformed_pattern_prefix(pattern)):
        # The requester's own input. It carries no repository fact, so it is retryable rather
        # than an instrument failure -- halting an honest run over a typo would be worse.
        return Served(
            outcome=Outcome.REFUSED,
            payload=b"",
            denial=Denial(
                reason="pattern-malformed",
                notice=stderr.decode("utf-8", "replace").strip(),
            ),
        )
    raise ServeError(
        f"search for {pattern!r} at {commit} could not be classified: "
        f"{stderr.decode('utf-8', 'replace').strip()}"
    )


def _serve_history(
    repo_root: Path, commit: str, target: str, policy: SurfacePolicy
) -> Served:
    """The exclusions ride on `log` too, for a reason `read` does not have.

    A deny prefix may name a FILE, and `log` selects a path RECURSIVELY. With deny prefix
    `private/x.txt`, the target `private` is beneath no prefix and authorizes -- `read` refuses it
    as a tree, but `:(top,literal)private` makes `log` report every commit touching
    `private/x.txt`. Measured on git 2.55. The authorization check answers "is this path denied";
    it cannot answer "does this path CONTAIN something denied", so the exclusions must answer
    that here, exactly as they do for `search`.
    """
    completed = run_git(
        repo_root,
        *_LOG_ARGV,
        commit,
        "--",
        literal_pathspec(target),
        *exclude_pathspecs(policy),
    )
    if completed.returncode != 0:
        raise ServeError(
            f"history of {target!r} at {commit} could not be classified: "
            f"{completed.stderr.decode('utf-8', 'replace').strip()}"
        )
    if not completed.stdout:
        return _miss(Outcome.MISS_NO_COMMITS)
    return Served(outcome=Outcome.SERVED, payload=completed.stdout)


def serve(
    repo_root: Path, commit: str, request: EvidenceRequest, policy: SurfacePolicy
) -> Served:
    """Answer one request at a pinned commit, or refuse it, or halt.

    ORDER: authorize, then verify, then dispatch. `authorize` comes first so a denied request
    produces NO git invocation at all -- a withheld path must leave no trace in a process table
    and no timing difference, and a refusal that had already spawned a process would be a
    refusal only in the return value. `verify_commit` comes second because miss classification
    is unsound against an unverified revision (see its docstring), and every path below
    classifies.

    THE AUTHORIZED SPELLING IS THE ONLY SPELLING USED BELOW. `request.target` is not read again
    for the operations that name a path: `auth.path` is the normalized value the policy was
    actually compared against, and using the raw one would authorize one path and read another.
    """
    auth = authorize(request, policy)
    if auth.denial is not None:
        return Served(outcome=Outcome.REFUSED, payload=b"", denial=auth.denial)
    resolved = verify_commit(repo_root, commit)
    if request.op is EvidenceOp.READ:
        if auth.path is None:
            # An internal invariant, not a user-facing miss: `authorize` always carries a path
            # for a READ it does not deny. An `assert` would vanish under `python -O`, at which
            # point `None` would interpolate into `f"{commit}:{target}"` rather than halt.
            raise ServeError("a READ authorization without a denial must carry a path")
        return _serve_read(repo_root, resolved, auth.path)
    if request.op is EvidenceOp.SEARCH:
        return _serve_search(repo_root, resolved, request.target, policy, auth.path)
    if auth.path is None:
        raise ServeError("a HISTORY authorization without a denial must carry a path")
    return _serve_history(repo_root, resolved, auth.path, policy)

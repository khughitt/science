"""What bytes a request is answered with. Policy is decided elsewhere.

Determinism is the whole product: two honest replays of one request against one commit must
produce identical bytes, because §5.3 refuses a review on disagreement. That needs three things
at once -- the commit pin, the canonical argv below, and the environment `run_git` pins -- and
losing any one of them silently converts an honest run into a refused one.

THE ATTRIBUTE STACK IS A SECOND ACTOR-OWNED CHANNEL, DISTINCT FROM `.git/config`, and it is not
reachable by the `-c` hardening `run_git` applies. A working-tree `.gitattributes` need not be
committed to take effect, and `$GIT_DIR/info/attributes` has no config key at all;
`--attr-source` replaces only the tracked-`.gitattributes` layer, so neither is neutralized
there. MEASURED, git 2.55: either layer carrying `* binary` makes `grep` answer
`Binary file <commit>:a.txt matches` at exit 0 instead of the `-z` record with a line number and
the matched content -- `SERVED`, reported as a success, carrying no evidence. `-a` in `_GREP_ARGV`
is what neutralizes the attribute stack for `grep`, and it is the only lever that does.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from science_model.evidence_broker import MAX_SERVED_BYTES, Outcome, SurfacePolicy

from science_tool.autonomy.git import GitOutputTooLarge, run_git
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


def _verdict_line(stderr: bytes) -> bytes:
    """git's LAST non-empty stderr line, which is where its verdict lands.

    THE WHOLE OF STDERR IS NOT THE VERDICT, and treating it as one hands the actor a switch that
    converts every defined miss into a halted run. `.git/objects/info/alternates` is untracked,
    actor-writable, and outside `.git/config`, so no `-c` override in `run_git` reaches it.
    MEASURED, git 2.55, with `/nonexistent/objects` written there:

        error: unable to normalize alternate object path: /nonexistent/objects
        fatal: path 'nope.txt' does not exist in '<commit>'

    Compared whole, that matches neither absent sentence and neither malformed-pattern prefix,
    so an ordinary absent path -- §5.1 calls it "frequently the decisive finding" -- raises
    `ServeError`, and a retryable malformed pattern does too. Anchoring on the LAST line keeps
    the interpolated, whole-sentence comparison that `_absent_sentences` documents (a substring
    search over stderr is the defect it exists to prevent) while letting git warn about anything
    it likes first.
    """
    lines = [line for line in stderr.strip().splitlines() if line.strip()]
    return lines[-1].strip() if lines else b""


#: `grep` renders through config unless argv says otherwise; `-E` is passed explicitly so
#: `grep.patternType` cannot decide what the caller's pattern MEANS.
#:
#: `-a` treats every blob as text, defeating the attribute stack described in the module
#: docstring. THE TRADE-OFF IS DELIBERATE AND WAS ACCEPTED: a genuinely binary blob's raw bytes
#: now enter the served payload. Determinism is the property replay depends on, and a payload
#: the actor can empty at will is worse than one that is occasionally raw. `-I` is not an
#: alternative -- it would skip "binary" files, and binary-ness is itself attribute-derived, so
#: the actor would still decide what the auditor is shown.
_GREP_ARGV: tuple[str, ...] = (
    "grep",
    "-a",
    "-n",
    "-z",
    "-E",
    "--no-color",
    "--no-column",
    "--no-recurse-submodules",
)

#: `log.showSignature=false` is already in `run_git`'s `_HARDENING` -- it EXECUTES, so it is
#: neutralized there rather than pinned here. What argv owns is rendering.
#:
#: `--no-follow` pins WHICH COMMITS ARE SELECTED, not how they render, which is why it belongs
#: here rather than among the inert keys. MEASURED, git 2.55: against a repository where
#: `old.txt` was renamed to `new.txt`, history for `new.txt` reports two commits by default and
#: three under `log.follow=true`. Follow arms only when exactly one pathspec is given, so a
#: policy with any deny prefix already disarms it by handing `log` its exclusions -- an EMPTY
#: deny policy is legitimate, is what most of the suite uses, and is exactly where this bites.
_LOG_ARGV: tuple[str, ...] = (
    "log",
    "--pretty=format:%H %aI",
    "--no-decorate",
    "--no-notes",
    "--no-abbrev-commit",
    "--no-follow",
)


@dataclass(frozen=True)
class Served:
    outcome: Outcome
    payload: bytes
    target: str
    denial: Denial | None = None
    pathspec: str | None = None


def _miss(outcome: Outcome, target: str, pathspec: str | None = None) -> Served:
    return Served(
        outcome=outcome,
        payload=MISS_MARKERS[outcome],
        target=target,
        pathspec=pathspec,
    )


def _too_large(target: str, pathspec: str | None = None) -> Served:
    """A refusal, not an error, and DETERMINISTIC GIVEN THE COMMIT.

    That determinism is what licenses journaling it: the same request against the same commit
    refuses identically at replay, so §5.2's comparison stays sound. Under §5.1 it contributes no
    coverage, exactly like a policy denial.

    The notice names no size and no path. A blinded requester learning "this file is larger than
    1 MiB" has learned the file exists, which is what the policy's uniform notice withholds.
    """
    return Served(
        outcome=Outcome.REFUSED,
        payload=b"",
        target=target,
        denial=Denial(
            reason="payload-too-large",
            notice="the requested material exceeds the per-request serving limit",
        ),
        pathspec=pathspec,
    )


def verify_commit(repo_root: Path, commit: str) -> str:
    """Resolve `commit` to a full object name, or raise `ServeError`.

    `serve` calls this ONCE PER REQUEST, after `authorize` and before any dispatch, and that
    position is load-bearing. For a well-formed but nonexistent commit git reports
    `path 'x' exists on disk, but not in '<commit>'` -- the same sentence it emits for a path
    added after the pinned commit. Miss classification is sound only once the revision is known
    good, so a broker that verified lazily would answer "absent at commit" for every path in a
    bogus revision.

    The resolved full object name, not the caller's spelling, is what every helper below is
    handed: `_absent_sentences` interpolates the commit into the sentence it compares, and git
    spells that sentence with the revision as given.
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
        if _verdict_line(typed.stderr) in _absent_sentences(commit, target):
            return _miss(Outcome.MISS_ABSENT, target)
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
    # PRE-CHECKED, NOT TRUNCATED. `-s` yields the blob size from the object header without
    # reading its content, so an oversized read never allocates the bytes it is about to refuse.
    sized = run_git(repo_root, "cat-file", "-s", f"{commit}:{target}")
    if sized.returncode != 0:
        raise ServeError(
            f"read of {target!r} at {commit} typed as a blob and then could not be sized: "
            f"{sized.stderr.decode('utf-8', 'replace').strip()}"
        )
    if int(sized.stdout.decode("ascii").strip()) > MAX_SERVED_BYTES:
        return _too_large(target)
    completed = run_git(repo_root, "cat-file", "blob", f"{commit}:{target}")
    if completed.returncode != 0:
        raise ServeError(
            f"read of {target!r} at {commit} typed as a blob and then failed: "
            f"{completed.stderr.decode('utf-8', 'replace').strip()}"
        )
    return Served(outcome=Outcome.SERVED, payload=completed.stdout, target=target)


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
    try:
        completed = run_git(
            repo_root,
            *_GREP_ARGV,
            "-e",
            pattern,
            commit,
            "--",
            *pathspecs,
            stdout_limit=MAX_SERVED_BYTES,
        )
    except GitOutputTooLarge as exc:
        # STDOUT ONLY. A `stderr` overflow is determined by mutable repository and runtime state,
        # so it must fail the invocation rather than enter the journal (design §3.2).
        if exc.stream != "stdout":
            raise
        return _too_large(pattern, pathspec)
    if completed.returncode == 0:
        return Served(
            outcome=Outcome.SERVED,
            payload=completed.stdout,
            target=pattern,
            pathspec=pathspec,
        )
    if completed.returncode == 1:
        return _miss(Outcome.MISS_NO_MATCH, pattern, pathspec)
    stderr = completed.stderr
    verdict = _verdict_line(stderr)
    if verdict.startswith(_malformed_pattern_prefix(pattern)):
        # The requester's own input. It carries no repository fact, so it is retryable rather
        # than an instrument failure -- halting an honest run over a typo would be worse.
        #
        # THE NOTICE IS THE VERDICT LINE, NOT ALL OF STDERR. The diagnostic may be given a
        # `Denial.notice` precisely because it echoes only the requester's own pattern back at
        # them; the actor-written warnings that can precede it (see `_verdict_line`) name
        # repository paths, and handing those to a blinded requester would disclose exactly what
        # the policy's uniform notice exists to withhold.
        return Served(
            outcome=Outcome.REFUSED,
            payload=b"",
            target=pattern,
            denial=Denial(
                reason="pattern-malformed",
                notice=verdict.decode("utf-8", "replace"),
            ),
            pathspec=pathspec,
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
    try:
        completed = run_git(
            repo_root,
            *_LOG_ARGV,
            commit,
            "--",
            literal_pathspec(target),
            *exclude_pathspecs(policy),
            stdout_limit=MAX_SERVED_BYTES,
        )
    except GitOutputTooLarge as exc:
        # STDOUT ONLY. A `stderr` overflow is determined by mutable repository and runtime state,
        # so it must fail the invocation rather than enter the journal (design §3.2).
        if exc.stream != "stdout":
            raise
        return _too_large(target)
    if completed.returncode != 0:
        raise ServeError(
            f"history of {target!r} at {commit} could not be classified: "
            f"{completed.stderr.decode('utf-8', 'replace').strip()}"
        )
    if not completed.stdout:
        return _miss(Outcome.MISS_NO_COMMITS, target)
    return Served(outcome=Outcome.SERVED, payload=completed.stdout, target=target)


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
        return Served(
            outcome=Outcome.REFUSED,
            payload=b"",
            target=request.target,
            denial=auth.denial,
            pathspec=request.pathspec,
        )
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

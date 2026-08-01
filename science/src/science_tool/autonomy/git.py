"""The one git invocation the autonomy surface makes.

Global Constraint 10 asks for a single spelling of `--no-replace-objects`. The reason a
single spelling matters is stronger than tidiness: **the actor owns `.git/config`**. It
is untracked, absent from `base..head`, and invisible to `git status`, so neither the
path gate nor the belief-basis capture can see it change -- and several config keys name
a PROGRAM that git then runs with the supervisor's privileges. A git call that skips this
module is a call the actor can turn into arbitrary execution inside the control plane,
and no layer of this design would report it.

`-c KEY=VALUE` on the command line outranks the repository-local file, which is the
actor-controlled layer, so the hardening below cannot be un-set from inside the worktree.

WHAT WAS PROBED, AND WHAT ACTUALLY EXECUTES. Each key below was built as a working attack
in a scratch repository against git 2.55, under exactly the commands this package runs --
`rev-parse`, `status --porcelain`, `log`, `show <commit>:<path>`, `diff --raw`,
`diff --name-status`, `grep`, `cat-file -t <commit>:<path>` and `cat-file blob <commit>:<path>`:

* `core.fsmonitor` -- EXECUTES, under `status`.
* `core.hooksPath` -- EXECUTES, under `status`, via the `post-index-change` hook. So does
  a hook dropped straight into `$GIT_DIR/hooks/`, which no `-c` key can blank; pointing
  `core.hooksPath` at a location with no hooks in it disarms both.
* a `filter=<driver>` attribute plus `[filter "<driver>"]` -- EXECUTES, under `status`.
  See `_filter_driver_overrides`; this one cannot be neutralized by a fixed key.
* `diff.external`, and `diff.<driver>.command` / `.textconv` reached through a
  `diff=<driver>` attribute -- do NOT fire. `--raw` and `--name-status` emit no textual
  diff, so git spawns no diff program, and `show <commit>:<path>` is a blob read.
* `core.pager` -- never spawned: every call here captures output, so stdout is a pipe and
  git does not page.
* `core.sshCommand`, `core.editor`, `core.alternateRefsCommand` -- no command here
  contacts a remote, opens an editor, or reads an alternate object store.
* `log.showSignature=true` combined with `gpg.program=./spawn.sh`, against a commit
  carrying a `gpgsig` header -- EXECUTES, under `log`. `gpg.program` alone is inert
  because it lacks a reason to verify: with `log.showSignature` unset git never asks for a
  signing program at all, regardless of what it names. `log.showSignature=true` alone,
  against that same signed commit, already reaches a program -- the default `gpg` on
  `PATH`. The composite row differs only in *which* program that reach lands on: the
  attacker-named one rather than the default. `-c log.showSignature=false` disarms it;
  blanking `gpg.program` instead does not -- verification stays enabled and git falls
  back to the default `gpg` on `PATH`, so the row still reads EXECUTES against a program
  this key never named.
* `diff.<driver>.textconv` reached through a `grep`-side attribute, `core.pager`, and
  `pager.grep` -- all INERT, under `grep`. `grep` never invokes a textconv filter and,
  like every other call in this module, always runs with captured output, so no pager is
  ever spawned.
* `cat-file -t <commit>:<path>` and `cat-file blob <commit>:<path>` -- probed separately,
  identical results. Every key probed is INERT: `core.pager`, `pager.cat-file`,
  `diff.<driver>.textconv`, `diff.<driver>.command`, `diff.external`, `filter.<driver>.clean`
  / `.smudge` / `.process`, `core.fsmonitor`, `core.hooksPath`, `core.quotePath`,
  `core.autocrlf`, `core.eol`, `log.showSignature`, `gpg.program`, `core.sshCommand`,
  `core.alternateRefsCommand` -- probed with `.gitattributes` binding the driver keys to the
  path, so each had a reason to fire. `cat-file blob` is a raw object read: it applies no
  smudge filter, no textconv and no eol conversion, and captured output means no pager. So
  `_HARDENING` gains NOTHING for this subcommand, per this module's standing rule.

  The broker uses this rather than `show <commit>:<path>` because `show` answers a path naming
  a TREE with a directory listing at exit 0, which the evidence broker cannot distinguish from
  a file read (design §3.2). `cat-file blob` refuses it.
* `grep.column=true`, `color.grep=always`, `color.ui=always` -- RENDER, under `grep`:
  they change output but spawn nothing. The broker pins the argv keys this shapes
  (`--no-color`, etc.) rather than neutralizing them here, since there is nothing here
  to neutralize.
* `log.showSignature=true` alone -- also reads RENDERS, but not for the same reason.
  Against the signed commit it still reaches the default `gpg` on `PATH`; with no
  `gpg.program` configured that is a real signature-verification attempt, and the
  program's own complaint (`gpg: no valid OpenPGP data found.`, etc.) lands in the same
  stdout the probe compares -- the probe's marker only watches `./spawn.sh`, so it cannot
  see a *default* binary run. This row is why `_HARDENING` carries
  `log.showSignature=false` rather than leaving verification enabled and hoping no
  `gpg.program` is ever configured.
* `grep.patternType`, `grep.extendedRegexp`, `grep.lineNumber`, `grep.fullName`,
  `grep.threads`, `core.quotePath`, `log.date`, `log.decorate`, `log.abbrevCommit`,
  `log.mailmap`, `format.pretty` -- INERT under the canonical argv the broker builds:
  each is either pinned explicitly in that argv or has no bearing on the fixed
  `--pretty=format:` this module's `log` callers already use.

Only what was shown to execute is neutralized. Blanking the rest would assert a defense
against behaviour this code has been shown not to have. `grep`'s three execution
candidates (`diff.<driver>.textconv`, `core.pager`, `pager.grep`) all measured INERT --
that is itself the probe's finding for `grep`, not an oversight: `grep` contributes
nothing to `_HARDENING`.
"""

from __future__ import annotations

import os
import selectors
import subprocess
from pathlib import Path


class GitError(ValueError):
    """git could not be invoked, or the invocation could not be hardened.

    Distinct from a non-zero exit, which each call site decides about for itself: a
    command that ran and refused is an answer, a command that never ran is not.
    """


class GitOutputTooLarge(GitError):
    """A git invocation produced more output than its caller allowed.

    A SUBCLASS OF `GitError`, so the DEFAULT disposition is the safe one. Five call sites already
    convert `GitError` into a run-level `unwired` -- `autonomy/extract.py:48`,
    `autonomy/toolkit.py:43`, `boundary/gitio.py:83` and `:166`, and
    `validate/checks/autonomous_runs.py:75`. An exception outside that hierarchy would escape all
    five and surface as an unhandled traceback: exit 1, which the documented codes read as
    `quarantined` rather than `unwired`. Overflow IS a failure to complete the invocation, which
    is what `GitError` already means.

    Subclassing costs no precision. A call site wanting a different disposition catches
    `GitOutputTooLarge` specifically, and `serve.py` does exactly that for its stdout case. ORDER
    MATTERS: an `except GitOutputTooLarge` must precede any `except GitError` in the same `try`.

    `consumed` is how §7 certifies that the ceiling is enforced DURING capture rather than after:
    a check moved to the end of the loop would report the whole output here.
    """

    def __init__(self, stream: str, limit: int, consumed: int, args: tuple[str, ...]) -> None:
        super().__init__(
            f"git {' '.join(args)} produced more than {limit} bytes on {stream}; refused rather "
            "than truncated, because a truncated answer is indistinguishable from a short one"
        )
        self.stream = stream
        self.limit = limit
        self.consumed = consumed


#: Diagnostics are never legitimately large, and this one is actor-influenced (§3.2.1).
MAX_GIT_STDERR_BYTES = 1 << 20

#: `include.path` makes the configuration listing arbitrarily large, and the preflight runs before
#: every call. Generous enough for any real configuration, bounded because the actor writes it.
MAX_CONFIG_LIST_BYTES = 1 << 20


#: The environment every autonomy git call runs under. `LC_ALL` and `LANG` are pinned
#: because argv is not the whole invocation: a POSIX class such as `[[:alpha:]]` matches a
#: different character set under `C` than under a UTF-8 locale, so two honest replays of one
#: pattern against one commit would disagree -- and §5.3 refuses on disagreement. The same
#: pin fixes git's DIAGNOSTIC text, which the broker's defined-miss classifier reads: under a
#: translated locale the miss messages would not match and an absent path would halt the run.
#:
#: `GIT_SHALLOW_FILE` and `GIT_NO_LAZY_FETCH` are here for the reason `-c` hardening is here: the
#: actor owns the file. `.git/shallow` is an ordinary file in the actor-owned `.git` directory --
#: MEASURED, git 2.55: one `echo <sha> > .git/shallow` takes `git log <commit>` from 3 commits to
#: 2, at exit 0 both ways, against an unchanged pinned commit. A check at run open cannot hold
#: against a file written after the run opens, so the defense is an input git no longer reads.
#:
#: A partial clone is the same problem in the worse direction. `--filter=tree:0` does not truncate
#: and does not fail: it LAZILY FETCHES the missing objects from its promisor remote, mid-request,
#: at exit 0 -- MEASURED, two `git fetch` subprocesses spawned under the canonical `log` argv. That
#: remote's URL lives in `.git/config`, so lazy fetch hands the actor an egress channel out of the
#: control plane and a payload whose content depends on a host it named. `-c` cannot close it: the
#: neutralization would have to name the remote, and the name is the actor's to choose.
#:
#: Under both pins a repository that cannot answer locally EXITS NON-ZERO instead of answering
#: short or phoning home, which every call site here already treats as a refusal to answer. Both
#: are no-ops in an ordinary complete clone, which has no boundary file and nothing to fetch.
#:
#: They apply to all three broker ops, not to `history` alone: a partial clone withholds blobs as
#: readily as trees, so `cat-file blob` and `grep` reach a promisor remote by the same mechanism.
#: Putting them in `_ENVIRONMENT` rather than at one call site is what makes that automatic.
#:
#: `TZ` is deliberately NOT pinned: `%aI` carries its own offset, so the rendered log does not
#: depend on the reader's zone. Pinning it would assert a defense against behaviour the chosen
#: format has been shown not to have.
_ENVIRONMENT: dict[str, str] = {
    "LC_ALL": "C",
    "LANG": "C",
    "GIT_SHALLOW_FILE": "/dev/null",
    "GIT_NO_LAZY_FETCH": "1",
}

#: The fixed half of the hardening -- keys whose names are known in advance.
_HARDENING: tuple[str, ...] = (
    "core.fsmonitor=",
    "core.hooksPath=/dev/null",
    "log.showSignature=false",
)

#: `filter.<name>.<key>` entries git executes. `required` is deliberately NOT reset: a
#: driver whose command is blanked while `required` stays true makes git exit non-zero,
#: which every call site here already treats as a refusal to answer.
_FILTER_COMMAND_KEYS: tuple[str, ...] = ("clean", "smudge", "process")


def _argv(repo_root: Path, overrides: tuple[str, ...], args: tuple[str, ...]) -> list[str]:
    """The single place autonomy's git argv is built."""
    argv = ["git", "--no-replace-objects"]
    for override in overrides:
        argv += ["-c", override]
    argv += ["-C", str(repo_root), *args]
    return argv


_CHUNK = 65536


def _capture(
    process: subprocess.Popen[bytes],
    *,
    input: bytes | None,
    stdout_limit: int | None,
    stderr_limit: int,
    args: tuple[str, ...],
) -> tuple[bytes, bytes]:
    """Pump stdin and drain both output pipes in ONE loop.

    ALL THREE STREAMS MUST SHARE THE LOOP, and this is not defensive coding -- it is the only
    shape that terminates. Pipe buffers are finite (~64 KiB each). Writing all of stdin before
    reading anything deadlocks the moment the child's own output fills its pipe: the child blocks
    writing stdout, so it stops reading stdin, so the parent blocks writing stdin, forever.
    MEASURED: `Popen(["cat"])` plus a 4 MiB `stdin.write` never returns. `boundary/sync.py` and
    `boundary/gitio.py` both pass payloads through `input=`, so this is a live path, not a
    hypothetical. Draining stdout fully before stderr fails the same way for the same reason.

    SHARING THE LOOP IS NOT SUFFICIENT ON ITS OWN. A selector plus a blocking
    `BufferedWriter.write` deadlocks identically -- also MEASURED -- because readiness for one byte
    does not stop `write` from looping until all 64 KiB are out. See the `os.set_blocking` call
    below: the nonblocking fd is what turns readiness into progress.

    The ceiling is checked as the bytes ARRIVE. A cap tested after the loop has already spent the
    memory it exists to protect, which is why `GitOutputTooLarge` carries `consumed`.
    """
    limits = {"stdout": stdout_limit, "stderr": stderr_limit}
    buffers: dict[str, bytearray] = {"stdout": bytearray(), "stderr": bytearray()}

    selector: selectors.BaseSelector | None = None
    pending = memoryview(input) if input else None
    try:
        # ALL POST-`Popen` SETUP IS INSIDE THIS CLEANUP GUARANTEE. Selector construction,
        # nonblocking setup, and registration may fail after the child exists; every such path
        # still closes the pipes, kills if necessary, and reaps the child below.
        selector = selectors.DefaultSelector()
        if pending is not None:
            assert process.stdin is not None
            # NONBLOCKING, AND WRITTEN WITH `os.write`. `EVENT_WRITE` promises only that AT LEAST
            # ONE byte can be written -- it does not make the write partial-friendly, and
            # `BufferedWriter.write(n)` loops until all n bytes are out. MEASURED: the selector
            # loop with `stdin.write(pending[:65536])` on a blocking fd still deadlocks against
            # `cat` and a 4 MiB payload. `os.set_blocking(fd, False)` plus `os.write` returns a
            # partial count and the loop makes progress. Do not mix buffered writes with the raw
            # fd: nothing is ever written through `process.stdin`, so its buffer stays empty and
            # `close()` just closes.
            os.set_blocking(process.stdin.fileno(), False)
            selector.register(process.stdin, selectors.EVENT_WRITE, "stdin")
        elif process.stdin is not None:
            process.stdin.close()
        for name in ("stdout", "stderr"):
            stream = getattr(process, name)
            assert stream is not None
            selector.register(stream, selectors.EVENT_READ, name)

        while selector.get_map():
            for key, _ in selector.select():
                if key.data == "stdin":
                    assert pending is not None
                    try:
                        written = os.write(key.fd, pending[:_CHUNK])
                    except BlockingIOError:
                        # Readiness is advisory; the pipe filled between select and write.
                        written = 0
                    except BrokenPipeError:
                        # The child exited without reading its input. That is an ANSWER (git
                        # refused early), not a failure to invoke, so it is not an error here.
                        written = len(pending)
                    pending = pending[written:]
                    if not pending:
                        selector.unregister(key.fileobj)
                        key.fileobj.close()  # type: ignore[union-attr]
                        pending = None
                    continue

                name = key.data
                chunk = key.fileobj.read1(_CHUNK)  # type: ignore[union-attr]
                if not chunk:
                    selector.unregister(key.fileobj)
                    continue
                buffers[name] += chunk
                limit = limits[name]
                if limit is not None and len(buffers[name]) > limit:
                    process.kill()
                    raise GitOutputTooLarge(name, limit, len(buffers[name]), args)
    finally:
        if selector is not None:
            selector.close()
        for stream in (process.stdin, process.stdout, process.stderr):
            if stream is not None and not stream.closed:
                stream.close()
        if process.poll() is None:
            process.kill()
        process.wait()
    return bytes(buffers["stdout"]), bytes(buffers["stderr"])


def _run(
    repo_root: Path,
    overrides: tuple[str, ...],
    args: tuple[str, ...],
    *,
    input: bytes | None = None,
    stdout_limit: int | None = None,
    stderr_limit: int = MAX_GIT_STDERR_BYTES,
) -> subprocess.CompletedProcess[bytes]:
    argv = _argv(repo_root, overrides, args)
    try:
        process = subprocess.Popen(
            argv,
            stdin=subprocess.PIPE if input is not None else subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env={**os.environ, **_ENVIRONMENT},
        )
        stdout, stderr = _capture(
            process,
            input=input,
            stdout_limit=stdout_limit,
            stderr_limit=stderr_limit,
            args=args,
        )
    except GitOutputTooLarge:
        # Preserve the subtype so call sites may choose the served-stdout disposition.
        raise
    except (AttributeError, OSError, ValueError) as exc:
        # `_capture` has already reaped a successfully spawned child before an error gets here.
        raise GitError(f"could not execute git {' '.join(args)} in {repo_root}: {exc}") from exc
    return subprocess.CompletedProcess(argv, process.returncode, stdout, stderr)


def _filter_driver_overrides(repo_root: Path) -> tuple[str, ...]:
    """`-c` overrides blanking every filter driver the repository can reach.

    THE VECTOR A FIXED KEY CANNOT COVER. A `filter=<driver>` attribute plus
    `[filter "<driver>"] clean = ...` in `.git/config` runs the driver's command during
    `git status`, every time git has to re-hash a worktree file -- and a same-size
    `touch` is enough to force that, so the actor gets execution while the tree still
    reads clean. The DRIVER NAME is the actor's to choose, so no fixed `-c` list reaches
    it. What does reach it: an attribute naming a driver that is not configured executes
    nothing, so blanking every CONFIGURED driver is complete regardless of the name.

    Defending on the driver rather than on the attribute is also what covers the whole
    attribute stack. All three layers select a driver -- a tracked or untracked
    `.gitattributes`, `$GIT_DIR/info/attributes`, and `core.attributesFile` -- and git's
    `--attr-source` replaces only the first of them.

    Enumerated across every scope, not just `--local`: `include.path` in `.git/config`
    pulls definitions in from another file, and those must be blanked too. A driver the
    OPERATOR configured globally (git-lfs, typically) is blanked as well, which is the
    intent -- the supervisor runs no filter for anyone. A repository that marks such a
    filter `required` then makes `git status` fail, and the run reads `unwired` rather
    than clean.
    """
    try:
        completed = _run(
            repo_root,
            _HARDENING,
            ("config", "--list", "--name-only", "-z"),
            stdout_limit=MAX_CONFIG_LIST_BYTES,
            stderr_limit=MAX_GIT_STDERR_BYTES,
        )
    except GitOutputTooLarge as exc:
        # FAILS THE INVOCATION, and is never journaled. Its size is determined by `.git/config`,
        # which the actor may edit at any time -- so a journaled refusal would replay differently
        # once the file changed, and §5.3 would return EXPOSURE_UNREPRODUCIBLE for an honest run.
        raise GitError(
            f"the git configuration of {repo_root} is too large to read, so its filter drivers "
            f"could not be neutralized: {exc}"
        ) from exc
    if completed.returncode != 0:
        message = completed.stderr.decode("utf-8", "replace").strip()
        raise GitError(
            f"could not read the git configuration of {repo_root}, so its filter drivers "
            f"could not be neutralized: {message}"
        )

    names: list[str] = []
    for key in completed.stdout.decode("utf-8", "replace").split("\0"):
        if not key.startswith("filter."):
            continue
        # NOT `if not name` -- the empty driver name is a real, reachable driver.
        # `[filter ""]` selected by `* filter=` yields the key `filter..clean`, and git
        # both reports and executes it; treating a falsy name as "no driver" left that
        # one armed. `-c filter..clean=` blanks it like any other.
        name, _, command_key = key[len("filter.") :].rpartition(".")
        if command_key not in _FILTER_COMMAND_KEYS:
            continue
        # `-c` splits at the FIRST `=`, so a driver named `a=b` would turn
        # `-c filter.a=b.clean=` into the key `filter.a` -- leaving the real driver armed.
        # Subsection names may contain `=`, so refuse rather than emit a broken override.
        if "=" in name or "\n" in name:
            raise GitError(
                f"{repo_root} configures a git filter driver named {name!r}, which cannot be "
                "neutralized through `-c`; git would execute it while this command reads the "
                "working tree"
            )
        if name not in names:
            names.append(name)
    return tuple(
        f"filter.{name}.{command_key}=" for name in names for command_key in _FILTER_COMMAND_KEYS
    )


def run_git(
    repo_root: Path,
    *args: str,
    input: bytes | None = None,
    stdout_limit: int | None = None,
) -> subprocess.CompletedProcess[bytes]:
    """Run one hardened git command against `repo_root`.

    Returns the completed process instead of deciding about its exit status, because the
    call sites need genuinely different disciplines: `extract` fails closed on any
    non-zero exit, `toolkit_is_clean` must be able to OBSERVE one, and the `validate`
    check turns one into a `Result`. What none of them may differ on is the argv, which
    is why it is built here and nowhere else.

    Raises `GitError` when git could not be started, the invocation could not be hardened,
    or a bounded capture could not complete. A normal nonzero git exit is still returned
    to the caller.

    Bytes, not text: `extract` has to detect non-UTF-8 blobs rather than have them
    silently replaced. `input` is passed to git's stdin for NUL-framed queries.

    `stdout_limit` bounds the captured payload and RAISES `GitOutputTooLarge` rather than
    truncating. It defaults to `None` -- unbounded -- because `extract` and `boundary/gitio`
    legitimately capture large diffs and sync payloads through this same function, and a blanket
    ceiling would regress them for a guarantee this design never made. The four call sites that
    need a bound pass one, and each chooses its own disposition (design §3.2).

    `stderr` is bounded on EVERY call at `MAX_GIT_STDERR_BYTES`, with no opt-out: it is captured
    alongside stdout regardless, it is actor-influenced, and no caller has a reason to want an
    unbounded diagnostic.
    """
    return _run(
        repo_root,
        (*_HARDENING, *_filter_driver_overrides(repo_root)),
        args,
        input=input,
        stdout_limit=stdout_limit,
        stderr_limit=MAX_GIT_STDERR_BYTES,
    )


def history_traversal_error(repo_root: Path, commit: str) -> str | None:
    """git's own diagnostic if `commit`'s ancestry cannot be walked from local objects, else None.

    A DIAGNOSTIC, not the guarantee. `GIT_SHALLOW_FILE` and `GIT_NO_LAZY_FETCH` above are what make
    `history` answer completely or fail; this exists so that a repository which cannot answer is an
    operator error at run open, naming the cause, rather than a `fatal: Failed to traverse parents`
    in the middle of a run. The two cover disjoint intervals: at `start_run` no actor exists yet, so
    an absence present then is genuine; anything appearing later is the actor's, and the pins
    neutralize it.

    IT ASKS THE SERVED PROPERTY, NOT A PROXY FOR IT. `serve._LOG_ARGV` carries no `-n`, so `history`
    walks to the root -- walking to the root is what to measure. `rev-parse
    --is-shallow-repository` is the proxy, and the pin blinds it: MEASURED, git 2.55, it reads
    `true` for a COMPLETE repository under `GIT_SHALLOW_FILE=/dev/null`, because
    `is_repository_shallow()` sets its flag on a SUCCESSFUL OPEN of the shallow file, before reading
    a line, and `/dev/null` opens. Under the pins it is constant-`true`.

    MEASURED, git 2.55, under the pins: a complete 6755-commit repository answers in 42 ms; a
    complete repository with `.git/shallow` PLANTED still answers, because the plant is ignored; a
    `--depth 1` clone exits 128.

    COVERS MISSING COMMITS ONLY -- do not widen this by assumption. MEASURED: `--filter=tree:0` and
    `--filter=blob:none` clones both report the full commit count. The tree case is refused at open
    by the §3.1 tree scan (`ls-tree -r` -> `fatal: not a tree object`); the blob case is not
    pre-empted at open and fails mid-run at exit 128, which is `GIT_NO_LAZY_FETCH` working. This is
    not a completeness oracle.
    """
    completed = run_git(repo_root, "rev-list", "--count", commit)
    if completed.returncode == 0:
        return None
    return (
        completed.stderr.decode("utf-8", "replace").strip()
        or f"git rev-list exited {completed.returncode} without a diagnostic"
    )

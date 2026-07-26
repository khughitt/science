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
`diff --name-status`:

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

Only what was shown to execute is neutralized. Blanking the rest would assert a defense
against behaviour this code has been shown not to have.
"""

from __future__ import annotations

import subprocess
from pathlib import Path


class GitError(ValueError):
    """git could not be invoked, or the invocation could not be hardened.

    Distinct from a non-zero exit, which each call site decides about for itself: a
    command that ran and refused is an answer, a command that never ran is not.
    """


#: The fixed half of the hardening -- keys whose names are known in advance.
_HARDENING: tuple[str, ...] = ("core.fsmonitor=", "core.hooksPath=/dev/null")

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


def _run(
    repo_root: Path, overrides: tuple[str, ...], args: tuple[str, ...]
) -> subprocess.CompletedProcess[bytes]:
    try:
        return subprocess.run(_argv(repo_root, overrides, args), capture_output=True)
    except (OSError, ValueError) as exc:
        raise GitError(f"could not execute git {' '.join(args)} in {repo_root}: {exc}") from exc


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
    completed = _run(repo_root, _HARDENING, ("config", "--list", "--name-only", "-z"))
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


def run_git(repo_root: Path, *args: str) -> subprocess.CompletedProcess[bytes]:
    """Run one hardened git command against `repo_root`.

    Returns the completed process instead of deciding about its exit status, because the
    call sites need genuinely different disciplines: `extract` fails closed on any
    non-zero exit, `toolkit_is_clean` must be able to OBSERVE one, and the `validate`
    check turns one into a `Result`. What none of them may differ on is the argv, which
    is why it is built here and nowhere else.

    Raises `GitError` only when git could not be invoked at all -- a missing binary is
    `unwired`, and a caller that let `FileNotFoundError` escape would exit 1, which the
    documented codes read as `quarantined`.

    Bytes, not text: `extract` has to detect non-UTF-8 blobs rather than have them
    silently replaced.
    """
    return _run(repo_root, (*_HARDENING, *_filter_driver_overrides(repo_root)), args)

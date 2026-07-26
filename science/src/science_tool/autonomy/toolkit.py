"""Which Science is rendering the verdict, and whether the run could have changed it.

Design §0: the authoritative gate executes from a supervisor-owned, pinned Science
installation, treating the run's worktree strictly as input. Both halves matter --
verifying the revision catches a toolkit that moved under the run, and locating the
installation catches a gate executing out of the tree it is judging. Either alone
leaves the other open.
"""

from __future__ import annotations

from pathlib import Path

import science_tool

from science_tool.autonomy.git import GitError, run_git


class ToolkitError(ValueError):
    """The judging installation could not be identified, or is not external to the run."""


def toolkit_source_root() -> Path:
    """The directory containing the running `science_tool` package."""
    package_file = science_tool.__file__
    if package_file is None:  # namespace package -- no single source location to pin
        raise ToolkitError("science_tool has no __file__; its source location cannot be pinned")
    return Path(package_file).resolve().parent.parent


def _git(root: Path, *args: str) -> tuple[int, str, str]:
    """`(returncode, stdout, stderr)` from the one hardened runner in `autonomy.git`.

    The exit status is handed back rather than acted on, because `toolkit_is_clean` must
    be able to observe a non-zero exit without raising. A git that could not be RUN is a
    different thing and does raise: `finish_run` turns `ToolkitError` into `unwired`,
    whereas a `FileNotFoundError` escaping here would leave click exiting 1 -- the code
    the shipped docs define as `quarantined`, which is the one direction a blocked run
    must never degrade in.
    """
    try:
        result = run_git(root, *args)
    except GitError as exc:
        raise ToolkitError(str(exc)) from exc
    return (
        result.returncode,
        result.stdout.decode("utf-8", "replace"),
        result.stderr.decode("utf-8", "replace"),
    )


def toolkit_revision(root: Path | None = None) -> str:
    """`git rev-parse HEAD` of the tree the running toolkit was loaded from.

    Deliberately pure -- it answers "which commit", not "which bytes". Pair it with
    `toolkit_is_clean`; on its own it cannot tell a pinned install from a dirty one.
    """
    target = toolkit_source_root() if root is None else root
    returncode, stdout, stderr = _git(target, "rev-parse", "HEAD")
    if returncode != 0:
        raise ToolkitError(f"could not read the toolkit revision at {target}: {stderr.strip()}")
    return stdout.strip()


def toolkit_is_clean(root: Path | None = None) -> bool:
    """True when the toolkit tree carries no uncommitted change of any kind.

    `--porcelain` with untracked files INCLUDED (the default): an untracked module is
    still importable, so it still judges the run, and HEAD reports the same sha either
    way. A failure to ask counts as dirty -- this feeds a refusal, and a probe that
    cannot see must not report clean.
    """
    target = toolkit_source_root() if root is None else root
    returncode, stdout, _ = _git(target, "status", "--porcelain")
    if returncode != 0:
        return False
    return not stdout.strip()


def assert_gate_is_external(project_root: Path) -> None:
    root = project_root.resolve()
    source = toolkit_source_root()
    if source == root or root in source.parents:
        raise ToolkitError(
            f"the running toolkit at {source} is inside the run's project root {root}. A run "
            "that edits toolkit code would be judged by the code it edited; run the gate from "
            "a supervisor-owned installation."
        )


def assert_toolkit_matches(recorded_revision: str) -> None:
    """Both halves of the pin: the same commit, and a checkout that IS that commit."""
    running = toolkit_revision()
    if running != recorded_revision:
        raise ToolkitError(
            f"toolkit revision moved during the run: baseline recorded {recorded_revision}, "
            f"the judging installation is at {running}"
        )
    # Module-level lookup, not a direct call, so a test can drive both answers without a
    # repository whose cleanliness it does not control.
    if not toolkit_is_clean():
        raise ToolkitError(
            f"the judging toolkit at {toolkit_source_root()} has uncommitted changes. Its "
            f"revision {running} would be attested in the run record, but the code that "
            "rendered the verdict is not that revision. Run the gate from a pinned checkout."
        )

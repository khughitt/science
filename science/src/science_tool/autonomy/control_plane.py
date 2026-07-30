"""The project-and-run-keyed canonical root a run id resolves against.

Today `science autonomy start --baseline-out` takes an arbitrary supervisor-chosen path,
so a run is addressable only by whoever placed it. A handle that names a baseline requires
that a run id DETERMINE where its baseline is, which is what this module supplies.

Nothing here mentions evidence. Addressing a run by its id is what a dispatch harness needs
to spawn N assignments and later resolve them, brokered or not (design §0).

THE KEY IS PROJECT-SCOPED. A run id is `<date>-<agent>-<short-id>`; two projects running the
same agent role on the same day with the same disambiguator produce the same slug, and a
fork inherits its parent's `science.yaml` name outright. A single global root would let one
project's session resolve another's baseline -- and between a fork and its parent, which
share a base commit, the replay would even succeed.

THE DIGEST IS THE WHOLE DIRECTORY NAME. `ProjectConfig.name` is an unconstrained `str` on a
model with `extra="allow"`, so a name containing `/` or `..`, or one long enough to blow a
path limit, would become a control-plane path that escapes or fails to create. The digest
already carries the whole identity; legibility costs nothing in a `project.json` beside the
run directories, where a human can read it and a path resolver never does.
"""

from __future__ import annotations

import hashlib
import os
import re
from datetime import date
from pathlib import Path

from science_model.autonomous_runs import (
    RUN_ID_PREFIX,
    RunRecordError,
    validate_run_identity,
)

from science_tool.autonomy.baseline import reject_baseline_inside_project

#: Overrides the XDG state location. Still containment-checked: an environment variable must
#: not be able to relocate the control plane into the tree the actor writes.
CONTROL_PLANE_ENV = "SCIENCE_CONTROL_PLANE"

_DATE_LENGTH = len("YYYY-MM-DD")
#: `date.fromisoformat` accepts far more than `YYYY-MM-DD` on Python 3.11+ -- ISO week
#: notation (`2026-W31-4`), basic format with trailing characters ignored (`20260730XY`),
#: even a path separator hiding past the digits it actually reads (`20260730/x`). None of
#: those can come from `generate_run_id`, which builds the date via `date.isoformat()` --
#: strict `YYYY-MM-DD`, always. The shape is checked here, BEFORE `fromisoformat` is asked
#: whether the date is real, so `fromisoformat`'s leniency never gets a substring it wasn't
#: shape-verified first.
_DATE_SHAPE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class ControlPlaneError(ValueError):
    """A handle or root that cannot address a run."""


def _absolute_or_refuse(value: str, variable: str) -> Path:
    """A relative control-plane root is refused, not resolved.

    Resolving it would bind the control plane to the current directory AT THE MOMENT OF
    THE CALL. `science autonomy start` and `science autonomy finish` are separate processes
    run by a supervisor that need not share a working directory, so the same run id would
    address two different baselines -- `finish` would find no journal, and every citation
    against that run would come back unserved. The failure is silent and looks like actor
    misbehaviour, which is the worst possible disguise for a configuration error.
    """
    path = Path(value).expanduser()
    if not path.is_absolute():
        raise ControlPlaneError(
            f"{variable} must be an absolute path, got {value!r}: a relative control plane "
            "resolves against the current directory, so a run opened from one directory "
            "would not be found from another"
        )
    return path


def control_plane_root(project_root: Path) -> Path:
    """Where every project's run directories live.

    Raises `BaselineError` -- not `ControlPlaneError` -- when the resolved root is inside
    the project: it is the same containment failure `write_baseline` refuses, judged by the
    same function, and one failure should not have two names.
    """
    configured = os.environ.get(CONTROL_PLANE_ENV)
    if configured is not None and configured != "":
        root = _absolute_or_refuse(configured, CONTROL_PLANE_ENV)
    elif configured == "":
        # Unlike `XDG_STATE_HOME` below, this variable has no external spec granting an
        # empty value the meaning "unset". `export SCIENCE_CONTROL_PLANE=` is a config
        # error, not an absent one, and falling back silently would hide it.
        raise ControlPlaneError(
            f"{CONTROL_PLANE_ENV} is set but empty; unset it entirely to use the XDG "
            "default, or set it to an absolute path"
        )
    else:
        # XDG_STATE_HOME: the XDG Base Directory spec requires an empty value here to be
        # treated the same as unset, so `xdg_state_home` (falsy on "") intentionally falls
        # through to the default below. Do not "fix" this to match the branch above.
        xdg_state_home = os.environ.get("XDG_STATE_HOME")
        base = (
            _absolute_or_refuse(xdg_state_home, "XDG_STATE_HOME")
            if xdg_state_home
            else Path.home() / ".local" / "state"
        )
        root = base / "science" / "runs"
    reject_baseline_inside_project(root, project_root)
    return root


def project_key(project_root: Path) -> str:
    """A digest of the resolved project root, and nothing else.

    Resolved, not as spelled: two worktrees of one project get two keys, which is correct --
    they are two trees at two commits -- but one project reached by two spellings must not.
    """
    resolved = str(project_root.resolve())
    return hashlib.sha256(resolved.encode("utf-8")).hexdigest()[:16]


def run_slug(handle: str) -> str:
    """The bare `<date>-<agent>-<short-id>` form, refusing anything no run could carry.

    Validated as a GENERATED RUN ID, not merely as a safe path component, and validated
    BEFORE it is joined to anything. A check applied to the joined path has already lost:
    `run_dir(project, "../../elsewhere")` would have produced a real directory belonging to
    another project, and a containment check on the result would then be arguing with a path
    that should never have been built.

    The split is unambiguous despite the agent slug containing hyphens, because
    `_SHORT_ID_RE` forbids them in the short id: the LAST hyphen is always the one between
    agent and suffix. That is what lets a bare handle -- which names no agent of its own --
    still be checked by the same `validate_run_identity` that guards `generate_run_id`,
    rather than by a looser shape test that would admit `2026-07-30-a`.
    """
    slug = handle.removeprefix(RUN_ID_PREFIX)
    if (
        len(slug) <= _DATE_LENGTH
        or slug[_DATE_LENGTH] != "-"
        or not _DATE_SHAPE_RE.match(slug[:_DATE_LENGTH])
    ):
        raise ControlPlaneError(f"run handle must begin with a YYYY-MM-DD date, got {handle!r}")
    try:
        date.fromisoformat(slug[:_DATE_LENGTH])
    except ValueError as exc:
        raise ControlPlaneError(
            f"run handle must begin with a real YYYY-MM-DD date, got {slug[:_DATE_LENGTH]!r}"
        ) from exc
    agent, separator, short_id = slug[_DATE_LENGTH + 1 :].rpartition("-")
    if not separator:
        raise ControlPlaneError(
            f"run handle must be <date>-<agent>-<short-id>; {handle!r} carries no short id"
        )
    try:
        validate_run_identity(agent=agent, short_id=short_id)
    except RunRecordError as exc:
        raise ControlPlaneError(f"{handle!r} is not a run id that could have been generated: {exc}") from exc
    return slug


def project_metadata_path(project_root: Path) -> Path:
    """`project.json` -- the human label, as metadata beside the run directories."""
    return control_plane_root(project_root) / project_key(project_root) / "project.json"


def run_dir(project_root: Path, handle: str) -> Path:
    """One run's directory. Creates nothing: this is a path calculation.

    Layout, for the slices that fill it:
        <root>/<project-key>/project.json      the human label
        <root>/<project-key>/<run-slug>/       this directory
    """
    return control_plane_root(project_root) / project_key(project_root) / run_slug(handle)

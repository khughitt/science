"""The supervisor's before-capture, persisted OUTSIDE the run's repository.

Design §0 puts the control plane outside the actor. The baseline is control-plane
state: it fixes what the belief basis looked like before the run, so a baseline the
actor can reach is a baseline it can rewrite. It also cannot live in `runs/`, which
`load_run_records` restricts to flat `*.md` records.

This is NOT an in-flight run record. `AutonomousRunRecord` deliberately has no in-flight
shape: a supervisor that dies mid-run leaves no attestation, and its branch reads as
unattested rather than clean.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, ConfigDict, ValidationError
from science_model.autonomous_runs import PolicyIdentity, RunTier

from science_tool.graph.belief_basis import BasisSnapshot, SnapshotIntegrityError, load_snapshot


class BaselineError(ValueError):
    """The baseline could not be written, read, or trusted."""


class RunBaseline(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    run_id: str
    agent: str
    model: str
    tier: RunTier
    branch: str
    base_commit: str
    toolkit_revision: str
    policy_identity: PolicyIdentity
    started: datetime
    snapshot: BasisSnapshot


def _containment_spellings(path: Path) -> tuple[Path, Path]:
    """The two paths containment must be judged on: as spelled, and as resolved.

    `absolute()` normalizes `..` and the cwd without following symlinks; `resolve()`
    follows them. They answer different questions and BOTH must be outside the project:
    a path spelled inside the tree is a path whose symlinks the actor controls, and a
    path spelled outside may still land inside through one.
    """
    return (Path(os.path.normpath(path.absolute())), path.resolve())


def reject_baseline_inside_project(path: Path, project_root: Path) -> None:
    """Refuse any baseline path at or under `project_root`, by either spelling."""
    roots = _containment_spellings(project_root)
    for candidate in _containment_spellings(path):
        for root in roots:
            if candidate == root or root in candidate.parents:
                raise BaselineError(
                    f"baseline path {path} is inside the project root {project_root}. The run's "
                    "actor writes that tree, so a baseline stored there is not a baseline the "
                    "supervisor owns."
                )


def write_baseline(path: Path, baseline: RunBaseline, *, project_root: Path) -> None:
    """Write a baseline exactly once.

    Exclusive creation, not `write_text`: reusing a baseline path would discard the
    before-state of whatever run already owns it, and that capture is the only thing
    that can ever judge that run.
    """
    reject_baseline_inside_project(path, project_root)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("x", encoding="utf-8") as handle:
            handle.write(baseline.model_dump_json(indent=2))
    except FileExistsError as exc:
        raise BaselineError(
            f"{path} already holds a baseline; a run's before-state is written once"
        ) from exc
    except OSError as exc:
        raise BaselineError(f"could not write baseline to {path}: {exc}") from exc


def read_baseline(path: Path, *, project_root: Path) -> RunBaseline:
    """Load and re-verify a baseline. A baseline we cannot trust is never usable:
    every failure here becomes `unwired` upstream, not `clean`."""
    reject_baseline_inside_project(path, project_root)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    # UnicodeDecodeError is a ValueError, NOT an OSError -- omitting it lets a
    # non-UTF-8 baseline escape this function as a bare exception instead of becoming
    # the `unwired` disposition every unreadable baseline must produce.
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise BaselineError(f"could not read baseline {path}: {exc}") from exc
    try:
        baseline = RunBaseline.model_validate(payload)
    except ValidationError as exc:
        raise BaselineError(f"invalid baseline {path}: {exc}") from exc
    try:
        # Re-run Plan A's seal over the embedded snapshot: model_validate accepts the
        # envelope's shape but not its integrity, and a hand-edited baseline would
        # otherwise be compared against as if it were the real before-state.
        load_snapshot(json.loads(baseline.snapshot.model_dump_json()))
    except (SnapshotIntegrityError, ValidationError, json.JSONDecodeError) as exc:
        raise BaselineError(f"baseline {path} carries an untrustworthy snapshot: {exc}") from exc
    return baseline

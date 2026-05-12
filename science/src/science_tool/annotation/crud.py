# science/src/science_tool/annotation/crud.py
"""CRUD orchestrator powering ack/dismiss/fix.

See spec docs/plans/2026-05-11-annotation-system-p3.3-spec.md
§"Write concerns: crud.py".
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path
from typing import Optional

import click

from science_tool.annotation import lifecycle, query
from science_tool.annotation.io import (
    atomic_write_text,
    serialize_sidecar,
)
from science_tool.annotation.model import Sidecar, Status


# ---- Result + error -------------------------------------------------

@dataclass(frozen=True)
class CrudResult:
    sidecar_path: Path
    qualified_id: str       # rel-path-qualified, e.g. "notes/foo:a-7f3a"
    prior_status: Status
    new_status: Status


class CrudRefusedDirty(Exception):
    """Raised when the target sidecar has uncommitted changes (no force-dirty)."""

    def __init__(self, sidecar_path: Path) -> None:
        self.sidecar_path = sidecar_path
        super().__init__(
            f"refusing: {sidecar_path} has uncommitted changes; "
            "commit/stash or use --force-dirty"
        )


# ---- Public API -----------------------------------------------------

def apply_status_change(
    root: Path,
    id_arg: str,
    new_status: Status,
    *,
    actor: str,
    now: datetime,
    reason: Optional[str] = None,
    force_dirty: bool = False,
) -> CrudResult:
    """Resolve → guard dirty tree → mutate via lifecycle → atomic rewrite.

    Propagates query errors (AnnotationNotFound, AmbiguousAnnotationId)
    and lifecycle errors (ValueError) to the caller; CLI layer
    converts each to a ClickException with the right exit code.
    """
    resolved = query.resolve_id(root, id_arg)
    if not force_dirty and _sidecar_is_dirty(root, resolved.sidecar_path):
        raise CrudRefusedDirty(resolved.sidecar_path)

    mutated = lifecycle.mutate_status(
        resolved.annotation, new_status,
        actor=actor, now=now, reason=reason,
    )
    new_annotations = tuple(
        mutated if a.id == resolved.annotation.id else a
        for a in resolved.sidecar.annotations
    )
    new_sidecar = replace(resolved.sidecar, annotations=new_annotations)
    atomic_write_text(
        resolved.sidecar_path, serialize_sidecar(new_sidecar),
    )
    return CrudResult(
        sidecar_path=resolved.sidecar_path,
        qualified_id=f"{resolved.entity_relpath}:{resolved.annotation.id}",
        prior_status=resolved.annotation.status,
        new_status=new_status,
    )


# ---- Helpers --------------------------------------------------------

def _sidecar_is_dirty(root: Path, sidecar_path: Path) -> bool:
    """Return True if `sidecar_path` shows uncommitted changes under `root`.

    Returns False on non-git roots (the dirty-tree guard is a
    convenience, not a hard correctness requirement; verify uses the
    same convention).
    """
    try:
        proc = subprocess.run(
            ["git", "status", "--porcelain", "--", str(sidecar_path)],
            cwd=str(root),
            capture_output=True, text=True, check=False,
        )
    except (OSError, FileNotFoundError):
        return False
    if proc.returncode != 0:
        return False
    return bool(proc.stdout.strip())


def _resolve_actor(actor_opt: Optional[str], root: Path) -> str:
    """Resolve --actor: explicit flag → git config user.email → fail.

    No silent fallbacks. Raises ClickException when the chain fails
    so the CLI surface produces a friendly error.
    """
    if actor_opt:
        return actor_opt
    try:
        proc = subprocess.run(
            ["git", "config", "user.email"],
            cwd=str(root),
            capture_output=True, text=True, check=False,
        )
    except (OSError, FileNotFoundError) as exc:
        raise click.ClickException(
            "--actor required (no git available to read user.email)"
        ) from exc
    email = proc.stdout.strip()
    if proc.returncode != 0 or not email:
        raise click.ClickException(
            "--actor required (no git user.email available)"
        )
    return email

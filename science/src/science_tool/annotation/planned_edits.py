"""The shared plan-then-apply edit vocabulary.

Reconciliation grew this vocabulary first, and resynthesis reached across a module
boundary for six of its private names. This module owns them so no generic helper
stays owned by one workflow.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from science_model.frontmatter import atomic_write_text

from science_tool.dag.entity_frontmatter import publish_new_file
from science_tool.entities import EntityCommandError
from science_tool.entity_reservation import claim_number_in_dir


class PlannedEditDriftError(EntityCommandError):
    """A planned update's target changed on disk after planning; the batch refused.

    Subclasses `EntityCommandError` so a workflow's existing wrap set covers it, but it is
    named in each publish table so the inventory of what the write stage can raise stays
    complete rather than relying on inheritance to be noticed.
    """


@dataclass(frozen=True)
class PlannedFileEdit:
    path: Path
    reason: str
    before_sha256: str | None
    after_sha256: str
    final_text: str
    changed: bool
    operation: Literal["create", "update"] = "update"
    claim_number: int | None = None
    kind: str | None = None
    local_part: str | None = None


def path_string(path: Path) -> str:
    return path.as_posix()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def current_text(path: Path) -> str:
    """Read a planning pre-image WITHOUT universal-newline translation.

    `Path.read_text()` normalizes CRLF to LF before planning ever runs, so a CRLF body
    would be silently rewritten by an edit that never touched it -- and the round-trip
    guard would certify that rewrite as correct. `entities.py`'s preserving parser reads
    the same way.
    """
    with path.open("r", encoding="utf-8", newline="") as handle:
        return handle.read()


def plan_update(path: Path, final_text: str, reason: str) -> PlannedFileEdit:
    return plan_update_from_text(path, current_text(path), final_text, reason)


def plan_update_from_text(
    path: Path, before_text: str, final_text: str, reason: str
) -> PlannedFileEdit:
    """Plan an update against the exact pre-image its post-image was derived from."""
    return PlannedFileEdit(
        path=path,
        reason=reason,
        before_sha256=sha256_text(before_text),
        after_sha256=sha256_text(final_text),
        final_text=final_text,
        changed=before_text != final_text,
    )


def plan_create(path: Path, final_text: str, reason: str) -> PlannedFileEdit:
    """A planned create asserts the destination is absent rather than reading it."""
    return PlannedFileEdit(
        path=path,
        reason=reason,
        before_sha256=None,
        after_sha256=sha256_text(final_text),
        final_text=final_text,
        changed=True,
        operation="create",
    )


def plan_create_or_update(path: Path, final_text: str, reason: str) -> PlannedFileEdit:
    """Dispatch on existence at PLAN time.

    Resynthesis plans resume snapshots and replacement propositions that may or may not
    exist yet. Under one publish primitive that distinction has to be decided somewhere,
    and plan time is where the pre-image is read anyway.
    """
    return (
        plan_update(path, final_text, reason)
        if path.exists()
        else plan_create(path, final_text, reason)
    )


def plan_numeric_create(
    path: Path,
    final_text: str,
    reason: str,
    *,
    kind: str,
    local_part: str,
    number: int,
) -> PlannedFileEdit:
    return PlannedFileEdit(
        path=path,
        reason=reason,
        before_sha256=None,
        after_sha256=sha256_text(final_text),
        final_text=final_text,
        changed=True,
        operation="create",
        claim_number=number,
        kind=kind,
        local_part=local_part,
    )


def publish_edit(edit: PlannedFileEdit, *, project_root: Path) -> None:
    """Publish one planned edit. The write stage's WHOLE vocabulary.

    Three publishes, three failure modes:

    | publish        | raises                              |
    |----------------|-------------------------------------|
    | update         | PlannedEditDriftError, OSError      |
    | create         | EntityWriteError, OSError           |
    | numeric create | EntityCommandError (drift), OSError |

    The create guarantee is stronger than the update guarantee, and the difference is real:
    the exclusive open("x") + os.link publish is atomic against a concurrent creator, so it
    can never clobber. The update refuses drift OBSERVED by the check immediately below --
    compare-then-os.replace leaves a narrow TOCTOU window. The check shortens the exposure
    from the whole planning phase to a few syscalls; it does not eliminate it.
    """
    if edit.operation == "create":
        if edit.claim_number is not None:
            assert edit.kind is not None and edit.local_part is not None
            claim_number_in_dir(
                project_root, edit.kind, edit.claim_number, edit.local_part, edit.final_text
            )
            return
        publish_new_file(edit.path, edit.final_text)
        return

    assert edit.before_sha256 is not None
    if sha256_text(current_text(edit.path)) != edit.before_sha256:
        raise PlannedEditDriftError(
            f"refusing to publish {path_string(edit.path)}: it changed on disk after this "
            f"batch was planned; re-run the preview"
        )
    atomic_write_text(edit.path, edit.final_text)


def edits_for_planned_texts(
    planned_text_by_path: Mapping[Path, str],
    original_text_by_path: Mapping[Path, str],
    creates: Mapping[Path, tuple[str, str, int] | None],
    *,
    reason_create: str,
    reason_update: str,
) -> dict[Path, PlannedFileEdit]:
    """One PlannedFileEdit per path, AFTER composition.

    `original_text_by_path` retains the exact first read used for composition, so edit
    construction never accepts a concurrent change as the pre-image of a stale post-image.

    `creates` maps a path to `(kind, local_part, number)` for a numeric create, or to `None`
    for a slug-addressed create. Paths absent from it are updates.
    """
    edits: dict[Path, PlannedFileEdit] = {}
    for path, post_image in planned_text_by_path.items():
        if path in creates:
            numeric = creates[path]
            edits[path] = (
                plan_numeric_create(
                    path,
                    post_image,
                    reason_create,
                    kind=numeric[0],
                    local_part=numeric[1],
                    number=numeric[2],
                )
                if numeric is not None
                else plan_create(path, post_image, reason_create)
            )
        else:
            edits[path] = plan_update_from_text(
                path, original_text_by_path[path], post_image, reason_update
            )
    return edits


_SIDE_STORE_REASONS = frozenset({"promotion_sidecar", "prose_decomposition_index"})


def publish_order(edits: Iterable[PlannedFileEdit]) -> list[PlannedFileEdit]:
    """Entity edits first, side stores last; within each group, by path.

    A write-stage failure can strand a partially applied batch (§4.2 claims no rollback), so
    WHICH half lands first is a real contract. Entity first means the next run sees the
    entity and can recover the index from it; index first means an index row pointing at a
    record that was never written.
    """
    return sorted(edits, key=lambda e: (e.reason in _SIDE_STORE_REASONS, e.path.as_posix()))


def changed_and_noop_paths(
    edits: Sequence[PlannedFileEdit],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    changed = tuple(path_string(edit.path) for edit in edits if edit.changed)
    noop = tuple(path_string(edit.path) for edit in edits if not edit.changed)
    return changed, noop

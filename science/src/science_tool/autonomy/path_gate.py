"""Layer 1 of design §5: the syntactic, default-deny path gate.

Complete by construction -- anything not explicitly allowed is denied -- and its
failure mode is over-restriction. It does NOT prove belief-neutrality; that is Layer 2
(`graph/belief_basis.py`, Plan A), which is authoritative precisely because it does not
depend on this allowlist being correct.

Pure: no filesystem, no git, no project state. The change set arrives already built.
"""

from __future__ import annotations

from pathlib import PurePosixPath

from pydantic import BaseModel, ConfigDict
from science_model.autonomous_runs import RunTier

from science_tool.autonomy.changes import ChangeSet, ChangeType, PathChange
from science_tool.autonomy.policy import denial_reason, is_creation_allowed, is_field_allowed


class GateInputError(ValueError):
    """The gate was handed an input it cannot decide over."""


class Denial(BaseModel):
    """One reason the run's write surface exceeded its tier."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    path: str
    field: str | None
    reason: str


class GateVerdict(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    allowed: bool
    denials: tuple[Denial, ...]


def _validate_report_path(report_path: str | None) -> str | None:
    if report_path is None:
        return None
    candidate = PurePosixPath(report_path)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise GateInputError(
            f"report_path must be a repository-relative path with no parent traversal, got {report_path!r}"
        )
    return str(candidate)


def _denials_for(change: PathChange) -> list[Denial]:
    if change.entity_kind is None:
        return [Denial(path=change.path, field=None, reason=denial_reason(change.path))]

    if change.change_type is ChangeType.DELETED:
        return [
            Denial(
                path=change.path,
                field=None,
                reason=f"entity deletion is not permitted for kind {change.entity_kind!r}",
            )
        ]

    if change.change_type is ChangeType.ADDED:
        # Creation has its own allowlist (design §4): a created entity can change
        # ANOTHER entity's belief basis, so it is not "editing a file with no
        # before-value". With CREATION_ALLOWLIST empty, every creation lands here.
        denied = [f for f in change.fields if not is_creation_allowed(change.entity_kind, f)]
        if not denied and change.fields:
            return []
        return [
            Denial(
                path=change.path,
                field=None,
                reason=f"entity creation is not permitted for kind {change.entity_kind!r}",
            )
        ]

    if not change.fields:
        # git reports an executable-bit or other metadata-only change as `M` with
        # identical blobs, and frontmatter key REORDERING parses to an identical dict.
        # Both reach here with no changed field. Allowing them would let repository
        # metadata escape the default-deny surface entirely -- so an unexplained
        # modification is denied, like anything else the gate cannot account for.
        return [
            Denial(
                path=change.path,
                field=None,
                reason="modified with no field-level change (file mode or byte-level edit); "
                "nothing about this modification is on an allowlist",
            )
        ]

    return [
        Denial(
            path=change.path,
            field=field,
            reason=f"field {field!r} is not on the {change.entity_kind!r} allowlist (default-deny)",
        )
        for field in change.fields
        if not is_field_allowed(change.entity_kind, field)
    ]


def evaluate(
    change_set: ChangeSet, *, tier: RunTier, report_path: str | None = None
) -> GateVerdict:
    """Decide whether every change in `change_set` is inside `tier`'s write surface.

    `report_path` is the run's own report, supplied by the supervisor (design §0) -- it
    is the ONLY path `report-only` may write, and it is allowed in `belief-neutral` too.
    """
    if tier is not RunTier.REPORT_ONLY and tier is not RunTier.BELIEF_NEUTRAL:
        raise GateInputError(f"tier must be a supported RunTier member, got {tier!r}")

    allowed_report = _validate_report_path(report_path)

    denials: list[Denial] = []
    for change in change_set.changes:
        if allowed_report is not None and change.path == allowed_report:
            continue
        if tier is RunTier.REPORT_ONLY:
            denials.append(
                Denial(
                    path=change.path,
                    field=None,
                    reason="tier 'report-only' may write only the run's own report path",
                )
            )
            continue
        denials.extend(_denials_for(change))

    ordered = tuple(sorted(denials, key=lambda d: (d.path, d.field or "")))
    return GateVerdict(allowed=not ordered, denials=ordered)

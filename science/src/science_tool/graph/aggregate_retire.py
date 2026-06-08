"""Plan + apply `entities.yaml` retirement (design §3, Phase 3b).

The planner is pure over the 3a classification + the compiled model; it never
mutates. It is scoped to `entities.yaml` declarations only (the §3.1 firewall —
`terms.yaml` and single-type aggregates are Phase-4/out of scope). Promotion is
id-preserving: the target is computed from the entity path policy, and a
non-conforming id is rejected, never renumbered. The executor (apply_retirement)
lives in the same module and owns all file mutation.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING

from science_tool.datapackage_promote import _is_safe_slug
from science_tool.entities import EntityCommandError, local_part_conforms, resolve_path_policy
from science_tool.graph.aggregate_triage import AggregateBucket, AggregateRowTriage

if TYPE_CHECKING:
    from science_tool.graph.sources import ProjectSources

_ENTITIES_FILE = "entities.yaml"


class RetireAction(str, Enum):
    PROMOTE = "promote"
    DELETE = "delete"


@dataclass(frozen=True, slots=True)
class PlannedRow:
    triage: AggregateRowTriage
    action: RetireAction
    source_path: str  # the entities.yaml file (declaration source_ref.path), project-root-relative
    line: int  # entry index within that file
    target_path: str | None  # PROMOTE: policy.root/<local>.md; reconcile: the existing owner file; DELETE: None


@dataclass(frozen=True, slots=True)
class RetirementPlan:
    promote: tuple[PlannedRow, ...]
    delete: tuple[PlannedRow, ...]
    reconcile: tuple[PlannedRow, ...]  # shadow rows to marker-check (promote_coined only); §3.5 step 2
    rejected: tuple[tuple[AggregateRowTriage, str], ...]


def _real_owner_path(sources: "ProjectSources", canonical_id: str) -> str | None:
    """The path of the non-aggregate, non-deprecated owner of `canonical_id`, if any."""
    for decl in sources.identity_declarations:
        if (
            decl.canonical_id == canonical_id
            and decl.adapter != "aggregate"
            and not decl.deprecated
            and decl.source_ref is not None
        ):
            return decl.source_ref.path
    return None


def plan_retirement(
    project_root: Path,
    sources: "ProjectSources",
    rows: list[AggregateRowTriage],
    *,
    promote_coined: bool,
    delete_cruft: bool,
    delete_shadow: bool,
) -> RetirementPlan:
    triage_by_id = {t.canonical_id: t for t in rows}
    action_for: dict[AggregateBucket, RetireAction | None] = {
        AggregateBucket.COINED: RetireAction.PROMOTE if promote_coined else None,
        AggregateBucket.CRUFT: RetireAction.DELETE if delete_cruft else None,
        AggregateBucket.SHADOW: RetireAction.DELETE if delete_shadow else None,
    }
    promote: list[PlannedRow] = []
    delete: list[PlannedRow] = []
    reconcile: list[PlannedRow] = []
    rejected: list[tuple[AggregateRowTriage, str]] = []

    for meta in sources.aggregate_rows:
        if Path(meta.path).name != _ENTITIES_FILE:
            continue  # §3.1 firewall: never touch terms.yaml / single-type aggregates
        triage = triage_by_id.get(meta.canonical_id)
        if triage is None:
            continue
        # Recovery candidate: a shadow whose owner we may have written in a prior run.
        if promote_coined and triage.bucket is AggregateBucket.SHADOW:
            owner = _real_owner_path(sources, meta.canonical_id)
            if owner is not None:
                reconcile.append(PlannedRow(triage, RetireAction.DELETE, meta.path, meta.line, owner))
        action = action_for.get(triage.bucket)
        if action is None:
            continue
        if action is RetireAction.DELETE:
            delete.append(PlannedRow(triage, action, meta.path, meta.line, None))
            continue
        # PROMOTE: resolve the policy and require an id-preserving, conforming, safe target.
        kind = meta.kind
        local_part = meta.canonical_id.split(":", 1)[1] if ":" in meta.canonical_id else meta.canonical_id
        try:
            policy = resolve_path_policy(kind, project_root=project_root)
        except EntityCommandError:
            rejected.append((triage, f"no path policy for kind {kind!r}"))
            continue
        # Conformance ALWAYS runs — including for slug kinds: a slug-strategy id must
        # still be a valid slug (_SLUG_RE rejects e.g. `bad_slug`, `Trailing-`). 3b is
        # id-preserving, so a non-conforming id is rejected, never renumbered.
        if not local_part_conforms(kind, local_part, project_root=project_root):
            rejected.append((triage, f"id {meta.canonical_id!r} does not conform to {policy.strategy} strategy"))
            continue
        if not _is_safe_slug(local_part):  # path-safety belt (no `..`); redundant for slug but cheap
            rejected.append((triage, "unsafe slug"))
            continue
        target = (policy.root / f"{local_part}.md").as_posix()
        promote.append(PlannedRow(triage, action, meta.path, meta.line, target))

    return RetirementPlan(tuple(promote), tuple(delete), tuple(reconcile), tuple(rejected))

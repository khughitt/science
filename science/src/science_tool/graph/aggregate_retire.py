"""Plan + apply aggregate-manifest retirement (design §3, Phase 3b/4a).

The planner is pure over the 3a classification + the compiled model; it never
mutates. It is scoped to the multi-type aggregate files (`entities.yaml`,
`terms.yaml`); single-type aggregates (`doc/<plural>/<plural>.{json,yaml}`) are
out of scope. Promotion is id-preserving: the target is computed from the entity
path policy, and a non-conforming id is rejected, never renumbered. The executor
(apply_retirement) lives in the same module and owns all file mutation.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING

import yaml

from science_tool.datapackage_promote import _is_safe_slug
from science_tool.entities import EntityCommandError, local_part_conforms, resolve_path_policy
from science_tool.graph.aggregate_triage import AggregateBucket, AggregateRowTriage
from science_tool.graph.decision_log import DecisionLogIndex, render_owner_file
from science_tool.graph.storage_adapters.aggregate import MULTI_TYPE_AGGREGATE_ROOT_KEYS, multi_type_root_key

if TYPE_CHECKING:
    from science_tool.graph.sources import AggregateRowMeta, ProjectSources


class RetireAction(str, Enum):
    PROMOTE = "promote"
    DELETE = "delete"


@dataclass(frozen=True, slots=True)
class PlannedRow:
    triage: AggregateRowTriage
    action: RetireAction
    source_path: str  # the aggregate file (entities.yaml/terms.yaml) declaration source_ref.path, project-root-relative
    line: int  # entry index within that file
    target_path: str | None  # PROMOTE: policy.root/<local>.md; reconcile: the existing owner file; DELETE: None


@dataclass(frozen=True, slots=True)
class RetirementPlan:
    promote: tuple[PlannedRow, ...]
    delete: tuple[PlannedRow, ...]
    # A SHADOW row may appear in BOTH reconcile AND delete when promote_coined and
    # delete_shadow are both set. This is intentional: reconcile is marker-gated
    # crash-recovery; delete is unconditional. The executor deduplicates (source_path,
    # line) via a set, so the aggregate entry is only dropped once.
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


def _promote_target(meta: "AggregateRowMeta", project_root: Path) -> tuple[str | None, str | None]:
    """Resolve an id-preserving promote target, or (None, reject_reason).

    Conformance ALWAYS runs (3b is id-preserving; a non-conforming id is
    rejected, never renumbered). Path-safety is policy-aware: slug/citekey/numeric
    ids go through the lowercase `_is_safe_slug` belt; verbatim ids (which
    `_is_safe_slug` would wrongly reject for being uppercase) use an explicit `..`
    traversal guard instead, since `_VERBATIM_RE` already excludes slashes.
    """
    kind = meta.kind
    local_part = meta.canonical_id.split(":", 1)[1] if ":" in meta.canonical_id else meta.canonical_id
    try:
        policy = resolve_path_policy(kind, project_root=project_root)
    except EntityCommandError:
        return None, f"no path policy for kind {kind!r}"
    # Path-safety belt, policy-aware. `_is_safe_slug` is lowercase-only and would
    # reject a verbatim id like `D10`. For verbatim, check the traversal guard first
    # (before conformance) so the rejection reason is explicit about the safety
    # concern. Other strategies keep the lowercase slug firewall after conformance.
    if policy.strategy == "verbatim":
        if ".." in local_part:
            return None, "unsafe local part"
    if not local_part_conforms(kind, local_part, project_root=project_root):
        return None, f"id {meta.canonical_id!r} does not conform to {policy.strategy} strategy"
    if policy.strategy != "verbatim" and not _is_safe_slug(local_part):
        return None, "unsafe local part"
    return (policy.root / f"{local_part}.md").as_posix(), None


def plan_retirement(
    project_root: Path,
    sources: "ProjectSources",
    rows: list[AggregateRowTriage],
    *,
    promote_coined: bool,
    delete_cruft: bool,
    delete_shadow: bool,
    promote_decisions: bool = False,
    decision_index: DecisionLogIndex | None = None,
) -> RetirementPlan:
    triage_by_ref = {(t.path, t.line): t for t in rows}
    action_for: dict[AggregateBucket, RetireAction | None] = {
        AggregateBucket.COINED: RetireAction.PROMOTE if promote_coined else None,
        AggregateBucket.CRUFT: RetireAction.DELETE if delete_cruft else None,
        AggregateBucket.SHADOW: RetireAction.DELETE if delete_shadow else None,
    }
    idx = decision_index if decision_index is not None else DecisionLogIndex({})
    promote: list[PlannedRow] = []
    delete: list[PlannedRow] = []
    reconcile: list[PlannedRow] = []
    rejected: list[tuple[AggregateRowTriage, str]] = []

    for meta in sources.aggregate_rows:
        if Path(meta.path).name not in MULTI_TYPE_AGGREGATE_ROOT_KEYS:
            continue  # firewall: only the multi-type files (entities.yaml/terms.yaml); never single-type aggregates
        triage = triage_by_ref.get((meta.path, meta.line))
        if triage is None:
            continue
        # Decision rows are governed by the injected index, NOT the bucket. The
        # triage classifier sends migration:* sources to CRUFT before the
        # decision-log rule, so real decisions (e.g. D9/D10) arrive bucketed
        # CRUFT — they must promote on an index hit and never be cruft-deleted.
        if meta.kind == "decision":
            if not promote_decisions:
                continue  # untouched (3b parity); delete_cruft never reaches here
            if idx.get(meta.canonical_id) is None:
                rejected.append((triage, f"no decision-log section for {meta.canonical_id}"))
                continue
            target, reason = _promote_target(meta, project_root)
            if target is None:
                rejected.append((triage, reason or "unpromotable"))
                continue
            promote.append(PlannedRow(triage, RetireAction.PROMOTE, meta.path, meta.line, target))
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
        # PROMOTE: resolve an id-preserving, conforming, safe target.
        target, reason = _promote_target(meta, project_root)
        if target is None:
            rejected.append((triage, reason or "unpromotable"))
            continue
        promote.append(PlannedRow(triage, action, meta.path, meta.line, target))

    return RetirementPlan(tuple(promote), tuple(delete), tuple(reconcile), tuple(rejected))


@dataclass(frozen=True, slots=True)
class RetirementReport:
    promoted: tuple[str, ...]
    deleted: tuple[str, ...]
    rejected: tuple[tuple[str, str], ...]
    skipped: tuple[tuple[str, str], ...]
    files_rewritten: tuple[str, ...]
    dry_run: bool


_STUB_BODY = "<!-- promoted from an aggregate manifest by substrate retirement; add definition -->\n"


def _read_entries(project_root: Path, rel: str) -> list[dict]:
    data = yaml.safe_load((project_root / rel).read_text(encoding="utf-8")) or {}
    root_key = multi_type_root_key(Path(rel).name)
    assert root_key is not None, f"not a multi-type aggregate file: {rel}"
    return data.get(root_key) or []


def _front_matter(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---", 4)
    if end == -1:
        return {}
    return yaml.safe_load(text[4:end]) or {}


def _owner_text(
    canonical_id: str,
    kind: str,
    title: str,
    description: object,
    profile: object,
    *,
    promoted_from: str,
) -> str:
    """Render an id-preserving owner file.

    Identity (`canonical_id`/`kind`) comes from the compiled model (the caller
    passes the triage values), not the raw aggregate row — the two multi-type
    files differ (entities.yaml: explicit canonical_id/kind; terms.yaml: `id` +
    inferred kind). A non-empty string `description` becomes the owner body (the
    §B5 "line of definition"); anything else falls back to the stub body.
    """
    fm: dict[str, object] = {"id": canonical_id, "type": kind, "title": title}
    if isinstance(profile, str) and profile:
        fm["profile"] = profile
    fm["promoted_from"] = promoted_from
    body = description.rstrip("\n") + "\n" if isinstance(description, str) and description else _STUB_BODY
    return "---\n" + yaml.safe_dump(fm, sort_keys=False, allow_unicode=True) + "---\n\n" + body


def _rewrite_aggregate(project_root: Path, rel: str, drop: set[int]) -> None:
    path = project_root / rel
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    root_key = multi_type_root_key(path.name)
    assert root_key is not None, f"not a multi-type aggregate file: {rel}"
    items = data.get(root_key) or []
    data[root_key] = [row for i, row in enumerate(items) if i not in drop]
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")


def apply_retirement(
    project_root: Path,
    plan: RetirementPlan,
    *,
    dry_run: bool,
    decision_index: DecisionLogIndex | None = None,
) -> RetirementReport:
    idx = decision_index if decision_index is not None else DecisionLogIndex({})
    promoted: list[str] = []
    deleted: list[str] = []
    rejected: list[tuple[str, str]] = [(t.canonical_id, reason) for t, reason in plan.rejected]
    skipped: list[tuple[str, str]] = []
    drop_by_file: dict[str, set[int]] = defaultdict(set)
    entries_cache: dict[str, list[dict]] = {}

    def entries(rel: str) -> list[dict]:
        if rel not in entries_cache:
            entries_cache[rel] = _read_entries(project_root, rel)
        return entries_cache[rel]

    # 1. Promote / reconcile-on-existing-marker.
    for pr in plan.promote:
        entry = entries(pr.source_path)[pr.line]
        title = entry.get("title")
        if not title:
            rejected.append((pr.triage.canonical_id, "missing required field title"))
            continue
        assert pr.target_path is not None
        target = project_root / pr.target_path
        if target.exists():
            if _front_matter(target).get("promoted_from") == pr.source_path:
                # Prior interrupted run wrote it; complete the half-done promote.
                promoted.append(pr.triage.canonical_id)
                drop_by_file[pr.source_path].add(pr.line)
            else:
                skipped.append((pr.triage.canonical_id, "target exists (foreign owner)"))
            continue
        if not dry_run:
            target.parent.mkdir(parents=True, exist_ok=True)
            if pr.triage.kind == "decision":
                section = idx.get(pr.triage.canonical_id)
                if section is None:
                    # Planner guaranteed a hit; be explicit rather than write a bad owner.
                    rejected.append((pr.triage.canonical_id, "decision section missing at apply time"))
                    continue
                text = render_owner_file(section, promoted_from=pr.source_path)
            else:
                text = _owner_text(
                    pr.triage.canonical_id,
                    pr.triage.kind,
                    title,
                    entry.get("description"),
                    entry.get("profile"),
                    promoted_from=pr.source_path,
                )
            target.write_text(text, encoding="utf-8")
        promoted.append(pr.triage.canonical_id)
        drop_by_file[pr.source_path].add(pr.line)

    # 2. Crash-recovery sweep (promote_coined only): a shadow whose owner bears OUR
    #    marker is a completed prior promotion — delete the stranded entry.
    for pr in plan.reconcile:
        assert pr.target_path is not None  # the existing owner file path
        owner = project_root / pr.target_path
        if owner.exists() and _front_matter(owner).get("promoted_from") == pr.source_path:
            if pr.triage.canonical_id not in promoted:
                promoted.append(pr.triage.canonical_id)
            drop_by_file[pr.source_path].add(pr.line)

    # 3. Deletes.
    for pr in plan.delete:
        if pr.triage.canonical_id not in promoted:
            deleted.append(pr.triage.canonical_id)
        drop_by_file[pr.source_path].add(pr.line)

    # 4. Rewrite each affected aggregate file once.
    files_rewritten = sorted(drop_by_file)
    if not dry_run:
        for rel in files_rewritten:
            _rewrite_aggregate(project_root, rel, drop_by_file[rel])

    return RetirementReport(
        tuple(promoted),
        tuple(deleted),
        tuple(rejected),
        tuple(skipped),
        tuple(files_rewritten),
        dry_run,
    )

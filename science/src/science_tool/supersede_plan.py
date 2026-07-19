from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Callable

from pydantic import BaseModel, ConfigDict

from science_tool.consolidation import (
    SupersessionDecisionMaterial, SupersessionError, _disposition_report, _prepare_supersession,
    build_decision_material, build_supersedes_graph_from_material, decision_digest,
)
from science_tool.plan_common import (
    ExplicitSupersessionIds, PathEscape, PathTransition, StagingError, StateFingerprint,
    SupersedeSelection, SurfaceMismatch, assert_same_surface, assert_staging_unique, fingerprint,
    matches, resolve_within, rollback_transitions, snapshot_paths, staged_write,
)

_SUPERSEDE_PLAN_SCHEMA = 1


class SupersedeApplyError(RuntimeError):
    pass


class SupersededChainReport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    survivor: str
    members: list[str]
    linear: bool


class NonLinearReport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    nodes: list[str]
    reason: str


class SkippedKind(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    kind: str


class InvalidRelation(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str
    path: str
    subject: str
    predicate: str
    object: str
    message: str


class TargetReport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    superseder: str
    path: str
    reason: str


class UnbackedInverse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    superseder: str
    reason: str


class SupersedePreviewReport(BaseModel):
    model_config = ConfigDict(extra="forbid")
    chains: list[SupersededChainReport]
    non_linear: list[NonLinearReport]
    to_mark: list[str]
    skipped_kinds: list[SkippedKind]
    to_repair: list[str]
    invalid_relations: list[InvalidRelation]
    archived_targets: list[TargetReport]
    unmanaged_targets: list[TargetReport]
    unbacked_inverses: list[UnbackedInverse]


class SupersedePlan(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: int
    project_root: str
    material_version: int
    preview_date: str
    selection: SupersedeSelection
    decision_inputs_sha256: str
    to_mark: list[str]
    to_repair: list[str]
    writes: list[PathTransition]
    preview_report: SupersedePreviewReport


def _selected_ids(selection: SupersedeSelection) -> frozenset[str] | None:
    if isinstance(selection, ExplicitSupersessionIds):
        return frozenset(selection.ids)
    return None  # AllSupersessionMembers -- no allowlist, every derivable member


def _fingerprint_of_text(text: str, *, mode: int | None) -> StateFingerprint:
    if mode is None:
        raise ValueError("a staged entity-rewrite requires a concrete file mode")
    return StateFingerprint(existed=True, type="file",
                            content_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
                            mode=mode, symlink_target=None)


def plan_supersede(
    project_root: Path, *, selection: SupersedeSelection, preview_date: str
) -> SupersedePlan:
    """Preview entry point: load the decision material ONCE, then delegate to the derivation.

    `derive_supersede_plan` is the reused half -- Gate B calls it with the exact material Gate A
    already authenticated, so a preview built here and a plan re-derived there run the identical
    derivation over the identical input.
    """
    project_root = project_root.resolve()
    material = build_decision_material(project_root)
    return derive_supersede_plan(project_root, material, selection=selection, preview_date=preview_date)


def derive_supersede_plan(
    project_root: Path,
    material: SupersessionDecisionMaterial,
    *,
    selection: SupersedeSelection,
    preview_date: str,
) -> SupersedePlan:
    """Derive the plan from an ALREADY-BUILT decision material -- no second load of decision
    inputs. Gate B passes the material it just authenticated in Gate A, so the digest surface IS
    the derivation surface: this function must never call `build_decision_material` or
    `load_supersession_inputs` itself, or a second, possibly-drifted load would defeat the gate.

    The disposition (`to_mark`/`to_repair`/the preview report) is a pure function of `material` via
    `build_supersedes_graph_from_material` + `_disposition_report` -- no filesystem read. Rendering
    each member's postimage still reads that member's CURRENT file (the body/other fields are not
    decision-bearing and are not part of the material), via `_prepare_supersession`, the same
    renderer `mark_superseded --apply` uses, threaded with `preview_date` so a saved plan's frozen
    `updated:` matches what a later apply of the same plan would stamp.
    """
    project_root = project_root.resolve()
    graph = build_supersedes_graph_from_material(material)
    ids = _selected_ids(selection)
    # Disposition from the MATERIAL-derived graph -- no second filesystem load.
    report_dict = _disposition_report(graph, ids=ids)
    to_mark = list(report_dict["to_mark"])
    to_repair = list(report_dict["to_repair"])

    writes: list[PathTransition] = []
    for member in (*to_mark, *to_repair):
        prepared = _prepare_supersession(project_root, graph, member, preview_date=preview_date)
        rel = prepared.path.relative_to(project_root).as_posix()
        pre = fingerprint(prepared.path)
        # A supersession rewrite REPLACES an existing file, so post preserves the live mode.
        post = _fingerprint_of_text(prepared.text, mode=pre.mode)
        writes.append(PathTransition(role="entity-rewrite", rel_path=rel, pre=pre, post=post,
                                     postimage=prepared.text))

    preview_report = SupersedePreviewReport(
        chains=report_dict["chains"], non_linear=report_dict["non_linear"],
        to_mark=to_mark, skipped_kinds=report_dict["skipped_kinds"], to_repair=to_repair,
        invalid_relations=report_dict["invalid_relations"],
        archived_targets=report_dict["archived_targets"],
        unmanaged_targets=report_dict["unmanaged_targets"],
        unbacked_inverses=report_dict["unbacked_inverses"],
    )
    return SupersedePlan(
        schema_version=1, project_root=str(project_root), material_version=material.material_version,
        preview_date=preview_date, selection=selection,
        decision_inputs_sha256=decision_digest(material),
        to_mark=to_mark, to_repair=to_repair, writes=writes, preview_report=preview_report,
    )


def apply_supersede_plan(project_root: Path, plan: SupersedePlan, *, staging_token: str,
                         _fault: Callable[[str], None] | None = None) -> dict:
    """Replay a saved `SupersedePlan` after three independent authorization layers pass, then
    execute through the staged-write primitive with atomic rollback on any failure.

    Gate order is load-bearing (design §9) and MUST NOT be reordered or merged:
      structural -> Gate A (decision digest) -> Gate B (full re-derivation from the SAME,
      Gate-A-verified material) -> pre-state -> execute (snapshot, staged_write, post-verify,
      rollback-on-failure).

    `build_decision_material` is called EXACTLY ONCE, in Gate A. Gate B re-derives the whole plan
    via `derive_supersede_plan(project_root, material, ...)`, reusing that same material rather than
    loading decision inputs a second time -- so the digest surface Gate A authenticated IS the
    surface Gate B derives from.
    """

    def fault(label: str) -> None:
        if _fault is not None:
            _fault(label)  # test-only kill seam; a BaseException here bypasses rollback

    project_root = project_root.resolve()
    if plan.schema_version != _SUPERSEDE_PLAN_SCHEMA:
        raise SupersedeApplyError(
            f"unsupported plan schema_version {plan.schema_version} (this tool writes "
            f"{_SUPERSEDE_PLAN_SCHEMA})")
    if plan.project_root != str(project_root):
        raise SupersedeApplyError("plan project_root does not match")

    # Structural -- containment, canonical paths, staging uniqueness, bijection (before any FS write
    # or digest/derivation work).
    members = [*plan.to_mark, *plan.to_repair]
    try:
        targets = [resolve_within(project_root, w.rel_path) for w in plan.writes]
        assert_staging_unique(project_root, targets, staging_token)
    except (PathEscape, StagingError) as exc:
        raise SupersedeApplyError(str(exc)) from exc
    if len({w.rel_path for w in plan.writes}) != len(plan.writes):
        raise SupersedeApplyError("duplicate write paths")
    if len(members) != len(set(members)) or len(members) != len(plan.writes):
        raise SupersedeApplyError("writes/disposition are not a bijection")
    # `prepared.path == w.rel_path` (design §9) is guaranteed by construction: `derive_supersede_plan`
    # builds each `PathTransition.rel_path` directly from `_prepare_supersession`'s returned path
    # (`rel = prepared.path.relative_to(project_root).as_posix()`), and Gate B's `assert_same_surface`
    # below re-verifies `plan.writes` against a freshly re-derived `expected.writes` built the same
    # way -- so a plan whose `rel_path` diverged from what re-derivation would produce is caught there.

    # Gate A -- rebuild the decision material ONCE, compare version + digest against the plan.
    material = build_decision_material(project_root)
    if material.material_version != plan.material_version:
        raise SupersedeApplyError("material_version mismatch")
    if decision_digest(material) != plan.decision_inputs_sha256:
        raise SupersedeApplyError("corpus changed since preview (decision digest mismatch)")

    # Gate B -- re-derive the WHOLE plan from the GATE-A-VERIFIED material (no second decision
    # load): `derive_supersede_plan` never calls `build_decision_material` itself, so the digest
    # surface authenticated above IS the derivation surface.
    try:
        expected = derive_supersede_plan(project_root, material, selection=plan.selection,
                                         preview_date=plan.preview_date)
    except SupersessionError as exc:
        raise SupersedeApplyError(str(exc)) from exc
    try:
        assert_same_surface(plan.writes, expected.writes)
    except SurfaceMismatch as exc:
        raise SupersedeApplyError(f"declared writes differ from re-derived: {exc}") from exc
    if expected.preview_report != plan.preview_report:
        raise SupersedeApplyError("re-derived preview report differs from the plan")
    if expected.to_mark != plan.to_mark or expected.to_repair != plan.to_repair:
        raise SupersedeApplyError("re-derived disposition differs from the plan")
    rpt = expected.preview_report
    if rpt.invalid_relations or rpt.unbacked_inverses:
        raise SupersedeApplyError("corpus-wide blockers present; refusing")

    # Pre-state gate -- do NOT write until every target's live state matches its frozen pre.
    for target, w in zip(targets, plan.writes, strict=True):
        if not matches(w.pre, target):
            raise SupersedeApplyError(f"pre-state changed for {w.rel_path}")

    # Execute -- snapshot every target, stage+commit each write, verify post-state, roll back
    # atomically on any failure.
    snap = snapshot_paths(targets)
    try:
        for target, w in zip(targets, plan.writes, strict=True):
            assert w.postimage is not None  # entity-rewrite role always carries a postimage
            assert w.post.mode is not None  # post.existed=True fingerprint always carries a mode
            staged_write(target, w.postimage, w.post.mode, staging_token, target_pre=w.pre)
            fault(f"written:{w.rel_path}")  # kill boundary: after each entity write
        for target, w in zip(targets, plan.writes, strict=True):
            if not matches(w.post, target):
                raise SupersedeApplyError(f"post-state verification failed for {w.rel_path}")
    except Exception as exc:
        rollback_transitions(plan.writes, project_root, snap)  # may raise RollbackHalt (propagates)
        if isinstance(exc, SupersedeApplyError):
            raise
        # A staged-write StagingError etc. becomes a SupersedeApplyError once the corpus is restored.
        raise SupersedeApplyError(f"apply failed and rolled back: {exc}") from exc
    return {"applied": list(plan.to_mark), "repaired": list(plan.to_repair)}

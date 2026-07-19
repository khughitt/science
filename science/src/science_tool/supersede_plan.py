from __future__ import annotations

import hashlib
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from science_tool.consolidation import (
    SupersessionDecisionMaterial, _disposition_report, _prepare_supersession,
    build_decision_material, build_supersedes_graph_from_material, decision_digest,
)
from science_tool.plan_common import (
    ExplicitSupersessionIds, PathTransition, StateFingerprint, SupersedeSelection, fingerprint,
)


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

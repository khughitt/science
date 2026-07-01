"""Programmatic Step 2b gate check used by integration tests."""

from __future__ import annotations

from pathlib import Path

from science_model.frontmatter import parse_entity_file, parse_frontmatter
from science_model.packages.schema import DerivationBlock, MemberOfDerivationBlock
from science_tool.datasets.semantics import reproducibility_class_for, repro_meets_bar
from science_tool.project_config import ReproducibilityPolicyConfig, ReproducibilityWaiver


def _load_dataset(project_root: Path, ds_id: str):
    slug = ds_id.removeprefix("dataset:")
    md = project_root / "entities" / "datasets" / f"{slug}.md"
    if not md.exists():
        return None
    try:
        return parse_entity_file(md, project_slug=project_root.name)
    except Exception:
        return None  # Invalid entities don't pass the gate


_RETRIEVABLE_LEVELS = {"public", "registration"}


def check_inputs(
    project_root: Path,
    dataset_ids: list[str],
    *,
    planned_retrieval: set[str] | None = None,
) -> tuple[bool, list[str]]:
    """Run Step 2b gate logic against `dataset_ids`. Returns (pass, halt_messages)."""
    halts: list[str] = []
    planned_retrieval = planned_retrieval or set()
    for ds_id in dataset_ids:
        e = _load_dataset(project_root, ds_id)
        if e is None:
            halts.append(f"{ds_id}: no dataset entity found")
            continue
        if e.origin == "external":
            if e.access is None:
                halts.append(f"{ds_id}: external entity missing access block")
                continue
            if ds_id in planned_retrieval and e.access.level in _RETRIEVABLE_LEVELS and not e.access.exception.mode:
                continue
            if not (e.access.verified or e.access.exception.mode != ""):
                halts.append(f"{ds_id}: external access.verified=false and no exception")
                continue
        elif e.origin == "derived":
            if e.derivation is None:
                halts.append(f"{ds_id}: derived entity missing derivation block")
                continue
            if isinstance(e.derivation, MemberOfDerivationBlock):
                # member_of datasets are structurally-derived; their readiness
                # is the parent collection's responsibility, not a pipeline run.
                continue
            if not isinstance(e.derivation, DerivationBlock):
                halts.append(f"{ds_id}: derived entity has unsupported derivation block")
                continue
            run_slug = e.derivation.workflow_run.removeprefix("workflow-run:")
            run_path = project_root / "entities" / "workflow-runs" / f"{run_slug}.md"
            if not run_path.exists():
                halts.append(f"{ds_id}: derivation.workflow_run {e.derivation.workflow_run} not found")
                continue
            run_fm_result = parse_frontmatter(run_path)
            run_fm = run_fm_result[0] if run_fm_result else {}
            if e.id not in (run_fm.get("produces") or []):
                halts.append(f"{ds_id}: workflow-run does not list this dataset in produces:")
                continue
            # Transitive: recurse into inputs.
            for upstream in e.derivation.inputs:
                ok, sub_halts = check_inputs(project_root, [upstream], planned_retrieval=planned_retrieval)
                if not ok:
                    halts.append(f"{ds_id} -> {sub_halts[0]}")
                    break
    return (not halts, halts)


def _load_dataset_fm(project_root: Path, ds_id: str) -> dict:
    slug = ds_id.removeprefix("dataset:")
    md = project_root / "entities" / "datasets" / f"{slug}.md"
    if not md.exists():
        return {}
    result = parse_frontmatter(md)
    return result[0] if result else {}


def _weakest_class(classes: list[tuple[str, str]]) -> tuple[str, str]:
    """Weakest = unknown if any, else lowest lattice rank."""
    if not classes:
        return "unknown", "no upstreams"
    for cls, gap in classes:
        if cls == "unknown":
            return "unknown", gap
    from science_tool.datasets.semantics import repro_class_rank

    return min(classes, key=lambda c: repro_class_rank(c[0]))


def _effective_repro_class(project_root: Path, ds_id: str, _seen: set[str] | None = None) -> tuple[str, str]:
    """Derived-closure class: weakest external upstream for a derived dataset."""
    _seen = _seen or set()
    if ds_id in _seen:
        return "insider-only", "cycle"
    _seen.add(ds_id)
    e = _load_dataset(project_root, ds_id)
    if e is None:
        return "unknown", "missing entity"
    if e.origin == "derived" and isinstance(e.derivation, DerivationBlock):
        upstream_classes = [_effective_repro_class(project_root, up, set(_seen)) for up in e.derivation.inputs]
        return _weakest_class(upstream_classes)
    return reproducibility_class_for(_load_dataset_fm(project_root, ds_id))


def check_reproducibility(
    project_root: Path,
    dataset_ids: list[str],
    *,
    policy: ReproducibilityPolicyConfig | None,
    waivers: list[ReproducibilityWaiver] | None = None,
) -> tuple[bool, list[str], list[str]]:
    """Reproducibility Step-2b enforcement over declared plan inputs.

    Every id in `dataset_ids` is a declared plan input. Returns (pass, halts, warns).
    policy=None => opt-out: nudge, no enforcement.
    """
    waivers = waivers or []
    halts: list[str] = []
    warns: list[str] = []

    if policy is None:
        if dataset_ids:
            warns.append(
                "reproducibility-policy-missing: plan has dataset inputs but no "
                "reproducibility_policy; reproducibility gate not enforced."
            )
        return True, halts, warns

    for ds_id in dataset_ids:
        cls, gap = _effective_repro_class(project_root, ds_id)
        if cls == "unknown":
            msg = f"{ds_id}: reproducibility class unknown ({gap})"
            (halts if policy.unknown == "halt" else warns).append(msg)
            continue
        if repro_meets_bar(cls, policy.bar):
            continue
        waived = any(w.dataset == ds_id and w.accepted_class == cls for w in waivers)
        if waived:
            warns.append(f"{ds_id}: below bar ({cls}) accepted via waiver")
            continue
        msg = f"{ds_id}: reproducibility {cls} below bar {policy.bar} ({gap})"
        (halts if policy.below_bar == "halt" else warns).append(msg)

    return (not halts, halts, warns)

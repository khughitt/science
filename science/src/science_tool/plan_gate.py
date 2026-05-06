"""Programmatic Step 2b gate check used by integration tests."""

from __future__ import annotations

from pathlib import Path

from science_model.frontmatter import parse_entity_file, parse_frontmatter


def _load_dataset(project_root: Path, ds_id: str):
    slug = ds_id.removeprefix("dataset:")
    md = project_root / "doc" / "datasets" / f"{slug}.md"
    if not md.exists():
        return None
    try:
        return parse_entity_file(md, project_slug=project_root.name)
    except Exception:
        return None  # Invalid entities don't pass the gate


def check_inputs(project_root: Path, dataset_ids: list[str]) -> tuple[bool, list[str]]:
    """Run Step 2b gate logic against `dataset_ids`. Returns (pass, halt_messages)."""
    halts: list[str] = []
    for ds_id in dataset_ids:
        e = _load_dataset(project_root, ds_id)
        if e is None:
            halts.append(f"{ds_id}: no dataset entity found")
            continue
        if e.origin == "external":
            if e.access is None:
                halts.append(f"{ds_id}: external entity missing access block")
                continue
            if not (e.access.verified or e.access.exception.mode != ""):
                halts.append(f"{ds_id}: external access.verified=false and no exception")
                continue
        elif e.origin == "derived":
            if e.derivation is None:
                halts.append(f"{ds_id}: derived entity missing derivation block")
                continue
            run_slug = e.derivation.workflow_run.removeprefix("workflow-run:")
            run_path = project_root / "doc" / "workflow-runs" / f"{run_slug}.md"
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
                ok, sub_halts = check_inputs(project_root, [upstream])
                if not ok:
                    halts.append(f"{ds_id} -> {sub_halts[0]}")
                    break
    return (not halts, halts)

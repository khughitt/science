"""`science-tool data-package migrate <slug>` — split legacy data-package into derived datasets + research-package."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from science_model.frontmatter import parse_frontmatter
from science_tool.datasets_register import (
    _append_yaml_list_item,
    _read_run,
    _read_workflow_outputs,
    write_derived_dataset_entities,
    write_per_output_datapackages,
    write_symmetric_edges,
)


@dataclass
class MigrationPlan:
    """What `migrate_data_package` would do for one data-package."""

    dp_slug: str
    dataset_paths: list[Path] = field(default_factory=list)
    research_package_path: Path | None = None
    superseded_status_target: Path | None = None


def _research_package_yaml(
    *,
    slug: str,
    dp_dir_rel: str,
    manifest_rel: str,
    cells_rel: str,
    figures: list[dict],
    vegalite: list[dict],
    excerpts: list[dict],
    displays: list[str],
    related: list[str],
) -> str:
    rp_id = f"research-package:{slug}"
    return (
        "---\n"
        f'id: "{rp_id}"\n'
        'type: "research-package"\n'
        f'title: "{slug}"\n'
        'status: "active"\n'
        f"displays: {displays!r}\n"
        f'location: "{dp_dir_rel}"\n'
        f'manifest: "{manifest_rel}"\n'
        f'cells: "{cells_rel}"\n'
        f"figures: {figures!r}\n"
        f"vegalite_specs: {vegalite!r}\n"
        f"code_excerpts: {excerpts!r}\n"
        f"related: {related!r}\n"
        "---\n"
    )


def list_unmigrated(project_root: Path) -> list[str]:
    """Return data-package slugs whose status isn't 'superseded'."""
    dp_dir = project_root / "doc" / "data-packages"
    if not dp_dir.exists():
        return []
    out: list[str] = []
    for md in sorted(dp_dir.rglob("*.md")):
        result = parse_frontmatter(md)
        if not result:
            continue
        fm, _ = result
        if fm.get("type") == "data-package" and fm.get("status") != "superseded":
            out.append(md.stem)
    return out


def migrate_data_package(project_root: Path, dp_slug: str, *, dry_run: bool = False) -> MigrationPlan:
    """Split a legacy data-package entity into derived datasets + a research-package.

    If `dry_run=True`, returns a MigrationPlan describing what would be written
    without making any changes. Idempotent: no-op when status is already 'superseded'.
    """
    dp_path = project_root / "doc" / "data-packages" / f"{dp_slug}.md"
    if not dp_path.exists():
        raise FileNotFoundError(f"no such data-package: {dp_path}")
    dp_fm, _ = parse_frontmatter(dp_path) or ({}, "")
    if dp_fm.get("status") == "superseded":
        return MigrationPlan(dp_slug=dp_slug)  # already migrated; no-op
    workflow_run_id = str(dp_fm.get("workflow_run", ""))
    if not workflow_run_id:
        raise ValueError("data-package has no workflow_run pointer; cannot migrate")
    # Validate the workflow has outputs:
    _, run_fm = _read_run(project_root, workflow_run_id)
    workflow_id = str(run_fm.get("workflow", ""))
    outputs = _read_workflow_outputs(project_root, workflow_id)
    if not outputs:
        raise ValueError(f"{workflow_id} has no outputs[] block; add one before migrating data-package:{dp_slug}")

    plan = MigrationPlan(dp_slug=dp_slug)

    # Compute paths that would be written (for both dry-run + real).
    workflow_slug = workflow_id.removeprefix("workflow:")
    run_slug = workflow_run_id.removeprefix("workflow-run:")
    for out in outputs:
        plan.dataset_paths.append(project_root / "doc" / "datasets" / f"{workflow_slug}-{run_slug}-{out['slug']}.md")

    # Locate the bundle dir from the data-package's manifest path.
    manifest_rel = str(dp_fm.get("manifest", ""))
    bundle_dir = (project_root / Path(manifest_rel).parent) if manifest_rel else None
    if bundle_dir is not None:
        plan.research_package_path = bundle_dir / "research-package.md"
    else:
        plan.research_package_path = project_root / "research" / "packages" / dp_slug / "research-package.md"
    plan.superseded_status_target = dp_path

    if dry_run:
        return plan

    # Reuse register-run to write per-output runtime datapackages + derived entities + symmetric edges.
    write_per_output_datapackages(project_root, workflow_run_id)
    written = write_derived_dataset_entities(project_root, workflow_run_id)
    written_ids = [ds_id for _, ds_id in written]
    write_symmetric_edges(project_root, workflow_run_id, written_ids)

    # Load the legacy bundle's research extension.
    figures: list[dict] = []
    vegalite: list[dict] = []
    excerpts: list[dict] = []
    cells_rel = str(dp_fm.get("cells", ""))
    if bundle_dir and (bundle_dir / "datapackage.json").exists():
        descriptor = json.loads((bundle_dir / "datapackage.json").read_text(encoding="utf-8"))
        research = descriptor.get("research") or {}
        figures = list(research.get("figures") or [])
        vegalite = list(research.get("vegalite_specs") or [])
        excerpts = list(research.get("code_excerpts") or [])
        if not cells_rel:
            cells_rel = research.get("cells", "")

    # Write the research-package entity.
    rp_path = plan.research_package_path
    rp_path.parent.mkdir(parents=True, exist_ok=True)
    rp_dir_rel = str(rp_path.parent.relative_to(project_root))
    rp_yaml = _research_package_yaml(
        slug=dp_slug,
        dp_dir_rel=rp_dir_rel,
        manifest_rel=manifest_rel,
        cells_rel=cells_rel,
        figures=figures,
        vegalite=vegalite,
        excerpts=excerpts,
        displays=written_ids,
        related=[workflow_run_id],
    )
    rp_path.write_text(rp_yaml, encoding="utf-8")

    # Append research-package to each derived dataset's consumed_by (invariant #11).
    for ds_id in written_ids:
        slug = ds_id.removeprefix("dataset:")
        ds_path = project_root / "doc" / "datasets" / f"{slug}.md"
        _append_yaml_list_item(ds_path, "consumed_by", f"research-package:{dp_slug}")

    # Mark the old data-package as superseded.
    dp_text = dp_path.read_text(encoding="utf-8")
    parts = dp_text.split("---", 2)
    fm = yaml.safe_load(parts[1]) or {}
    fm["status"] = "superseded"
    fm["superseded_by"] = f"research-package:{dp_slug}"
    new_fm = yaml.safe_dump(fm, sort_keys=False)
    dp_path.write_text(f"---\n{new_fm}---{parts[2]}", encoding="utf-8")

    return plan

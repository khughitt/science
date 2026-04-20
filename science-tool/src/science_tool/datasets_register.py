"""`science-tool dataset register-run` — emit derived dataset entities + per-output datapackages."""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

import yaml

from science_model.frontmatter import parse_frontmatter


def _read_workflow_outputs(project_root: Path, workflow_id: str) -> list[dict]:
    """Return the workflow's `outputs:` block. Raises FileNotFoundError if missing."""
    slug = workflow_id.removeprefix("workflow:")
    wf_path = project_root / "doc" / "workflows" / f"{slug}.md"
    if not wf_path.exists():
        raise FileNotFoundError(f"workflow entity not found: {wf_path}")
    result = parse_frontmatter(wf_path)
    fm = result[0] if result else {}
    return list(fm.get("outputs") or [])


def _read_run(project_root: Path, run_id: str) -> tuple[Path, dict]:
    slug = run_id.removeprefix("workflow-run:")
    run_path = project_root / "doc" / "workflow-runs" / f"{slug}.md"
    if not run_path.exists():
        raise FileNotFoundError(f"workflow-run entity not found: {run_path}")
    result = parse_frontmatter(run_path)
    fm = result[0] if result else {}
    return run_path, fm


def _read_run_aggregate_datapackage(project_root: Path, workflow_slug: str, run_slug: str) -> tuple[Path, dict]:
    rt = project_root / "results" / workflow_slug / run_slug / "datapackage.yaml"
    if not rt.exists():
        raise FileNotFoundError(f"run-aggregate datapackage not found: {rt}")
    return rt, yaml.safe_load(rt.read_text(encoding="utf-8"))


def _run_dir_slug(workflow_slug: str, run_entity_slug: str) -> str:
    """Return the run directory name by stripping the workflow slug prefix.

    Convention: run entity slug is ``<workflow-slug>-<run-id>`` and the
    results directory is ``results/<workflow-slug>/<run-id>/``.
    Example: workflow slug ``wf``, run slug ``wf-r1`` → dir name ``r1``.
    Falls back to the full run_entity_slug if the prefix is not present.
    """
    prefix = f"{workflow_slug}-"
    if run_entity_slug.startswith(prefix):
        return run_entity_slug[len(prefix) :]
    return run_entity_slug


def write_per_output_datapackages(project_root: Path, workflow_run_id: str) -> list[Path]:
    """Write one datapackage.yaml per declared output. Returns list of written paths.

    Per-output datapackages are VIEWS into a subset of the run-aggregate's resources,
    NOT file relocations. Resource paths kept verbatim; basepath: ".." resolves them
    against the run root where the workflow originally wrote the files.
    """
    run_path, run_fm = _read_run(project_root, workflow_run_id)
    workflow_id = str(run_fm.get("workflow", ""))
    workflow_slug = workflow_id.removeprefix("workflow:")
    run_entity_slug = workflow_run_id.removeprefix("workflow-run:")
    run_slug = _run_dir_slug(workflow_slug, run_entity_slug)
    outputs = _read_workflow_outputs(project_root, workflow_id)
    if not outputs:
        raise ValueError(f"workflow {workflow_id} has no outputs[] block; add one before registering")
    rt_path, rt = _read_run_aggregate_datapackage(project_root, workflow_slug, run_slug)
    by_name = {r["name"]: r for r in (rt.get("resources") or [])}
    run_root = rt_path.parent
    written: list[Path] = []
    for out in outputs:
        slug = str(out["slug"])
        names = list(out.get("resource_names") or [])
        out_resources = []
        for n in names:
            if n not in by_name:
                raise ValueError(
                    f"output {slug!r} declares resource_name {n!r} but run datapackage has no such resource"
                )
            r = dict(by_name[n])
            referenced = (run_root / r["path"]).resolve()
            if not referenced.exists():
                raise FileNotFoundError(
                    f"output {slug!r}: resource {n!r} declares path {r['path']!r} but no such file at {referenced}"
                )
            out_resources.append(r)
        out_dir = run_root / slug
        out_dir.mkdir(parents=True, exist_ok=True)
        out_dp_path = out_dir / "datapackage.yaml"
        out_dp: dict = {
            "profiles": ["science-pkg-runtime-1.0"],
            "name": f"{workflow_slug}-{run_slug}-{slug}",
            "title": str(out.get("title", "")),
            "basepath": "..",
            "resources": out_resources,
        }
        if out.get("ontology_terms"):
            out_dp["ontology_terms"] = list(out["ontology_terms"])
        out_dp_path.write_text(yaml.safe_dump(out_dp, sort_keys=False), encoding="utf-8")
        written.append(out_dp_path)
    return written


def _entity_yaml_block(
    *,
    slug: str,
    title: str,
    workflow_id: str,
    workflow_run_id: str,
    git_commit: str,
    config_snapshot: str,
    produced_at: str,
    inputs: list[str],
    dp_path_rel: str,
    ontology_terms: list[str],
) -> str:
    entity_id = f"dataset:{slug}"
    return (
        "---\n"
        f'id: "{entity_id}"\n'
        'type: "dataset"\n'
        f'title: "{title}"\n'
        'status: "active"\n'
        'profiles: ["science-pkg-entity-1.0"]\n'
        'origin: "derived"\n'
        'tier: "use-now"\n'
        'license: "internal"\n'
        'update_cadence: "static"\n'
        f"ontology_terms: {ontology_terms!r}\n"
        f'datapackage: "{dp_path_rel}"\n'
        "derivation:\n"
        f'  workflow: "{workflow_id}"\n'
        f'  workflow_run: "{workflow_run_id}"\n'
        f'  git_commit: "{git_commit}"\n'
        f'  config_snapshot: "{config_snapshot}"\n'
        f'  produced_at: "{produced_at}"\n'
        f"  inputs: {inputs!r}\n"
        "consumed_by: []\n"
        f'created: "{produced_at[:10]}"\n'
        f'updated: "{produced_at[:10]}"\n'
        "---\n"
    )


def write_derived_dataset_entities(project_root: Path, workflow_run_id: str) -> list[tuple[Path, str]]:
    """Returns list of (path, dataset_id) tuples for written entities."""
    run_path, run_fm = _read_run(project_root, workflow_run_id)
    workflow_id = str(run_fm.get("workflow", ""))
    workflow_slug = workflow_id.removeprefix("workflow:")
    run_entity_slug = workflow_run_id.removeprefix("workflow-run:")
    run_dir = _run_dir_slug(workflow_slug, run_entity_slug)
    outputs = _read_workflow_outputs(project_root, workflow_id)
    git_commit = str(run_fm.get("git_commit", ""))
    config_snapshot = str(run_fm.get("config_snapshot", ""))
    produced_at = str(run_fm.get("last_run") or datetime.now(timezone.utc).isoformat())
    inputs = list(run_fm.get("inputs") or [])
    written: list[tuple[Path, str]] = []
    for out in outputs:
        # entity slug uses the full run entity slug for uniqueness across workflow runs
        slug = f"{workflow_slug}-{run_entity_slug}-{out['slug']}"
        ds_path = project_root / "doc" / "datasets" / f"{slug}.md"
        ds_path.parent.mkdir(parents=True, exist_ok=True)
        # path on disk uses the run dir slug (strips workflow prefix)
        dp_rel = f"results/{workflow_slug}/{run_dir}/{out['slug']}/datapackage.yaml"
        body = _entity_yaml_block(
            slug=slug,
            title=str(out.get("title", slug)),
            workflow_id=workflow_id,
            workflow_run_id=workflow_run_id,
            git_commit=git_commit,
            config_snapshot=config_snapshot,
            produced_at=produced_at,
            inputs=inputs,
            dp_path_rel=dp_rel,
            ontology_terms=list(out.get("ontology_terms") or []),
        )
        # Idempotent: skip writing if existing content matches new content exactly.
        if ds_path.exists() and ds_path.read_text(encoding="utf-8") == body:
            written.append((ds_path, f"dataset:{slug}"))
            continue
        ds_path.write_text(body, encoding="utf-8")
        written.append((ds_path, f"dataset:{slug}"))
    return written


_FM_BOUND = re.compile(r"^---\s*\n(?P<fm>.*?\n)---\s*\n", re.DOTALL)


def _append_yaml_list_item(file_path: Path, field: str, value: str) -> None:
    """Append `<value>` to a YAML list field within frontmatter, deduplicated.

    Preserves comments, key order, and formatting in the rest of the file by
    rewriting only the targeted field's value. Handles three list shapes:
    - Inline empty: `field: []`        -> rewritten to `field: ["<value>"]`
    - Inline non-empty: `field: ["a"]` -> rewritten to `field: ["a", "<value>"]`
    - Block-form: `field:\\n  - "a"\\n`  -> appends `  - "<value>"` line below the last item

    Idempotent: if `<value>` is already present in the field, no-op.
    """
    text = file_path.read_text(encoding="utf-8")
    m = _FM_BOUND.match(text)
    if not m:
        return
    fm = m.group("fm")
    fm_parsed = yaml.safe_load(fm) or {}
    current = list(fm_parsed.get(field) or [])
    if value in current:
        return  # deduplicated

    inline_empty = re.compile(rf"^(?P<indent>\s*){re.escape(field)}:\s*\[\s*\]\s*$", re.MULTILINE)
    inline_nonempty = re.compile(rf"^(?P<indent>\s*){re.escape(field)}:\s*\[(?P<items>.*?)\]\s*$", re.MULTILINE)
    block_header = re.compile(rf"^(?P<indent>\s*){re.escape(field)}:\s*$", re.MULTILINE)

    if (m_e := inline_empty.search(fm)) is not None:
        new_line = f'{m_e["indent"]}{field}: ["{value}"]'
        new_fm = fm[: m_e.start()] + new_line + fm[m_e.end() :]
    elif (m_i := inline_nonempty.search(fm)) is not None:
        items = m_i["items"].rstrip()
        new_items = f'{items}, "{value}"' if items else f'"{value}"'
        new_line = f"{m_i['indent']}{field}: [{new_items}]"
        new_fm = fm[: m_i.start()] + new_line + fm[m_i.end() :]
    elif (m_b := block_header.search(fm)) is not None:
        block_indent = m_b["indent"]
        item_indent = block_indent + "  "
        item_pattern = re.compile(rf"^{re.escape(item_indent)}-\s")
        head_end = m_b.end()
        tail = fm[head_end:]
        lines = tail.split("\n")
        last_item_idx = -1
        for i, line in enumerate(lines):
            if item_pattern.match(line):
                last_item_idx = i
            elif line.strip() == "" or line.startswith("#"):
                continue
            else:
                break
        new_item_line = f'{item_indent}- "{value}"'
        if last_item_idx >= 0:
            lines.insert(last_item_idx + 1, new_item_line)
        else:
            lines.insert(0, new_item_line)
        new_fm = fm[:head_end] + "\n".join(lines)
    else:
        new_fm = fm + f'{field}:\n  - "{value}"\n'

    file_path.write_text(text[: m.start("fm")] + new_fm + text[m.end("fm") :], encoding="utf-8")


def write_symmetric_edges(project_root: Path, workflow_run_id: str, written_dataset_ids: list[str]) -> None:
    """Append produces[] on workflow-run + consumed_by on each upstream input."""
    run_slug = workflow_run_id.removeprefix("workflow-run:")
    run_path = project_root / "doc" / "workflow-runs" / f"{run_slug}.md"
    for ds_id in written_dataset_ids:
        _append_yaml_list_item(run_path, "produces", ds_id)
    result = parse_frontmatter(run_path)
    fm = result[0] if result else {}
    for upstream_id in list(fm.get("inputs") or []):
        slug = upstream_id.removeprefix("dataset:")
        upstream_path = project_root / "doc" / "datasets" / f"{slug}.md"
        if upstream_path.exists():
            _append_yaml_list_item(upstream_path, "consumed_by", workflow_run_id)

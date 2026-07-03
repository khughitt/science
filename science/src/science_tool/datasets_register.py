"""`science dataset register-run` — emit derived dataset entities + per-output datapackages."""

from __future__ import annotations

import re
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from science_model.frontmatter import parse_frontmatter

from science_tool.commons.identity_stamp import derive_stamp
from science_tool.identity_authoring import ASSEMBLY_REGISTRY_ID, BASE_DATASET_SCHEMA_PROFILE, require_profile_identity


def _read_workflow_outputs(project_root: Path, workflow_id: str) -> list[dict]:
    """Return the workflow's `outputs:` block. Raises FileNotFoundError if missing."""
    slug = workflow_id.removeprefix("workflow:")
    wf_path = project_root / "entities" / "workflows" / f"{slug}.md"
    if not wf_path.exists():
        raise FileNotFoundError(f"workflow entity not found: {wf_path}")
    result = parse_frontmatter(wf_path)
    fm = result[0] if result else {}
    return list(fm.get("outputs") or [])


def _read_run(project_root: Path, run_id: str) -> tuple[Path, dict]:
    slug = run_id.removeprefix("workflow-run:")
    run_path = project_root / "entities" / "workflow-runs" / f"{slug}.md"
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
    _, run_fm = _read_run(project_root, workflow_run_id)
    workflow_id = str(run_fm.get("workflow", ""))
    workflow_slug = workflow_id.removeprefix("workflow:")
    run_entity_slug = workflow_run_id.removeprefix("workflow-run:")
    run_slug = _run_dir_slug(workflow_slug, run_entity_slug)
    outputs = _read_workflow_outputs(project_root, workflow_id)
    if not outputs:
        raise ValueError(f"workflow {workflow_id} has no outputs[] block; add one before registering")
    resolutions = _resolve_output_identities(project_root, run_fm, outputs)
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
        resolved_identity = resolutions.get(str(out["slug"]))
        if resolved_identity is not None and resolved_identity.identity_context:
            out_dp["science"] = {"identity_context": derive_stamp(resolved_identity.identity_context)}
        out_dp_path.write_text(yaml.safe_dump(out_dp, sort_keys=False), encoding="utf-8")
        written.append(out_dp_path)
    return written


@dataclass(frozen=True)
class _ResolvedOutputIdentity:
    identity_context: dict[str, Any]
    data_inputs: list[str]
    transformations: list[dict[str, Any]]


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
    transformations: list[dict[str, Any]] | None,
    dp_path_rel: str,
    ontology_terms: list[str],
    schema_profile: str = BASE_DATASET_SCHEMA_PROFILE,
    identity_context: dict | None = None,
) -> str:
    entity_id = f"dataset:{slug}"
    identity_text = ""
    if identity_context:
        identity_text = yaml.safe_dump(
            {"identity_context": identity_context},
            sort_keys=False,
            allow_unicode=True,
            default_flow_style=False,
        )
    derivation_transformations = ""
    if transformations:
        transformations_yaml = yaml.safe_dump(
            {"transformations": transformations},
            sort_keys=False,
            allow_unicode=True,
            default_flow_style=False,
        )
        derivation_transformations = "".join(f"  {line}" for line in transformations_yaml.splitlines(True))
    return (
        "---\n"
        f'schema_profile: "{schema_profile}"\n'
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
        f"{derivation_transformations}"
        "consumed_by: []\n"
        f"{identity_text}"
        f'created: "{produced_at[:10]}"\n'
        f'updated: "{produced_at[:10]}"\n'
        "---\n"
    )


def _output_schema_profile(out: dict) -> str:
    if "schema_profile" not in out:
        return BASE_DATASET_SCHEMA_PROFILE
    value = out["schema_profile"]
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"output {out.get('slug')!r} has blank schema_profile")
    return value


def _validate_output_identity(out: dict) -> None:
    if "identity" in out and not isinstance(out["identity"], dict):
        raise ValueError(f"output {out.get('slug')!r} identity must be a mapping")


def _transform_from_input_paths(identity_contract: dict[str, Any]) -> list[str]:
    paths: list[str] = []
    assembly = identity_contract.get("assembly")
    if isinstance(assembly, dict):
        transform = assembly.get("transform")
        if isinstance(transform, dict) and transform.get("from") == "input":
            paths.append("identity.assembly.transform.from")
    molecular_ids = identity_contract.get("molecular_ids")
    if isinstance(molecular_ids, dict):
        for tier, tier_identity in molecular_ids.items():
            if not isinstance(tier_identity, dict):
                continue
            transform = tier_identity.get("transform")
            if isinstance(transform, dict) and transform.get("from") == "input":
                paths.append(f"identity.molecular_ids.{tier}.transform.from")
    return paths


def _validate_transform_from_input(out: dict, run_inputs: list[str]) -> None:
    identity_contract = out.get("identity")
    if not isinstance(identity_contract, dict) or len(run_inputs) <= 1:
        return
    paths = _transform_from_input_paths(identity_contract)
    if not paths:
        return
    joined = ", ".join(paths)
    raise ValueError(
        f"output {out.get('slug')!r} uses from: input at {joined} with multiple inputs; use from: dataset:X"
    )


def _dataset_frontmatter(project_root: Path, dataset_id: str) -> dict:
    slug = dataset_id.removeprefix("dataset:")
    path = project_root / "entities" / "datasets" / f"{slug}.md"
    if not path.exists():
        raise ValueError(f"dataset identity source not found: {dataset_id}")
    result = parse_frontmatter(path)
    return result[0] if result else {}


def _input_identity_map(project_root: Path, dataset_ids: list[str]) -> dict[str, dict[str, Any]]:
    identities: dict[str, dict[str, Any]] = {}
    for dataset_id in dataset_ids:
        fm = _dataset_frontmatter(project_root, dataset_id)
        identity_context = fm.get("identity_context")
        if isinstance(identity_context, dict):
            identities[dataset_id] = identity_context
    return identities


def _dedupe_preserving_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _proxy_source_datasets(identity_contract: dict[str, Any]) -> list[str]:
    assembly = identity_contract.get("assembly")
    if not isinstance(assembly, dict):
        return []
    proxy = assembly.get("proxy")
    if not isinstance(proxy, dict):
        return []
    sources = proxy.get("sources")
    if not isinstance(sources, list):
        return []
    dataset_ids: list[str] = []
    for source in sources:
        if not isinstance(source, dict):
            continue
        dataset_id = source.get("dataset")
        if isinstance(dataset_id, str) and dataset_id.startswith("dataset:"):
            dataset_ids.append(dataset_id)
    return dataset_ids


def _lookup_identity_value(identity_context: dict[str, Any], tier_path: tuple[str, ...]) -> Any:
    current: Any = identity_context
    for part in tier_path:
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _resolve_inherit_from(
    *,
    out_slug: str,
    tier_name: str,
    tier_path: tuple[str, ...],
    source_id: str,
    identities: dict[str, dict[str, Any]],
) -> Any:
    source_identity = identities.get(source_id)
    if source_identity is None:
        raise ValueError(f"output {out_slug!r} {tier_name} inherit.from source {source_id!r} has no identity_context")
    inherited = _lookup_identity_value(source_identity, tier_path)
    if inherited is None:
        raise ValueError(f"output {out_slug!r} {tier_name} inherit.from source {source_id!r} lacks {tier_name}")
    return deepcopy(inherited)


def _resolve_bare_inherit(
    *,
    out_slug: str,
    tier_name: str,
    tier_path: tuple[str, ...],
    selected_inputs: list[str],
    identities: dict[str, dict[str, Any]],
) -> Any:
    inherited_values: list[Any] = []
    for input_id in selected_inputs:
        source_identity = identities.get(input_id)
        if source_identity is None:
            raise ValueError(f"output {out_slug!r} {tier_name} inherit source {input_id!r} has no identity_context")
        inherited = _lookup_identity_value(source_identity, tier_path)
        if inherited is None:
            raise ValueError(f"output {out_slug!r} {tier_name} inherit source {input_id!r} lacks {tier_name}")
        inherited_values.append(inherited)
    if not inherited_values:
        raise ValueError(f"output {out_slug!r} {tier_name} inherit has no usable input identity")
    first = inherited_values[0]
    if any(value != first for value in inherited_values[1:]):
        raise ValueError(f"output {out_slug!r} {tier_name} inherit inputs disagree")
    return deepcopy(first)


def _is_inherit_from_contract(value: Any) -> bool:
    return (
        isinstance(value, dict)
        and set(value) == {"inherit"}
        and isinstance(value.get("inherit"), dict)
        and isinstance(value["inherit"].get("from"), str)
    )


def _identity_lookup_sources_for_value(value: Any, selected_inputs: list[str]) -> list[str]:
    if value == "inherit":
        return selected_inputs
    if _is_inherit_from_contract(value):
        return [value["inherit"]["from"]]
    return []


def _identity_lookup_sources(identity_contract: dict[str, Any], selected_inputs: list[str]) -> list[str]:
    sources = _identity_lookup_sources_for_value(identity_contract.get("taxon"), selected_inputs)
    assembly_contract = identity_contract.get("assembly")
    sources.extend(_identity_lookup_sources_for_value(assembly_contract, selected_inputs))
    if (
        isinstance(assembly_contract, dict)
        and ("transform" in assembly_contract or "proxy" in assembly_contract)
        and "registry" not in assembly_contract
    ):
        sources.extend(selected_inputs)
    molecular_contract = identity_contract.get("molecular_ids")
    if isinstance(molecular_contract, dict):
        for value in molecular_contract.values():
            sources.extend(_identity_lookup_sources_for_value(value, selected_inputs))
    return _dedupe_preserving_order(sources)


def _resolve_identity_value(
    *,
    value: Any,
    out_slug: str,
    tier_name: str,
    tier_path: tuple[str, ...],
    selected_inputs: list[str],
    identities: dict[str, dict[str, Any]],
) -> Any:
    if value == "inherit":
        return _resolve_bare_inherit(
            out_slug=out_slug,
            tier_name=tier_name,
            tier_path=tier_path,
            selected_inputs=selected_inputs,
            identities=identities,
        )
    if _is_inherit_from_contract(value):
        return _resolve_inherit_from(
            out_slug=out_slug,
            tier_name=tier_name,
            tier_path=tier_path,
            source_id=value["inherit"]["from"],
            identities=identities,
        )
    return deepcopy(value)


def _shared_input_assembly(selected_inputs: list[str], identities: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    assemblies = [
        assembly
        for input_id in selected_inputs
        if isinstance((assembly := _lookup_identity_value(identities.get(input_id, {}), ("assembly",))), dict)
    ]
    if not assemblies:
        return None
    first = assemblies[0]
    if any(assembly != first for assembly in assemblies[1:]):
        return None
    return first


def _normalize_assembly_contract(
    assembly: Any,
    *,
    selected_inputs: list[str],
    identities: dict[str, dict[str, Any]],
) -> Any:
    if not isinstance(assembly, dict) or ("transform" not in assembly and "proxy" not in assembly):
        return assembly
    normalized = deepcopy(assembly)
    inherited_assembly = _shared_input_assembly(selected_inputs, identities)
    if "registry" not in normalized:
        inherited_registry = inherited_assembly.get("registry") if isinstance(inherited_assembly, dict) else None
        normalized["registry"] = inherited_registry if isinstance(inherited_registry, str) else ASSEMBLY_REGISTRY_ID
    if "resolution_status" not in normalized:
        normalized["resolution_status"] = "declared_unresolved"
    if "seqcol_digest" not in normalized and "label" not in normalized:
        normalized["label"] = "UNKNOWN"
    return normalized


def _transform_entry(transform: dict[str, Any], target: str) -> dict[str, Any]:
    entry: dict[str, Any] = {
        "kind": "identity_transform",
        "target": target,
        "dataset": transform["dataset"],
        "type": transform["type"],
    }
    for key in ("from", "to", "method"):
        if key in transform:
            entry[key] = transform[key]
    return entry


def _identity_transformations(identity_context: dict[str, Any]) -> list[dict[str, Any]]:
    transformations: list[dict[str, Any]] = []
    assembly = identity_context.get("assembly")
    if isinstance(assembly, dict):
        transform = assembly.get("transform")
        if isinstance(transform, dict) and isinstance(transform.get("dataset"), str):
            transformations.append(_transform_entry(transform, "assembly"))
        proxy = assembly.get("proxy")
        if isinstance(proxy, dict) and isinstance(proxy.get("via"), str):
            transformations.append({"kind": "proxy_via", "dataset": proxy["via"], "type": proxy.get("type", "proxy")})
    molecular_ids = identity_context.get("molecular_ids")
    if isinstance(molecular_ids, dict):
        for tier, tier_identity in molecular_ids.items():
            if not isinstance(tier_identity, dict):
                continue
            transform = tier_identity.get("transform")
            if isinstance(transform, dict) and isinstance(transform.get("dataset"), str):
                transformations.append(_transform_entry(transform, f"molecular_ids.{tier}"))
    return transformations


def _resolve_output_identity(
    project_root: Path,
    out: dict[str, Any],
    run_inputs: list[str],
) -> _ResolvedOutputIdentity | None:
    identity_contract = out.get("identity")
    if not isinstance(identity_contract, dict):
        return None
    out_slug = str(out.get("slug"))
    proxy_sources = _proxy_source_datasets(identity_contract)
    selected_inputs = _dedupe_preserving_order([*run_inputs, *proxy_sources])
    identity_sources = _identity_lookup_sources(identity_contract, selected_inputs)
    identities = _input_identity_map(project_root, identity_sources) if identity_sources else {}
    identity_context: dict[str, Any] = {}

    if "taxon" in identity_contract:
        identity_context["taxon"] = _resolve_identity_value(
            value=identity_contract["taxon"],
            out_slug=out_slug,
            tier_name="taxon",
            tier_path=("taxon",),
            selected_inputs=selected_inputs,
            identities=identities,
        )
    if "assembly" in identity_contract:
        assembly = _resolve_identity_value(
            value=identity_contract["assembly"],
            out_slug=out_slug,
            tier_name="assembly",
            tier_path=("assembly",),
            selected_inputs=selected_inputs,
            identities=identities,
        )
        identity_context["assembly"] = _normalize_assembly_contract(
            assembly,
            selected_inputs=selected_inputs,
            identities=identities,
        )
    molecular_contract = identity_contract.get("molecular_ids")
    if isinstance(molecular_contract, dict):
        molecular_ids: dict[str, Any] = {}
        for tier, value in molecular_contract.items():
            tier_name = f"molecular_ids.{tier}"
            molecular_ids[tier] = _resolve_identity_value(
                value=value,
                out_slug=out_slug,
                tier_name=tier_name,
                tier_path=("molecular_ids", str(tier)),
                selected_inputs=selected_inputs,
                identities=identities,
            )
        if molecular_ids:
            identity_context["molecular_ids"] = molecular_ids

    return _ResolvedOutputIdentity(
        identity_context=identity_context,
        data_inputs=selected_inputs,
        transformations=_identity_transformations(identity_context),
    )


def _resolve_output_identities(
    project_root: Path,
    run_fm: dict,
    outputs: list[dict],
) -> dict[str, _ResolvedOutputIdentity]:
    run_inputs = list(run_fm.get("inputs") or [])
    resolved: dict[str, _ResolvedOutputIdentity] = {}
    for out in outputs:
        identity = _resolve_output_identity(project_root, out, run_inputs)
        if identity is not None:
            resolved[str(out["slug"])] = identity
    return resolved


def _identity_sidecar_path(project_root: Path, workflow_id: str, workflow_run_id: str, out_slug: str) -> Path:
    workflow_slug = workflow_id.removeprefix("workflow:")
    run_entity_slug = workflow_run_id.removeprefix("workflow-run:")
    run_slug = _run_dir_slug(workflow_slug, run_entity_slug)
    return project_root / "results" / workflow_slug / run_slug / out_slug / "identity_context.yaml"


def _validate_identity_sidecar(
    *,
    project_root: Path,
    workflow_id: str,
    workflow_run_id: str,
    out: dict,
    resolved_identity: _ResolvedOutputIdentity | None,
) -> None:
    out_slug = str(out["slug"])
    sidecar_path = _identity_sidecar_path(project_root, workflow_id, workflow_run_id, out_slug)
    if not sidecar_path.exists():
        return
    sidecar = yaml.safe_load(sidecar_path.read_text(encoding="utf-8"))
    if not isinstance(sidecar, dict):
        raise ValueError(f"{sidecar_path}: identity_context.yaml must contain a mapping")
    expected = derive_stamp(resolved_identity.identity_context) if resolved_identity is not None else {}
    if sidecar != expected:
        raise ValueError(f"{sidecar_path}: identity_context.yaml disagrees with workflow output identity contract")


def _schema_profile_with_identity_extension(schema_profile: str, identity_context: dict[str, Any] | None) -> str:
    if not identity_context:
        return schema_profile
    if "+bio.identity_context/" in f"+{schema_profile}":
        return schema_profile
    return f"{schema_profile}+bio.identity_context/1.0"


def preflight_register_run_identity(project_root: Path, workflow_run_id: str) -> None:
    """Validate output identity metadata before register-run writes files."""
    _, run_fm = _read_run(project_root, workflow_run_id)
    workflow_id = str(run_fm.get("workflow", ""))
    run_inputs = list(run_fm.get("inputs") or [])
    outputs = _read_workflow_outputs(project_root, workflow_id)
    for out in outputs:
        _output_schema_profile(out)
        _validate_output_identity(out)
        _validate_transform_from_input(out, run_inputs)
    resolutions = _resolve_output_identities(project_root, run_fm, outputs)
    for out in outputs:
        resolved_identity = resolutions.get(str(out["slug"]))
        _validate_identity_sidecar(
            project_root=project_root,
            workflow_id=workflow_id,
            workflow_run_id=workflow_run_id,
            out=out,
            resolved_identity=resolved_identity,
        )
        identity_context = resolved_identity.identity_context if resolved_identity is not None else None
        schema_profile = _schema_profile_with_identity_extension(_output_schema_profile(out), identity_context)
        require_profile_identity(schema_profile, identity_context)


def write_derived_dataset_entities(project_root: Path, workflow_run_id: str) -> list[tuple[Path, str]]:
    """Returns list of (path, dataset_id) tuples for written entities."""
    _, run_fm = _read_run(project_root, workflow_run_id)
    workflow_id = str(run_fm.get("workflow", ""))
    workflow_slug = workflow_id.removeprefix("workflow:")
    run_entity_slug = workflow_run_id.removeprefix("workflow-run:")
    run_dir = _run_dir_slug(workflow_slug, run_entity_slug)
    outputs = _read_workflow_outputs(project_root, workflow_id)
    resolutions = _resolve_output_identities(project_root, run_fm, outputs)
    git_commit = str(run_fm.get("git_commit", ""))
    config_snapshot = str(run_fm.get("config_snapshot", ""))
    produced_at = str(run_fm.get("last_run") or datetime.now(timezone.utc).isoformat())
    inputs = list(run_fm.get("inputs") or [])
    written: list[tuple[Path, str]] = []
    for out in outputs:
        # Entity slug = run entity slug + output slug. run_entity_slug already begins
        # with the workflow slug (it IS `<workflow-slug>-<run-id>`), so it provides
        # cross-run uniqueness on its own — prepending workflow_slug again double-
        # prefixed the id (dataset:wf-wf-r1-...). This composition also matches the
        # per-output datapackage name (`{workflow_slug}-{run_dir}-{out_slug}`), keeping
        # the entity id and its datapackage name in sync.
        slug = f"{run_entity_slug}-{out['slug']}"
        ds_path = project_root / "entities" / "datasets" / f"{slug}.md"
        ds_path.parent.mkdir(parents=True, exist_ok=True)
        # path on disk uses the run dir slug (strips workflow prefix)
        dp_rel = f"results/{workflow_slug}/{run_dir}/{out['slug']}/datapackage.yaml"
        resolved_identity = resolutions.get(str(out["slug"]))
        identity_context = resolved_identity.identity_context if resolved_identity is not None else None
        data_inputs = resolved_identity.data_inputs if resolved_identity is not None else inputs
        transformations = resolved_identity.transformations if resolved_identity is not None else []
        schema_profile = _schema_profile_with_identity_extension(_output_schema_profile(out), identity_context)
        body = _entity_yaml_block(
            slug=slug,
            title=str(out.get("title", slug)),
            workflow_id=workflow_id,
            workflow_run_id=workflow_run_id,
            git_commit=git_commit,
            config_snapshot=config_snapshot,
            produced_at=produced_at,
            inputs=data_inputs,
            transformations=transformations,
            dp_path_rel=dp_rel,
            ontology_terms=list(out.get("ontology_terms") or []),
            schema_profile=schema_profile,
            identity_context=identity_context,
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
    run_path = project_root / "entities" / "workflow-runs" / f"{run_slug}.md"
    for ds_id in written_dataset_ids:
        _append_yaml_list_item(run_path, "produces", ds_id)
    upstream_ids: list[str] = []
    for ds_id in written_dataset_ids:
        slug = ds_id.removeprefix("dataset:")
        ds_path = project_root / "entities" / "datasets" / f"{slug}.md"
        if not ds_path.exists():
            continue
        result = parse_frontmatter(ds_path)
        fm = result[0] if result else {}
        derivation = fm.get("derivation")
        if isinstance(derivation, dict):
            upstream_ids.extend(str(value) for value in (derivation.get("inputs") or []))
    for upstream_id in _dedupe_preserving_order(upstream_ids):
        slug = upstream_id.removeprefix("dataset:")
        upstream_path = project_root / "entities" / "datasets" / f"{slug}.md"
        if upstream_path.exists():
            _append_yaml_list_item(upstream_path, "consumed_by", workflow_run_id)

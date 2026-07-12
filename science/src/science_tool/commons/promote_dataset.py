"""The dataset/datapackage half of commons promotion.

Datasets promote differently from papers, topics, and themes: they carry a
datapackage whose resources must be verified (hash, size, reachability) and a
side-channel payload that lands outside the entity file. None of that logic is
shared with the other kinds — it reached the generic pipeline through
`dataset`-kind conditionals, which is why it can live in its own module.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Literal, Mapping

from science_tool.commons.datapackage import (
    Resolved,
    ResourceSource,
    Unexpandable,
    parse_resource_hash,
    render_canonical_datapackage_yaml,
    resolve_local_ref,
    stream_sha256_and_bytes,
    validate_logical_path,
    validate_source,
)
from science_tool.commons.errors import (
    DataLogicalPathError,
    PromoteCandidateError,
    PromoteResourceDigestMismatchError,
    PromoteResourceMissingError,
)
from science_tool.commons.promote_types import (
    PerResourceResult,
    PromoteCandidate,
    ResourceVerification,
    SideChannelContext,
    SideChannelResult,
    _GENERATED_BY_PROMOTE_KEYS,
    _OVERLAY_ONLY_KEYS,
    _PROMOTE_DERIVED_IDENTITY_KEYS,
)


def _dataset_side_channel_apply(ctx: SideChannelContext) -> SideChannelResult:
    from science_tool.commons.config import (
        _data_yaml_path,
        _upsert_data_override,
        check_override_conflict,
    )

    extras = ctx.plan.dataset_audit_extras.get(ctx.decision.slug)
    if extras is None:
        return SideChannelResult(artifact_paths=[], backup_paths=[])
    if "override_path" not in extras:
        raise PromoteCandidateError(
            "dataset side-channel apply requires override_path audit extra",
            slug=ctx.decision.slug,
        )
    override_path = extras["override_path"]
    if not isinstance(override_path, str | os.PathLike):
        raise PromoteCandidateError(
            "dataset side-channel apply requires string override_path audit extra",
            slug=ctx.decision.slug,
        )
    override_path = Path(override_path)
    check_override_conflict(slug=ctx.decision.slug, planned_path=override_path)
    _upsert_data_override(
        slug=ctx.decision.slug,
        absolute_path=override_path,
        op_id=ctx.op_id,
        allow_existing_backup=True,
    )
    yaml_path = _data_yaml_path()
    backup_path = yaml_path.parent / f"data.yaml.bak.{ctx.op_id}"
    absent_sentinel_path = yaml_path.parent / f"data.yaml.bak.{ctx.op_id}.absent"
    actual_backup = backup_path if backup_path.exists() else absent_sentinel_path
    return SideChannelResult(
        artifact_paths=[yaml_path],
        backup_paths=[actual_backup],
    )


def _project_relative_path(project_root: Path, value: str, *, field: str) -> Path:
    rel_path = Path(value)
    if rel_path.is_absolute():
        raise PromoteCandidateError(f"{field} path {value!r} must be project-relative")
    root_abs = project_root.resolve()
    abs_path = (root_abs / rel_path).resolve(strict=False)
    try:
        abs_path.relative_to(root_abs)
    except ValueError as exc:
        raise PromoteCandidateError(f"{field} path {value!r} escapes project root") from exc
    return abs_path


def _datapackage_relative_path(datapackage_dir: Path, value: str, *, field: str) -> Path:
    rel_path = Path(value)
    if rel_path.is_absolute():
        raise PromoteCandidateError(f"{field} path {value!r} must be relative to the datapackage")
    package_dir_abs = datapackage_dir.resolve()
    abs_path = (package_dir_abs / rel_path).resolve(strict=False)
    try:
        abs_path.relative_to(package_dir_abs)
    except ValueError as exc:
        raise PromoteCandidateError(f"{field} path {value!r} escapes the datapackage directory") from exc
    return abs_path


def _load_project_datapackage(project_root: Path, datapackage_value: Any) -> tuple[Path, dict[str, Any]]:
    if not isinstance(datapackage_value, str) or not datapackage_value.strip():
        raise PromoteCandidateError("dataset candidate requires a non-empty string datapackage field")

    dp_abs = _project_relative_path(project_root, datapackage_value, field="datapackage")
    if not dp_abs.is_file():
        raise PromoteCandidateError(f"datapackage file does not exist: {datapackage_value}")

    try:
        dp_raw = dp_abs.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise PromoteCandidateError(f"datapackage file is unreadable: {exc}") from exc
    try:
        dp_doc = json.loads(dp_raw)
    except json.JSONDecodeError as exc:
        raise PromoteCandidateError(f"datapackage JSON parse error: {exc}") from exc
    if not isinstance(dp_doc, dict):
        raise PromoteCandidateError("datapackage JSON top-level value must be an object")
    resources = dp_doc.get("resources")
    if not isinstance(resources, list):
        raise PromoteCandidateError("datapackage JSON requires resources to be a list")
    return dp_abs, dp_doc


def _resource_name(resource: Mapping[str, Any], resource_path: str) -> str:
    name = resource.get("name")
    if isinstance(name, str) and name:
        return name
    return resource_path


def _validate_datapackage_resources(slug: str, dp_abs: Path, dp_doc: dict[str, Any]) -> None:
    resources = dp_doc["resources"]
    for idx, resource in enumerate(resources):
        if not isinstance(resource, dict):
            raise PromoteCandidateError(f"datapackage resources[{idx}] must be an object")
        resource_path = resource.get("path")
        if not isinstance(resource_path, str) or not resource_path.strip():
            raise PromoteCandidateError(f"datapackage resources[{idx}].path must be a non-empty string")
        try:
            validate_logical_path(resource_path)
        except DataLogicalPathError as exc:
            raise PromoteCandidateError(
                f"datapackage resources[{idx}].path is invalid: {exc.reason}"
            ) from exc

        raw_source = resource.get("source")
        if raw_source is not None:
            # Sourced resource: bytes are off-repo; validate the source shape
            # and skip the co-located filesystem existence check.
            try:
                validate_source(raw_source)
            except ValueError as exc:
                raise PromoteCandidateError(
                    f"datapackage resources[{idx}] has an invalid source: {exc}"
                ) from exc
            continue

        resource_abs = _datapackage_relative_path(
            dp_abs.parent,
            resource_path,
            field=f"datapackage resources[{idx}].path",
        )
        if not resource_abs.is_file():
            raise PromoteResourceMissingError(
                slug=slug,
                resource_name=_resource_name(resource, resource_path),
                resource_path=Path(resource_path),
            )


def _dataset_class_for_promotion(fm: Mapping[str, Any]) -> Literal["deposit", "reference", "pointer"]:
    raw = fm.get("dataset_class", "deposit")
    if raw in {"deposit", "reference", "pointer"}:
        return raw
    raise PromoteCandidateError(f"dataset_class {raw!r} is not one of deposit, reference, pointer")


def _dataset_access_for_promotion(fm: Mapping[str, Any]) -> Mapping[str, Any]:
    access = fm.get("access")
    if not isinstance(access, Mapping):
        raise PromoteCandidateError("reference/pointer promotion requires an access block")
    return access


def _validate_reference_pointer_promotion(fm: Mapping[str, Any], *, slug: str) -> None:
    dataset_class = _dataset_class_for_promotion(fm)
    if dataset_class not in {"reference", "pointer"}:
        return
    if fm.get("origin") != "external":
        raise PromoteCandidateError(
            f"{dataset_class} promotion requires origin: external",
            slug=slug,
        )
    access = _dataset_access_for_promotion(fm)
    if access.get("verified") is not True:
        raise PromoteCandidateError(
            f"{dataset_class} promotion requires access.verified: true",
            slug=slug,
        )
    source_url = access.get("source_url")
    if not isinstance(source_url, str) or not source_url.strip():
        raise PromoteCandidateError(
            f"{dataset_class} promotion requires access.source_url",
            slug=slug,
        )
    method = access.get("verification_method")
    allowed_methods = (
        {"landing-confirmed", "metadata-confirmed", "credential-confirmed"}
        if dataset_class == "reference"
        else {"landing-confirmed", "metadata-confirmed"}
    )
    if method not in allowed_methods:
        allowed = ", ".join(sorted(allowed_methods))
        raise PromoteCandidateError(
            f"{dataset_class} promotion requires verification_method in {{{allowed}}}",
            slug=slug,
        )


def _normalize_derivation_for_commons(derivation: Any) -> Any:
    """Normalize a derived-dataset `derivation` block into the commons form.

    Project-local validation accepts the heavyweight register-run `DerivationBlock`
    (`workflow`, `workflow_run`, `git_commit`, `config_snapshot`, `produced_at`,
    `inputs`), but commons `mixin-dataset-1.0` "workflow derivation" requires the
    lightweight `workflow_recipe` + `inputs` shape. Promote synthesizes the
    lightweight form from the heavyweight one so a single authored state is both
    validate-clean and promotable (fb-2026-05-30-003):

    - `workflow_recipe` ← the heavyweight `workflow` entity ref (the recipe pointer);
    - `recipe_lockfile` ← `config_snapshot`, when present (optional in commons);
    - `inputs` carried over unchanged (already `dataset:` refs);
    - run-specific provenance (`workflow_run`, `git_commit`, `produced_at`) is
      dropped — it is run identity, not recipe identity, and the commons dataset
      is recipe-level.

    Already-lightweight blocks (have `workflow_recipe`) and `member_of` derivations
    are returned unchanged. An unrecognized shape is returned unchanged so the
    commons schema validator reports it rather than this function masking it.
    """
    if not isinstance(derivation, dict):
        return derivation
    if "workflow_recipe" in derivation or derivation.get("kind") == "member_of":
        return derivation
    if "workflow" not in derivation:
        return derivation
    normalized: dict[str, Any] = {
        "kind": "workflow",
        "workflow_recipe": derivation["workflow"],
        "inputs": list(derivation.get("inputs", [])),
    }
    config_snapshot = derivation.get("config_snapshot")
    if config_snapshot:
        normalized["recipe_lockfile"] = config_snapshot
    return normalized


def _dataset_dropped_fields(
    raw_frontmatter: dict,
    *,
    canonical_fields: dict,
    project_only_fields: dict,
) -> list[str]:
    """Return project frontmatter keys that landed in neither bucket.

    These are keys not recognized by base, dataset mixin, or overlay-1.1 schemas;
    promote drops them silently from output but records them in the audit log.

    Convention: keys starting with `_` are intentional metadata/sentinels and not reported.
    """
    routed = set(canonical_fields) | set(project_only_fields)
    internal = _GENERATED_BY_PROMOTE_KEYS | _PROMOTE_DERIVED_IDENTITY_KEYS | _OVERLAY_ONLY_KEYS
    return sorted(
        k for k in raw_frontmatter if k not in routed and k not in internal and not k.startswith("_")
    )


def _candidate_dataset_class(candidate: PromoteCandidate) -> Literal["deposit", "reference", "pointer"]:
    fields: dict[str, Any] = {}
    fields.update(candidate.project_only_fields)
    fields.update(candidate.canonical_fields)
    return _dataset_class_for_promotion(fields)


def _dataset_per_resource(
    candidate: PromoteCandidate, *, verify_digests: bool = False
) -> PerResourceResult:
    if candidate.datapackage_source_path is None or candidate.datapackage_doc is None:
        raise PromoteCandidateError(
            "dataset planning requires discovery datapackage metadata",
            slug=candidate.slug,
        )

    per_resource: dict[str, tuple[str, int]] = {}
    verifications: list[ResourceVerification] = []
    dp_parent = candidate.datapackage_source_path.parent
    resources = candidate.datapackage_doc.get("resources")
    if not isinstance(resources, list):
        raise PromoteCandidateError(
            "dataset datapackage resources must be a list",
            slug=candidate.slug,
        )
    for idx, resource in enumerate(resources):
        if not isinstance(resource, Mapping):
            raise PromoteCandidateError(
                f"datapackage resources[{idx}] must be an object",
                slug=candidate.slug,
            )
        resource_path = resource.get("path")
        if not isinstance(resource_path, str) or not resource_path.strip():
            raise PromoteCandidateError(
                f"datapackage resources[{idx}].path must be a non-empty string",
                slug=candidate.slug,
            )
        try:
            validate_logical_path(resource_path)
        except DataLogicalPathError as exc:
            raise PromoteCandidateError(
                f"datapackage resources[{idx}].path is invalid: {exc.reason}",
                slug=candidate.slug,
            ) from exc
        name = _resource_name(resource, resource_path)

        raw_source = resource.get("source")
        if raw_source is None:
            # Co-located resource: resolve under the datapackage dir and stream.
            resource_abs = _datapackage_relative_path(
                dp_parent,
                resource_path,
                field=f"datapackage resources[{idx}].path",
            )
            try:
                per_resource[name] = stream_sha256_and_bytes(resource_abs)
            except OSError as exc:
                raise PromoteCandidateError(
                    f"cannot read datapackage resources[{idx}] bytes: {exc}",
                    slug=candidate.slug,
                    path=resource_abs,
                ) from exc
            continue

        # Sourced resource: trust the build-stamped (hash, bytes); no local I/O
        # in the default path.
        try:
            source = validate_source(raw_source)
        except ValueError as exc:
            raise PromoteCandidateError(
                f"datapackage resources[{idx}] has an invalid source: {exc}",
                slug=candidate.slug,
            ) from exc
        stamped = _stamped_metadata(resource, idx, candidate.slug)
        per_resource[name] = stamped
        if verify_digests:
            verifications.append(
                _verify_sourced_resource(
                    candidate.project_slug, name, source, stamped, candidate.slug
                )
            )

    return PerResourceResult(
        per_resource=per_resource, verifications=tuple(verifications)
    )


def _stamped_metadata(
    resource: Mapping[str, Any], idx: int, slug: str
) -> tuple[str, int]:
    """Validate and return the build-stamped (hash, bytes) of a sourced resource."""
    raw_hash = resource.get("hash")
    if not isinstance(raw_hash, str):
        raise PromoteCandidateError(
            f"sourced datapackage resources[{idx}] has a missing or non-string 'hash'",
            slug=slug,
        )
    try:
        parse_resource_hash(raw_hash)
    except ValueError as exc:
        raise PromoteCandidateError(
            f"sourced datapackage resources[{idx}] has an invalid 'hash': {exc}",
            slug=slug,
        ) from exc
    raw_bytes = resource.get("bytes")
    if (
        not isinstance(raw_bytes, int)
        or isinstance(raw_bytes, bool)
        or raw_bytes < 0
    ):
        raise PromoteCandidateError(
            f"sourced datapackage resources[{idx}] has a missing or invalid 'bytes'",
            slug=slug,
        )
    return raw_hash, raw_bytes


def _verify_sourced_resource(
    project_slug: str,
    name: str,
    source: ResourceSource,
    stamped: tuple[str, int],
    slug: str,
) -> ResourceVerification:
    """Resolve a sourced resource on this host and return its verify verdict.

    Raises on a hard error (digest drift, or a ref that resolves but is missing).
    """
    if source.type != "local":
        return ResourceVerification(
            project_slug=project_slug,
            name=name,
            status="skipped_remote",
            detail=f"{source.type}: no fetcher this iteration",
        )
    try:
        resolution = resolve_local_ref(source.ref)
    except ValueError as exc:
        raise PromoteCandidateError(
            f"cannot verify sourced resource {name!r}: {exc}",
            slug=slug,
        ) from exc
    if isinstance(resolution, Unexpandable):
        return ResourceVerification(
            project_slug=project_slug,
            name=name,
            status="skipped_off_host",
            detail=resolution.ref,
        )
    if not isinstance(resolution, Resolved):
        raise AssertionError(
            f"unexpected RefResolution type: {type(resolution).__name__}"
        )
    if not resolution.exists:
        raise PromoteCandidateError(
            f"sourced resource {name!r} ref resolves to a missing file: "
            f"{resolution.path}",
            slug=slug,
            path=resolution.path,
        )
    actual = stream_sha256_and_bytes(resolution.path)
    if actual != stamped:
        raise PromoteResourceDigestMismatchError(
            slug=slug,
            resource_name=name,
            expected=stamped,
            actual=actual,
            path=resolution.path,
        )
    return ResourceVerification(
        project_slug=project_slug,
        name=name,
        status="verified",
        detail=f"{actual[0]} ({actual[1]} bytes)",
    )


def _validate_dataset_group_datapackages(
    *,
    canonical_slug: str,
    primary: PromoteCandidate,
    candidates: list[PromoteCandidate],
    primary_per_resource: dict[str, tuple[str, int]],
    verify_digests: bool = False,
) -> tuple[ResourceVerification, ...]:
    if len(candidates) <= 1:
        return ()
    if primary.datapackage_doc is None:
        raise PromoteCandidateError(
            "dataset planning requires discovery datapackage metadata",
            slug=canonical_slug,
        )
    primary_content = render_canonical_datapackage_yaml(
        project_doc=primary.datapackage_doc,
        canonical_slug=canonical_slug,
        per_resource=primary_per_resource,
    )
    group_verifications: list[ResourceVerification] = []
    for candidate in candidates:
        if candidate is primary:
            continue
        candidate_result = _dataset_per_resource(candidate, verify_digests=verify_digests)
        candidate_per_resource = candidate_result.per_resource
        group_verifications.extend(candidate_result.verifications)
        if candidate_per_resource != primary_per_resource:
            raise PromoteCandidateError(
                f"dataset {canonical_slug!r} project {candidate.project_slug!r} "
                f"has divergent resource hashes/bytes from primary project "
                f"{primary.project_slug!r}",
                slug=canonical_slug,
                path=candidate.datapackage_source_path,
            )
        if candidate.datapackage_doc is None:
            raise PromoteCandidateError(
                "dataset planning requires discovery datapackage metadata",
                slug=canonical_slug,
                path=candidate.datapackage_source_path,
            )
        candidate_content = render_canonical_datapackage_yaml(
            project_doc=candidate.datapackage_doc,
            canonical_slug=canonical_slug,
            per_resource=candidate_per_resource,
        )
        if candidate_content != primary_content:
            raise PromoteCandidateError(
                f"dataset {canonical_slug!r} project {candidate.project_slug!r} "
                f"has divergent canonical datapackage content from primary "
                f"project {primary.project_slug!r}",
                slug=canonical_slug,
                path=candidate.datapackage_source_path,
            )
    return tuple(group_verifications)


def _dataset_recipe_source_hint(canonical_fields: Mapping[str, Any]) -> str | None:
    sources = canonical_fields.get("sources")
    if isinstance(sources, list) and sources:
        return str(sources[0])
    if isinstance(sources, str) and sources.strip():
        return sources
    source = canonical_fields.get("source")
    if isinstance(source, str) and source.strip():
        return source
    access = canonical_fields.get("access")
    if isinstance(access, Mapping):
        source_url = access.get("source_url")
        if isinstance(source_url, str) and source_url.strip():
            return source_url
    return None


def _render_dataset_recipe_stub(*, slug: str, source_hint: str | None) -> str:
    src_line = f"Acquisition: {source_hint}." if source_hint else "Acquisition: unspecified."
    return (
        "# Recipe back-fill needed\n\n"
        f"{src_line}\n\n"
        "Promote stubbed this README because no project recipe was detected. "
        "Replace with the acquisition or preprocessing workflow.\n"
    )

"""Promotable dataset descriptor contract checks.

This is an authoring-time guard for project-local dataset descriptors before
`science commons promote dataset` is run. It intentionally stays side-effect
free: validate checks the same local datapackage prerequisites promotion needs,
but does not touch the commons checkout or global data overrides.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any

from science_tool.commons.adapter import CommonsEntityAdapter
from science_tool.commons.config import resolve_commons_root
from science_tool.commons.errors import CommonsError, PromoteCandidateError, PromoteResourceMissingError
from science_tool.commons.promote import (
    _load_project_datapackage,
    _validate_datapackage_resources,
)
from science_tool.validate._helpers import dataset_frontmatters
from science_tool.validate.checks import Check
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Result, Severity

PROMOTABLE_ENTITY_PROFILE = "science-pkg-entity-1.0"


def _result(path: str | None, message: str, rule: str) -> Result:
    return Result(Severity.ERROR, Path(path) if path else None, None, message, rule, None)


def _is_dataset_descriptor(fm: Mapping[str, Any]) -> bool:
    path = fm.get("_path")
    return isinstance(path, str) and (
        path.startswith("entities/datasets/") or path.startswith("overlays/datasets/")
    )


def _profile_names(value: Any) -> set[str]:
    if not isinstance(value, (list, tuple, set)):
        return set()
    return {profile for profile in value if isinstance(profile, str)}


def _is_promotion_candidate(fm: Mapping[str, Any]) -> bool:
    return PROMOTABLE_ENTITY_PROFILE in _profile_names(fm.get("profiles")) or _is_pinned_overlay(fm)


def _is_pinned_overlay(fm: Mapping[str, Any]) -> bool:
    return bool(fm.get("overlay_of")) or bool(fm.get("pin_version"))


def _ident(fm: Mapping[str, Any]) -> str:
    ident = fm.get("id")
    return ident if isinstance(ident, str) and ident else "dataset:?"


def _validate_datapackage_ref(
    *,
    ctx: ValidateContext,
    fm: Mapping[str, Any],
    field: str,
    rule: str,
) -> tuple[Path, dict[str, Any]] | Result:
    path = fm.get("_path")
    ident = _ident(fm)
    try:
        datapackage_path, datapackage_doc = _load_project_datapackage(
            ctx.project_root,
            fm.get(field),
        )
        _validate_datapackage_resources(ident.removeprefix("dataset:"), datapackage_path, datapackage_doc)
    except PromoteResourceMissingError as exc:
        return _result(
            path if isinstance(path, str) else None,
            f"{ident}: {field} datapackage resource is missing: {exc}",
            rule,
        )
    except PromoteCandidateError as exc:
        return _result(
            path if isinstance(path, str) else None,
            f"{ident}: {field} datapackage is not promotable: {exc}",
            rule,
        )
    return datapackage_path, datapackage_doc


def _has_qa_resource(datapackage_doc: Mapping[str, Any]) -> bool:
    resources = datapackage_doc.get("resources")
    if not isinstance(resources, list):
        return False
    for resource in resources:
        if not isinstance(resource, Mapping):
            continue
        candidates = [resource.get("name"), resource.get("path")]
        for candidate in candidates:
            if not isinstance(candidate, str):
                continue
            normalized = candidate.lower()
            if "qa" in normalized or "qc" in normalized:
                return True
    return False


def _source_refs_missing(fm: Mapping[str, Any]) -> bool:
    refs = fm.get("source_refs")
    return not isinstance(refs, list) or not any(isinstance(ref, str) and ref.strip() for ref in refs)


def _missing_candidate_fields(fm: Mapping[str, Any]) -> list[str]:
    missing = [
        field
        for field in ("origin", "tier")
        if field not in fm or fm[field] in (None, "")
    ]
    origin = fm.get("origin")
    if origin == "external" and ("access" not in fm or fm["access"] in (None, "")):
        missing.append("access")
    if origin == "derived" and ("derivation" not in fm or fm["derivation"] in (None, "")):
        missing.append("derivation")
    return missing


def _validate_overlay_pin(fm: Mapping[str, Any]) -> Result | None:
    path = fm.get("_path")
    rel_path = path if isinstance(path, str) else None
    ident = _ident(fm)
    overlay_of = fm.get("overlay_of")
    pin_version = fm.get("pin_version")
    if not isinstance(overlay_of, str) or not overlay_of.strip():
        return _result(
            rel_path,
            f"{ident}: pinned dataset overlay requires overlay_of",
            "dataset-promotion.pin-missing",
        )
    if not isinstance(pin_version, str) or not pin_version.strip():
        return _result(
            rel_path,
            f"{ident}: pinned dataset overlay requires pin_version",
            "dataset-promotion.pin-missing",
        )
    if overlay_of != ident:
        return _result(
            rel_path,
            f"{ident}: overlay_of {overlay_of!r} does not match descriptor id",
            "dataset-promotion.pin-mismatch",
        )
    try:
        commons_root = resolve_commons_root()
        if not commons_root.is_dir():
            raise FileNotFoundError(commons_root)
        canonical = CommonsEntityAdapter(commons_root).load(overlay_of)
    except (CommonsError, OSError) as exc:
        return _result(
            rel_path,
            f"{ident}: commons canonical could not be resolved for pinned overlay: {exc}",
            "dataset-promotion.pin-unresolved",
        )
    canonical_version = canonical.frontmatter.get("version")
    if canonical_version != pin_version:
        return _result(
            rel_path,
            f"{ident}: pins {pin_version} but commons canonical is {canonical_version}",
            "dataset-promotion.pin-version-mismatch",
        )
    return None


def evaluate_dataset_promotion_contract(
    datasets: list[dict[str, Any]],
    *,
    ctx: ValidateContext,
) -> Iterator[Result]:
    for fm in datasets:
        if (fm.get("kind") or fm.get("type")) != "dataset" or not _is_dataset_descriptor(fm):
            continue

        path = fm.get("_path")
        rel_path = path if isinstance(path, str) else None
        ident = _ident(fm)

        if not _is_promotion_candidate(fm):
            continue

        if _source_refs_missing(fm):
            yield _result(
                rel_path,
                f"{ident}: promotable dataset descriptor requires non-empty source_refs",
                "dataset-promotion.source-refs-missing",
            )

        if _is_pinned_overlay(fm):
            pin_result = _validate_overlay_pin(fm)
            if pin_result is not None:
                yield pin_result
            result = _validate_datapackage_ref(
                ctx=ctx,
                fm=fm,
                field="source",
                rule="dataset-promotion.source-unresolved",
            )
            if isinstance(result, Result):
                yield result
            continue

        for field in _missing_candidate_fields(fm):
            yield _result(
                rel_path,
                f"{ident}: dataset promotion candidate missing required field {field!r}",
                "dataset-promotion.required-field-missing",
            )

        result = _validate_datapackage_ref(
            ctx=ctx,
            fm=fm,
            field="datapackage",
            rule="dataset-promotion.datapackage-unresolved",
        )
        if isinstance(result, Result):
            yield result
            continue
        _datapackage_path, datapackage_doc = result
        if not _has_qa_resource(datapackage_doc):
            yield _result(
                rel_path,
                f"{ident}: datapackage has no QA resource; include a resource with qa in its name or path",
                "dataset-promotion.qa-resource-missing",
            )


@Check(section="dataset promotion contract", order=33)
def check_dataset_promotion_contract(ctx: ValidateContext) -> Iterator[Result]:
    yield from evaluate_dataset_promotion_contract(dataset_frontmatters(ctx), ctx=ctx)

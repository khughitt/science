"""Promotable dataset descriptor contract checks.

This is an authoring-time guard for project-local dataset descriptors before
`science commons promote dataset` is run. It intentionally stays side-effect
free: validate checks the same local datapackage prerequisites promotion needs,
but does not touch the commons checkout or global data overrides.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from pathlib import Path
from typing import Any, cast

from science_model.audit import FindingRule

from science_tool.validate.findings import validation_observation
from science_tool.validate.findings import declare_validation_rules
from science_tool.commons.adapter import CommonsEntityAdapter
from science_tool.commons.config import resolve_commons_root
from science_tool.commons.errors import CommonsError, PromoteCandidateError, PromoteResourceMissingError
from science_tool.commons.promote import (
    _load_project_datapackage,
    _validate_datapackage_resources,
)
from science_tool.validate._helpers import dataset_frontmatters
from science_tool.validate.checks import Check, CheckObservation
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Result, Severity

PROMOTABLE_ENTITY_PROFILE = "science-pkg-entity-1.0"


SECTION, RULES = declare_validation_rules(
    section_id="dataset-promotion-contract",
    section_title="dataset promotion contract",
    section_order=136,
    rule_ids=(
        "dataset-promotion.datapackage-unresolved",
        "dataset-promotion.pin-mismatch",
        "dataset-promotion.pin-missing",
        "dataset-promotion.pin-unresolved",
        "dataset-promotion.pin-version-mismatch",
        "dataset-promotion.qa-resource-missing",
        "dataset-promotion.reference-access-invalid",
        "dataset-promotion.required-field-missing",
        "dataset-promotion.source-refs-missing",
        "dataset-promotion.source-unresolved",
    ),
    severities=frozenset({"error", "warn", "info"}),
)


def _result(
    path: str | None,
    message: str,
    rule: FindingRule,
    *,
    key: list[str],
) -> Result:
    return cast(
        Result,
        validation_observation(
            severity=Severity.ERROR,
            path=Path(path) if path else None,
            line=None,
            message=message,
            rule=rule,
            task=None,
            qualifiers={"key": key},
        ),
    )


def _is_dataset_descriptor(fm: Mapping[str, Any]) -> bool:
    path = fm.get("_path")
    return isinstance(path, str) and (path.startswith("entities/datasets/") or path.startswith("overlays/datasets/"))


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


def _dataset_class(fm: Mapping[str, Any]) -> str:
    raw = fm.get("dataset_class")
    if raw in {"deposit", "reference", "pointer"}:
        return raw
    return "deposit"


def _reference_access_result(fm: Mapping[str, Any]) -> CheckObservation | None:
    dataset_class = _dataset_class(fm)
    if dataset_class not in {"reference", "pointer"}:
        return None
    path = fm.get("_path")
    rel_path = path if isinstance(path, str) else None
    ident = _ident(fm)
    access = fm.get("access")
    if not isinstance(access, Mapping):
        return _result(
            rel_path,
            f"{ident}: {dataset_class} promotion requires an access block",
            RULES["dataset-promotion.reference-access-invalid"],
            key=["access"],
        )
    source_url = access.get("source_url")
    method = access.get("verification_method")
    allowed_methods = (
        {"landing-confirmed", "metadata-confirmed", "credential-confirmed"}
        if dataset_class == "reference"
        else {"landing-confirmed", "metadata-confirmed"}
    )
    if (
        access.get("verified") is not True
        or not isinstance(source_url, str)
        or not source_url.strip()
        or method not in allowed_methods
    ):
        allowed = ", ".join(sorted(allowed_methods))
        return _result(
            rel_path,
            f"{ident}: {dataset_class} promotion requires verified access.source_url "
            f"and verification_method in {{{allowed}}}",
            RULES["dataset-promotion.reference-access-invalid"],
            key=["access"],
        )
    return None


def _validate_datapackage_ref(
    *,
    ctx: ValidateContext,
    fm: Mapping[str, Any],
    field: str,
    rule: FindingRule,
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
            key=[field],
        )
    except PromoteCandidateError as exc:
        return _result(
            path if isinstance(path, str) else None,
            f"{ident}: {field} datapackage is not promotable: {exc}",
            rule,
            key=[field],
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
    missing = [field for field in ("origin", "tier") if field not in fm or fm[field] in (None, "")]
    origin = fm.get("origin")
    if origin == "external" and ("access" not in fm or fm["access"] in (None, "")):
        missing.append("access")
    if origin == "derived" and ("derivation" not in fm or fm["derivation"] in (None, "")):
        missing.append("derivation")
    return missing


def _validate_overlay_pin(fm: Mapping[str, Any]) -> tuple[CheckObservation | None, str | None]:
    path = fm.get("_path")
    rel_path = path if isinstance(path, str) else None
    ident = _ident(fm)
    overlay_of = fm.get("overlay_of")
    pin_version = fm.get("pin_version")
    if not isinstance(overlay_of, str) or not overlay_of.strip():
        return (
            _result(
                rel_path,
                f"{ident}: pinned dataset overlay requires overlay_of",
                RULES["dataset-promotion.pin-missing"],
                key=["overlay_of"],
            ),
            None,
        )
    if not isinstance(pin_version, str) or not pin_version.strip():
        return (
            _result(
                rel_path,
                f"{ident}: pinned dataset overlay requires pin_version",
                RULES["dataset-promotion.pin-missing"],
                key=["pin_version"],
            ),
            None,
        )
    if overlay_of != ident:
        return (
            _result(
                rel_path,
                f"{ident}: overlay_of {overlay_of!r} does not match descriptor id",
                RULES["dataset-promotion.pin-mismatch"],
                key=["overlay_of"],
            ),
            None,
        )
    try:
        commons_root = resolve_commons_root()
        if not commons_root.is_dir():
            raise FileNotFoundError(commons_root)
        canonical = CommonsEntityAdapter(commons_root).load(overlay_of)
    except (CommonsError, OSError) as exc:
        return (
            _result(
                rel_path,
                f"{ident}: commons canonical could not be resolved for pinned overlay: {exc}",
                RULES["dataset-promotion.pin-unresolved"],
                key=["overlay_of"],
            ),
            None,
        )
    canonical_version = canonical.frontmatter.get("version")
    if canonical_version != pin_version:
        return (
            _result(
                rel_path,
                f"{ident}: pins {pin_version} but commons canonical is {canonical_version}",
                RULES["dataset-promotion.pin-version-mismatch"],
                key=["pin_version"],
            ),
            None,
        )
    return None, _dataset_class(canonical.frontmatter)


def evaluate_dataset_promotion_contract(
    datasets: list[dict[str, Any]],
    *,
    ctx: ValidateContext,
) -> Iterator[CheckObservation]:
    for fm in datasets:
        if fm.get("kind") != "dataset" or not _is_dataset_descriptor(fm):
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
                RULES["dataset-promotion.source-refs-missing"],
                key=["source_refs"],
            )

        if _is_pinned_overlay(fm):
            pin_result, canonical_dataset_class = _validate_overlay_pin(fm)
            if pin_result is not None:
                yield pin_result
            if canonical_dataset_class in {"reference", "pointer"}:
                continue
            result = _validate_datapackage_ref(
                ctx=ctx,
                fm=fm,
                field="source",
                rule=RULES["dataset-promotion.source-unresolved"],
            )
            if isinstance(result, Result):
                yield result
            continue

        for field in _missing_candidate_fields(fm):
            yield _result(
                rel_path,
                f"{ident}: dataset promotion candidate missing required field {field!r}",
                RULES["dataset-promotion.required-field-missing"],
                key=[field],
            )

        if _dataset_class(fm) in {"reference", "pointer"}:
            access_result = _reference_access_result(fm)
            if access_result is not None:
                yield access_result
            continue

        result = _validate_datapackage_ref(
            ctx=ctx,
            fm=fm,
            field="datapackage",
            rule=RULES["dataset-promotion.datapackage-unresolved"],
        )
        if isinstance(result, Result):
            yield result
            continue
        _datapackage_path, datapackage_doc = result
        if not _has_qa_resource(datapackage_doc):
            yield _result(
                rel_path,
                f"{ident}: datapackage has no QA resource; include a resource with qa in its name or path",
                RULES["dataset-promotion.qa-resource-missing"],
                key=["qa-resource"],
            )


@Check(section=SECTION, order=33, producer_id="validate.dataset-promotion-contract", rules=tuple(RULES.values()))
def check_dataset_promotion_contract(ctx: ValidateContext) -> Iterator[CheckObservation]:
    yield from evaluate_dataset_promotion_contract(dataset_frontmatters(ctx), ctx=ctx)

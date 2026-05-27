"""Dataset taxonomy checks (Pillar A1): source_class / derived_kind / dataset_usage.

Reads RAW frontmatter (the closed graph Entity does not surface these on a tolerant
discovery pass, and a malformed core-kind entity would otherwise crash the strict
loader), so the schema-critical rules are re-enforced here with friendly messages.
The curation down-weight itself, and the reference-as-evidence cross-entity check,
land in A2. See docs/plans/2026-05-26-bio-dataset-taxonomy-epistemic-integration-design.md.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Any

from science_tool.validate._helpers import dataset_frontmatters
from science_tool.validate.checks import Check
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Result, Severity

_SOURCE_CLASSES = ("observational", "derived", "reference")
_DERIVED_KINDS = ("aggregate", "transform", "model_output")
_USAGE_ROLES = (
    "analyzed",
    "set_definition_source",
    "validation_source",
    "cited",
    "upstream",
    "training",
)
_USAGE_OVERLAPS = ("full", "partial", "unknown")
_DEPENDENCE_PROVENANCE_ROLES = ("upstream", "training")


def _result(severity: Severity, path: str | None, message: str, rule: str) -> Result:
    return Result(severity, Path(path) if path else None, None, message, rule, None)


def _usage_defect(entry: Any) -> str | None:
    """Defect message for one dataset_usage entry, or None if well-formed."""
    if not isinstance(entry, dict):
        return "entry is not an object"
    ref = entry.get("ref")
    if not isinstance(ref, str) or not ref.startswith("dataset:"):
        return "ref must be a 'dataset:' reference"
    if entry.get("role") not in _USAGE_ROLES:
        return f"role must be one of {list(_USAGE_ROLES)}"
    overlap = entry.get("overlap")
    if overlap is not None and overlap not in _USAGE_OVERLAPS:
        return f"overlap must be one of {list(_USAGE_OVERLAPS)}"
    return None


def evaluate_dataset_taxonomy(datasets: Iterable[dict[str, Any]]) -> Iterator[Result]:
    """Pure core: `datasets` are raw frontmatter dicts (each with `_path`)."""
    for fm in datasets:
        # `kind` is canonical; `type` is the authored alias — accept either.
        if (fm.get("kind") or fm.get("type")) != "dataset":
            continue
        path = fm.get("_path")
        ident = fm.get("id", "?")
        source_class = fm.get("source_class")
        derived_kind = fm.get("derived_kind")

        # --- source_class ---
        if source_class is None:
            yield _result(
                Severity.WARN,
                path,
                f"{ident}: dataset declares no source_class "
                f"(observational|derived|reference); epistemic weighting cannot apply",
                "taxonomy.source-class-undeclared",
            )
        elif source_class not in _SOURCE_CLASSES:
            yield _result(
                Severity.ERROR,
                path,
                f"{ident}: source_class {source_class!r} invalid "
                f"(expected one of {list(_SOURCE_CLASSES)})",
                "taxonomy.source-class-invalid",
            )

        # --- derived_kind consistency ---
        if source_class == "derived":
            if not derived_kind:
                yield _result(
                    Severity.ERROR,
                    path,
                    f"{ident}: source_class=derived requires derived_kind "
                    f"({list(_DERIVED_KINDS)})",
                    "taxonomy.derived-kind-missing",
                )
            elif derived_kind not in _DERIVED_KINDS:
                yield _result(
                    Severity.ERROR,
                    path,
                    f"{ident}: derived_kind {derived_kind!r} invalid "
                    f"(expected one of {list(_DERIVED_KINDS)})",
                    "taxonomy.derived-kind-invalid",
                )
        elif derived_kind is not None:
            yield _result(
                Severity.ERROR,
                path,
                f"{ident}: derived_kind is only allowed when source_class=derived "
                f"(source_class={source_class!r})",
                "taxonomy.derived-kind-misplaced",
            )

        # --- dataset_usage well-formedness ---
        # A present-but-non-list dataset_usage (e.g. a single mapping authored
        # without the leading `-`) is a real defect, not "no usage": ERROR rather
        # than silently treating it as empty.
        usage = fm.get("dataset_usage")
        entries: list[Any] = []
        if isinstance(usage, list):
            entries = usage
        elif usage is not None:
            yield _result(
                Severity.ERROR,
                path,
                f"{ident}: dataset_usage must be a list of usage entries, "
                f"got {type(usage).__name__}",
                "taxonomy.dataset-usage-malformed",
            )
        for entry in entries:
            defect = _usage_defect(entry)
            if defect is not None:
                yield _result(
                    Severity.ERROR,
                    path,
                    f"{ident}: malformed dataset_usage entry — {defect}",
                    "taxonomy.dataset-usage-malformed",
                )

        # --- A-D3: external-produced derived artifact must record its inputs ---
        # derivation.inputs is gated to origin=derived, so an origin=external model
        # output / meta-analysis can only record inputs via dataset_usage
        # (role upstream|training). Without it, independence is not derivable.
        if fm.get("origin") == "external" and source_class == "derived":
            has_provenance = any(
                isinstance(e, dict) and e.get("role") in _DEPENDENCE_PROVENANCE_ROLES
                for e in entries
            )
            if not has_provenance:
                yield _result(
                    Severity.WARN,
                    path,
                    f"{ident}: external derived artifact has no dataset_usage with "
                    f"role upstream|training; independence cannot be derived (A-D3)",
                    "taxonomy.external-derived-no-provenance",
                )


@Check(section="dataset taxonomy", order=31)
def check_dataset_taxonomy(ctx: ValidateContext) -> Iterator[Result]:
    yield from evaluate_dataset_taxonomy(dataset_frontmatters(ctx))

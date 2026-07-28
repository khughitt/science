"""Dataset metadata vocabulary checks: license, tier, update_cadence.

Reads RAW frontmatter via `dataset_frontmatters` (matching dataset_taxonomy.py) so
a malformed entity can never crash the strict loader. All findings are WARN — never
ERROR — so nothing blocks `validate` by default.

The allowed-cadence set is kept equal to the `update_cadence` enum in
science-pkg-entity-1.0.json (a test enforces the equality); growing the vocabulary
means updating the schema first, then this constant.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import cast

from science_model.licenses import LICENSE_SENTINELS, is_recognized, suggest

from science_model.audit import FindingRule

from science_tool.validate.findings import validation_observation
from science_tool.validate.findings import declare_validation_rules
from science_tool.validate._helpers import dataset_frontmatters
from science_tool.validate.checks import Check, CheckObservation
from science_tool.validate.context import ValidateContext
from science_tool.validate.observations import ValidationNotice
from science_tool.validate.result import Result, Severity
from science_tool.datasets.semantics import dataset_class_for, has_runtime_artifact

_ALLOWED_TIERS = {"use-now", "evaluate-next", "track"}
_ALLOWED_CADENCES = {
    "static",
    "rolling",
    "monthly",
    "quarterly",
    "annual",
    "versioned-releases",
}
_DEPOSIT_METHODS = {"", "retrieved", "credential-confirmed", "landing-confirmed"}
_REFERENCE_METHODS = {"", "credential-confirmed", "landing-confirmed", "metadata-confirmed"}
_POINTER_METHODS = {"", "landing-confirmed", "metadata-confirmed"}


SECTION, RULES = declare_validation_rules(
    section_id="dataset-metadata",
    section_title="dataset metadata",
    section_order=131,
    rule_ids=(
        "dataset.cadence-unrecognized",
        "dataset.class-unrecognized",
        "dataset.legacy-missing-class",
        "dataset.license-missing",
        "dataset.license-unrecognized",
        "dataset.method-class-mismatch",
        "dataset.pointer-runtime-artifact",
        "dataset.reference-missing-source-url",
        "dataset.reference-runtime-artifact",
        "dataset.tier-unrecognized",
    ),
    severities=frozenset({"error", "warn", "info"}),
)


def _result(
    severity: Severity,
    path: str | None,
    message: str,
    rule: FindingRule,
) -> Result | ValidationNotice:
    return cast(
        Result | ValidationNotice,
        validation_observation(
            severity=severity,
            path=Path(path) if path else None,
            line=None,
            message=message,
            rule=rule,
            task=None,
            qualifiers={"key": []},
        ),
    )


def _enum_finding(
    value: object, allowed: set[str], *, path: str | None, ident: str, field: str, rule: FindingRule
) -> Result | ValidationNotice | None:
    """Warn when a present value is non-string or outside `allowed`. Absent
    (None / "" / whitespace-only string) → no finding. Never raises on odd types."""
    if value is None:
        return None
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped or stripped in allowed:
            return None
        display: object = stripped
    else:
        # Present but not a string (e.g. a list or int): unrecognized, not a crash.
        display = value
    return _result(
        Severity.WARN,
        path,
        f"{ident}: unrecognized {field} {display!r} (expected one of {sorted(allowed)})",
        rule,
    )


def evaluate_dataset_metadata(
    datasets: Iterable[dict],
) -> Iterator[Result | ValidationNotice]:
    """Pure core: `datasets` are raw frontmatter dicts (each with `_path`).

    Defensive against malformed raw frontmatter: non-string license/tier/cadence
    values become warnings, never exceptions (this runs on un-validated input).
    """
    for fm in datasets:
        if fm.get("kind") != "dataset":
            continue
        path = fm.get("_path")
        ident = fm.get("id", "?")
        origin = fm.get("origin")

        # --- license ---
        license_raw = fm.get("license")
        if isinstance(license_raw, str):
            license_value: str | None = license_raw.strip()
        elif license_raw is None:
            license_value = ""
        else:
            license_value = None  # present but non-string → unrecognized

        if license_value == "":
            if origin == "external":
                yield _result(
                    Severity.WARN,
                    path,
                    f"{ident}: external dataset declares no license "
                    f"(set an SPDX id, or a sentinel: {sorted(LICENSE_SENTINELS)})",
                    RULES["dataset.license-missing"],
                )
        elif license_value is None or not is_recognized(license_value):
            hint = suggest(license_value) if isinstance(license_value, str) else None
            suffix = f" — did you mean {hint!r}?" if hint else ""
            display = license_raw if license_value is None else license_value
            yield _result(
                Severity.WARN,
                path,
                f"{ident}: unrecognized license {display!r}{suffix}",
                RULES["dataset.license-unrecognized"],
            )

        # --- tier / update_cadence (present-but-unrecognized only) ---
        tier_finding = _enum_finding(
            fm.get("tier"),
            _ALLOWED_TIERS,
            path=path,
            ident=ident,
            field="tier",
            rule=RULES["dataset.tier-unrecognized"],
        )
        if tier_finding is not None:
            yield tier_finding

        cadence_finding = _enum_finding(
            fm.get("update_cadence"),
            _ALLOWED_CADENCES,
            path=path,
            ident=ident,
            field="update_cadence",
            rule=RULES["dataset.cadence-unrecognized"],
        )
        if cadence_finding is not None:
            yield cadence_finding

        raw_dataset_class = fm.get("dataset_class")
        if not (isinstance(raw_dataset_class, str) and raw_dataset_class.strip()):
            yield _result(
                Severity.INFO,
                path,
                f"{ident}: dataset_class is missing; defaulting to deposit until the row is touched",
                RULES["dataset.legacy-missing-class"],
            )

        try:
            dataset_class = dataset_class_for(fm)
        except ValueError as exc:
            yield _result(Severity.WARN, path, f"{ident}: {exc}", RULES["dataset.class-unrecognized"])
            continue

        access = fm.get("access")
        access_block = access if isinstance(access, dict) else {}
        method = access_block.get("verification_method", "")
        method_value = method.strip() if isinstance(method, str) else method
        allowed_methods = {
            "deposit": _DEPOSIT_METHODS,
            "reference": _REFERENCE_METHODS,
            "pointer": _POINTER_METHODS,
        }[dataset_class]
        if method_value not in allowed_methods:
            yield _result(
                Severity.WARN,
                path,
                f"{ident}: verification_method {method_value!r} is incompatible with dataset_class {dataset_class!r}",
                RULES["dataset.method-class-mismatch"],
            )

        if dataset_class in {"reference", "pointer"} and not (
            isinstance(access_block.get("source_url"), str) and access_block["source_url"].strip()
        ):
            yield _result(
                Severity.WARN,
                path,
                f"{ident}: {dataset_class} dataset requires access.source_url",
                RULES["dataset.reference-missing-source-url"],
            )

        if dataset_class == "reference" and has_runtime_artifact(fm):
            yield _result(
                Severity.WARN,
                path,
                f"{ident}: reference dataset has a runtime artifact; convert it to dataset_class deposit",
                RULES["dataset.reference-runtime-artifact"],
            )
        if dataset_class == "pointer" and has_runtime_artifact(fm):
            yield _result(
                Severity.WARN,
                path,
                f"{ident}: pointer dataset has a runtime artifact; convert it to dataset_class deposit",
                RULES["dataset.pointer-runtime-artifact"],
            )


@Check(section=SECTION, order=32, producer_id="validate.dataset-metadata", rules=tuple(RULES.values()))
def check_dataset_metadata(ctx: ValidateContext) -> Iterator[CheckObservation]:
    yield from evaluate_dataset_metadata(dataset_frontmatters(ctx))

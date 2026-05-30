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

from science_model.licenses import LICENSE_SENTINELS, is_recognized, suggest

from science_tool.validate._helpers import dataset_frontmatters
from science_tool.validate.checks import Check
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Result, Severity

_ALLOWED_TIERS = {"use-now", "evaluate-next", "track"}
_ALLOWED_CADENCES = {
    "static",
    "rolling",
    "monthly",
    "quarterly",
    "annual",
    "versioned-releases",
}


def _result(severity: Severity, path: str | None, message: str, rule: str) -> Result:
    return Result(severity, Path(path) if path else None, None, message, rule, None)


def _enum_finding(
    value: object, allowed: set[str], *, path: str | None, ident: str, field: str, rule: str
) -> Result | None:
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


def evaluate_dataset_metadata(datasets: Iterable[dict]) -> Iterator[Result]:
    """Pure core: `datasets` are raw frontmatter dicts (each with `_path`).

    Defensive against malformed raw frontmatter: non-string license/tier/cadence
    values become warnings, never exceptions (this runs on un-validated input).
    """
    for fm in datasets:
        if (fm.get("kind") or fm.get("type")) != "dataset":
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
                    "dataset.license-missing",
                )
        elif license_value is None or not is_recognized(license_value):
            hint = suggest(license_value) if isinstance(license_value, str) else None
            suffix = f" — did you mean {hint!r}?" if hint else ""
            display = license_raw if license_value is None else license_value
            yield _result(
                Severity.WARN,
                path,
                f"{ident}: unrecognized license {display!r}{suffix}",
                "dataset.license-unrecognized",
            )

        # --- tier / update_cadence (present-but-unrecognized only) ---
        tier_finding = _enum_finding(
            fm.get("tier"), _ALLOWED_TIERS,
            path=path, ident=ident, field="tier", rule="dataset.tier-unrecognized",
        )
        if tier_finding is not None:
            yield tier_finding

        cadence_finding = _enum_finding(
            fm.get("update_cadence"), _ALLOWED_CADENCES,
            path=path, ident=ident, field="update_cadence", rule="dataset.cadence-unrecognized",
        )
        if cadence_finding is not None:
            yield cadence_finding


@Check(section="dataset metadata", order=32)
def check_dataset_metadata(ctx: ValidateContext) -> Iterator[Result]:
    yield from evaluate_dataset_metadata(dataset_frontmatters(ctx))

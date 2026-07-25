"""Health-report projection: section classification and severity thresholding.

Lives beside health rather than in ``budget/`` so the budgeting mechanism stays free of
domain knowledge.

The classification was verified against the TypedDicts on 2026-07-24 and getting it wrong
is not cosmetic: treating ``cross_paper_evidence`` as a ``counts_as_issue`` section hides
its errors entirely, because it has no such field.

``counts_as_issue`` is ISSUE-COUNT MEMBERSHIP, not severity. It decides whether a row
feeds ``count_issues`` and is never used to filter display -- the two are orthogonal, and
``prose_epistemics`` emits ``severity: "warning"`` together with ``counts_as_issue: True``.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


class UnknownSection(Exception):
    """A report section with no registered classification.

    Raised rather than guessed: silently capping an unrecognised section would be exactly
    the silent-degradation this program exists to remove.
    """


SEVERITY_SECTIONS = frozenset(
    {
        "validation",
        "schema_invalid",
        "dataset_anomalies",
        "entity_identity",
        "cross_paper_evidence",
        "prose_epistemics",
    }
)

COUNTS_AS_ISSUE_SECTIONS = frozenset({"managed_artifacts"})

UNFILTERED_SECTIONS = frozenset(
    {
        "agent_context",
        "archive_lag",
        "identity_policy",
        "invalid_entity_aspects",
        "layered_claims",
        "legacy_task_type",
        "lingering_tags_lines",
        "unregistered_ref_kinds",
        "unresolved_refs",
        "tooling_scaffold",
        "accepted_validation",
        # An unwired check DID NOT RUN. graph/health.py:60 keeps it out of total_issues so
        # a report containing one cannot claim the project is clean; hiding it behind a
        # severity default would defeat exactly that.
        "unwired_checks",
    }
)

# Sections whose rows live under a "findings" key rather than at the top level.
NESTED_FINDING_SECTIONS = frozenset({"cross_paper_evidence", "prose_epistemics"})

# Registered non-row mappings that pass through projection after a shape check.
MAPPING_SECTIONS = frozenset({"archive_lag", "layered_claims"})

# Non-list sections that pass through untouched. This is an ALLOW-LIST, not a type test:
# any other non-list key is refused. `coverage_gaps` is deliberately absent -- it is a local
# inside `build_health_report`, never a report key (`health.py:341-351`).
SCALAR_SECTIONS = frozenset({"total_issues", "_meta"})

SEVERITY_ORDER: dict[str, int] = {"info": 0, "warning": 1, "warn": 1, "error": 2}

_THRESHOLD_FLOOR: dict[str, int] = {"all": 0, "warn": 1, "error": 2}


def meets_threshold(row: Mapping[str, Any], threshold: str) -> bool:
    """True when ``row`` is at or above ``threshold``.

    A row with no ``severity`` key survives every threshold: absence of the signal is not
    evidence of low severity, and dropping such rows would hide findings. A present value,
    including explicit ``None``, must be a registered severity string.
    """
    if threshold not in _THRESHOLD_FLOOR:
        raise ValueError(f"unknown health threshold {threshold!r}")
    if "severity" not in row:
        return True
    severity = row["severity"]
    if not isinstance(severity, str) or severity not in SEVERITY_ORDER:
        raise ValueError(f"unknown health severity {severity!r}")
    return SEVERITY_ORDER[severity] >= _THRESHOLD_FLOOR[threshold]


SECTION_ROW_CAP = 40

_ROW_SCHEMAS: dict[str, dict[str, str]] = {
    "unresolved_refs": {
        "target": "str",
        "mention_count": "int",
        "sources": "str_list",
        "looks_like": "str",
    },
    "unregistered_ref_kinds": {
        "kind": "str",
        "field": "str",
        "mention_count": "int",
        "refs": "str_list",
        "sources": "str_list",
    },
    "lingering_tags_lines": {"file": "str", "values": "str_list"},
    "agent_context": {
        "code": "str",
        "source_file": "str",
        "detail": "str",
        "fix": "str",
    },
    "identity_policy": {
        "check": "str",
        "entity_id": "str",
        "source_file": "str",
        "message": "str",
    },
    "entity_identity": {
        "code": "str",
        "severity": "severity",
        "message": "str",
        "path": "optional_str",
        "canonical_id": "optional_str",
    },
    "legacy_task_type": {
        "task_id": "str",
        "legacy_type": "str",
        "source_file": "str",
    },
    "invalid_entity_aspects": {
        "entity_id": "str",
        "source_file": "str",
        "message": "str",
    },
    # dataset_anomalies is deliberately absent: HealthReport declares list[dict], so
    # only its projection-relevant severity field is validated below.
    "schema_invalid": {
        "code": "str",
        "severity": "severity",
        "kind": "str",
        "path": "str",
        "message": "str",
    },
    "managed_artifacts": {
        "name": "str",
        "install_target": "str",
        "version": "str",
        "status": "str",
        "detail": "str",
        "counts_as_issue": "bool",
    },
    "tooling_scaffold": {"code": "str", "detail": "str", "fix": "str"},
    "validation": {
        "severity": "severity",
        "path": "optional_str",
        "line": "optional_int",
        "message": "str",
        "rule": "optional_str",
        "task": "optional_str",
    },
    "accepted_validation": {
        "severity": "severity",
        "path": "optional_str",
        "line": "optional_int",
        "message": "str",
        "rule": "optional_str",
        "task": "optional_str",
        "accepted_reason": "str",
    },
    "unwired_checks": {
        "check": "str",
        "code": "str",
        "reason": "optional_str",
    },
}

_CROSS_PAPER_FINDING_SCHEMA = {
    "code": "str",
    "severity": "severity",
    "sidecar": "str",
    "annotation": "str",
    "reason": "str",
    "detail": "str",
}

_LAYERED_ROW_SCHEMAS: dict[str, dict[str, str]] = {
    "rival_model_packets_missing_discriminating_predictions": {
        "proposition": "str",
        "source_path": "str",
        "packet_id": "str",
    },
    "migration_issues": {
        "proposition": "str",
        "source_path": "str",
        "warnings": "str_list",
        "todos": "str_list",
    },
}

_GENERIC_ROW_SECTIONS = frozenset({"dataset_anomalies"})


def _required_field(container: Mapping[str, Any], key: str, path: str) -> Any:
    if key not in container:
        raise ValueError(f"{path} is missing required field {key!r}")
    return container[key]


def _required_mapping(
    container: Mapping[str, Any],
    key: str,
    path: str,
) -> Mapping[str, Any]:
    value = _required_field(container, key, path)
    if not isinstance(value, Mapping):
        raise TypeError(f"{path}.{key} must be a mapping, got {type(value).__name__}")
    return value


def _required_list(container: Mapping[str, Any], key: str, path: str) -> list[Any]:
    value = _required_field(container, key, path)
    if not isinstance(value, list):
        raise TypeError(f"{path}.{key} must be a list, got {type(value).__name__}")
    return value


def _validate_mapping_members(rows: list[Any], path: str) -> None:
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping):
            raise TypeError(f"{path}[{index}] must be a mapping, got {type(row).__name__}")


def _validate_field_kind(value: Any, kind: str, path: str) -> None:
    if kind == "severity":
        if not isinstance(value, str) or value not in SEVERITY_ORDER:
            raise ValueError(f"unknown health severity {value!r} at {path}")
        return
    if kind == "str":
        valid = isinstance(value, str)
        expected = "a str"
    elif kind == "optional_str":
        valid = value is None or isinstance(value, str)
        expected = "a str or None"
    elif kind == "int":
        valid = type(value) is int
        expected = "an int"
    elif kind == "optional_int":
        valid = value is None or type(value) is int
        expected = "an int or None"
    elif kind == "bool":
        valid = type(value) is bool
        expected = "a bool"
    elif kind == "numeric":
        valid = isinstance(value, (int, float)) and not isinstance(value, bool)
        expected = "numeric"
    elif kind == "str_list":
        valid = isinstance(value, list) and all(isinstance(item, str) for item in value)
        expected = "a list of str"
    else:  # pragma: no cover - schemas above are closed over these kinds
        raise AssertionError(f"unknown health projection field kind {kind!r}")
    if not valid:
        raise TypeError(f"{path} must be {expected}, got {type(value).__name__}")


def _validate_row_schema(
    row: Mapping[str, Any],
    schema: Mapping[str, str],
    path: str,
) -> None:
    for key, kind in schema.items():
        value = _required_field(row, key, path)
        _validate_field_kind(value, kind, f"{path}.{key}")


def _validate_row_section(rows: list[Any], section: str) -> None:
    path = f"health report section {section}"
    _validate_mapping_members(rows, path)
    schema = _ROW_SCHEMAS.get(section)
    for index, row in enumerate(rows):
        row_path = f"{path}[{index}]"
        if schema is not None:
            _validate_row_schema(row, schema, row_path)
        elif section in _GENERIC_ROW_SECTIONS:
            severity = _required_field(row, "severity", row_path)
            _validate_field_kind(severity, "severity", f"{row_path}.severity")
        else:  # pragma: no cover - every registered row section is explicit above
            raise AssertionError(f"health report section {section!r} has no row schema")


def _validate_integer_field(container: Mapping[str, Any], key: str, path: str) -> None:
    value = _required_field(container, key, path)
    if type(value) is not int:
        raise TypeError(f"{path}.{key} must be an int, got {type(value).__name__}")


def _validate_coverage_metric(
    layered: Mapping[str, Any],
    key: str,
    path: str,
) -> None:
    metric = _required_mapping(layered, key, path)
    metric_path = f"{path}.{key}"
    _validate_integer_field(metric, "numerator", metric_path)
    _validate_integer_field(metric, "denominator", metric_path)
    fraction = _required_field(metric, "fraction", metric_path)
    if not isinstance(fraction, (int, float)) or isinstance(fraction, bool):
        raise TypeError(
            f"{metric_path}.fraction must be numeric, got {type(fraction).__name__}"
        )


def _validate_mapping_section(section: str, value: Mapping[str, Any]) -> None:
    path = f"health report section {section}"
    if section == "archive_lag":
        for key in ("done_in_active", "retired_in_active", "missing_completed"):
            _validate_integer_field(value, key, path)
        return

    for key in (
        "proposition_claim_layer_coverage",
        "causal_leaning_identification_coverage",
    ):
        _validate_coverage_metric(value, key, path)
    for key in (
        "rival_model_packets_missing_discriminating_predictions",
        "migration_issues",
    ):
        rows = _required_list(value, key, path)
        _validate_mapping_members(rows, f"{path}.{key}")
        for index, row in enumerate(rows):
            _validate_row_schema(
                row,
                _LAYERED_ROW_SCHEMAS[key],
                f"{path}.{key}[{index}]",
            )


def _validate_nested_section(
    section: str,
    value: Mapping[str, Any],
) -> list[Any]:
    path = f"health report section {section}"
    if section == "cross_paper_evidence":
        for key in ("status", "empty_state"):
            field = _required_field(value, key, path)
            if not isinstance(field, str):
                raise TypeError(f"{path}.{key} must be a str, got {type(field).__name__}")
        _required_mapping(value, "summary", path)
        propositions = _required_list(value, "propositions", path)
        _validate_mapping_members(propositions, f"{path}.propositions")
    else:
        applicable = _required_field(value, "applicable", path)
        if type(applicable) is not bool:
            raise TypeError(
                f"{path}.applicable must be a bool, got {type(applicable).__name__}"
            )
        _required_mapping(value, "summary", path)
        _required_mapping(value, "coverage", path)
        sources = _required_list(value, "sources", path)
        _validate_mapping_members(sources, f"{path}.sources")

    findings = _required_list(value, "findings", path)
    _validate_mapping_members(findings, f"{path}.findings")
    for index, finding in enumerate(findings):
        finding_path = f"{path}.findings[{index}]"
        if section == "cross_paper_evidence":
            _validate_row_schema(
                finding,
                _CROSS_PAPER_FINDING_SCHEMA,
                finding_path,
            )
        else:
            severity = _required_field(finding, "severity", finding_path)
            _validate_field_kind(severity, "severity", f"{finding_path}.severity")
            counts_as_issue = _required_field(finding, "counts_as_issue", finding_path)
            _validate_field_kind(
                counts_as_issue,
                "bool",
                f"{finding_path}.counts_as_issue",
            )
    return findings


def _validate_scalar_section(section: str, value: Any) -> None:
    path = f"health report section {section}"
    if section == "total_issues":
        if type(value) is not int:
            raise TypeError(f"{path} must be an int, got {type(value).__name__}")
        return

    if not isinstance(value, Mapping):
        raise TypeError(f"{path} must be a mapping, got {type(value).__name__}")
    timings = _required_list(value, "timings", path)
    _validate_mapping_members(timings, f"{path}.timings")
    for index, timing in enumerate(timings):
        _validate_row_schema(
            timing,
            {"name": "str", "duration_seconds": "numeric"},
            f"{path}.timings[{index}]",
        )
    duration = _required_field(value, "total_duration_seconds", path)
    _validate_field_kind(duration, "numeric", f"{path}.total_duration_seconds")


def _classified(section: str) -> str:
    if section in UNFILTERED_SECTIONS:
        return "unfiltered"
    if section in SEVERITY_SECTIONS:
        return "severity"
    if section in COUNTS_AS_ISSUE_SECTIONS:
        return "counts_as_issue"
    raise UnknownSection(
        f"health report section {section!r} has no classification. Add it to "
        f"SEVERITY_SECTIONS, COUNTS_AS_ISSUE_SECTIONS, or UNFILTERED_SECTIONS in "
        f"graph/health_projection.py. Refusing rather than guessing a cap."
    )


def _project_section(
    rows: list[Any],
    section: str,
    threshold: str,
    cap: int,
    omitted: dict[str, int],
) -> list[Any]:
    _validate_mapping_members(rows, f"health report section {section}")
    kind = _classified(section)
    if kind == "unfiltered":
        return rows

    if kind == "severity":
        kept = [row for row in rows if meets_threshold(row, threshold)]
    else:
        kept = list(rows)

    capped = kept[:cap]
    dropped = (len(rows) - len(kept)) + (len(kept) - len(capped))
    if dropped:
        omitted[section] = dropped
    return capped


def _validate_report(report: Mapping[str, Any]) -> None:
    """Validate the complete registered source shape before narrowing any section."""
    for key, value in report.items():
        if key in SCALAR_SECTIONS:
            _validate_scalar_section(key, value)
            continue

        if key in NESTED_FINDING_SECTIONS:
            if not isinstance(value, Mapping):
                raise TypeError(
                    f"health report section {key!r} must be a mapping, "
                    f"got {type(value).__name__}"
                )
            _validate_nested_section(key, value)
            continue

        if key in MAPPING_SECTIONS:
            if not isinstance(value, Mapping):
                raise TypeError(
                    f"health report section {key!r} must be a mapping, "
                    f"got {type(value).__name__}"
                )
            _validate_mapping_section(key, value)
            continue

        # Classify before checking the value type so unknown scalars are refused as
        # unregistered sections rather than mislabeled as malformed row sections.
        _classified(key)
        if not isinstance(value, list):
            raise TypeError(
                f"health report section {key!r} must be a list, "
                f"got {type(value).__name__}"
            )
        _validate_row_section(value, key)


def project_health_report(
    report: dict[str, Any],
    threshold: str,
    cap: int | None = None,
) -> dict[str, Any]:
    """Narrow a health report for display without changing what it claims.

    ``total_issues`` is copied through untouched: it is the clean-report gate
    (``graph/health_cli.py:158``) and redefining it as a displayed count would let a
    filtered report announce "Project is clean". ``displayed_issues`` is computed by
    ``count_issues`` over the PROJECTED report, so "showing N of M" compares like with
    like rather than a raw row count against an issue count.
    """
    from science_tool.graph.health import count_issues

    if cap is not None:
        if type(cap) is not int:
            raise TypeError(
                f"health projection cap must be an int, got {type(cap).__name__}"
            )
        if cap < 0:
            raise ValueError(f"health projection cap must be non-negative, got {cap}")
    if threshold not in _THRESHOLD_FLOOR:
        raise ValueError(f"unknown health threshold {threshold!r}")

    effective_cap = SECTION_ROW_CAP if cap is None else cap
    _validate_report(report)
    # Task 8's counter is also the complete-root contract validator. Run it over the
    # source before narrowing, then again below over the projection for displayed_issues.
    count_issues(report)

    omitted: dict[str, int] = {}
    projected: dict[str, Any] = {}

    for key, value in report.items():
        # SCALAR_SECTIONS is the ONLY way a non-list section skips classification. Testing
        # `not isinstance(value, (list, dict))` here instead would let a newly added
        # boolean/int/string section pass through unexamined purely because of its Python
        # type -- the silent escape this projector exists to prevent.
        if key in SCALAR_SECTIONS:
            _validate_scalar_section(key, value)
            projected[key] = value
            continue

        if key in NESTED_FINDING_SECTIONS:
            if not isinstance(value, Mapping):
                raise TypeError(
                    f"health report section {key!r} must be a mapping, "
                    f"got {type(value).__name__}"
                )
            findings = _validate_nested_section(key, value)
            projected[key] = {
                **value,
                "findings": _project_section(
                    findings, key, threshold, effective_cap, omitted
                ),
            }
            continue

        if key in MAPPING_SECTIONS:
            if not isinstance(value, Mapping):
                raise TypeError(
                    f"health report section {key!r} must be a mapping, "
                    f"got {type(value).__name__}"
                )
            _validate_mapping_section(key, value)
            projected[key] = value
            continue

        # Classification happens before the list check so an unknown scalar still raises
        # UnknownSection rather than being mistaken for a malformed known section.
        _classified(key)
        if not isinstance(value, list):
            raise TypeError(
                f"health report section {key!r} must be a list, "
                f"got {type(value).__name__}"
            )
        projected[key] = _project_section(value, key, threshold, effective_cap, omitted)

    projected["displayed_issues"] = count_issues(projected)
    projected["section_omitted"] = omitted
    return projected

"""Checks for generated Labnote export package descriptors."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from science_model.audit import FindingRule

from science_tool.labnote_view_contract import descriptor_errors
from science_tool.validate.findings import validation_observation
from science_tool.validate.findings import declare_validation_rules
from science_tool.validate.checks import Check, CheckObservation
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Severity

SECTION, RULES = declare_validation_rules(
    section_id="labnote-export",
    section_title="labnote export",
    section_order=145,
    rule_ids=(
        "labnote-export.hidden-kinds-malformed",
        "labnote-export.kind-visible-and-hidden",
        "labnote-export.view-entity-types-missing",
        "labnote-export.view-id-invalid",
        "labnote-export.view-malformed",
        "labnote-export.view-route-mismatch",
        "labnote-export.view-surface-invalid",
        "labnote-export.views-json-invalid",
    ),
    severities=frozenset({"error", "warn", "info"}),
)


def _result(
    path: str | Path | None,
    message: str,
    rule: FindingRule,
    *,
    key: list[str],
) -> CheckObservation:
    return validation_observation(
        severity=Severity.ERROR,
        path=Path(path) if path else None,
        line=None,
        message=message,
        rule=rule,
        task=None,
        qualifiers={"key": key},
    )


def evaluate_labnote_export_views(views: dict[str, Any], path: str | Path | None) -> Iterator[CheckObservation]:
    """Report every structural defect the shared descriptor contract finds.

    Route derivation and surface legality live in `labnote_view_contract`, so the
    exporter and this check can never drift. Deduplication keys on the error's own
    canonical identity, which is descriptor content rather than a view ID — two
    different malformed views that share an ID must both be reported.
    """
    emitted: set[tuple[str, str, str | None]] = set()
    for error in descriptor_errors(views):
        key = (error.code, error.field, error.identity)
        if key in emitted:
            continue
        emitted.add(key)
        yield _result(
            path,
            error.message,
            RULES[f"labnote-export.{error.code}"],
            key=[error.code, error.identity if error.identity is not None else error.field],
        )


@Check(section=SECTION, order=890, producer_id="validate.labnote-export", rules=tuple(RULES.values()))
def check_labnote_export(ctx: ValidateContext) -> Iterator[CheckObservation]:
    views_path = ctx.project_root / ".labnote" / "app_export" / "views.json"
    if not views_path.exists():
        return

    try:
        views = json.loads(views_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        yield _result(
            views_path,
            f"Labnote views.json is not valid JSON: {exc}",
            RULES["labnote-export.views-json-invalid"],
            key=["json-invalid"],
        )
        return

    if not isinstance(views, dict):
        yield _result(
            views_path,
            "Labnote views.json must contain a JSON object",
            RULES["labnote-export.views-json-invalid"],
            key=["root-not-object"],
        )
        return

    yield from evaluate_labnote_export_views(views, views_path)

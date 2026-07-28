"""Checks for generated Labnote export package descriptors."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from science_model.audit import FindingRule
from science_model.audit.fingerprint import canonical_json

from science_tool.validate.findings import validation_observation
from science_tool.validate.findings import declare_validation_rules
from science_tool.validate.checks import Check, CheckObservation
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Severity

_BROWSE_SURFACES = {"explore", "findings"}


SECTION, RULES = declare_validation_rules(
    section_id="labnote-export",
    section_title="labnote export",
    section_order=145,
    rule_ids=(
        "labnote-export.view-entity-types-missing",
        "labnote-export.view-malformed",
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


def _valid_entity_types(value: object) -> bool:
    return isinstance(value, list) and len(value) > 0 and all(isinstance(item, str) and item.strip() for item in value)


def evaluate_labnote_export_views(views: dict[str, Any], path: str | Path | None) -> Iterator[CheckObservation]:
    emitted: set[tuple[str, str]] = set()
    for index, view in enumerate(views.get("views") or []):
        view_key = canonical_json(view).decode("utf-8")
        if not isinstance(view, dict):
            identity = ("view-malformed", view_key)
            if identity in emitted:
                continue
            emitted.add(identity)
            yield _result(
                path,
                f"views[{index}]: view must be a mapping",
                RULES["labnote-export.view-malformed"],
                key=list(identity),
            )
            continue

        surface = view.get("surface")
        if surface not in _BROWSE_SURFACES:
            continue
        if _valid_entity_types(view.get("entity_types")):
            continue

        identity = ("view-entity-types-missing", view_key)
        if identity in emitted:
            continue
        emitted.add(identity)
        view_id = view.get("id") or index
        yield _result(
            path,
            f"view {view_id}: {surface} views must declare non-empty entity_types",
            RULES["labnote-export.view-entity-types-missing"],
            key=list(identity),
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

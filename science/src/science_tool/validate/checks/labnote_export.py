"""Checks for generated Labnote export package descriptors."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from science_tool.validate.checks import Check
from science_tool.validate.context import ValidateContext
from science_tool.validate.result import Result, Severity

_BROWSE_SURFACES = {"explore", "findings"}


def _result(path: str | Path | None, message: str, rule: str) -> Result:
    return Result(Severity.ERROR, Path(path) if path else None, None, message, rule, None)


def _valid_entity_types(value: object) -> bool:
    return isinstance(value, list) and len(value) > 0 and all(isinstance(item, str) and item.strip() for item in value)


def evaluate_labnote_export_views(views: dict[str, Any], path: str | Path | None) -> Iterator[Result]:
    for index, view in enumerate(views.get("views") or []):
        if not isinstance(view, dict):
            yield _result(
                path,
                f"views[{index}]: view must be a mapping",
                "labnote-export.view-malformed",
            )
            continue

        surface = view.get("surface")
        if surface not in _BROWSE_SURFACES:
            continue
        if _valid_entity_types(view.get("entity_types")):
            continue

        view_id = view.get("id") or index
        yield _result(
            path,
            f"view {view_id}: {surface} views must declare non-empty entity_types",
            "labnote-export.view-entity-types-missing",
        )


@Check("labnote export", 890)
def check_labnote_export(ctx: ValidateContext) -> Iterator[Result]:
    views_path = ctx.project_root / ".labnote" / "app_export" / "views.json"
    if not views_path.exists():
        return

    try:
        views = json.loads(views_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        yield _result(
            views_path,
            f"Labnote views.json is not valid JSON: {exc}",
            "labnote-export.views-json-invalid",
        )
        return

    if not isinstance(views, dict):
        yield _result(
            views_path,
            "Labnote views.json must contain a JSON object",
            "labnote-export.views-json-invalid",
        )
        return

    yield from evaluate_labnote_export_views(views, views_path)

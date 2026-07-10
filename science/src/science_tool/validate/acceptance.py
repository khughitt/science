from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from science_tool.data_root import project_config_path
from science_tool.validate.result import Result, Severity


def filter_accepted_warnings(project_root: Path, results: list[Result]) -> list[Result]:
    entries = _accepted_validation_entries(project_root)
    if not entries:
        return results
    return [result for result in results if not _is_accepted_warning(result, entries)]


def _accepted_validation_entries(project_root: Path) -> list[dict[str, Any]]:
    manifest_path = project_config_path(project_root)
    try:
        manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    except OSError:
        return []
    if not isinstance(manifest, dict):
        return []
    health = manifest.get("health")
    if not isinstance(health, dict):
        return []
    entries = health.get("accepted_validation")
    if not isinstance(entries, list):
        return []
    return [entry for entry in entries if isinstance(entry, dict)]


def _is_accepted_warning(result: Result, entries: list[dict[str, Any]]) -> bool:
    if result.severity is not Severity.WARN:
        return False
    return any(_accepts_result(entry, result) for entry in entries)


def _accepts_result(entry: dict[str, Any], result: Result) -> bool:
    reason = entry.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        return False
    rule = entry.get("rule")
    if not isinstance(rule, str) or result.rule != rule:
        return False
    severity = entry.get("severity")
    if isinstance(severity, str) and severity not in {"warn", "warning"}:
        return False
    path = entry.get("path")
    if isinstance(path, str) and (str(result.path) if result.path is not None else None) != path:
        return False
    task = entry.get("task")
    if isinstance(task, str) and result.task != task:
        return False
    return _text_matches(result.message, entry.get("message_contains"))


def _text_matches(value: str, needles: object) -> bool:
    if needles is None:
        return True
    if isinstance(needles, str):
        return needles in value
    if isinstance(needles, list):
        return all(isinstance(needle, str) and needle in value for needle in needles)
    return False

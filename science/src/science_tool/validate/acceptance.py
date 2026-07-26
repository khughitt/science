from __future__ import annotations

import re
from pathlib import Path, PurePosixPath
from typing import Any

import yaml

from science_tool.correspondence.signature import SIGNATURE_VERSION
from science_tool.data_root import project_config_path
from science_tool.validate.result import Result, Severity

EVIDENCE_SCOPED_RULES: frozenset[str] = frozenset({"plan.correspondence-drift"})

# The EXACT emitted token — one literal ": " separator, no `\s*`. A bare `<version>:<hex>`,
# a bare `evidence-signature:` prefix, or a variant-whitespace spelling (`:v2:`, two spaces,
# a newline) is NOT evidence-scoped: it would pass a lax guard yet never substring-match the
# literal the check emits (`evidence-signature: {signature}`), so it must not qualify (§5.5).
#
# The version is READ from the signature module, never repeated here: a hardcoded copy is a
# second place the version lives, and it would keep honouring stale entries after a bump.
SIGNATURE_TOKEN_SPEC = f"evidence-signature: {SIGNATURE_VERSION}:<64-hex>"
_SIGNATURE_RE = re.compile(rf"\bevidence-signature: {SIGNATURE_VERSION}:[0-9a-f]{{64}}\b")


def accepted_validation_entries(project_root: Path) -> list[dict[str, Any]]:
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


def _message_contains_values(needles: object) -> list[str]:
    if isinstance(needles, str):
        return [needles]
    if isinstance(needles, list):
        return [n for n in needles if isinstance(n, str)]
    return []


def _text_matches(value: str, needles: object) -> bool:
    if needles is None:
        return True
    if isinstance(needles, str):
        return needles in value
    if isinstance(needles, list):
        return all(isinstance(needle, str) and needle in value for needle in needles)
    return False


def _severity_matches(entry_severity: object, finding_severity: str) -> bool:
    if not isinstance(entry_severity, str):
        return True
    norm = "warn" if entry_severity in {"warn", "warning"} else entry_severity
    fnorm = "warn" if finding_severity in {"warn", "warning"} else finding_severity
    return norm == fnorm


def entry_matches(
    entry: dict[str, Any],
    *,
    rule: str | None,
    severity: str,
    path: str | None,
    task: str | None,
    message: str,
) -> bool:
    reason = entry.get("reason")
    if not isinstance(reason, str) or not reason.strip():
        return False
    e_rule = entry.get("rule")
    if not isinstance(e_rule, str) or rule != e_rule:
        return False
    if not _severity_matches(entry.get("severity"), severity):
        return False
    e_path = entry.get("path")
    if isinstance(e_path, str) and path != e_path:
        return False
    e_task = entry.get("task")
    if isinstance(e_task, str) and task != e_task:
        return False
    return _text_matches(message, entry.get("message_contains"))


def entry_is_evidence_scoped(entry: dict[str, Any]) -> bool:
    return any(_SIGNATURE_RE.search(v) for v in _message_contains_values(entry.get("message_contains")))


def entry_path_is_project_relative(entry: dict[str, Any]) -> bool:
    """A scoped entry must name ONE non-empty, project-relative path. A missing or
    absolute `path` would let one evidence signature blind that rule across every plan
    in the tree (design §5.5), so it is rejected."""
    path = entry.get("path")
    return isinstance(path, str) and path != "" and not PurePosixPath(path).is_absolute()


def entry_is_well_scoped(entry: dict[str, Any]) -> bool:
    """The full acceptance gate for an evidence-scoped rule: complete signature token
    AND a project-relative path. Both `entry_suppresses` (fail-closed) and the
    malformed-acceptance check (Task 6) derive their decision from this one predicate."""
    return entry_is_evidence_scoped(entry) and entry_path_is_project_relative(entry)


def entry_suppresses(
    entry: dict[str, Any],
    *,
    rule: str | None,
    severity: str,
    path: str | None,
    task: str | None,
    message: str,
) -> bool:
    if not entry_matches(entry, rule=rule, severity=severity, path=path, task=task, message=message):
        return False
    if rule in EVIDENCE_SCOPED_RULES and not entry_is_well_scoped(entry):
        return False  # fail closed: an unscoped or unlocated entry for this rule never suppresses
    return True


def filter_accepted_warnings(project_root: Path, results: list[Result]) -> list[Result]:
    entries = accepted_validation_entries(project_root)
    if not entries:
        return results
    kept: list[Result] = []
    for result in results:
        if result.severity is not Severity.WARN:
            kept.append(result)
            continue
        suppressed = any(
            entry_suppresses(
                entry,
                rule=result.rule,
                severity=result.severity.value,
                path=str(result.path) if result.path is not None else None,
                task=result.task,
                message=result.message,
            )
            for entry in entries
        )
        if not suppressed:
            kept.append(result)
    return kept

from __future__ import annotations

import hashlib
import re
from pathlib import Path, PurePosixPath
from typing import Any, cast

import yaml

from science_model.audit import AcceptedFinding, AuditFinding, ReportedFinding
from science_model.audit.fingerprint import canonical_json

from science_tool.correspondence.signature import SIGNATURE_VERSION
from science_tool.data_root import project_config_path

EVIDENCE_SCOPED_RULES: frozenset[str] = frozenset({"plan.correspondence-drift"})


def canonical_acceptance_severity(severity: object) -> str | None:
    """Return the matcher spelling, or ``None`` for a wildcard value."""
    if not isinstance(severity, str):
        return None
    return "warn" if severity in {"warn", "warning"} else severity


def _pre_migration_key_fields(entry: dict[str, Any]) -> dict[str, object]:
    rule = entry.get("rule")
    if not isinstance(rule, str):
        raise ValueError("acceptance entry has no string rule")
    fields: dict[str, object] = {"rule": rule}
    severity = canonical_acceptance_severity(entry.get("severity"))
    if severity is not None:
        fields["severity"] = severity
    for name in ("path", "task"):
        value = entry.get(name)
        if isinstance(value, str):
            fields[name] = value
    needles = entry.get("message_contains")
    if isinstance(needles, str):
        fields["message_contains"] = [needles]
    elif isinstance(needles, list):
        if not all(isinstance(value, str) for value in needles):
            raise ValueError(
                "malformed message_contains cannot acquire an acceptance key"
            )
        fields["message_contains"] = list(needles)
    elif needles is not None:
        raise ValueError("malformed message_contains cannot acquire an acceptance key")
    return fields


def pre_migration_acceptance_key(entry: dict[str, Any]) -> str:
    payload = b"science.acceptance.v1\n" + canonical_json(
        _pre_migration_key_fields(entry)
    )
    return hashlib.sha256(payload).hexdigest()[:32]


def legacy_validation_fields(finding: AuditFinding) -> dict[str, object]:
    path = finding.subject.path if finding.subject.type == "path" else None
    task = finding.qualifiers.get("task")
    return {
        "rule": finding.rule_id,
        "severity": finding.severity,
        "path": path,
        "task": task if isinstance(task, str) else None,
        "message": finding.message,
    }


def partition_health_acceptances(
    project_root: Path, reported_findings: list[ReportedFinding]
) -> tuple[list[ReportedFinding], list[AcceptedFinding]]:
    entries = accepted_validation_entries(project_root)
    remaining: list[ReportedFinding] = []
    accepted: list[AcceptedFinding] = []
    for reported in reported_findings:
        if reported.producer_id != "validate":
            remaining.append(reported)
            continue
        fields = legacy_validation_fields(reported.finding)
        matched = next(
            (
                entry
                for entry in entries
                if entry_suppresses(
                    entry,
                    rule=cast(str, fields["rule"]),
                    severity=cast(str, fields["severity"]),
                    path=cast(str | None, fields["path"]),
                    task=cast(str | None, fields["task"]),
                    message=cast(str, fields["message"]),
                )
            ),
            None,
        )
        if matched is None:
            remaining.append(reported)
            continue
        accepted.append(
            AcceptedFinding(
                producer_id=reported.producer_id,
                finding=reported.finding,
                acceptance_key=pre_migration_acceptance_key(matched),
                reason=matched["reason"].strip(),
            )
        )
    return remaining, accepted


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
    canonical_entry = canonical_acceptance_severity(entry_severity)
    if canonical_entry is None:
        return True
    return canonical_entry == canonical_acceptance_severity(finding_severity)


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


def filter_accepted_warnings(
    project_root: Path,
    results: list[AuditFinding],
) -> list[AuditFinding]:
    entries = accepted_validation_entries(project_root)
    if not entries:
        return results
    kept: list[AuditFinding] = []
    for finding in results:
        if finding.severity != "warn":
            kept.append(finding)
            continue
        fields = legacy_validation_fields(finding)
        suppressed = any(
            entry_suppresses(
                entry,
                rule=finding.rule_id,
                severity=finding.severity,
                path=cast(str | None, fields["path"]),
                task=cast(str | None, fields["task"]),
                message=finding.message,
            )
            for entry in entries
        )
        if not suppressed:
            kept.append(finding)
    return kept

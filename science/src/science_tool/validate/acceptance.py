from __future__ import annotations

import base64
import hashlib
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path, PurePosixPath
from typing import Any, Literal, Mapping, cast

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from science_model.audit import AcceptedFinding, AuditFinding, ReportedFinding
from science_model.audit.fingerprint import canonical_json

from science_tool.correspondence.signature import SIGNATURE_VERSION
from science_tool.data_root import project_config_path

EVIDENCE_SCOPED_RULES: frozenset[str] = frozenset({"plan.correspondence-drift"})

AcceptanceSeverity = Literal["warn", "error"]
_SEVERITY_ORDER = {"warn": 0, "error": 1}


class AcceptedValidationEntry(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    finding_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    fingerprint_version: Literal[1]
    severity_scope: tuple[AcceptanceSeverity, ...]
    reason: str
    accepted_on: date | None = None

    @field_validator("fingerprint_version", mode="before")
    @classmethod
    def _strict_fingerprint_version(cls, value: object) -> int:
        if type(value) is not int or value != 1:
            raise ValueError("fingerprint_version must be the integer 1")
        return value

    @field_validator("severity_scope", mode="before")
    @classmethod
    def _canonical_scope(cls, value: object) -> tuple[str, ...]:
        if not isinstance(value, list) or not value:
            raise ValueError("severity_scope must be a non-empty list")
        if any(not isinstance(item, str) or item not in _SEVERITY_ORDER for item in value):
            raise ValueError("severity_scope members must be 'warn' or 'error'")
        return tuple(sorted(set(value), key=_SEVERITY_ORDER.__getitem__))

    @field_validator("reason")
    @classmethod
    def _nonblank_reason(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("reason must be nonblank")
        return normalized

    @property
    def acceptance_key(self) -> str:
        fields = {
            "finding_id": self.finding_id,
            "severity_scope": list(self.severity_scope),
        }
        payload = b"science.acceptance.v1\n" + canonical_json(fields)
        return hashlib.sha256(payload).hexdigest()[:32]


@dataclass(frozen=True)
class CurrentAcceptance:
    raw_digest: str
    entry: AcceptedValidationEntry


@dataclass(frozen=True)
class LegacyAcceptance:
    raw_digest: str
    raw: Mapping[str, object]


@dataclass(frozen=True)
class InvalidAcceptance:
    raw_digest: str
    error: str


ClassifiedAcceptance = CurrentAcceptance | LegacyAcceptance | InvalidAcceptance


def _digest_json_value(value: object, ancestors: frozenset[int] = frozenset()) -> object:
    if isinstance(value, date):
        return {"__science_yaml_date__": value.isoformat()}
    if isinstance(value, bytes):
        return {"__science_yaml_binary__": base64.b64encode(value).decode("ascii")}
    if isinstance(value, (Mapping, list, tuple, set, frozenset)):
        if id(value) in ancestors:
            return {"__science_yaml_cycle__": type(value).__qualname__}
        ancestors = ancestors | {id(value)}
    if isinstance(value, Mapping):
        if all(isinstance(key, str) for key in value):
            return {
                key: _digest_json_value(item, ancestors) for key, item in value.items()
            }
        pairs = [
            [_digest_json_value(key, ancestors), _digest_json_value(item, ancestors)]
            for key, item in value.items()
        ]
        return {"__science_yaml_mapping__": sorted(pairs, key=canonical_json)}
    if isinstance(value, (list, tuple)):
        return [_digest_json_value(item, ancestors) for item in value]
    if isinstance(value, (set, frozenset)):
        members = sorted(
            (_digest_json_value(item, ancestors) for item in value), key=canonical_json
        )
        return {"__science_yaml_set__": members}
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return {"__science_yaml_unsupported__": type(value).__qualname__}


def raw_acceptance_digest(raw: object) -> str:
    return hashlib.sha256(canonical_json(_digest_json_value(raw))).hexdigest()[:32]


def classify_acceptance_entry(raw: object) -> ClassifiedAcceptance:
    digest = raw_acceptance_digest(raw)
    if isinstance(raw, Mapping) and "finding_id" in raw:
        try:
            entry = AcceptedValidationEntry.model_validate(dict(raw))
        except ValidationError as exc:
            return InvalidAcceptance(digest, str(exc))
        return CurrentAcceptance(digest, entry)
    if isinstance(raw, Mapping) and isinstance(raw.get("rule"), str):
        return LegacyAcceptance(digest, dict(raw))
    return InvalidAcceptance(
        digest,
        "entry must be a current finding_id mapping or a legacy mapping with string rule",
    )


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
            raise ValueError("malformed message_contains cannot acquire an acceptance key")
        fields["message_contains"] = list(needles)
    elif needles is not None:
        raise ValueError("malformed message_contains cannot acquire an acceptance key")
    return fields


def pre_migration_acceptance_key(entry: dict[str, Any]) -> str:
    payload = b"science.acceptance.v1\n" + canonical_json(_pre_migration_key_fields(entry))
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
    entries = [
        entry
        for entry in accepted_validation_entries(project_root)
        if isinstance(entry, dict)
    ]
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


def accepted_validation_entries(project_root: Path) -> list[object]:
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
    return entries


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
    entries = [
        entry
        for entry in accepted_validation_entries(project_root)
        if isinstance(entry, dict)
    ]
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

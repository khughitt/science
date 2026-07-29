from __future__ import annotations

import base64
import hashlib
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Literal, Mapping

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from science_model.audit import AcceptedFinding, AuditFinding, ReportedFinding
from science_model.audit.fingerprint import canonical_json

from science_tool.data_root import project_config_path
from science_tool.findings.producers import FindingRegistry, validate_finding

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


def _digest_json_value(
    value: object,
    ancestors: frozenset[int] = frozenset(),
) -> object:
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
            return {key: _digest_json_value(item, ancestors) for key, item in value.items()}
        pairs = [
            [
                _digest_json_value(key, ancestors),
                _digest_json_value(item, ancestors),
            ]
            for key, item in value.items()
        ]
        return {"__science_yaml_mapping__": sorted(pairs, key=canonical_json)}
    if isinstance(value, (list, tuple)):
        return [_digest_json_value(item, ancestors) for item in value]
    if isinstance(value, (set, frozenset)):
        members = sorted(
            (_digest_json_value(item, ancestors) for item in value),
            key=canonical_json,
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


def partition_accepted_findings(
    project_root: Path,
    reported_findings: list[ReportedFinding],
    *,
    registry: FindingRegistry,
) -> tuple[list[ReportedFinding], list[AcceptedFinding]]:
    entries = tuple(
        classified.entry
        for raw in accepted_validation_entries(project_root)
        if isinstance(
            classified := classify_acceptance_entry(raw),
            CurrentAcceptance,
        )
    )
    remaining: list[ReportedFinding] = []
    accepted: list[AcceptedFinding] = []
    for reported in reported_findings:
        if reported.producer_id != "validate":
            remaining.append(reported)
            continue
        finding_id = validate_finding(
            registry,
            reported.producer_id,
            reported.finding,
        )
        matched = next(
            (
                entry
                for entry in entries
                if entry.finding_id == finding_id and reported.finding.severity in entry.severity_scope
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
                acceptance_key=matched.acceptance_key,
                reason=matched.reason,
            )
        )
    return remaining, accepted


def filter_accepted_warnings(
    project_root: Path,
    results: list[AuditFinding],
    *,
    registry: FindingRegistry,
) -> list[AuditFinding]:
    warnings = [
        ReportedFinding(producer_id="validate", finding=finding) for finding in results if finding.severity == "warn"
    ]
    remaining_warnings, _accepted = partition_accepted_findings(
        project_root,
        warnings,
        registry=registry,
    )
    remaining_warning_findings = [item.finding for item in remaining_warnings]
    kept: list[AuditFinding] = []
    for finding in results:
        if finding.severity != "warn":
            kept.append(finding)
        elif finding in remaining_warning_findings:
            kept.append(finding)
            remaining_warning_findings.remove(finding)
    return kept

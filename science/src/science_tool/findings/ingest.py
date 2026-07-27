"""Trusted ingestion: the write boundary (design §8).

An untrusted actor writes ONE gated report path. Ingestion validates it, computes
identities, and upserts canonical cases. `entity_kind_for_path` already returns
`None` for `doc/audits/cases/...` and the path gate already reads `None` as denied,
so "Layer 1 works unchanged" is literal -- nothing in `autonomy/policy.py` is edited.

This is NOT a multi-file transaction and does not claim to be. Full prevalidation,
then atomic per-record writes under a project-scoped lock. A crash after three
renames leaves three committed cases, which is acceptable ONLY because recovery is
idempotent: re-running the same report re-applies it, and every already-written
occurrence is a no-op by idempotency key. Retry is the documented recovery.
"""

from __future__ import annotations

import fcntl
import json
import os
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterator

from pydantic import BaseModel, ConfigDict, ValidationError
from science_model.audit import (
    REPORT_SCHEMA_VERSION,
    AuditFinding,
    AuditFindingRecord,
    AuditReport,
    Occurrence,
    RuleDeclarationError,
    Transition,
    finding_fingerprint,
    occurrence_key,
)
from science_model.audit.record import canonical_occurrence_content

from science_tool.findings.paths import (
    PathSafetyError,
    read_inside_bounded,
    resolve_inside,
)
from science_tool.findings.producers import FindingRegistry, RegistryError
from science_tool.findings.storage import (
    CaseStorageError,
    CaseStore,
    case_filename,
    case_store,
)

MAX_REPORT_BYTES = 8 * 1024 * 1024
SUPPORTED_FINGERPRINT_VERSIONS = frozenset({1})


class IngestError(ValueError):
    """A report was refused, or an occurrence conflicts with a stored one."""


class IngestOutcome(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    records_written: int
    occurrences_appended: int
    occurrences_skipped: int


def load_report(project_root: Path, path: Path) -> AuditReport:
    """Read the actor's one gated report path.

    Takes the project root because the report must LIVE inside it: §8 gives the actor
    exactly one supervisor-supplied report path, on a surface `report-only` already
    allows. `read_inside_bounded` therefore walks every component -- a link at any of
    them is refused, not merely one on the file itself -- and reads once from a single
    `O_NOFOLLOW` descriptor it also sized, so `stat()`-then-`read()` cannot race.
    """
    try:
        text = read_inside_bounded(project_root, path, MAX_REPORT_BYTES)
    except PathSafetyError as exc:
        raise IngestError(str(exc)) from exc
    except OSError as exc:
        raise IngestError(f"could not read {path}: {exc}") from exc
    try:
        raw = json.loads(text)
    except json.JSONDecodeError as exc:
        raise IngestError(f"could not parse {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise IngestError(f"{path} is not a JSON object")
    if raw.get("schema_version") != REPORT_SCHEMA_VERSION:
        raise IngestError(
            f"{path} declares schema_version {raw.get('schema_version')!r}; this "
            f"toolkit implements {REPORT_SCHEMA_VERSION} and refuses to coerce"
        )
    try:
        return AuditReport.model_validate(raw)
    except ValidationError as exc:
        raise IngestError(f"{path} is not a valid audit report: {exc}") from exc


@contextmanager
def _locked_store(project_root: Path) -> Iterator[CaseStore]:
    """Serialize ingestion per project and hand back the SAME anchored store.

    The lock and every case operation act through ONE directory descriptor. Taking the
    lock and then obtaining a store from a second walk would reintroduce exactly the
    check/use gap the descriptor exists to close -- the lock would be held on one
    directory while the writes went to whatever the pathname named by then.

    The lock file is opened without `O_TRUNC` and required to be a regular file. Its
    contents do not matter, which is why truncating it would be indefensible: if the
    name were a hard link to something real, `O_TRUNC` would empty that for no benefit.
    """
    try:
        with case_store(project_root, create=True) as store:
            descriptor = store.lock()
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX)
                try:
                    yield store
                finally:
                    fcntl.flock(descriptor, fcntl.LOCK_UN)
            finally:
                os.close(descriptor)
    except (CaseStorageError, PathSafetyError) as exc:
        raise IngestError(str(exc)) from exc


class _Planned(BaseModel):
    model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)

    finding_id: str
    finding: AuditFinding
    producer_id: str
    acceptance_key: str | None
    identity_qualifiers: dict[str, object]


def _plan(
    project_root: Path,
    report: AuditReport,
    registry: FindingRegistry,
) -> list[_Planned]:
    """Validate everything and compute every identity BEFORE writing anything."""
    if report.fingerprint_version not in SUPPORTED_FINGERPRINT_VERSIONS:
        raise IngestError(
            f"report declares fingerprint_version {report.fingerprint_version}; this "
            f"toolkit implements {sorted(SUPPORTED_FINGERPRINT_VERSIONS)}"
        )

    for producer_id, metrics in report.metrics.items():
        try:
            registry.validate_metrics(producer_id, metrics.model_dump())
        except RegistryError as exc:
            raise IngestError(str(exc)) from exc

    planned: list[_Planned] = []
    channels = [
        (r.producer_id, r.finding, None) for r in report.findings
    ] + [
        (a.producer_id, a.finding, a.acceptance_key) for a in report.accepted
    ]

    for producer_id, finding, acceptance_key in channels:
        if producer_id not in registry.producers_by_id:
            raise IngestError(f"unregistered producer {producer_id!r}")
        try:
            rule = registry.rule(finding.rule_id)
        except RegistryError as exc:
            raise IngestError(str(exc)) from exc
        if finding.severity not in rule.severities:
            raise IngestError(
                f"{finding.rule_id}: severity {finding.severity!r} is not in "
                f"{sorted(rule.severities)}"
            )
        if finding.subject.type not in rule.subject_types:
            raise IngestError(
                f"{finding.rule_id}: subject type {finding.subject.type!r} is not in "
                f"{sorted(rule.subject_types)}"
            )
        if finding.subject.type == "identifier" and rule.identifier_namespaces:
            if finding.subject.namespace not in rule.identifier_namespaces:
                raise IngestError(
                    f"{finding.rule_id}: namespace {finding.subject.namespace!r} is not "
                    f"in {sorted(rule.identifier_namespaces)}"
                )
        _assert_paths_are_safe(project_root, finding)

        try:
            # The SAME two routines `FindingRule.build()` runs, so a producer and the
            # write boundary cannot disagree about whether a finding is well typed or
            # about what its identity is. `validate_qualifiers` is strict: a report
            # carrying `"1"` where the schema declares `int` is refused rather than
            # coerced-then-discarded, so what is fingerprinted is what was declared.
            rule.validate_qualifiers(finding.qualifiers)
            identity = rule.identity_subset(finding.qualifiers)
        except RuleDeclarationError as exc:
            raise IngestError(str(exc)) from exc
        planned.append(
            _Planned(
                finding_id=finding_fingerprint(
                    rule_id=finding.rule_id,
                    subject=finding.subject,
                    identity_qualifiers=identity,
                ),
                finding=finding,
                producer_id=producer_id,
                acceptance_key=acceptance_key,
                identity_qualifiers=identity,
            )
        )

    # The at-most-one-per-(producer, finding_id) rule of §1, enforced HERE because it
    # needs the fingerprint, which needs the registry. `AuditReport` cannot do it:
    # keying on the whole payload would pass two observations with identical identity
    # and different prose, which is exactly the collision this rule prevents.
    seen: set[tuple[str, str]] = set()
    for item in planned:
        key = (item.producer_id, item.finding_id)
        if key in seen:
            raise IngestError(
                f"{item.producer_id!r} emitted two findings with identity "
                f"{item.finding_id}: aggregate their evidence into one finding, or "
                f"declare an identity qualifier on {item.finding.rule_id!r} that tells "
                "them apart (design §1)"
            )
        seen.add(key)
    return planned


def _assert_paths_are_safe(project_root: Path, finding: AuditFinding) -> None:
    """Every path the finding names must resolve inside the project without a link.

    The model normalizes path SYNTAX; only the filesystem can answer whether a
    component is a symlink, so the check lives here.
    """
    candidates: list[str] = []
    if finding.subject.type == "path":
        candidates.append(finding.subject.path)
    candidates.extend(
        item.path for item in finding.evidence if item.type == "location"
    )
    for candidate in candidates:
        try:
            resolve_inside(project_root, candidate)
        except PathSafetyError as exc:
            raise IngestError(f"{finding.rule_id}: {exc}") from exc


def ingest_report(
    project_root: Path,
    report: AuditReport,
    registry: FindingRegistry,
    *,
    actor: str = "ingest",
) -> IngestOutcome:
    planned = _plan(project_root, report, registry)
    observed_at = datetime.fromisoformat(report.generated_at)
    if observed_at.tzinfo is None:
        observed_at = observed_at.replace(tzinfo=UTC)

    written = appended = skipped = 0
    with _locked_store(project_root) as store:
        for item in planned:
            occurrence = Occurrence(
                idempotency_key=occurrence_key(
                    producer_id=item.producer_id,
                    ingestion_ref=report.ingestion_ref,
                    finding_id=item.finding_id,
                ),
                producer_id=item.producer_id,
                ingestion_ref=report.ingestion_ref,
                observed_at=observed_at,
                severity=item.finding.severity,
                message=item.finding.message,
                qualifiers=dict(item.finding.qualifiers),
                evidence=tuple(item.finding.evidence),
                acceptance_key=item.acceptance_key,
            )
            probe = AuditFindingRecord(
                finding_id=item.finding_id,
                fingerprint_version=report.fingerprint_version,
                rule_id=item.finding.rule_id,
                subject=item.finding.subject,
                identity_qualifiers=item.identity_qualifiers,
                occurrences=(occurrence,),
                transitions=(
                    Transition(
                        from_status=None,
                        to_status="proposed",
                        actor=actor,
                        at=observed_at,
                        reason=f"detected by {item.producer_id}",
                    ),
                ),
                status="proposed",
            )
            name = case_filename(probe)
            # `store.has` is an `lstat` through the held descriptor: a DANGLING link is
            # present under its own name, and treating it as absent would write
            # straight through it. `store.read` below refuses it explicitly instead.
            if not store.has(name):
                store.write(probe)
                written += 1
                appended += 1
                continue

            try:
                existing = store.read(name)
            except CaseStorageError as exc:
                raise IngestError(str(exc)) from exc

            stored = {o.idempotency_key: o for o in existing.occurrences}
            prior = stored.get(occurrence.idempotency_key)
            if prior is not None:
                if canonical_occurrence_content(
                    prior
                ) != canonical_occurrence_content(occurrence):
                    raise IngestError(
                        f"idempotency conflict on {item.finding_id}: key "
                        f"{occurrence.idempotency_key} already exists with different "
                        "observation content; identical keys must mean identical "
                        "observations"
                    )
                skipped += 1
                continue

            # `with_occurrence`, not `model_copy(update=...)`: the latter bypasses every
            # validator, so a malformed append would reach disk unchecked.
            store.write(existing.with_occurrence(occurrence))
            appended += 1

    return IngestOutcome(
        records_written=written,
        occurrences_appended=appended,
        occurrences_skipped=skipped,
    )

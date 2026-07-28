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

from pydantic import BaseModel, ConfigDict, ValidationError, field_validator
from pydantic_core import PydanticSerializationError
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
from science_model.audit.record import (
    canonical_occurrence_content,
    normalized_instant,
)

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
    serialize_case,
)

MAX_REPORT_BYTES = 8 * 1024 * 1024
MAX_REPORT_NESTING = 100
SUPPORTED_FINGERPRINT_VERSIONS = frozenset({1})


class IngestError(ValueError):
    """A report was refused, or an occurrence conflicts with a stored one."""


class IngestOutcome(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    records_written: int
    occurrences_appended: int
    occurrences_skipped: int


class IngestionProvenance(BaseModel):
    """Supervisor-attested report provenance, independent of actor-authored JSON."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    ingestion_ref: str
    generated_at: str
    producer_ids: frozenset[str]

    @field_validator("ingestion_ref")
    @classmethod
    def _valid_ingestion_ref(cls, value: str) -> str:
        if not value or "\0" in value:
            raise ValueError("ingestion_ref must be nonempty and NUL-free")
        return value

    @field_validator("generated_at")
    @classmethod
    def _valid_generated_at(cls, value: str) -> str:
        try:
            datetime.fromisoformat(value)
        except ValueError as exc:
            raise ValueError(
                f"generated_at must be ISO-8601, got {value!r}: {exc}"
            ) from exc
        return value

    @field_validator("producer_ids")
    @classmethod
    def _valid_producer_ids(cls, value: frozenset[str]) -> frozenset[str]:
        if not value:
            raise ValueError("producer_ids must contain at least one producer")
        invalid = sorted(item for item in value if not item.strip() or "\0" in item)
        if invalid:
            raise ValueError(f"producer ids must be nonblank and NUL-free: {invalid!r}")
        return value


class IngestionContext(BaseModel):
    """Frozen canonical entity universe supplied by the trusted graph loader."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    canonical_entity_ids: frozenset[str]

    @field_validator("canonical_entity_ids")
    @classmethod
    def _valid_entity_ids(cls, value: frozenset[str]) -> frozenset[str]:
        invalid = sorted(item for item in value if not item.strip() or "\0" in item)
        if invalid:
            raise ValueError(
                f"canonical entity ids must be nonblank and NUL-free: {invalid!r}"
            )
        return value


def _require_bounded_json_nesting(value: object, path: Path) -> None:
    stack: list[tuple[object, int]] = [(value, 0)]
    while stack:
        current, parent_depth = stack.pop()
        if isinstance(current, dict):
            children = current.values()
        elif isinstance(current, list):
            children = current
        else:
            continue

        depth = parent_depth + 1
        if depth > MAX_REPORT_NESTING:
            raise IngestError(
                f"could not parse {path}: excessive nesting exceeds "
                f"{MAX_REPORT_NESTING}"
            )
        stack.extend((child, depth) for child in children)


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
    except RecursionError as exc:
        raise IngestError(f"could not parse {path}: excessive nesting") from exc
    except ValueError as exc:
        # JSONDecodeError is a ValueError. The broader base also covers CPython's
        # bounded-integer refusal. Decoder nesting behavior varies by Python version;
        # the explicit post-decode check below enforces the portable boundary.
        raise IngestError(f"could not parse {path}: {exc}") from exc
    _require_bounded_json_nesting(raw, path)
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


def _snapshot_report(report: AuditReport) -> AuditReport:
    """Revalidate a detached JSON-shaped snapshot at the write boundary.

    `frozen=True` prevents attribute assignment, not mutation of nested lists, and
    `model_copy(update=...)` / `model_construct(...)` deliberately bypass validation.
    Calling `model_validate(report)` would also be insufficient because Pydantic may
    return the already-constructed instance. A JSON dump followed by strict validation
    both detaches mutable aliases and re-establishes every report invariant.
    """
    try:
        payload = report.model_dump(mode="json", warnings="error")
        snapshot = AuditReport.model_validate(payload, strict=True)
        canonical = json.dumps(
            snapshot.model_dump(mode="json", warnings="error"),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        if len(canonical) > MAX_REPORT_BYTES:
            raise IngestError(
                f"canonical report snapshot is {len(canonical)} bytes, which exceeds "
                f"{MAX_REPORT_BYTES}"
            )
        return snapshot
    except IngestError:
        raise
    except (
        PydanticSerializationError,
        ValidationError,
        ValueError,
        RecursionError,
    ) as exc:
        raise IngestError(f"report is not a valid audit report: {exc}") from exc


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
    provenance: IngestionProvenance,
    context: IngestionContext,
) -> list[_Planned]:
    """Validate everything and compute every identity BEFORE writing anything."""
    if report.fingerprint_version not in SUPPORTED_FINGERPRINT_VERSIONS:
        raise IngestError(
            f"report declares fingerprint_version {report.fingerprint_version}; this "
            f"toolkit implements {sorted(SUPPORTED_FINGERPRINT_VERSIONS)}"
        )

    trusted_producers = {producer_id: producer_id for producer_id in provenance.producer_ids}
    unknown_producers = set(trusted_producers) - set(registry.producers_by_id)
    if unknown_producers:
        raise IngestError(
            f"unregistered producer ids in report provenance: "
            f"{sorted(unknown_producers)}"
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
        if producer_id not in trusted_producers:
            raise IngestError(
                f"producer {producer_id!r} is not in the trusted provenance"
            )
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
        if finding.subject.type == "identifier":
            if finding.subject.namespace not in rule.identifier_namespaces:
                raise IngestError(
                    f"{finding.rule_id}: namespace {finding.subject.namespace!r} is not "
                    f"in {sorted(rule.identifier_namespaces)}"
                )
        if (
            finding.subject.type == "entity"
            and finding.subject.ref not in context.canonical_entity_ids
        ):
            raise IngestError(
                f"{finding.rule_id}: entity subject {finding.subject.ref!r} is not an "
                "exact member of the trusted canonical project entity universe"
            )
        _assert_paths_are_safe(project_root, finding)

        try:
            # The SAME two routines `FindingRule.build()` runs, so a producer and the
            # write boundary cannot disagree about whether a finding is well typed or
            # about what its identity is. `validate_qualifiers` is strict: a report
            # carrying `"1"` where the schema declares `int` is refused rather than
            # coerced-then-discarded, so what is fingerprinted is what was declared.
            canonical_qualifiers = rule.canonicalize_identity_qualifiers(
                finding.qualifiers
            )
            rule.validate_qualifiers(canonical_qualifiers)
            identity = rule.identity_subset(canonical_qualifiers)
        except RuleDeclarationError as exc:
            raise IngestError(str(exc)) from exc
        canonical_finding = AuditFinding(
            rule_id=finding.rule_id,
            subject=finding.subject,
            severity=finding.severity,
            qualifiers=canonical_qualifiers,
            message=finding.message,
            evidence=finding.evidence,
        )
        planned.append(
            _Planned(
                finding_id=finding_fingerprint(
                    rule_id=canonical_finding.rule_id,
                    subject=canonical_finding.subject,
                    identity_qualifiers=identity,
                ),
                finding=canonical_finding,
                producer_id=trusted_producers[producer_id],
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


def _assert_attested_provenance(
    report: AuditReport,
    provenance: IngestionProvenance,
) -> None:
    report_producer_ids = frozenset(
        {
            *report.meta.producers_run,
            *(item.producer_id for item in report.unwired),
        }
    )
    if report.ingestion_ref != provenance.ingestion_ref:
        raise IngestError(
            "report ingestion_ref does not exactly match the trusted attestation"
        )
    if report.generated_at != provenance.generated_at:
        raise IngestError(
            "report generated_at does not exactly match the trusted attestation"
        )
    if report_producer_ids != provenance.producer_ids:
        raise IngestError(
            "report producer ids do not exactly match the trusted attestation: "
            f"report={sorted(report_producer_ids)}, "
            f"trusted={sorted(provenance.producer_ids)}"
        )


def _new_record(
    item: _Planned,
    report: AuditReport,
    provenance: IngestionProvenance,
    observed_at: datetime,
    actor: str,
) -> AuditFindingRecord:
    occurrence = Occurrence(
        idempotency_key=occurrence_key(
            producer_id=item.producer_id,
            ingestion_ref=provenance.ingestion_ref,
            finding_id=item.finding_id,
        ),
        producer_id=item.producer_id,
        ingestion_ref=provenance.ingestion_ref,
        observed_at=observed_at,
        severity=item.finding.severity,
        message=item.finding.message,
        qualifiers=dict(item.finding.qualifiers),
        evidence=tuple(item.finding.evidence),
        acceptance_key=item.acceptance_key,
    )
    return AuditFindingRecord(
        finding_id=item.finding_id,
        fingerprint_version=report.fingerprint_version,
        rule_id=item.finding.rule_id,
        subject=item.finding.subject,
        identity_qualifiers=item.identity_qualifiers,
        occurrences=(occurrence,),
        transitions=(
            _genesis_transition(occurrence, actor),
        ),
        status="proposed",
    )


def _occurrence_order(occurrence: Occurrence) -> tuple[str, str]:
    return (
        normalized_instant(occurrence.observed_at),
        occurrence.idempotency_key,
    )


def _genesis_transition(occurrence: Occurrence, actor: str) -> Transition:
    return Transition(
        from_status=None,
        to_status="proposed",
        actor=actor,
        at=occurrence.observed_at,
        reason=f"detected by {occurrence.producer_id}",
    )


def _with_canonical_occurrences(
    template: AuditFindingRecord,
    occurrences: tuple[Occurrence, ...],
) -> AuditFindingRecord:
    ordered = tuple(sorted(occurrences, key=_occurrence_order))
    return AuditFindingRecord.model_validate(
        {
            **template.model_dump(mode="python"),
            "occurrences": ordered,
        }
    )


def _classify_writes(
    store: CaseStore,
    probes: list[AuditFindingRecord],
) -> tuple[list[AuditFindingRecord], int, int, int]:
    """Resolve every logical conflict before the first case write.

    The lock is already held. Stored reads and idempotency decisions happen for every
    target first; only the returned records may enter the I/O phase. Thus validation,
    malformed stored cases, and content conflicts are zero-write failures, while a
    later actual write failure may still leave earlier atomic records committed and is
    recovered by retry.
    """
    grouped: dict[str, list[AuditFindingRecord]] = {}
    for probe in probes:
        grouped.setdefault(case_filename(probe), []).append(probe)

    existing_by_name = {name: store.read(name) for name in store.names()}
    writes: list[AuditFindingRecord] = []
    written = appended = skipped = 0
    for name in sorted(grouped):
        incoming_probes = grouped[name]
        incoming = tuple(probe.occurrences[0] for probe in incoming_probes)
        existing = existing_by_name.get(name)

        if existing is None:
            writes.append(
                _with_canonical_occurrences(incoming_probes[0], incoming)
            )
            written += 1
            appended += len(incoming)
            continue

        stored = {
            occurrence.idempotency_key: occurrence
            for occurrence in existing.occurrences
        }
        additions: list[Occurrence] = []
        for occurrence in incoming:
            prior = stored.get(occurrence.idempotency_key)
            if prior is None:
                additions.append(occurrence)
                continue
            if canonical_occurrence_content(prior) != canonical_occurrence_content(
                occurrence
            ):
                raise IngestError(
                    f"idempotency conflict on {existing.finding_id}: key "
                    f"{occurrence.idempotency_key} already exists with different "
                    "observation content; identical keys must mean identical "
                    "observations"
                )
            skipped += 1

        if additions:
            writes.append(
                _with_canonical_occurrences(
                    existing,
                    (*existing.occurrences, *additions),
                )
            )
            appended += len(additions)

    return writes, written, appended, skipped


def ingest_report(
    project_root: Path,
    report: AuditReport,
    registry: FindingRegistry,
    *,
    provenance: IngestionProvenance,
    context: IngestionContext,
    actor: str = "ingest",
) -> IngestOutcome:
    report = _snapshot_report(report)
    _assert_attested_provenance(report, provenance)
    if not actor.strip() or "\0" in actor:
        raise IngestError("ingestion actor must be nonblank and NUL-free")
    planned = _plan(project_root, report, registry, provenance, context)
    observed_at = datetime.fromisoformat(provenance.generated_at)
    if observed_at.tzinfo is None:
        observed_at = observed_at.replace(tzinfo=UTC)

    probes = [
        _new_record(item, report, provenance, observed_at, actor) for item in planned
    ]
    with _locked_store(project_root) as store:
        writes, written, appended, skipped = _classify_writes(
            store,
            probes,
        )
        for record in writes:
            serialize_case(record)
        for record in writes:
            store.write(record)

    return IngestOutcome(
        records_written=written,
        occurrences_appended=appended,
        occurrences_skipped=skipped,
    )

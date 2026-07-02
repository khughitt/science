from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from science_tool.annotation.proposition_reconciliation import (
    LANE_FACTORIZATION,
    LANE_SAME_CLAIM,
    ReconciliationReport,
    candidate_indexes,
    judgment_id,
    members_have_current_edge,
    resolve_same_claim_candidate,
)


SCHEMA_VERSION = 1
DEFAULT_DECISION_LOG = "results/proposition-reconciliation/decisions.jsonl"

DecisionLane = Literal["same_claim", "factorization_disagreement"]

_ACTION_KIND = "record_reconciliation_decision"
_LANE_A_DECISIONS = frozenset({"related_but_distinct", "conflict_or_negation"})
_LANE_B_DECISIONS = frozenset({"split_possible"})


class DecisionRecordError(ValueError):
    pass


@dataclass(frozen=True)
class DecisionRecord:
    schema_version: int
    decision_id: str
    judgment_id: str
    candidate_id: str
    lane: DecisionLane
    decision: str
    members: tuple[str, ...]
    proposition: str | None
    confidence: str
    rationale: str
    source_review: str
    review_source: str
    recorded_at: str


@dataclass(frozen=True)
class EvaluatedDecision:
    record: DecisionRecord
    current_candidate_id: str
    suppresses_candidate: bool


@dataclass(frozen=True)
class StaleDecision:
    record: DecisionRecord
    reason: str


@dataclass(frozen=True)
class ConflictingDecision:
    scope: tuple[str, tuple[str, ...]]
    decision_ids: tuple[str, ...]
    decisions: tuple[str, ...]


@dataclass(frozen=True)
class DecisionEvaluation:
    active: tuple[EvaluatedDecision, ...]
    stale: tuple[StaleDecision, ...]
    duplicates: tuple[str, ...]
    conflicts: tuple[ConflictingDecision, ...]
    suppressed_same_claim_candidate_ids: frozenset[str]
    suppressed_factorization_candidate_ids: frozenset[str]


@dataclass(frozen=True)
class AppendDecisionResult:
    appended: tuple[str, ...]
    already_recorded: tuple[str, ...]


def decision_record_id(
    lane: str,
    decision: str,
    judgment_ref: str,
    primary_ref: str,
    refs: Sequence[str] = (),
) -> str:
    digest = hashlib.sha256(
        "\0".join([lane, decision, judgment_ref, primary_ref, *sorted(refs)]).encode()
    ).hexdigest()
    return f"reconcile-decision:{digest}"


def decision_record_to_json(record: DecisionRecord) -> dict[str, Any]:
    _validate_record_shape(record)
    return {
        "schema_version": record.schema_version,
        "decision_id": record.decision_id,
        "judgment_id": record.judgment_id,
        "candidate_id": record.candidate_id,
        "lane": record.lane,
        "decision": record.decision,
        "members": list(record.members),
        "proposition": record.proposition,
        "confidence": record.confidence,
        "rationale": record.rationale,
        "source_review": record.source_review,
        "review_source": record.review_source,
        "recorded_at": record.recorded_at,
    }


def decision_record_from_json(
    payload: Mapping[str, Any],
    *,
    line_no: int | None = None,
) -> DecisionRecord:
    prefix = f"line {line_no}: " if line_no is not None else ""
    if not isinstance(payload, Mapping):
        raise DecisionRecordError(f"{prefix}decision record must be an object")

    lane_text = _required_json_text(payload, "lane", prefix)
    if lane_text == LANE_SAME_CLAIM:
        lane: DecisionLane = LANE_SAME_CLAIM
    elif lane_text == LANE_FACTORIZATION:
        lane = LANE_FACTORIZATION
    else:
        raise DecisionRecordError(f"{prefix}unsupported lane: {lane_text!r}")

    members = _json_members(payload.get("members"), prefix)
    proposition_value = payload.get("proposition")
    if proposition_value is not None and not isinstance(proposition_value, str):
        raise DecisionRecordError(f"{prefix}proposition must be a string or null")

    record = DecisionRecord(
        schema_version=_required_int(payload.get("schema_version"), "schema_version", prefix),
        decision_id=_required_json_text(payload, "decision_id", prefix),
        judgment_id=_required_json_text(payload, "judgment_id", prefix),
        candidate_id=_required_json_text(payload, "candidate_id", prefix),
        lane=lane,
        decision=_required_json_text(payload, "decision", prefix),
        members=members,
        proposition=proposition_value.strip() if isinstance(proposition_value, str) else None,
        confidence=_required_json_text(payload, "confidence", prefix),
        rationale=_required_json_text(payload, "rationale", prefix),
        source_review=_required_json_text(payload, "source_review", prefix),
        review_source=_required_json_text(payload, "review_source", prefix),
        recorded_at=_required_json_text(payload, "recorded_at", prefix),
    )
    try:
        _validate_record_shape(record)
    except DecisionRecordError as exc:
        raise DecisionRecordError(f"{prefix}{exc}") from exc
    return record


def load_decision_records(path: Path) -> tuple[DecisionRecord, ...]:
    if not path.exists():
        return ()

    parsed: list[tuple[int, Any]] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            parsed.append((line_no, json.loads(line)))
        except json.JSONDecodeError as exc:
            raise DecisionRecordError(f"line {line_no}: malformed JSON") from exc
    return tuple(
        decision_record_from_json(payload, line_no=line_no)
        for line_no, payload in parsed
    )


def append_decision_records(
    path: Path,
    records: Sequence[DecisionRecord],
) -> AppendDecisionResult:
    existing_ids = {record.decision_id for record in load_decision_records(path)}
    appended: list[str] = []
    already_recorded: list[str] = []
    pending: list[DecisionRecord] = []

    for record in sorted(records, key=lambda item: item.decision_id):
        _validate_record_shape(record)
        if record.decision_id in existing_ids:
            already_recorded.append(record.decision_id)
            continue
        existing_ids.add(record.decision_id)
        appended.append(record.decision_id)
        pending.append(record)

    if pending:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            for record in pending:
                payload = decision_record_to_json(record)
                handle.write(json.dumps(payload, sort_keys=True))
                handle.write("\n")

    return AppendDecisionResult(tuple(appended), tuple(already_recorded))


def evaluate_decision_records(
    records: Sequence[DecisionRecord],
    report: ReconciliationReport,
) -> DecisionEvaluation:
    same_by_id, factor_by_id = candidate_indexes(report)
    seen: set[str] = set()
    current: list[EvaluatedDecision] = []
    stale: list[StaleDecision] = []
    duplicates: list[str] = []

    for record in records:
        _validate_record_shape(record)
        if record.decision_id in seen:
            duplicates.append(record.decision_id)
            continue
        seen.add(record.decision_id)

        if record.lane == LANE_SAME_CLAIM:
            members = set(record.members)
            candidate = resolve_same_claim_candidate(
                record.candidate_id,
                members,
                same_by_id,
                report.same_claim_candidates,
            )
            if candidate is None:
                stale.append(StaleDecision(record, "candidate-missing"))
                continue
            if not members_have_current_edge(candidate, members):
                stale.append(StaleDecision(record, "members-no-longer-edge-connected"))
                continue
            current.append(
                EvaluatedDecision(
                    record,
                    candidate.candidate_id,
                    set(candidate.propositions) == members,
                )
            )
            continue

        factor = factor_by_id.get(record.candidate_id)
        if factor is None or factor.proposition != record.proposition:
            stale.append(StaleDecision(record, "candidate-missing"))
            continue
        current.append(EvaluatedDecision(record, factor.candidate_id, True))

    conflicts = _decision_conflicts(current)
    conflicted_scopes = {conflict.scope for conflict in conflicts}
    active = tuple(
        item for item in current if _decision_scope(item.record) not in conflicted_scopes
    )
    return DecisionEvaluation(
        active=active,
        stale=tuple(stale),
        duplicates=tuple(sorted(duplicates)),
        conflicts=conflicts,
        suppressed_same_claim_candidate_ids=frozenset(
            item.current_candidate_id
            for item in active
            if item.record.lane == LANE_SAME_CLAIM and item.suppresses_candidate
        ),
        suppressed_factorization_candidate_ids=frozenset(
            item.current_candidate_id
            for item in active
            if item.record.lane == LANE_FACTORIZATION and item.suppresses_candidate
        ),
    )


def record_from_action_payload(
    action: Mapping[str, Any],
    *,
    recorded_at: str,
) -> DecisionRecord:
    if action.get("kind") != _ACTION_KIND:
        raise DecisionRecordError(f"action kind must be {_ACTION_KIND!r}")
    if action.get("status") != "advisory":
        raise DecisionRecordError("action status must be 'advisory'")
    if action.get("blockers"):
        raise DecisionRecordError("advisory action must not have blockers")

    recorded = _required_str(recorded_at, "recorded_at")
    decision = _required_text(action, "decision")
    candidate_id = _required_text(action, "candidate_id")
    judgment_ref = _required_text(action, "judgment_id")

    if decision in _LANE_A_DECISIONS:
        lane: DecisionLane = LANE_SAME_CLAIM
        members = _members(action)
        proposition = None
        expected_judgment = judgment_id(lane, decision, members)
        record_refs = members
    elif decision in _LANE_B_DECISIONS:
        lane = LANE_FACTORIZATION
        members = ()
        proposition = _required_text(action, "proposition")
        expected_judgment = judgment_id(lane, decision, [proposition])
        record_refs = (proposition,)
    else:
        raise DecisionRecordError(f"unsupported reconciliation decision: {decision!r}")

    if judgment_ref != expected_judgment:
        raise DecisionRecordError("action judgment_id does not match decision inputs")

    return DecisionRecord(
        schema_version=SCHEMA_VERSION,
        decision_id=decision_record_id(
            lane,
            decision,
            judgment_ref,
            candidate_id,
            record_refs,
        ),
        judgment_id=judgment_ref,
        candidate_id=candidate_id,
        lane=lane,
        decision=decision,
        members=members,
        proposition=proposition,
        confidence=_required_text(action, "confidence"),
        rationale=_required_text(action, "rationale"),
        source_review=_required_text(action, "source_review"),
        review_source=_required_text(action, "review_source"),
        recorded_at=recorded,
    )


def _validate_record_shape(record: DecisionRecord) -> None:
    if record.schema_version != SCHEMA_VERSION:
        raise DecisionRecordError(f"schema_version must be {SCHEMA_VERSION}")
    for field_name in (
        "decision_id",
        "judgment_id",
        "candidate_id",
        "decision",
        "confidence",
        "rationale",
        "source_review",
        "review_source",
        "recorded_at",
    ):
        _required_str(getattr(record, field_name), field_name)
    if not all(isinstance(member, str) and member.strip() for member in record.members):
        raise DecisionRecordError("members must be non-empty strings")
    if tuple(sorted(set(record.members))) != record.members:
        raise DecisionRecordError("members must be sorted and unique")
    if record.proposition is not None:
        _required_str(record.proposition, "proposition")

    if record.lane == LANE_SAME_CLAIM:
        if record.decision not in _LANE_A_DECISIONS:
            raise DecisionRecordError("same_claim decision is not supported")
        if not record.members:
            raise DecisionRecordError("same_claim record must have members")
        if record.proposition is not None:
            raise DecisionRecordError("same_claim record must not have proposition")
        refs: Sequence[str] = record.members
    elif record.lane == LANE_FACTORIZATION:
        if record.decision not in _LANE_B_DECISIONS:
            raise DecisionRecordError("factorization decision is not supported")
        if record.members:
            raise DecisionRecordError("factorization record must not have members")
        if record.proposition is None:
            raise DecisionRecordError("factorization record must have proposition")
        refs = (record.proposition,)
    else:
        raise DecisionRecordError(f"unsupported lane: {record.lane!r}")

    expected_judgment = judgment_id(record.lane, record.decision, refs)
    if record.judgment_id != expected_judgment:
        raise DecisionRecordError("judgment_id does not match decision inputs")
    expected_decision = decision_record_id(
        record.lane,
        record.decision,
        record.judgment_id,
        record.candidate_id,
        refs,
    )
    if record.decision_id != expected_decision:
        raise DecisionRecordError("decision_id does not match decision inputs")


def _decision_scope(record: DecisionRecord) -> tuple[str, tuple[str, ...]]:
    if record.lane == LANE_SAME_CLAIM:
        return (record.lane, record.members)
    if record.proposition is None:
        raise DecisionRecordError("factorization record must have proposition")
    return (record.lane, (record.proposition,))


def _decision_conflicts(
    records: Sequence[EvaluatedDecision],
) -> tuple[ConflictingDecision, ...]:
    by_scope: dict[tuple[str, tuple[str, ...]], list[DecisionRecord]] = {}
    for item in records:
        by_scope.setdefault(_decision_scope(item.record), []).append(item.record)

    conflicts: list[ConflictingDecision] = []
    for scope, scoped_records in by_scope.items():
        decisions = tuple(sorted({record.decision for record in scoped_records}))
        if len(decisions) < 2:
            continue
        conflicts.append(
            ConflictingDecision(
                scope=scope,
                decision_ids=tuple(sorted(record.decision_id for record in scoped_records)),
                decisions=decisions,
            )
        )
    return tuple(conflicts)


def _required_text(action: Mapping[str, Any], field_name: str) -> str:
    return _required_str(action.get(field_name), field_name)


def _required_json_text(
    payload: Mapping[str, Any],
    field_name: str,
    prefix: str,
) -> str:
    try:
        value = payload[field_name]
    except KeyError as exc:
        raise DecisionRecordError(f"{prefix}{field_name} is required") from exc
    try:
        return _required_str(value, field_name)
    except DecisionRecordError as exc:
        raise DecisionRecordError(f"{prefix}{exc}") from exc


def _required_int(value: Any, field_name: str, prefix: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise DecisionRecordError(f"{prefix}{field_name} must be an integer")
    return value


def _required_str(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DecisionRecordError(f"{field_name} must be a non-empty string")
    return value.strip()


def _json_members(value: Any, prefix: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, Sequence) or isinstance(value, str):
        raise DecisionRecordError(f"{prefix}members must be a sequence of strings")
    if not all(isinstance(member, str) and member.strip() for member in value):
        raise DecisionRecordError(f"{prefix}members must be non-empty strings")
    return tuple(member.strip() for member in value)


def _members(action: Mapping[str, Any]) -> tuple[str, ...]:
    members = action.get("members")
    if not isinstance(members, Sequence) or isinstance(members, str):
        raise DecisionRecordError("members must be a sequence of strings")
    if not all(isinstance(member, str) and member.strip() for member in members):
        raise DecisionRecordError("members must be non-empty strings")
    refs = tuple(sorted({member.strip() for member in members}))
    if not refs:
        raise DecisionRecordError("members must not be empty")
    return refs

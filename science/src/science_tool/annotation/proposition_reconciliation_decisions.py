from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from science_tool.annotation.proposition_reconciliation import (
    DECISION_ACCEPTED_SPARSE_HINTS,
    LANE_FACTORIZATION,
    LANE_SAME_CLAIM,
    ReconciliationReport,
    SameClaimCandidate,
    candidate_id,
    candidate_indexes,
    factorization_assertion_fingerprint,
    judgment_id,
    members_have_current_edge,
    resolve_same_claim_candidate,
)


SCHEMA_VERSION = 1
DEFAULT_DECISION_LOG = "results/proposition-reconciliation/decisions.jsonl"

DecisionLane = Literal["same_claim", "factorization_disagreement"]

_ACTION_KIND = "record_reconciliation_decision"
_LANE_A_DECISIONS = frozenset({"related_but_distinct", "conflict_or_negation"})
_LANE_B_DECISIONS = frozenset({"split_possible", DECISION_ACCEPTED_SPARSE_HINTS})


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
    assertion_fingerprint: str | None
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


@dataclass(frozen=True)
class RecordDecisionPlan:
    would_append: tuple[DecisionRecord, ...]
    already_recorded: tuple[str, ...]
    stale_existing: tuple[StaleDecision, ...]
    blockers: tuple[Mapping[str, Any], ...]


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
    payload: dict[str, Any] = {
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
    if record.assertion_fingerprint is not None:
        payload["assertion_fingerprint"] = record.assertion_fingerprint
    return payload


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
    assertion_fingerprint: str | None = None
    if "assertion_fingerprint" in payload:
        assertion_fingerprint = _required_assertion_fingerprint(
            payload["assertion_fingerprint"],
            prefix,
        )

    record = DecisionRecord(
        schema_version=_required_schema_version(payload.get("schema_version"), prefix),
        decision_id=_required_json_text(payload, "decision_id", prefix),
        judgment_id=_required_json_text(payload, "judgment_id", prefix),
        candidate_id=_required_json_text(payload, "candidate_id", prefix),
        lane=lane,
        decision=_required_json_text(payload, "decision", prefix),
        members=members,
        proposition=proposition_value.strip() if isinstance(proposition_value, str) else None,
        assertion_fingerprint=assertion_fingerprint,
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


def build_record_decision_plan(
    action_plan: Mapping[str, Any],
    existing_records: Sequence[DecisionRecord],
    report: ReconciliationReport,
    recorded_at: str,
) -> RecordDecisionPlan:
    _required_schema_version(action_plan.get("schema_version"), "")
    if action_plan.get("errors"):
        raise DecisionRecordError("action plan contains errors")
    actions = action_plan.get("actions")
    if not isinstance(actions, list):
        raise DecisionRecordError("actions must be a list")

    existing_evaluation = evaluate_decision_records(existing_records, report)
    planned_ids = {record.decision_id for record in existing_records}
    blockers: list[Mapping[str, Any]] = []
    new_records: list[DecisionRecord] = []
    new_record_actions: dict[str, Mapping[str, Any]] = {}
    already_recorded: list[str] = []

    for action in actions:
        if not isinstance(action, Mapping):
            blockers.append({"reason": "malformed-action", "detail": "action must be an object"})
            continue
        if action.get("kind") != _ACTION_KIND:
            continue
        try:
            record = record_from_action_payload(action, recorded_at=recorded_at)
        except DecisionRecordError as exc:
            blockers.append(_action_blocker(action, _action_error_reason(exc), str(exc)))
            continue

        evaluation = evaluate_decision_records([record], report)
        if evaluation.stale:
            stale = evaluation.stale[0]
            blockers.append(_record_blocker(record, action, stale.reason, stale.reason))
            continue
        if record.decision_id in planned_ids:
            already_recorded.append(record.decision_id)
            continue
        planned_ids.add(record.decision_id)
        new_records.append(record)
        new_record_actions[record.decision_id] = action

    conflicted_new_ids = _conflicting_new_decision_ids(
        existing_records,
        new_records,
        report,
    )
    for record in new_records:
        if record.decision_id in conflicted_new_ids:
            blockers.append(
                _record_blocker(
                    record,
                    new_record_actions[record.decision_id],
                    "conflicting-reviewed-decisions",
                    "conflicts with another current reviewed decision",
                )
            )

    would_append = tuple(
        sorted(
            (
                record
                for record in new_records
                if record.decision_id not in conflicted_new_ids
            ),
            key=lambda item: item.decision_id,
        )
    )
    return RecordDecisionPlan(
        would_append=would_append,
        already_recorded=tuple(sorted(set(already_recorded))),
        stale_existing=existing_evaluation.stale,
        blockers=tuple(blockers),
    )


def record_decision_plan_to_json(
    plan: RecordDecisionPlan,
    *,
    appended: Sequence[str] = (),
) -> dict[str, Any]:
    return {
        "summary": {
            "would_append": len(plan.would_append),
            "already_recorded": len(plan.already_recorded),
            "stale_existing": len(plan.stale_existing),
            "blockers": len(plan.blockers),
            "appended": len(appended),
        },
        "would_append": [decision_record_to_json(record) for record in plan.would_append],
        "already_recorded": list(plan.already_recorded),
        "stale_existing": [
            {
                "reason": stale.reason,
                "record": decision_record_to_json(stale.record),
            }
            for stale in plan.stale_existing
        ],
        "blockers": [_jsonable(blocker) for blocker in plan.blockers],
        "appended": list(appended),
    }


def reviewed_decisions_to_json(evaluation: DecisionEvaluation) -> dict[str, Any]:
    return {
        "active": [
            {
                "decision_id": item.record.decision_id,
                "candidate_id": item.current_candidate_id,
                "lane": item.record.lane,
                "decision": item.record.decision,
                "members": list(item.record.members),
                "proposition": item.record.proposition,
                "suppresses_candidate": item.suppresses_candidate,
            }
            for item in evaluation.active
        ],
        "stale": [
            {
                "decision_id": item.record.decision_id,
                "reason": item.reason,
            }
            for item in evaluation.stale
        ],
        "duplicates": list(evaluation.duplicates),
        "conflicts": [
            {
                "scope": {
                    "lane": conflict.scope[0],
                    "refs": list(conflict.scope[1]),
                },
                "decision_ids": list(conflict.decision_ids),
                "decisions": list(conflict.decisions),
            }
            for conflict in evaluation.conflicts
        ],
    }


def apply_reviewed_decisions_to_report_payload(
    payload: Mapping[str, Any],
    evaluation: DecisionEvaluation,
    *,
    show_reviewed: bool,
) -> dict[str, Any]:
    summary = dict(payload["summary"])
    same_claim_candidates = [dict(item) for item in payload["same_claim_candidates"]]
    factorization_disagreements = [
        dict(item) for item in payload["factorization_disagreements"]
    ]

    summary["generated_same_claim_candidates"] = len(same_claim_candidates)
    summary["generated_factorization_disagreements"] = len(factorization_disagreements)
    summary["reviewed_decisions"] = len(evaluation.active)
    summary["stale_reviewed_decisions"] = len(evaluation.stale)
    summary["duplicate_reviewed_decisions"] = len(evaluation.duplicates)
    summary["conflicting_reviewed_decisions"] = len(evaluation.conflicts)

    reviewed_by_candidate_id = {
        item.current_candidate_id: item.record.decision_id for item in evaluation.active
    }

    filtered_same_claim_candidates = _filter_report_candidates(
        same_claim_candidates,
        suppressed_candidate_ids=evaluation.suppressed_same_claim_candidate_ids,
        reviewed_by_candidate_id=reviewed_by_candidate_id,
        show_reviewed=show_reviewed,
    )
    filtered_factorization_disagreements = _filter_report_candidates(
        factorization_disagreements,
        suppressed_candidate_ids=evaluation.suppressed_factorization_candidate_ids,
        reviewed_by_candidate_id=reviewed_by_candidate_id,
        show_reviewed=show_reviewed,
    )

    summary["same_claim_candidates"] = len(filtered_same_claim_candidates)
    summary["factorization_disagreements"] = len(filtered_factorization_disagreements)

    output = dict(payload)
    output["summary"] = summary
    output["same_claim_candidates"] = filtered_same_claim_candidates
    output["factorization_disagreements"] = filtered_factorization_disagreements
    output["reviewed_decisions"] = reviewed_decisions_to_json(evaluation)
    return output


def project_decision_evaluation_to_report(
    evaluation: DecisionEvaluation,
    report: ReconciliationReport,
) -> DecisionEvaluation:
    scoped_same_by_id, scoped_factor_by_id = candidate_indexes(report)
    scoped_factor_candidate_ids = frozenset(scoped_factor_by_id)
    scoped_snapshot_refs = frozenset(report.proposition_snapshots)
    scoped_same_claim_refs = scoped_snapshot_refs | frozenset(
        ref
        for candidate in report.same_claim_candidates
        for ref in candidate.propositions
    )
    scoped_factorization_refs = scoped_snapshot_refs | frozenset(
        candidate.proposition for candidate in report.factorization_disagreements
    )

    active: list[EvaluatedDecision] = []
    for item in evaluation.active:
        if item.record.lane == LANE_SAME_CLAIM:
            members = set(item.record.members)
            candidate = _resolve_scoped_same_claim_candidate(
                item.record.candidate_id,
                members,
                scoped_same_by_id,
                report.same_claim_candidates,
            )
            if candidate is None or not members_have_current_edge(candidate, members):
                continue
            active.append(
                EvaluatedDecision(
                    item.record,
                    candidate.candidate_id,
                    set(candidate.propositions) == members,
                )
            )
            continue

        if item.current_candidate_id in scoped_factor_candidate_ids:
            active.append(item)

    conflicts = tuple(
        conflict
        for conflict in evaluation.conflicts
        if _conflict_intersects_report(
            conflict,
            scoped_same_claim_refs=scoped_same_claim_refs,
            scoped_factorization_refs=scoped_factorization_refs,
        )
    )
    stale = tuple(
        item
        for item in evaluation.stale
        if _stale_decision_intersects_report(item, scoped_snapshot_refs)
    )
    scoped_decision_ids = frozenset(
        item.record.decision_id for item in active
    ) | frozenset(item.record.decision_id for item in stale) | frozenset(
        decision_id
        for conflict in conflicts
        for decision_id in conflict.decision_ids
    )
    return DecisionEvaluation(
        active=tuple(active),
        stale=stale,
        duplicates=tuple(
            decision_id
            for decision_id in evaluation.duplicates
            if decision_id in scoped_decision_ids
        ),
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


def _resolve_scoped_same_claim_candidate(
    candidate_ref: str,
    members: set[str],
    same_by_id: Mapping[str, SameClaimCandidate],
    all_same: tuple[SameClaimCandidate, ...],
) -> SameClaimCandidate | None:
    candidate = resolve_same_claim_candidate(candidate_ref, members, same_by_id, all_same)
    if candidate is not None:
        return candidate

    subset_candidate = same_by_id.get(candidate_id(LANE_SAME_CLAIM, sorted(members)))
    if subset_candidate is not None:
        return subset_candidate

    matches = [
        candidate
        for candidate in all_same
        if set(candidate.propositions) == members
        and members_have_current_edge(candidate, members)
    ]
    if len(matches) == 1:
        return matches[0]
    return None


def _conflict_intersects_report(
    conflict: ConflictingDecision,
    *,
    scoped_same_claim_refs: frozenset[str],
    scoped_factorization_refs: frozenset[str],
) -> bool:
    lane, refs = conflict.scope
    if lane == LANE_SAME_CLAIM:
        return bool(set(refs) & scoped_same_claim_refs)
    if lane == LANE_FACTORIZATION:
        return bool(set(refs) & scoped_factorization_refs)
    return False


def _stale_decision_intersects_report(
    stale: StaleDecision,
    scoped_snapshot_refs: frozenset[str],
) -> bool:
    if stale.record.lane == LANE_SAME_CLAIM:
        return bool(set(stale.record.members) & scoped_snapshot_refs)
    if stale.record.lane == LANE_FACTORIZATION:
        return stale.record.proposition in scoped_snapshot_refs
    return False


def _filter_report_candidates(
    candidates: Sequence[Mapping[str, Any]],
    *,
    suppressed_candidate_ids: frozenset[str],
    reviewed_by_candidate_id: Mapping[str, str],
    show_reviewed: bool,
) -> list[dict[str, Any]]:
    filtered: list[dict[str, Any]] = []
    for candidate in candidates:
        candidate_id_value = candidate["candidate_id"]
        if candidate_id_value in suppressed_candidate_ids and not show_reviewed:
            continue
        item = dict(candidate)
        reviewed_decision_id = reviewed_by_candidate_id.get(candidate_id_value)
        if reviewed_decision_id is not None:
            item["reviewed_decision_id"] = reviewed_decision_id
        filtered.append(item)
    return filtered


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
        if record.decision == DECISION_ACCEPTED_SPARSE_HINTS:
            if factor.recommended_action != "insufficient_hints":
                stale.append(StaleDecision(record, "candidate-no-longer-sparse-hints"))
                continue
            if record.assertion_fingerprint != factorization_assertion_fingerprint(factor):
                stale.append(StaleDecision(record, "assertion-fingerprint-changed"))
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


def _action_error_reason(exc: DecisionRecordError) -> str:
    if str(exc).startswith("candidate_id "):
        return "candidate-missing"
    return "malformed-action"


def _action_blocker(
    action: Mapping[str, Any],
    reason: str,
    detail: str,
) -> Mapping[str, Any]:
    blocker: dict[str, Any] = {"reason": reason, "detail": detail}
    action_id = action.get("action_id")
    if isinstance(action_id, str) and action_id.strip():
        blocker["action_id"] = action_id.strip()
    return blocker


def _record_blocker(
    record: DecisionRecord,
    action: Mapping[str, Any] | None,
    reason: str,
    detail: str,
) -> Mapping[str, Any]:
    blocker: dict[str, Any] = {
        "reason": reason,
        "detail": detail,
        "decision_id": record.decision_id,
    }
    if action is not None:
        action_id = action.get("action_id")
        if isinstance(action_id, str) and action_id.strip():
            blocker["action_id"] = action_id.strip()
    return blocker


def _conflicting_new_decision_ids(
    existing_records: Sequence[DecisionRecord],
    new_records: Sequence[DecisionRecord],
    report: ReconciliationReport,
) -> frozenset[str]:
    if not new_records:
        return frozenset()
    new_ids = {record.decision_id for record in new_records}
    evaluation = evaluate_decision_records([*existing_records, *new_records], report)
    conflicted: set[str] = set()
    for conflict in evaluation.conflicts:
        conflicted.update(decision_id for decision_id in conflict.decision_ids if decision_id in new_ids)
    return frozenset(conflicted)


def _jsonable(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [_jsonable(item) for item in value]
    return value


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
    assertion_fingerprint: str | None = None

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
        if decision == DECISION_ACCEPTED_SPARSE_HINTS:
            inputs = action.get("inputs")
            if not isinstance(inputs, Mapping):
                raise DecisionRecordError("inputs must be an object")
            assertion_fingerprint = _required_assertion_fingerprint(
                inputs.get("assertion_fingerprint"),
            )
            record_refs = (proposition, assertion_fingerprint)
        else:
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
        assertion_fingerprint=assertion_fingerprint,
        confidence=_required_text(action, "confidence"),
        rationale=_required_text(action, "rationale"),
        source_review=_required_text(action, "source_review"),
        review_source=_required_text(action, "review_source"),
        recorded_at=recorded,
    )


def _validate_record_shape(record: DecisionRecord) -> None:
    _required_schema_version(record.schema_version, "")
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
    if record.assertion_fingerprint is not None:
        _validate_assertion_fingerprint(record.assertion_fingerprint)

    if record.lane == LANE_SAME_CLAIM:
        if record.decision not in _LANE_A_DECISIONS:
            raise DecisionRecordError("same_claim decision is not supported")
        if not record.members:
            raise DecisionRecordError("same_claim record must have members")
        if record.proposition is not None:
            raise DecisionRecordError("same_claim record must not have proposition")
        if record.assertion_fingerprint is not None:
            raise DecisionRecordError("same_claim record must not have assertion_fingerprint")
        judgment_refs: Sequence[str] = record.members
        decision_refs: Sequence[str] = record.members
    elif record.lane == LANE_FACTORIZATION:
        if record.decision not in _LANE_B_DECISIONS:
            raise DecisionRecordError("factorization decision is not supported")
        if record.members:
            raise DecisionRecordError("factorization record must not have members")
        if record.proposition is None:
            raise DecisionRecordError("factorization record must have proposition")
        judgment_refs = (record.proposition,)
        if record.decision == DECISION_ACCEPTED_SPARSE_HINTS:
            if record.assertion_fingerprint is None:
                raise DecisionRecordError(
                    "accepted_sparse_hints record must have assertion_fingerprint"
                )
            decision_refs = (record.proposition, record.assertion_fingerprint)
        else:
            if record.assertion_fingerprint is not None:
                raise DecisionRecordError(
                    "factorization record must not have assertion_fingerprint"
                )
            decision_refs = (record.proposition,)
    else:
        raise DecisionRecordError(f"unsupported lane: {record.lane!r}")

    expected_judgment = judgment_id(record.lane, record.decision, judgment_refs)
    if record.judgment_id != expected_judgment:
        raise DecisionRecordError("judgment_id does not match decision inputs")
    expected_decision = decision_record_id(
        record.lane,
        record.decision,
        record.judgment_id,
        record.candidate_id,
        decision_refs,
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


def _required_schema_version(value: Any, prefix: str) -> int:
    schema_version = _required_int(value, "schema_version", prefix)
    if schema_version != SCHEMA_VERSION:
        raise DecisionRecordError(f"{prefix}schema_version must be {SCHEMA_VERSION}")
    return schema_version


def _required_str(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DecisionRecordError(f"{field_name} must be a non-empty string")
    return value.strip()


def _required_assertion_fingerprint(value: Any, prefix: str = "") -> str:
    try:
        fingerprint = _required_str(value, "assertion_fingerprint")
        _validate_assertion_fingerprint(fingerprint)
    except DecisionRecordError as exc:
        raise DecisionRecordError(f"{prefix}{exc}") from exc
    return fingerprint


def _validate_assertion_fingerprint(value: str) -> None:
    prefix = "sha256:"
    digest = value.removeprefix(prefix)
    if (
        not value.startswith(prefix)
        or len(digest) != 64
        or any(char not in "0123456789abcdef" for char in digest)
    ):
        raise DecisionRecordError(
            "assertion_fingerprint must be sha256: followed by 64 lowercase hex chars"
        )


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

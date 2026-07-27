"""The canonical stored case (design §4).

`AuditFindingRecord` carries IMMUTABLE identity plus APPEND-ONLY history. It deliberately
does NOT store a canonical payload: whoever ingested first would otherwise own the
message, severity, and evidence forever, and later observations would be discarded.

`status` is DERIVED from the last transition and validated against the stored value.
Disagreement is a load error, not a repair.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Annotated, Literal, get_args

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, model_validator

from science_model.audit.evidence import MAX_EVIDENCE_ENTRIES, Evidence
from science_model.audit.finding import (
    HashComponent,
    QualifierMap,
    Severity,
    reject_nul,
)
from science_model.audit.subjects import FindingSubject

DOC_KIND = "audit-case"

OCCURRENCE_DOMAIN = "science.occurrence.v1"
REVIEW_DOMAIN = "science.review.v1"


def _to_utc(value: datetime) -> datetime:
    """Every stored moment is an AWARE datetime in UTC.

    Normalizing at validation rather than at each use is the difference between a
    property and a convention. `current_severity()` compares `observed_at` values with
    `>`, and Python raises `TypeError` on a naive/aware pair -- so a record holding one
    of each would crash a method the design describes as a defined function of the log.
    Frontmatter and JSON both round-trip through parsers that may or may not attach a
    timezone, which is precisely why the model cannot assume one was attached.

    A naive value is READ AS UTC, matching what ingestion does with a report's
    `generated_at`. That is a decision, not a guess, and it lives in one place.
    """
    aware = value if value.tzinfo is not None else value.replace(tzinfo=UTC)
    return aware.astimezone(UTC)


#: Applied to every moment this module stores.
Instant = Annotated[datetime, AfterValidator(_to_utc)]

CaseStatus = Literal["proposed", "confirmed", "dismissed", "promoted"]
ReviewerKind = Literal["human", "agent", "deterministic"]
ReviewOutcome = Literal["confirms", "refutes", "abstains"]

#: DERIVED from the `Literal`, never retyped. The CLI's `--status` choice is built
#: from this, so a status added above appears in `--help` without a second edit --
#: and, more to the point, a status *not* above cannot be offered.
CASE_STATUSES: tuple[str, ...] = get_args(CaseStatus)

#: The transition graph is CLOSED. Any pair absent here is rejected.
PERMITTED_TRANSITIONS: frozenset[tuple[CaseStatus | None, CaseStatus]] = frozenset(
    {
        (None, "proposed"),
        ("proposed", "confirmed"),
        ("proposed", "dismissed"),
        ("confirmed", "dismissed"),
        ("confirmed", "promoted"),
        ("dismissed", "proposed"),
        ("promoted", "dismissed"),
    }
)


class RecordError(ValueError):
    """A stored case is malformed."""


def _components(**parts: str) -> None:
    """Every component of a `\\0`-delimited payload, checked before it is joined.

    The models below annotate these same fields with `HashComponent`, so a stored
    record cannot carry a NUL. This is the other half: these two functions are public,
    and a caller reaching them directly -- a producer computing a key to compare, a
    migration -- gets the same refusal rather than a silently ambiguous digest.
    """
    for name, value in parts.items():
        try:
            reject_nul(value)
        except ValueError as exc:
            raise RecordError(f"{name}: {exc}") from exc


def occurrence_key(*, producer_id: str, ingestion_ref: str, finding_id: str) -> str:
    _components(
        producer_id=producer_id,
        ingestion_ref=ingestion_ref,
        finding_id=finding_id,
    )
    payload = f"{OCCURRENCE_DOMAIN}\n{producer_id}\0{ingestion_ref}\0{finding_id}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def review_id(
    *,
    reviewer_kind: str,
    reviewer_ref: str,
    lens: str | None,
    run_ref: str,
    finding_id: str,
) -> str:
    """Lens is PART OF review identity: two lenses in one run are two reviews."""
    _components(
        reviewer_kind=reviewer_kind,
        reviewer_ref=reviewer_ref,
        lens=lens or "",
        run_ref=run_ref,
        finding_id=finding_id,
    )
    payload = (
        f"{REVIEW_DOMAIN}\n{reviewer_kind}\0{reviewer_ref}\0{lens or ''}\0"
        f"{run_ref}\0{finding_id}"
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


class _Base(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        revalidate_instances="always",
    )


class Occurrence(_Base):
    """One COMPLETE observation. Nothing a producer said is discarded."""

    #: REQUIRED, and validated against `occurrence_key(...)` by the owning record.
    #: Optional would mean a stored key nobody ever checks.
    idempotency_key: str = Field(pattern=r"^[0-9a-f]{64}$")
    #: `HashComponent`, not `str`: both are joined with `\0` to form that key.
    producer_id: HashComponent = Field(min_length=1)
    ingestion_ref: HashComponent = Field(min_length=1)
    observed_at: Instant
    severity: Severity
    message: str
    #: Frozen like every qualifier mapping here: a stored observation is history, and
    #: history that can be edited in place is not history.
    qualifiers: QualifierMap = Field(default_factory=dict, validate_default=True)
    evidence: tuple[Evidence, ...] = Field(
        default=(),
        max_length=MAX_EVIDENCE_ENTRIES,
    )
    #: Present when the observation arrived on the report's `accepted` channel. Same
    #: 32-hex shape the report's `AcceptedFinding` requires -- a stored key with a
    #: different shape could never match the entry that produced it.
    acceptance_key: str | None = Field(default=None, pattern=r"^[0-9a-f]{32}$")

    def content_signature(self) -> str:
        """What must match for an identical idempotency key to be a genuine retry."""
        return hashlib.sha256(
            canonical_occurrence_content(self).encode("utf-8")
        ).hexdigest()


def normalized_instant(value: datetime) -> str:
    """One SPELLING per instant: UTC, microsecond precision.

    `Instant` already guarantees an aware UTC value on anything stored; this fixes the
    textual form as well, so `12:00` and `12:00:00.000000` cannot hash differently.
    `_to_utc` is applied again rather than assumed, because this is also called on
    freshly built occurrences before they are attached to a record.
    """
    return _to_utc(value).isoformat(timespec="microseconds")


def canonical_occurrence_content(occurrence: Occurrence) -> str:
    """The COMPLETE observation, which is what an idempotency key promises.

    `observed_at` is included. Omitting it meant that reusing an ingestion ref with a
    different timestamp -- the same run identifier claiming a different moment -- was
    silently accepted as an identical retry. The docstring above calls an occurrence
    one complete observation; a comparison that skipped a field it stores would make
    that false.

    `producer_id`, `ingestion_ref`, and the record's `finding_id` are deliberately
    absent: they are the KEY, not the content, and comparing a key against itself
    proves nothing.
    """
    from science_model.audit.fingerprint import canonical_json

    return canonical_json(
        {
            "observed_at": normalized_instant(occurrence.observed_at),
            "severity": occurrence.severity,
            "message": occurrence.message,
            "qualifiers": {
                key: value for key, value in sorted(occurrence.qualifiers.items())
            },
            "evidence": [
                evidence.model_dump(mode="json", exclude_none=True)
                for evidence in occurrence.evidence
            ],
            "acceptance_key": occurrence.acceptance_key,
        }
    ).decode("utf-8")


class Transition(_Base):
    from_status: CaseStatus | None
    to_status: CaseStatus
    actor: str
    at: Instant
    reason: str = Field(min_length=1)
    task_ref: str | None = None

    @model_validator(mode="after")
    def _validate(self) -> Transition:
        if (self.from_status, self.to_status) not in PERMITTED_TRANSITIONS:
            raise RecordError(
                f"transition {self.from_status!r} -> {self.to_status!r} is not permitted"
            )
        if self.to_status == "promoted" and not self.task_ref:
            raise RecordError("a transition to 'promoted' requires task_ref")
        if self.to_status != "promoted" and self.task_ref is not None:
            raise RecordError(
                "task_ref is forbidden except on a transition to 'promoted'"
            )
        return self


class Review(_Base):
    review_id: str
    #: `reviewer_kind` is a `Literal`, so it cannot carry a NUL; the other three are
    #: free strings joined into `review_id`, so they are `HashComponent`.
    reviewer_kind: ReviewerKind
    reviewer_ref: HashComponent
    lens: HashComponent | None = None
    model: str | None = None
    run_ref: HashComponent
    at: Instant
    outcome: ReviewOutcome
    note: str = Field(min_length=1)

    @model_validator(mode="after")
    def _agent_provenance(self) -> Review:
        if self.reviewer_kind == "agent":
            if not self.lens:
                raise RecordError("an agent review requires a lens (design §4)")
            if not self.model:
                raise RecordError(
                    "an agent review requires model provenance, so the correlation "
                    "caution stays measurable (design §4)"
                )
        return self


#: Ordering for "the most severe observation", highest first.
_SEVERITY_RANK: dict[str, int] = {"error": 3, "warn": 2, "info": 1}


class AuditFindingRecord(BaseModel):
    """FROZEN, with immutable history collections.

    Every derived value stored here is RECOMPUTED and checked on construction:
    occurrence keys, review ids, the status implied by the transition log, and the
    promoted task. A stored derived value nobody validates is a value that can lie.

    Appending goes through `with_occurrence` / `with_review` / `with_transition`,
    which rebuild through the constructor. `model_copy(update=...)` is deliberately
    NOT the append path: it bypasses every validator above.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    finding_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    #: `Literal[1]`, not `int`. A stored record naming a fingerprint version this
    #: toolkit does not implement must not validate: its `finding_id` would be a
    #: digest under rules nothing here can reproduce, so every derived check below
    #: would be comparing against a scheme it cannot compute. Adding v2 means editing
    #: this line deliberately, which is the point.
    fingerprint_version: Literal[1]
    rule_id: str
    subject: FindingSubject
    #: The identity-bearing subset. `finding_id` is a digest OVER this mapping, so a
    #: mutable one would let a caller change the identity without changing the digest.
    identity_qualifiers: QualifierMap = Field(
        default_factory=dict,
        validate_default=True,
    )

    occurrences: tuple[Occurrence, ...] = Field(min_length=1)
    reviews: tuple[Review, ...] = ()
    transitions: tuple[Transition, ...] = Field(min_length=1)

    status: CaseStatus
    promoted_task: str | None = None

    @model_validator(mode="after")
    def _validate(self) -> AuditFindingRecord:
        self._validate_transitions()
        self._validate_occurrences()
        self._validate_reviews()
        return self

    def _validate_transitions(self) -> None:
        if self.transitions[0].from_status is not None:
            raise RecordError(
                "the first transition must be the genesis `None -> proposed`; the log "
                "is never empty and status needs no special case"
            )
        expected: CaseStatus | None = None
        promotion_task: str | None = None
        for transition in self.transitions:
            if transition.from_status != expected:
                raise RecordError(
                    f"transition log is discontinuous: expected from_status "
                    f"{expected!r}, got {transition.from_status!r}"
                )
            expected = transition.to_status
            if transition.to_status == "promoted":
                promotion_task = transition.task_ref
        if self.status != expected:
            raise RecordError(
                f"status {self.status!r} disagrees with the transition log, which ends "
                f"at {expected!r}; this is a load error, not something to repair"
            )
        if (self.status == "promoted") != (self.promoted_task is not None):
            raise RecordError(
                "promoted_task is present if and only if status is 'promoted'"
            )
        if self.status == "promoted" and self.promoted_task != promotion_task:
            raise RecordError(
                f"promoted_task {self.promoted_task!r} does not match the task_ref "
                f"{promotion_task!r} recorded on the promotion transition"
            )

    def _validate_occurrences(self) -> None:
        seen: set[str] = set()
        for occurrence in self.occurrences:
            expected = occurrence_key(
                producer_id=occurrence.producer_id,
                ingestion_ref=occurrence.ingestion_ref,
                finding_id=self.finding_id,
            )
            if occurrence.idempotency_key != expected:
                raise RecordError(
                    f"occurrence idempotency_key {occurrence.idempotency_key!r} is not "
                    f"the key derived from its own fields ({expected!r})"
                )
            if occurrence.idempotency_key in seen:
                raise RecordError(
                    f"duplicate occurrence idempotency_key "
                    f"{occurrence.idempotency_key!r}"
                )
            seen.add(occurrence.idempotency_key)
            self._validate_identity_agreement(occurrence)

    def _validate_identity_agreement(self, occurrence: Occurrence) -> None:
        """Every occurrence must agree with the record on identity-bearing keys.

        `finding_id` is a digest over `identity_qualifiers`, and an occurrence carries
        the producer's FULL qualifier mapping. If the two disagree on a key that bears
        identity, the record is claiming an identity its own evidence contradicts --
        an occurrence about `field: year` filed under the digest for `field: month`.
        Comparison is on NFC-normalized values, the same form the fingerprint hashes,
        so two spellings of one string are not read as two different facts.
        """
        from science_model.audit.fingerprint import normalize_identity_value

        for key, value in self.identity_qualifiers.items():
            if key not in occurrence.qualifiers:
                raise RecordError(
                    f"occurrence {occurrence.idempotency_key!r} omits identity "
                    f"qualifier {key!r}, which this case's finding_id is derived from"
                )
            if normalize_identity_value(
                occurrence.qualifiers[key]
            ) != normalize_identity_value(value):
                raise RecordError(
                    f"occurrence {occurrence.idempotency_key!r} reports {key!r}="
                    f"{occurrence.qualifiers[key]!r} but this case's identity is "
                    f"{key!r}={value!r}; they are different findings"
                )

    def _validate_reviews(self) -> None:
        seen: set[str] = set()
        for review in self.reviews:
            expected = review_id(
                reviewer_kind=review.reviewer_kind,
                reviewer_ref=review.reviewer_ref,
                lens=review.lens,
                run_ref=review.run_ref,
                finding_id=self.finding_id,
            )
            if review.review_id != expected:
                raise RecordError(
                    f"review_id {review.review_id!r} is not the id derived from its own "
                    f"fields ({expected!r})"
                )
            if review.review_id in seen:
                raise RecordError(f"duplicate review_id {review.review_id!r}")
            seen.add(review.review_id)

    def with_occurrence(self, occurrence: Occurrence) -> AuditFindingRecord:
        """Append through the constructor, so every validator above runs."""
        return AuditFindingRecord.model_validate(
            {
                **self.model_dump(mode="python"),
                "occurrences": (*self.occurrences, occurrence),
            }
        )

    def with_review(self, review: Review) -> AuditFindingRecord:
        return AuditFindingRecord.model_validate(
            {
                **self.model_dump(mode="python"),
                "reviews": (*self.reviews, review),
            }
        )

    def with_transition(
        self,
        transition: Transition,
        *,
        promoted_task: str | None = None,
    ) -> AuditFindingRecord:
        return AuditFindingRecord.model_validate(
            {
                **self.model_dump(mode="python"),
                "transitions": (*self.transitions, transition),
                "status": transition.to_status,
                "promoted_task": promoted_task,
            }
        )

    def current_severity(self) -> Severity:
        """Max severity over occurrences from EACH producer's MOST RECENT ingestion.

        A defined function of the log (design §4), not a field anyone writes. An older
        run that saw `error` does not keep a case at `error` after every producer's
        latest look says `warn`.
        """
        latest: dict[str, tuple[datetime, Severity]] = {}
        for occurrence in self.occurrences:
            seen = latest.get(occurrence.producer_id)
            if seen is None or occurrence.observed_at > seen[0]:
                latest[occurrence.producer_id] = (
                    occurrence.observed_at,
                    occurrence.severity,
                )
            elif occurrence.observed_at == seen[0]:
                if _SEVERITY_RANK[occurrence.severity] > _SEVERITY_RANK[seen[1]]:
                    latest[occurrence.producer_id] = (
                        seen[0],
                        occurrence.severity,
                    )
        return max(
            (severity for _at, severity in latest.values()),
            key=lambda severity: _SEVERITY_RANK[severity],
        )

    def confirmation_count(self) -> int:
        """Distinct confirming reviews. NEVER a confidence, NEVER aggregated."""
        return len({r.review_id for r in self.reviews if r.outcome == "confirms"})

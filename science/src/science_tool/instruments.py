"""Canonical instrument result type — the silent-instrument ruling.

An *instrument* is a helper whose empty return is rendered to a user as a
finding. The failure this type exists to stop: an instrument returns a
clean-looking empty result when it never actually ran, and the caller reports
that as "nothing found".

The invariant, enforced below rather than merely documented:

    ``empty`` and ``unwired`` are different, and the result cannot be
    constructed without choosing between them.

- ``ok`` — ran, found rows.
- ``empty`` — ran, genuinely found nothing. A TRUE zero finding.
- ``unwired`` — could not run. ``rows`` is meaningless. Requires no rows AND a
  machine-readable ``code``.

``reason``/``code`` are NOT exclusive to ``unwired``: a run that succeeded while
silently dropping part of its input carries them as a caveat on an ``ok``/``empty``
result. A renderer must surface a ``reason`` whatever the status.

See docs/plans/2026-07-11-instrument-result-convergence-design.md.
"""

from __future__ import annotations

from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, Field, model_validator

RowT = TypeVar("RowT")

InstrumentStatus = Literal["ok", "empty", "unwired"]

#: Modules whose public helpers must return ``InstrumentResult``.
#:
#: This tuple is the SINGLE definition of the instrument namespace. The AST guard
#: (tests/test_instrument_boundary.py) imports it, and any migration query must
#: import it too. Written twice, the guard and the query would drift — which is
#: the class of failure this whole module exists to prevent.
INSTRUMENT_MODULES: tuple[str, ...] = (
    "big_picture/knowledge_gaps.py",
    "big_picture/validator.py",
    "graph/health.py",
    "graph/health_checks/unresolved_refs.py",
    "graph/health_checks/unregistered_ref_kinds.py",
    "graph/health_checks/lingering_tags.py",
    "graph/health_checks/identity_policy.py",
    "graph/health_checks/entity_identity.py",
    "graph/health_checks/dataset_anomalies.py",
    "graph/health_checks/agent_context.py",
    "graph/health_checks/tooling_scaffold.py",
    "graph/health_checks/validate.py",
    "graph/health_checks/legacy_task_type.py",
    "graph/health_checks/invalid_entity_aspects.py",
    "graph/health_checks/archive_lag.py",
    "graph/health_checks/managed_artifacts.py",
    "graph/health_checks/prose_epistemics.py",
    "graph/health_checks/cross_paper_evidence.py",
    "graph/health_checks/layered_claim_migration.py",
    "graph/attention.py",
    "graph/store/summary.py",
    "graph/store/queries.py",
    "graph/store/inquiry.py",
    "graph/store/validation.py",
    "curate/inventory.py",
    "benchmark_catalog.py",
    "datasets_catalog.py",
)


class InstrumentResult(BaseModel, Generic[RowT]):
    status: InstrumentStatus
    rows: list[RowT] = Field(default_factory=list)
    reason: str | None = None
    code: str | None = None

    @model_validator(mode="after")
    def _enforce_status_invariant(self) -> "InstrumentResult[RowT]":
        if self.status == "ok" and not self.rows:
            raise ValueError("status='ok' requires non-empty rows; use status='empty'")
        if self.status == "empty" and self.rows:
            raise ValueError("status='empty' forbids rows")
        if self.status == "unwired":
            if self.rows:
                raise ValueError("status='unwired' forbids rows; they are meaningless")
            if not self.code:
                raise ValueError("status='unwired' requires a machine-readable code")
        return self

    @classmethod
    def ok(
        cls,
        rows: list[RowT],
        *,
        code: str | None = None,
        reason: str | None = None,
    ) -> "InstrumentResult[RowT]":
        return cls(status="ok", rows=rows, code=code, reason=reason)

    @classmethod
    def empty(
        cls,
        *,
        code: str | None = None,
        reason: str | None = None,
    ) -> "InstrumentResult[RowT]":
        return cls(status="empty", rows=[], code=code, reason=reason)

    @classmethod
    def unwired(cls, *, code: str, reason: str | None = None) -> "InstrumentResult[RowT]":
        return cls(status="unwired", rows=[], code=code, reason=reason)

    @classmethod
    def from_rows(
        cls,
        rows: list[RowT],
        *,
        code: str | None = None,
        reason: str | None = None,
    ) -> "InstrumentResult[RowT]":
        """Ran successfully; ``ok`` if it found anything, ``empty`` if it truly did not.

        Use this ONLY where the instrument definitely ran. If it may not have run,
        the caller must decide and call ``unwired`` explicitly — that decision is
        the entire point of this type and must not be inferred from row count.
        """
        if rows:
            return cls.ok(rows, code=code, reason=reason)
        return cls.empty(code=code, reason=reason)


ValidationVerdictStatus = Literal["passed", "failed", "unwired"]


class ValidationVerdict(BaseModel, Generic[RowT]):
    """Canonical validator/audit result — the verdict axis of the instrument convergence.

    Sibling to ``InstrumentResult``. Where an *instrument* reports found/empty/unwired, a
    *validator* reports a pass/fail VERDICT over a report card present whenever it ran.
    There is no ``empty``: a validator that ran is ``passed`` or ``failed``; one that could
    not is ``unwired``. ``passed`` with an empty card is told from ``unwired`` by STATUS,
    never by row count.

    Named ``ValidationVerdict``, not ``Verdict``: ``science_tool.verdict`` is the epistemic
    verdict-token package — a different meaning of the word.

    The verdict is set EXPLICITLY by the caller. The type is ``Generic[RowT]`` and cannot
    inspect ``row["status"]``, exactly as ``InstrumentResult`` cannot inspect its rows.
    """

    status: ValidationVerdictStatus
    rows: list[RowT] = Field(default_factory=list)
    reason: str | None = None
    code: str | None = None

    @model_validator(mode="after")
    def _enforce_status_invariant(self) -> "ValidationVerdict[RowT]":
        if self.status == "unwired":
            if self.rows:
                raise ValueError("status='unwired' forbids rows; they are meaningless")
            if not self.code:
                raise ValueError("status='unwired' requires a machine-readable code")
        return self

    @classmethod
    def passed(
        cls, rows: list[RowT], *, code: str | None = None, reason: str | None = None
    ) -> "ValidationVerdict[RowT]":
        return cls(status="passed", rows=rows, code=code, reason=reason)

    @classmethod
    def failed(
        cls, rows: list[RowT], *, code: str | None = None, reason: str | None = None
    ) -> "ValidationVerdict[RowT]":
        return cls(status="failed", rows=rows, code=code, reason=reason)

    @classmethod
    def unwired(cls, *, code: str, reason: str | None = None) -> "ValidationVerdict[RowT]":
        return cls(status="unwired", rows=[], code=code, reason=reason)

    @classmethod
    def from_has_failures(
        cls,
        rows: list[RowT],
        has_failures: bool,
        *,
        code: str | None = None,
        reason: str | None = None,
    ) -> "ValidationVerdict[RowT]":
        return cls(status="failed" if has_failures else "passed", rows=rows, code=code, reason=reason)

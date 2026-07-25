from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from science_model.autonomous_runs import (
    RUN_ID_PREFIX,
    AutonomousRunRecord,
    RunBudget,
    RunDisposition,
    RunTier,
)

_BASE = "a" * 40
_HEAD = "b" * 40
_TOOLKIT = "c" * 40
_DIGEST = "d" * 64


def _payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "id": "run:2026-07-24-curation-sweep-a3f1",
        "agent": "curation-sweep",
        "model": "claude-opus-5",
        "tier": "belief-neutral",
        "branch": "auto/2026-07-24-curation-sweep-a3f1",
        "base_commit": _BASE,
        "head_commit": _HEAD,
        "toolkit_revision": _TOOLKIT,
        "policy_identity": {"id": "core-default", "version": "1"},
        "basis_digest": _DIGEST,
        "started": datetime(2026, 7, 24, 9, 0, tzinfo=UTC),
        "ended": datetime(2026, 7, 24, 9, 30, tzinfo=UTC),
        "budget": {"tokens": 12000, "wall_clock_seconds": 1800.5},
        "disposition": "clean",
    }
    payload.update(overrides)
    return payload


def test_valid_record_round_trips() -> None:
    record = AutonomousRunRecord.model_validate(_payload())
    assert record.id == "run:2026-07-24-curation-sweep-a3f1"
    assert record.slug == "2026-07-24-curation-sweep-a3f1"
    assert record.tier is RunTier.BELIEF_NEUTRAL
    assert record.disposition is RunDisposition.CLEAN
    assert record.policy_identity.id == "core-default"
    assert record.budget == RunBudget(tokens=12000, wall_clock_seconds=1800.5)
    assert record.triggered_by is None


def test_record_is_frozen() -> None:
    record = AutonomousRunRecord.model_validate(_payload())
    with pytest.raises(ValidationError):
        record.disposition = RunDisposition.QUARANTINED  # type: ignore[misc]


def test_unknown_field_is_refused() -> None:
    with pytest.raises(ValidationError):
        AutonomousRunRecord.model_validate(_payload(entities_written=["hypothesis:h01"]))


def test_id_must_carry_the_run_prefix() -> None:
    with pytest.raises(ValidationError, match=RUN_ID_PREFIX):
        AutonomousRunRecord.model_validate(_payload(id="2026-07-24-curation-sweep-a3f1"))


def test_id_must_name_its_own_agent() -> None:
    # The id says `curation-sweep`; the record claims a different agent. Accepting this
    # would let one run present two identities to `git log` and to the graph.
    with pytest.raises(ValidationError, match="must name its agent"):
        AutonomousRunRecord.model_validate(_payload(agent="drift-sweep"))


def test_id_must_begin_with_a_real_calendar_date() -> None:
    with pytest.raises(ValidationError, match="YYYY-MM-DD"):
        AutonomousRunRecord.model_validate(
            _payload(
                id="run:2026-07-32-curation-sweep-a3f1",
                branch="auto/2026-07-32-curation-sweep-a3f1",
            )
        )


def test_short_id_may_not_absorb_a_hyphen() -> None:
    # `agent: curation` + short id `sweep-a3f1` is the second reading of the same string.
    # Constructive validation must refuse it rather than pick a reading.
    with pytest.raises(ValidationError, match="short suffix"):
        AutonomousRunRecord.model_validate(_payload(agent="curation"))


def test_branch_must_match_the_id() -> None:
    with pytest.raises(ValidationError, match="branch must be"):
        AutonomousRunRecord.model_validate(_payload(branch="auto/some-other-branch"))


@pytest.mark.parametrize("field_name", ["base_commit", "head_commit", "toolkit_revision"])
def test_abbreviated_sha_is_refused(field_name: str) -> None:
    with pytest.raises(ValidationError, match="40-character"):
        AutonomousRunRecord.model_validate(_payload(**{field_name: "a1b2c3d"}))


@pytest.mark.parametrize("field_name", ["base_commit", "head_commit", "toolkit_revision"])
def test_uppercase_sha_is_refused(field_name: str) -> None:
    with pytest.raises(ValidationError, match="40-character"):
        AutonomousRunRecord.model_validate(_payload(**{field_name: "A" * 40}))


def test_head_may_equal_base() -> None:
    # A report-only run legitimately commits nothing. Requiring movement would make
    # the honest no-op case unrepresentable.
    record = AutonomousRunRecord.model_validate(_payload(head_commit=_BASE))
    assert record.head_commit == record.base_commit


def test_basis_digest_must_be_a_sha256() -> None:
    with pytest.raises(ValidationError, match="64-character"):
        AutonomousRunRecord.model_validate(_payload(basis_digest="d" * 40))


def test_ended_may_not_precede_started() -> None:
    with pytest.raises(ValidationError, match="precedes"):
        AutonomousRunRecord.model_validate(
            _payload(ended=datetime(2026, 7, 24, 8, 0, tzinfo=UTC))
        )


@pytest.mark.parametrize("field_name", ["started", "ended"])
def test_naive_timestamps_are_refused(field_name: str) -> None:
    with pytest.raises(ValidationError, match="timezone"):
        AutonomousRunRecord.model_validate(
            _payload(**{field_name: datetime(2026, 7, 24, 9, 15)})
        )


def test_triggered_by_must_be_omitted_not_blank() -> None:
    with pytest.raises(ValidationError, match="omitted, not blank"):
        AutonomousRunRecord.model_validate(_payload(triggered_by="   "))


def test_triggered_by_is_kept_when_present() -> None:
    record = AutonomousRunRecord.model_validate(_payload(triggered_by="schedule:weekly-curation"))
    assert record.triggered_by == "schedule:weekly-curation"


def test_budget_is_required() -> None:
    # The design marks only `triggered_by` optional. A run that reports no cost is a run
    # whose cost nobody can audit, and S4's estimates are built from exactly this field.
    payload = _payload()
    del payload["budget"]
    with pytest.raises(ValidationError):
        AutonomousRunRecord.model_validate(payload)


def test_budget_requires_at_least_one_measure() -> None:
    with pytest.raises(ValidationError, match="tokens"):
        AutonomousRunRecord.model_validate(_payload(budget={}))


@pytest.mark.parametrize("measure", ["tokens", "wall_clock_seconds"])
def test_budget_refuses_negative_values(measure: str) -> None:
    with pytest.raises(ValidationError, match="negative"):
        AutonomousRunRecord.model_validate(_payload(budget={measure: -1}))


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_budget_refuses_non_finite_wall_clock(value: float) -> None:
    # `nan < 0` and `inf < 0` are both False, so a bare sign check lets these through.
    with pytest.raises(ValidationError, match="finite"):
        AutonomousRunRecord.model_validate(_payload(budget={"wall_clock_seconds": value}))


def test_budget_accepts_either_measure() -> None:
    record = AutonomousRunRecord.model_validate(_payload(budget={"tokens": 12000}))
    assert record.budget == RunBudget(tokens=12000)


@pytest.mark.parametrize("field_name", ["model", "agent"])
def test_blank_identity_strings_are_refused(field_name: str) -> None:
    with pytest.raises(ValidationError):
        AutonomousRunRecord.model_validate(_payload(**{field_name: "   "}))


@pytest.mark.parametrize("part", ["id", "version"])
def test_blank_policy_identity_parts_are_refused(part: str) -> None:
    identity = {"id": "core-default", "version": "1"} | {part: "  "}
    with pytest.raises(ValidationError, match="may not be blank"):
        AutonomousRunRecord.model_validate(_payload(policy_identity=identity))


def test_tier_vocabulary_is_closed() -> None:
    # There is deliberately no `full` tier: changing belief is human work by definition.
    with pytest.raises(ValidationError):
        AutonomousRunRecord.model_validate(_payload(tier="full"))
    assert {tier.value for tier in RunTier} == {"report-only", "belief-neutral"}


def test_disposition_vocabulary_is_closed() -> None:
    with pytest.raises(ValidationError):
        AutonomousRunRecord.model_validate(_payload(disposition="passed"))
    assert {d.value for d in RunDisposition} == {"clean", "quarantined", "unwired"}


def test_unwired_run_must_omit_its_basis_digest() -> None:
    # `unwired` means the basis was NOT computable. A digest on such a record can only
    # have been fabricated, and a fabricated value inside a supervisor attestation is the
    # precise failure the run record exists to make impossible.
    with pytest.raises(ValidationError, match="must be omitted when disposition is 'unwired'"):
        AutonomousRunRecord.model_validate(_payload(disposition="unwired"))


def test_unwired_run_validates_without_a_basis_digest() -> None:
    record = AutonomousRunRecord.model_validate(
        _payload(disposition="unwired", basis_digest=None)
    )
    assert record.disposition is RunDisposition.UNWIRED
    assert record.basis_digest is None


@pytest.mark.parametrize("disposition", ["clean", "quarantined"])
def test_a_wired_run_still_requires_its_basis_digest(disposition: str) -> None:
    # The rule is conditional in BOTH directions: omitting the digest is required when
    # unwired and refused otherwise. A plain `str | None` would silently accept this.
    with pytest.raises(ValidationError, match="basis_digest is required"):
        AutonomousRunRecord.model_validate(
            _payload(disposition=disposition, basis_digest=None)
        )

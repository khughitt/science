from __future__ import annotations

import pytest
from science_model.autonomous_runs import RunTier

from science_tool.autonomy.changes import BODY_FIELD, ChangeSet, ChangeType, PathChange
from science_tool.autonomy.path_gate import GateInputError, evaluate


def _cs(*changes: PathChange) -> ChangeSet:
    return ChangeSet(base_commit="a" * 40, head_commit="b" * 40, changes=changes)


def _paper(fields: tuple[str, ...], change_type: ChangeType = ChangeType.MODIFIED) -> PathChange:
    return PathChange(
        path="entities/papers/smith2020.md",
        change_type=change_type,
        entity_kind="paper",
        fields=fields,
    )


def test_an_allowlisted_field_edit_is_allowed():
    verdict = evaluate(_cs(_paper(("venue",))), tier=RunTier.BELIEF_NEUTRAL)
    assert verdict.allowed is True
    assert verdict.denials == ()


def test_a_belief_bearing_field_edit_is_denied():
    verdict = evaluate(_cs(_paper(("confidence",))), tier=RunTier.BELIEF_NEUTRAL)
    assert verdict.allowed is False
    assert [d.field for d in verdict.denials] == ["confidence"]


def test_an_allowed_field_does_not_launder_a_denied_sibling():
    """A single denial in a multi-field edit denies the change."""
    verdict = evaluate(_cs(_paper(("venue", "confidence"))), tier=RunTier.BELIEF_NEUTRAL)
    assert verdict.allowed is False
    assert [d.field for d in verdict.denials] == ["confidence"]


def test_a_body_prose_edit_is_denied():
    verdict = evaluate(_cs(_paper((BODY_FIELD,))), tier=RunTier.BELIEF_NEUTRAL)
    assert verdict.allowed is False
    assert verdict.denials[0].field == BODY_FIELD


def test_a_field_nobody_registered_is_denied_with_no_test_edit():
    """Design test #4: default-deny needs no registration and no edit here."""
    verdict = evaluate(
        _cs(_paper(("zzz_field_invented_tomorrow",))), tier=RunTier.BELIEF_NEUTRAL
    )
    assert verdict.allowed is False


def test_entity_creation_is_denied():
    verdict = evaluate(_cs(_paper(("title",), ChangeType.ADDED)), tier=RunTier.BELIEF_NEUTRAL)
    assert verdict.allowed is False
    assert "creation" in verdict.denials[0].reason


def test_entity_deletion_is_denied():
    verdict = evaluate(_cs(_paper((), ChangeType.DELETED)), tier=RunTier.BELIEF_NEUTRAL)
    assert verdict.allowed is False
    assert "deletion" in verdict.denials[0].reason


def test_a_kind_with_no_allowlist_entry_is_denied():
    change = PathChange(
        path="entities/hypotheses/h01.md",
        change_type=ChangeType.MODIFIED,
        entity_kind="hypothesis",
        fields=("status",),
    )
    assert evaluate(_cs(change), tier=RunTier.BELIEF_NEUTRAL).allowed is False


def test_a_non_entity_path_is_denied_with_its_named_reason():
    change = PathChange(
        path="core/decisions.md", change_type=ChangeType.MODIFIED, entity_kind=None, fields=()
    )
    verdict = evaluate(_cs(change), tier=RunTier.BELIEF_NEUTRAL)
    assert verdict.allowed is False
    assert "guard integrity" in verdict.denials[0].reason
    assert verdict.denials[0].field is None


def test_report_only_denies_what_belief_neutral_allows():
    """Design §1: report-only may write ONLY the run's own report path."""
    change_set = _cs(_paper(("venue",)))
    assert evaluate(change_set, tier=RunTier.BELIEF_NEUTRAL).allowed is True
    assert evaluate(change_set, tier=RunTier.REPORT_ONLY).allowed is False


def test_the_report_path_is_allowed_in_both_tiers():
    change = PathChange(
        path="results/sweep-a3f1.md", change_type=ChangeType.ADDED, entity_kind=None, fields=()
    )
    for tier in (RunTier.REPORT_ONLY, RunTier.BELIEF_NEUTRAL):
        verdict = evaluate(_cs(change), tier=tier, report_path="results/sweep-a3f1.md")
        assert verdict.allowed is True, tier


def test_report_only_with_no_report_path_allows_nothing():
    change = PathChange(
        path="results/sweep-a3f1.md", change_type=ChangeType.ADDED, entity_kind=None, fields=()
    )
    assert evaluate(_cs(change), tier=RunTier.REPORT_ONLY).allowed is False


@pytest.mark.parametrize("invalid_tier", ["report-only", "third-tier"])
def test_an_invalid_runtime_tier_is_rejected(invalid_tier: str):
    with pytest.raises(GateInputError):
        evaluate(
            _cs(_paper(("venue",))),
            tier=invalid_tier,  # type: ignore[arg-type]
        )


@pytest.mark.parametrize("bad", ["/abs/report.md", "../escape.md", "a/../../escape.md"])
def test_an_unsafe_report_path_is_rejected_rather_than_honoured(bad: str):
    with pytest.raises(GateInputError):
        evaluate(_cs(), tier=RunTier.REPORT_ONLY, report_path=bad)


def test_an_empty_change_set_is_allowed():
    assert evaluate(_cs(), tier=RunTier.BELIEF_NEUTRAL).allowed is True


def test_a_modification_with_no_changed_fields_is_denied():
    """Fail-open regression: git reports a chmod as `M` with identical blobs, so a
    modification carrying no field change must not read as 'nothing to deny'."""
    verdict = evaluate(_cs(_paper(())), tier=RunTier.BELIEF_NEUTRAL)
    assert verdict.allowed is False
    assert "no field-level change" in verdict.denials[0].reason


def test_denials_are_ordered_by_path_then_field():
    verdict = evaluate(
        _cs(
            _paper(("confidence", "abstract")),
            PathChange(
                path="core/decisions.md",
                change_type=ChangeType.MODIFIED,
                entity_kind=None,
                fields=(),
            ),
        ),
        tier=RunTier.BELIEF_NEUTRAL,
    )
    assert [(d.path, d.field) for d in verdict.denials] == [
        ("core/decisions.md", None),
        ("entities/papers/smith2020.md", "abstract"),
        ("entities/papers/smith2020.md", "confidence"),
    ]

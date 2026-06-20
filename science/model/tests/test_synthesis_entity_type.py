from __future__ import annotations


def test_entity_type_has_synthesis_and_is_not_a_mechanism_participant() -> None:
    from science_model.entities import _DISALLOWED_MECHANISM_PARTICIPANT_KINDS, EntityType

    assert EntityType.SYNTHESIS.value == "synthesis"
    # synthesis is a document/output kind like report → must be barred as a
    # mechanism participant exactly as report is.
    assert EntityType.SYNTHESIS.value in _DISALLOWED_MECHANISM_PARTICIPANT_KINDS
    assert EntityType.REPORT.value in _DISALLOWED_MECHANISM_PARTICIPANT_KINDS  # guard the mirror

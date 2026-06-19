from __future__ import annotations

import pytest
from pydantic import ValidationError

from science_model.propositions import DiscussesMembership, PropositionEntity
from science_model.reasoning import MembershipRole


def _prop(discusses):
    return PropositionEntity(
        id="proposition:p1",
        type="proposition",
        title="P1",
        status="active",
        ontology_terms=[],
        source_refs=[],
        related=[],
        discusses=discusses,
    )


def test_bare_string_is_core():
    p = _prop(["hypothesis:h1"])
    assert list(p.iter_memberships()) == [("hypothesis:h1", MembershipRole.CORE)]


def test_object_form_carries_role():
    p = _prop([{"frame": "hypothesis:h1", "role": "rival"}])
    assert list(p.iter_memberships()) == [("hypothesis:h1", MembershipRole.RIVAL)]


def test_object_role_defaults_to_core():
    p = _prop([{"frame": "hypothesis:h1"}])
    assert list(p.iter_memberships()) == [("hypothesis:h1", MembershipRole.CORE)]


def test_mixed_string_and_object():
    p = _prop(["hypothesis:h1", {"frame": "mechanism:m1", "role": "background"}])
    assert list(p.iter_memberships()) == [
        ("hypothesis:h1", MembershipRole.CORE),
        ("mechanism:m1", MembershipRole.BACKGROUND),
    ]


def test_unknown_role_rejected_at_model_layer():
    with pytest.raises(ValidationError):
        _prop([{"frame": "hypothesis:h1", "role": "rebuttal"}])


def test_membership_requires_frame():
    with pytest.raises(ValidationError):
        DiscussesMembership(role="core")


def test_empty_frame_rejected():
    with pytest.raises(ValidationError):
        DiscussesMembership(frame="", role="core")


def test_extra_keys_forbidden():
    with pytest.raises(ValidationError):
        DiscussesMembership(frame="hypothesis:h1", role="core", note="oops")


def test_conflicting_duplicate_frame_rejected_at_model_layer():
    with pytest.raises(ValidationError):
        _prop(["hypothesis:h1", {"frame": "hypothesis:h1", "role": "rival"}])


def test_identical_duplicate_frame_allowed():
    p = _prop(["hypothesis:h1", "hypothesis:h1"])  # same role -> no conflict
    assert list(p.iter_memberships()) == [("hypothesis:h1", MembershipRole.CORE)]

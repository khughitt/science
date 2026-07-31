from __future__ import annotations

import pytest
from pydantic import ValidationError

from science_model.evidence_broker import SurfacePolicy


def test_deny_prefixes_are_normalized_on_construction():
    policy = SurfacePolicy(deny_prefixes=("./notes//drafts", "a\\b"), notice="withheld")
    assert policy.deny_prefixes == ("notes/drafts", "a/b")


def test_a_traversal_prefix_is_refused_not_collapsed():
    with pytest.raises(ValidationError):
        SurfacePolicy(deny_prefixes=("notes/../secrets",), notice="withheld")


def test_an_absolute_prefix_is_refused():
    with pytest.raises(ValidationError):
        SurfacePolicy(deny_prefixes=("/etc/passwd",), notice="withheld")


def test_a_notice_is_required():
    """A policy that denies without telling the requester anything is a policy that
    cannot be honoured uniformly, which is the property a blinding study needs."""
    with pytest.raises(ValidationError):
        SurfacePolicy(deny_prefixes=("notes",))


def test_the_policy_is_frozen_and_forbids_extras():
    policy = SurfacePolicy(deny_prefixes=("notes",), notice="withheld")
    with pytest.raises(ValidationError):
        policy.deny_prefixes = ()
    with pytest.raises(ValidationError):
        SurfacePolicy(deny_prefixes=(), notice="withheld", budget=3)

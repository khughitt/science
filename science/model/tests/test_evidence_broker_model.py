from __future__ import annotations

import unicodedata

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


def test_a_non_nfc_prefix_is_refused_rather_than_silently_weakened():
    """MEASURED, git 2.55: with an NFD `café/x.txt` committed, a deny prefix written in NFD is
    stored as NFC, `:(top,literal,exclude)café` in NFC matches nothing, and `git grep` serves
    the file and its content -- while `read` of the same path normalizes to NFC too and misses.
    The policy is enforced by `read` and not by `search`, and the caller who wrote it cannot
    tell.

    There is no spelling of `SurfacePolicy` that denies that path, because storage is NFC and
    git matches bytes. So the construction fails instead of returning a policy weaker than the
    one asked for. `assert policy.deny_prefixes == (nfd,)` would be the wrong fix: it makes the
    field a byte-exact carrier and breaks the "one spelling" property `authorize` depends on.
    """
    nfd = unicodedata.normalize("NFD", "café")
    assert nfd != unicodedata.normalize("NFC", nfd), "fixture is not actually NFD"
    with pytest.raises(ValidationError, match="not in NFC"):
        SurfacePolicy(deny_prefixes=(nfd,), notice="withheld")


def test_an_nfc_prefix_carrying_the_same_characters_is_accepted():
    """The control. Refusing every non-ASCII prefix would be a stricter-looking rule that
    withdraws a legitimate policy: the NFC spelling reaches git byte-exactly and works."""
    nfc = unicodedata.normalize("NFC", "café")
    assert SurfacePolicy(deny_prefixes=(nfc,), notice="withheld").deny_prefixes == (nfc,)


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

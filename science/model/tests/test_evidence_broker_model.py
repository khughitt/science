from __future__ import annotations

import unicodedata

import pytest
from pydantic import ValidationError

from science_model.evidence_broker import (
    MAX_INLINE_LINES,
    MAX_TARGET_CHARS,
    REPLAY_PROTOCOL_VERSION,
    EvidenceExposure,
    EvidenceSession,
    ExposureEntry,
    InlineInput,
    InstrumentIdentity,
    Outcome,
    SurfacePolicy,
)

COMMIT = "a" * 40
OTHER = "b" * 40
INSTRUMENT = InstrumentIdentity(ref="rubric.md", sha256="c" * 64, prompt_hash="d" * 64)
POLICY = SurfacePolicy(notice="withheld")


def _entry(**overrides) -> ExposureEntry:
    fields = {
        "op": "read",
        "target": "a.md",
        "commit": COMMIT,
        "sha256": "e" * 64,
        "outcome": Outcome.SERVED,
    }
    return ExposureEntry(**{**fields, **overrides})


def _exposure(**overrides) -> EvidenceExposure:
    fields = {
        "commit": COMMIT,
        "budget": 10,
        "requests_used": 0,
        "instrument": INSTRUMENT,
        "surface_policy": POLICY,
        "replay_protocol": REPLAY_PROTOCOL_VERSION,
        "entries": (),
    }
    return EvidenceExposure(**{**fields, **overrides})


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
    withdraws a legitimate policy: the NFC spelling reaches git byte-exactly and works --
    against a tree whose paths are themselves NFC.

    That qualifier is load-bearing. Plan 4a refuses a brokered run at open unless every tree
    path is valid UTF-8 and already NFC, so this model test remains only the accepted-spelling
    control.
    """
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


def test_requests_used_must_equal_the_non_inline_entry_count() -> None:
    """A spend counter that can disagree with the log it counts is a value that can lie."""
    with pytest.raises(ValidationError, match="requests_used"):
        _exposure(requests_used=1, entries=(_entry(op="inline"),))


def test_a_refusal_counts_toward_the_spend() -> None:
    """Denials spend rounds, so they are entries like any other."""
    exposure = _exposure(requests_used=1, entries=(_entry(outcome=Outcome.REFUSED),))
    assert exposure.requests_used == 1


def test_requests_used_may_not_exceed_the_budget() -> None:
    with pytest.raises(ValidationError, match="budget"):
        _exposure(budget=1, requests_used=2, entries=(_entry(), _entry(target="b.md")))


def test_entries_must_agree_with_the_exposure_commit() -> None:
    """A run that read two trees did not have one evidence surface."""
    with pytest.raises(ValidationError, match="commit"):
        _exposure(requests_used=1, entries=(_entry(commit=OTHER),))


def test_an_inline_entry_carries_served() -> None:
    """Inline seeding is the supervisor's own input, not a request outcome."""
    with pytest.raises(ValidationError, match="inline"):
        _exposure(entries=(_entry(op="inline", outcome=Outcome.REFUSED),))


def test_the_instrument_is_required() -> None:
    with pytest.raises(ValidationError):
        EvidenceExposure(
            commit=COMMIT,
            budget=1,
            requests_used=0,
            surface_policy=POLICY,
            replay_protocol=REPLAY_PROTOCOL_VERSION,
        )


def test_a_budget_of_zero_is_legitimate() -> None:
    assert _exposure(budget=0, requests_used=0).budget == 0


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("target", "a" * (MAX_TARGET_CHARS + 1)),
        ("pathspec", "a" * (MAX_TARGET_CHARS + 1)),
        ("commit", "a" * 39),
        ("sha256", "e" * 63),
    ],
)
def test_request_fields_have_the_bounds_the_journal_assumes(field, value) -> None:
    with pytest.raises(ValidationError):
        _entry(**{field: value})


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("target", "a" * (MAX_TARGET_CHARS + 1)),
        ("sha256", "e" * 63),
        ("lines", MAX_INLINE_LINES + 1),
    ],
)
def test_inline_fields_have_the_bounds_the_journal_assumes(field, value) -> None:
    fields = {"target": "a.md", "sha256": "e" * 64, "lines": 1, field: value}
    with pytest.raises(ValidationError):
        InlineInput(**fields)


def test_surface_commits_have_the_fixed_width_the_journal_assumes() -> None:
    with pytest.raises(ValidationError):
        _exposure(commit="a" * 39)
    with pytest.raises(ValidationError):
        EvidenceSession(
            session_id="run-x",
            journal_path="journal.jsonl",
            commit="a" * 39,
            budget=0,
            surface_policy=POLICY,
            instrument=INSTRUMENT,
        )


def test_replay_protocol_version_is_two() -> None:
    """Pinned as a VALUE, not just a symbol.

    Every reference in the toolkit imports the name, so a drifting number would break nothing
    and be noticed by no one. Serving changed in plan 4a -- bounds, two environment pins -- and
    §5.2 makes that a bump. Changing this constant means deciding that prior exposures no longer
    replay; that decision belongs in a diff someone reviews.
    """
    from science_model.evidence_broker import REPLAY_PROTOCOL_VERSION

    assert REPLAY_PROTOCOL_VERSION == 2


def test_served_bounds_are_derived_from_the_budget() -> None:
    """The per-run ceiling is the per-request one times the budget, not an independent number.

    Plan 3 derived MAX_JOURNAL_BYTES from model bounds so a run could not write a journal it
    could not read back. The same argument applies to `served/`: a run whose disk ceiling was
    chosen separately could accept a request it cannot store.
    """
    from science_model.evidence_broker import (
        MAX_BUDGET,
        MAX_RUN_SERVED_BYTES,
        MAX_SERVED_BYTES,
    )

    assert MAX_SERVED_BYTES == 1 << 20
    assert MAX_RUN_SERVED_BYTES == MAX_BUDGET * MAX_SERVED_BYTES

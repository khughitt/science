"""Project-authored kinds get a base-2.0 profile, and the mixin still pins the kind.

Base 2.0 constrains `kind` SYNTACTICALLY (a pattern), because an enum of ~50 core kinds would
have to be edited every time a kind is added -- mutating a versioned schema, which is the one
thing versioning exists to forbid. The entire safety argument for that widening is that each
mixin re-pins the kind with a `const`. Untested, that argument is a comment.
"""

from __future__ import annotations

import pytest

from science_model.entity_schema import (
    EntityValidationError,
    EntityValidator,
    default_profile_for_kind,
    parse_profile,
)
from science_model.entity_schema.profile import ProfileParseError


def test_hypothesis_derives_a_base_2_profile() -> None:
    assert (
        default_profile_for_kind("hypothesis").render()
        == "science-entity-base/2.0+hypothesis/1.0"
    )


def test_commons_kinds_stay_on_base_1() -> None:
    # Non-negotiable: 369 live commons records pin base 1.0. The base version is PER-KIND.
    assert default_profile_for_kind("dataset").render() == "science-entity-base/1.0+dataset/2.0"
    assert default_profile_for_kind("paper").render() == "science-entity-base/1.0+paper/2.0"


def test_unknown_mixin_still_rejected() -> None:
    with pytest.raises(ProfileParseError):
        parse_profile("science-entity-base/2.0+nonsense/1.0")


# An OTHERWISE-VALID external dataset. Every field here is load-bearing, and the first draft of
# this test had none of them: `dataset:x` fails the dataset mixin's own id pattern (min 2 chars),
# `tier: raw` is not in the tier enum, `origin: external` REQUIRES `access`, and the dataset
# mixin REQUIRES `datapackage`. That payload failed for five reasons, only one of which was the
# `const` -- so the test passed with the const DELETED. A test that cannot fail certifies nothing.
_VALID_DATASET = {
    "id": "dataset:example-cohort",
    "kind": "dataset",
    "title": "T",
    "created": "2026-07-13",
    "updated": "2026-07-13",
    "origin": "external",
    "tier": "use-now",
    "datapackage": "data/example-cohort/datapackage.json",
    "access": {"level": "public", "verified": True},
}
_BASE2_DATASET = parse_profile("science-entity-base/2.0+dataset/1.0")


def test_the_dataset_control_payload_is_otherwise_VALID() -> None:
    # THE CONTROL. It is the only thing that gives the next test its meaning: it proves the
    # payload's ONLY defect is the one the next test injects. Without it, the next test is
    # asserting that an invalid record is invalid.
    EntityValidator().validate_as(dict(_VALID_DATASET), _BASE2_DATASET)


def test_a_mixin_const_still_narrows_the_kind_under_base_2() -> None:
    # Base 2.0's `kind` is a PATTERN, so the base alone accepts any lowercase word -- `hypothesis`
    # included. The mixin's `const` is what re-pins it. Here that claim is executed.
    with pytest.raises(EntityValidationError) as exc:
        EntityValidator().validate_as(dict(_VALID_DATASET, kind="hypothesis"), _BASE2_DATASET)

    # Assert the REASON, not merely the failure. The error set must be exactly {kind}: if any
    # other field also failed, the payload is no longer a control and the const is untested again.
    failed = {
        (err.absolute_path[0] if err.absolute_path else "<root>") for err in exc.value.errors
    }
    assert failed == {"kind"}

"""`validate_persisted_base_shape` — necessary validation of durable source shape.

NOT sufficient entity-schema validation. It exists because writer containment (design §5.5) must
land before `proposition` and `evidence-line` have mixins, and a writer that persists source it
never checked is the defect the whole programme is about.
"""

from __future__ import annotations

import pytest

from science_model.entity_schema import EntityValidationError, EntityValidator


def _ok() -> dict:
    return {
        "id": "proposition:0001-x",
        "kind": "proposition",
        "title": "concept:a affects concept:b",
        "created": "2026-07-27",
        "updated": "2026-07-27",
    }


def test_a_well_formed_mapping_passes() -> None:
    EntityValidator().validate_persisted_base_shape(_ok())


def test_empty_title_is_refused() -> None:
    # THE case this exists for: base 2.0 declares title {"type": "string", "minLength": 1} and
    # requires it. 769 persisted records violate it today.
    payload = _ok() | {"title": ""}
    with pytest.raises(EntityValidationError, match="title"):
        EntityValidator().validate_persisted_base_shape(payload)


@pytest.mark.parametrize("missing", ["id", "kind", "title", "created", "updated"])
def test_each_base_required_field_is_enforced(missing: str) -> None:
    payload = _ok()
    del payload[missing]
    with pytest.raises(EntityValidationError, match=missing):
        EntityValidator().validate_persisted_base_shape(payload)


def test_an_invalid_date_is_refused() -> None:
    # Load-bearing, and silently defeated if `format_checker` is dropped: JSON Schema treats
    # `format` as an ANNOTATION unless a checker is supplied. Measured -- without it,
    # created="not-a-date" produces zero errors; with it, "'not-a-date' is not a 'date'".
    # Plan 2's finding migration rules `updated = created`, so date validity is not decorative.
    payload = _ok() | {"created": "not-a-date"}
    with pytest.raises(EntityValidationError, match="not a 'date'"):
        EntityValidator().validate_persisted_base_shape(payload)


def test_unknown_keys_are_ALLOWED() -> None:
    # The contract's stated limit. `unevaluatedProperties: false` is NOT applied: these kinds have
    # no mixin, so closing here would reject every field the kind legitimately carries. Shadow-key
    # refusal is piece 2's job, not this operation's.
    EntityValidator().validate_persisted_base_shape(_ok() | {"stance": "supports"})


def test_base_shape_admits_what_a_closed_kinds_composed_schema_refuses() -> None:
    # THE contrast the "necessary, NOT sufficient" claim rests on: one mapping that PASSES this
    # operation and FAILS full composed entity-schema validation. `hypothesis` is in
    # PROJECT_MIXIN_NAMES, so its composed schema sets `unevaluatedProperties: false` -- the
    # closure `proposition`/`evidence-line` do not have yet. The shadow key `stance` is
    # unevaluated by base 2.0 + hypothesis/1.0 alike, so it alone trips `validate_as` there; this
    # operation, checking base 2.0 only, has no closure to trip and admits it. That gap is
    # precisely why this operation is not a substitute for entity-schema validation.
    from science_model.entity_schema.profile import default_profile_for_kind

    payload = {
        "id": "hypothesis:0001-x",
        "kind": "hypothesis",
        "title": "concept:a affects concept:b",
        "created": "2026-07-27",
        "updated": "2026-07-27",
        "status": "draft",
        "stance": "supports",
    }
    EntityValidator().validate_persisted_base_shape(payload)
    with pytest.raises(EntityValidationError, match="stance"):
        EntityValidator().validate_as(payload, default_profile_for_kind("hypothesis"))


def test_it_does_not_weaken_validate_as() -> None:
    # `validate_as` must still refuse a base-only profile. If this ever passes, the separate
    # operation has been folded back into the sufficient one and the distinction is lost.
    from science_model.entity_schema.profile import ProfileComponent, ProfileString

    base_only = ProfileString(
        base=ProfileComponent(name="science-entity-base", version="2.0"), mixin=None, extensions=()
    )
    with pytest.raises(EntityValidationError, match="type mixin"):
        EntityValidator().validate_as(_ok(), base_only)

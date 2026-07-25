from __future__ import annotations

import dataclasses

import pytest

from science_tool.graph.belief import EvidenceUnit
from science_tool.graph.belief_basis import unit_key


def _u(stance: str = "supports", **kw) -> EvidenceUnit:
    base = dict(
        line_uri="x", stance=stance, strength="strong", independence="independent",
        independence_group="g", evidence_role="direct_test",
        evidence_type="empirical_data_evidence", dispute_scope=None,
        proxy_directness=None, has_measurement_model=False, source=None,
        observability_keys=(),
    )
    base.update(kw)
    return EvidenceUnit(**base)


def _distinct(value: object) -> object:
    """Return a value of compatible shape that differs from `value`."""
    if isinstance(value, bool):
        return not value
    if isinstance(value, float):
        return value + 1.0
    if isinstance(value, tuple):
        return (*value, "perturbed")
    if isinstance(value, str):
        return value + "-perturbed"
    return "perturbed"  # None, and anything else


def test_identical_units_share_a_key():
    assert unit_key(_u()) == unit_key(_u())


def test_differing_strength_changes_the_key():
    assert unit_key(_u(strength="strong")) != unit_key(_u(strength="weak"))


def test_every_field_value_affects_the_key():
    """Fail-closed: every field's VALUE must reach the key, not just its name.

    Checking that field names appear in the key would pass an implementation
    serializing {name: None} for every field. Perturbing each value in turn
    catches that, and stays valid if unit_key later returns a hash instead
    of a JSON string.
    """
    base = _u()
    for field in dataclasses.fields(EvidenceUnit):
        mutated = dataclasses.replace(base, **{field.name: _distinct(getattr(base, field.name))})
        assert unit_key(mutated) != unit_key(base), f"{field.name} does not affect the key"


def test_unserializable_value_raises_rather_than_coercing():
    """No `default=` fallback: an unrepresentable value must fail loudly at capture.

    A `default=str` would stringify this and could collapse two distinct objects
    into one key, silently weakening the basis.
    """
    unit = dataclasses.replace(_u(), source=object())
    with pytest.raises(TypeError):
        unit_key(unit)

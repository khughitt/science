from __future__ import annotations

from science_model.entities import EntityType
from science_model.identity import EntityClass
from science_model.profiles.core import CORE_PROFILE
from science_model.profiles.local import LOCAL_PROFILE
from science_model.profiles.schema import KindCategory

RESERVED = frozenset({"unknown"})
SOURCE_ONLY = frozenset({"model", "canonical_parameter", "parameter_binding"})

_ALL = [*CORE_PROFILE.entity_kinds, *LOCAL_PROFILE.entity_kinds]
_CATEGORY = {ek.name: ek.category for ek in _ALL}


def _authored_core() -> set[str]:
    return {ek.name for ek in _ALL if ek.category == KindCategory.AUTHORED_CORE}


def test_assertion1_authored_core_equals_enum_core_projection() -> None:
    enum_core_projection = {v.value for v in EntityType} - RESERVED - SOURCE_ONLY
    assert _authored_core() == enum_core_projection


def test_assertion2_every_enum_member_is_classified() -> None:
    unclassified = {v.value for v in EntityType if _CATEGORY.get(v.value) is None}
    assert unclassified == set(), f"unclassified EntityType members: {sorted(unclassified)}"


def test_assertion3_reserved_named_contract() -> None:
    assert _CATEGORY["unknown"] == KindCategory.RESERVED
    assert "unknown" not in _authored_core()


def test_assertion3_source_only_named_contracts() -> None:
    for name in SOURCE_ONLY:
        assert _CATEGORY[name] == KindCategory.SOURCE_ONLY, name
        assert name not in _authored_core()


def test_source_only_descriptors_carry_operational_class() -> None:
    for ek in LOCAL_PROFILE.entity_kinds:
        if ek.category == KindCategory.SOURCE_ONLY:
            assert ek.entity_class == EntityClass.OPERATIONAL, ek.name

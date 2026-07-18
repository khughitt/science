from __future__ import annotations

from science_model.profiles.core import CORE_PROFILE


def _spec_kind():
    return next(k for k in CORE_PROFILE.entity_kinds if k.name == "spec")


def test_spec_kind_is_import_ready() -> None:
    spec = _spec_kind()
    assert spec.home == "entities/specs"
    assert spec.strategy == "numeric"
    assert spec.default_status == "active"
    assert spec.statuses == ["draft", "active", "complete", "superseded", "retired", "archived"]

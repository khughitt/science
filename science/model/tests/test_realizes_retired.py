"""sci:realizes is retired (umbrella Spec 0, task:t087).

A workflow does not realize one method; each of its steps applies one.
Spec 1 adds sci:applies (workflow-step -> method) in its place.
"""

from science_model.profiles.core import CORE_PROFILE

_NAMES = {rk.name for rk in CORE_PROFILE.relation_kinds}
_PREDICATES = {rk.predicate for rk in CORE_PROFILE.relation_kinds}


def test_realizes_relation_kind_is_gone() -> None:
    assert "realizes" not in _NAMES
    assert "sci:realizes" not in _PREDICATES


def test_the_surviving_workflow_relations_are_untouched() -> None:
    assert {"contains", "executes", "feeds_into", "implements"} <= _NAMES

"""workflow-step is a definition, not an execution (umbrella Spec 0, task:t087)."""

from science_model.profiles.core import CORE_PROFILE

_STEP = next(ek for ek in CORE_PROFILE.entity_kinds if ek.name == "workflow-step")


def test_statuses_are_the_definition_lifecycle() -> None:
    assert list(_STEP.statuses) == ["active", "superseded", "retired"]


def test_default_status_is_active() -> None:
    assert _STEP.default_status == "active"


def test_no_execution_states_remain() -> None:
    assert not {"pending", "running", "complete", "failed"} & set(_STEP.statuses)


def test_description_does_not_claim_to_cover_runs() -> None:
    assert "run" not in _STEP.description.lower()

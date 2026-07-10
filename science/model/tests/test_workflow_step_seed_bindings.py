"""WorkflowStepEntity seed bindings (umbrella Spec 1, task:t079).

A binding names a SOURCE, never a value. Realized seed values belong to
Spec 2's RunFingerprint.step_seeds.
"""

import pytest
from pydantic import ValidationError

from science_model.entities import WorkflowStepEntity


def _step(**kwargs) -> WorkflowStepEntity:
    # project / ontology_terms / related / source_refs are REQUIRED on base
    # `Entity` (no defaults). Markdown fixtures get them from the loader's
    # `_fill_derived_defaults`; a direct constructor call must pass them.
    return WorkflowStepEntity(
        id="workflow-step:cluster",
        kind="workflow-step",
        title="Cluster",
        project="demo",
        ontology_terms=[],
        related=[],
        source_refs=[],
        content_preview="",
        file_path="entities/workflow-steps/cluster.md",
        **kwargs,
    )


def test_new_fields_default_to_empty() -> None:
    step = _step()
    assert step.method == ""
    assert step.seed_bindings == {}
    assert step.rationale == ""


def test_config_source_is_accepted() -> None:
    step = _step(method="method:leiden", seed_bindings={"random_state": "config.seed"})
    assert step.seed_bindings["random_state"] == "config.seed"


def test_dotted_config_key_is_accepted() -> None:
    assert _step(seed_bindings={"s": "config.cluster.random_state"}).seed_bindings["s"]


def test_literal_source_is_accepted() -> None:
    assert _step(seed_bindings={"random_state": "literal:42"}).seed_bindings["random_state"]


def test_negative_literal_is_accepted() -> None:
    assert _step(seed_bindings={"s": "literal:-1"}).seed_bindings["s"] == "literal:-1"


@pytest.mark.parametrize(
    "source",
    [
        "42",             # a bare value, not a source
        "literal:abc",    # not an int
        "literal:",       # empty
        "config.",        # empty key
        "config",         # no key
        "env.SEED",       # unsupported form
        "",               # empty
        "literal:42\n",   # `$` would accept this; `\Z` must not
        "config.seed\n",  # likewise
        " literal:42",    # leading whitespace
        "literal:42 ",    # trailing whitespace
    ],
)
def test_malformed_binding_source_is_rejected(source: str) -> None:
    # A malformed source is a syntax error, not an epistemic gap: fail early.
    with pytest.raises(ValidationError, match="binding source"):
        _step(seed_bindings={"random_state": source})


def test_empty_parameter_name_is_rejected() -> None:
    with pytest.raises(ValidationError, match="parameter name"):
        _step(seed_bindings={"": "literal:42"})


def test_rationale_round_trips() -> None:
    assert _step(rationale="GPU atomics").rationale == "GPU atomics"

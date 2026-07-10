"""MethodEntity stochasticity vocabulary (umbrella Spec 1, task:t079)."""

import pytest
from pydantic import ValidationError

from science_model.entities import MethodEntity, Stochasticity


def _method(**kwargs) -> MethodEntity:
    return MethodEntity(
        id="method:leiden",
        kind="method",
        title="Leiden clustering",
        project="demo",
        ontology_terms=[],
        related=[],
        source_refs=[],
        content_preview="",
        file_path="entities/methods/leiden.md",
        **kwargs,
    )


def test_stochasticity_members() -> None:
    assert Stochasticity.DETERMINISTIC == "deterministic"
    assert Stochasticity.SEEDABLE == "seedable"
    assert Stochasticity.NONDETERMINISTIC == "nondeterministic"


def test_stochasticity_defaults_to_none_meaning_unclassified() -> None:
    # Optional on the model, required at the point of use: an unclassified
    # method must parse, because 46 of 51 live `method` entities are glossary
    # terms and design documents that no workflow step will ever apply.
    assert _method().stochasticity is None
    assert _method().seed_params == []


def test_stochasticity_parses_from_frontmatter_string() -> None:
    assert _method(stochasticity="seedable").stochasticity is Stochasticity.SEEDABLE


def test_stochasticity_rejects_an_unknown_classification() -> None:
    with pytest.raises(ValidationError):
        _method(stochasticity="maybe")


def test_seedable_does_not_require_seed_params() -> None:
    # Deliberate: all four seedable methods in the live corpus describe their
    # stochastic step without naming its parameter. `method.seed-params-missing`
    # warns; the model does not refuse the record.
    method = _method(stochasticity="seedable")
    assert method.stochasticity is Stochasticity.SEEDABLE
    assert method.seed_params == []


def test_seed_params_round_trip() -> None:
    assert _method(seed_params=["random_state", "init_seed"]).seed_params == [
        "random_state",
        "init_seed",
    ]

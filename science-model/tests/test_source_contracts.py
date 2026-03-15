from science_model import AuthoredTargetedRelation, BindingSource, ModelSource, ParameterSource


def test_model_source_round_trip() -> None:
    source = ModelSource(
        canonical_id="model:navier-stokes",
        title="Navier-Stokes equations",
        profile="project_specific",
        source_path="knowledge/sources/project_specific/models.yaml",
        domain="fluid-dynamics",
        aliases=["NavierStokes"],
        source_refs=["paper:legatiuk2021"],
        related=["question:q01-model-granularity"],
        relations=[AuthoredTargetedRelation(predicate="sci:approximates", target="model:stokes")],
    )

    round_tripped = ModelSource.model_validate(source.model_dump())

    assert round_tripped == source


def test_parameter_source_defaults_optional_fields() -> None:
    source = ParameterSource(
        canonical_id="parameter:kinematic-viscosity",
        title="Kinematic viscosity",
        symbol="nu",
        profile="project_specific",
        source_path="knowledge/sources/project_specific/parameters.yaml",
    )

    assert source.related == []
    assert source.ontology_terms == []
    assert source.relations == []


def test_binding_source_round_trip() -> None:
    binding = BindingSource(
        model="model:navier-stokes",
        parameter="parameter:kinematic-viscosity",
        source_path="knowledge/sources/project_specific/bindings.yaml",
        symbol="nu",
        role="viscosity",
        confidence=1.0,
        match_tier="canonical",
        default_value=0.1,
        typical_range=[0.01, 1.0],
        source_refs=["paper:legatiuk2021"],
        notes="High-confidence canonical match.",
    )

    round_tripped = BindingSource.model_validate(binding.model_dump())

    assert round_tripped == binding

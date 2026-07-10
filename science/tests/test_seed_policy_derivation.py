import pytest

from science_model.entities import MethodEntity, Stochasticity, WorkflowStepEntity

from science_tool.seed_policy_derivation import SeedPolicyDerivationError, derive_seed_policy


def _method(slug, stochasticity, seed_params=()):
    return MethodEntity(
        id=f"method:{slug}", kind="method", title=slug,
        stochasticity=stochasticity, seed_params=list(seed_params),
        project="demo", ontology_terms=[], related=[], source_refs=[],
        content_preview="", file_path=f"entities/methods/{slug}.md",
    )


def _step(slug, method="", seed_bindings=None):
    return WorkflowStepEntity(
        id=f"workflow-step:{slug}", kind="workflow-step", title=slug,
        workflow="workflow:w", method=method, seed_bindings=seed_bindings or {},
        project="demo", ontology_terms=[], related=[], source_refs=[],
        content_preview="", file_path=f"entities/workflow-steps/{slug}.md",
    )


def _derive(steps, methods, config=None):
    return derive_seed_policy(
        workflow_id="workflow:w", steps=steps, method_for_step=methods,
        config=config or {}, config_path="results/w/r/config.yaml",
    )


def test_zero_steps_fails_closed():
    with pytest.raises(SeedPolicyDerivationError, match="Declare at least one step"):
        _derive([], {})


def test_methodless_step_fails_closed():
    s = _step("a")
    with pytest.raises(SeedPolicyDerivationError, match="declares no method"):
        _derive([s], {})


def test_unresolved_method_fails_closed():
    s = _step("a", method="method:nope")
    with pytest.raises(SeedPolicyDerivationError, match="does not resolve"):
        _derive([s], {})          # absent from method_for_step


def test_unclassified_method_fails_closed():
    s = _step("a", method="method:m")
    with pytest.raises(SeedPolicyDerivationError, match="has no stochasticity"):
        _derive([s], {s.id: _method("m", None)})


def test_all_deterministic_derives_deterministic_with_no_seeds():
    s = _step("a", method="method:m")
    policy, seeds = _derive([s], {s.id: _method("m", Stochasticity.DETERMINISTIC)})
    assert (policy.kind, policy.rationale, seeds) == ("deterministic", None, {})


def test_binding_on_a_deterministic_method_contributes_no_seed():
    # validate already WARNs on this; a seed that controls nothing is not a seed,
    # and recording it would break `deterministic => empty step_seeds`.
    s = _step("a", method="method:m", seed_bindings={"random_state": "literal:1"})
    policy, seeds = _derive([s], {s.id: _method("m", Stochasticity.DETERMINISTIC)})
    assert (policy.kind, seeds) == ("deterministic", {})


def test_seedable_fully_bound_derives_seeded():
    s = _step("a", method="method:m", seed_bindings={"random_state": "literal:42"})
    policy, seeds = _derive([s], {s.id: _method("m", Stochasticity.SEEDABLE, ["random_state"])})
    assert policy.kind == "seeded" and policy.rationale is None
    assert seeds == {"workflow-step:a": {"random_state": 42}}


def test_seedable_unbound_param_derives_stochastic_unseeded():
    s = _step("a", method="method:m")
    policy, _ = _derive([s], {s.id: _method("m", Stochasticity.SEEDABLE, ["random_state"])})
    assert policy.kind == "stochastic-unseeded"
    assert "'random_state' unbound" in policy.rationale


def test_seedable_with_no_seed_params_derives_stochastic_unseeded():
    # `method.seed-params-missing` is warn-only, so this state is reachable. Without
    # the `paramless` term it would derive `seeded` vacuously with empty step_seeds
    # and crash RunFingerprint's invariant.
    s = _step("a", method="method:m")
    policy, seeds = _derive([s], {s.id: _method("m", Stochasticity.SEEDABLE)})
    assert policy.kind == "stochastic-unseeded"
    assert "declares no seed_params" in policy.rationale
    assert seeds == {}


def test_nondeterministic_derives_stochastic_unseeded_but_keeps_its_seeds():
    # A nondeterministic method MAY declare and bind seed_params (Spec 1 corollary):
    # `nondeterministic` means "not fully seed-controlled", not "cannot be seeded".
    s = _step("a", method="method:m", seed_bindings={"random_state": "literal:7"})
    policy, seeds = _derive([s], {s.id: _method("m", Stochasticity.NONDETERMINISTIC, ["random_state"])})
    assert policy.kind == "stochastic-unseeded"
    assert "which is nondeterministic" in policy.rationale
    assert seeds == {"workflow-step:a": {"random_state": 7}}


def test_two_steps_seed_the_same_param_differently():
    a = _step("a", method="method:m", seed_bindings={"random_state": "literal:1"})
    b = _step("b", method="method:m", seed_bindings={"random_state": "literal:2"})
    m = _method("m", Stochasticity.SEEDABLE, ["random_state"])
    policy, seeds = _derive([a, b], {a.id: m, b.id: m})
    assert policy.kind == "seeded"
    assert seeds == {"workflow-step:a": {"random_state": 1}, "workflow-step:b": {"random_state": 2}}


def test_config_binding_is_realized_from_the_snapshot():
    s = _step("a", method="method:m", seed_bindings={"random_state": "config.cluster.seed"})
    m = _method("m", Stochasticity.SEEDABLE, ["random_state"])
    policy, seeds = _derive([s], {s.id: m}, config={"cluster": {"seed": 99}})
    assert seeds == {"workflow-step:a": {"random_state": 99}}


def test_missing_config_key_fails_closed():
    s = _step("a", method="method:m", seed_bindings={"random_state": "config.absent"})
    m = _method("m", Stochasticity.SEEDABLE, ["random_state"])
    with pytest.raises(SeedPolicyDerivationError, match="has no key 'absent'"):
        _derive([s], {s.id: m}, config={})


def test_non_int_config_value_fails_closed():
    s = _step("a", method="method:m", seed_bindings={"random_state": "config.seed"})
    m = _method("m", Stochasticity.SEEDABLE, ["random_state"])
    with pytest.raises(SeedPolicyDerivationError, match="is not an integer"):
        _derive([s], {s.id: m}, config={"seed": "42"})


def test_bool_config_value_is_not_an_integer():
    # `bool` is an `int` subclass in Python; `isinstance(True, int)` is True.
    s = _step("a", method="method:m", seed_bindings={"random_state": "config.seed"})
    m = _method("m", Stochasticity.SEEDABLE, ["random_state"])
    with pytest.raises(SeedPolicyDerivationError, match="is not an integer"):
        _derive([s], {s.id: m}, config={"seed": True})


def test_binding_to_a_param_the_method_does_not_declare_is_ignored():
    # Spec 1's `seed-binding-unknown-param` WARNs on this; step_seeds records only
    # parameters the method actually declares.
    s = _step("a", method="method:m", seed_bindings={"random_state": "literal:1", "typo": "literal:2"})
    m = _method("m", Stochasticity.SEEDABLE, ["random_state"])
    _, seeds = _derive([s], {s.id: m})
    assert seeds == {"workflow-step:a": {"random_state": 1}}


def test_rationale_is_stable_across_step_order():
    a = _step("a", method="method:ma")
    b = _step("b", method="method:mb")
    ma, mb = _method("ma", Stochasticity.NONDETERMINISTIC), _method("mb", Stochasticity.NONDETERMINISTIC)
    p1, _ = _derive([a, b], {a.id: ma, b.id: mb})
    p2, _ = _derive([b, a], {a.id: ma, b.id: mb})
    assert p1.rationale == p2.rationale


def test_mixed_workflow_derives_stochastic_unseeded_and_records_the_seeded_step():
    a = _step("a", method="method:seedable", seed_bindings={"random_state": "literal:1"})
    b = _step("b", method="method:nondet")
    policy, seeds = _derive(
        [a, b],
        {a.id: _method("seedable", Stochasticity.SEEDABLE, ["random_state"]),
         b.id: _method("nondet", Stochasticity.NONDETERMINISTIC)},
    )
    assert policy.kind == "stochastic-unseeded"
    assert seeds == {"workflow-step:a": {"random_state": 1}}


def test_deterministic_method_declaring_seed_params_still_contributes_no_seed():
    # Spec 1 permits a deterministic method to declare seed_params, so the
    # `param in method.seed_params` filter does NOT cover this case -- only the
    # explicit deterministic skip does. Without that skip this derives
    # `deterministic` with a NON-empty step_seeds, which RunFingerprint rejects.
    # `test_binding_on_a_deterministic_method_contributes_no_seed` passes either
    # way, because its method declares no seed_params.
    s = _step("a", method="method:m", seed_bindings={"random_state": "literal:1"})
    policy, seeds = _derive([s], {s.id: _method("m", Stochasticity.DETERMINISTIC, ["random_state"])})
    assert (policy.kind, seeds) == ("deterministic", {})

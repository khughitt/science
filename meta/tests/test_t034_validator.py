import pytest

from t034_validator import (
    Store,
    detect_cycle,
    effective_codes,
    validate_causal_graph,
    validate_mr_graph_model,
    validate_payload,
    validate_strengthen_cee,
    validate_v13_authoring,
)


def _rules(issues):
    return {issue.rule for issue in issues if issue.severity == "error"}


def _mr_base_payload(**core_overrides):
    payload = {
        "core": {
            "extensions": ["mr-graph-model", "causal-graph", "statistical-uncertainty"],
            "validation_role": "prioritize-attention",
            "reason_codes": [],
        },
        "extension/mr-graph-model": {
            "exposure_set": ["var:exposure-1"],
            "outcome_set": ["var:outcome-1"],
            "instrument_set": ["snp:rs1"],
            "instrument_validity_assumptions": ["relevance", "exclusion"],
            "pleiotropy_model": "mr-egger",
            "direction_constraint": "bidirectional-search",
            "graph_object_type": "graph-posterior",
            "summary_statistic_provenance": "dataset:gwas-1",
        },
    }
    payload["core"].update(core_overrides)
    return payload


def _payload(extensions, *, validation_role="record-only", reason_codes=None, input_artifact_refs=None, exts=None):
    payload = {
        "core": {
            "extensions": list(extensions),
            "validation_role": validation_role,
            "reason_codes": list(reason_codes or []),
            "input_artifact_refs": list(input_artifact_refs or []),
        },
    }
    for key, value in (exts or {}).items():
        payload[f"extension/{key.replace('_', '-')}"] = value
    return payload


def _store_with(*items):
    store = Store()
    for payload_id, payload in items:
        store.add(payload_id, payload)
    return store


def _production_mr_graph_payload(**core_overrides):
    payload = _mr_base_payload(**core_overrides)
    payload["extension/causal-graph"] = {"graph_object_type": "graph-posterior", "edges": []}
    payload["extension/statistical-uncertainty"] = {}
    return payload


def test_validate_payload_accepts_valid_mr_graph_model_payload():
    store = _store_with(("mra1", _production_mr_graph_payload()))

    assert validate_payload(store, "mra1") == []


def test_validate_payload_rejects_handwritten_auto_injected_reason_codes():
    payload = _production_mr_graph_payload(reason_codes=["instrument-assumption-risk"])
    store = _store_with(("mra1", payload))

    assert _rules(validate_payload(store, "mra1")) == {"v1.3-auto-inject"}


def test_validate_payload_rejects_extension_section_mismatches():
    payload = {
        "core": {
            "extensions": ["mr-graph-model", "causal-graph"],
            "validation_role": "prioritize-attention",
            "reason_codes": [],
        },
        "extension/mr-graph-model": {},
    }
    store = _store_with(("mra1", payload))

    assert "core-extensions-shape" in _rules(validate_payload(store, "mra1"))


def test_validate_payload_accepts_two_stage_mr_strengthen_belief_after_retirement():
    mra1 = _production_mr_graph_payload(reason_codes=["pleiotropy-untested"])
    mra1["extension/mr-graph-model"]["pleiotropy_model"] = "not-modelled"
    id1 = _payload(
        ["causal-identification"],
        input_artifact_refs=["mra1"],
        exts={"causal_identification": {"identification_status": "identified"}},
    )
    cee1 = _payload(
        ["causal-effect-estimate", "mr-analysis", "statistical-uncertainty"],
        validation_role="strengthen-belief",
        input_artifact_refs=["id1"],
        exts={
            "causal_effect_estimate": {
                "identification_payload_ref": "id1",
                "estimator_diagnostics": {"converged": True},
            },
            "mr_analysis": {
                "mr_graph_payload_ref": "mra1",
                "pleiotropy_handling": "mr-egger-intercept",
            },
            "statistical_uncertainty": {},
        },
    )
    store = _store_with(("mra1", mra1), ("id1", id1), ("cee1", cee1))

    assert validate_payload(store, "cee1") == []


def _causal_graph_cases():
    yield pytest.param(
        {
            "core": {"extensions": ["causal-discovery-run", "causal-graph"]},
            "extension/causal-graph": {
                "graph_object_type": "CPDAG",
                "edges": [
                    {
                        "a": "var:vaccination",
                        "b": "var:severe-illness",
                        "epistemic_role": "data_discovered_adjacency",
                        "oriented": False,
                    },
                    {
                        "a": "var:age",
                        "b": "var:severe-illness",
                        "epistemic_role": "assumed_background_edge",
                        "oriented": True,
                    },
                ],
            },
        },
        set(),
        id="valid-cpdag",
    )
    yield pytest.param(
        {
            "core": {"extensions": ["causal-discovery-run", "causal-graph"]},
            "extension/causal-graph": {
                "graph_object_type": "CPDAG",
                "edges": [{"a": "var:a", "b": "var:b", "epistemic_role": "mechanistic_hypothesis"}],
            },
        },
        {"rule-cg-3-mech"},
        id="cpdag-with-mechanistic-edge",
    )
    yield pytest.param(
        {
            "core": {"extensions": ["mechanistic-hypothesis-bundle", "causal-graph"]},
            "extension/causal-graph": {
                "graph_object_type": "candidate-graph",
                "edges": [{"a": "protein:EGFR", "b": "protein:ERK", "epistemic_role": "mechanistic_hypothesis"}],
            },
        },
        set(),
        id="mhb-with-mechanistic-edge",
    )
    yield pytest.param(
        {
            "core": {"extensions": ["causal-discovery-run", "causal-graph"]},
            "extension/causal-graph": {
                "graph_object_type": "candidate-graph",
                "edges": [{"a": "var:a", "b": "var:b", "epistemic_role": "mechanistic_hypothesis"}],
            },
        },
        {"rule-cg-3-mech"},
        id="discovery-run-with-mechanistic-edge",
    )
    yield pytest.param(
        {
            "core": {"extensions": ["causal-discovery-run", "causal-graph"]},
            "extension/causal-graph": {
                "graph_object_type": "CPDAG",
                "edges": [{"a": "var:x", "b": "var:y", "epistemic_role": "identified_causal_effect"}],
            },
        },
        {"rule-cg-3"},
        id="cpdag-with-identified-edge",
    )
    yield pytest.param(
        {
            "core": {"extensions": ["mechanistic-hypothesis-bundle", "causal-graph"]},
            "extension/causal-graph": {"graph_object_type": "mechanistic", "edges": []},
        },
        {"rule-cg-1"},
        id="unknown-graph-object-type",
    )
    yield pytest.param(
        {
            "core": {"extensions": ["causal-discovery-run", "causal-graph"]},
            "extension/causal-graph": {"edges": []},
        },
        {"rule-cg-1"},
        id="missing-graph-object-type",
    )
    yield pytest.param(
        {
            "core": {
                "extensions": ["mr-graph-model", "causal-graph", "statistical-uncertainty"],
                "reason_codes": ["instrument-assumption-risk", "extracted-from-summary-only"],
            },
            "extension/causal-graph": {"graph_object_type": "graph-posterior", "edges": []},
        },
        set(),
        id="graph-posterior-empty-edges",
    )
    yield pytest.param(
        {
            "core": {"extensions": ["graph-diagnostic"]},
            "extension/graph-diagnostic": {"diagnostic_kind": "self-compatibility", "result": "correlative"},
        },
        set(),
        id="no-causal-graph-extension",
    )
    yield pytest.param(
        {
            "core": {
                "extensions": ["mechanistic-hypothesis-bundle", "causal-graph"],
                "reason_codes": [
                    "mechanism-hypothesis-only",
                    "prior-network-dependent",
                    "extracted-from-summary-only",
                ],
            },
            "extension/causal-graph": {
                "graph_object_type": "candidate-graph",
                "edges": [
                    {"a": "protein:EGFR", "b": "protein:ERK", "epistemic_role": "mechanistic_hypothesis"},
                    {
                        "a": "metabolite:succinate",
                        "b": "protein:HIF1A",
                        "epistemic_role": "mechanistic_hypothesis",
                    },
                ],
            },
        },
        set(),
        id="dugourd-adapted",
    )


@pytest.mark.parametrize(("payload", "expected_rules"), list(_causal_graph_cases()))
def test_causal_graph_prototype_cases(payload, expected_rules):
    assert _rules(validate_causal_graph("payload-1", payload)) == expected_rules


def _mr_graph_model_cases():
    yield pytest.param(_mr_base_payload(), set(), id="minimal-valid")

    payload = _mr_base_payload(validation_role="strengthen-belief")
    yield pytest.param(payload, {"mr-2"}, id="strengthen-forbidden")

    payload = _mr_base_payload(validation_role="gate-update")
    yield pytest.param(payload, {"mr-2"}, id="gate-update-forbidden")

    payload = _mr_base_payload(validation_role="quality-record-only")
    yield pytest.param(payload, {"mr-2"}, id="quality-record-forbidden")

    payload = _mr_base_payload(validation_role="record-only")
    yield pytest.param(payload, set(), id="record-only-permitted")

    payload = _mr_base_payload()
    payload["core"]["extensions"] = ["mr-graph-model", "causal-graph"]
    yield pytest.param(payload, {"mr-3"}, id="missing-co-required-extension")

    payload = _mr_base_payload()
    del payload["extension/mr-graph-model"]["instrument_set"]
    yield pytest.param(payload, {"mr-5"}, id="missing-instrument-set-no-summary-gate")

    payload = _mr_base_payload()
    del payload["extension/mr-graph-model"]["instrument_set"]
    payload["core"]["reason_codes"] = ["extracted-from-summary-only"]
    yield pytest.param(payload, set(), id="missing-instrument-set-with-summary-gate")

    payload = _mr_base_payload()
    del payload["extension/mr-graph-model"]["summary_statistic_provenance"]
    payload["core"]["reason_codes"] = ["extracted-from-summary-only"]
    yield pytest.param(payload, set(), id="missing-provenance-with-summary-gate")

    payload = _mr_base_payload()
    del payload["extension/mr-graph-model"]["summary_statistic_provenance"]
    yield pytest.param(payload, {"mr-5"}, id="missing-provenance-no-summary-gate")

    payload = _mr_base_payload()
    del payload["extension/mr-graph-model"]["exposure_set"]
    payload["core"]["reason_codes"] = ["extracted-from-summary-only"]
    yield pytest.param(payload, {"mr-4"}, id="always-required-missing-with-gate")

    payload = _mr_base_payload()
    payload["extension/mr-graph-model"]["pleiotropy_model"] = "none-assumed"
    yield pytest.param(payload, {"mr-7"}, id="pleiotropy-blocking-code-missing")

    payload = _mr_base_payload()
    payload["extension/mr-graph-model"]["pleiotropy_model"] = "not-modelled"
    payload["core"]["reason_codes"] = ["pleiotropy-untested"]
    yield pytest.param(payload, set(), id="pleiotropy-blocking-code-correct")

    payload = _mr_base_payload()
    payload["core"]["reason_codes"] = ["pleiotropy-untested"]
    yield pytest.param(payload, {"mr-7"}, id="pleiotropy-untested-overdeclared")

    payload = _mr_base_payload()
    payload["extension/mr-graph-model"]["pleiotropy_model"] = "unspecified"
    payload["core"]["reason_codes"] = ["pleiotropy-unspecified", "extracted-from-summary-only"]
    yield pytest.param(payload, set(), id="pleiotropy-unspecified-correct")

    payload = _mr_base_payload()
    payload["extension/mr-graph-model"]["pleiotropy_model"] = "unspecified"
    yield pytest.param(payload, {"mr-8"}, id="pleiotropy-unspecified-code-missing")

    payload = _mr_base_payload()
    payload["core"]["reason_codes"] = ["pleiotropy-unspecified"]
    yield pytest.param(payload, {"mr-8"}, id="pleiotropy-unspecified-overdeclared")

    payload = _mr_base_payload()
    payload["extension/mr-graph-model"]["direction_constraint"] = "exposures-to-outcomes-only"
    yield pytest.param(payload, {"mr-9"}, id="reverse-causation-required")

    payload = _mr_base_payload()
    payload["extension/mr-graph-model"]["direction_constraint"] = "exposures-to-outcomes-only"
    payload["extension/mr-graph-model"]["instrument_validity_assumptions"] = [
        "relevance",
        "exclusion",
        "direction-inherent-from-iv-class",
    ]
    yield pytest.param(payload, set(), id="reverse-causation-carve-out")

    payload = _mr_base_payload()
    payload["core"]["reason_codes"] = ["reverse-causation-assumed"]
    yield pytest.param(payload, {"mr-9"}, id="reverse-causation-overdeclared")

    payload = _mr_base_payload()
    payload["core"]["reason_codes"] = ["instrument-assumption-risk"]
    yield pytest.param(payload, set(), id="instrument-assumption-risk-handwritten")

    payload = _mr_base_payload()
    payload["extension/mr-graph-model"]["graph_object_type"] = "ADMG"
    yield pytest.param(payload, {"mr-1"}, id="graph-object-type-out-of-slice")

    payload = {
        "core": {
            "extensions": ["causal-discovery-run", "causal-graph"],
            "validation_role": "prioritize-attention",
            "reason_codes": [],
        },
    }
    yield pytest.param(payload, set(), id="no-extension-loaded")

    payload = {
        "core": {
            "extensions": ["mr-graph-model", "causal-graph", "statistical-uncertainty"],
            "validation_role": "prioritize-attention",
            "reason_codes": ["pleiotropy-unspecified", "extracted-from-summary-only"],
        },
        "extension/mr-graph-model": {
            "exposure_set": ["var:lipid-traits"],
            "outcome_set": ["var:cardiovascular-outcomes"],
            "instrument_validity_assumptions": ["relevance", "direction-inherent-from-iv-class"],
            "pleiotropy_model": "unspecified",
            "direction_constraint": "exposures-to-outcomes-only",
            "graph_object_type": "graph-posterior",
        },
    }
    yield pytest.param(payload, set(), id="zuber-pilot-adapted")

    payload = {
        "core": {
            "extensions": ["mr-graph-model", "causal-graph", "statistical-uncertainty"],
            "validation_role": "strengthen-belief",
            "reason_codes": ["pleiotropy-unspecified", "extracted-from-summary-only"],
        },
        "extension/mr-graph-model": {
            "exposure_set": ["var:lipid-traits"],
            "outcome_set": ["var:cardiovascular-outcomes"],
            "instrument_validity_assumptions": ["relevance", "direction-inherent-from-iv-class"],
            "pleiotropy_model": "unspecified",
            "direction_constraint": "exposures-to-outcomes-only",
            "graph_object_type": "graph-posterior",
        },
    }
    yield pytest.param(payload, {"mr-2"}, id="zuber-pilot-strengthen-attempt")


@pytest.mark.parametrize(("payload", "expected_rules"), list(_mr_graph_model_cases()))
def test_mr_graph_model_prototype_cases(payload, expected_rules):
    assert _rules(validate_mr_graph_model("payload-1", payload)) == expected_rules


def test_effective_codes_auto_injects_extension_codes():
    store = Store()
    store.add("p1", _payload(["mr-graph-model", "causal-graph", "statistical-uncertainty"]))

    assert effective_codes(store, "p1") == {"instrument-assumption-risk"}


def test_effective_codes_propagates_only_blocking_codes():
    store = Store()
    store.add("disc1", _payload(["causal-discovery-run", "causal-graph"], reason_codes=["causal-sufficiency-assumption"]))
    store.add(
        "id1",
        _payload(
            ["causal-identification"],
            input_artifact_refs=["disc1"],
            exts={"causal_identification": {"identification_status": "pending"}},
        ),
    )

    codes = effective_codes(store, "id1")

    assert "identification-missing" in codes
    assert "causal-sufficiency-assumption" not in codes


def test_effective_codes_retires_identification_missing_when_identified():
    store = Store()
    store.add("disc1", _payload(["causal-discovery-run", "causal-graph"]))
    store.add(
        "id1",
        _payload(
            ["causal-identification"],
            input_artifact_refs=["disc1"],
            exts={"causal_identification": {"identification_status": "identified"}},
        ),
    )

    assert "identification-missing" not in effective_codes(store, "id1")


def test_effective_codes_retires_pleiotropy_when_handled():
    store = Store()
    store.add(
        "mra1",
        _payload(
            ["mr-graph-model", "causal-graph", "statistical-uncertainty"],
            reason_codes=["pleiotropy-untested"],
        ),
    )
    store.add(
        "cee1",
        _payload(
            ["causal-effect-estimate", "mr-analysis", "statistical-uncertainty"],
            input_artifact_refs=["mra1"],
            exts={"mr_analysis": {"pleiotropy_handling": "mr-egger-intercept"}},
        ),
    )

    assert "pleiotropy-untested" not in effective_codes(store, "cee1")


def test_effective_codes_cycle_halts_and_reports_cycle():
    store = Store()
    store.add("a", _payload(["causal-discovery-run", "causal-graph"], input_artifact_refs=["b"]))
    store.add("b", _payload(["causal-identification"], input_artifact_refs=["a"]))

    assert isinstance(effective_codes(store, "a"), set)
    assert detect_cycle(store, "a") is not None


def test_v13_authoring_allows_conditional_reason_codes():
    payload = _payload(
        ["mr-graph-model", "causal-graph", "statistical-uncertainty"],
        reason_codes=["reverse-causation-assumed"],
    )

    assert validate_v13_authoring("p1", payload) == []


def test_v13_authoring_rejects_handwritten_auto_injected_codes():
    payload = _payload(
        ["mr-graph-model", "causal-graph", "statistical-uncertainty"],
        reason_codes=["instrument-assumption-risk", "reverse-causation-assumed"],
    )

    assert _rules(validate_v13_authoring("p1", payload)) == {"v1.3-auto-inject"}


def test_strengthen_belief_passes_with_identified_upstream_no_forbidden_codes_and_diagnostics():
    store = Store()
    store.add("disc1", _payload(["causal-discovery-run", "causal-graph"]))
    store.add(
        "id1",
        _payload(
            ["causal-identification"],
            input_artifact_refs=["disc1"],
            exts={"causal_identification": {"identification_status": "identified"}},
        ),
    )
    store.add(
        "cee1",
        _payload(
            ["causal-effect-estimate", "statistical-uncertainty"],
            validation_role="strengthen-belief",
            input_artifact_refs=["id1"],
            exts={
                "causal_effect_estimate": {
                    "identification_payload_ref": "id1",
                    "estimator_diagnostics": {"converged": True},
                }
            },
        ),
    )

    assert validate_strengthen_cee(store, "cee1") == []


def test_strengthen_belief_rejects_pending_identification_and_propagated_blocking_code():
    store = Store()
    store.add("disc1", _payload(["causal-discovery-run", "causal-graph"]))
    store.add(
        "id1",
        _payload(
            ["causal-identification"],
            input_artifact_refs=["disc1"],
            exts={"causal_identification": {"identification_status": "pending"}},
        ),
    )
    store.add(
        "cee1",
        _payload(
            ["causal-effect-estimate", "statistical-uncertainty"],
            validation_role="strengthen-belief",
            input_artifact_refs=["id1"],
            exts={
                "causal_effect_estimate": {
                    "identification_payload_ref": "id1",
                    "estimator_diagnostics": {"converged": True},
                }
            },
        ),
    )

    assert _rules(validate_strengthen_cee(store, "cee1")) == {"cee-strengthen-a", "cee-strengthen-b"}


def test_strengthen_belief_rejects_unretired_mr_analysis_instrument_assumption_risk():
    store = Store()
    store.add("disc1", _payload(["causal-discovery-run", "causal-graph"]))
    store.add(
        "id1",
        _payload(
            ["causal-identification"],
            input_artifact_refs=["disc1"],
            exts={"causal_identification": {"identification_status": "identified"}},
        ),
    )
    store.add(
        "cee1",
        _payload(
            ["causal-effect-estimate", "mr-analysis", "statistical-uncertainty"],
            validation_role="strengthen-belief",
            input_artifact_refs=["id1"],
            exts={
                "causal_effect_estimate": {
                    "identification_payload_ref": "id1",
                    "estimator_diagnostics": {"converged": True},
                },
                "mr_analysis": {"pleiotropy_handling": "unhandled"},
            },
        ),
    )

    assert _rules(validate_strengthen_cee(store, "cee1")) == {"cee-strengthen-b"}


def test_strengthen_belief_requires_estimator_diagnostics():
    store = Store()
    store.add("disc1", _payload(["causal-discovery-run", "causal-graph"]))
    store.add(
        "id1",
        _payload(
            ["causal-identification"],
            input_artifact_refs=["disc1"],
            exts={"causal_identification": {"identification_status": "identified"}},
        ),
    )
    store.add(
        "cee1",
        _payload(
            ["causal-effect-estimate", "statistical-uncertainty"],
            validation_role="strengthen-belief",
            input_artifact_refs=["id1"],
            exts={"causal_effect_estimate": {"identification_payload_ref": "id1"}},
        ),
    )

    assert _rules(validate_strengthen_cee(store, "cee1")) == {"cee-strengthen-c"}


def test_strengthen_belief_requires_resolved_identification_ref():
    store = Store()
    store.add(
        "cee1",
        _payload(
            ["causal-effect-estimate", "statistical-uncertainty"],
            validation_role="strengthen-belief",
            exts={
                "causal_effect_estimate": {
                    "identification_payload_ref": "id-does-not-exist",
                    "estimator_diagnostics": {"converged": True},
                }
            },
        ),
    )

    assert _rules(validate_strengthen_cee(store, "cee1")) == {"cee-strengthen-a"}


def test_strengthen_belief_rule_does_not_fire_for_record_only_payloads():
    store = Store()
    store.add(
        "cee1",
        _payload(
            ["causal-effect-estimate", "statistical-uncertainty"],
            validation_role="record-only",
            exts={"causal_effect_estimate": {"identification_payload_ref": "missing"}},
        ),
    )

    assert validate_strengthen_cee(store, "cee1") == []


def test_two_stage_mr_retires_instrument_assumption_risk_before_strengthen_belief_check():
    store = Store()
    store.add(
        "mra1",
        _payload(
            ["mr-graph-model", "causal-graph", "statistical-uncertainty"],
            validation_role="prioritize-attention",
            reason_codes=["pleiotropy-untested"],
            exts={
                "mr_graph_model": {
                    "instrument_validity_assumptions": ["relevance", "exclusion"],
                }
            },
        ),
    )
    store.add(
        "id1",
        _payload(
            ["causal-identification"],
            input_artifact_refs=["mra1"],
            exts={"causal_identification": {"identification_status": "identified"}},
        ),
    )
    store.add(
        "cee1",
        _payload(
            ["causal-effect-estimate", "mr-analysis", "statistical-uncertainty"],
            validation_role="strengthen-belief",
            input_artifact_refs=["id1"],
            exts={
                "causal_effect_estimate": {
                    "identification_payload_ref": "id1",
                    "estimator_diagnostics": {"converged": True},
                },
                "mr_analysis": {
                    "mr_graph_payload_ref": "mra1",
                    "pleiotropy_handling": "mr-egger-intercept",
                },
            },
        ),
    )

    assert _rules(validate_strengthen_cee(store, "cee1")) == set()

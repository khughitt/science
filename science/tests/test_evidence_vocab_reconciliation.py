from science_model.reasoning import EvidenceRole, EvidenceStrength, EvidenceType
from science_tool.graph.belief_weights import (
    DIAGNOSTIC_ROLES,
    EVIDENCE_ROLE_RANK,
    EVIDENCE_TYPE_RANK,
    STRENGTH_RANK,
    UNRANKED_EVIDENCE_TYPES,
    normalize_evidence_type,
)


def test_type_rank_reconciles_with_enum():
    assert set(EVIDENCE_TYPE_RANK) | UNRANKED_EVIDENCE_TYPES == set(EvidenceType)
    assert set(EVIDENCE_TYPE_RANK).isdisjoint(UNRANKED_EVIDENCE_TYPES)


def test_negative_result_is_unranked():
    assert EvidenceType.NEGATIVE_RESULT in UNRANKED_EVIDENCE_TYPES
    assert EvidenceType.NEGATIVE_RESULT not in EVIDENCE_TYPE_RANK


def test_role_rank_reconciles_excluding_diagnostic():
    assert set(EVIDENCE_ROLE_RANK) == set(EvidenceRole) - DIAGNOSTIC_ROLES
    assert DIAGNOSTIC_ROLES <= set(EvidenceRole)


def test_strength_rank_reconciles_with_enum():
    assert set(STRENGTH_RANK) == set(EvidenceStrength)


def test_normalize_evidence_type_parity():
    assert normalize_evidence_type("empirical_data_evidence") == "empirical_data"
    assert normalize_evidence_type("empirical_data") == "empirical_data"
    assert normalize_evidence_type("expert_judgment") == "expert_judgment"
    assert normalize_evidence_type("differential_expression") == "differential_expression"
    assert normalize_evidence_type(None) == ""
    assert normalize_evidence_type("") == ""


def test_rank_lookup_by_string_value_still_works():
    assert EVIDENCE_TYPE_RANK["empirical_data"] == 4
    assert EVIDENCE_ROLE_RANK["direct_test"] == 3
    assert STRENGTH_RANK["strong"] == 3


def test_is_authored_assertion_recognizes_both_expert_judgment_spellings():
    from science_tool.graph.belief import EvidenceUnit, is_authored_assertion

    def _u(et):
        return EvidenceUnit(
            line_uri="a", stance="supports", strength=None, independence="independent",
            independence_group=None, evidence_role=None, evidence_type=et,
            dispute_scope=None, proxy_directness=None, has_measurement_model=False,
            source=None, observability_keys=(),
        )
    assert is_authored_assertion(_u("expert_judgment"))
    assert is_authored_assertion(_u("expert_judgment_evidence"))
    assert not is_authored_assertion(_u("empirical_data"))

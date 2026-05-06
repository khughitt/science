from science_model.provenance import EvidenceIndependence, ProvenanceType


def test_provenance_type_values():
    assert ProvenanceType.MATHEMATICAL == "mathematical"
    assert ProvenanceType.EMPIRICAL == "empirical"
    assert ProvenanceType.EDITORIAL == "editorial"
    assert ProvenanceType.DERIVED == "derived"


def test_provenance_type_is_str():
    """ProvenanceType values can be used as plain strings."""
    assert isinstance(ProvenanceType.MATHEMATICAL, str)
    assert f"type is {ProvenanceType.EDITORIAL}" == "type is editorial"


def test_evidence_independence_values():
    assert EvidenceIndependence.INDEPENDENT == "independent"
    assert EvidenceIndependence.SHARED_SOURCE == "shared-source"
    assert EvidenceIndependence.CIRCULAR == "circular"


def test_evidence_independence_is_str():
    assert isinstance(EvidenceIndependence.INDEPENDENT, str)


def test_all_provenance_types():
    """Verify exactly 4 provenance types exist."""
    assert len(ProvenanceType) == 4


def test_all_independence_levels():
    """Verify exactly 3 independence levels exist."""
    assert len(EvidenceIndependence) == 3

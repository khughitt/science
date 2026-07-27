import pytest
from pydantic import ValidationError

from science_model.audit.evidence import LocationEvidence, TextEvidence
from science_model.audit.finding import AuditFinding, normalize_severity
from science_model.audit.subjects import EntitySubject


def _finding(**overrides):
    base = dict(
        rule_id="dataset.cached-field-drift",
        subject=EntitySubject(ref="dataset:gtex-v8"),
        severity="warn",
        qualifiers={"field": "year"},
        message="cached year 2019 differs from source 2020",
        evidence=[],
    )
    return AuditFinding(**{**base, **overrides})


def test_rule_id_is_a_string_on_the_wire():
    assert _finding().model_dump(mode="json")["rule_id"] == "dataset.cached-field-drift"


def test_severity_normalizes_warning_to_warn():
    assert normalize_severity("warning") == "warn"
    assert normalize_severity("warn") == "warn"
    assert _finding(severity="warning").severity == "warn"


def test_unknown_severity_is_refused():
    with pytest.raises(ValidationError):
        _finding(severity="critical")


def test_evidence_collection_bound_is_enforced():
    ok = [TextEvidence(text=str(i)) for i in range(100)]
    _finding(evidence=ok)
    with pytest.raises(ValidationError):
        _finding(evidence=ok + [TextEvidence(text="101")])


def test_evidence_round_trips_as_a_discriminated_union():
    finding = _finding(
        evidence=[LocationEvidence(path="a.py", line=3), TextEvidence(text="note")]
    )
    reloaded = AuditFinding.model_validate(finding.model_dump(mode="json"))
    assert reloaded == finding


def test_unknown_field_is_refused():
    with pytest.raises(ValidationError):
        _finding(rule="dataset.cached-field-drift")


def test_qualifiers_cannot_be_mutated_in_place():
    finding = _finding()
    with pytest.raises(TypeError):
        finding.qualifiers["field"] = "month"  # type: ignore[index]
    with pytest.raises(TypeError):
        del finding.qualifiers["field"]  # type: ignore[attr-defined]
    assert finding.qualifiers == {"field": "year"}


def test_a_qualifier_mapping_is_copied_not_aliased():
    source = {"field": "year"}
    finding = _finding(qualifiers=source)
    source["field"] = "month"
    assert finding.qualifiers["field"] == "year"


def test_nested_qualifier_arrays_are_copied_not_aliased():
    source = {
        "tags": ["stable", ["nested"]],
        "metadata": {"labels": ["kept"]},
    }
    finding = _finding(qualifiers=source)

    source["tags"][0] = "caller-mutated"
    source["tags"][1].append("caller-added")
    source["metadata"]["labels"].append("caller-added")
    source["metadata"]["caller-key"] = "caller-added"

    assert finding.model_dump(mode="json")["qualifiers"] == {
        "tags": ["stable", ["nested"]],
        "metadata": {"labels": ["kept"]},
    }


def test_nested_qualifier_arrays_cannot_be_mutated_through_a_finding():
    finding = _finding(
        qualifiers={
            "tags": ["stable", ["nested"]],
            "metadata": {"labels": ["kept"]},
        }
    )

    with pytest.raises(TypeError):
        finding.qualifiers["tags"][0] = "mutated"
    with pytest.raises(TypeError):
        finding.qualifiers["tags"][1][0] = "mutated"
    with pytest.raises(TypeError):
        finding.qualifiers["metadata"]["labels"][0] = "mutated"
    with pytest.raises(TypeError):
        finding.qualifiers["metadata"]["labels"] = ["mutated"]

    dumped = finding.model_dump(mode="json")["qualifiers"]
    assert dumped == {
        "tags": ["stable", ["nested"]],
        "metadata": {"labels": ["kept"]},
    }
    assert type(dumped["tags"]) is list
    assert type(dumped["tags"][1]) is list
    assert type(dumped["metadata"]["labels"]) is list


def test_an_omitted_qualifier_mapping_is_frozen_too():
    finding = _finding(qualifiers={})
    bare = AuditFinding(
        rule_id="dataset.cached-field-drift",
        subject=EntitySubject(ref="dataset:gtex-v8"),
        severity="warn",
        message="m",
    )
    assert bare.qualifiers == finding.qualifiers == {}
    with pytest.raises(TypeError):
        bare.qualifiers["sneak"] = 1  # type: ignore[index]


def test_qualifiers_serialize_as_a_plain_dict():
    dumped = _finding().model_dump(mode="json")["qualifiers"]
    assert type(dumped) is dict
    assert dumped == {"field": "year"}

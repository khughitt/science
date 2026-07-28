import pytest
from pydantic import ValidationError

from science_model.audit.evidence import LocationEvidence, Span, TextEvidence


def test_location_evidence_normalizes_path_and_refuses_traversal():
    assert LocationEvidence(path="./src/x.py").path == "src/x.py"
    with pytest.raises(ValidationError):
        LocationEvidence(path="../outside.py")


def test_location_evidence_refuses_nul_at_the_model_boundary():
    with pytest.raises(ValidationError, match="NUL"):
        LocationEvidence(path="src/a\0b.py")


def test_location_pointer_permits_positional_segments():
    # Unlike PathSubject.pointer: evidence is not identity-bearing.
    assert LocationEvidence(path="science.yaml", pointer="health.x[3]").pointer


def test_line_is_one_based():
    assert LocationEvidence(path="a.py", line=1).line == 1
    with pytest.raises(ValidationError):
        LocationEvidence(path="a.py", line=0)


def test_line_and_span_are_mutually_exclusive():
    with pytest.raises(ValidationError):
        LocationEvidence(path="a.py", line=3, span=Span(start_line=3, end_line=4))


def test_span_ends_are_inclusive_and_ordered():
    Span(start_line=3, end_line=3)
    with pytest.raises(ValidationError):
        Span(start_line=5, end_line=4)
    with pytest.raises(ValidationError):
        Span(start_line=0, end_line=1)


def test_span_columns_are_paired():
    Span(start_line=1, end_line=1, start_col=2, end_col=4)
    with pytest.raises(ValidationError):
        Span(start_line=1, end_line=1, start_col=2)
    with pytest.raises(ValidationError):
        Span(start_line=1, end_line=1, start_col=4, end_col=2)


def test_text_evidence_bounds():
    TextEvidence(text="x" * 4000)
    with pytest.raises(ValidationError):
        TextEvidence(text="x" * 4001)
    with pytest.raises(ValidationError):
        TextEvidence(text="ok", label="y" * 201)


def test_unknown_fields_are_refused_not_ignored():
    with pytest.raises(ValidationError):
        LocationEvidence(path="a.py", lien=3)
    with pytest.raises(ValidationError):
        TextEvidence(text="ok", labl="x")

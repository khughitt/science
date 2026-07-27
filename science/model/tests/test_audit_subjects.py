import pytest
from pydantic import ValidationError

from science_model.audit.subjects import (
    EntitySubject,
    IdentifierSubject,
    PathSubject,
    ProjectSubject,
    normalize_project_path,
)


def test_entity_subject_requires_prefixed_ref():
    assert EntitySubject(ref="dataset:gtex-v8").ref == "dataset:gtex-v8"
    with pytest.raises(ValidationError):
        EntitySubject(ref="gtex-v8")


def test_path_subject_normalizes_separators_and_strips_trailing_slash():
    assert PathSubject(path="entities/papers/").path == "entities/papers"
    assert PathSubject(path="./science.yaml").path == "science.yaml"


def test_path_subject_refuses_absolute_and_any_traversal_segment():
    for bad in (
        "/etc/passwd",
        "../outside.md",
        "entities/../../escape.md",
        # Refused, NOT collapsed to "b": a traversal segment is rejected outright, so
        # no path that mentions `..` is ever accepted on the strength of where it
        # happens to land.
        "a/../b",
        "a/b/..",
    ):
        with pytest.raises(ValidationError):
            PathSubject(path=bad)


def test_path_subject_pointer_forbids_positional_segments():
    PathSubject(path="science.yaml", pointer="health.accepted_validation")
    with pytest.raises(ValidationError):
        PathSubject(path="science.yaml", pointer="health.accepted_validation[3]")


def test_identifier_subject_lowercases_namespace_and_requires_value():
    subject = IdentifierSubject(namespace="Managed-Artifact", value="validate.sh")
    assert subject.namespace == "managed-artifact"
    with pytest.raises(ValidationError):
        IdentifierSubject(namespace="managed-artifact", value="")


def test_project_subject_carries_no_other_field():
    assert ProjectSubject().type == "project"
    with pytest.raises(ValidationError):
        ProjectSubject(ref="anything")


def test_normalize_project_path_is_idempotent():
    once = normalize_project_path("entities//papers/./x.md")
    assert once == "entities/papers/x.md"
    assert normalize_project_path(once) == once

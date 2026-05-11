# science/tests/test_annotation_skolem.py
"""Unit tests for science_tool.annotation.skolem."""
import pytest

from science_tool.annotation.skolem import skolem_iri


def test_target_iri() -> None:
    assert skolem_iri("a-7f3a", "target") == "a-7f3a/target"


def test_selector_iri() -> None:
    assert skolem_iri("a-7f3a", "selector") == "a-7f3a/target/selector"


def test_first_body_iri_omits_index() -> None:
    assert skolem_iri("a-7f3a", "body") == "a-7f3a/body"


def test_second_body_iri_appends_index() -> None:
    assert skolem_iri("a-7f3a", "body", index=2) == "a-7f3a/body/2"


def test_first_body_with_explicit_index_one_omits() -> None:
    assert skolem_iri("a-7f3a", "body", index=1) == "a-7f3a/body"


def test_unknown_role_raises() -> None:
    with pytest.raises(ValueError, match="unknown role"):
        skolem_iri("a-7f3a", "bogus")  # type: ignore[arg-type]


def test_index_invalid_for_target() -> None:
    with pytest.raises(ValueError, match="index"):
        skolem_iri("a-7f3a", "target", index=2)

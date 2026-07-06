"""Fail-fast validator tests for DAG reference entries."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from science_tool.dag.schema import RefEntry, SchemaError


def test_ref_entry_valid_task() -> None:
    ref = RefEntry.model_validate({"task": "t001", "description": "some task"})
    assert ref.description == "some task"


def test_ref_entry_valid_doi() -> None:
    ref = RefEntry.model_validate({"doi": "10.1000/xyz123", "description": "paper ref"})
    assert ref.description == "paper ref"


def test_ref_entry_doi_null_rejected() -> None:
    with pytest.raises((ValidationError, SchemaError), match="non-null kind tag"):
        RefEntry.model_validate({"doi": None, "description": "placeholder ref"})


def test_ref_entry_zero_kinds_raises() -> None:
    with pytest.raises((ValidationError, SchemaError)):
        RefEntry.model_validate({"author_year": "Smith 2024", "description": "missing kind"})


def test_ref_entry_two_kinds_raises() -> None:
    with pytest.raises((ValidationError, SchemaError)):
        RefEntry.model_validate({"task": "t001", "doi": "10.1/x", "description": "ambiguous ref"})


def test_ref_entry_author_year_not_a_kind() -> None:
    with pytest.raises((ValidationError, SchemaError)):
        RefEntry.model_validate({"author_year": "Smith 2024", "description": "no kind"})

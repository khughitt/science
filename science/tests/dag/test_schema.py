"""Fail-fast validator tests for dag/schema.py (v1 invariants)."""

from __future__ import annotations

import warnings
from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from science_tool.dag.schema import (
    EdgeRecord,
    EdgeStatus,
    EdgesYamlFile,
    Identification,
    PosteriorBlock,
    RefEntry,
    SchemaError,
)

# ---------------------------------------------------------------------------
# RefEntry — exactly one kind tag
# ---------------------------------------------------------------------------


def test_ref_entry_valid_task() -> None:
    ref = RefEntry.model_validate({"task": "t001", "description": "some task"})
    assert ref.description == "some task"


def test_ref_entry_valid_doi() -> None:
    ref = RefEntry.model_validate({"doi": "10.1000/xyz123", "description": "paper ref"})
    assert ref.description == "paper ref"


def test_ref_entry_doi_null_rejected() -> None:
    """doi: null is a dishonest citation — rejected by the tightened schema.
    Entries migrating from the legacy pattern must use a concrete paper: ref.
    """
    with pytest.raises((ValidationError, SchemaError), match="non-null kind tag"):
        RefEntry.model_validate({"doi": None, "description": "placeholder ref"})


def test_ref_entry_zero_kinds_raises() -> None:
    """Ref entry with no kind tag → SchemaError / ValidationError."""
    with pytest.raises((ValidationError, SchemaError)):
        RefEntry.model_validate({"author_year": "Smith 2024", "description": "missing kind"})


def test_ref_entry_two_kinds_raises() -> None:
    """Ref entry with two kind tags → SchemaError / ValidationError."""
    with pytest.raises((ValidationError, SchemaError)):
        RefEntry.model_validate({"task": "t001", "doi": "10.1/x", "description": "ambiguous ref"})


def test_ref_entry_author_year_not_a_kind() -> None:
    """author_year alone is not a kind tag."""
    with pytest.raises((ValidationError, SchemaError)):
        RefEntry.model_validate({"author_year": "Smith 2024", "description": "no kind"})


# ---------------------------------------------------------------------------
# PosteriorBlock — HDI requires beta
# ---------------------------------------------------------------------------


def test_posterior_block_valid_with_beta_and_hdi() -> None:
    pb = PosteriorBlock(beta=0.3, hdi_low=0.1, hdi_high=0.5)
    assert pb.beta == pytest.approx(0.3)


def test_posterior_block_valid_beta_only() -> None:
    pb = PosteriorBlock(beta=0.3)
    assert pb.beta == pytest.approx(0.3)


def test_posterior_block_valid_empty() -> None:
    pb = PosteriorBlock()
    assert pb.beta is None


def test_posterior_block_hdi_low_without_beta_raises() -> None:
    with pytest.raises((ValidationError, SchemaError)):
        PosteriorBlock(hdi_low=0.1, hdi_high=0.5)


def test_posterior_block_hdi_high_without_beta_raises() -> None:
    with pytest.raises((ValidationError, SchemaError)):
        PosteriorBlock(hdi_high=0.5)


def test_posterior_block_hdi_low_alone_without_beta_raises() -> None:
    with pytest.raises((ValidationError, SchemaError)):
        PosteriorBlock(hdi_low=0.1)


# ---------------------------------------------------------------------------
# EdgeRecord — id required
# ---------------------------------------------------------------------------


def _minimal_edge(**kwargs: object) -> dict:
    base: dict = {
        "id": 1,
        "source": "a",
        "target": "b",
        "description": "test edge",
    }
    base.update(kwargs)
    return base


def test_edge_record_valid_minimal() -> None:
    e = EdgeRecord(**_minimal_edge())
    assert e.id == 1
    assert e.edge_status == EdgeStatus.unknown
    assert e.identification == Identification.none


def test_edge_record_missing_id_raises() -> None:
    data = _minimal_edge()
    del data["id"]
    with pytest.raises((ValidationError, SchemaError)):
        EdgeRecord(**data)


# ---------------------------------------------------------------------------
# EdgeRecord — identification defaults to Identification.none + DeprecationWarning
# ---------------------------------------------------------------------------


def test_edge_record_missing_identification_defaults_to_none() -> None:
    data = _minimal_edge()
    # no 'identification' key
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        e = EdgeRecord(**data)
    assert e.identification == Identification.none
    deprecation_msgs = [str(w.message) for w in caught if issubclass(w.category, DeprecationWarning)]
    assert any("identification" in m for m in deprecation_msgs), (
        f"Expected DeprecationWarning mentioning 'identification'; got: {deprecation_msgs}"
    )


def test_edge_record_explicit_identification_no_warning() -> None:
    data = _minimal_edge(identification="observational")
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        EdgeRecord(**data)
    deprecation_msgs = [w for w in caught if issubclass(w.category, DeprecationWarning)]
    assert not deprecation_msgs, "No DeprecationWarning expected when identification is explicit"


# ---------------------------------------------------------------------------
# EdgeRecord — illegal enum values
# ---------------------------------------------------------------------------


def test_edge_record_illegal_edge_status_raises() -> None:
    with pytest.raises((ValidationError, SchemaError)):
        EdgeRecord(**_minimal_edge(edge_status="foo"))


def test_edge_record_illegal_identification_raises() -> None:
    with pytest.raises((ValidationError, SchemaError)):
        EdgeRecord(**_minimal_edge(identification="guessed"))


# ---------------------------------------------------------------------------
# EdgeRecord — eliminated ↔ eliminated_by coupling
# ---------------------------------------------------------------------------


def _ref_list() -> list[dict]:
    return [{"task": "t001", "description": "provenance"}]


def test_edge_record_eliminated_with_provenance_valid() -> None:
    e = EdgeRecord(**_minimal_edge(edge_status="eliminated", eliminated_by=_ref_list()))
    assert e.edge_status == EdgeStatus.eliminated
    assert e.eliminated_by is not None


def test_edge_record_eliminated_without_provenance_raises() -> None:
    with pytest.raises((ValidationError, SchemaError)):
        EdgeRecord(**_minimal_edge(edge_status="eliminated"))


def test_edge_record_not_eliminated_with_eliminated_by_raises() -> None:
    with pytest.raises((ValidationError, SchemaError)):
        EdgeRecord(**_minimal_edge(edge_status="supported", eliminated_by=_ref_list()))


def test_edge_record_eliminated_empty_list_raises() -> None:
    """eliminated_by=[] (empty, falsy) should also fail."""
    with pytest.raises((ValidationError, SchemaError)):
        EdgeRecord(**_minimal_edge(edge_status="eliminated", eliminated_by=[]))


# ---------------------------------------------------------------------------
# EdgesYamlFile — duplicate (source, target) pairs
# ---------------------------------------------------------------------------


def _file_data(*edges: dict) -> dict:
    return {"dag": "test-dag", "edges": list(edges)}


def test_edges_yaml_file_valid() -> None:
    data = _file_data(
        {"id": 1, "source": "a", "target": "b", "description": "e1"},
        {"id": 2, "source": "b", "target": "c", "description": "e2"},
    )
    parsed = EdgesYamlFile(**data)
    assert len(parsed.edges) == 2


def test_edges_yaml_file_duplicate_source_target_raises() -> None:
    data = _file_data(
        {"id": 1, "source": "a", "target": "b", "description": "e1"},
        {"id": 2, "source": "a", "target": "b", "description": "duplicate"},
    )
    with pytest.raises((ValidationError, SchemaError)):
        EdgesYamlFile(**data)


def test_edges_yaml_file_same_source_different_target_valid() -> None:
    data = _file_data(
        {"id": 1, "source": "a", "target": "b", "description": "e1"},
        {"id": 2, "source": "a", "target": "c", "description": "e2"},
    )
    parsed = EdgesYamlFile(**data)
    assert len(parsed.edges) == 2


def test_edges_yaml_file_empty_edges_valid() -> None:
    parsed = EdgesYamlFile(**{"dag": "empty-dag", "edges": []})
    assert parsed.edges == []


# ---------------------------------------------------------------------------
# Sanity fixture: h1-progression.edges.yaml must parse cleanly
# ---------------------------------------------------------------------------


def test_mm30_h1_progression_parses_cleanly() -> None:
    fixture = Path("/mnt/ssd/Dropbox/r/mm30/doc/figures/dags/h1-progression.edges.yaml")
    if not fixture.exists():
        pytest.skip("mm30 fixture not available")
    data = yaml.safe_load(fixture.read_text())
    parsed = EdgesYamlFile(**data)
    assert len(parsed.edges) == 6

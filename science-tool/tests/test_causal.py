"""Tests for causal inquiry type system."""

from pathlib import Path

import pytest

from science_tool.graph.store import (
    INITIAL_GRAPH_TEMPLATE,
    PREDICATE_REGISTRY,
    VALID_INQUIRY_TYPES,
    add_hypothesis,
    add_inquiry,
    get_inquiry,
)


@pytest.fixture
def graph_path(tmp_path: Path) -> Path:
    """Fresh graph file for testing."""
    gp = tmp_path / "knowledge" / "graph.trig"
    gp.parent.mkdir(parents=True)
    gp.write_text(INITIAL_GRAPH_TEMPLATE, encoding="utf-8")
    return gp


class TestInquiryType:
    def test_add_inquiry_with_type_causal(self, graph_path: Path) -> None:
        """Verify inquiry_type='causal' is stored and returned by get_inquiry."""
        add_hypothesis(graph_path, "h01", "Test hypothesis", source="paper:doi_test")
        add_inquiry(
            graph_path,
            slug="causal-test",
            label="Causal Test",
            target="hypothesis:h01",
            inquiry_type="causal",
        )
        result = get_inquiry(graph_path, "causal-test")
        assert result["inquiry_type"] == "causal"

    def test_add_inquiry_default_type_general(self, graph_path: Path) -> None:
        """Verify default inquiry_type is 'general'."""
        add_hypothesis(graph_path, "h01", "Test hypothesis", source="paper:doi_test")
        add_inquiry(
            graph_path,
            slug="general-test",
            label="General Test",
            target="hypothesis:h01",
        )
        result = get_inquiry(graph_path, "general-test")
        assert result["inquiry_type"] == "general"

    def test_invalid_inquiry_type_rejected(self, graph_path: Path) -> None:
        """Verify ValueError on invalid inquiry type."""
        add_hypothesis(graph_path, "h01", "Test hypothesis", source="paper:doi_test")
        with pytest.raises(ValueError, match="Invalid inquiry type"):
            add_inquiry(
                graph_path,
                slug="bad-type",
                label="Bad Type",
                target="hypothesis:h01",
                inquiry_type="randomized",
            )

    def test_causal_predicates_registered(self) -> None:
        """Verify new causal predicates are in PREDICATE_REGISTRY."""
        pred_names = [p["predicate"] for p in PREDICATE_REGISTRY]
        for pred in ["sci:inquiryType", "sci:treatment", "sci:outcome"]:
            assert pred in pred_names, f"{pred} not in PREDICATE_REGISTRY"

    def test_valid_inquiry_types_constant(self) -> None:
        """Verify the VALID_INQUIRY_TYPES constant."""
        assert "general" in VALID_INQUIRY_TYPES
        assert "causal" in VALID_INQUIRY_TYPES

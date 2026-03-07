"""Tests for inquiry abstraction."""

from science_tool.graph.store import PREDICATE_REGISTRY, SCI_NS


class TestOntologyExtensions:
    def test_inquiry_predicates_registered(self) -> None:
        """New inquiry predicates appear in the registry."""
        pred_names = [p["predicate"] for p in PREDICATE_REGISTRY]
        for pred in [
            "sci:target",
            "sci:boundaryRole",
            "sci:inquiryStatus",
            "sci:feedsInto",
            "sci:assumes",
            "sci:produces",
            "sci:paramValue",
            "sci:paramSource",
            "sci:paramRef",
            "sci:paramNote",
            "sci:observability",
            "sci:validatedBy",
        ]:
            assert pred in pred_names, f"{pred} not in PREDICATE_REGISTRY"

    def test_inquiry_predicates_have_inquiry_layer(self) -> None:
        """Inquiry-specific predicates use 'inquiry' layer."""
        inquiry_preds = [
            p for p in PREDICATE_REGISTRY if p["layer"] == "inquiry"
        ]
        assert len(inquiry_preds) >= 8

    def test_boundary_role_constants(self) -> None:
        """BoundaryIn and BoundaryOut are defined as URIRefs."""
        assert SCI_NS.BoundaryIn is not None
        assert SCI_NS.BoundaryOut is not None
        assert str(SCI_NS.BoundaryIn).endswith("BoundaryIn")
        assert str(SCI_NS.BoundaryOut).endswith("BoundaryOut")

    def test_inquiry_type_constants(self) -> None:
        """Inquiry entity types are defined."""
        for type_name in ["Inquiry", "Variable", "Transformation", "Assumption", "Unknown", "ValidationCheck"]:
            attr = getattr(SCI_NS, type_name)
            assert str(attr).endswith(type_name)

from science_model.profiles import CORE_PROFILE
from science_model.profiles.schema import RelationKind
from science_model.relations import relation_allows_kinds


def test_relation_kind_restricts_endpoints() -> None:
    relation = RelationKind(
        name="tests",
        predicate="sci:tests",
        source_kinds=["task", "experiment"],
        target_kinds=["hypothesis", "question"],
        layer="layer/core",
    )
    assert "hypothesis" in relation.target_kinds
    assert relation.layer == "layer/core"


def test_evidence_line_as_supports_source() -> None:
    supports = next(r for r in CORE_PROFILE.relation_kinds if r.name == "supports")
    assert relation_allows_kinds(supports, "evidence-line", "proposition")
    assert relation_allows_kinds(supports, "evidence-line", "hypothesis")


def test_evidence_line_as_disputes_source() -> None:
    disputes = next(r for r in CORE_PROFILE.relation_kinds if r.name == "disputes")
    assert relation_allows_kinds(disputes, "evidence-line", "hypothesis")
    assert relation_allows_kinds(disputes, "evidence-line", "proposition")


def test_bears_on_reaches_evidence_line() -> None:
    bears_on = next(r for r in CORE_PROFILE.relation_kinds if r.name == "bears_on")
    assert relation_allows_kinds(bears_on, "observation", "evidence-line")

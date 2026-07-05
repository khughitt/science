from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pytest
from rdflib import Dataset, Graph, Literal, URIRef
from rdflib.namespace import PROV, RDF

from science_tool.annotation import io as anno_io
from science_tool.annotation.cross_paper_evidence import (
    CrossPaperEvidenceError,
    LiteratureAssertion,
    build_cross_paper_evidence_report,
    emit_literature_evidence,
    derive_literature_evidence,
    lit_assertion_uri,
    proposition_source_refs_map,
)
from science_tool.annotation.model import (
    Annotation,
    Motivation,
    SpecificResource,
    Status,
    TextQuoteSelector,
    TextualBody,
)
from science_tool.graph.io import CITO_NS, PROJECT_NS, SCI_NS, entity_uri_for_ref
from science_tool.graph.grounding import ground_proposition, load_grounding_graphs
from science_tool.graph.materialize import materialize_graph


_CREATED = datetime(2026, 6, 30, tzinfo=timezone.utc)
_ANN_REF = "annotation:entities/papers/Smith2020.source#a-1"


def _assertion(stance: str) -> LiteratureAssertion:
    return LiteratureAssertion(
        proposition_ref="proposition:p",
        paper_ref="paper:Smith2020",
        stance=stance,
        annotation_id="a-1",
        sidecar="entities/papers/Smith2020.source.anno.trig",
        annotation_ref=_ANN_REF,
    )


def _graphs() -> tuple[Dataset, Graph, Graph]:
    dataset = Dataset()
    return (
        dataset,
        dataset.graph(PROJECT_NS["graph/knowledge"]),
        dataset.graph(PROJECT_NS["graph/provenance"]),
    )


def _ann(
    frag: str,
    *,
    stance: str,
    promoted_to: str = "proposition:p",
) -> Annotation:
    body = json.dumps({"section": "abstract", "stance": stance})
    return Annotation(
        id=frag,
        target=SpecificResource(
            source="Smith2020.source.md",
            selector=TextQuoteSelector(exact=frag, prefix="", suffix=""),
        ),
        bodies=(TextualBody(value=body, format="application/json"),),
        motivation=Motivation.CLASSIFYING,
        annotation_type="proposition",
        source="llm-annot:m:paper-annotate-v1",
        status=Status.OPEN,
        creator="paper-annotate",
        created=_CREATED,
        content_hash="0" * 64,
        promoted_to=promoted_to,
    )


def _write_paper_sidecar(root: Path, anns: list[Annotation]) -> None:
    md = root / "entities" / "papers" / "Smith2020.source.md"
    md.parent.mkdir(parents=True, exist_ok=True)
    md.write_text("Body.\n", encoding="utf-8")
    anno_io.write_sidecar(anno_io.sidecar_for_markdown(md), anno_io.Sidecar(annotations=tuple(anns)))


@dataclass(frozen=True)
class _Entity:
    canonical_id: str
    kind: str
    source_refs: tuple[str, ...]


def test_emit_literature_evidence_support_line_full_triple_shape() -> None:
    _, knowledge, provenance = _graphs()

    emit_literature_evidence(knowledge, provenance, [_assertion("asserted")])

    line_uri = lit_assertion_uri("proposition:p", "paper:Smith2020", "asserted")
    prop_uri = entity_uri_for_ref("proposition:p")
    paper_uri = entity_uri_for_ref("paper:Smith2020")
    assert (line_uri, RDF.type, SCI_NS.EvidenceLine) in knowledge
    assert (line_uri, CITO_NS.supports, prop_uri) in knowledge
    assert (line_uri, SCI_NS.evidenceType, Literal("literature")) in provenance
    assert (line_uri, SCI_NS.evidenceRole, Literal("proxy_support")) in provenance
    assert (line_uri, SCI_NS.evidenceStrength, Literal("moderate")) in provenance
    assert (line_uri, SCI_NS.evidenceIndependence, Literal("independent")) in provenance
    assert (line_uri, SCI_NS.independenceGroup, Literal("literature-paper:Smith2020")) in provenance
    assert (line_uri, PROV.wasDerivedFrom, paper_uri) in provenance


def test_emit_literature_evidence_negated_stance_emits_disputes() -> None:
    _dataset, knowledge, provenance = _graphs()

    emit_literature_evidence(knowledge, provenance, [_assertion("negated")])

    line_uri = lit_assertion_uri("proposition:p", "paper:Smith2020", "negated")
    assert (line_uri, CITO_NS.disputes, entity_uri_for_ref("proposition:p")) in knowledge
    assert (line_uri, CITO_NS.supports, entity_uri_for_ref("proposition:p")) not in knowledge


def test_emit_literature_evidence_hypothesized_stance_uses_weak_background_support() -> None:
    _, knowledge, provenance = _graphs()

    emit_literature_evidence(knowledge, provenance, [_assertion("hypothesized")])

    line_uri = lit_assertion_uri("proposition:p", "paper:Smith2020", "hypothesized")
    assert (line_uri, CITO_NS.supports, entity_uri_for_ref("proposition:p")) in knowledge
    assert (line_uri, SCI_NS.evidenceRole, Literal("background_constraint")) in provenance
    assert (line_uri, SCI_NS.evidenceStrength, Literal("weak")) in provenance


def test_derive_literature_evidence_raises_aggregate_error_on_scanner_faults(tmp_path: Path) -> None:
    _write_paper_sidecar(tmp_path, [_ann("a-1", stance="maybe")])
    dataset = Dataset()

    with pytest.raises(CrossPaperEvidenceError) as exc:
        derive_literature_evidence(dataset, tmp_path, {"proposition:p": frozenset({"paper:Smith2020", _ANN_REF})})

    assert [fault.reason for fault in exc.value.faults] == ["invalid-stance"]


def test_derive_literature_evidence_emits_when_clean_and_requires_both_source_refs(tmp_path: Path) -> None:
    _write_paper_sidecar(tmp_path, [_ann("a-1", stance="asserted")])
    dataset = Dataset()

    derive_literature_evidence(
        dataset,
        tmp_path,
        {"proposition:p": frozenset({"paper:Smith2020", _ANN_REF})},
    )

    line_uri = lit_assertion_uri("proposition:p", "paper:Smith2020", "asserted")
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
    provenance = dataset.graph(PROJECT_NS["graph/provenance"])
    assert (line_uri, CITO_NS.supports, entity_uri_for_ref("proposition:p")) in knowledge
    assert (line_uri, PROV.wasDerivedFrom, entity_uri_for_ref("paper:Smith2020")) in provenance


def test_proposition_source_refs_map_filters_entities_by_kind() -> None:
    entities = [
        _Entity("proposition:p", "proposition", ("paper:Smith2020", _ANN_REF)),
        _Entity("question:q", "question", ("paper:Smith2020",)),
    ]

    assert proposition_source_refs_map(entities) == {
        "proposition:p": frozenset({"paper:Smith2020", _ANN_REF})
    }


def _manifest(root: Path) -> None:
    (root / "science.yaml").write_text(
        "name: test\nknowledge_profiles:\n  local: local\n",
        encoding="utf-8",
    )


def _paper_entity(root: Path, citekey: str) -> None:
    path = root / "entities" / "papers" / f"{citekey}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f"---\nid: paper:{citekey}\nkind: paper\ntitle: {citekey}\nstatus: active\n---\n\nAbstract.\n",
        encoding="utf-8",
    )


def _proposition_entity(root: Path, slug: str, source_refs: list[str]) -> None:
    path = root / "entities" / "propositions" / f"{slug}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    refs = "".join(f"  - {ref}\n" for ref in source_refs)
    path.write_text(
        f"---\nid: proposition:{slug}\nkind: proposition\ntitle: {slug}\nstatus: active\n"
        f"source_refs:\n{refs}---\n\nClaim.\n",
        encoding="utf-8",
    )


def _promoted_ann(frag: str, *, stance: str, slug: str = "claim") -> Annotation:
    body = json.dumps({"section": "results", "stance": stance})
    return Annotation(
        id=frag,
        target=SpecificResource(
            source="x.source.md",
            selector=TextQuoteSelector(exact=frag, prefix="", suffix=""),
        ),
        bodies=(TextualBody(value=body, format="application/json"),),
        motivation=Motivation.CLASSIFYING,
        annotation_type="proposition",
        source="llm-annot:m:paper-annotate-v1",
        status=Status.OPEN,
        creator="paper-annotate",
        created=_CREATED,
        content_hash="0" * 64,
        promoted_to=f"proposition:{slug}",
    )


def _paper_with_promoted(root: Path, citekey: str, *, stance: str, slug: str = "claim") -> None:
    _paper_entity(root, citekey)
    md = root / "entities" / "papers" / f"{citekey}.source.md"
    md.write_text("Results show the claim.\n", encoding="utf-8")
    anno_io.write_sidecar(
        anno_io.sidecar_for_markdown(md),
        anno_io.Sidecar(
            annotations=(_promoted_ann(f"{citekey}-1", stance=stance, slug=slug),)
        ),
    )


def _ann_ref(citekey: str) -> str:
    return f"annotation:entities/papers/{citekey}.source#{citekey}-1"


def _scaffold_three_papers(root: Path) -> None:
    _manifest(root)
    papers = ["A2020", "B2021", "C2022"]
    source_refs = [f"paper:{citekey}" for citekey in papers] + [
        _ann_ref(citekey) for citekey in papers
    ]
    _proposition_entity(root, "claim", source_refs)
    _paper_with_promoted(root, "A2020", stance="asserted")
    _paper_with_promoted(root, "B2021", stance="asserted")
    _paper_with_promoted(root, "C2022", stance="negated")


def test_corpus_shaped_three_paper_smoke_fixture_is_contested_without_well_supported(
    tmp_path: Path,
) -> None:
    _manifest(tmp_path)
    papers = ["Alpha2026", "Beta2026", "Gamma2026"]
    source_refs = [f"paper:{citekey}" for citekey in papers] + [
        _ann_ref(citekey) for citekey in papers
    ]
    _proposition_entity(tmp_path, "p", source_refs)
    _paper_with_promoted(tmp_path, "Alpha2026", stance="asserted", slug="p")
    _paper_with_promoted(tmp_path, "Beta2026", stance="asserted", slug="p")
    _paper_with_promoted(tmp_path, "Gamma2026", stance="negated", slug="p")

    report = build_cross_paper_evidence_report(tmp_path)
    row = {item["proposition"]: item for item in report["propositions"]}["proposition:p"]

    assert report["summary"]["propositions"] == 1
    assert report["summary"]["units"] == 3
    assert row["belief"]["contested"] is True
    assert row["belief"]["belief_magnitude"] != "well_supported"

    trig = materialize_graph(tmp_path, strict=False)
    knowledge, provenance = load_grounding_graphs(trig)
    result = ground_proposition("proposition:p", knowledge, provenance, floor="fragile")

    assert result.support_units == 2
    assert result.dispute_units == 1
    assert result.contested is True
    assert result.belief_magnitude != "well_supported"


def test_e2e_two_papers_assert_one_disputes_is_contested(tmp_path: Path) -> None:
    _scaffold_three_papers(tmp_path)

    trig = materialize_graph(tmp_path, strict=False)
    knowledge, provenance = load_grounding_graphs(trig)
    result = ground_proposition("proposition:claim", knowledge, provenance, floor="fragile")

    assert result.support_units == 2
    assert result.dispute_units == 1
    assert result.contested is True
    assert result.belief_magnitude == "supported"


def test_e2e_behavior_neutral_when_no_promoted_statements(tmp_path: Path) -> None:
    _manifest(tmp_path)
    _proposition_entity(tmp_path, "claim", ["paper:A2020"])
    _paper_entity(tmp_path, "A2020")

    trig = materialize_graph(tmp_path, strict=False)
    knowledge, provenance = load_grounding_graphs(trig)
    result = ground_proposition("proposition:claim", knowledge, provenance, floor="fragile")

    assert result.support_units == 0
    assert result.dispute_units == 0


def test_e2e_virtual_edges_enter_bears_on_closure(tmp_path: Path) -> None:
    _scaffold_three_papers(tmp_path)

    trig = materialize_graph(tmp_path, strict=False)
    dataset = Dataset()
    dataset.parse(source=str(trig), format="trig")
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
    prop = URIRef(PROJECT_NS["proposition/claim"])

    bears_on = list(knowledge.triples((None, SCI_NS.bearsOn, prop)))

    assert any("evidence-line/lit-assertion/" in str(subject) for subject, _, _ in bears_on)


def test_e2e_stale_promoted_to_fails_build(tmp_path: Path) -> None:
    _manifest(tmp_path)
    _proposition_entity(tmp_path, "claim", ["paper:A2020"])
    _paper_with_promoted(tmp_path, "A2020", stance="asserted", slug="ghost")

    with pytest.raises(CrossPaperEvidenceError):
        materialize_graph(tmp_path, strict=False)


def test_same_paper_mixed_stance_yields_contested_group() -> None:
    _, knowledge, provenance = _graphs()
    support = LiteratureAssertion(
        proposition_ref="proposition:p",
        paper_ref="paper:A",
        stance="asserted",
        annotation_id="ann-1",
        sidecar="s",
        annotation_ref="annotation:entities/papers/A.source#ann-1",
    )
    dispute = LiteratureAssertion(
        proposition_ref="proposition:p",
        paper_ref="paper:A",
        stance="negated",
        annotation_id="ann-2",
        sidecar="s",
        annotation_ref="annotation:entities/papers/A.source#ann-2",
    )

    emit_literature_evidence(knowledge, provenance, [support, dispute])

    from science_tool.graph.belief import aggregate_belief, collect_evidence_units

    belief = aggregate_belief(
        collect_evidence_units(knowledge, provenance, [entity_uri_for_ref("proposition:p")])
    )
    assert belief.contested is True
    assert belief.contested_groups == {"literature-paper:A"}

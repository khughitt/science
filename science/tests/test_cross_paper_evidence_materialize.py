from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pytest
from rdflib import Dataset, Graph, Literal
from rdflib.namespace import PROV, RDF

from science_tool.annotation import io as anno_io
from science_tool.annotation.cross_paper_evidence import (
    CrossPaperEvidenceError,
    LiteratureAssertion,
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


_CREATED = datetime(2026, 6, 30, tzinfo=timezone.utc)
_ANN_REF = "annotation:entities/papers/Smith2020.source#a-1"


def _assertion(stance: str) -> LiteratureAssertion:
    return LiteratureAssertion(
        "proposition:p",
        "paper:Smith2020",
        stance,
        "a-1",
        "entities/papers/Smith2020.source.anno.trig",
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

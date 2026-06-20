from __future__ import annotations

from datetime import date
from pathlib import Path

from rdflib import Dataset, Literal, URIRef
from rdflib.namespace import RDF, SKOS

from science_tool.graph.io import PROJECT_NS, SCI_NS
from science_tool.wander.context import assemble_bundle
from science_tool.wander.provenance import PROV_WAS_DERIVED_FROM, SCHEMA_IDENTIFIER


def _u(path: str) -> URIRef:
    return URIRef(PROJECT_NS[path])


def _build_dataset(tmp_path: Path) -> tuple[Dataset, Path]:
    dataset = Dataset()
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
    provenance = dataset.graph(PROJECT_NS["graph/provenance"])

    h1 = _u("hypothesis/h1")
    knowledge.add((h1, RDF.type, SCI_NS.Hypothesis))
    knowledge.add((h1, SKOS.prefLabel, Literal("First")))
    knowledge.add((h1, SCI_NS.freshnessState, Literal("fresh")))

    source_file = tmp_path / "doc" / "h1.md"
    source_file.parent.mkdir(parents=True)
    source_file.write_text("a" * 200)
    source_uri = URIRef(PROJECT_NS["source/doc_h1.md"])
    provenance.add((h1, PROV_WAS_DERIVED_FROM, source_uri))
    provenance.add((source_uri, SCHEMA_IDENTIFIER, Literal(str(source_file))))
    return dataset, source_file


def _sample_for_walk_from_dataset(dataset: Dataset):
    from science_tool.graph.attention import (
        compute_attention_candidates,
        weighted_sample_without_replacement,
    )

    candidates = compute_attention_candidates(dataset, today=date(2026, 5, 9))
    return weighted_sample_without_replacement(candidates, limit=len(candidates), seed=0)


def test_bundle_includes_candidate_components_neighbors_filesystem(tmp_path: Path) -> None:
    dataset, source_file = _build_dataset(tmp_path)

    candidates = _sample_for_walk_from_dataset(dataset)
    bundle = assemble_bundle(candidates[0], dataset, repo_root=tmp_path)

    assert bundle.entity_id == "hypothesis:h1"
    assert bundle.label == "First"
    assert bundle.kind == "hypothesis"
    assert bundle.weight > 0
    assert bundle.components["incoming_bears_on"] == 0.0
    assert bundle.source_path == str(source_file)
    assert bundle.content_length == 200
    assert bundle.mtime is not None
    assert bundle.neighbors.bears_on_incoming == []
    assert bundle.active_references == []


def test_bundle_omits_filesystem_fields_when_no_source(tmp_path: Path) -> None:
    dataset = Dataset()
    knowledge = dataset.graph(PROJECT_NS["graph/knowledge"])
    h1 = _u("hypothesis/h1")
    knowledge.add((h1, RDF.type, SCI_NS.Hypothesis))
    knowledge.add((h1, SKOS.prefLabel, Literal("First")))
    knowledge.add((h1, SCI_NS.freshnessState, Literal("fresh")))

    candidates = _sample_for_walk_from_dataset(dataset)
    bundle = assemble_bundle(candidates[0], dataset, repo_root=tmp_path)

    assert bundle.source_path is None
    assert bundle.mtime is None
    assert bundle.content_length is None

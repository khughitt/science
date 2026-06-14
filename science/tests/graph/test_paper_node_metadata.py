from __future__ import annotations

from pathlib import Path

from rdflib import Literal
from rdflib import URIRef
from rdflib.namespace import PROV, RDF, SKOS

from science_tool.graph.io import DCAT_NS, DCTERMS_NS
from science_tool.graph.materialize import PROJECT_NS, SCI_NS, _build_dataset_from_sources, _entity_uri
from science_tool.graph.sources import load_project_sources

_MANIFEST = "name: demo\nprofile: research\nprofiles: {local: local}\nlayout_version: 3\n"


def _write(root: Path, bib: str) -> None:
    (root / "science.yaml").write_text(_MANIFEST, encoding="utf-8")
    (root / "papers").mkdir(parents=True, exist_ok=True)
    (root / "papers" / "references.bib").write_text(bib, encoding="utf-8")


def test_paper_node_carries_bib_metadata(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "@article{Smith2024,\n  title = {Cells},\n  year = {2024},\n  doi = {10.1/x},\n  url = {https://ex/x},\n}\n",
    )
    sources = load_project_sources(tmp_path, include_commons=False, strict_core_schema=False, strict_identity=False)
    ds = _build_dataset_from_sources(sources)
    knowledge = ds.graph(PROJECT_NS["graph/knowledge"])
    uri = _entity_uri("paper:Smith2024")
    assert (uri, SKOS.prefLabel, Literal("Cells")) in knowledge  # title (pre-existing path)
    assert (uri, RDF.type, PROV.Entity) in knowledge  # NEW: reference/provenance typing
    assert (uri, DCTERMS_NS.date, Literal("2024")) in knowledge  # NEW: year
    assert (uri, SCI_NS.doi, Literal("10.1/x")) in knowledge  # NEW: doi
    assert (uri, DCAT_NS.downloadURL, URIRef("https://ex/x")) in knowledge  # NEW: url (design surface)


def test_book_node_carries_bib_metadata(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "@book{Kelly1982,\n  title = {Control},\n  year = {1982},\n  doi = {10.1/k},\n  url = {https://ex/k},\n}\n",
    )
    sources = load_project_sources(tmp_path, include_commons=False, strict_core_schema=False, strict_identity=False)
    ds = _build_dataset_from_sources(sources)
    knowledge = ds.graph(PROJECT_NS["graph/knowledge"])
    uri = _entity_uri("book:Kelly1982")
    assert (uri, SKOS.prefLabel, Literal("Control")) in knowledge  # title
    assert (uri, RDF.type, PROV.Entity) in knowledge  # provenance typing
    assert (uri, DCTERMS_NS.date, Literal("1982")) in knowledge  # year
    assert (uri, SCI_NS.doi, Literal("10.1/k")) in knowledge  # doi
    assert (uri, DCAT_NS.downloadURL, URIRef("https://ex/k")) in knowledge  # url


def test_book_node_without_optional_fields_emits_only_type_and_label(tmp_path: Path) -> None:
    _write(tmp_path, "@book{BareBook2000,\n  title = {Bare},\n}\n")  # no year/doi/url
    sources = load_project_sources(tmp_path, include_commons=False, strict_core_schema=False, strict_identity=False)
    ds = _build_dataset_from_sources(sources)
    knowledge = ds.graph(PROJECT_NS["graph/knowledge"])
    uri = _entity_uri("book:BareBook2000")
    assert (uri, SKOS.prefLabel, Literal("Bare")) in knowledge  # present
    assert (uri, RDF.type, PROV.Entity) in knowledge  # present (unconditional)
    # absent bib fields emit NO predicate (not an empty/None literal):
    assert not any(knowledge.triples((uri, DCTERMS_NS.date, None)))
    assert not any(knowledge.triples((uri, SCI_NS.doi, None)))
    assert not any(knowledge.triples((uri, DCAT_NS.downloadURL, None)))


def test_paper_node_without_optional_fields_emits_only_type_and_label(tmp_path: Path) -> None:
    _write(tmp_path, "@article{Bare2000,\n  title = {Bare},\n}\n")  # no year/doi/url
    sources = load_project_sources(tmp_path, include_commons=False, strict_core_schema=False, strict_identity=False)
    ds = _build_dataset_from_sources(sources)
    knowledge = ds.graph(PROJECT_NS["graph/knowledge"])
    uri = _entity_uri("paper:Bare2000")
    assert (uri, SKOS.prefLabel, Literal("Bare")) in knowledge  # present
    assert (uri, RDF.type, PROV.Entity) in knowledge  # present (unconditional)
    # absent bib fields emit NO predicate (not an empty/None literal):
    assert not any(knowledge.triples((uri, DCTERMS_NS.date, None)))
    assert not any(knowledge.triples((uri, SCI_NS.doi, None)))
    assert not any(knowledge.triples((uri, DCAT_NS.downloadURL, None)))

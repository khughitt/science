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
